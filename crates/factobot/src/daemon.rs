//! The factobot daemon: owns one game server and its RCON connection, and
//! serves the socket protocol in `protocol.rs` on two sockets:
//!
//! - the agent socket, with the agent-facing methods only;
//! - the dev socket, with those plus harness tools (`lua`, `reload`,
//!   `snapshot`, `world_hash`, `milestones`, `screenshot`). Agents never get
//!   this socket.
//!
//! Optionally it also supervises graphical spectator clients (`viewer.rs`):
//! a camera for screenshots (the dev `screenshot` and the agent's `screen`)
//! and a window for watching live. Every call on either socket is appended
//! to `<run_dir>/calls.jsonl`.

use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result, bail};
use base64::Engine as _;
use factobot::protocol::{
    ErrorBody, ErrorCode, PNG_FIELD, PROTOCOL_VERSION, Request, Response, wait_timeout_error,
};
use serde_json::{Value, json};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::{UnixListener, UnixStream};
use tokio::signal::unix::{SignalKind, signal};
use tokio::sync::Mutex;

use crate::rcon::Rcon;
use crate::server::{Server, ServerConfig};
use crate::viewer::{self, Viewer};

/// How long a camera or viewer client may take to load and join.
const JOIN_TIMEOUT: Duration = Duration::from_secs(180);
/// How long the camera may take to write a screenshot.
const SCREENSHOT_TIMEOUT: Duration = Duration::from_secs(60);

/// Graphical clients the daemon keeps connected.
#[derive(Debug, Clone)]
pub struct Viewers {
    /// Extracted graphical build: contains `bin/x64/factorio` and `data/`.
    pub client_dir: PathBuf,
    pub kinds: Vec<viewer::Kind>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Surface {
    Agent,
    Dev,
}

impl Surface {
    fn name(self) -> &'static str {
        match self {
            Self::Agent => "agent",
            Self::Dev => "dev",
        }
    }
}

struct Game {
    server: Server,
    rcon: Rcon,
    viewers: Vec<Viewer>,
}

impl Game {
    /// Start the server, then each viewer, and wait until every viewer has
    /// joined as a spectator. A window viewer with no usable X11 display
    /// fails here, before Factorio starts (decision 65).
    async fn start(config: &ServerConfig, viewers: &Viewers) -> Result<Self> {
        if viewers.kinds.contains(&viewer::Kind::Viewer) {
            viewer::require_window_display().await?;
        }
        let (server, rcon) = Server::start(config).await?;
        let mut game = Self {
            server,
            rcon,
            viewers: Vec::new(),
        };
        for &kind in &viewers.kinds {
            let viewer = Viewer::start(
                kind,
                &viewers.client_dir,
                &config.run_dir.join("mods"),
                &config.run_dir,
                config.game_addr(),
            )
            .await?;
            game.viewers.push(viewer);
            game.wait_until_joined(kind).await?;
            let viewer = game.viewers.last_mut().expect("viewer just pushed");
            if let Err(err) = viewer.publish_atlas().await {
                eprintln!("{}: sprite atlas not shared: {err:#}", kind.player_name());
            }
        }
        Ok(game)
    }

    async fn wait_until_joined(&mut self, kind: viewer::Kind) -> Result<()> {
        let name = kind.player_name();
        let deadline = Instant::now() + JOIN_TIMEOUT;
        let command = format!("/factobot player_connected {}", json!({ "name": name }));
        loop {
            let reply: Value = serde_json::from_str(self.rcon.exec(&command).await?.trim())?;
            if reply["result"] == Value::Bool(true) {
                return Ok(());
            }
            let viewer = self.viewers.last_mut().expect("viewer just pushed");
            if let Some(status) = viewer.exit_status() {
                bail!(
                    "{name} exited before joining ({status}); see {}",
                    viewer
                        .write_dir
                        .parent()
                        .unwrap_or(&viewer.write_dir)
                        .join("client.log")
                        .display()
                );
            }
            if Instant::now() > deadline {
                bail!("{name} did not join within {JOIN_TIMEOUT:?}");
            }
            tokio::time::sleep(Duration::from_millis(500)).await;
        }
    }

    /// Disconnect the viewers, then save and stop the server.
    async fn stop(&mut self) -> Result<()> {
        for viewer in &mut self.viewers {
            viewer.stop().await;
        }
        self.server.stop(Some(&mut self.rcon)).await
    }

