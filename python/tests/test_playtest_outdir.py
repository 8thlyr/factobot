"""Refuse a run directory that already holds a world, still run one that holds
only an old transcript, and pick two different default directories in the same
second."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

import factobot.playtest as playtest


def _files(root: Path) -> dict[str, bytes]:
    return {
        os.fspath(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class _FreshWorld:
    """A new map that answers the polls a run makes before the agent exits."""

    game_port = 0

    def __init__(self, socket: Path) -> None:
        self.agent_socket = socket

    def milestones(self) -> dict[str, Any]:
        return {"tick": 0, "packs": []}

    def lua(self, _code: str) -> Any:
        return {"tick": 0, "names": {}}

    def calls(self) -> list[dict[str, Any]]:
        return []


@pytest.mark.parametrize("name", ["save.zip", "calls.jsonl"])
def test_a_run_directory_that_holds_a_world_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    out = tmp_path / "out"
    world = out / "world"
    world.mkdir(parents=True)
    (world / name).write_bytes(b"earlier")
    (out / "transcript.jsonl").write_text("old transcript\n")
    before = _files(out)

    def start_world(**_: Any) -> None:
        raise AssertionError("start_world entered")

    def mkdtemp(*_args: Any, **_kwargs: Any) -> str:
        raise AssertionError("agent home created")

    monkeypatch.setattr(playtest, "start_world", start_world)
    monkeypatch.setattr(tempfile, "mkdtemp", mkdtemp)

    save = world / "save.zip"
    with pytest.raises(SystemExit) as raised:
        playtest.run_playtest(
            "task",
            out,
            command=["/bin/true", "{prompt}"],
            seed=1,
            camera=False,
            timeout=5,
        )

    assert str(raised.value) == (
        f"{out} holds an earlier run's world. Continue it with --save {save} --out <new directory>"
    )
    assert _files(out) == before
