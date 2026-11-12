from __future__ import annotations

import base64
import itertools
import json
import os
import socket
import tempfile
from pathlib import Path
from typing import Any, TextIO

PROTOCOL_VERSION = 3
# Past the daemon's screenshot budget (60 s) and its RCON budget (10 s), so a
# slow render or save comes back as the daemon's own error. A timeout still
# drops the socket: the reply may arrive later, or only in part (decision 86).
DEFAULT_TIMEOUT = 90.0


class FactobotError(Exception):
    """The daemon answered with `ok: false`."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def default_socket() -> Path:
    """Same resolution as `fac --socket`: FACTOBOT_SOCKET, then the runtime dir."""
    if explicit := os.environ.get("FACTOBOT_SOCKET"):
        return Path(explicit)
    # Like `fac`, an empty or relative XDG_RUNTIME_DIR counts as unset: the XDG
    # Base Directory Specification says a relative path there is invalid.
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    if Path(runtime).is_absolute():
        base = Path(runtime)
    else:
        base = Path(tempfile.gettempdir()) / f"factobot-{os.environ.get('USER', 'user')}"
    return base / "factobot" / "fac.sock"


class Client:
    """One connection to a factobot daemon. Calls are sequential.

    A call that times out, or whose reply is not one JSON line for that call,
    closes the socket. The next call connects again, so a late or half-read
    reply cannot be taken for it. A reply the daemon finished, including
    `ok: false`, keeps the connection.
    """

    def __init__(
        self,
        socket_path: str | os.PathLike[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self._path = os.fspath(socket_path or default_socket())
        self._timeout = timeout
        self._sock: socket.socket | None = None
        self._reader: TextIO | None = None
        self._ids = itertools.count(1)
        # The `hud` of the latest answer that had one (docs/protocol.md).
        self.hud: dict[str, Any] | None = None
        self._connect()

    def _connect(self) -> None:
        self.close()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(self._timeout)
            sock.connect(self._path)
        except Exception:
            sock.close()
            raise
        self._sock = sock
        self._reader = sock.makefile("r", encoding="utf-8")

    def call(self, method: str, params: Any = None) -> Any:
        if self._sock is None or self._reader is None:
            self._connect()
        sock, reader = self._sock, self._reader
        if sock is None or reader is None:
            raise ConnectionError("not connected")
        request_id = next(self._ids)
        request = {"v": PROTOCOL_VERSION, "id": request_id, "method": method, "params": params}
        try:
            sock.sendall(json.dumps(request).encode() + b"\n")
            line = reader.readline()
        except TimeoutError:
            self.close()
            raise TimeoutError(f"{method} got no reply in {self._timeout:g} s") from None
        except OSError:
            self.close()
            raise
        if not line:
            self.close()
            raise ConnectionError("daemon closed the connection")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as err:
            self.close()
            raise ConnectionError("daemon sent a response that is not JSON") from err
        if not isinstance(response, dict):
            self.close()
            raise ConnectionError("daemon sent a response that is not an object")
        if response.get("id") != request_id:
            self.close()
            raise ConnectionError(f"response id {response.get('id')} != request {request_id}")
        if "hud" in response:
            self.hud = response["hud"]
        if "ok" not in response:
            self.close()
            raise ConnectionError("daemon response has no ok field")
        if not response["ok"]:
            error = response["error"]
            raise FactobotError(error["code"], error["message"])
        return response["result"]

    def status(self) -> dict[str, Any]:
        return self.call("status")

    def screenshot(
        self, path: str | os.PathLike[str], *, zoom: float | None = None, grid: bool = True
    ) -> dict[str, Any]:
        """What the agent's screen shows (`screen`), written to `path` as a PNG.

        Returns the result with the file's absolute `path` in place of the
        image data, as `fac screenshot` prints it. `grid` lays map coordinates
        over the picture. Needs a world started with a camera.
        """
        result = self.call("screen", {"zoom": zoom, "grid": grid})
        file = Path(path).absolute()
        file.write_bytes(base64.b64decode(result.pop("png_base64")))
        result["path"] = os.fspath(file)
        return result

    def close(self) -> None:
        reader, self._reader = self._reader, None
        sock, self._sock = self._sock, None
        # Closing the reader closes the socket. Closing both raises EBADF.
        if reader is not None:
            reader.close()
        elif sock is not None:
            sock.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
