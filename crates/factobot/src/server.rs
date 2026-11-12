//! Supervises one Factorio headless server: prepares its run directory,
//! starts it with the factobot mod and RCON on localhost, and stops it.
//! The game port listens on localhost too unless `listen` names another
//! address for remote spectators (`fac watch`).
//!
//! Only the daemon stops the server, by RCON `/quit`, so the server saves
//! exactly once. Factorio saves when it gets SIGTERM or SIGINT but dies at
//! once, mid-save, on a second one, and `systemctl stop` sends a second
//! SIGTERM to the whole unit as soon as its main process exits. The server
//! therefore runs in its own process group (a terminal's Ctrl-C reaches the
//! daemon only), with SIGTERM blocked (signals sent to every process of a
//! unit or session never reach it). A daemon killed outright takes the
//! server with it, unsaved, as it did when they shared a process group.

use std::fs;
use std::net::{IpAddr, SocketAddr};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::{Duration, Instant};
use std::{io, ptr};

use anyhow::{Context, Result, bail};
use rand::distr::{Alphanumeric, SampleString};
use serde_json::json;
use tokio::process::{Child, Command};

use crate::rcon::{Rcon, RconError};

const STARTUP_TIMEOUT: Duration = Duration::from_secs(90);
/// One command. A slow `server_save` can outlive this; the client then drops
/// a half-read packet and reconnects, and the playtest logs the miss and
/// continues (decision 86). Kept under the gap between this and the harness's
/// 90 s stop wait, so `/quit` plus `SHUTDOWN_TIMEOUT` still finishes in time.
const RCON_TIMEOUT: Duration = Duration::from_secs(10);
/// How long a quitting server may take to save before it is killed. Saves
/// of large factories take seconds; this stays under systemd's default
/// TimeoutStopSec of 90 s, and the harness waits longer for the daemon.
const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(60);

/// Built-in content packs that ship with the 2.x headless build (which
/// bundles the expansion) and stay off: the benchmark targets the base game
/// only (decision 8), and a base-game client cannot join a server running them.
const DISABLED_BUILTIN_MODS: [&str; 4] = ["space-age", "quality", "elevated-rails", "recycler"];

#[derive(Debug, Clone)]
pub struct ServerConfig {
    /// Extracted headless build: contains `bin/x64/factorio` and `data/`.
    pub factorio_dir: PathBuf,
    /// Scratch directory owned by this server: config, mods, save, logs.
    pub run_dir: PathBuf,
    /// Source of the factobot Lua mod (`mod/factobot` in the repo).
    pub mod_dir: PathBuf,
    pub game_port: u16,
    /// Address the game port listens on. Factorio binds one address only,
    /// so the daemon's own camera and viewer connect here too.
    pub listen: IpAddr,
    pub rcon_port: u16,
    /// Map seed for a new world. Ignored when the run directory already has
    /// a save or `initial_save` is set.
    pub seed: Option<u32>,
    /// Start from a copy of this save instead of generating a world.
    pub initial_save: Option<PathBuf>,
}

impl ServerConfig {
    /// Where game clients connect.
    pub fn game_addr(&self) -> SocketAddr {
        SocketAddr::new(self.listen, self.game_port)
    }
}

pub struct Server {
    child: Child,
    log_path: PathBuf,
}

impl Server {
    pub async fn start(config: &ServerConfig) -> Result<(Self, Rcon)> {
        let binary = config.factorio_dir.join("bin/x64/factorio");
        if !binary.is_file() {
            bail!(
                "no Factorio binary at {}; run `mise run fetch-factorio` or pass --factorio-dir",
                binary.display()
            );
        }
        let mod_dir = config
            .mod_dir
            .canonicalize()
            .with_context(|| format!("mod directory {}", config.mod_dir.display()))?;
        let run = prepare_run_dir(config, &mod_dir)?;

        if !run.save.exists() {
            match &config.initial_save {
                Some(initial) => {
                    fs::copy(initial, &run.save)
                        .with_context(|| format!("copying save {}", initial.display()))?;
                }
                None => create_save(&binary, &run, config.seed).await?,
            }
        }

        let password = Alphanumeric.sample_string(&mut rand::rng(), 32);
        let rcon_addr = format!("127.0.0.1:{}", config.rcon_port);
        let log_path = config.run_dir.join("server.log");
        // Append: a restart (`fac dev reload`) keeps the earlier log.
        let log = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .with_context(|| format!("opening {}", log_path.display()))?;
        let mut command = Command::new(&binary);
        command
            .arg("--config")
            .arg(&run.config_ini)
            .arg("--mod-directory")
            .arg(&run.mods)
            .arg("--start-server")
            .arg(&run.save)
            .arg("--server-settings")
            .arg(&run.server_settings)
            // Localhost unless `listen` says otherwise: anyone who can reach
            // the port can join, and the mod makes every player a spectator.
            .arg("--bind")
            .arg(config.game_addr().to_string())
            .arg("--rcon-bind")
            .arg(&rcon_addr)
            .arg("--rcon-password")
            .arg(&password)
            .stdin(Stdio::null())
            .stdout(Stdio::from(log.try_clone()?))
            .stderr(Stdio::from(log))
            .kill_on_drop(true)
            .process_group(0);
        shield_from_signals(&mut command);
        let child = command
            .spawn()
            .with_context(|| format!("starting {}", binary.display()))?;
        let mut server = Self { child, log_path };
        let rcon = server.wait_for_rcon(&rcon_addr, &password).await?;
        Ok((server, rcon))
    }

