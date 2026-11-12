"""Call-log reads and process cleanup stay reliable when a run is killed or a write is partial."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from contextlib import suppress
from pathlib import Path

from factobot.harness import read_jsonl, stop_daemon


def test_read_jsonl_ignores_a_partial_trailing_line(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    path.write_bytes(b'{"surface":"agent","n":1}\n{"surface":"dev"')
    assert read_jsonl(path) == [{"surface": "agent", "n": 1}]
    with path.open("ab") as file:
        file.write(b',"n":2}\n')
    assert read_jsonl(path) == [{"surface": "agent", "n": 1}, {"surface": "dev", "n": 2}]


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)


def test_stop_daemon_kills_a_group_that_ignores_sigterm(tmp_path: Path) -> None:
    child_file = tmp_path / "child"
    script = tmp_path / "run"
    script.write_text(f"#!/bin/bash\ntrap '' TERM\nsleep 60 &\necho $! > {child_file}\nwait\n")
    script.chmod(0o755)
    process = subprocess.Popen([os.fspath(script)], start_new_session=True)
    try:
        deadline = time.monotonic() + 2
        while not child_file.exists():
            assert process.poll() is None and time.monotonic() < deadline
            time.sleep(0.02)
        child = int(child_file.read_text().strip())
        stop_daemon(process, timeout=0.3)
        assert process.returncode == -signal.SIGKILL
        deadline = time.monotonic() + 2
        while Path(f"/proc/{child}").exists():
            assert time.monotonic() < deadline, f"child {child} is still running"
            time.sleep(0.02)
    finally:
        _kill_group(process)
