"""A long playtest keeps going: an agent that quits before the --until goal is
resumed in the same conversation, the run stops when the goal is reached, the
agent finds the skills it was given (and still not the repository), and
autosaves load with the tick they were taken at."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

import factobot.playtest as playtest
from factobot.client import FactobotError

REPO = Path(__file__).resolve().parents[2]

# Stands in for a harness: reports its arguments and what it sees, quits on
# its first run and plays on (sleeps) from the second.
FAKE_AGENT = """\
#!/usr/bin/python3
import json, os, pathlib, sys, time

home = pathlib.Path.home()
runs = home / "runs"
run = int(runs.read_text()) + 1 if runs.exists() else 1
runs.write_text(str(run))
omp_config = home / ".omp/agent/config.yml"
skills = [
    str(path.relative_to(home))
    for path in sorted(home.glob("**/SKILL.md"))
]
print(json.dumps({{"type": "session", "id": "omp-session"}}))
print(json.dumps({{"type": "system", "subtype": "init", "session_id": "claude-session"}}))
print(json.dumps({{
    "type": "fake",
    "run": run,
    "argv": sys.argv[1:],
    "skills": skills,
    "skill_text": [(home / path).read_text() for path in skills],
    "repo_visible": os.path.exists({repo!r}),
    "bash_timeouts": [os.environ.get(f"BASH_{{kind}}_TIMEOUT_MS") for kind in ("DEFAULT", "MAX")],
    "omp_config": omp_config.read_text() if omp_config.exists() else None,
}}), flush=True)
if run >= {play_from}:
    time.sleep(600)
time.sleep({quit_after})
"""

SKILL = (
    "---\nname: zebra\ndescription: Zebra facts. Use when asked about zebras.\n---\n\nPLUMTREE\n"
)


def fake_agent(tmp_path: Path, name: str, *, play_from: int = 2, quit_after: float = 0) -> Path:
    path = tmp_path / "bin" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(
        FAKE_AGENT.format(repo=os.fspath(REPO), play_from=play_from, quit_after=quit_after)
    )
    path.chmod(0o755)
    return path


def fake_runs(out: Path) -> list[dict[str, Any]]:
    transcript = out / "transcript.jsonl"
    if not transcript.exists():
        return []
    # stderr lands in the transcript too, and is not JSON.
    events = map(playtest._json_or_none, transcript.read_text().splitlines())
    return [event for event in events if event and event.get("type") == "fake"]


class RocketWorld:
    """A world that launches its rocket once the agent's `launch_at_run`th run plays."""

    game_port = 0
    launch_at_run: int | None = 2

    def __init__(self, socket_dir: Path, out: Path) -> None:
        self.agent_socket = socket_dir / "fac.sock"
        self.out = out

    def resumed(self) -> bool:
        return any(run["run"] == 2 for run in fake_runs(self.out))

    def milestones(self) -> dict[str, Any]:
        runs = [run["run"] for run in fake_runs(self.out)]
        launched = 4321 if self.launch_at_run in runs else None
        # A game minute passes and labs use packs while the resumed agent plays.
        used = 12 if self.resumed() else 0
        pack = {"name": "automation-science-pack", "made_by_hand": 0, "made_by_machine": used}
        return {
            "tick": 7300 if self.resumed() else 3000,
            "packs": [{**pack, "used_by_labs": used}],
            "rocket_launched_tick": launched,
        }

    def lua(self, code: str) -> Any:
        if code != playtest.RESEARCHED_LUA:
            raise FactobotError("game_error", "this stand-in answers only the research read")
        names = ["automation", "logistics"] if self.resumed() else ["logistics"]
        return {"tick": 7300 if self.resumed() else 3000, "names": names}

    def calls(self) -> list[dict[str, Any]]:
        return CALLS


CALLS = [
    {"surface": "agent", "method": "observe", "response": {"ok": True, "result": {"name": "ü"}}},
    {"surface": "agent", "method": "observe", "response": {"ok": True, "result": 1}},
    {"surface": "agent", "method": "walk", "response": {"ok": False, "error": {"code": "x"}}},
    {"surface": "dev", "method": "milestones", "response": {"ok": True, "result": 1}},
]


