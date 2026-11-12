"""Follow a playtest agent live: what it says, the `fac` commands it runs and what they return.

    python -m factobot.agentview                      # newest run in target/playtests
    python -m factobot.agentview target/playtests/red-science-20261102-230056

Reads the run's `transcript.jsonl` (the harness's stdout: Claude Code's
stream-json or omp's JSON events, told apart by their shape) and the world's
`calls.jsonl`. For a harness whose output it does not know, it shows each
`fac` call from `calls.jsonl` instead, so any agent can be watched. It prints
what the agent has done so far, then follows the run, prefixing each new line
with the game tick of the latest `fac` call. It only reads files, so it can
watch from another terminal on the same host while the run goes on.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TextIO

# Event types that mark a transcript as omp's JSON mode. Claude Code's
# stream-json is told by its shape instead (see `is_claude`), since a custom
# harness may well print a bare `result` or `system` event of its own.
OMP_EVENTS = {"session", "agent_start", "message_end", "tool_execution_end", "agent_end"}

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"


class Follower:
    """Yields the complete JSON objects appended to a JSONL file since the last read."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.partial = b""
        self.inode: int | None = None

    def read(self) -> Iterator[dict[str, Any]]:
        try:
            with self.path.open("rb") as file:
                stat = os.fstat(file.fileno())
                # A file replaced (a reused run directory) or cut short starts over.
                if stat.st_ino != self.inode or stat.st_size < self.offset:
                    self.inode, self.offset, self.partial = stat.st_ino, 0, b""
                file.seek(self.offset)
                data = file.read()
        except FileNotFoundError:
            return
        self.offset += len(data)
        *lines, self.partial = (self.partial + data).split(b"\n")
        for line in lines:
            # A harness's stdout can carry the odd non-JSON line (warnings, hooks).
            if not line.startswith(b"{"):
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Bad JSON, or bytes that are not UTF-8.
                continue
            if isinstance(event, dict):
                yield event


def printable(text: str) -> str:
    """`text` with control characters shown as `\\xNN`, so the agent's output (or a
    `fac` result) cannot send escape sequences (clipboard writes, window titles)
    to the watcher's terminal."""
    return "".join(
        "    "
        if char == "\t"
        else f"\\x{ord(char):02x}"
        if unicodedata.category(char) == "Cc"
        else char
        for char in text
    )


def is_claude(event: dict[str, Any]) -> bool:
    """Whether `event` could only come from Claude Code's stream-json: its
    `system` init event, or a message event carrying a message object."""
    kind = event.get("type")
    if kind == "system":
        return event.get("subtype") == "init"
    return kind in ("assistant", "user") and isinstance(event.get("message"), dict)