    fn camera_dir(&self) -> Option<PathBuf> {
        self.viewers
            .iter()
            .find(|viewer| viewer.kind == viewer::Kind::Camera)
            .map(|camera| camera.write_dir.clone())
    }
}

struct State {
    config: ServerConfig,
    viewers: Viewers,
    game: Mutex<Game>,
    calls: std::sync::Mutex<fs::File>,
    screenshots: AtomicU64,
}

pub struct Sockets {
    pub agent: PathBuf,
    pub dev: PathBuf,
}

pub async fn run(config: ServerConfig, viewers: Viewers, sockets: Sockets) -> Result<()> {
    // Install handlers before start-up: it can take a minute, and a signal
    // that hit the default handler would orphan the Factorio child. They stay
    // installed until the daemon exits, so a second Ctrl-C, or the second
    // SIGTERM `systemctl stop` sends, cannot cut the save short. SIGHUP is a
    // closed terminal.
    let mut sigint = signal(SignalKind::interrupt())?;
    let mut sigterm = signal(SignalKind::terminate())?;
    let mut sighup = signal(SignalKind::hangup())?;
    let agent_listener = bind(&sockets.agent)?;
    let dev_listener = match bind(&sockets.dev) {
        Ok(listener) => listener,
        Err(err) => {
            let _ = fs::remove_file(&sockets.agent);
            return Err(err);
        }
    };
    let remove_sockets = || {
        let _ = fs::remove_file(&sockets.agent);
        let _ = fs::remove_file(&sockets.dev);
    };
    let calls_path = config.run_dir.join("calls.jsonl");
    let calls = match fs::create_dir_all(&config.run_dir).and_then(|()| {
        fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&calls_path)
    }) {
        Ok(calls) => calls,
        Err(err) => {
            remove_sockets();
            return Err(
                anyhow::Error::from(err).context(format!("opening {}", calls_path.display()))
            );
        }
    };

    let started = tokio::select! {
        // Dropping the start future kills the children (`kill_on_drop`).
        _ = sigint.recv() => None,
        _ = sigterm.recv() => None,
        _ = sighup.recv() => None,
        started = Game::start(&config, &viewers) => Some(started),
    };
    let game = match started {
        Some(Ok(game)) => game,
        Some(Err(err)) => {
            remove_sockets();
            return Err(err);
        }
        None => {
            remove_sockets();
            return Ok(());
        }
    };
    let state = Arc::new(State {
        config,
        viewers,
        game: Mutex::new(game),
        calls: std::sync::Mutex::new(calls),
        screenshots: AtomicU64::new(0),
    });
    eprintln!(
        "factobot daemon ready on {} (dev: {})",
        sockets.agent.display(),
        sockets.dev.display()
    );

    let outcome = tokio::select! {
        _ = sigint.recv() => Ok(()),
        _ = sigterm.recv() => Ok(()),
        _ = sighup.recv() => Ok(()),
        err = watch_server(state.clone()) => Err(err),
        err = accept_loop(agent_listener, state.clone(), Surface::Agent) => Err(err),
        err = accept_loop(dev_listener, state.clone(), Surface::Dev) => Err(err),
    };

    remove_sockets();
    if outcome.is_ok() {
        // Not `eprintln!`: on a hung-up terminal the write fails with EIO,
        // and the panic would skip the save and kill the server.
        let _ = writeln!(
            std::io::stderr(),
            "factobot daemon stopping: saving the world"
        );
    }
    state.game.lock().await.stop().await?;
    outcome
}

/// Fails once the game server has exited outside a restart: after a crash,
/// or when `reload`/`snapshot` could not start it again. The daemon then
/// exits non-zero instead of answering `unavailable` forever.
async fn watch_server(state: Arc<State>) -> anyhow::Error {
    loop {
        tokio::time::sleep(Duration::from_millis(500)).await;
        if let Some(status) = state.game.lock().await.server.exit_status() {
            return anyhow::anyhow!(
                "Factorio exited unexpectedly ({status}); see {}",
                state.config.run_dir.join("server.log").display()
            );
        }
    }
}

