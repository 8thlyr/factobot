"""Start and drive throwaway game worlds for tests and development.

A `World` is one `fac daemon` with its own headless server, run directory,
ports and sockets. Use `world.agent` for what an agent may call and
`world.dev` (or the helpers below) for harness-only tools.

    with start_world(seed=7, speed=10) as world:
        world.lua('game.surfaces[1].create_entity{name="wooden-chest", position={0, 0}}')
        world.run_ticks(600)
        print(world.world_hash())
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factobot.client import Client

PR_SET_PDEATHSIG = 1  # linux/prctl.h
# Seconds the daemon gets to save and stop its server; longer than its own
# 60 s limit for the server.
DAEMON_STOP_TIMEOUT = 90.0
# After SIGKILL, how long to wait for the daemon to disappear. A process stuck
# in uninterruptible sleep is left unreaped rather than waited on forever.
DAEMON_KILL_TIMEOUT = 5.0


def _free_port(kind: int) -> int:
    with socket.socket(socket.AF_INET, kind) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def find_fac() -> Path:
    """`FACTOBOT_FAC`, else `fac` on PATH, else this checkout's `target/debug/fac`."""
    if explicit := os.environ.get("FACTOBOT_FAC"):
        return Path(explicit)
    if found := shutil.which("fac"):
        return Path(found)
    # python/src/factobot/harness.py -> the checkout root, when this is one.
    repo = Path(__file__).resolve().parents[3]
    if not (repo / "Cargo.toml").exists():
        raise FileNotFoundError("no fac binary: set FACTOBOT_FAC or put fac on PATH")
    if (built := repo / "target" / "debug" / "fac").exists():
        return built
    raise FileNotFoundError(
        f"no fac binary: set FACTOBOT_FAC, put fac on PATH, or run cargo build in {repo}"
    )


def find_agent_fac() -> Path:
    """The agent's `fac`: `fac-agent` next to `find_fac()`, built with it.

    It has the agent commands only, no `daemon`, `watch` or `dev` (decision 64).
    """
    agent = find_fac().resolve().with_name("fac-agent")
    if not agent.exists():
        raise FileNotFoundError(f"no {agent}: `cargo build` builds it next to fac")
    return agent


@dataclass
class World:
    run_dir: Path
    agent: Client
    dev: Client
    process: subprocess.Popen[bytes]
    game_port: int

    def lua(self, code: str) -> Any:
        """Run Lua in the game; expressions return their value."""
        return self.dev.call("lua", {"code": code})

    def tick(self) -> int:
        return int(self.lua("game.tick"))

    def world_hash(self) -> dict[str, Any]:
        return self.dev.call("world_hash")

    def milestones(self) -> dict[str, Any]:
        """Science and rocket milestones the harness scores from (protocol `milestones`)."""
        return self.dev.call("milestones")

    def snapshot(self, path: str | os.PathLike[str]) -> Path:
        """Save the world to `path`; the server restarts to do it."""
        return Path(self.dev.call("snapshot", {"path": os.fspath(Path(path).absolute())})["path"])

    def reload(self) -> None:
        """Restart the server from its current state, picking up mod changes."""
        self.dev.call("reload")

    def pause(self) -> None:
        self.lua("game.tick_paused = true")

    def run_ticks(self, ticks: int, timeout: float = 120.0) -> int:
        """Pause, advance exactly `ticks` ticks, and stay paused. Returns the tick."""
        self.pause()
        if ticks > 0:
            self.lua(f"game.ticks_to_run = {ticks}")
            deadline = time.monotonic() + timeout
            while self.lua("game.ticks_to_run") != 0:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"{ticks} ticks did not finish in {timeout} s")
                time.sleep(0.02)
        return self.tick()

    def run_to_tick(self, tick: int) -> int:
        """Pause and advance to exactly `tick` (which must not have passed yet)."""
        self.pause()
        now = self.tick()
        if now > tick:
            raise ValueError(f"tick {tick} has already passed (now {now})")
        return self.run_ticks(tick - now)

    def calls(self) -> list[dict[str, Any]]:
        """Entries of the daemon's call log so far.

        A read can land while the daemon is still writing a line. That fragment
        has no newline yet and is not a record (decision 86).
        """
        return read_jsonl(self.run_dir / "calls.jsonl")

    def screenshot(
        self,
        path: str | os.PathLike[str],
        *,
        at: tuple[float, float] = (0.0, 0.0),
        zoom: float = 1.0,
        size: tuple[int, int] = (1280, 720),
    ) -> Path:
        """Render the map around `at` to a PNG (needs `start_world(camera=True)`)."""
        result = self.dev.call(
            "screenshot",
            {
                "x": at[0],
                "y": at[1],
                "zoom": zoom,
                "width": size[0],
                "height": size[1],
                "path": os.fspath(Path(path).absolute()),
            },
        )
        return Path(result["path"])

    @property
    def agent_socket(self) -> Path:
        """The only socket an agent may be given (alone in its directory)."""
        return self.run_dir / "agent" / "fac.sock"


