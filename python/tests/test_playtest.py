"""The playtest harness stops the agent, writes its summary and cleans up its
sandbox home even when a harness call fails mid-run, never starts it on a
milestone already reached, resumes it on the `fac` the run started with, on
SIGTERM or Ctrl-C stops the agent, saves the world and writes its summary, and
takes back only a genuine login refresh."""

from __future__ import annotations

import json
import os
import signal
import tempfile
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import pytest

import factobot.playtest as playtest
from factobot.client import FactobotError
from factobot.harness import World


def processes_named(name: str) -> list[int]:
    """Host pids whose argv[0] is `name`; the agent's own pids live in the sandbox's namespace."""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv0 = (entry / "cmdline").read_bytes().split(b"\0", 1)[0]
        except OSError:
            continue
        if argv0 == name.encode():
            found.append(int(entry.name))
    return found


def assert_gone(name: str) -> None:
    """Wait up to 5 s for every process named `name` to end: the kernel kills the
    rest of the sandbox's PID namespace only after bwrap is gone."""
    deadline = time.monotonic() + 5
    while processes_named(name):
        assert time.monotonic() < deadline, f"{name} is still running"
        time.sleep(0.05)


class BrokenWorld:
    """A world whose daemon dies once the agent is running."""

    game_port = 0

    def __init__(self, socket: Path, agent_name: str) -> None:
        self.agent_socket = socket
        self.agent_name = agent_name
        self.milestone_reads = 0

    def milestones(self) -> dict[str, Any]:
        self.milestone_reads += 1
        if self.milestone_reads > 1:
            # Fail only once the agent is really running in the sandbox.
            give_up = time.monotonic() + 10
            while not processes_named(self.agent_name):
                assert time.monotonic() < give_up, "the agent never started"
                time.sleep(0.05)
            raise ConnectionError("daemon is gone")
        pack = {
            "name": "automation-science-pack",
            "made_by_hand": 3,
            "made_by_machine": 0,
            "used_by_labs": 0,
        }
        return {"tick": 40, "packs": [pack]}

    def lua(self, _code: str) -> Any:
        return {"tick": 0, "names": {}}

    def calls(self) -> list[dict[str, Any]]:
        return []


def test_agent_is_stopped_and_home_removed_when_harness_call_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent_name = f"factobot-test-agent-{uuid.uuid4().hex}"
    agent = tmp_path / "agent"
    agent.write_text(f"#!/bin/bash\nexec -a {agent_name} sleep 600\n")
    agent.chmod(0o755)

    homes = tmp_path / "tmp"
    homes.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", os.fspath(homes))
    fac = tmp_path / "fac"
    fac.touch()
    monkeypatch.setattr(playtest, "find_agent_fac", lambda: fac)
    socket_dir = tmp_path / "socket"
    socket_dir.mkdir()

    @contextmanager
    def start_world(**_: Any) -> Iterator[BrokenWorld]:
        yield BrokenWorld(socket_dir / "fac.sock", agent_name)

    monkeypatch.setattr(playtest, "start_world", start_world)
    monkeypatch.setattr(playtest, "STOP_SIGNAL_GRACE", 0.05)
    task = tmp_path / "task.md"
    task.write_text("task\n")
    saved = {
        signum: signal.getsignal(signum)
        for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
    }
    try:
        code = playtest.main(
            [
                os.fspath(task),
                "--out",
                os.fspath(tmp_path / "out"),
                "--seed",
                "1",
                "--timeout",
                "0.2",
                "--until",
                "automation-science-pack",
                "--",
                os.fspath(agent),
                "{prompt}",
            ]
        )
    finally:
        for signum, handler in saved.items():
            signal.signal(signum, handler)

    # --until is set and the milestone was not reached, so main exits non-zero.
    assert code == 1
    assert_gone(agent_name)
    assert list(homes.iterdir()) == []
    summary = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert summary["error"] == "ConnectionError: daemon is gone"
    assert summary["stopped"] is False
    assert summary["timed_out"] is False
    assert summary["exit_code"] is None
    assert summary["start_tick"] == 40
    assert summary["end_tick"] == 40
    assert summary["packs_at_start"] == summary["packs"]
    assert summary["packs"] == [
        {
            "name": "automation-science-pack",
            "made_by_hand": 3,
            "made_by_machine": 0,
            "used_by_labs": 0,
        }
    ]


