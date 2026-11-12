//! Graphical Factorio clients that join a game server as spectators.
//!
//! - The **camera** renders under its own Xvfb display (Mesa llvmpipe, no
//!   GPU) and takes screenshots for `fac dev screenshot` and the agent's
//!   `fac screenshot`.
//! - The **viewer** opens a normal window on the caller's display so a
//!   person can watch the game live.
//! - **`fac watch`** opens the same window on another machine, joining a
//!   daemon started with `--listen` (`watch`).
//!
//! Windowed clients keep `WAYLAND_DISPLAY`, so a Hyprland session can
//! attach, and they exit before Factorio starts when `DISPLAY` is unset or
//! the X server does not accept a connection. The camera sets its own Xvfb
//! `DISPLAY` and removes `WAYLAND_DISPLAY`.
//!
//! All need the graphical build (`scripts/fetch-factorio --client`). The mod
//! turns every player into a spectator without a character, so watching
//! never changes the world.
//!
//! Loading sprites takes a client about 45 s of every CPU thread, and
//! several minutes on a loaded machine, so clients share a sprite atlas
//! cache per client build and renderer (`atlas-cache/` beside its `bin/`):
//! with it a client starts in about 5 s.

use std::fs;
use std::net::{SocketAddr, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Duration;

use anyhow::{Context, Result, bail};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};

use crate::server;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Camera,
    Viewer,
}

impl Kind {
    pub fn player_name(self) -> &'static str {
        match self {
            Self::Camera => "factobot-camera",
            Self::Viewer => "factobot-viewer",
        }
    }
}

pub struct Viewer {
    pub kind: Kind,
    /// The client's write-data directory (`script-output/` lives here).
    pub write_dir: PathBuf,
    /// Where this client publishes the atlas cache it builds.
    shared_atlas: PathBuf,
    atlas: Atlas,
    client: Child,
    xvfb: Option<Child>,
}

impl Viewer {
    /// Launch the client and point it at the server. Joining finishes
    /// asynchronously; the daemon waits for the player to show up in game,
    /// then calls `publish_atlas`.
    pub async fn start(
        kind: Kind,
        client_dir: &Path,
        mods_dir: &Path,
        run_dir: &Path,
        server: SocketAddr,
    ) -> Result<Self> {
        let dir = run_dir.join(kind.player_name());
        // The camera renders every frame on the CPU (Mesa llvmpipe), over 200%
        // of a core with nobody watching, and has no frame-rate cap. It starts
        // under `nice`, so every Factorio thread, llvmpipe workers included,
        // inherits the low priority. At low priority it yields to the server
        // and to anything else in its scheduling group: its cpu cgroup, or with
        // the cpu controller off, its session's autogroup (the harness starts
        // each world in a session of its own, so then only that world). Nice
        // does not reach across groups (other systemd slices, users, services
        // or sessions), so it competes with those at normal weight.
        // Screenshots just take longer under load.
        let nice = (kind == Kind::Camera).then_some(15);
        // A window needs the caller's X11 display. Check before starting
        // anything else, so a headless `--viewer` says why instead of dying
        // inside Factorio.
        let window = match kind {
            Kind::Viewer => Some(require_window_display().await?),
            Kind::Camera => None,
        };
        let xvfb = match kind {
            Kind::Camera => Some(start_xvfb(&dir).await?),
            Kind::Viewer => None,
        };
        let display = xvfb.as_ref().map(|(_, display)| display.clone());
        let shared = shared_atlas(client_dir, kind);
        let (client, write_dir, atlas) = spawn_client(
            client_dir,
            kind,
            &dir,
            mods_dir,
            kind.player_name(),
            &server.to_string(),
            nice,
            |command| {
                command.arg("--disable-audio");
                if let Some(display) = &display {
                    command.arg("--window-size").arg("1280x720");
                    force_x11(command, display);
                } else if let Some(display) = &window {
                    // Leave WAYLAND_DISPLAY set. On a Hyprland desktop the
                    // session attaches only when both variables are present.
                    command.env("DISPLAY", display);
                }
            },
        )
        .await?;
        Ok(Self {
            kind,
            write_dir,
            shared_atlas: shared,
            atlas,
            client,
            xvfb: xvfb.map(|(xvfb, _)| xvfb),
        })
    }