fn bind(socket: &Path) -> Result<UnixListener> {
    if let Some(dir) = socket.parent().filter(|dir| !dir.exists()) {
        fs::create_dir_all(dir)?;
        fs::set_permissions(dir, fs::Permissions::from_mode(0o700))?;
    }
    if socket.exists() {
        if std::os::unix::net::UnixStream::connect(socket).is_ok() {
            bail!("a daemon is already listening on {}", socket.display());
        }
        fs::remove_file(socket).with_context(|| format!("removing stale {}", socket.display()))?;
    }
    UnixListener::bind(socket).with_context(|| format!("binding {}", socket.display()))
}

async fn accept_loop(listener: UnixListener, state: Arc<State>, surface: Surface) -> anyhow::Error {
    loop {
        match listener.accept().await {
            Ok((stream, _)) => {
                let state = state.clone();
                tokio::spawn(async move {
                    if let Err(err) = serve(stream, state, surface).await {
                        tracing::debug!("client connection ended: {err}");
                    }
                });
            }
            Err(err) => return err.into(),
        }
    }
}

async fn serve(stream: UnixStream, state: Arc<State>, surface: Surface) -> Result<()> {
    let (read, mut write) = stream.into_split();
    let mut lines = BufReader::new(read).lines();
    while let Some(line) = lines.next_line().await? {
        let started = Instant::now();
        let (response, request, tick) = match serde_json::from_str::<Request>(&line) {
            Ok(request) if request.v != PROTOCOL_VERSION => (
                Response::err(
                    request.id,
                    ErrorCode::BadRequest,
                    format!(
                        "protocol version {} is not supported; this daemon speaks {PROTOCOL_VERSION}",
                        request.v
                    ),
                ),
                Some(request),
                None,
            ),
            Ok(request) => {
                let ((outcome, tick), hud) = handle(&state, surface, &request).await;
                let response = match outcome {
                    Ok(result) => Response::ok(request.id, result),
                    Err(error) => Response::err(request.id, error.code, error.message),
                };
                (response.with_hud(hud), Some(request), tick)
            }
            Err(err) => (
                Response::err(0, ErrorCode::BadRequest, format!("invalid request: {err}")),
                None,
                None,
            ),
        };
        log_call(&state, surface, request.as_ref(), &response, tick, started);
        let mut out = serde_json::to_vec(&response)?;
        out.push(b'\n');
        write.write_all(&out).await?;
    }
    Ok(())
}

fn log_call(
    state: &State,
    surface: Surface,
    request: Option<&Request>,
    response: &Response,
    tick: Option<u64>,
    started: Instant,
) {
    let unix_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |elapsed| elapsed.as_millis());
    let unpictured = without_png(response);
    let entry = json!({
        "unix_ms": unix_ms,
        "duration_ms": started.elapsed().as_secs_f64() * 1000.0,
        "surface": surface.name(),
        "tick": tick,
        "method": request.map(|r| r.method.as_str()),
        "params": request.map(|r| &r.params),
        "response": unpictured.as_ref().unwrap_or(response),
    });
    let mut line = entry.to_string();
    line.push('\n');
    // One record per write, always ending in a newline. A reader that lands
    // mid-write ignores the trailing fragment, which has no newline yet.
    let mut file = state
        .calls
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner);
    if let Err(err) = file.write_all(line.as_bytes()) {
        tracing::warn!("could not append to calls.jsonl: {err}");
    }
}

/// A call's result or error, and the game tick the mod answered at: none
/// when the call never reached the mod or its reply was unreadable.
type Outcome = (Result<Value, ErrorBody>, Option<u64>);

/// Answer a request. Agent methods come back with the mod's HUD.
async fn handle(state: &State, surface: Surface, request: &Request) -> (Outcome, Option<Value>) {
    match request.method.as_str() {
        "wait" => wait_for_job(state, &request.params).await,
        method if AGENT_METHODS.contains(&method) => {
            let ((result, tick), hud) = call_mod_with_hud(state, method, &request.params).await;
            ((result.map(empty_tables_as_lists), tick), hud)
        }
        _ => (handle_other(state, surface, request).await, None),
    }
}