class ReachedWorld:
    """A world, say from a save, that reached red science before this run."""

    game_port = 0

    def __init__(self, socket: Path) -> None:
        self.agent_socket = socket

    def milestones(self) -> dict[str, Any]:
        return {
            "tick": 90000,
            "packs": [{"name": "automation-science-pack", "first_automated_research": 54321}],
        }

    def calls(self) -> list[dict[str, Any]]:
        return []


def test_until_refuses_a_milestone_the_world_already_reached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = tmp_path / "agent-started"
    agent = tmp_path / "agent"
    agent.write_text(f"#!/bin/sh\ntouch {started}\n")
    agent.chmod(0o755)
    (tmp_path / "fac").touch()
    monkeypatch.setattr(playtest, "find_agent_fac", lambda: tmp_path / "fac")

    @contextmanager
    def start_world(**_: Any) -> Iterator[ReachedWorld]:
        yield ReachedWorld(tmp_path / "agent.sock")

    monkeypatch.setattr(playtest, "start_world", start_world)

    with pytest.raises(ValueError, match="already reached automation-science-pack at tick 54321"):
        playtest.run_playtest(
            "task",
            tmp_path / "out",
            command=[os.fspath(agent), "{prompt}"],
            seed=1,
            camera=False,
            timeout=5,
            until="automation-science-pack",
            save=tmp_path / "save.zip",
        )

    assert not started.exists()
    assert not (tmp_path / "out" / "summary.json").exists()


class FreshWorld:
    """A new map: tick 0, no science packs made."""

    game_port = 0

    def __init__(self, socket: Path) -> None:
        self.agent_socket = socket

    def milestones(self) -> dict[str, Any]:
        return {"tick": 0, "packs": []}

    def lua(self, _code: str) -> Any:
        return {"tick": 0, "names": {}}

    def calls(self) -> list[dict[str, Any]]:
        return []


def test_stop_during_world_boot_never_starts_the_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = tmp_path / "agent-started"
    agent = tmp_path / "agent"
    agent.write_text(f"#!/bin/sh\ntouch {started}\n")
    agent.chmod(0o755)
    (tmp_path / "fac").touch()
    monkeypatch.setattr(playtest, "find_agent_fac", lambda: tmp_path / "fac")
    stop = threading.Event()

    @contextmanager
    def start_world(**_: Any) -> Iterator[FreshWorld]:
        # The stop signal lands while the world boots.
        stop.set()
        yield FreshWorld(tmp_path / "agent.sock")

    monkeypatch.setattr(playtest, "start_world", start_world)

    summary = playtest.run_playtest(
        "task",
        tmp_path / "out",
        command=[os.fspath(agent), "{prompt}"],
        seed=1,
        camera=False,
        timeout=5,
        stop=stop,
    )

    assert not started.exists()
    assert summary["stopped"] is True
    assert summary["timed_out"] is False
    assert summary["exit_code"] is None


class SavingWorld:
    """A world whose daemon got the stop signal and is saving: every poll fails."""

    game_port = 0

    def __init__(self, socket: Path) -> None:
        self.agent_socket = socket

    def milestones(self) -> dict[str, Any]:
        raise ConnectionError("daemon closed the connection")

    def calls(self) -> list[dict[str, Any]]:
        return []


