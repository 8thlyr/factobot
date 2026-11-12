"""The Inspect tool's `fac` command line: agents get the agent socket and the
agent commands, nothing harness-only."""

from __future__ import annotations

import pytest

from factobot.tasks import fac_argv


@pytest.mark.parametrize(
    ("command", "refused"),
    [
        ("fac dev lua game.tick", "dev"),
        ("fac daemon --seed 1", "daemon"),
        ("fac watch gamehost", "watch"),
        ("fac --socket /tmp/other.sock status", "--socket"),
        ("fac --socket=/tmp/other.sock status", "--socket"),
        ("fac status --socket /tmp/other.sock", "--socket"),
        ("fac --dev-socket /tmp/dev.sock status", "--dev-socket"),
        ("fac --dev-socket=/tmp/dev.sock status", "--dev-socket"),
        ("status --dev-socket=/tmp/dev.sock", "--dev-socket"),
    ],
)
def test_harness_only_commands_and_other_sockets_are_refused(command: str, refused: str) -> None:
    with pytest.raises(ValueError, match=f"^`fac {refused}` is not available to agents$"):
        fac_argv(command)


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("fac observe --radius 5", ["observe", "--radius", "5"]),
        ("walk 10,4 --wait", ["walk", "10,4", "--wait"]),
        ("fac craft 'iron-gear-wheel' --count=5", ["craft", "iron-gear-wheel", "--count=5"]),
    ],
)
def test_agent_commands_pass_through(command: str, args: list[str]) -> None:
    assert fac_argv(command) == args