def _die_with_parent(parent: int) -> Callable[[], None]:
    """Make the daemon get SIGTERM, and stop its server and clients, when the
    process that started it dies. A test run killed outright (a timeout, a
    killed kernel) never reaches its cleanup, and its worlds used to keep
    running for hours."""

    # Looked up here, not in the forked child: dlopen/dlsym take the loader's
    # lock, which another thread may have held at fork time.
    prctl = ctypes.CDLL(None, use_errno=True).prctl

    def setup() -> None:
        prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
        if os.getppid() != parent:  # the parent died before prctl took effect
            os._exit(1)

    return setup


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """JSON objects in `path`, ignoring a trailing line the writer has not finished.

    `calls.jsonl` is appended one record at a time, each ending in a newline.
    A read that lands mid-write sees a fragment with no newline; that fragment
    is not a record yet. A finished line that is not JSON is an error.
    """
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return []
    if not data.endswith(b"\n"):
        data = data.rpartition(b"\n")[0]
    records: list[dict[str, Any]] = []
    for line in data.splitlines():
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path} has a JSON value that is not an object")
        records.append(value)
    return records


def stop_daemon(process: subprocess.Popen[bytes], *, timeout: float = DAEMON_STOP_TIMEOUT) -> None:
    """SIGTERM `process` so it can save, then SIGKILL its process group if it stays up.

    The Factorio server is not in this group; it dies with the daemon. A daemon
    that exits as the signal is sent is reaped. One that survives SIGKILL is
    left unreaped rather than waited on forever.
    """
    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=DAEMON_KILL_TIMEOUT)
        return
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if process.poll() is not None:
            return
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=DAEMON_KILL_TIMEOUT)


@contextmanager
def start_world(
    *,
    seed: int | None = None,
    save: str | os.PathLike[str] | None = None,
    speed: float | None = None,
    setup: str | None = None,
    run_dir: str | os.PathLike[str] | None = None,
    fac: str | os.PathLike[str] | None = None,
    camera: bool = False,
    viewer: bool = False,
    listen: str | None = None,
    startup_timeout: float = 120.0,
) -> Iterator[World]:
    """Boot a world, yield it, and stop it (saving) on exit.

    `seed` generates a new map; `save` starts from a copy of a save instead.
    `speed` sets `game.speed`; `setup` is Lua run once the world is up.
    `camera` adds a spectator client on a private Xvfb for `World.screenshot`;
    `viewer` opens a spectator window on the current display. Both need the
    graphical build and add up to a minute of startup. `listen` sets the
    address the game port listens on (localhost by default), for `fac watch`.
    A temporary run directory is deleted afterwards unless the daemon failed.
    """
    fac_path = Path(fac) if fac else find_fac()
    owned_dir = run_dir is None
    root = Path(run_dir) if run_dir else Path(tempfile.mkdtemp(prefix="factobot-world-"))
    root.mkdir(parents=True, exist_ok=True)
    # Separate directories, so an agent can be given the agent socket's
    # directory without the dev socket in it.
    agent_sock, dev_sock = root / "agent" / "fac.sock", root / "dev" / "dev.sock"
    if camera or viewer:
        startup_timeout = max(startup_timeout, 300.0)

    game_port = _free_port(socket.SOCK_DGRAM)
    args = [
        os.fspath(fac_path),
        "daemon",
        "--run-dir",
        os.fspath(root),
        "--rcon-port",
        str(_free_port(socket.SOCK_STREAM)),
        "--game-port",
        str(game_port),
    ]
    if listen is not None:
        args += ["--listen", listen]
    if seed is not None:
        args += ["--seed", str(seed)]
    if save is not None:
        args += ["--save", os.fspath(Path(save).absolute())]
    if camera:
        args.append("--camera")
    if viewer:
        args.append("--viewer")

    log_path = root / "daemon.log"
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            args,
            env={
                **os.environ,
                "FACTOBOT_SOCKET": os.fspath(agent_sock),
                "FACTOBOT_DEV_SOCKET": os.fspath(dev_sock),
            },
            stdout=log,
            stderr=subprocess.STDOUT,
            # Own session and process group, so a hung daemon can be killed
            # with its clients; its server, in a group of its own, dies with it.
            start_new_session=True,
            preexec_fn=_die_with_parent(os.getpid()),
        )
    clients: list[Client] = []
    try:
        deadline = time.monotonic() + startup_timeout
        while b"daemon ready" not in log_path.read_bytes():
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("fac daemon did not start:\n" + log_path.read_text())
            time.sleep(0.1)
        agent, dev = Client(agent_sock), Client(dev_sock)
        clients += [agent, dev]
        world = World(run_dir=root, agent=agent, dev=dev, process=process, game_port=game_port)
        if speed is not None:
            world.lua(f"game.speed = {speed}")
        if setup:
            world.lua(setup)
        yield world
    finally:
        # A client that fails to close must not skip stopping the daemon.
        try:
            for client in clients:
                client.close()
        finally:
            # The daemon saves and stops the server; never signal the server
            # too, since a second signal kills a saving server outright.
            stop_daemon(process)
            if owned_dir and process.returncode == 0:
                shutil.rmtree(root, ignore_errors=True)