@pytest.mark.parametrize("fails", ["daemon-exits", "first-poll"])
@pytest.mark.parametrize("stopped", [True, False], ids=["stopped", "not-stopped"])
def test_world_that_fails_to_boot_after_a_stop_still_writes_the_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fails: str, stopped: bool
) -> None:
    """`systemctl stop` during boot signals the daemon too, so it exits before
    it is ready or stops answering before the runner's first poll."""
    started = tmp_path / "agent-started"
    agent = tmp_path / "agent"
    agent.write_text(f"#!/bin/sh\ntouch {started}\n")
    agent.chmod(0o755)
    (tmp_path / "fac").touch()
    monkeypatch.setattr(playtest, "find_agent_fac", lambda: tmp_path / "fac")
    monkeypatch.setattr(playtest, "STOP_SIGNAL_GRACE", 0.1)
    stop = threading.Event()

    @contextmanager
    def start_world(**_: Any) -> Iterator[SavingWorld]:
        if stopped:
            stop.set()
        if fails == "daemon-exits":
            raise RuntimeError("fac daemon did not start:\n")
        yield SavingWorld(tmp_path / "agent.sock")

    monkeypatch.setattr(playtest, "start_world", start_world)
    # A reused --out: an earlier run's transcript must not leak into this summary.
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "transcript.jsonl").write_text(
        json.dumps({"type": "result", "num_turns": 42, "total_cost_usd": 1.5, "result": "old"})
        + "\n"
    )

    def run() -> dict[str, Any]:
        return playtest.run_playtest(
            "task",
            tmp_path / "out",
            command=[os.fspath(agent), "{prompt}"],
            seed=1,
            camera=False,
            timeout=5,
            until="automation-science-pack",
            stop=stop,
        )

    if not stopped:
        # Without a stop signal a world that fails to boot is an error.
        with pytest.raises((RuntimeError, ConnectionError)):
            run()
        assert not (tmp_path / "out" / "summary.json").exists()
        return

    summary = run()

    assert not started.exists()
    assert json.loads((tmp_path / "out" / "summary.json").read_text()) == summary
    assert summary["stopped"] is True
    assert summary["timed_out"] is False
    assert summary["exit_code"] is None
    assert summary["milestone_tick"] is None
    assert summary["start_tick"] is None
    assert summary["end_tick"] is None
    assert summary["packs"] is None
    assert summary["turns"] is None
    assert summary["cost_usd"] is None
    assert summary["final_answer"] is None
    assert summary["resumes"] == []
    assert summary["research"] == []


class StoppingWorld(FreshWorld):
    """A fresh map whose daemon gets the stop signal once the agent has run:
    it is saving, so every poll after the first fails."""

    def __init__(self, socket: Path, stop: threading.Event) -> None:
        super().__init__(socket)
        self.stop = stop
        self.reads = 0

    def milestones(self) -> dict[str, Any]:
        self.reads += 1
        if self.reads > 1:
            self.stop.set()
            raise ConnectionError("daemon closed the connection")
        pack = {"name": "automation-science-pack", "made_by_hand": 0, "made_by_machine": 0}
        return {"tick": 0, "packs": [{**pack, "used_by_labs": 0}]}


@pytest.mark.parametrize("until", ["automation-science-pack", None])
def test_a_stop_that_ends_the_agent_first_still_writes_the_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, until: str | None
) -> None:
    """bwrap passes on the agent's death by SIGTERM as exit 143 before the runner's
    own handler has run, while the daemon, signalled too, is saving."""
    agent = tmp_path / "agent"
    agent.write_text("#!/bin/sh\nexit 143\n")
    agent.chmod(0o755)
    (tmp_path / "fac").touch()
    monkeypatch.setattr(playtest, "find_agent_fac", lambda: tmp_path / "fac")
    monkeypatch.setattr(playtest, "STOP_SIGNAL_GRACE", 0.1)
    stop = threading.Event()

    @contextmanager
    def start_world(**_: Any) -> Iterator[StoppingWorld]:
        yield StoppingWorld(tmp_path / "agent.sock", stop)

    monkeypatch.setattr(playtest, "start_world", start_world)

    summary = playtest.run_playtest(
        "task",
        tmp_path / "out",
        command=[os.fspath(agent), "{prompt}"],
        seed=1,
        camera=False,
        timeout=60,
        until=until,
        stop=stop,
    )

    assert json.loads((tmp_path / "out" / "summary.json").read_text()) == summary
    assert summary["exit_code"] == 143
    assert summary["stopped"] is True
    assert summary["resumes"] == []
    assert summary["end_tick"] == 0