class View:
    def __init__(self, out: TextIO, *, color: bool, width: int, result_lines: int) -> None:
        self.out = out
        self.color = color
        self.width = width
        self.result_lines = result_lines
        self.tick: int | None = None
        # "claude" or "omp" once the transcript shows which; None shows the call log.
        self.harness: str | None = None

    def paint(self, style: str, text: str) -> str:
        return f"{style}{text}{RESET}" if self.color else text

    def line(self, style: str, text: str) -> None:
        prefix = f"{self.tick:>8} " if self.tick is not None else " " * 9
        room = max(self.width - len(prefix), 20)
        for i, part in enumerate(text.splitlines() or [""]):
            part = printable(part)
            if len(part) > room:
                part = part[: room - 1] + "…"
            lead = prefix if i == 0 else " " * len(prefix)
            self.out.write(self.paint(DIM, lead) + self.paint(style, part) + "\n")

    def call(self, call: dict[str, Any]) -> None:
        if isinstance(call.get("tick"), int):
            self.tick = call["tick"]
        # With no transcript this view can read, the call log is the agent's story.
        if self.harness is None and call.get("surface") == "agent":
            params = call.get("params")
            params_text = json.dumps(params, separators=(",", ":")) if params else ""
            self.line(CYAN, f"fac {call.get('method')} {params_text}".rstrip())
            style, text = self.summarize(json.dumps(call.get("response")))
            self.line(style, f"  {text}")

    def event(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if self.harness is None:
            if is_claude(event):
                self.harness = "claude"
            elif kind in OMP_EVENTS:
                self.harness = "omp"
        if self.harness == "claude":
            self.claude_event(event)
        elif self.harness == "omp":
            self.omp_event(event)

    def claude_event(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            self.line(BOLD, f"agent started: {event.get('model')}")
        elif kind == "system" and event.get("subtype") == "permission_denied":
            self.line(YELLOW, f"denied: {event.get('tool_name')}")
        elif kind in ("assistant", "user"):
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                if kind == "assistant":
                    self.assistant(block)
                elif block.get("type") == "tool_result":
                    self.result(block.get("content"), is_error=bool(block.get("is_error")))
        elif kind == "result":
            cost = event.get("total_cost_usd")
            cost_text = f", ${cost:.2f}" if isinstance(cost, int | float) else ""
            self.line(BOLD, f"agent finished: {event.get('num_turns')} turns{cost_text}")
            if event.get("result"):
                self.line(BOLD, str(event["result"]))

    def omp_event(self, event: dict[str, Any]) -> None:
        # omp streams every token as `message_update`; the finished message
        # (`message_end`) and the tool's result (`tool_execution_end`) carry it all.
        kind = event.get("type")
        message = event.get("message")
        if kind == "session":
            self.line(BOLD, "agent started: omp")
        elif kind == "message_end" and isinstance(message, dict):
            content = message.get("content")
            if message.get("role") == "assistant" and isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        self.assistant(block)
        elif kind == "tool_execution_end":
            result = event.get("result")
            content = result.get("content") if isinstance(result, dict) else result
            self.result(content, is_error=bool(event.get("isError")))
        elif kind == "agent_end":
            self.line(BOLD, "agent finished")

    def assistant(self, block: dict[str, Any]) -> None:
        text, thinking = block.get("text"), block.get("thinking")
        if block.get("type") == "text" and isinstance(text, str) and text.strip():
            self.line(BOLD, text.strip())
        elif block.get("type") == "thinking" and isinstance(thinking, str) and thinking.strip():
            # Recent Claude models leave thinking text out by default; show it when there is some.
            self.line(DIM, thinking.strip())
        elif block.get("type") in ("tool_use", "toolCall"):
            # Claude Code's tool_use carries `input`, omp's toolCall `arguments`.
            tool_input = block.get("input", block.get("arguments", {}))
            command = tool_input.get("command") if isinstance(tool_input, dict) else None
            self.line(CYAN, f"$ {command}" if command else f"{block.get('name')} {tool_input}")

    def result(self, content: Any, *, is_error: bool) -> None:
        if isinstance(content, list):
            content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
        lines = [line for line in str(content or "").splitlines() if line.strip()]
        if is_error:
            self.line(RED, "\n".join(["error:", *lines[: self.result_lines]]))
            return
        for line in lines[: self.result_lines]:
            style, text = self.summarize(line)
            self.line(style, f"  {text}")
        if (hidden := len(lines) - self.result_lines) > 0:
            self.line(DIM, f"  ... {hidden} more line{'s' if hidden > 1 else ''}")

    @staticmethod
    def summarize(line: str) -> tuple[str, str]:
        """Style and text for one line of output: a `fac` response as `ok …` or `error …`."""
        try:
            response = json.loads(line)
        except json.JSONDecodeError:
            return DIM, line
        if not isinstance(response, dict) or "ok" not in response:
            return DIM, line
        if response["ok"]:
            return GREEN, f"ok {json.dumps(response.get('result'), separators=(',', ':'))}"
        return RED, f"error {json.dumps(response.get('error'), separators=(',', ':'))}"


def newest_run(root: Path) -> Path:
    # The run that started last. playtest.py touches `started` as a run
    # begins and never again, so its mtime is the start time; the directory's
    # own mtime moves whenever a file appears in it (the transcript, the
    # summary), so it cannot order runs that overlap or were cut short.
    # Directories from before the marker existed fall back to their mtime.
    def started(path: Path) -> float:
        marker = path / "started"
        return (marker if marker.exists() else path).stat().st_mtime

    runs = sorted((path for path in root.glob("*/") if path.is_dir()), key=started)
    if not runs:
        raise SystemExit(f"no playtest runs under {root}")
    return runs[-1]


def line_count(text: str) -> int:
    count = int(text)
    if count < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or more, not {count}")
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m factobot.agentview",
        description="Follow a playtest agent: its messages, the fac commands it runs and "
        "their results, each line prefixed with the game tick and cut to the terminal's "
        "width (not cut when stdout is not a terminal). Ctrl+C stops watching; "
        "the run goes on.",
        epilog="Example: python -m factobot.agentview target/playtests/red-science-20261102-230056",
    )
    parser.add_argument(
        "run",
        nargs="?",
        type=Path,
        help="playtest run directory [default: the newest under target/playtests]",
    )
    parser.add_argument("--no-follow", action="store_true", help="print what is there and exit")
    parser.add_argument(
        "--result-lines",
        type=line_count,
        default=3,
        help="lines of each command's output to show [default: 3]",
    )
    args = parser.parse_args(argv)

    run = args.run or newest_run(Path("target/playtests"))
    # playtest.py touches `started` once the harness is set up, makes world/
    # just after and transcript.jsonl once the agent starts; a directory with
    # none of them is not a run and never will be.
    markers = ("started", "world", "transcript.jsonl")
    if not run.is_dir() or not any((run / marker).exists() for marker in markers):
        raise SystemExit(f"{run} is not a playtest run directory")
    if args.no_follow and not (run / "transcript.jsonl").exists():
        raise SystemExit(f"{run} has no transcript.jsonl")
    transcript = Follower(run / "transcript.jsonl")
    calls = Follower(run / "world" / "calls.jsonl")
    view = View(
        sys.stdout,
        color=sys.stdout.isatty() and "NO_COLOR" not in os.environ,
        width=shutil.get_terminal_size().columns if sys.stdout.isatty() else sys.maxsize,
        result_lines=args.result_lines,
    )
    view.line(BOLD, f"watching {run}")
    if not (run / "transcript.jsonl").exists():
        view.line(
            DIM,
            "no transcript yet: the world is still booting, or the run failed before "
            f"the agent started (see {run / 'world' / 'daemon.log'}); waiting for the agent",
        )
    try:
        # What happened before we started has no tick to show: the transcript
        # carries no times, so print it bare, then tick each event seen live.
        for event in transcript.read():
            view.event(event)
        if view.harness is None:
            for call in calls.read():
                view.call(call)
        while not args.no_follow:
            if view.harness is None:
                # Learn the harness before showing calls a known one also shows.
                for event in transcript.read():
                    view.event(event)
            for call in calls.read():
                view.call(call)
            for event in transcript.read():
                view.event(event)
            sys.stdout.flush()
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
