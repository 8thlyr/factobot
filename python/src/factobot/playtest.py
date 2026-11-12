"""Playtest the `fac` CLI with a real agent harness before it is benchmarked.

    python -m factobot.playtest playtests/smoke.md --model sonnet
    python -m factobot.playtest playtests/smoke.md --agent omp --model sonnet
    python -m factobot.playtest playtests/smoke.md -- my-agent --print {prompt}

Boots a fresh world (or a copy of a save), then runs an agent harness
headless against it: Claude Code, omp, or any command line given after `--`.
Every harness runs in the same bubblewrap sandbox (`factobot.sandbox`), which
shows it the `fac` CLI, the agent socket and a throwaway home with only what
the harness needs to log in, plus any skills given with `--skill`. With
`--until`, an agent that quits before the milestone is resumed in the same
conversation. Everything lands in one directory for review: the harness's
stdout, the daemon's call log, autosaves and a summary.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

from factobot import sandbox
from factobot.client import PROTOCOL_VERSION, FactobotError
from factobot.harness import World, find_agent_fac, start_world

PREAMBLE = """\
You are playing Factorio through the `fac` command-line tool. The game is
running in real time. Run `fac --help` to see the commands; every command
prints one JSON object. The game is reachable only through `fac`.

Your task:

"""

DEFAULT_MODEL = "sonnet"

CLAUDE_FLAGS = [
    "--output-format",
    "stream-json",
    "--verbose",
    "--tools",
    "Bash,Read",
    # The sandbox, not Claude Code's permission rules, limits what the agent
    # reaches, so it gets the same shell as every other harness. Read is there
    # to look at the PNG `fac screenshot` writes: a shell sees only its path.
    "--permission-mode",
    "bypassPermissions",
    # No user settings, CLAUDE.md, skills or MCP servers from the host. The
    # session is saved in the sandbox home, which is deleted after the run, so
    # an agent that stops early can be resumed.
    "--setting-sources",
    "local",
    "--strict-mcp-config",
    "--disable-slash-commands",
]

# With --skill: Claude Code reads ~/.claude/skills only with the `user` setting
# source (here the sandbox home's, which holds nothing else), runs them through
# its Skill tool, and --disable-slash-commands would turn them off.
CLAUDE_SKILL_FLAGS = [
    "--output-format",
    "stream-json",
    "--verbose",
    "--tools",
    "Bash,Read,Skill",
    "--permission-mode",
    "bypassPermissions",
    "--setting-sources",
    "user,local",
    "--strict-mcp-config",
]

OMP_FLAGS = [
    "--mode",
    "json",
    "--tools",
    # read, as Claude Code's Read, shows the agent a `fac screenshot` PNG.
    "bash,read",
    # No rules, AGENTS.md, extensions or language servers. Skills are only the
    # ones given with --skill (`--no-skills` without any). The session is saved
    # in the sandbox home, which is deleted after the run, so an agent that
    # stops early can be resumed.
    "--no-rules",
    "--no-context-files",
    "--no-extensions",
    "--no-lsp",
    "--session-dir",
    f"{sandbox.HOME}/sessions",
    "--no-title",
    "--approval-mode",
    "yolo",
]

# Seconds to wait for the runner's own stop signal once the agent or the daemon
# has gone from one: systemd and a closed terminal signal every process of the
# run, in no set order.
STOP_SIGNAL_GRACE = 2.0
# How often the runner checks for its stop signal while it waits for one.
STOP_POLL_INTERVAL = 0.05


def _stop_within(stop: threading.Event | None, seconds: float) -> bool:
    """Whether `stop` is set now or within `seconds`.

    Polls `is_set()` rather than calling `stop.wait()`: the signal handler sets
    `stop` on this same thread, and `Event.wait` holds the event's lock, which
    `Event.set` in a handler that interrupts it would then block on forever.
    `is_set()` takes no lock.
    """
    if stop is None:
        return False
    deadline = time.monotonic() + seconds
    while not stop.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(STOP_POLL_INTERVAL, remaining))
    return True


def _set_on_signals(stop: threading.Event, signums: tuple[signal.Signals, ...]) -> None:
    """Set `stop` on the first of `signums`; later ones are swallowed, except that
    a second Ctrl-C (SIGINT) interrupts the runner at once.

    The handler runs on the main thread and `Event.set` takes the event's lock,
    so a second signal whose handler set `stop` again while the first still
    held that lock would block forever. The first call swaps in a no-op before
    it takes the lock, and the main thread only ever calls `is_set()`.

    A SIGHUP or SIGINT the runner was started ignoring (by `nohup`, say) stays
    ignored.
    """
    signums = tuple(
        signum
        for signum in signums
        if signum not in (signal.SIGHUP, signal.SIGINT)
        or signal.getsignal(signum) is not signal.SIG_IGN
    )

    def arm_interrupt(*_: object) -> None:
        signal.signal(signal.SIGINT, signal.default_int_handler)

    def on_signal(first: int, _frame: object) -> None:
        for signum in signums:
            signal.signal(signum, lambda *_: None)
        if signal.SIGINT in signums:
            signal.signal(
                signal.SIGINT,
                signal.default_int_handler if first == signal.SIGINT else arm_interrupt,
            )
        stop.set()

    for signum in signums:
        signal.signal(signum, on_signal)


# How many times an agent that quits before the --until milestone is resumed.
DEFAULT_MAX_RESUMES = 10

# An agent process that exits non-zero this soon after it started, with no
# `fac` call, failed to start (a login or network error, say) rather than
# quit; after QUICK_FAILURE_LIMIT of those in a row, resuming stops.
QUICK_FAILURE_SECONDS = 30.0
QUICK_FAILURE_LIMIT = 2

# Autosaves rotate through this many files, so one cut short by a kill
# leaves the others intact.
AUTOSAVE_SLOTS = 3
# After a failed autosave, wait this long (or the autosave interval, if it is
# shorter) before trying again. The game may still be writing the save.
AUTOSAVE_RETRY_SECONDS = 30.0


# The file in its working directory an agent keeps its own notes in, by the
# rocket task's prompt. The run directory keeps a copy (decision 85).
NOTES_FILE = "notes.md"
TICKS_PER_MINUTE = 3600

# `summary.json` shape. docs/run-record.md lists the keys.
SCHEMA = 1

# `fac ... --wait` blocks for up to 600 s, so a harness's shell must not cut it
# off or move it to the background sooner (milliseconds, with some slack).
BASH_TIMEOUT_MS = "660000"

# omp moves a bash call that runs past 60 s to a background job and returns at
# once, so the agent would go on before a long `fac ... --wait` ends. Its own
# per-call timeout (300 s unless the model asks for more) is not a setting.
OMP_CONFIG = "bash:\n  autoBackground:\n    enabled: false\n"


@dataclass
class Harness:
    """How to start one agent harness inside the sandbox."""

    name: str
    command: list[str]
    binaries: dict[str, Path]
    # The command that continues the run after the agent quit early, given the
    # transcript so far and the message to send.
    resume: Callable[[list[dict[str, Any]], str], list[str]]
    env: dict[str, str] = field(default_factory=dict)
    expose: list[Path] = field(default_factory=list)
    # Host addresses and TCP ports the sandbox may reach although they are on
    # the host or its LAN or tailnet (see `sandbox.start`).
    allow: list[tuple[str, int]] = field(default_factory=list)
    # Runs after the agent stops, before its home is deleted.
    finish: Callable[[], None] = lambda: None


def claude_harness(prompt: str, model: str, home: Path, skills: Sequence[Path] = ()) -> Harness:
    """Claude Code, logged in with a copy of the host's Claude.ai OAuth login and nothing else."""
    host_file = Path.home() / ".claude" / ".credentials.json"
    login = json.loads(host_file.read_text()).get("claudeAiOauth") if host_file.exists() else None
    if not login:
        raise SystemExit(f"Claude Code has no login in {host_file}; run `claude` and log in")
    _write_private(home / ".claude" / ".credentials.json", {"claudeAiOauth": login})
    _install_skills(skills, home / ".claude" / "skills")
    claude = f"{sandbox.AGENT_BIN}/claude"
    flags = ["--model", model, *(CLAUDE_SKILL_FLAGS if skills else CLAUDE_FLAGS)]

    def resume(events: list[dict[str, Any]], message: str) -> list[str]:
        session = _last_session(events, "system", "session_id")
        if session is None:
            return [claude, "-p", f"{prompt}\n\n{message}", *flags]
        return [claude, "-p", message, "--resume", session, *flags]

    return Harness(
        name="claude",
        command=[claude, "-p", prompt, *flags],
        binaries={"claude": sandbox.resolve_binary("claude")},
        resume=resume,
        env={
            "DISABLE_AUTOUPDATER": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            # Bash calls default to 120 s, after which Claude Code backgrounds them;
            # `fac ... --wait` may block for up to 600 s.
            "BASH_DEFAULT_TIMEOUT_MS": BASH_TIMEOUT_MS,
            "BASH_MAX_TIMEOUT_MS": BASH_TIMEOUT_MS,
        },
        finish=lambda: _return_refreshed_login(host_file, login, home),
    )