    /// Once the client is in game, its sprite atlas is complete: when it
    /// built one, share it with the clients that start after it.
    pub async fn publish_atlas(&mut self) -> Result<()> {
        if self.atlas != Atlas::Build {
            return Ok(());
        }
        self.atlas = Atlas::Off;
        let (write_dir, shared) = (self.write_dir.clone(), self.shared_atlas.clone());
        tokio::task::spawn_blocking(move || publish_atlas(&write_dir, &shared)).await?
    }

    pub fn exit_status(&mut self) -> Option<std::process::ExitStatus> {
        self.client.try_wait().ok().flatten()
    }

    pub async fn stop(&mut self) {
        let _ = self.client.kill().await;
        if let Some(xvfb) = &mut self.xvfb {
            let _ = xvfb.kill().await;
        }
    }
}

/// Join the server at `server` (`HOST:PORT`) in a window on this display as
/// the spectator `name`, and return once the window closes. `DISPLAY` is
/// passed through and `WAYLAND_DISPLAY` is left set, so a Hyprland session
/// can attach. This fails before Factorio starts when `DISPLAY` is unset or
/// the X server does not accept a connection, or when `server` does not
/// resolve. The client loads the factobot mod from `mod_dir`, which must
/// match the server's copy file for file, or Factorio refuses the join.
pub async fn watch(
    client_dir: &Path,
    mod_dir: &Path,
    state_dir: &Path,
    server: &str,
    name: &str,
) -> Result<()> {
    let display = require_window_display().await?;
    resolve_watch_server(server).await?;
    let mod_dir = mod_dir
        .canonicalize()
        .with_context(|| format!("mod directory {}", mod_dir.display()))?;
    let dir = state_dir.join(name);
    let mods = dir.join("mods");
    server::write_mods(&mods, &mod_dir)?;
    let shared = shared_atlas(client_dir, Kind::Viewer);
    let (mut client, write_dir, atlas) = spawn_client(
        client_dir,
        Kind::Viewer,
        &dir,
        &mods,
        name,
        server,
        None,
        |command| {
            command.env("DISPLAY", &display);
        },
    )
    .await?;
    let status = client.wait().await?;
    // The window closed. A client that got as far as joining wrote its whole
    // atlas; share it with the next one.
    let log_path = dir.join("client.log");
    let log = fs::read(&log_path).unwrap_or_default();
    let log_text = String::from_utf8_lossy(&log);
    if atlas == Atlas::Build
        && log_text.contains("Factorio initialised")
        && let Err(err) =
            tokio::task::spawn_blocking(move || publish_atlas(&write_dir, &shared)).await?
    {
        eprintln!("fac watch: sprite atlas not shared: {err:#}");
    }
    if !status.success() {
        bail!(
            "{}",
            watch_exit_message(server, &log_path, &status, &log_text)
        );
    }
    Ok(())
}

/// What to do when a windowed client has no X11 display.
const WINDOW_DISPLAY_HINT: &str = concat!(
    "Open the window on a desktop host, from a terminal on that desktop, ",
    "or set DISPLAY to that session's display. On a Hyprland desktop that is DISPLAY=:0, ",
    "and WAYLAND_DISPLAY must be the Hyprland socket (often wayland-1), or the client cannot attach. ",
    "A shell that did not inherit the desktop has to export both."
);

/// Where a playtest or rocket run prints the address `fac watch` should use.
const SERVER_HINT: &str = concat!(
    "Use the address and port the run printed on stderr ",
    "(`watch with: fac watch <address>:<port>`). `mise run watch` reads HOST, ",
    "and a missing port means 34197, which is not the port a playtest or rocket run picked."
);

fn missing_display_message(wayland_set: bool) -> String {
    let lead = if wayland_set {
        "DISPLAY is unset. WAYLAND_DISPLAY is set, and that is not enough."
    } else {
        "DISPLAY is unset."
    };
    format!("{lead} {WINDOW_DISPLAY_HINT}")
}

fn unusable_display_message(display: &str, problem: &str) -> String {
    format!("DISPLAY={display} is not a usable X11 display ({problem}). {WINDOW_DISPLAY_HINT}")
}

