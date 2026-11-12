//! The harness's `fac`: every agent command, plus the harness-only `daemon`,
//! `watch` and `dev`. Agents get `fac-agent` instead, which has no code for
//! those (decision 64).

mod daemon;
mod rcon;
mod server;
mod viewer;

use std::net::IpAddr;
use std::path::PathBuf;
use std::process::ExitCode;

use clap::{Parser, Subcommand};
use factobot::agent::{self, agent_call, default_socket, parse_finite, parse_pair};
use serde_json::Value;

use crate::server::ServerConfig;

/// Play Factorio from the command line, and run the worlds agents play in.
/// Shares the agent's `--help` guidance (`agent::ABOUT`, `agent::GUIDANCE`).
#[derive(Parser)]
#[command(name = "fac", version, about = agent::ABOUT, long_about = format!("{}\n\n{}", agent::ABOUT, agent::GUIDANCE))]
struct Cli {
    /// Daemon socket.
    #[arg(long, env = "FACTOBOT_SOCKET", default_value_os_t = default_socket(), global = true)]
    socket: PathBuf,
    /// Harness debug socket [default: dev.sock next to --socket].
    #[arg(long, env = "FACTOBOT_DEV_SOCKET", global = true, hide = true)]
    dev_socket: Option<PathBuf>,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    #[command(flatten)]
    Agent(agent::Command),
    /// Run the daemon in the foreground: start a headless server, then serve
    /// agent commands until SIGINT, SIGTERM or SIGHUP, which save the world
    /// and stop the server. Harness use only.
    #[command(
        hide = true,
        after_help = "Examples:\n  fac daemon\n  fac daemon --seed 42 --camera\n  fac daemon --seed 42 --viewer          # watch in a window on $DISPLAY\n  fac daemon --listen 192.0.2.10        # let `fac watch` join from that network\n  fac daemon --save tests/worlds/start.zip\n  fac daemon --run-dir /tmp/fb-1 --rcon-port 27016 --game-port 34198 --socket /tmp/fb-1/fac.sock"
    )]
    Daemon {
        /// Extracted Factorio headless build.
        #[arg(long, env = "FACTOBOT_FACTORIO_DIR", default_value_os_t = default_factorio_dir())]
        factorio_dir: PathBuf,
        /// Scratch directory for this server's config, mods, save and logs.
        #[arg(long, env = "FACTOBOT_RUN_DIR", default_value_os_t = default_run_dir())]
        run_dir: PathBuf,
        /// The factobot Lua mod source.
        #[arg(long, env = "FACTOBOT_MOD_DIR", default_value = concat!(env!("CARGO_MANIFEST_DIR"), "/../../mod/factobot"))]
        mod_dir: PathBuf,
        #[arg(long, default_value_t = 34197)]
        game_port: u16,
        /// Address the game port listens on. Anyone who can reach it can
        /// join as a spectator with `fac watch`; RCON stays on localhost.
        #[arg(long, default_value = "127.0.0.1")]
        listen: IpAddr,
        #[arg(long, default_value_t = 27015)]
        rcon_port: u16,
        /// Map seed for a new world (only used when the run directory has no save).
        #[arg(long, conflicts_with = "save")]
        seed: Option<u32>,
        /// Start from a copy of this save (only used when the run directory has no save).
        #[arg(long)]
        save: Option<PathBuf>,
        /// Keep a spectator client on a private Xvfb display for `fac dev
        /// screenshot` and the agent's `fac screenshot`.
        #[arg(long)]
        camera: bool,
        /// Keep a spectator client open in a window on the current display.
        /// On a Hyprland desktop that needs the session's DISPLAY and WAYLAND_DISPLAY.
        #[arg(long)]
        viewer: bool,
        /// Extracted graphical Factorio build, for --camera and --viewer.
        #[arg(long, env = "FACTOBOT_CLIENT_DIR", default_value_os_t = default_client_dir())]
        client_dir: PathBuf,
    },
    /// Watch a daemon's game from another machine: open a spectator window
    /// on this display, joined to SERVER. DISPLAY must name a display the X
    /// server accepts. On a Hyprland desktop that is the session's DISPLAY=:0,
    /// and WAYLAND_DISPLAY must be that session's socket, or the window
    /// cannot attach. The daemon must listen on an address this machine
    /// reaches (`fac daemon --listen`), and this checkout's mod must match
    /// the daemon's file for file. SERVER is `host` or `host:port` (port
    /// 34197 when omitted). A playtest or rocket run prints the one to use on
    /// stderr (`watch with: fac watch <address>:<port>`). `mise run watch`
    /// passes its HOST environment variable as SERVER, and needs it set.
    /// Returns when the window closes. Harness use only.
    #[command(
        hide = true,
        after_help = "Examples:\n  fac watch gamehost\n  fac watch 192.0.2.10:34198\n  HOST=192.0.2.10:34198 mise run watch\n  fac watch gamehost --name factobot-watch-laptop\n\nRun this where DISPLAY is set, such as a terminal on that machine's desktop. On a Hyprland desktop also set WAYLAND_DISPLAY to the Hyprland socket, or the window cannot attach. A missing DISPLAY fails before Factorio starts."
    )]
    Watch {
        /// Server as `host` or `host:port` (port 34197 by default).
        server: String,
        /// Player name; must be unique on the server. It also names this
        /// client's state directory, so it cannot contain a path separator.
        #[arg(long, default_value_t = format!("factobot-watch-{}", hostname()), value_parser = parse_player_name)]
        name: String,
        /// The factobot Lua mod source.
        #[arg(long, env = "FACTOBOT_MOD_DIR", default_value = concat!(env!("CARGO_MANIFEST_DIR"), "/../../mod/factobot"))]
        mod_dir: PathBuf,
        /// Extracted graphical Factorio build.
        #[arg(long, env = "FACTOBOT_CLIENT_DIR", default_value_os_t = default_client_dir())]
        client_dir: PathBuf,
    },
    /// Harness debug tools on the dev socket. Agents do not get this socket.
    #[command(
        hide = true,
        subcommand,
        after_help = "Examples:\n  fac dev lua game.tick\n  fac dev reload\n  fac dev snapshot /tmp/before-build.zip\n  fac dev hash\n  fac dev milestones\n  fac dev screenshot"
    )]
    Dev(DevCommand),
}