@pytest.fixture
def rocket_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Patches in a RocketWorld; returns the run directory to use."""
    out = tmp_path / "out"
    socket_dir = tmp_path / "socket"
    socket_dir.mkdir()

    @contextmanager
    def start(**_: Any) -> Iterator[RocketWorld]:
        yield RocketWorld(socket_dir, out)

    monkeypatch.setattr(playtest, "start_world", start)
    homes = tmp_path / "tmp"
    homes.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", os.fspath(homes))
    fac = tmp_path / "fac"
    fac.touch()
    monkeypatch.setattr(playtest, "find_agent_fac", lambda: fac)
    return out


@pytest.mark.parametrize("preset", ["omp", "claude"])
def test_preset_with_a_skill_is_resumed_until_the_rocket_launches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rocket_world: Path, preset: str
) -> None:
    out = rocket_world
    host_home = tmp_path / "host-home"
    (host_home / ".omp").mkdir(parents=True)
    (host_home / ".omp" / "auth-broker.token").write_text("token")
    (host_home / ".claude").mkdir()
    (host_home / ".claude" / ".credentials.json").write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "a", "refreshToken": "r", "expiresAt": 1}})
    )
    monkeypatch.setenv("HOME", os.fspath(host_home))
    monkeypatch.setenv("OMP_AUTH_BROKER_URL", "http://192.0.2.1:8765")
    agent = fake_agent(tmp_path, preset)
    monkeypatch.setenv("PATH", f"{agent.parent}:{os.environ['PATH']}")
    skill = tmp_path / "skills" / "zebra"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(SKILL)

    summary = playtest.run_playtest(
        "Launch a rocket.",
        out,
        agent=preset,
        model="opus",
        skills=[skill],
        seed=1,
        camera=False,
        timeout=120,
        until="rocket",
    )

    assert summary["milestone_tick"] == 4321
    assert summary["exit_code"] is None  # stopped at the launch, not quit
    assert not summary["timed_out"]
    assert [resume["exit_code"] for resume in summary["resumes"]] == [0]
    assert summary["skills"] == ["zebra"]
    # logistics was researched before the run started, automation during it.
    assert summary["research"] == [{"name": "automation", "tick": 7300}]
    assert summary["lab_use_by_minute"] == [
        {"tick": 7300, "used_by_labs": {"automation-science-pack": 12}}
    ]
    # Compact JSON in UTF-8: observe 34 ("ü" takes two bytes) + 22, walk 33; dev calls don't count.
    assert summary["response_bytes"] == {"total": 89, "by_method": {"observe": 56, "walk": 33}}
    first, second = fake_runs(out)
    skill_dir = ".omp/agent/skills" if preset == "omp" else ".claude/skills"
    for run in (first, second):
        assert run["skills"] == [f"{skill_dir}/zebra/SKILL.md"]
        assert run["skill_text"] == [SKILL]
        assert not run["repo_visible"]
        if preset == "claude":
            assert run["bash_timeouts"] == ["660000", "660000"]
            assert run["omp_config"] is None
        else:
            assert run["omp_config"] == "bash:\n  autoBackground:\n    enabled: false\n"
    assert "--resume" not in first["argv"]
    resumed = second["argv"]
    assert resumed[resumed.index("--resume") + 1] == f"{preset}-session"
    message = "The rocket has not launched yet. Keep playing."
    if preset == "omp":
        assert resumed[-1] == message
        assert resumed[resumed.index("--skills") + 1] == "zebra"
        assert resumed[resumed.index("--tools") + 1] == "bash,read"
    else:
        assert resumed[resumed.index("-p") + 1] == message
        assert resumed[resumed.index("--setting-sources") + 1] == "user,local"
        assert resumed[resumed.index("--tools") + 1] == "Bash,Read,Skill"


def test_resumes_stop_at_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rocket_world: Path
) -> None:
    out = rocket_world
    monkeypatch.setattr(RocketWorld, "launch_at_run", None)
    agent = fake_agent(tmp_path, "quitter", play_from=99)
    # A reused --out: an earlier run's transcript must not count among this run's agents.
    out.mkdir()
    (out / "transcript.jsonl").write_text(json.dumps({"type": "fake", "run": 7, "argv": []}) + "\n")

    summary = playtest.run_playtest(
        "Launch a rocket.",
        out,
        command=[os.fspath(agent), "{prompt}"],
        seed=1,
        camera=False,
        timeout=120,
        until="rocket",
        max_resumes=2,
    )

    assert summary["milestone_tick"] is None
    assert summary["exit_code"] == 0
    assert len(summary["resumes"]) == 2
    prompts = [run["argv"][-1] for run in fake_runs(out)]
    # A custom command has no session to resume: it gets the task again, with the note.
    assert len(prompts) == 3
    assert prompts[0].endswith("Launch a rocket.")
    assert (
        prompts[1]
        == prompts[2]
        == (prompts[0] + "\n\nThe rocket has not launched yet. Keep playing.")
    )


def test_an_agent_that_fails_at_once_is_not_resumed_again_and_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rocket_world: Path
) -> None:
    out = rocket_world
    monkeypatch.setattr(RocketWorld, "launch_at_run", None)
    # As omp does when it cannot reach its auth broker.
    agent = tmp_path / "broken"
    agent.write_text(
        '#!/bin/sh\necho \'{"type": "started"}\'\n'
        "echo 'Auth broker at http://x is unreachable' >&2\nexit 1\n"
    )
    agent.chmod(0o755)

    summary = playtest.run_playtest(
        "Launch a rocket.",
        out,
        command=[os.fspath(agent), "{prompt}"],
        seed=1,
        camera=False,
        timeout=120,
        until="rocket",
        max_resumes=100,
    )

    # One resume after the first failure, none after the second.
    assert [resume["exit_code"] for resume in summary["resumes"]] == [1]
    assert summary["exit_code"] == 1
    assert summary["agent_failed"] == "Auth broker at http://x is unreachable"
    assert summary["milestone_tick"] is None
    assert (out / "transcript.jsonl").read_text().count('"started"') == 2


def test_a_stop_ends_the_run_without_a_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rocket_world: Path
) -> None:
    out = rocket_world
    monkeypatch.setattr(RocketWorld, "launch_at_run", None)
    # Plays on (sleeps) until the signal stops it.
    agent = fake_agent(tmp_path, "player", play_from=1)
    stop = threading.Event()

    def signal_once_started() -> None:
        while not fake_runs(out):
            time.sleep(0.05)
        stop.set()

    threading.Thread(target=signal_once_started, daemon=True).start()
    summary = playtest.run_playtest(
        "Launch a rocket.",
        out,
        command=[os.fspath(agent), "{prompt}"],
        seed=1,
        camera=False,
        timeout=120,
        until="rocket",
        stop=stop,
    )

    assert summary["stopped"] is True
    assert not summary["timed_out"]
    assert summary["exit_code"] is None
    assert summary["resumes"] == []
    assert len(fake_runs(out)) == 1
    assert json.loads((out / "summary.json").read_text())["stopped"] is True


def test_a_stop_while_the_resumed_agent_starts_keeps_the_earlier_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rocket_world: Path
) -> None:
    out = rocket_world
    monkeypatch.setattr(RocketWorld, "launch_at_run", None)
    agent = fake_agent(tmp_path, "quitter", play_from=99)
    stop = threading.Event()
    real_start = playtest.sandbox.start
    starts = 0

    # The stop signal reaches the sandbox as it starts the resumed agent, which
    # makes the start fail.
    def start(*args: Any, **kwargs: Any) -> Any:
        nonlocal starts
        starts += 1
        if starts == 2:
            stop.set()
            raise RuntimeError("bwrap failed: killed")
        return real_start(*args, **kwargs)

    monkeypatch.setattr(playtest.sandbox, "start", start)
    summary = playtest.run_playtest(
        "Launch a rocket.",
        out,
        command=[os.fspath(agent), "{prompt}"],
        seed=1,
        camera=False,
        timeout=120,
        until="rocket",
        stop=stop,
    )

    assert summary["stopped"] is True
    assert len(summary["resumes"]) == 1
    assert summary["fac_calls"] == 3
    assert summary["fac_errors"] == 1
    assert summary["methods"] == ["observe", "walk"]
    assert summary["response_bytes"]["total"] == 89


def test_a_claude_login_refreshed_during_the_run_goes_back_to_the_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rocket_world: Path
) -> None:
    given = {"accessToken": "a1", "refreshToken": "r1", "expiresAt": 1000, "scopes": ["x"]}
    host_home = tmp_path / "host-home"
    (host_home / ".claude").mkdir(parents=True)
    host_file = host_home / ".claude" / ".credentials.json"
    host_file.write_text(json.dumps({"claudeAiOauth": given}))
    monkeypatch.setenv("HOME", os.fspath(host_home))
    # Claude Code refreshing its login inside the sandbox, then quitting.
    claude = tmp_path / "bin" / "claude"
    claude.parent.mkdir()
    claude.write_text(
        "#!/usr/bin/python3\nimport json, pathlib\n"
        'path = pathlib.Path.home() / ".claude/.credentials.json"\n'
        'login = json.loads(path.read_text())["claudeAiOauth"]\n'
        'login.update(accessToken="a2", refreshToken="r2", expiresAt=2000)\n'
        'path.write_text(json.dumps({"claudeAiOauth": login}))\n'
    )
    claude.chmod(0o755)
    monkeypatch.setenv("PATH", f"{claude.parent}:{os.environ['PATH']}")

    summary = playtest.run_playtest(
        "Launch a rocket.",
        rocket_world,
        agent="claude",
        model="opus",
        seed=1,
        camera=False,
        timeout=120,
    )

    assert summary["exit_code"] == 0
    assert json.loads(host_file.read_text()) == {
        "claudeAiOauth": {**given, "accessToken": "a2", "refreshToken": "r2", "expiresAt": 2000}
    }