/// `Some` when `server` is not `HOST:PORT` with a numeric port.
fn server_spec_error(server: &str) -> Option<&'static str> {
    let Some((host, port)) = server.rsplit_once(':') else {
        return Some("expected HOST:PORT");
    };
    if host.is_empty() || port.parse::<u16>().is_err() {
        return Some("expected HOST:PORT with a numeric port");
    }
    None
}

async fn resolve_watch_server(server: &str) -> Result<()> {
    if let Some(problem) = server_spec_error(server) {
        bail!("{problem} ({server}). {SERVER_HINT}");
    }
    match tokio::net::lookup_host(server).await {
        Ok(mut addrs) => {
            if addrs.next().is_none() {
                bail!("cannot resolve {server}. {SERVER_HINT}");
            }
        }
        Err(err) => bail!("cannot resolve {server} ({err}). {SERVER_HINT}"),
    }
    Ok(())
}

fn watch_exit_message(
    server: &str,
    log_path: &Path,
    status: &std::process::ExitStatus,
    log: &str,
) -> String {
    let said = factorio_error_line(log)
        .map(|line| format!(" Factorio said: {line}."))
        .unwrap_or_default();
    let join = if log_join_failed(log) {
        format!(" The client did not join {server}. {SERVER_HINT}")
    } else {
        String::new()
    };
    let display = if log_display_failed(log) {
        format!(" {WINDOW_DISPLAY_HINT}")
    } else {
        String::new()
    };
    format!(
        "Factorio exited with {status}; see {}{said}{join}{display}",
        log_path.display()
    )
}

/// The last Factorio `Error` line, trimmed. The log prefixes each one with
/// the time and `Error`.
fn factorio_error_line(log: &str) -> Option<&str> {
    log.lines().rev().find_map(|line| {
        let trimmed = line.trim();
        trimmed.contains(" Error ").then_some(trimmed)
    })
}

fn log_join_failed(log: &str) -> bool {
    [
        "MultiplayerManager failed",
        "Could not establish network communication",
        "not-received-connection-accept-reply",
        "Connection refused",
    ]
    .iter()
    .any(|marker| log.contains(marker))
}

fn log_display_failed(log: &str) -> bool {
    let lower = log.to_ascii_lowercase();
    [
        "no available video device",
        "sdl_error",
        "wayland not available",
        "could not initialize graphics",
        "could not create display",
    ]
    .iter()
    .any(|marker| lower.contains(marker))
}

/// Point the camera at its Xvfb display and keep it off Wayland.
/// Factorio's SDL backend prefers Wayland when `WAYLAND_DISPLAY` is set,
/// which would hide the Xvfb display. Windowed clients leave
/// `WAYLAND_DISPLAY` set so a Hyprland session can attach.
fn force_x11(command: &mut Command, display: &str) {
    command
        .env("DISPLAY", display)
        .env_remove("WAYLAND_DISPLAY");
}

fn read_window_display() -> Result<String> {
    let display = std::env::var("DISPLAY").unwrap_or_default();
    let display = display.trim().to_owned();
    let wayland_set = std::env::var("WAYLAND_DISPLAY")
        .ok()
        .is_some_and(|value| !value.trim().is_empty());
    if display.is_empty() {
        bail!("{}", missing_display_message(wayland_set));
    }
    if let Err(problem) = open_x_display(&display) {
        bail!("{}", unusable_display_message(&display, &problem));
    }
    Ok(display)
}

pub async fn require_window_display() -> Result<String> {
    tokio::task::spawn_blocking(read_window_display).await?
}

#[derive(Debug)]
enum XTarget {
    /// The socket `/tmp/.X11-unix/XN`, then TCP on `tcp_port` when set.
    Local {
        number: u16,
        tcp_port: Option<u16>,
    },
    Tcp {
        host: String,
        port: u16,
    },
}