#[derive(Subcommand)]
enum DevCommand {
    /// Run Lua in the game and print the result. Expressions return their
    /// value; statements return null. Reads stdin when CODE is `-`.
    #[command(
        after_help = "Examples:\n  fac dev lua game.tick\n  fac dev lua 'game.speed = 10'\n  fac dev lua - < setup.lua"
    )]
    Lua { code: String },
    /// Restart the server from its current state so mod changes take effect.
    #[command(after_help = "Examples:\n  fac dev reload")]
    Reload,
    /// Save the world to a zip (the server restarts to do it).
    #[command(after_help = "Examples:\n  fac dev snapshot /tmp/before-build.zip")]
    Snapshot { path: PathBuf },
    /// Deterministic fingerprint of every entity on the map, with the tick.
    #[command(after_help = "Examples:\n  fac dev hash")]
    Hash,
    /// Science milestones for scoring: per science pack, how many were made
    /// by hand and by machines, how many labs used, the tick labs first
    /// researched with a machine-made one, and machine-made packs so far at
    /// the end of each game minute; and the tick of the first rocket launch.
    #[command(after_help = "Examples:\n  fac dev milestones")]
    Milestones,
    /// Render part of the map to a PNG with the camera client (daemon needs
    /// --camera). Coordinates are map tiles; zoom 1 is the game's default.
    #[command(
        after_help = "Examples:\n  fac dev screenshot\n  fac dev screenshot --at 10,-4 --zoom 0.5 --size 1920x1080 -o /tmp/base.png"
    )]
    Screenshot {
        /// Map position at the centre of the image, as X,Y.
        #[arg(long, default_value = "0,0", value_parser = parse_pair)]
        at: (f64, f64),
        #[arg(long, default_value_t = 1.0, value_parser = parse_finite)]
        zoom: f64,
        /// Image size in pixels, as WIDTHxHEIGHT.
        #[arg(long, default_value = "1280x720", value_parser = parse_size)]
        size: (u32, u32),
        /// Where to write the PNG [default: <run dir>/screenshots/].
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
}

