"""Which run `agentview` attaches to, and what it shows for each harness."""

from __future__ import annotations

import io
import os
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from factobot.agentview import Follower, View, main, newest_run


def render(events: list[dict[str, Any]], calls: list[dict[str, Any]]) -> list[str]:
    out = io.StringIO()
    view = View(out, color=False, width=200, result_lines=3)
    for event in events:
        view.event(event)
    for call in calls:
        view.call(call)
    return [line.strip() for line in out.getvalue().splitlines()]


CALL = {
    "surface": "agent",
    "tick": 341,
    "method": "craft",
    "params": {"recipe": "no-such-item", "count": 1},
    "response": {"ok": False, "error": {"code": "rejected", "message": "no recipe"}},
}


def test_omp_events_show_messages_commands_and_results() -> None:
    # Shapes from omp 18.15 `--mode json`.
    lines = render(
        [
            {"type": "session", "version": 3, "cwd": "/home/agent/work"},
            {"type": "message_update", "assistantMessageEvent": {"type": "text_delta"}},
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "Check the status."},
                        {"type": "text", "text": "Looking."},
                        {
                            "type": "toolCall",
                            "name": "bash",
                            "arguments": {"command": "fac status"},
                        },
                    ],
                },
            },
            {
                "type": "tool_execution_end",
                "toolName": "bash",
                "result": {"content": [{"type": "text", "text": '{"ok":true,"result":1}'}]},
                "isError": False,
            },
            {
                "type": "tool_execution_end",
                "result": {"content": [{"type": "text", "text": "bash: nope"}]},
                "isError": True,
            },
            {"type": "agent_end", "messages": []},
        ],
        [CALL],
    )
    assert lines == [
        "agent started: omp",
        "Check the status.",
        "Looking.",
        "$ fac status",
        "ok 1",
        "error:",
        "bash: nope",
        "agent finished",
    ]


def test_unknown_harness_shows_the_call_log() -> None:
    assert render([{"type": "something-else"}], [CALL]) == [
        '341 fac craft {"recipe":"no-such-item","count":1}',
        '341   error {"code":"rejected","message":"no recipe"}',
    ]


def test_a_custom_harness_with_claude_like_event_types_shows_the_call_log() -> None:
    events = [{"type": "result"}, {"type": "system"}, {"type": "assistant", "message": "hi"}]
    assert render(events, [CALL]) == render([], [CALL])


def test_known_harness_leaves_the_call_log_to_its_transcript() -> None:
    assert render([{"type": "system", "subtype": "init", "model": "m"}], [CALL]) == [
        "agent started: m"
    ]


def test_claude_tool_calls_and_results() -> None:
    lines = render(
        [
            {"type": "system", "subtype": "init", "model": "m"},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Bash", "input": {"command": "fac status"}},
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "s"}},
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "tool_result", "content": '{"ok":true,"result":1}\na\nb\nc'},
                        {"type": "tool_result", "content": "denied", "is_error": True},
                    ]
                },
            },
        ],
        [],
    )
    assert lines == [
        "agent started: m",
        "$ fac status",
        "Skill {'skill': 's'}",
        "ok 1",
        "a",
        "b",
        "... 1 more line",
        "error:",
        "denied",
    ]


