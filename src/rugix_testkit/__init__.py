"""Rugix testing toolkit — QEMU VM management and rugix-ctrl interface."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rugix-testkit")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from rugix_testkit.qemu.config import Drive, Pflash, VMConfig, find_free_port
from rugix_testkit.qemu.handle import VMHandle
from rugix_testkit.qemu.vm import QemuVM
from rugix_testkit.result import CmdError, CmdResult
from rugix_testkit.rugix import RugixCtrl, SystemInfo
from rugix_testkit.types import JsonObject, JsonValue

__all__ = [
    "CmdError",
    "CmdResult",
    "Drive",
    "Pflash",
    "QemuVM",
    "RugixCtrl",
    "SystemInfo",
    "VMConfig",
    "VMHandle",
    "JsonObject",
    "JsonValue",
    "find_free_port",
]