/// `DISPLAY` as an X server to connect to. A local display (`:0`, `unix:0`)
/// is the socket `/tmp/.X11-unix/XN`; a bare `:N` falls back to TCP on
/// `localhost:6000+N` when that socket refuses, as libxcb does. A display
/// with a host is TCP on port `6000 + N`, which is how an SSH X11 forward is
/// reached.
fn x_target(display: &str) -> Result<XTarget, String> {
    let display = display.trim();
    let (host, rest) = if let Some(rest) = display.strip_prefix('[') {
        rest.split_once("]:")
            .map(|(host, rest)| (host.to_owned(), rest))
            .ok_or_else(|| format!("expected [host]:number, got {display:?}"))?
    } else {
        display
            .rsplit_once(':')
            .map(|(host, rest)| (host.to_owned(), rest))
            .ok_or_else(|| format!("expected [host]:number, got {display:?}"))?
    };
    let number = rest.split(['.', '/']).next().unwrap_or("");
    if number.is_empty() || !number.bytes().all(|byte| byte.is_ascii_digit()) {
        return Err(format!("display number in {display:?} is not a number"));
    }
    let number: u16 = number
        .parse()
        .map_err(|_| format!("display number in {display:?} is out of range"))?;
    let port = u16::try_from(6000u32 + u32::from(number)).ok();
    let (protocol, host) = match host.split_once('/') {
        Some((protocol, host)) => (protocol, host.to_owned()),
        None => ("", host),
    };
    let local = protocol == "unix"
        || protocol == "local"
        || host.is_empty()
        || host == "unix"
        || host == "local";
    if local {
        // libxcb (`_xcb_open`) tries TCP only when DISPLAY names neither a
        // protocol nor a host.
        let bare = protocol.is_empty() && host.is_empty();
        return Ok(XTarget::Local {
            number,
            tcp_port: port.filter(|_| bare),
        });
    }
    let port = port.ok_or_else(|| format!("display number in {display:?} is out of range"))?;
    Ok(XTarget::Tcp { host, port })
}

/// Whether anything accepts connections for `display`. A refused or missing
/// socket is unusable; authorization is left to Factorio, which reads the
/// same `XAUTHORITY` this process has.
fn open_x_display(display: &str) -> Result<(), String> {
    match x_target(display)? {
        XTarget::Local { number, tcp_port } => match (connect_local(number), tcp_port) {
            (Err(problem), Some(port)) => {
                connect_tcp("localhost", port).map_err(|tcp| format!("{problem}, and {tcp}"))
            }
            (local, _) => local,
        },
        XTarget::Tcp { host, port } => connect_tcp(&host, port),
    }
}

fn connect_local(number: u16) -> Result<(), String> {
    let path = PathBuf::from(format!("/tmp/.X11-unix/X{number}"));
    // On Linux, libxcb tries the abstract socket `@/tmp/.X11-unix/XN`
    // before the file, so a server is reachable even where `/tmp` is
    // private (a sandbox, a container sharing the host's network).
    if connect_abstract(&path) {
        return Ok(());
    }
    if !path.exists() {
        return Err(format!(
            "no X11 socket at {} or its abstract name",
            path.display()
        ));
    }
    std::os::unix::net::UnixStream::connect(&path)
        .map(|_| ())
        .map_err(|err| format!("could not connect to {} ({err})", path.display()))
}

fn connect_tcp(host: &str, port: u16) -> Result<(), String> {
    let formatted = if host.contains(':') {
        format!("[{host}]:{port}")
    } else {
        format!("{host}:{port}")
    };
    let addrs = formatted
        .to_socket_addrs()
        .map_err(|err| format!("could not resolve {formatted} ({err})"))?;
    let mut failure = None;
    for addr in addrs {
        match std::net::TcpStream::connect_timeout(&addr, Duration::from_secs(3)) {
            Ok(_) => return Ok(()),
            Err(err) => failure = Some(err),
        }
    }
    Err(match failure {
        Some(err) => format!("could not connect to {formatted} ({err})"),
        None => format!("could not resolve {formatted}"),
    })
}

#[cfg(target_os = "linux")]
fn connect_abstract(path: &Path) -> bool {
    use std::os::linux::net::SocketAddrExt;
    use std::os::unix::net::{SocketAddr, UnixStream};
    SocketAddr::from_abstract_name(path.as_os_str().as_encoded_bytes())
        .and_then(|addr| UnixStream::connect_addr(&addr))
        .is_ok()
}

#[cfg(not(target_os = "linux"))]
fn connect_abstract(_path: &Path) -> bool {
    false
}

/// How a client uses the shared sprite atlas cache.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Atlas {
    /// A mod ships images, which the cache would have to include.
    Off,
    /// Load the shared cache, read-only.
    Shared,
    /// Build a cache in write-data, to publish once the client is in game.
    Build,
}

/// What `cache-sprite-atlas` writes into write-data: about 1.1 GB.
const ATLAS_FILES: [&str; 2] = ["atlas-cache.dat", "crop-cache.dat"];