    async fn wait_for_rcon(&mut self, addr: &str, password: &str) -> Result<Rcon> {
        let started = Instant::now();
        loop {
            if let Some(status) = self.child.try_wait()? {
                bail!(
                    "Factorio exited during startup ({status}); see {}",
                    self.log_path.display()
                );
            }
            match Rcon::connect(addr, password, RCON_TIMEOUT).await {
                Ok(rcon) => return Ok(rcon),
                Err(RconError::AuthRejected) => bail!("RCON rejected the generated password"),
                Err(_) if started.elapsed() < STARTUP_TIMEOUT => {
                    tokio::time::sleep(Duration::from_millis(250)).await;
                }
                Err(err) => bail!(
                    "RCON not reachable at {addr} after {STARTUP_TIMEOUT:?}: {err}; see {}",
                    self.log_path.display()
                ),
            }
        }
    }

    /// The exit status if the server process has already exited.
    pub fn exit_status(&mut self) -> Option<std::process::ExitStatus> {
        self.child.try_wait().ok().flatten()
    }

    /// Ask the server to quit (it saves first), wait for it, and kill it
    /// only if it is still running after `SHUTDOWN_TIMEOUT`.
    pub async fn stop(&mut self, rcon: Option<&mut Rcon>) -> Result<()> {
        if let Some(rcon) = rcon {
            // The connection drops as the server exits, so an error here is
            // expected. A server already quitting on a SIGINT of its own
            // ignores the command and saves anyway; either way, wait.
            let _ = rcon.exec("/quit").await;
        }
        match tokio::time::timeout(SHUTDOWN_TIMEOUT, self.child.wait()).await {
            Ok(status) => {
                status?;
            }
            Err(_) => {
                tracing::warn!("Factorio did not quit within {SHUTDOWN_TIMEOUT:?}; killing it");
                self.child.kill().await?;
            }
        }
        Ok(())
    }
}

/// Block SIGTERM in the server and kill it when the daemon dies (see the
/// module docs). Factorio keeps an inherited signal mask in every thread
/// (probed on 2.1.24: SIGTERM stays pending, SIGINT still saves).
#[allow(unsafe_code)]
fn shield_from_signals(command: &mut Command) {
    let daemon = std::process::id();
    // SAFETY: the closure runs in the forked child before exec and calls
    // only async-signal-safe functions on its own stack.
    unsafe {
        command.pre_exec(move || {
            let mut set = std::mem::zeroed::<libc::sigset_t>();
            libc::sigemptyset(&mut set);
            libc::sigaddset(&mut set, libc::SIGTERM);
            let err = libc::pthread_sigmask(libc::SIG_BLOCK, &set, ptr::null_mut());
            if err != 0 {
                return Err(io::Error::from_raw_os_error(err));
            }
            // A saving death signal would be no use: the kernel sends it
            // again each time the server is handed to another of the dying
            // daemon's threads, and the second one cuts the save short
            // (probed with SIGINT). It is sent when the forking thread
            // exits, and tokio's worker threads live as long as the daemon.
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) == -1 {
                return Err(io::Error::last_os_error());
            }
            // The daemon died before the death signal was armed. Only the
            // errno reaches the parent, and a raw one needs no allocation.
            if libc::getppid() != daemon as libc::pid_t {
                return Err(io::Error::from_raw_os_error(libc::ESRCH));
            }
            Ok(())
        });
    }
}

struct RunPaths {
    config_ini: PathBuf,
    mods: PathBuf,
    save: PathBuf,
    server_settings: PathBuf,
    map_gen_settings: PathBuf,
}

