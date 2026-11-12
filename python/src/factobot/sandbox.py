"""Run an agent harness in a bubblewrap sandbox that shows it `fac` and nothing of the harness.

The sandbox is the same for every harness, so no harness's own permission
rules have to hold it. Inside it the agent finds:

- `/opt/factobot/bin/fac`: the agent's `fac` (the `fac-agent` build), which
  has no `daemon`, `watch` or `dev` subcommands to run;
- `/run/factobot/fac.sock`: the world's agent socket, alone in its directory
  (`FACTOBOT_SOCKET` points at it);
- `/opt/agent/bin/`: the harness binary;
- `/home/agent`: a throwaway home holding only what the harness needs to
  authenticate, with the empty working directory `/home/agent/work`;
- `/usr` and `/etc` read-only, a private `/tmp`, `/dev` and `/proc`, and a
  network of its own that slirp4netns connects to the internet, so the
  harness can reach its model API.

Everything else is absent: the repository and its worktrees, the run
directory with the config, call log and dev socket, `/run/user`, the rest of
`$HOME`, and the host's processes (`--unshare-pid` gives the sandbox its own
`/proc`, so the server's command line is not visible). The sandbox's own
network namespace hides the host's abstract Unix sockets (an X server's among
them), and slirp4netns's `--disable-host-loopback` keeps the host's
localhost services out of reach. Unreachable routes in that namespace keep
out the host's other addresses and the private, tailnet and link-local
ranges, where `--listen` puts a game port and other hosts run worlds; the
only exceptions are the address and TCP port pairs a harness needs, such as
omp's auth broker, which nftables rules in the namespace hold to that port.
"""

from __future__ import annotations

import fcntl
import json
import os
import select
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import IO, Any

BWRAP = "/usr/bin/bwrap"
SLIRP4NETNS = "/usr/bin/slirp4netns"
NSENTER = "/usr/bin/nsenter"
IP = "/usr/bin/ip"
NFT = "/usr/bin/nft"
# slirp4netns's gateway, through which the sandbox reaches everything outside.
SLIRP_GATEWAY = "10.0.2.2"
# Ranges the sandbox may not reach, besides the host's own addresses: private
# LANs, the shared range Tailscale and carrier NAT use, and link-local. The
# slirp4netns network 10.0.2.0/24 stays reachable through its more specific
# route, for DNS at 10.0.2.3.
BLOCKED_RANGES = (
    "10.0.0.0/8",
    "100.64.0.0/10",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.168.0.0/16",
)
# slirp4netns forwards DNS sent to this address to the host's resolver.
RESOLV_CONF = "nameserver 10.0.2.3\n"
# ioctl on a namespace fd that returns an fd for the user namespace owning it.
NS_GET_USERNS = 0xB701
# How long slirp4netns may take to signal that the sandbox network is up.
SLIRP_READY_TIMEOUT = 30.0
# After SIGKILL, how long to wait before leaving a stuck process unreaped.
REAP_TIMEOUT = 5.0
HOME = "/home/agent"
WORKDIR = f"{HOME}/work"
SOCKET_DIR = "/run/factobot"
FAC_BIN = "/opt/factobot/bin"
AGENT_BIN = "/opt/agent/bin"


def resolve_binary(name: str) -> Path:
    """The real file behind `name` on PATH, through symlinks and mise's shims."""
    found = shutil.which(name)
    if found is None:
        raise FileNotFoundError(f"{name} is not on PATH")
    path = Path(found).resolve()
    if path.name == "mise":
        # A mise command wrapper is a symlink to mise itself; ask mise for the tool.
        path = Path(
            subprocess.run(
                ["mise", "which", name], check=True, capture_output=True, text=True
            ).stdout.strip()
        ).resolve()
    return path