/// Where clients of `kind` publish the atlas cache they build. Factorio
/// builds a different atlas for each renderer (on one desktop, llvmpipe picks the
/// very-high preset with 16384-pixel bitmaps and the Intel GPU a lower one
/// with 8192) and rejects one built by another. The camera always renders
/// on llvmpipe under Xvfb, and windowed clients usually on the desktop's
/// GPU, so each kind keeps its own cache rather than overwriting the other's.
fn shared_atlas(client_dir: &Path, kind: Kind) -> PathBuf {
    client_dir.join("atlas-cache").join(match kind {
        Kind::Camera => "xvfb",
        Kind::Viewer => "window",
    })
}

/// A sibling of the shared cache directory `shared`, named
/// `<its name>.<suffix>-<pid>`.
fn beside(shared: &Path, suffix: &str) -> PathBuf {
    let name = shared.file_name().unwrap_or_default().to_string_lossy();
    shared.with_file_name(format!("{name}.{suffix}-{}", std::process::id()))
}

/// Start a client from `client_command` plus `setup`. It tries its own
/// kind's shared atlas cache first, then the other kind's (a window under
/// `xvfb-run` renders like the camera), waiting each time until the client
/// has read it. A cache made for another renderer is rejected, and the
/// client then stalls trying to rewrite the read-only files, so it is
/// killed and the next cache tried. With none left, the client builds its
/// own. A rejected cache stays: the renderer it was built on may still use
/// it, and a client that builds a new one replaces it when it publishes.
#[allow(clippy::too_many_arguments)]
async fn spawn_client(
    client_dir: &Path,
    kind: Kind,
    dir: &Path,
    mods_dir: &Path,
    name: &str,
    server: &str,
    nice: Option<u8>,
    setup: impl Fn(&mut Command),
) -> Result<(Child, PathBuf, Atlas)> {
    let spawn = |atlas: Atlas, shared: &Path| -> Result<(Child, PathBuf)> {
        let (mut command, write_dir) =
            client_command(client_dir, shared, dir, mods_dir, name, server, nice, atlas)?;
        setup(&mut command);
        let client = command.spawn().context("starting graphical Factorio")?;
        Ok((client, write_dir))
    };
    let own = shared_atlas(client_dir, kind);
    if mods_have_images(mods_dir)? {
        let (client, write_dir) = spawn(Atlas::Off, &own)?;
        return Ok((client, write_dir, Atlas::Off));
    }
    let other = match kind {
        Kind::Camera => Kind::Viewer,
        Kind::Viewer => Kind::Camera,
    };
    for shared in [own.clone(), shared_atlas(client_dir, other)] {
        if !ATLAS_FILES.iter().all(|f| shared.join(f).is_file()) {
            continue;
        }
        let (mut client, write_dir) = spawn(Atlas::Shared, &shared)?;
        if read_shared_atlas(&dir.join("client.log"), &mut client).await {
            return Ok((client, write_dir, Atlas::Shared));
        }
        let _ = client.kill().await;
    }
    let (client, write_dir) = spawn(Atlas::Build, &own)?;
    Ok((client, write_dir, Atlas::Build))
}

/// Whether the client read the shared atlas cache. Factorio logs which way
/// it went within seconds of starting; a client that exits first, or never
/// says, is left to the caller's own checks.
async fn read_shared_atlas(log: &Path, client: &mut Child) -> bool {
    let deadline = tokio::time::Instant::now() + Duration::from_secs(120);
    while tokio::time::Instant::now() < deadline {
        let text = fs::read(log).unwrap_or_default();
        let text = String::from_utf8_lossy(&text);
        if text.contains("Atlases loaded from disk cache") {
            return true;
        }
        if text.contains("Atlases were not loaded from disk cache") {
            return false;
        }
        if client.try_wait().ok().flatten().is_some() {
            return true;
        }
        tokio::time::sleep(Duration::from_millis(250)).await;
    }
    true
}