fn prepare_run_dir(config: &ServerConfig, mod_dir: &Path) -> Result<RunPaths> {
    let run_dir = &config.run_dir;
    let mods = run_dir.join("mods");
    let write_data = run_dir.join("write-data");
    fs::create_dir_all(&mods)?;
    fs::create_dir_all(&write_data)?;

    let config_ini = run_dir.join("config.ini");
    fs::write(
        &config_ini,
        format!(
            "[path]\nread-data={}\nwrite-data={}\n",
            config.factorio_dir.join("data").display(),
            write_data.display()
        ),
    )?;

    write_mods(&mods, mod_dir)?;

    let server_settings = run_dir.join("server-settings.json");
    fs::write(
        &server_settings,
        serde_json::to_vec_pretty(&json!({
            "name": "factobot",
            "description": "factobot benchmark environment",
            "visibility": {"public": false, "lan": false},
            "require_user_verification": false,
            // Real-time play (decision 2): the world keeps running with no
            // players connected.
            "auto_pause": false,
            "autosave_interval": 0,
        }))?,
    )?;

    // Decision 9: peaceful, and no enemy bases at all. Unlisted fields keep
    // Factorio's defaults.
    let map_gen_settings = run_dir.join("map-gen-settings.json");
    fs::write(
        &map_gen_settings,
        serde_json::to_vec_pretty(&json!({
            "peaceful_mode": true,
            "autoplace_controls": {"enemy-base": {"frequency": 0, "size": 0}},
        }))?,
    )?;

    Ok(RunPaths {
        config_ini,
        mods,
        save: run_dir.join("save.zip"),
        server_settings,
        map_gen_settings,
    })
}

/// Fill a mod directory with the server's mod set: base and factobot on,
/// the built-in content packs off, factobot linked from `mod_dir`. A client
/// can only join with the same set, so `fac watch` uses this too.
pub fn write_mods(mods: &Path, mod_dir: &Path) -> Result<()> {
    fs::create_dir_all(mods)?;
    let mut mod_list = vec![
        json!({"name": "base", "enabled": true}),
        json!({"name": "factobot", "enabled": true}),
    ];
    mod_list.extend(
        DISABLED_BUILTIN_MODS
            .iter()
            .map(|name| json!({"name": name, "enabled": false})),
    );
    fs::write(
        mods.join("mod-list.json"),
        serde_json::to_vec_pretty(&json!({ "mods": mod_list }))?,
    )?;

    let link = mods.join("factobot");
    if link.symlink_metadata().is_ok() {
        fs::remove_file(&link).with_context(|| format!("replacing {}", link.display()))?;
    }
    std::os::unix::fs::symlink(mod_dir, &link)
        .with_context(|| format!("linking {} -> {}", link.display(), mod_dir.display()))
}

async fn create_save(binary: &Path, run: &RunPaths, seed: Option<u32>) -> Result<()> {
    let mut command = Command::new(binary);
    command
        .arg("--config")
        .arg(&run.config_ini)
        .arg("--mod-directory")
        .arg(&run.mods)
        .arg("--create")
        .arg(&run.save)
        .arg("--map-gen-settings")
        .arg(&run.map_gen_settings);
    if let Some(seed) = seed {
        command.arg("--map-gen-seed").arg(seed.to_string());
    }
    let output = command
        .stdin(Stdio::null())
        .output()
        .await
        .context("running factorio --create")?;
    if !output.status.success() {
        // The load log is on stdout and the reason is usually on stderr.
        // Keeping only stdout hides why the world was not created.
        bail!(
            "{}",
            failed_create_message(output.status, &output.stdout, &output.stderr)
        );
    }
    Ok(())
}

/// Text of a failed `factorio --create`. Empty streams are left out so a
/// process that wrote on only one of them does not add a blank section.
fn failed_create_message(status: std::process::ExitStatus, stdout: &[u8], stderr: &[u8]) -> String {
    let mut message = format!("factorio --create failed ({status}):\n");
    for (label, bytes) in [("stdout", stdout), ("stderr", stderr)] {
        if bytes.is_empty() {
            continue;
        }
        let text = String::from_utf8_lossy(bytes);
        message.push_str(label);
        message.push_str(":\n");
        message.push_str(&text);
        if !text.ends_with('\n') {
            message.push('\n');
        }
    }
    message
}

#[cfg(test)]
mod tests {
    use std::os::unix::process::ExitStatusExt;
    use std::process::ExitStatus;

    use super::*;

    #[test]
    fn failed_create_message_includes_stderr() {
        let status = ExitStatus::from_raw(3 << 8);
        let msg = failed_create_message(status, b"loading data", b"Error: bad map settings");
        assert!(
            msg.contains("factorio --create failed (exit status: 3):"),
            "{msg}"
        );
        assert!(msg.contains("stdout:\nloading data\nstderr:\n"), "{msg}");
        assert!(msg.contains("Error: bad map settings\n"), "{msg}");
    }
}
