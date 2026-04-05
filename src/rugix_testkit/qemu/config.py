"""Configuration types for QEMU virtual machines."""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Drive:
    """
    A QEMU block device.

    When *overlay* is ``True``, a temporary qcow2 overlay is created on top
    of *file* (which is left unmodified). The overlay is expanded to *size*
    if given.
    """

    file: Path
    format: str = "raw"
    interface: str | None = None
    overlay: bool = False
    size: str | None = None


@dataclass(frozen=True)
class Pflash:
    """
    A QEMU pflash (firmware) drive.

    Mutable pflash images are copied to the work directory so the original
    is never modified.

    When *size* is set, a zero-filled image of that size is created and
    *file* is written at offset 0. When *size* is ``None`` and
    *readonly* is ``False``, the file is simply copied. When *file* is
    ``None`` (and *size* is set), an empty image is created.
    """

    file: Path | None = None
    format: str = "raw"
    readonly: bool = False
    size: str | None = None


_DEFAULT_MACHINES = {
    "x86_64": "q35",
    "aarch64": "virt",
    "arm": "virt",
}


@dataclass
class VMConfig:
    """
    Full configuration for a QEMU virtual machine.

    *machine* defaults to the standard QEMU machine for the given *arch*
    (``q35`` for x86_64, ``virt`` for aarch64/arm).
    """

    arch: str
    machine: str | None = None
    memory: int = 1024
    smp: int = 4
    cpu: str | None = None
    drives: list[Drive] = field(default_factory=list)
    pflash: list[Pflash] = field(default_factory=list)
    ssh_port: int | None = None
    net: str = "user,model=virtio-net-pci"
    extra_args: list[str] = field(default_factory=list)

    @property
    def qemu_binary(self) -> str:
        """The QEMU binary name for this architecture."""
        return f"qemu-system-{self.arch}"

    @property
    def effective_machine(self) -> str:
        """The machine type, falling back to a default for the architecture."""
        if self.machine is not None:
            return self.machine
        try:
            return _DEFAULT_MACHINES[self.arch]
        except KeyError:
            raise ValueError(
                f"No default machine for arch {self.arch!r}, specify explicitly"
            )


def find_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port