/// Copy the atlas cache a client built into the shared directory `shared`,
/// its own kind's, replacing any cache there: the client built its own
/// because it found none it could use. Two clients that built one at once
/// both publish; either result serves.
fn publish_atlas(write_dir: &Path, shared: &Path) -> Result<()> {
    let staging = beside(shared, "new");
    let result = (|| -> Result<()> {
        fs::create_dir_all(&staging)?;
        for file in ATLAS_FILES {
            let copy = staging.join(file);
            fs::copy(write_dir.join(file), &copy)
                .with_context(|| format!("copying {file} from {}", write_dir.display()))?;
            let mut permissions = fs::metadata(&copy)?.permissions();
            permissions.set_readonly(true);
            fs::set_permissions(&copy, permissions)?;
        }
        Ok(())
    })();
    if result.is_ok() {
        let stale = beside(shared, "stale");
        let replaced = fs::rename(shared, &stale).is_ok();
        let published = fs::rename(&staging, shared).is_ok();
        if replaced {
            let _ = fs::remove_dir_all(&stale);
        }
        if published {
            // The run's copy lives on /tmp, often a tmpfs.
            for file in ATLAS_FILES {
                let _ = fs::remove_file(write_dir.join(file));
            }
            return Ok(());
        }
    }
    let _ = fs::remove_dir_all(&staging);
    result
}

/// Whether a mod ships PNG or JPEG files, which go into the sprite atlas.
fn mods_have_images(dir: &Path) -> Result<bool> {
    for entry in fs::read_dir(dir).with_context(|| format!("reading {}", dir.display()))? {
        let path = entry?.path();
        if path.is_dir() {
            if mods_have_images(&path)? {
                return Ok(true);
            }
        } else if path.extension().is_some_and(|ext| {
            ["png", "jpg", "jpeg"]
                .iter()
                .any(|e| ext.eq_ignore_ascii_case(e))
        }) {
            return Ok(true);
        }
    }
    Ok(false)
}

/// A graphical client that joins `server` as `name`, with its config,
/// write-data and log under `dir`, started under `nice -n <nice>` when
/// given. A client on the shared atlas cache reads it from `shared`.
/// Returns the command and the write-data directory.
#[allow(clippy::too_many_arguments)]
fn client_command(
    client_dir: &Path,
    shared: &Path,
    dir: &Path,
    mods_dir: &Path,
    name: &str,
    server: &str,
    nice: Option<u8>,
    atlas: Atlas,
) -> Result<(Command, PathBuf)> {
    let binary = client_dir.join("bin/x64/factorio");
    if !binary.is_file() {
        bail!(
            "no graphical Factorio at {}; run `mise run fetch-factorio -- --client` (needs FACTORIO_TOKEN)",
            binary.display()
        );
    }
    let write_dir = dir.join("write-data");
    fs::create_dir_all(&write_dir)?;
    let config_ini = dir.join("config.ini");
    let mut graphics = String::from("[graphics]\n");
    if atlas != Atlas::Off {
        graphics.push_str("cache-sprite-atlas=true\n");
    }
    if name == Kind::Camera.player_name() {
        // Warning icons (no power, unplugged, no fuel, ...) blink on and off
        // every half second of the client's own clock, so half of all
        // screenshots missed them (probed on 2.1.24).
        graphics.push_str("enable-warning-icons-blinking=false\n");
    }
    fs::write(
        &config_ini,
        format!(
            "[path]\nread-data={}\nwrite-data={}\n{graphics}",
            client_dir.join("data").display(),
            write_dir.display()
        ),
    )?;
    for file in ATLAS_FILES {
        let link = write_dir.join(file);
        let _ = fs::remove_file(&link);
        if atlas == Atlas::Shared {
            // A relative target would resolve against write-data, not the
            // working directory a relative `--client-dir` is relative to.
            std::os::unix::fs::symlink(std::path::absolute(shared.join(file))?, &link)?;
        }
    }
    // The server runs without user verification, so a bare username is
    // enough to join. No account token goes near the client.
    fs::write(
        write_dir.join("player-data.json"),
        format!("{}\n", serde_json::json!({ "service-username": name })),
    )?;
    let log = fs::File::create(dir.join("client.log"))?;
    // `nice` execs Factorio, so the child's pid is still Factorio's.
    let mut command = match nice {
        Some(n) => {
            let mut command = Command::new("nice");
            command.arg("-n").arg(n.to_string()).arg(&binary);
            command
        }
        None => Command::new(&binary),
    };
    command
        .arg("--config")
        .arg(&config_ini)
        .arg("--mod-directory")
        .arg(mods_dir)
        .arg("--mp-connect")
        .arg(server)
        .stdin(Stdio::null())
        .stdout(Stdio::from(log.try_clone()?))
        .stderr(Stdio::from(log))
        .kill_on_drop(true);
    Ok((command, write_dir))
}