async fn handle_other(state: &State, surface: Surface, request: &Request) -> Outcome {
    match (surface, request.method.as_str()) {
        (_, "status") => match call_mod(state, "status", &Value::Null).await {
            (Ok(game), tick) => (
                Ok(json!({
                    "daemon": {
                        "version": env!("CARGO_PKG_VERSION"),
                        "protocol": PROTOCOL_VERSION,
                    },
                    "game": game,
                })),
                tick,
            ),
            failed => failed,
        },
        (_, "screen") => screen(state, &request.params).await,
        (Surface::Dev, "world_hash") => call_mod(state, "world_hash", &Value::Null).await,
        (Surface::Dev, "milestones") => {
            let (result, tick) = call_mod(state, "milestones", &Value::Null).await;
            (result.map(milestones_result), tick)
        }
        (Surface::Dev, "screenshot") => screenshot(state, &request.params).await,
        (Surface::Dev, "lua") => match request.params.get("code").and_then(Value::as_str) {
            Some(code) => {
                call_command(state, &format!("/factobot-dev {code}"))
                    .await
                    .0
            }
            None => (
                Err(bad_params("lua needs params {\"code\": \"<lua>\"}")),
                None,
            ),
        },
        (Surface::Dev, "reload") => (restart(state, None).await.map(|()| json!({})), None),
        (Surface::Dev, "snapshot") => match request.params.get("path").and_then(Value::as_str) {
            Some(path) => {
                let path = PathBuf::from(path);
                (
                    restart(state, Some(&path))
                        .await
                        .map(|()| json!({ "path": path })),
                    None,
                )
            }
            None => (
                Err(bad_params(
                    "snapshot needs params {\"path\": \"<file.zip>\"}",
                )),
                None,
            ),
        },
        (_, other) => (
            Err(ErrorBody {
                code: ErrorCode::UnknownMethod,
                message: format!("unknown method {other:?}"),
            }),
            None,
        ),
    }
}

fn bad_params(message: &str) -> ErrorBody {
    ErrorBody {
        code: ErrorCode::BadRequest,
        message: message.to_owned(),
    }
}

/// Stop the server (it saves on quit), optionally copy the save to
/// `snapshot`, and start it again from that save with the current mod code.
/// Viewers disconnect first and rejoin afterwards.
async fn restart(state: &State, snapshot: Option<&Path>) -> Result<(), ErrorBody> {
    let unavailable = |err: anyhow::Error| ErrorBody {
        code: ErrorCode::Unavailable,
        message: format!("{err:#}"),
    };
    let mut game = state.game.lock().await;
    game.stop().await.map_err(unavailable)?;
    // A bad snapshot path must not leave the world down: start the server
    // again whatever the copy did, then report the copy's error.
    let copied = match snapshot {
        Some(path) => copy_save(&state.config.run_dir.join("save.zip"), path),
        None => Ok(()),
    };
    *game = Game::start(&state.config, &state.viewers)
        .await
        .map_err(unavailable)?;
    copied.map_err(|err| ErrorBody {
        code: ErrorCode::BadRequest,
        message: format!("{err:#}"),
    })
}

/// What the agent's screen shows (decision 67): 1920x1080, the most common
/// player screen.
const SCREEN_WIDTH: u32 = 1920;
const SCREEN_HEIGHT: u32 = 1080;
/// Pixels per tile at zoom 1, the game's default zoom.
const TILE_PX: f64 = 32.0;
/// Zoom a player has with a character: in as far as 3, and out as far as the
/// game view goes, 200 tiles across a 16:9 screen (0.3 at 1920 px; probed
/// with `LuaPlayer::zoom_limits` on 2.1.24). The agent's view stops at 0.5,
/// 60 tiles each way, so it stays on the 5x5 chunks its body has revealed,
/// at least 64 tiles each way (decision 31).
const SCREEN_ZOOM: std::ops::RangeInclusive<f64> = 0.5..=3.0;

/// One render by the camera client.
struct Shot {
    /// Map position at the centre of the image; `None` centres it on the
    /// agent's body.
    at: Option<(f64, f64)>,
    zoom: f64,
    width: u32,
    height: u32,
    /// Daytime to light it with (0 is noon); `None` keeps the surface's own.
    daytime: Option<f64>,
    /// Tiles between the lines of the coordinate grid drawn over it; `None`
    /// draws no grid.
    grid: Option<u32>,
}

/// A finished render: the PNG in the camera's script-output, which the
/// caller moves or deletes, and the map position at its centre.
struct Rendered {
    file: PathBuf,
    center: (f64, f64),
}