def omp_harness(prompt: str, model: str, home: Path, skills: Sequence[Path] = ()) -> Harness:
    """omp, logged in through the host's auth broker: its URL and bearer token only."""
    url = os.environ.get("OMP_AUTH_BROKER_URL")
    token = Path.home() / ".omp" / "auth-broker.token"
    if not url or not token.exists():
        raise SystemExit(
            "omp runs through an auth broker here: set OMP_AUTH_BROKER_URL and keep its "
            f"token in {token}"
        )
    (home / ".omp").mkdir(mode=0o700, parents=True, exist_ok=True)
    shutil.copyfile(token, home / ".omp" / "auth-broker.token")
    (home / ".omp" / "auth-broker.token").chmod(0o600)
    (home / "sessions").mkdir()
    _install_skills(skills, home / ".omp" / "agent" / "skills")
    (home / ".omp" / "agent").mkdir(exist_ok=True)
    (home / ".omp" / "agent" / "config.yml").write_text(OMP_CONFIG)
    omp = f"{sandbox.AGENT_BIN}/omp"
    only_skills = (
        ["--skills", ",".join(skill.name for skill in skills)] if skills else ["--no-skills"]
    )
    flags = ["--model", model, *OMP_FLAGS, *only_skills]

    def resume(events: list[dict[str, Any]], message: str) -> list[str]:
        session = _last_session(events, "session", "id")
        if session is None:
            return [omp, "-p", *flags, f"{prompt}\n\n{message}"]
        return [omp, "-p", *flags, "--resume", session, message]

    return Harness(
        name="omp",
        command=[omp, "-p", *flags, prompt],
        binaries={"omp": sandbox.resolve_binary("omp")},
        resume=resume,
        env={"OMP_AUTH_BROKER_URL": url},
        allow=_broker_address(url),
    )


