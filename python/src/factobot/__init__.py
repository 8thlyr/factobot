"""Python client for the factobot daemon.

The daemon speaks newline-delimited JSON over a Unix socket; the protocol is
specified in docs/protocol.md at the repository root.
"""

from factobot.client import Client, FactobotError, default_socket

__all__ = ["Client", "FactobotError", "default_socket"]
