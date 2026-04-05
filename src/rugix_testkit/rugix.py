"""Typed wrapper around the rugix-ctrl CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .result import CmdResult
from .types import JsonObject

if TYPE_CHECKING:
    from .qemu.handle import VMHandle


@dataclass
class SystemInfo:
    """Parsed output of ``rugix-ctrl system info --json``."""

    raw: JsonObject

    @property
    def boot_flow(self) -> str:
        """The active boot flow (e.g. ``"grub"``)."""
        boot = self.raw["boot"]
        assert isinstance(boot, dict)
        result = boot["bootFlow"]
        assert isinstance(result, str)
        return result

    @property
    def active_group(self) -> str | None:
        """The currently booted group (e.g. ``"a"``), or ``None``."""
        boot = self.raw["boot"]
        assert isinstance(boot, dict)
        result = boot.get("activeGroup")
        assert result is None or isinstance(result, str)
        return result

    @property
    def default_group(self) -> str | None:
        """The default boot group, or ``None``."""
        boot = self.raw["boot"]
        assert isinstance(boot, dict)
        result = boot.get("defaultGroup")
        assert result is None or isinstance(result, str)
        return result

    @property
    def slots(self) -> JsonObject:
        """Slot information keyed by slot name."""
        result = self.raw.get("slots", {})
        assert isinstance(result, dict)
        return result


class RugixCtrl:
    """Interface to rugix-ctrl running inside a VM."""

    def __init__(self, vm: VMHandle) -> None:
        self.vm = vm

    def system_info(self) -> SystemInfo:
        """Query system info from rugix-ctrl."""
        data = self.vm.run_json(["rugix-ctrl", "system", "info", "--json"])
        return SystemInfo(raw=data)

    def update_install(
        self,
        source: str,
        *,
        reboot: str = "no",
        insecure: bool = True,
    ) -> CmdResult:
        """Install an update bundle from *source*."""
        cmd = ["rugix-ctrl", "update", "install", source, "--reboot", reboot]
        if insecure:
            cmd.append("--insecure-skip-bundle-verification")
        return self.vm.run(cmd, hide=True, timeout=300)

    def system_commit(self) -> CmdResult:
        """Commit the current system state."""
        return self.vm.run(["rugix-ctrl", "system", "commit"], hide=True)