/// Render with the camera client and wait until the PNG is written. The
/// tick is the one the mod took the screenshot on.
async fn render(state: &State, shot: &Shot) -> (Result<Rendered, ErrorBody>, Option<u64>) {
    let Some(camera_dir) = state.game.lock().await.camera_dir() else {
        return (
            Err(ErrorBody {
                code: ErrorCode::Unavailable,
                message: "no camera: screenshots need a world started with a camera \
                          (fac daemon --camera; playtests: --camera)"
                    .into(),
            }),
            None,
        );
    };
    let n = state.screenshots.fetch_add(1, Ordering::Relaxed);
    let game_path = format!("factobot/shot-{n}.png");
    // A file left by an earlier daemon on this run directory must not pass for the new render.
    let file = camera_dir.join("script-output").join(&game_path);
    let _ = fs::remove_file(&file);
    let mut params = json!({
        "player": viewer::Kind::Camera.player_name(),
        "path": game_path,
        "zoom": shot.zoom,
        "width": shot.width,
        "height": shot.height,
    });
    if let Some((x, y)) = shot.at {
        params["x"] = x.into();
        params["y"] = y.into();
    }
    if let Some(daytime) = shot.daytime {
        params["daytime"] = daytime.into();
    }
    if let Some(grid) = shot.grid {
        params["grid"] = grid.into();
    }
    let (reply, tick) = call_mod(state, "screenshot", &params).await;
    let reply = match reply {
        Ok(reply) => reply,
        Err(err) => return (Err(err), tick),
    };
    let center = match (reply["center"]["x"].as_f64(), reply["center"]["y"].as_f64()) {
        (Some(x), Some(y)) => (x, y),
        _ => {
            return (
                Err(ErrorBody {
                    code: ErrorCode::GameError,
                    message: format!("the mod's screenshot gave no centre: {reply}"),
                }),
                tick,
            );
        }
    };
    let written = wait_for_png(&file).await.map_err(|err| ErrorBody {
        code: ErrorCode::GameError,
        message: format!("{err:#}"),
    });
    (written.map(|()| Rendered { file, center }), tick)
}

/// Render part of the map with the camera client and return the PNG path.
async fn screenshot(state: &State, params: &Value) -> Outcome {
    let number =
        |key: &str, default: f64| params.get(key).and_then(Value::as_f64).unwrap_or(default);
    let zoom = number("zoom", 1.0);
    let (width, height) = (
        number("width", 1280.0) as u32,
        number("height", 720.0) as u32,
    );
    let sizes_ok = (1..=8192).contains(&width) && (1..=8192).contains(&height);
    if !sizes_ok || zoom <= 0.0 {
        return (
            Err(bad_params(
                "screenshot needs 1-8192 px sizes and a positive zoom",
            )),
            None,
        );
    }
    let shot = Shot {
        at: Some((number("x", 0.0), number("y", 0.0))),
        zoom,
        width,
        height,
        daytime: Some(0.0),
        grid: None,
    };
    let (rendered, tick) = render(state, &shot).await;
    let saved = rendered.and_then(|rendered| {
        let dest = match params.get("path").and_then(Value::as_str) {
            Some(path) => PathBuf::from(path),
            // `shot-<n>.png`, numbered by the daemon.
            None => state
                .config
                .run_dir
                .join("screenshots")
                .join(rendered.file.file_name().unwrap_or_default()),
        };
        copy_save(&rendered.file, &dest)
            .and_then(|()| fs::remove_file(&rendered.file).map_err(Into::into))
            .map_err(|err| bad_params(&format!("{err:#}")))?;
        Ok(json!({ "path": dest, "tick": tick, "width": width, "height": height }))
    });
    (saved, tick)
}

/// Tiles between grid lines on the agent's screen (decision 78): 10 where a
/// tile is 48 pixels or less, 5 closer in.
fn grid_step(zoom: f64) -> u32 {
    if zoom > 1.5 { 5 } else { 10 }
}

