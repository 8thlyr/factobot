"""A timed-out or garbled daemon reply must not be read as the next call."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from factobot.client import Client


def _handle(conn: socket.socket) -> None:
    conn.settimeout(2)
    buf = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                request = json.loads(line)
                method = request["method"]
                if method == "slow":
                    time.sleep(0.6)
                    try:
                        conn.sendall(_reply(request["id"], result="late"))
                    except OSError:
                        return
                elif method == "bad":
                    conn.sendall(_reply(request["id"], ok=False, code="rejected", message="no"))
                elif method == "junk":
                    conn.sendall(b"not json\n")
                else:
                    conn.sendall(_reply(request["id"], result=method))
    except OSError:
        return
    finally:
        conn.close()


def _reply(
    request_id: int,
    *,
    result: str | None = None,
    ok: bool = True,
    code: str = "",
    message: str = "",
) -> bytes:
    if ok:
        body: dict[str, object] = {"id": request_id, "ok": True, "result": result}
    else:
        body = {"id": request_id, "ok": False, "error": {"code": code, "message": message}}
    return json.dumps(body).encode() + b"\n"


@pytest.fixture
def daemon(tmp_path: Path) -> Iterator[tuple[Path, list[int]]]:
    path = tmp_path / "fac.sock"
    ready = threading.Event()
    stop = threading.Event()
    accepted: list[int] = []

    def serve() -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(path))
        sock.listen(8)
        sock.settimeout(0.2)
        ready.set()
        try:
            while not stop.is_set():
                try:
                    conn, _ = sock.accept()
                except TimeoutError:
                    continue
                accepted.append(1)
                threading.Thread(target=_handle, args=(conn,), daemon=True).start()
        finally:
            sock.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(2)
    yield path, accepted
    stop.set()
    thread.join(2)


def test_a_timed_out_call_is_not_the_next_calls_reply(daemon: tuple[Path, list[int]]) -> None:
    path, accepted = daemon
    client = Client(path, timeout=0.2)
    try:
        with pytest.raises(TimeoutError, match=r"slow got no reply in 0\.2 s"):
            client.call("slow")
        assert client.call("echo") == "echo"
    finally:
        client.close()
    # The late reply stayed on the old connection.
    assert len(accepted) == 2