def bwrap_command(
    command: list[str],
    *,
    home: Path,
    socket_dir: Path,
    fac: Path,
    binaries: dict[str, Path],
    expose: Sequence[Path] = (),
    info_fd: int,
    block_fd: int,
    resolv_fd: int,
) -> list[str]:
    """The bwrap invocation that runs `command` in the sandbox.

    `home` is mounted read-write at HOME, `socket_dir` (holding the agent
    socket only) read-only at SOCKET_DIR, `fac` (the agent's build,
    `fac-agent`) at FAC_BIN/fac, and each of `binaries` at AGENT_BIN/<name>.
    `expose` adds host paths read-only at the same path, for a custom harness
    that needs more than one file. bwrap writes the sandbox's pid to
    `info_fd`, waits for a byte on `block_fd` before it runs `command`, and
    reads the sandbox's resolv.conf from `resolv_fd`; `start` drives all three.
    """
    args = [
        BWRAP,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        # Run as root, bwrap keeps every capability without this, and the agent
        # could delete the unreachable routes `_block_local_networks` adds.
        "--cap-drop",
        "ALL",
        "--info-fd",
        str(info_fd),
        "--block-fd",
        str(block_fd),
        "--ro-bind",
        "/usr",
        "/usr",
    ]
    # Arch and most current distributions link these into /usr; mirror the host.
    for top in ("/bin", "/sbin", "/lib", "/lib64"):
        path = Path(top)
        if path.is_symlink():
            args += ["--symlink", os.readlink(path), top]
        elif path.is_dir():
            args += ["--ro-bind", top, top]
    args += [
        "--ro-bind",
        "/etc",
        "/etc",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/var/tmp",
        "--tmpfs",
        "/run",
        # /etc/resolv.conf may link into /run (systemd-resolved's stub); bind at its target.
        "--ro-bind-data",
        str(resolv_fd),
        os.path.realpath("/etc/resolv.conf"),
        "--ro-bind",
        os.fspath(socket_dir),
        SOCKET_DIR,
        "--ro-bind",
        os.fspath(fac),
        f"{FAC_BIN}/fac",
    ]
    for name, path in binaries.items():
        args += ["--ro-bind", os.fspath(path), f"{AGENT_BIN}/{name}"]
    for path in expose:
        args += ["--ro-bind", os.fspath(path), os.fspath(path)]
    args += ["--bind", os.fspath(home), HOME, "--chdir", WORKDIR, "--", *command]
    return args