/// What the agent's screen shows: the camera's render centred on its body,
/// returned as base64 PNG data, since the agent can't read the run directory.
async fn screen(state: &State, params: &Value) -> Outcome {
    let grid = match params.get("grid") {
        None | Some(Value::Null) => true,
        Some(Value::Bool(grid)) => *grid,
        Some(_) => return (Err(bad_params("grid must be true or false")), None),
    };
    let zoom = match params.get("zoom") {
        None | Some(Value::Null) => 1.0,
        Some(zoom) => match zoom.as_f64() {
            Some(zoom) if SCREEN_ZOOM.contains(&zoom) => zoom,
            _ => {
                return (
                    Err(bad_params(&format!(
                        "zoom must be a number from {} to {}",
                        SCREEN_ZOOM.start(),
                        SCREEN_ZOOM.end()
                    ))),
                    None,
                );
            }
        },
    };
    let shot = Shot {
        at: None,
        zoom,
        width: SCREEN_WIDTH,
        height: SCREEN_HEIGHT,
        daytime: None,
        grid: grid.then(|| grid_step(zoom)),
    };
    let (rendered, tick) = render(state, &shot).await;
    let result = rendered.and_then(|rendered| {
        let png = fs::read(&rendered.file);
        let _ = fs::remove_file(&rendered.file);
        let png = png.map_err(|err| ErrorBody {
            code: ErrorCode::GameError,
            message: format!("reading {}: {err}", rendered.file.display()),
        })?;
        let (x, y) = rendered.center;
        let half_width = f64::from(SCREEN_WIDTH) / (2.0 * TILE_PX * zoom);
        let half_height = f64::from(SCREEN_HEIGHT) / (2.0 * TILE_PX * zoom);
        let point = |x: f64, y: f64| json!({ "x": round2(x), "y": round2(y) });
        let mut result = json!({
            "tick": tick,
            "width": SCREEN_WIDTH,
            "height": SCREEN_HEIGHT,
            "zoom": zoom,
            "center": point(x, y),
            "area": {
                "left_top": point(x - half_width, y - half_height),
                "right_bottom": point(x + half_width, y + half_height),
            },
            PNG_FIELD: base64::engine::general_purpose::STANDARD.encode(png),
        });
        if let Some(step) = shot.grid {
            result["grid_tiles"] = step.into();
        }
        Ok(result)
    });
    (result, tick)
}

fn round2(value: f64) -> f64 {
    (value * 100.0).round() / 100.0
}

/// A response to log in place of one that carries PNG data: the same, with
/// the data's length in `png_base64_bytes` instead of the data.
fn without_png(response: &Response) -> Option<Response> {
    let result = response.result.as_ref()?.as_object()?;
    let png = result.get(PNG_FIELD)?.as_str()?;
    let mut kept: serde_json::Map<String, Value> = result
        .iter()
        .filter(|(key, _)| *key != PNG_FIELD)
        .map(|(key, value)| (key.clone(), value.clone()))
        .collect();
    kept.insert("png_base64_bytes".into(), png.len().into());
    Some(Response::ok(response.id, Value::Object(kept)))
}