#[tokio::main]
async fn main() -> ExitCode {
    factobot::init_tracing();
    let cli = Cli::parse();
    match cli.command {
        Command::Agent(command) => {
            agent::run(agent::Cli {
                socket: cli.socket,
                command,
            })
            .await
        }
        Command::Daemon {
            factorio_dir,
            run_dir,
            mod_dir,
            game_port,
            listen,
            rcon_port,
            seed,
            save,
            camera,
            viewer,
            client_dir,
        } => {
            let config = ServerConfig {
                factorio_dir,
                run_dir,
                mod_dir,
                game_port,
                listen,
                rcon_port,
                seed,
                initial_save: save,
            };
            let viewers = daemon::Viewers {
                client_dir,
                kinds: [
                    (camera, viewer::Kind::Camera),
                    (viewer, viewer::Kind::Viewer),
                ]
                .into_iter()
                .filter_map(|(on, kind)| on.then_some(kind))
                .collect(),
            };
            let sockets = daemon::Sockets {
                dev: dev_socket(&cli.socket, cli.dev_socket),
                agent: cli.socket,
            };
            match daemon::run(config, viewers, sockets).await {
                Ok(()) => ExitCode::SUCCESS,
                Err(err) => {
                    eprintln!("fac daemon: {err:#}");
                    ExitCode::FAILURE
                }
            }
        }
        Command::Watch {
            server,
            name,
            mod_dir,
            client_dir,
        } => {
            let server = if server.contains(':') {
                server
            } else {
                format!("{server}:34197")
            };
            let state_dir = data_home("XDG_STATE_HOME", ".local/state").join("factobot/watch");
            match viewer::watch(&client_dir, &mod_dir, &state_dir, &server, &name).await {
                Ok(()) => ExitCode::SUCCESS,
                Err(err) => {
                    eprintln!("fac watch: {err:#}");
                    ExitCode::FAILURE
                }
            }
        }
        Command::Dev(command) => {
            let socket = dev_socket(&cli.socket, cli.dev_socket);
            let (method, params) = match command {
                DevCommand::Lua { code } => {
                    let code = if code == "-" {
                        match std::io::read_to_string(std::io::stdin()) {
                            Ok(code) => code,
                            Err(err) => {
                                eprintln!("fac dev lua: reading stdin: {err}");
                                return ExitCode::FAILURE;
                            }
                        }
                    } else {
                        code
                    };
                    ("lua", serde_json::json!({ "code": code }))
                }
                DevCommand::Reload => ("reload", Value::Null),
                DevCommand::Snapshot { path } => (
                    "snapshot",
                    serde_json::json!({ "path": absolute_path(path) }),
                ),
                DevCommand::Hash => ("world_hash", Value::Null),
                DevCommand::Milestones => ("milestones", Value::Null),
                DevCommand::Screenshot {
                    at: (x, y),
                    zoom,
                    size: (width, height),
                    output,
                } => {
                    let output = output.map(absolute_path);
                    (
                        "screenshot",
                        serde_json::json!({
                            "x": x, "y": y, "zoom": zoom,
                            "width": width, "height": height, "path": output,
                        }),
                    )
                }
            };
            agent_call(&socket, method, params).await
        }
    }
}

fn dev_socket(agent: &std::path::Path, explicit: Option<PathBuf>) -> PathBuf {
    explicit.unwrap_or_else(|| agent.with_file_name("dev.sock"))
}

/// An absolute path when the process can resolve one, otherwise `path` unchanged.
fn absolute_path(path: PathBuf) -> PathBuf {
    std::path::absolute(&path).unwrap_or(path)
}

fn parse_size(text: &str) -> Result<(u32, u32), String> {
    let (w, h) = text.split_once('x').ok_or("expected WIDTHxHEIGHT")?;
    match (w.parse(), h.parse()) {
        (Ok(w), Ok(h)) => Ok((w, h)),
        _ => Err(format!("expected WIDTHxHEIGHT, got {text:?}")),
    }
}

/// A player name that is a single plain path component, so joining it to the
/// watch state directory never leaves that directory.
fn parse_player_name(text: &str) -> Result<String, String> {
    let mut parts = std::path::Path::new(text).components();
    match (parts.next(), parts.next()) {
        (Some(std::path::Component::Normal(part)), None) if part == text => Ok(text.to_owned()),
        _ => Err(format!("expected a plain player name, got {text:?}")),
    }
}

fn data_home(var: &str, fallback: &str) -> PathBuf {
    std::env::var_os(var).map_or_else(
        || PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(fallback),
        PathBuf::from,
    )
}

fn hostname() -> String {
    std::fs::read_to_string("/proc/sys/kernel/hostname")
        .map(|name| name.trim().to_owned())
        .unwrap_or_else(|_| "host".into())
}

/// `FACTORIO_VERSION` comes from mise.toml, read at runtime or else baked in
/// when `fac` was built under mise.
fn factorio_version() -> String {
    std::env::var("FACTORIO_VERSION")
        .ok()
        .or(option_env!("FACTORIO_VERSION").map(str::to_owned))
        .unwrap_or_default()
}

fn default_factorio_dir() -> PathBuf {
    data_home("XDG_CACHE_HOME", ".cache")
        .join("factobot/factorio")
        .join(factorio_version())
}

/// Where `scripts/fetch-factorio --client` puts the graphical build.
fn default_client_dir() -> PathBuf {
    data_home("XDG_CACHE_HOME", ".cache")
        .join("factobot/factorio")
        .join(format!("{}-client", factorio_version()))
}

fn default_run_dir() -> PathBuf {
    data_home("XDG_STATE_HOME", ".local/state").join("factobot/run")
}

#[cfg(test)]
mod tests {
    use clap::CommandFactory;

    use super::*;

    #[test]
    fn long_help_holds_the_guidance() {
        let long_about = Cli::command().get_long_about().unwrap().to_string();
        assert!(long_about.contains(agent::GUIDANCE));
    }
}