@contextmanager
def start(
    command: list[str],
    *,
    env: dict[str, str],
    stdout: int | IO[Any] | None,
    stderr: int | IO[Any] | None = subprocess.STDOUT,
    home: Path,
    socket_dir: Path,
    fac: Path,
    binaries: dict[str, Path],
    expose: Sequence[Path] = (),
    allow: Sequence[tuple[str, int]] = (),
) -> Iterator[subprocess.Popen[bytes]]:
    """Run `command` in the sandbox with a network of its own; yields the bwrap process.

    The sandbox gets its own network namespace, so the host's abstract Unix
    sockets and loopback stay out of reach; slirp4netns gives it outbound
    internet with `--disable-host-loopback`, and unreachable routes keep the
    host's other addresses and the LAN and tailnet ranges out. `allow` lists
    the exceptions, IPv4 addresses with the one TCP port the sandbox may reach
    on each (omp's auth broker on the host's tailnet address). The command
    runs only once the network is up, and the bwrap process is killed if it
    is still running when the block exits.
    """
    if not Path(SLIRP4NETNS).exists():
        raise SystemExit(f"the sandbox's network needs slirp4netns; install it ({SLIRP4NETNS})")
    with _Pipes() as pipes, tempfile.TemporaryFile() as log:
        info_r, info_w = pipes.pipe()
        block_r, block_w = pipes.pipe()
        resolv_r, resolv_w = pipes.pipe()
        os.write(resolv_w, RESOLV_CONF.encode())
        pipes.close(resolv_w)
        args = bwrap_command(
            command,
            home=home,
            socket_dir=socket_dir,
            fac=fac,
            binaries=binaries,
            expose=expose,
            info_fd=info_w,
            block_fd=block_r,
            resolv_fd=resolv_r,
        )
        # stdin is /dev/null: the agent must not read the operator's terminal.
        process = subprocess.Popen(
            args,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            pass_fds=(info_w, block_r, resolv_r),
        )
        try:
            for fd in (info_w, block_r, resolv_r):
                pipes.close(fd)
            text = pipes.read_all(info_r)
            if not text:
                raise RuntimeError(f"bwrap failed to start the sandbox (exit {process.wait()})")
            child = json.loads(text)["child-pid"]
            # bwrap soon moves the child into a nested user namespace with no
            # capabilities, so join the one that owns the network namespace.
            netns = pipes.add(os.open(f"/proc/{child}/ns/net", os.O_RDONLY))
            userns = pipes.add(fcntl.ioctl(netns, NS_GET_USERNS))
            _block_local_networks(netns, userns, {address for address, _ in allow})
            exit_r, exit_w = pipes.pipe()
            ready_r, ready_w = pipes.pipe()
            slirp = subprocess.Popen(
                [
                    SLIRP4NETNS,
                    "--configure",
                    "--mtu=65520",
                    "--disable-host-loopback",
                    # A seccomp filter limits the syscalls a libslirp bug could use.
                    # Not --enable-sandbox: it needs setegid(0), which fails in
                    # bwrap's user namespace, where only the user is mapped.
                    "--enable-seccomp",
                    "--netns-type=path",
                    "--userns-path",
                    f"/proc/self/fd/{userns}",
                    "--exit-fd",
                    str(exit_r),
                    "--ready-fd",
                    str(ready_w),
                    f"/proc/self/fd/{netns}",
                    "tap0",
                ],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                pass_fds=(exit_r, ready_w, netns, userns),
            )
            try:
                for fd in (exit_r, ready_w):
                    pipes.close(fd)
                try:
                    ready = read_byte(ready_r, SLIRP_READY_TIMEOUT)
                except TimeoutError:
                    reap(slirp)
                    raise RuntimeError(
                        f"slirp4netns was not ready within {SLIRP_READY_TIMEOUT:g} s"
                    ) from None
                if ready != b"1":
                    reap(slirp)
                    log.seek(0)
                    raise RuntimeError(
                        "slirp4netns could not give the sandbox a network: "
                        + log.read().decode(errors="replace").strip()
                    )
                _allow_hosts(netns, userns, allow)
                for fd in (netns, userns):
                    pipes.close(fd)
                os.write(block_w, b"1")
                pipes.close(block_w)
                yield process
            finally:
                # Closing the exit fd stops slirp4netns.
                pipes.close(exit_w)
                reap(slirp)
        finally:
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    process.kill()
            reap(process)


def reap(process: subprocess.Popen[bytes], *, timeout: float = REAP_TIMEOUT) -> None:
    """Wait up to `timeout` for `process`, then kill it and wait once more.

    A process that has already exited is reaped. One that survives SIGKILL is
    left in place so a stuck process cannot hang the runner.
    """
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            process.kill()
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=timeout)


def read_byte(fd: int, timeout: float) -> bytes:
    """One byte from `fd`, or `b""` on EOF.

    Raises TimeoutError when nothing arrives within `timeout` seconds, so a
    slirp4netns that never signals ready cannot stall the runner.
    """
    deadline = time.monotonic() + timeout
    os.set_blocking(fd, False)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"no byte within {timeout:g} s")
        readable, _, _ = select.select([fd], [], [], remaining)
        if not readable:
            continue
        try:
            return os.read(fd, 1)
        except BlockingIOError:
            continue


