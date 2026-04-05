"""SSH connection helpers using Fabric."""

from __future__ import annotations

import json
import logging
import shlex
import time

import fabric
import paramiko

from ..result import CmdError, CmdResult
from ..types import JsonObject

logger = logging.getLogger(__name__)


def connect_ssh(
    host: str = "localhost",
    port: int = 2222,
    user: str = "root",
    connect_timeout: float = 10,
) -> fabric.Connection:
    """
    Open a Fabric SSH connection.

    Defaults are tailored for test VMs: passwordless ``root`` access
    with no key lookup or agent forwarding. Not suitable for
    production SSH connections.
    """
    # Fabric doesn't support SSH "none" auth, so we set up the
    # paramiko transport manually to avoid password auth attempts.
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sock = paramiko.Transport((host, port))
    sock.connect(username=user)
    sock.auth_none(user)
    client._transport = sock

    conn = fabric.Connection(host=host, port=port, user=user)
    conn.client = client
    conn.transport = sock
    logger.info("SSH connected to %s:%d", host, port)
    return conn


def wait_for_ssh(
    host: str = "localhost",
    port: int = 2222,
    user: str = "root",
    timeout: float = 300,
    interval: float = 5,
) -> fabric.Connection:
    """
    Poll until SSH becomes available.

    Returns a connected :class:`fabric.Connection`.
    """
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    # Suppress paramiko's ERROR-level transport logging during polling
    # — failed attempts are expected and not actionable.
    paramiko_logger = logging.getLogger("paramiko.transport")
    original_level = paramiko_logger.level
    paramiko_logger.setLevel(logging.CRITICAL)
    try:
        while time.monotonic() < deadline:
            try:
                conn = connect_ssh(host, port, user, connect_timeout=min(interval, 10))
                paramiko_logger.setLevel(original_level)
                return conn
            except Exception as exc:
                last_error = exc
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(interval, remaining))
    finally:
        paramiko_logger.setLevel(original_level)

    raise TimeoutError(
        f"SSH not available on {host}:{port} after {timeout}s: {last_error}"
    )


def run_cmd(
    conn: fabric.Connection,
    args: list[str],
    *,
    check: bool = True,
    **kwargs: object,
) -> CmdResult:
    """
    Run a command given as a list of arguments over SSH.

    Arguments are escaped via :func:`shlex.join` so callers never need
    to worry about shell quoting. Raises :class:`CmdError` on non-zero
    exit unless *check* is ``False``.
    """
    command = shlex.join(args)
    # Tell fabric not to raise on non-zero so we can handle it ourselves.
    result = conn.run(command, warn=True, in_stream=False, **kwargs)
    cmd_result = CmdResult(
        command=command,
        stdout=result.stdout,
        stderr=result.stderr,
        return_code=result.return_code,
    )
    if check and not cmd_result.ok:
        raise CmdError(cmd_result)
    return cmd_result


def run_json(
    conn: fabric.Connection,
    args: list[str],
    *,
    check: bool = True,
    **kwargs: object,
) -> JsonObject:
    """
    Run a command and parse its stdout as JSON.

    *args* is a list of command arguments (escaped automatically).
    """
    result = run_cmd(conn, args, check=check, hide=True, **kwargs)
    data: JsonObject = json.loads(result.stdout)
    return data