def test_follower_holds_a_partial_line_until_its_newline(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    follower = Follower(path)
    assert list(follower.read()) == []
    path.write_bytes(b'not json\n{"x":"\xff"}\n{bad\n{"type":"a"}\n{"type":')
    assert list(follower.read()) == [{"type": "a"}]
    with path.open("ab") as file:
        file.write(b'"b"}\n')
    assert list(follower.read()) == [{"type": "b"}]


def test_follower_starts_over_on_a_file_cut_short_or_replaced(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_bytes(b'{"type":"old","n":1234567890}\n')
    follower = Follower(path)
    assert list(follower.read()) == [{"type": "old", "n": 1234567890}]
    path.write_bytes(b'{"type":"new"}\n')
    assert list(follower.read()) == [{"type": "new"}]
    # A new file in its place, longer than what was read of the old one.
    (tmp_path / "next.jsonl").write_bytes(b'{"type":"newer","n":1234567890}\n')
    (tmp_path / "next.jsonl").replace(path)
    assert list(follower.read()) == [{"type": "newer", "n": 1234567890}]


def test_malformed_messages_are_skipped() -> None:
    init = {"type": "system", "subtype": "init", "model": "m"}
    assert render(
        [
            init,
            {"type": "user", "message": "text"},
            {"type": "assistant", "message": {"content": "text"}},
            {"type": "assistant", "message": {"content": ["text", {"type": "text", "text": 1}]}},
            {"type": "user", "message": {"content": [None]}},
        ],
        [],
    ) == ["agent started: m"]
    assert render(
        [
            {"type": "session"},
            {"type": "message_end", "message": {"role": "assistant", "content": "text"}},
            {"type": "message_end", "message": {"role": "assistant", "content": ["text"]}},
        ],
        [],
    ) == ["agent started: omp"]


def test_escape_sequences_reach_the_terminal_as_text() -> None:
    # OSC 52 writes the watcher's clipboard, OSC 0 sets the window title, CSI clears the screen.
    text = "hi \x1b]52;c;ZWNobyBwd25lZA==\x07 \x1b]0;owned\x07 \x9b2J\x1b[2J done"
    out = io.StringIO()
    view = View(out, color=False, width=200, result_lines=3)
    view.event({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})
    view.event({"type": "user", "message": {"content": [{"type": "tool_result", "content": text}]}})
    shown = out.getvalue()
    controls = [char for char in shown if char != "\n" and unicodedata.category(char) == "Cc"]
    assert controls == []
    assert "\\x1b]52;c;ZWNobyBwd25lZA==\\x07" in shown


def make_run(root: Path, name: str, *, started: int, transcript: bool, summary: bool) -> Path:
    # What playtest.py leaves: `started` and world/ as the run begins, the
    # transcript once the agent starts, summary.json only on a normal finish.
    run = root / name
    (run / "world").mkdir(parents=True)
    (run / "started").touch()
    os.utime(run / "started", (started, started))
    if transcript:
        (run / "transcript.jsonl").write_text("{}\n")
    if summary:
        (run / "summary.json").write_text("{}\n")
    return run


def test_newest_run_picks_a_run_still_booting(tmp_path: Path) -> None:
    # The old run's directory changed last (its summary.json), after the new one began.
    old = make_run(tmp_path, "old-run", started=1_000, transcript=True, summary=True)
    os.utime(old, (3_000, 3_000))
    new = make_run(tmp_path, "new-run", started=2_000, transcript=False, summary=False)
    os.utime(new, (2_000, 2_000))

    assert newest_run(tmp_path) == new


def test_newest_run_prefers_a_live_run_over_one_that_just_finished(tmp_path: Path) -> None:
    # Two overlapping runs: the older one finishes, and writing its
    # summary.json makes its directory the most recently modified.
    live = make_run(tmp_path, "live-run", started=2_000, transcript=True, summary=False)
    os.utime(live, (2_000, 2_000))
    older = make_run(tmp_path, "older-run", started=1_000, transcript=True, summary=True)
    os.utime(older, (3_000, 3_000))

    assert newest_run(tmp_path) == live


def test_newest_run_passes_over_an_old_run_that_never_finished(tmp_path: Path) -> None:
    # A run stopped with Ctrl-C (or whose world failed to boot) never writes
    # summary.json; a later run that finished normally is still the newest,
    # even when the aborted run's directory changed after it.
    aborted = make_run(tmp_path, "aborted-old", started=1_000, transcript=True, summary=False)
    os.utime(aborted, (6_000, 6_000))
    finished = make_run(tmp_path, "finished-new", started=4_000, transcript=True, summary=True)
    os.utime(finished, (5_000, 5_000))

    assert newest_run(tmp_path) == finished


def test_a_directory_that_is_not_a_run_fails_instead_of_waiting(tmp_path: Path) -> None:
    (tmp_path / "x").mkdir()

    with pytest.raises(SystemExit, match="is not a playtest run directory"):
        main([str(tmp_path)])


def test_a_run_that_has_only_started_is_a_run(tmp_path: Path) -> None:
    # Between `started` and world/ the run is still setting up, not an error.
    (tmp_path / "started").touch()

    with pytest.raises(SystemExit, match=r"has no transcript\.jsonl"):
        main([str(tmp_path), "--no-follow"])


def test_a_negative_result_lines_is_refused(tmp_path: Path) -> None:
    (tmp_path / "world").mkdir()

    with pytest.raises(SystemExit) as raised:
        main([str(tmp_path), "--no-follow", "--result-lines", "-1"])
    assert raised.value.code == 2