def _broker_address(url: str) -> list[tuple[str, int]]:
    """The IPv4 address and TCP port of the auth broker at `url`, which usually runs on
    this host's tailnet address, where the sandbox may otherwise not connect."""
    parts = urllib.parse.urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if not parts.hostname:
        raise SystemExit(f"OMP_AUTH_BROKER_URL has no host: {url}")
    try:
        found = socket.getaddrinfo(parts.hostname, port, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror as err:
        raise SystemExit(f"cannot resolve the auth broker's host {parts.hostname}: {err}") from err
    return sorted({(str(info[4][0]), port) for info in found})


def custom_harness(
    argv: list[str], prompt: str, *, env_names: list[str], expose: list[Path]
) -> Harness:
    """Any other harness: `{prompt}` in an argument becomes the prompt text.

    It has no session the runner knows how to resume, so a resume starts the
    command again with the task and the continuation message as the prompt.
    Its home is kept between the two, for a harness that saves its own state.
    """
    if not any("{prompt}" in arg for arg in argv):
        raise SystemExit("the agent command needs {prompt} in one of its arguments")
    binary = Path(argv[0]).resolve() if "/" in argv[0] else sandbox.resolve_binary(argv[0])
    name = Path(argv[0]).name
    binaries: dict[str, Path] = {}
    if binary.is_relative_to("/usr"):
        executable = os.fspath(binary)
    else:
        binaries[name] = binary
        executable = f"{sandbox.AGENT_BIN}/{name}"
    missing = [env for env in env_names if env not in os.environ]
    if missing:
        raise SystemExit(f"--env names a variable that is not set: {', '.join(missing)}")

    def command(text: str) -> list[str]:
        return [executable, *(arg.replace("{prompt}", text) for arg in argv[1:])]

    return Harness(
        name=name,
        command=command(prompt),
        binaries=binaries,
        resume=lambda _events, message: command(f"{prompt}\n\n{message}"),
        env={env: os.environ[env] for env in env_names},
        expose=expose,
    )


def _last_session(events: list[dict[str, Any]], kind: str, key: str) -> str | None:
    """The id of the session the harness last reported, from its `kind` events."""
    for event in reversed(events):
        value = event.get(key)
        if event.get("type") == kind and isinstance(value, str) and value:
            return value
    return None


def _is_skill(skill: Path) -> bool:
    return (skill / "SKILL.md").is_file()


def _install_skills(skills: Sequence[Path], directory: Path) -> None:
    """Copy each skill directory into `directory` in the sandbox home, where the harness
    looks for skills; nothing else of the host comes with it."""
    for skill in skills:
        if not _is_skill(skill):
            raise SystemExit(f"{skill} is not a skill: it has no SKILL.md")
        shutil.copytree(skill, directory / skill.name)


def _continuation(until: str) -> str:
    """What a resumed agent is told."""
    if until == "rocket":
        return "The rocket has not launched yet. Keep playing."
    return f"Labs have not yet researched with a machine-made {until}. Keep playing."


def _utc_now() -> str:
    """Current time in UTC, as `YYYY-MM-DDTHH:MM:SS.ffffffZ`."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _sha256_tree(root: Path) -> str:
    """SHA-256 of the files under `root`, in sorted relative-path order.

    Each file updates the digest with its `/`-separated path, a NUL, its bytes
    and a NUL. A file symbolic link counts as the file it points at. A directory
    symbolic link is not walked.
    """
    digest = hashlib.sha256()
    files = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    for rel in files:
        digest.update(rel.encode())
        digest.update(b"\0")
        digest.update((root / rel).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _package_version() -> str | None:
    try:
        return importlib.metadata.version("factobot")
    except importlib.metadata.PackageNotFoundError:
        return None


def _git_state() -> dict[str, Any] | None:
    """Commit and dirty flag of the checkout that contains the working directory.

    None outside a checkout, and when git cannot name HEAD. `dirty` is true when
    `git status --porcelain` prints anything (staged, unstaged or untracked).
    """
    env = os.environ.copy()
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    sha = (commit.stdout or "").strip()
    if not sha:
        return None
    return {"commit": sha, "dirty": bool((status.stdout or "").strip())}


def _world_versions(world: World) -> tuple[str | None, str | None, int | float | None]:
    """Factorio version, factobot mod version and `game.speed`.

    Nulls when the world does not answer with `script.active_mods` and
    `game.speed`.
    """
    try:
        facts = world.lua("{mods = script.active_mods, speed = game.speed}")
    except (FactobotError, OSError):
        return None, None, None
    if not isinstance(facts, dict):
        return None, None, None
    mods = facts.get("mods")
    game = mods.get("base") if isinstance(mods, dict) else None
    mod = mods.get("factobot") if isinstance(mods, dict) else None
    speed = facts.get("speed")
    if not isinstance(game, str):
        game = None
    if not isinstance(mod, str):
        mod = None
    if isinstance(speed, bool) or not isinstance(speed, int | float):
        speed = None
    return game, mod, speed


def _write_summary(out_dir: Path, summary: dict[str, Any]) -> None:
    """Replace `summary.json` as a whole, so a signal mid-write cannot truncate it."""
    temporary = out_dir / f".summary.{os.getpid()}.tmp"
    try:
        temporary.write_text(json.dumps(summary, indent=2) + "\n")
        os.replace(temporary, out_dir / "summary.json")
    finally:
        temporary.unlink(missing_ok=True)


def run_playtest(
    task: str,
    out_dir: Path,
    *,
    agent: str = "claude",
    model: str | None = None,
    command: list[str] | None = None,
    env_names: Sequence[str] = (),
    expose: Sequence[Path] = (),
    skills: Sequence[Path] = (),
    seed: int,
    camera: bool,
    timeout: float,
    setup: str | None = None,
    listen: str | None = None,
    until: str | None = None,
    save: Path | None = None,
    notes: str | None = None,
    max_resumes: int = DEFAULT_MAX_RESUMES,
    autosave_minutes: float | None = None,
    stop: threading.Event | None = None,
) -> dict[str, Any]:
    """Run one agent against a world. `command`, if given, replaces the `agent` preset.

    With `until`, an agent that quits before the milestone is resumed up to
    `max_resumes` times. `autosave_minutes` saves the world that often (wall
    time) while the agent plays. Setting `stop` (from a signal handler) ends
    the run as the timeout does, with no resume after it. `notes` starts the
    agent with that text as `notes.md` in its working directory; the file it
    leaves there is copied to the run directory at every autosave and when
    the run ends.
    """
    # The daemon loads an existing world/save.zip and then ignores --seed and
    # --save, and it appends to world/calls.jsonl. A reused directory would
    # play the earlier world while the summary recorded this run's seed.
    # Continue from that save in a new directory.
    world_dir = out_dir / "world"
    save = world_dir / "save.zip"
    if save.is_file() or (world_dir / "calls.jsonl").is_file():
        raise SystemExit(
            f"{out_dir} holds an earlier run's world. "
            f"Continue it with --save {save} --out <new directory>"
        )
    if not Path(sandbox.BWRAP).exists():
        raise SystemExit(f"playtests run agents in bubblewrap; install it ({sandbox.BWRAP})")
    for tool in (sandbox.SLIRP4NETNS, sandbox.NSENTER, sandbox.IP):
        if not Path(tool).exists():
            raise SystemExit(f"the sandbox's network needs {tool}; install it")
    if command and skills:
        raise SystemExit("--skill installs skills for the claude and omp presets only")
    # The agent's home lives outside the run directory, which the agent must
    # not see, and is deleted afterwards because it holds a copy of the
    # harness's login.
    state = Path(tempfile.mkdtemp(prefix="factobot-agent-"))
    home = state / "home"
    (home / "work").mkdir(parents=True)
    home.chmod(0o700)
    if notes is not None:
        (home / "work" / NOTES_FILE).write_text(notes)
    prompt = PREAMBLE + task
    try:
        if command:
            harness = custom_harness(
                command, prompt, env_names=list(env_names), expose=list(expose)
            )
        elif agent == "claude":
            harness = claude_harness(prompt, model or DEFAULT_MODEL, home, skills)
        elif agent == "omp":
            harness = omp_harness(prompt, model or DEFAULT_MODEL, home, skills)
        else:
            raise SystemExit(f"no agent preset named {agent!r}; give a command after -- instead")
        # The host addresses the sandbox may reach (omp's auth broker) are let
        # through with nftables; fail now, before the world boots.
        if harness.allow and not Path(sandbox.NFT).exists():
            raise SystemExit(
                f"{harness.name} needs nftables in the sandbox; install it ({sandbox.NFT})"
            )
        # After the harness, so a missing login leaves no run directory behind.
        out_dir.mkdir(parents=True, exist_ok=True)
        # agentview orders runs by this file's mtime: when the run started.
        (out_dir / "started").touch()
        summary = _run(
            harness,
            task,
            out_dir,
            state=state,
            model=model if command else model or DEFAULT_MODEL,
            seed=seed,
            camera=camera,
            timeout=timeout,
            setup=setup,
            listen=listen,
            until=until,
            save=save,
            max_resumes=max_resumes,
            autosave_minutes=autosave_minutes,
            stop=stop,
            skills=skills,
        )
        summary["skills"] = [skill.name for skill in skills]
        _write_summary(out_dir, summary)
    finally:
        # The home holds a copy of the login: it goes even if the notes fail to copy.
        try:
            _keep_notes(home, out_dir)
        finally:
            shutil.rmtree(state, ignore_errors=True)
    return summary


def _run(
    harness: Harness,
    task: str,
    out_dir: Path,
    *,
    state: Path,
    model: str | None,
    seed: int,
    camera: bool,
    timeout: float,
    setup: str | None,
    listen: str | None,
    until: str | None,
    save: Path | None,
    max_resumes: int,
    autosave_minutes: float | None,
    stop: threading.Event | None,
    skills: Sequence[Path] = (),
) -> dict[str, Any]:
    transcript = out_dir / "transcript.jsonl"
    # A reused --out may hold an earlier run's transcript. Remove it now, so a
    # stop during boot, which never starts an agent, can't report that run's
    # turns, cost and answer as this one's.
    transcript.unlink(missing_ok=True)
    started = time.monotonic()
    started_at = _utc_now()
    git = _git_state()
    # Unset until the world first answers; a stop during boot can leave them so.
    game_version: str | None = None
    mod_version: str | None = None
    game_speed: int | float | None = None
    start: dict[str, Any] | None = None
    progress: _Progress | None = None
    milestones: dict[str, Any] | None = None
    autosaver: _Autosaver | None = None
    reached: int | None = None
    exit_code: int | None = None
    # Set once a signal (`stop`) ends the run; no agent starts or resumes after it.
    stopped = False
    resumes: list[dict[str, Any]] = []
    # Agent processes in a row that failed at once, and the last one's last line.
    quick_failures = 0
    agent_failed: str | None = None
    # Set when the world fails after it has answered, and nobody stopped the run.
    error: str | None = None
    agent_calls: list[dict[str, Any]] = []
    # Copied now, next to the `fac` the daemon is about to start from, so every
    # start and resume runs the same build: a `cargo build` during the run
    # replaces or removes target/debug/fac-agent, and a new build may speak
    # another protocol than the running daemon.
    fac = state / "fac-agent"
    shutil.copy2(find_agent_fac(), fac)
    try:
        with start_world(
            seed=None if save else seed,
            save=save,
            camera=camera,
            setup=setup,
            run_dir=out_dir / "world",
            listen=listen,
        ) as world:
            if listen is not None:
                print(
                    f"watch with: fac watch {listen}:{world.game_port}",
                    file=sys.stderr,
                    flush=True,
                )
            # A save carries its tick and pack counts into the run, so the summary
            # records where the agent started.
            start = world.milestones()
            if until is not None:
                # Fails now on an unknown pack. A save keeps its milestone ticks, so one
                # that already reached the milestone would stop the agent on the first
                # poll and report a success this run never earned.
                already = _milestone_tick(start, until)
                if already is not None:
                    raise ValueError(
                        f"the world already reached {until} at tick {already}; "
                        "--until needs a milestone the run has yet to reach"
                    )
            game_version, mod_version, game_speed = _world_versions(world)
            progress = _Progress(world, start)
            milestones = start
            autosaver = (
                _Autosaver(world, autosave_minutes, state / "home", out_dir)
                if autosave_minutes
                else None
            )
            command = harness.command
            # --timeout limits the agent's own run, so world boot and setup don't count.
            deadline = time.monotonic() + timeout
            try:
                while True:
                    # A stop signal during world boot, or between an agent quitting and
                    # its resume, leaves nothing for the agent to do.
                    if _stop_within(stop, 0.0):
                        stopped = True
                        break
                    # Appends, so the transcript keeps growing across resumes and
                    # agentview follows on.
                    began, offset = time.monotonic(), _size(transcript)
                    calls_before = _agent_call_count(world)
                    with transcript.open("a") as out:
                        exit_code, reached = _supervise(
                            command,
                            harness,
                            fac,
                            world,
                            state,
                            out,
                            deadline,
                            until,
                            autosaver,
                            stop,
                            progress,
                        )
                    # An agent (or its sandbox) killed by a signal the runner never
                    # sent: the signal that stops the run may be on its way here too.
                    killed = exit_code is not None and exit_code < 0
                    stopped = _stop_within(stop, STOP_SIGNAL_GRACE if killed else 0.0)
                    if exit_code is None or reached is not None or until is None or stopped:
                        break
                    # The agent quit on its own, maybe right after reaching the milestone,
                    # or died of a stop signal that also has the daemon saving.
                    try:
                        now = progress.poll()
                    except (OSError, FactobotError):
                        if not _stop_within(stop, STOP_SIGNAL_GRACE):
                            raise
                        stopped = True
                        break
                    reached = _milestone_tick(now, until)
                    if reached is not None:
                        break
                    quick = (
                        exit_code != 0
                        and time.monotonic() - began < QUICK_FAILURE_SECONDS
                        and _agent_call_count(world) == calls_before
                    )
                    quick_failures = quick_failures + 1 if quick else 0
                    if quick_failures >= QUICK_FAILURE_LIMIT:
                        agent_failed = _last_line(transcript, offset) or f"exit {exit_code}"
                        print(
                            f"the agent failed {quick_failures} times in a row within "
                            f"{QUICK_FAILURE_SECONDS:.0f} s and no fac call (exit {exit_code}); "
                            f"not resuming it: {agent_failed}",
                            file=sys.stderr,
                            flush=True,
                        )
                        break
                    if len(resumes) >= max_resumes or time.monotonic() >= deadline:
                        break
                    resumes.append(
                        {
                            "exit_code": exit_code,
                            "tick": now["tick"],
                            "wall_seconds": round(time.monotonic() - started, 1),
                        }
                    )
                    print(
                        f"the agent quit (exit {exit_code}) before {until}; resuming it "
                        f"({len(resumes)}/{max_resumes})",
                        file=sys.stderr,
                        flush=True,
                    )
                    command = harness.resume(_events(transcript), _continuation(until))
            finally:
                # A cleanup failure must neither lose the summary nor hide an error
                # the loop raised.
                try:
                    harness.finish()
                except Exception as err:
                    print(f"harness cleanup failed: {err}", file=sys.stderr, flush=True)
                # Also when the loop raised, as a stop during a resumed agent's
                # sandbox start does: the agents before it made calls.
                agent_calls = [call for call in world.calls() if call["surface"] == "agent"]
            try:
                milestones = progress.poll()
            except (OSError, FactobotError):
                # Stopped by a signal the daemon got too, so it is saving or gone:
                # the last poll stands.
                if not stopped and not _stop_within(stop, STOP_SIGNAL_GRACE):
                    raise
                stopped = True
                milestones = progress.milestones
    except (OSError, FactobotError, RuntimeError) as err:
        # systemctl stop and Ctrl-C signal the daemon and the sandbox too, so a stop
        # can make start_world (RuntimeError: the daemon exited before it was
        # ready), the first reads of the world or the sandbox's start fail.
        # Once the world has answered, a failure with no stop signal still ends
        # the run, and the summary keeps the last poll instead of a traceback.
        if _stop_within(stop, STOP_SIGNAL_GRACE):
            stopped = True
        elif start is None:
            raise
        else:
            error = f"{type(err).__name__}: {err}"
            print(f"the world failed ({error}); writing the summary", file=sys.stderr, flush=True)
        milestones = progress.milestones if progress is not None else start

    turns, cost, final_answer = _harness_report(harness.name, _events(transcript))
    return {
        "schema": SCHEMA,
        "started_at": started_at,
        "ended_at": _utc_now(),
        "git": git,
        "versions": {
            "factobot": _package_version(),
            "game": game_version,
            "mod": mod_version,
            "protocol": PROTOCOL_VERSION,
        },
        "game_speed": game_speed,
        "task_sha256": _sha256_text(task),
        "setup_sha256": None if setup is None else _sha256_text(setup),
        "skill_sha256": {skill.name: _sha256_tree(skill) for skill in skills},
        "config": {
            "timeout": timeout,
            "max_resumes": max_resumes,
            "autosave_minutes": autosave_minutes,
            "camera": camera,
            "listen": listen,
        },
        "task": task.strip().splitlines()[0] if task.strip() else "",
        "agent": harness.name,
        "model": model,
        # A save brings its own map; --seed generated nothing in that run.
        "seed": None if save else seed,
        "save": os.fspath(save.absolute()) if save else None,
        "exit_code": exit_code,
        "stopped": stopped,
        # A world failure named in `error` is neither a timeout nor a stop.
        "timed_out": error is None and exit_code is None and reached is None and not stopped,
        "wall_seconds": round(time.monotonic() - started, 1),
        "turns": turns,
        "cost_usd": cost,
        "fac_calls": len(agent_calls),
        "fac_errors": sum(1 for call in agent_calls if not call["response"]["ok"]),
        "methods": sorted({call["method"] for call in agent_calls if call["method"]}),
        "response_bytes": _response_bytes(agent_calls),
        "final_answer": final_answer,
        "until": until,
        "milestone_tick": (
            _milestone_tick(milestones, until) if until is not None and milestones else None
        ),
        "resumes": resumes,
        "agent_failed": agent_failed,
        "error": error,
        "research": progress.research if progress else [],
        "lab_use_by_minute": progress.lab_use if progress else [],
        "autosaves": autosaver.latest() if autosaver else [],
        # Null when a stop during world boot left the world unread.
        "start_tick": start["tick"] if start else None,
        "end_tick": milestones["tick"] if milestones else None,
        "packs_at_start": _pack_counts(start) if start else None,
        "packs": _pack_counts(milestones) if milestones else None,
        "out_dir": os.fspath(out_dir),
    }


def _supervise(
    command: list[str],
    harness: Harness,
    fac: Path,
    world: World,
    state: Path,
    out: IO[str],
    deadline: float,
    until: str | None,
    autosaver: _Autosaver | None,
    stop: threading.Event | None,
    progress: _Progress,
) -> tuple[int | None, int | None]:
    """Run one agent process until it exits, the world reaches `until`, the deadline
    passes, or `stop` is set. Every poll also records research and lab use in `progress`.

    Returns its exit code (None if it was stopped) and the milestone tick, if reached.
    """
    with sandbox.start(
        command,
        env={**sandbox.base_env(), **harness.env},
        stdout=out,
        home=state / "home",
        socket_dir=world.agent_socket.parent,
        fac=fac,
        binaries=harness.binaries,
        expose=harness.expose,
        allow=harness.allow,
    ) as agent:
        # Stop the agent however the loop ends, including when a harness call raises,
        # so a dead daemon never leaves an agent running unattended. `agent` is
        # bwrap, whose --die-with-parent and PID namespace kill the agent and its
        # children at once, so a SIGTERM would give the harness no grace anyway.
        try:
            while True:
                try:
                    return agent.wait(timeout=max(0.0, min(5.0, deadline - time.monotonic()))), None
                except subprocess.TimeoutExpired:
                    pass
                if _stop_within(stop, 0.0):
                    return None, None
                if autosaver is not None:
                    autosaver.poll()
                milestones = _poll_milestones(progress, stop)
                if milestones is None:
                    # The daemon got the stop signal first and is saving.
                    return None, None
                reached = _milestone_tick(milestones, until) if until is not None else None
                if reached is not None or time.monotonic() >= deadline:
                    return None, reached
        finally:
            if agent.poll() is None:
                with suppress(ProcessLookupError):
                    agent.kill()
            # A process that exits as we kill it is reaped; one that survives
            # SIGKILL must not hang the runner.
            sandbox.reap(agent)


# The player force's researched technologies, with the tick they were read at.
RESEARCHED_LUA = (
    "local names = {} "
    "for name, tech in pairs(game.forces.player.technologies) do "
    "if tech.researched then names[#names + 1] = name end end "
    "return {tick = game.tick, names = names}"
)


class _Progress:
    """What a run review needs from the world over time, read at each poll (about every
    5 s of wall time) since the game keeps no record of when it happened.

    `research` lists each technology finished during the run with the tick of the first
    poll that saw it researched, so up to one poll late. `lab_use` holds, for each game
    minute a poll fell in, the packs labs had used so far (cumulative) and the tick.
    """

    def __init__(self, world: World, start: dict[str, Any]) -> None:
        self.world = world
        self.known = set(self._researched()["names"] or [])
        self.research: list[dict[str, Any]] = []
        self.lab_use: list[dict[str, Any]] = []
        self.minute = start["tick"] // TICKS_PER_MINUTE
        # The latest milestones read, which the summary falls back on when the
        # daemon is already saving for a stop signal of its own.
        self.milestones = start

    def _researched(self) -> dict[str, Any]:
        return self.world.lua(RESEARCHED_LUA)

    def poll(self) -> dict[str, Any]:
        """Read the milestones, note what changed, and return them."""
        milestones = self.world.milestones()
        self.milestones = milestones
        now = self._researched()
        # An empty Lua table comes back as an empty object.
        for name in sorted(set(now["names"] or []) - self.known):
            self.known.add(name)
            self.research.append({"name": name, "tick": now["tick"]})
        minute = milestones["tick"] // TICKS_PER_MINUTE
        if minute > self.minute:
            self.minute = minute
            used = {pack["name"]: pack["used_by_labs"] for pack in milestones["packs"]}
            self.lab_use.append(
                {"tick": milestones["tick"], "used_by_labs": {k: v for k, v in used.items() if v}}
            )
        return milestones


class _Autosaver:
    """Saves the running world every `minutes` of wall time while the agent plays.

    `game.server_save` writes `world/write-data/saves/autosave-<n>.zip` in the
    run directory, cycling through AUTOSAVE_SLOTS names. A later run continues
    from one with `--save`.
    """

    def __init__(self, world: World, minutes: float, home: Path, out_dir: Path) -> None:
        self.world = world
        self.home = home
        self.out_dir = out_dir
        self.interval = minutes * 60
        self.due = time.monotonic() + self.interval
        self.saves: list[dict[str, Any]] = []
        self.directory = world.run_dir / "write-data" / "saves"
        # server_save fails when the directory is missing.
        self.directory.mkdir(parents=True, exist_ok=True)

    def poll(self) -> None:
        if time.monotonic() < self.due:
            return
        started = time.monotonic()
        name = f"autosave-{len(self.saves) % AUTOSAVE_SLOTS + 1}"
        try:
            tick = self.world.lua(
                f'local tick = game.tick; game.server_save("{name}"); return tick'
            )
        except (OSError, FactobotError) as err:
            # A save can outlive the daemon's reply budget, and the game may
            # still be writing it. Losing one autosave must not end the run.
            self.due = time.monotonic() + min(self.interval, AUTOSAVE_RETRY_SECONDS)
            print(f"autosave failed: {err}", file=sys.stderr, flush=True)
            return
        self.due = started + self.interval
        path = self.directory / f"{name}.zip"
        self.saves.append({"path": os.fspath(path), "tick": tick})
        print(f"autosave at tick {tick}: {path}", file=sys.stderr, flush=True)
        # The agent's notes describe this save's world: keep the two together.
        _keep_notes(self.home, self.out_dir)

    def latest(self) -> list[dict[str, Any]]:
        """The saves still on disk, oldest first."""
        return self.saves[-AUTOSAVE_SLOTS:]


def _poll_milestones(progress: _Progress, stop: threading.Event | None) -> dict[str, Any] | None:
    """The milestones, retried once. None means `stop` is set.

    A timed-out daemon call drops the socket and the next call opens a new
    one, so one failure is not yet a dead world (decision 86). A second
    failure is the daemon saving or gone for a stop signal, or a real error.
    """
    try:
        return progress.poll()
    except (OSError, FactobotError):
        if _stop_within(stop, 0.0):
            return None
    try:
        return progress.poll()
    except (OSError, FactobotError):
        if _stop_within(stop, STOP_SIGNAL_GRACE):
            return None
        raise


def _size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _last_line(path: Path, offset: int) -> str | None:
    """The last non-empty line written to `path` after `offset`, if any."""
    with path.open("rb") as file:
        file.seek(offset)
        lines = file.read().decode(errors="replace").splitlines()
    return next((line.strip() for line in reversed(lines) if line.strip()), None)


def _agent_call_count(world: World) -> int:
    return sum(1 for call in world.calls() if call["surface"] == "agent")


def _events(transcript: Path) -> list[dict[str, Any]]:
    # A stop during world boot leaves no transcript: the agent never started.
    lines = transcript.read_text().splitlines() if transcript.exists() else []
    return [event for event in map(_json_or_none, lines) if event]


def _harness_report(
    name: str, events: list[dict[str, Any]]
) -> tuple[int | None, float | None, str | None]:
    """Turns, dollar cost and final answer, as far as the harness itself reports them.

    Claude Code's `result` event carries all three, once per process. A run
    with resumes adds up the turns, which each result counts for its own
    process only, but not the cost: a resumed session's `total_cost_usd`
    already includes its earlier spend, so the last result of each session
    holds that session's total. A process that was stopped wrote no result,
    so its turns and its spend since the session's previous result are
    missing. omp's last assistant message is its answer; its turns and cost
    stay unknown rather than estimated, and so does everything for a harness
    this does not know.
    """
    if name == "claude":
        results = [event for event in events if event.get("type") == "result"]
        if not results:
            return None, None, None
        turns = [r["num_turns"] for r in results if isinstance(r.get("num_turns"), int)]
        session_costs: dict[Any, float] = {}
        for r in results:
            if isinstance(r.get("total_cost_usd"), int | float):
                session_costs[r.get("session_id")] = r["total_cost_usd"]
        return (
            sum(turns) if turns else None,
            sum(session_costs.values()) if session_costs else None,
            results[-1].get("result"),
        )
    if name == "omp":
        for event in reversed(events):
            message = event.get("message")
            if (
                event.get("type") == "message_end"
                and isinstance(message, dict)
                and message.get("role") == "assistant"
            ):
                texts = [
                    block.get("text", "")
                    for block in message.get("content", [])
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                return None, None, "\n".join(texts).strip() or None
    return None, None, None


def _write_private(path: Path, value: Any) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.touch(mode=0o600)
    path.write_text(json.dumps(value))


# What a refresh changes in Claude Code's `claudeAiOauth` login, and the type each must have.
REFRESHED_FIELDS = {
    "accessToken": str,
    "refreshToken": str,
    "expiresAt": int,
    "refreshTokenExpiresAt": int,
}


def _return_refreshed_login(host_file: Path, given: dict[str, Any], home: Path) -> None:
    """Hand a login Claude Code refreshed inside the sandbox back to the host.

    A long run outlives the access token (about 8 hours), and refreshing it
    may retire the refresh token the host still holds. If the host's login is
    still the one the sandbox got, the refreshed one replaces it; if the host
    refreshed meanwhile, the host's stays.

    The agent can write anything in its home, so the file is read without
    following symlinks, and only the token fields a refresh changes come back,
    each with its expected type, and only when the access token expires later
    than the one given. Every other field stays the host's.
    """
    text = _read_without_symlinks(home, ".claude", ".credentials.json")
    try:
        stored = json.loads(text) if text is not None else None
    except json.JSONDecodeError:
        stored = None
    refreshed = stored.get("claudeAiOauth") if isinstance(stored, dict) else None
    if not isinstance(refreshed, dict) or refreshed == given:
        return
    tokens = {
        key: refreshed[key]
        for key, kind in REFRESHED_FIELDS.items()
        if type(refreshed.get(key)) is kind and refreshed[key]
    }
    expires = given.get("expiresAt")
    if (
        not {"accessToken", "refreshToken", "expiresAt"} <= tokens.keys()
        or not isinstance(expires, int)
        or tokens["expiresAt"] <= expires
    ):
        print(
            f"Claude Code's login in the sandbox is not a refresh of the one it got; "
            f"kept {host_file}",
            file=sys.stderr,
        )
        return
    host = json.loads(host_file.read_text())
    if host.get("claudeAiOauth") != given:
        print(
            f"Claude Code refreshed its login in the sandbox, but {host_file} changed too; "
            "kept the host's",
            file=sys.stderr,
        )
        return
    host["claudeAiOauth"] = {**given, **tokens}
    staged = host_file.with_name(host_file.name + ".factobot")
    _write_private(staged, host)
    os.replace(staged, host_file)


def _keep_notes(home: Path, out_dir: Path) -> None:
    """Copy the agent's notes, if it keeps any, from its home to the run directory."""
    text = _read_without_symlinks(home, "work", NOTES_FILE)
    if text is not None and out_dir.is_dir():
        (out_dir / NOTES_FILE).write_text(text)


def _read_without_symlinks(root: Path, *parts: str, limit: int = 1 << 20) -> str | None:
    """The text of the regular file `root/parts...`, or None if any part is a symlink,
    missing or unreadable."""
    # O_NONBLOCK so a FIFO in place of the file cannot hang the harness.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        # The agent owns its home and may have made it unreadable.
        fd = os.open(root, flags | os.O_DIRECTORY)
    except OSError:
        return None
    try:
        for i, part in enumerate(parts):
            last = i == len(parts) - 1
            try:
                child = os.open(part, flags | (0 if last else os.O_DIRECTORY), dir_fd=fd)
            except OSError:
                return None
            os.close(fd)
            fd = child
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        data = os.read(fd, limit + 1)
    finally:
        os.close(fd)
    if len(data) > limit:
        return None
    return data.decode(errors="replace")


def _milestone_tick(milestones: dict[str, Any], goal: str) -> int | None:
    """The tick the world reached `goal`: the first rocket launch for `rocket`, else
    the first research with a machine-made pack of that name (decision 43)."""
    if goal == "rocket":
        if "rocket_launched_tick" not in milestones:
            raise ValueError("this mod does not report rocket launches (no rocket_launched_tick)")
        return milestones["rocket_launched_tick"]
    for entry in milestones["packs"]:
        if entry["name"] == goal:
            return entry.get("first_automated_research")
    raise ValueError(f"no science pack named {goal!r}")


def _response_bytes(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Bytes of the daemon's responses to the agent's calls, as compact JSON (as the
    socket carries them), in total and per method, largest first."""
    by_method: dict[str, int] = {}
    for call in calls:
        text = json.dumps(call["response"], separators=(",", ":"), ensure_ascii=False)
        method = call["method"] or "(invalid request)"
        by_method[method] = by_method.get(method, 0) + len(text.encode())
    return {
        "total": sum(by_method.values()),
        "by_method": dict(sorted(by_method.items(), key=lambda item: -item[1])),
    }


def _pack_counts(milestones: dict[str, Any]) -> list[dict[str, Any]]:
    """The science packs made by hand, made by machine or used by labs so far."""
    return [
        {key: pack.get(key) for key in ("name", "made_by_hand", "made_by_machine", "used_by_labs")}
        for pack in milestones["packs"]
        if pack["made_by_hand"] or pack["made_by_machine"] or pack["used_by_labs"]
    ]


def _json_or_none(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def timeout_seconds(text: str) -> float:
    """Parse `--timeout`. 0 is a real duration that ends the run at once, not unlimited.

    NaN and infinity never compare as already past, so a deadline of either would
    not fire and the run would have no cap. A negative value is already past.
    """
    try:
        seconds = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid float value: {text!r}") from None
    if not math.isfinite(seconds) or seconds < 0:
        raise argparse.ArgumentTypeError(
            "must be a finite number of seconds, 0 or more; "
            "0 ends the run at once and is not unlimited, so a long run needs a "
            f"large count such as 999999999, not {text}"
        )
    return seconds


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # Everything after `--` is a custom agent command, kept out of argparse.
    command: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1 :]
    parser = argparse.ArgumentParser(
        prog="python -m factobot.playtest",
        usage="%(prog)s [options] TASK [-- COMMAND ARG...]",
        description="Run an agent harness against a fresh world, or a copy of a save, in a "
        "bubblewrap sandbox that shows it only the fac CLI. A command after -- runs instead "
        "of a preset; {prompt} in its arguments becomes the prompt.",
        epilog="Examples:\n"
        "  python -m factobot.playtest playtests/smoke.md --model sonnet\n"
        "  python -m factobot.playtest playtests/smoke.md --agent omp --model sonnet\n"
        "  python -m factobot.playtest playtests/smoke.md --env MY_API_KEY \\\n"
        "      -- my-agent --print {prompt}\n"
        "  python -m factobot.playtest playtests/red-science.md --model opus \\\n"
        "      --until automation-science-pack --timeout 36000 --listen $(tailscale ip -4)\n"
        "  python -m factobot.playtest playtests/keep-going.md --model opus \\\n"
        "      --save target/playtests/red-science-20261102-230056/world/save.zip --timeout 36000\n"
        "  python -m factobot.playtest playtests/rocket.md --agent omp --model opus \\\n"
        "      --skill skills/factorio-rocket --camera --until rocket --timeout 172800 \\\n"
        "      --max-resumes 100 --autosave-minutes 10",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "task",
        type=Path,
        help="Markdown file with the task for the agent; a .lua file of the same name "
        "next to it, if any, sets up the world first",
    )
    parser.add_argument(
        "--agent",
        choices=["claude", "omp"],
        default="claude",
        help="harness preset: Claude Code or omp [default: claude]",
    )
    parser.add_argument(
        "--model",
        help=f"model for the preset, as the harness names it [default: {DEFAULT_MODEL}]; "
        "with a custom command, only recorded in the summary",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="NAME",
        help="pass this environment variable to a custom command, e.g. its API key (repeatable)",
    )
    parser.add_argument(
        "--expose",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="mount this host path read-only at the same path for a custom command, e.g. "
        "its runtime (repeatable)",
    )
    parser.add_argument(
        "--skill",
        action="append",
        default=[],
        type=Path,
        metavar="DIR",
        help="copy this skill directory (with a SKILL.md) into the agent's home where the "
        "claude or omp preset finds it, e.g. skills/factorio-rocket (repeatable). A run "
        "with skills is assisted, not a benchmark score (decisions 48 and 77)",
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--camera",
        action="store_true",
        help="also start a camera client, which gives the agent `fac screenshot` (decision 67)",
    )
    parser.add_argument(
        "--timeout",
        type=timeout_seconds,
        default=1800,
        metavar="SECONDS",
        help="seconds the agent may run before it is stopped, not counting world boot. "
        "0 ends the run at once and is not unlimited; there is no unlimited value, so a "
        "run that should keep going uses a large count such as 999999999 [default: 1800]",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="output directory [default: target/playtests/<task>-<timestamp>-<random>]. "
        "docs/run-record.md describes summary.json",
    )
    parser.add_argument(
        "--listen",
        metavar="ADDRESS",
        help="game port address, so `fac watch ADDRESS:PORT` can join from another machine; "
        "the port is printed on stderr",
    )
    parser.add_argument(
        "--until",
        metavar="GOAL",
        help="stop the agent once the world reaches GOAL: `rocket` for the first rocket "
        "launch, or a science pack name, e.g. automation-science-pack, for the first "
        "research with a machine-made one; success then means the harness saw it. Refused "
        "when the world (say a --save) has already reached it",
    )
    parser.add_argument(
        "--max-resumes",
        type=int,
        default=DEFAULT_MAX_RESUMES,
        metavar="N",
        help="with --until, resume an agent that quits before GOAL (and before --timeout) "
        f"up to N times, telling it to keep playing [default: {DEFAULT_MAX_RESUMES}]",
    )
    parser.add_argument(
        "--save",
        type=Path,
        help="start from a copy of this save instead of a new map from --seed, e.g. the "
        "world/save.zip a finished run leaves behind or one of its autosaves",
    )
    parser.add_argument(
        "--notes",
        type=Path,
        metavar="FILE",
        help="put a copy of this file in the agent's working directory as notes.md, e.g. the "
        "notes.md an earlier run left in its run directory, when continuing from its --save",
    )
    parser.add_argument(
        "--autosave-minutes",
        type=float,
        metavar="N",
        help="save the world every N minutes of wall time while the agent plays, to "
        f"world/write-data/saves/autosave-1.zip ... autosave-{AUTOSAVE_SLOTS}.zip in the "
        "run directory, in turn [default: off]",
    )
    args = parser.parse_args(argv)
    if (args.env or args.expose) and not command:
        parser.error("--env and --expose only apply to a custom command after --")
    if args.skill and command:
        parser.error("--skill applies to the claude and omp presets, not a custom command")
    for skill in args.skill:
        if not _is_skill(skill):
            parser.error(f"--skill {skill}: no SKILL.md in it")
    if args.max_resumes < 0:
        parser.error("--max-resumes must be 0 or more")
    if args.autosave_minutes is not None and args.autosave_minutes <= 0:
        parser.error("--autosave-minutes must be more than 0")

    # SIGTERM (systemctl stop, kill), SIGHUP (a closed terminal) and a first
    # Ctrl-C end the run the way --timeout does: stop the agent, stop the world,
    # which saves, and write the summary. Dying on the signal would leave the
    # agent running, and systemd sends a second SIGTERM that must not cut that
    # cleanup short. A second Ctrl-C interrupts the runner at once.
    stop = threading.Event()
    _set_on_signals(stop, (signal.SIGTERM, signal.SIGHUP, signal.SIGINT))
    # The stamp has one-second resolution, so two runs of one task started in
    # the same second would share a directory and the second would load the
    # first's world. The suffix keeps those directories apart.
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = args.out or (Path("target/playtests") / f"{args.task.stem}-{stamp}-{os.urandom(4).hex()}")
    setup_file = args.task.with_suffix(".lua")
    summary = run_playtest(
        args.task.read_text(),
        out.absolute(),
        agent=args.agent,
        model=args.model,
        command=command or None,
        env_names=args.env,
        expose=[path.absolute() for path in args.expose],
        skills=[path.resolve() for path in args.skill],
        seed=args.seed,
        camera=args.camera,
        timeout=args.timeout,
        setup=setup_file.read_text() if setup_file.exists() else None,
        listen=args.listen,
        until=args.until,
        save=args.save,
        notes=args.notes.read_text() if args.notes else None,
        max_resumes=args.max_resumes,
        autosave_minutes=args.autosave_minutes,
        stop=stop,
    )
    print(json.dumps(summary, indent=2))
    if args.until is not None:
        return 0 if summary["milestone_tick"] is not None else 1
    return 0 if summary["exit_code"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