class RebuildingWorld(FreshWorld):
    """A fresh map while `cargo build` replaces fac-agent: on every poll after the first."""

    def __init__(self, socket: Path, fac: Path) -> None:
        super().__init__(socket)
        self.fac = fac
        self.polls = 0

    def milestones(self) -> dict[str, Any]:
        self.polls += 1
        if self.polls > 1:
            # As cargo does: the old file goes and a new one takes its name.
            self.fac.unlink(missing_ok=True)
            self.fac.write_text("new build\n")
        pack = {"name": "automation-science-pack", "made_by_hand": 0, "made_by_machine": 0}
        return {"tick": 0, "packs": [{**pack, "used_by_labs": 0}]}


def test_a_resumed_agent_keeps_the_fac_the_run_started_with(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = tmp_path / "agent"
    agent.write_text("#!/bin/sh\ncat /opt/factobot/bin/fac\n")
    agent.chmod(0o755)
    fac = tmp_path / "fac"
    fac.write_text("old build\n")
    monkeypatch.setattr(playtest, "find_agent_fac", lambda: fac)

    @contextmanager
    def start_world(**_: Any) -> Iterator[RebuildingWorld]:
        yield RebuildingWorld(tmp_path / "agent.sock", fac)

    monkeypatch.setattr(playtest, "start_world", start_world)

    summary = playtest.run_playtest(
        "task",
        tmp_path / "out",
        command=[os.fspath(agent), "{prompt}"],
        seed=1,
        camera=False,
        timeout=60,
        until="automation-science-pack",
        max_resumes=1,
    )

    assert len(summary["resumes"]) == 1
    transcript = (tmp_path / "out" / "transcript.jsonl").read_text()
    assert transcript.splitlines() == ["old build", "old build"]


def test_a_failed_cleanup_still_writes_the_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    agent = tmp_path / "agent"
    agent.write_text("#!/bin/sh\nexit 0\n")
    agent.chmod(0o755)
    (tmp_path / "fac").touch()
    monkeypatch.setattr(playtest, "find_agent_fac", lambda: tmp_path / "fac")

    @contextmanager
    def start_world(**_: Any) -> Iterator[FreshWorld]:
        yield FreshWorld(tmp_path / "agent.sock")

    monkeypatch.setattr(playtest, "start_world", start_world)
    custom_harness = playtest.custom_harness

    def failing_finish() -> None:
        raise OSError("host credentials vanished")

    def harness(*args: Any, **kwargs: Any) -> playtest.Harness:
        found = custom_harness(*args, **kwargs)
        found.finish = failing_finish
        return found

    monkeypatch.setattr(playtest, "custom_harness", harness)

    summary = playtest.run_playtest(
        "task",
        tmp_path / "out",
        command=[os.fspath(agent), "{prompt}"],
        seed=1,
        camera=False,
        timeout=60,
    )

    assert summary["exit_code"] == 0
    assert json.loads((tmp_path / "out" / "summary.json").read_text()) == summary
    assert "harness cleanup failed: host credentials vanished" in capsys.readouterr().err


def test_a_hangup_ignored_under_nohup_stays_ignored() -> None:
    saved = {signum: signal.getsignal(signum) for signum in (signal.SIGTERM, signal.SIGHUP)}
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        playtest._set_on_signals(threading.Event(), (signal.SIGTERM, signal.SIGHUP))
        assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN
        assert callable(signal.getsignal(signal.SIGTERM))
    finally:
        for signum, handler in saved.items():
            signal.signal(signum, handler)


GIVEN = {
    "accessToken": "a1",
    "refreshToken": "r1",
    "expiresAt": 1000,
    "scopes": ["user:inference"],
    "subscriptionType": "max",
}


def return_login(
    tmp_path: Path, sandbox_login: Any, *, how: str = "file", host_login: Any = GIVEN
) -> dict[str, Any]:
    """The host's credentials file, which holds `host_login` when the run ends, after
    the agent left `sandbox_login` in its home, written there as `how` says."""
    host_file = tmp_path / "host" / ".credentials.json"
    host_file.parent.mkdir()
    host_file.write_text(json.dumps({"claudeAiOauth": host_login, "other": 1}))
    home = tmp_path / "home"
    home.mkdir()
    text = json.dumps({"claudeAiOauth": sandbox_login})
    if how == "symlinked-dir":
        # The agent points its .claude directory at one elsewhere on the host.
        (tmp_path / "elsewhere").mkdir()
        (home / ".claude").symlink_to(tmp_path / "elsewhere")
    else:
        (home / ".claude").mkdir()
    sandbox_file = home / ".claude" / ".credentials.json"
    if how == "symlink":
        # The agent points its credentials at a host file it hopes holds another login.
        target = tmp_path / "elsewhere.json"
        target.write_text(text)
        sandbox_file.symlink_to(target)
    elif how == "fifo":
        # Read without O_NONBLOCK, a FIFO would hang the runner.
        os.mkfifo(sandbox_file)
    elif how == "too-big":
        sandbox_file.write_text(text + " " * (1 << 20))
    elif how == "unparseable":
        sandbox_file.write_text(text[:-1])
    else:
        sandbox_file.write_text(text)
    if how == "unreadable-home":
        home.chmod(0)
    try:
        playtest._return_refreshed_login(host_file, GIVEN, home)
    finally:
        home.chmod(0o700)
    return json.loads(host_file.read_text())


def test_refreshed_login_returns_its_tokens_only(tmp_path: Path) -> None:
    refreshed = {
        **GIVEN,
        "accessToken": "a2",
        "refreshToken": "r2",
        "expiresAt": 2000,
        "subscriptionType": "free",
    }
    host = return_login(tmp_path, refreshed)
    assert host == {
        "claudeAiOauth": {**GIVEN, "accessToken": "a2", "refreshToken": "r2", "expiresAt": 2000},
        "other": 1,
    }


REFRESH = {**GIVEN, "accessToken": "a2", "refreshToken": "r2", "expiresAt": 2000}


@pytest.mark.parametrize(
    ("sandbox_login", "how"),
    [
        ("garbage-from-agent", "file"),
        ({**REFRESH, "accessToken": 5}, "file"),
        ({**REFRESH, "refreshToken": ""}, "file"),
        ({**REFRESH, "expiresAt": 1000}, "file"),
        (REFRESH, "symlink"),
        (REFRESH, "symlinked-dir"),
        (REFRESH, "fifo"),
        (REFRESH, "too-big"),
        (REFRESH, "unparseable"),
        (REFRESH, "unreadable-home"),
    ],
    ids=[
        "not-a-login",
        "wrong-type",
        "empty-token",
        "not-newer",
        "symlink",
        "symlinked-dir",
        "fifo",
        "too-big",
        "unparseable",
        "unreadable-home",
    ],
)
def test_agent_cannot_plant_a_login_on_the_host(
    tmp_path: Path, sandbox_login: Any, how: str
) -> None:
    host = return_login(tmp_path, sandbox_login, how=how)
    assert host == {"claudeAiOauth": GIVEN, "other": 1}


def test_a_login_the_host_refreshed_meanwhile_is_kept(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host_refresh = {**GIVEN, "accessToken": "a3", "refreshToken": "r3", "expiresAt": 3000}
    host = return_login(tmp_path, REFRESH, host_login=host_refresh)
    assert host == {"claudeAiOauth": host_refresh, "other": 1}
    assert "kept the host's" in capsys.readouterr().err


def test_the_agents_notes_are_kept_but_never_through_a_symlink(tmp_path: Path) -> None:
    home, out = tmp_path / "home", tmp_path / "run"
    (home / "work").mkdir(parents=True)
    out.mkdir()
    (home / "work" / "notes.md").write_text("iron trunk at y 0\n")
    playtest._keep_notes(home, out)  # pyright: ignore[reportPrivateUsage]
    assert (out / "notes.md").read_text() == "iron trunk at y 0\n"

    # The agent owns its home: a link to a host file must not be copied out.
    secret = tmp_path / "secret"
    secret.write_text("host only\n")
    (home / "work" / "notes.md").unlink()
    (home / "work" / "notes.md").symlink_to(secret)
    playtest._keep_notes(home, out)  # pyright: ignore[reportPrivateUsage]
    assert (out / "notes.md").read_text() == "iron trunk at y 0\n"


def test_timeout_zero_is_a_duration_and_a_large_count_is_too() -> None:
    # 0 is a real duration: the deadline is now, so the run stops at once.
    # It is not an uncapped run. A long run passes a large finite count.
    assert playtest.timeout_seconds("0") == 0.0
    assert playtest.timeout_seconds("999999999") == 999999999.0


@pytest.mark.parametrize("text", ["-1", "-0.01", "nan", "inf", "1e400"])
def test_a_timeout_that_is_not_a_finite_duration_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    # NaN and infinity never compare as past, so they would leave the run uncapped.
    # A negative deadline is already past. Refuse them before any world starts.
    missing = tmp_path / "missing.md"

    with pytest.raises(SystemExit) as raised:
        playtest.main([os.fspath(missing), "--timeout", text])

    assert raised.value.code == 2
    assert "not unlimited" in capsys.readouterr().err


def test_timeout_help_says_zero_is_not_unlimited(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        playtest.main(["--help"])

    assert raised.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "0 ends the run at once and is not unlimited" in help_text
    assert "999999999" in help_text


class _SaveWorld:
    """A world whose first autosave fails and whose second one lands."""

    def __init__(self, root: Path) -> None:
        self.run_dir = root
        self.attempts = 0

    def lua(self, code: str) -> int:
        assert "server_save" in code
        self.attempts += 1
        if self.attempts == 1:
            raise FactobotError("unavailable", "rcon timed out after 10s")
        return 42


def test_a_failed_autosave_is_logged_and_the_next_one_is_kept(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world = _SaveWorld(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    saver = playtest._Autosaver(cast(World, world), 10, home, out)
    saver.due = 0
    saver.poll()
    assert saver.saves == []
    assert saver.due > time.monotonic()
    err = capsys.readouterr().err
    assert "autosave failed: unavailable: rcon timed out after 10s" in err

    saver.due = 0
    saver.poll()
    assert saver.saves[0]["tick"] == 42
    assert "autosave at tick 42" in capsys.readouterr().err
    assert world.attempts == 2


class _Milestones:
    def __init__(self, fail: int, stop: threading.Event | None = None) -> None:
        self.fail = fail
        self.stop = stop
        self.calls = 0

    def poll(self) -> dict[str, Any]:
        self.calls += 1
        if self.calls == self.fail and self.stop is not None:
            self.stop.set()
        if self.calls <= self.fail:
            raise ConnectionError("daemon closed the connection")
        return {"tick": 7, "packs": []}


def test_a_milestone_poll_is_retried_once() -> None:
    progress = _Milestones(fail=1)
    assert playtest._poll_milestones(cast(playtest._Progress, progress), None) == {
        "tick": 7,
        "packs": [],
    }
    assert progress.calls == 2


def test_resumed_claude_session_cost_is_not_counted_twice() -> None:
    # Claude Code's total_cost_usd after --resume includes the session's
    # earlier spend; num_turns counts the resumed process only.
    events = [
        {"type": "result", "session_id": "s", "num_turns": 3, "total_cost_usd": 1.0},
        {"type": "result", "session_id": "s", "num_turns": 2, "total_cost_usd": 1.5},
        {"type": "result", "session_id": "t", "num_turns": 1, "total_cost_usd": 0.25},
    ]
    turns, cost, _ = playtest._harness_report("claude", events)
    assert (turns, cost) == (6, 1.75)