/// The client writes screenshots asynchronously; a PNG is complete once its
/// IEND chunk is on disk.
async fn wait_for_png(path: &Path) -> Result<()> {
    const IEND: &[u8] = b"IEND\xaeB`\x82";
    let deadline = Instant::now() + SCREENSHOT_TIMEOUT;
    loop {
        if fs::read(path).is_ok_and(|bytes| bytes.ends_with(IEND)) {
            return Ok(());
        }
        if Instant::now() > deadline {
            bail!(
                "the camera did not write {} within {SCREENSHOT_TIMEOUT:?}",
                path.display()
            );
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
}

fn copy_save(save: &Path, to: &Path) -> Result<()> {
    if let Some(dir) = to.parent().filter(|dir| !dir.as_os_str().is_empty()) {
        fs::create_dir_all(dir).with_context(|| format!("creating {}", dir.display()))?;
    }
    fs::copy(save, to).with_context(|| format!("copying the save to {}", to.display()))?;
    Ok(())
}

/// Call a method of the factobot mod's `/factobot` command.
async fn call_mod(state: &State, method: &str, params: &Value) -> Outcome {
    call_mod_with_hud(state, method, params).await.0
}

/// Call an agent method of the mod and keep the HUD it answers with.
async fn call_mod_with_hud(
    state: &State,
    method: &str,
    params: &Value,
) -> (Outcome, Option<Value>) {
    call_command(state, &format!("/factobot {method} {params}")).await
}

/// A mod call that never reached a reply, so there is no tick and no HUD.
fn command_failed(code: ErrorCode, message: String) -> (Outcome, Option<Value>) {
    ((Err(ErrorBody { code, message }), None), None)
}

/// Run a mod command and unwrap its `{ok, result | error, tick, hud}` reply.
async fn call_command(state: &State, command: &str) -> (Outcome, Option<Value>) {
    let raw = {
        let mut game = state.game.lock().await;
        match game.rcon.exec(command).await {
            Ok(raw) => raw,
            Err(err) => {
                let status = game
                    .server
                    .exit_status()
                    .map(|status| format!(" (Factorio exited: {status})"))
                    .unwrap_or_default();
                return command_failed(ErrorCode::Unavailable, format!("{err}{status}"));
            }
        }
    };
    let reply: Value = match serde_json::from_str(raw.trim()) {
        Ok(reply) => reply,
        Err(err) => {
            return command_failed(
                ErrorCode::GameError,
                format!("mod returned non-JSON ({err}): {}", raw.trim()),
            );
        }
    };
    let tick = reply["tick"].as_u64();
    let hud = reply.get("hud").filter(|hud| hud.is_object()).cloned();
    if reply["ok"] == Value::Bool(true) {
        ((Ok(reply["result"].clone()), tick), hud)
    } else {
        let error = ErrorBody {
            code: match reply["code"].as_str() {
                Some("rejected") => ErrorCode::Rejected,
                Some("bad_request") => ErrorCode::BadRequest,
                Some("unavailable") => ErrorCode::Unavailable,
                _ => ErrorCode::GameError,
            },
            message: reply["error"]
                .as_str()
                .unwrap_or("mod reported an error without a message")
                .to_owned(),
        };
        ((Err(error), tick), hud)
    }
}

/// Agent methods the mod implements; the daemon passes them through.
const AGENT_METHODS: &[&str] = &[
    "observe",
    "inventory",
    "stats",
    "map",
    "walk",
    "mine",
    "craft",
    "job",
    "jobs",
    "cancel",
    "place",
    "place_line",
    "insert",
    "take",
    "rotate",
    "inspect",
    "set_recipe",
    "research",
    "launch",
];

const WAIT_DEFAULT_S: f64 = 60.0;
const WAIT_POLL: Duration = Duration::from_millis(100);

/// Block in real time until a job leaves `running` or `timeout` seconds
/// pass, then return the job. The game keeps running meanwhile.
async fn wait_for_job(state: &State, params: &Value) -> (Outcome, Option<Value>) {
    let Some(id) = params.get("id").and_then(Value::as_u64) else {
        return (
            (
                Err(bad_params("wait needs params {\"id\": <job id>}")),
                None,
            ),
            None,
        );
    };
    let timeout = params
        .get("timeout")
        .and_then(Value::as_f64)
        .unwrap_or(WAIT_DEFAULT_S);
    if let Some(err) = wait_timeout_error(timeout) {
        return ((Err(err), None), None);
    }
    let deadline = Instant::now() + Duration::from_secs_f64(timeout);
    // The polls leave the HUD alone: each HUD marks its warnings as said, and
    // no poll's answer is shown (protocol.md).
    let poll = json!({ "id": id, "hud": "skip" });
    loop {
        let ((job, _), _) = call_mod_with_hud(state, "job", &poll).await;
        match job {
            Ok(job) if job["state"] == "running" && Instant::now() < deadline => {
                tokio::time::sleep(WAIT_POLL).await;
            }
            _ => break,
        }
    }
    // One ordinary look ends the wait, so its answer carries the HUD.
    let ((job, tick), hud) = call_mod_with_hud(state, "job", &json!({ "id": id })).await;
    ((job.map(empty_tables_as_lists), tick), hud)
}

/// Lua has one table type, so the mod's JSON writes an empty list as `{}`.
/// Agent results and the dev `milestones` result use lists for every
/// collection, so `{}` always means `[]`.
fn empty_tables_as_lists(value: Value) -> Value {
    match value {
        Value::Object(map) if map.is_empty() => Value::Array(Vec::new()),
        Value::Object(map) => Value::Object(
            map.into_iter()
                .map(|(key, value)| (key, empty_tables_as_lists(value)))
                .collect(),
        ),
        Value::Array(items) => Value::Array(items.into_iter().map(empty_tables_as_lists).collect()),
        other => other,
    }
}

/// The mod's `milestones` result with empty tables as lists and
/// `rocket_launched_tick` set to null until a rocket has launched: Lua
/// leaves a nil field out of its JSON.
fn milestones_result(result: Value) -> Value {
    let mut result = empty_tables_as_lists(result);
    if let Value::Object(map) = &mut result {
        map.entry("rocket_launched_tick").or_insert(Value::Null);
    }
    result
}