/// Start Xvfb on a free display number and return it with `:N`.
async fn start_xvfb(dir: &Path) -> Result<(Child, String)> {
    // `-displayfd 1`: Xvfb picks a free display and prints its number on
    // stdout once it accepts connections.
    fs::create_dir_all(dir)?;
    let log = fs::File::create(dir.join("xvfb.log"))?;
    let mut child = Command::new("Xvfb")
        .args([
            "-displayfd",
            "1",
            "-screen",
            "0",
            "1280x720x24",
            "-nolisten",
            "tcp",
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::from(log))
        .kill_on_drop(true)
        .spawn()
        .context("starting Xvfb (install xorg-server-xvfb)")?;
    let stdout = child.stdout.take().context("Xvfb stdout")?;
    let mut line = String::new();
    tokio::time::timeout(
        Duration::from_secs(20),
        BufReader::new(stdout).read_line(&mut line),
    )
    .await
    .context("Xvfb did not report a display within 20 s")??;
    let number = line.trim();
    if number.is_empty() {
        bail!(
            "Xvfb exited without a display; see {}",
            dir.join("xvfb.log").display()
        );
    }
    Ok((child, format!(":{number}")))
}

#[cfg(test)]
mod tests {
    use std::os::unix::process::ExitStatusExt;
    use std::process::ExitStatus;

    use super::{XTarget, open_x_display, server_spec_error, watch_exit_message, x_target};

    fn exit_code(code: i32) -> ExitStatus {
        ExitStatus::from_raw(code << 8)
    }

    /// The first display number in `numbers` with no X socket file whose TCP
    /// port (6000 + number) `hold` can take, and what `hold` returned.
    /// Panics when there is none, so a busy host fails the test loudly.
    fn free_display<T>(numbers: std::ops::Range<u16>, hold: impl Fn(u16) -> Option<T>) -> (u16, T) {
        numbers
            .clone()
            .find_map(|number| {
                if std::path::Path::new(&format!("/tmp/.X11-unix/X{number}")).exists() {
                    return None;
                }
                hold(6000 + number).map(|held| (number, held))
            })
            .unwrap_or_else(|| panic!("no free X display number in {numbers:?}"))
    }

    /// Hold 127.0.0.1:`port` with a socket that never listens: nothing else
    /// can take the port, and every connection to it is refused.
    fn refusing_port(port: u16) -> Option<tokio::net::TcpSocket> {
        let socket = tokio::net::TcpSocket::new_v4().ok()?;
        socket.bind(([127, 0, 0, 1], port).into()).ok()?;
        Some(socket)
    }

    fn listening_port(port: u16) -> Option<std::net::TcpListener> {
        std::net::TcpListener::bind(("127.0.0.1", port)).ok()
    }

    #[test]
    fn x_display_targets() {
        let local = |display| match x_target(display).unwrap() {
            XTarget::Local { number, tcp_port } => (number, tcp_port),
            other => panic!("expected a local display, got {other:?}"),
        };
        assert_eq!(local(":0"), (0, Some(6000)));
        assert_eq!(local(":0.0"), (0, Some(6000)));
        assert_eq!(local("unix:1"), (1, None));
        assert_eq!(local("unix/localhost:2"), (2, None));
        assert_eq!(local(":65535"), (65535, None));
        match x_target("localhost:10.0").unwrap() {
            XTarget::Tcp { host, port } => {
                assert_eq!(host, "localhost");
                assert_eq!(port, 6010);
            }
            other => panic!("expected a TCP display, got {other:?}"),
        }
        match x_target("[::1]:0").unwrap() {
            XTarget::Tcp { host, port } => {
                assert_eq!(host, "::1");
                assert_eq!(port, 6000);
            }
            other => panic!("expected a TCP display, got {other:?}"),
        }
        assert!(x_target("not-a-display").is_err());
    }

    #[test]
    fn missing_local_display_names_the_socket_and_the_tcp_port() {
        let (number, _held) = free_display(280..320, refusing_port);
        let err = open_x_display(&format!(":{number}")).unwrap_err();
        assert!(err.contains(&format!("/tmp/.X11-unix/X{number}")), "{err}");
        assert!(
            err.contains(&format!("could not connect to localhost:{}", 6000 + number)),
            "{err}"
        );
    }

    #[test]
    fn bare_local_display_falls_back_to_tcp() {
        let (number, _listener) = free_display(320..360, listening_port);
        let bare = open_x_display(&format!(":{number}"));
        assert!(bare.is_ok(), "{bare:?}");
        // An explicit unix display never tries TCP, as in libxcb.
        let unix = open_x_display(&format!("unix:{number}")).unwrap_err();
        assert!(!unix.contains("localhost"), "{unix}");
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn abstract_only_local_display_is_usable() {
        use std::os::linux::net::SocketAddrExt;
        use std::os::unix::net::{SocketAddr, UnixListener};
        let Some((number, listener)) = (400..600).rev().find_map(|number: u16| {
            let path = format!("/tmp/.X11-unix/X{number}");
            if std::path::Path::new(&path).exists() {
                return None;
            }
            let addr = SocketAddr::from_abstract_name(path.as_bytes()).ok()?;
            UnixListener::bind_addr(&addr)
                .ok()
                .map(|listener| (number, listener))
        }) else {
            panic!("no free abstract X socket name");
        };
        let result = open_x_display(&format!(":{number}"));
        drop(listener);
        assert!(result.is_ok(), "{result:?}");
    }

    #[test]
    fn open_tcp_display_is_usable() {
        let (number, _listener) = free_display(200..240, listening_port);
        let result = open_x_display(&format!("127.0.0.1:{number}"));
        assert!(result.is_ok(), "{result:?}");
    }

    #[test]
    fn closed_tcp_display_is_unusable() {
        // The port stays bound, not listening, until the probe is done.
        let (number, _held) = free_display(240..280, refusing_port);
        let err = open_x_display(&format!("127.0.0.1:{number}")).unwrap_err();
        assert!(
            err.starts_with(&format!("could not connect to 127.0.0.1:{}", 6000 + number)),
            "{err}"
        );
    }

    #[test]
    fn server_spec_requires_a_numeric_port() {
        assert!(server_spec_error("gamehost").is_some());
        assert!(server_spec_error("gamehost:abc").is_some());
        assert!(server_spec_error(":34197").is_some());
        assert!(server_spec_error("gamehost:34197").is_none());
        assert!(server_spec_error("[::1]:34197").is_none());
        assert!(server_spec_error("192.0.2.10:34198").is_none());
    }

    #[test]
    fn failed_join_points_at_the_printed_address() {
        let log = "\
  10.000 Joining game
  20.000 Error ClientMultiplayerManager.cpp:85: MultiplayerManager failed: \"Could not establish network communication with server.\"
";
        let msg = watch_exit_message(
            "gamehost:34197",
            std::path::Path::new("/tmp/client.log"),
            &exit_code(1),
            log,
        );
        assert!(msg.contains("gamehost:34197"), "{msg}");
        assert!(msg.contains("watch with: fac watch"), "{msg}");
        assert!(msg.contains("Factorio said:"), "{msg}");
        assert!(
            msg.contains("Could not establish network communication"),
            "{msg}"
        );
        assert!(msg.contains("The client did not join"), "{msg}");
    }

    #[test]
    fn display_failure_in_the_log_repeats_the_hint() {
        let log = "0.001 Error SDL: No available video device\n";
        let msg = watch_exit_message(
            "gamehost:34197",
            std::path::Path::new("client.log"),
            &exit_code(1),
            log,
        );
        assert!(msg.contains("cannot attach"), "{msg}");
        assert!(msg.contains("WAYLAND_DISPLAY"), "{msg}");
        assert!(!msg.contains("did not join"), "{msg}");
    }

    #[test]
    fn other_exit_keeps_the_log_path() {
        let msg = watch_exit_message(
            "gamehost:34197",
            std::path::Path::new("/tmp/w/client.log"),
            &exit_code(1),
            "loading\n",
        );
        assert!(msg.contains("exited with"), "{msg}");
        assert!(msg.contains("/tmp/w/client.log"), "{msg}");
        assert!(!msg.contains("watch with:"), "{msg}");
        assert!(!msg.contains("WAYLAND_DISPLAY"), "{msg}");
    }
}