def _block_local_networks(netns: int, userns: int, allowed: set[str]) -> None:
    """Add unreachable routes in the sandbox's network namespace for the host's
    own IPv4 addresses (but those in `allowed`) and `BLOCKED_RANGES`.

    slirp4netns connects out from the host, so without these the sandbox
    could reach every service the host can: a game port on the tailnet
    address, other worlds on the LAN. The agent cannot remove the routes,
    since bwrap drops all its capabilities (`--cap-drop ALL`), even when the
    runner is root.
    """
    interfaces = json.loads(subprocess.check_output([IP, "-j", "-4", "addr", "show"]))
    own = {
        f"{address['local']}/32"
        for interface in interfaces
        for address in interface.get("addr_info", [])
        if not address["local"].startswith("127.") and address["local"] not in allowed
    }
    routes = "".join(f"route add unreachable {dest}\n" for dest in (*BLOCKED_RANGES, *sorted(own)))
    _in_netns(netns, userns, [IP, "-batch", "-"], routes)


def _allow_hosts(netns: int, userns: int, allow: Sequence[tuple[str, int]]) -> None:
    """Let the sandbox reach each address in `allow` on its TCP port and nothing else.

    A route for the address itself, more specific than the unreachable ones,
    sends it out through slirp4netns, whose network must be up for that.
    Routes can't tell ports apart, so nftables rules in the namespace then
    accept TCP to that port only and reject everything else to the address.
    """
    if not allow:
        return
    addresses = sorted({address for address, _ in allow})
    routes = "".join(
        f"route add {address}/32 via {SLIRP_GATEWAY} dev tap0\n" for address in addresses
    )
    accepts = "".join(
        f"    ip daddr {address} tcp dport {port} accept\n" for address, port in allow
    )
    rejects = "".join(f"    ip daddr {address} reject\n" for address in addresses)
    rules = (
        "table ip factobot {\n"
        "  chain output {\n"
        "    type filter hook output priority filter; policy accept;\n"
        f"{accepts}{rejects}"
        "  }\n"
        "}\n"
    )
    _in_netns(netns, userns, [NFT, "-f", "-"], rules)
    _in_netns(netns, userns, [IP, "-batch", "-"], routes)


def _in_netns(netns: int, userns: int, argv: list[str], script: str) -> None:
    """Run `argv` with `script` on stdin in the sandbox's network namespace, with the
    capabilities of its user namespace."""
    # --keep-caps carries the capabilities nsenter gains in the sandbox's user
    # namespace over to the command, which runs as the unprivileged user.
    result = subprocess.run(
        [
            NSENTER,
            f"--user=/proc/self/fd/{userns}",
            f"--net=/proc/self/fd/{netns}",
            "--preserve-credentials",
            "--keep-caps",
            *argv,
        ],
        input=script.encode(),
        capture_output=True,
        pass_fds=(netns, userns),
    )
    if result.returncode != 0:
        raise RuntimeError(
            "could not wall the sandbox off from the host's networks: "
            + result.stderr.decode(errors="replace").strip()
        )


class _Pipes:
    """File descriptors `start` still holds; each is closed once, at the latest on exit."""

    def __init__(self) -> None:
        self.open: set[int] = set()

    def add(self, fd: int) -> int:
        self.open.add(fd)
        return fd

    def pipe(self) -> tuple[int, int]:
        read, write = os.pipe()
        self.open |= {read, write}
        return read, write

    def close(self, fd: int) -> None:
        if fd in self.open:
            self.open.remove(fd)
            os.close(fd)

    def read_all(self, fd: int) -> str:
        self.open.remove(fd)
        with os.fdopen(fd) as stream:
            return stream.read()

    def __enter__(self) -> _Pipes:
        return self

    def __exit__(self, *_: object) -> None:
        for fd in list(self.open):
            self.close(fd)


def base_env() -> dict[str, str]:
    """The environment every harness starts from inside the sandbox."""
    return {
        "PATH": f"{FAC_BIN}:{AGENT_BIN}:/usr/local/bin:/usr/bin:/bin",
        "HOME": HOME,
        "USER": "agent",
        "SHELL": "/bin/bash",
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "TERM": "dumb",
        "TMPDIR": "/tmp",
        "FACTOBOT_SOCKET": f"{SOCKET_DIR}/fac.sock",
    }
