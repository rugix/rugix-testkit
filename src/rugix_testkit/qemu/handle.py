"""High-level VM handle combining QEMU process and SSH connection."""

from __future__ import annotations

import json
import logging
import time
import warnings
from pathlib import Path
from typing import Any

import fabric

from ..result import CmdResult
from ..types import JsonObject
from .config import VMConfig
from .ssh import run_cmd, wait_for_ssh
from .vm import QemuVM

logger = logging.getLogger(__name__)


class VMHandle:
    """
    Convenience facade: running QEMU VM + SSH connection.

    Use as a context manager for automatic cleanup::

        with VMHandle.start(config) as vm:
            result = vm.run(["uname", "-a"])
    """

    def __init__(self, config: VMConfig, *, work_dir: Path | None = None) -> None:
        self._qemu = QemuVM(config, work_dir=work_dir)
        self._conn: fabric.Connection | None = None
        self._ssh_port: int | None = None
        self._command_history: list[CmdResult] = []
        self._closed = False

    @property
    def config(self) -> VMConfig:
        """The VM configuration."""
        return self._qemu.config

    @property
    def serial_output(self) -> str:
        """Captured serial console output from QEMU."""
        return self._qemu.serial_output

    @classmethod
    def start(
        cls,
        config: VMConfig,
        *,
        work_dir: Path | None = None,
        boot_timeout: float = 300,
    ) -> VMHandle:
        """
        Prepare a VM, start it, and wait for SSH.

        Args:
            config: VM configuration.
            work_dir: Persistent work directory (temp dir if *None*).
            boot_timeout: Seconds to wait for SSH after boot.
        """
        handle = cls(config, work_dir=work_dir)
        handle._qemu.prepare()
        handle._ssh_port = handle._qemu.start()

        try:
            handle._conn = wait_for_ssh(port=handle._ssh_port, timeout=boot_timeout)
        except Exception:
            logger.error("Boot failed. Serial output:\n%s", handle._qemu.serial_output)
            handle._qemu.stop()
            handle._qemu.cleanup()
            raise

        return handle

    @property
    def command_history(self) -> list[CmdResult]:
        """All commands executed on the VM via :meth:`run`, in order."""
        return list(self._command_history)

    def run(self, args: list[str], *, check: bool = True, **kwargs: Any) -> CmdResult:
        """Run a command on the VM over SSH."""
        assert self._conn is not None
        result = run_cmd(self._conn, args, check=check, **kwargs)
        self._command_history.append(result)
        return result

    def run_json(self, args: list[str], **kwargs: Any) -> JsonObject:
        """Run a command on the VM and parse stdout as JSON."""
        result = self.run(args, hide=True, **kwargs)
        data: JsonObject = json.loads(result.stdout)
        return data

    def close(self) -> None:
        """Close SSH, stop QEMU, and clean up the work directory."""
        self._closed = True
        if self._conn is not None:
            self._conn.close()
        self._qemu.stop()
        self._qemu.cleanup()

    def reboot(self, timeout: float = 300) -> None:
        """Reboot the VM and wait for SSH to come back up."""
        try:
            self.run(["reboot"], check=False, hide=True)
        except Exception:
            pass
        self.wait_for_reboot(timeout=timeout)

    def wait_for_reboot(self, timeout: float = 300) -> None:
        """Wait for an in-progress reboot to complete and reconnect SSH."""
        assert self._ssh_port is not None and self._conn is not None

        deadline = time.monotonic() + timeout
        transport = self._conn.transport
        if transport is not None:
            while time.monotonic() < deadline:
                if not transport.is_active():
                    break
                time.sleep(0.5)
            else:
                logger.warning("SSH transport never went down, reconnecting anyway.")

        self._conn.close()

        time.sleep(10)

        remaining = max(0, deadline - time.monotonic())
        self._conn = wait_for_ssh(port=self._ssh_port, timeout=remaining or 30)

    def __enter__(self) -> VMHandle:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        if not self._closed:
            warnings.warn(
                "VMHandle was garbage collected without close(). "
                "Use 'with VMHandle.start(...) as vm:' to ensure cleanup.",
                ResourceWarning,
                stacklevel=1,
            )
