"""Tests for QEMU configuration types."""

import pytest

from rugix_testkit.qemu.config import VMConfig, find_free_port


class TestVMConfig:
    def test_effective_machine_defaults(self):
        assert VMConfig(arch="x86_64").effective_machine == "q35"
        assert VMConfig(arch="aarch64").effective_machine == "virt"
        assert VMConfig(arch="arm").effective_machine == "virt"

    def test_effective_machine_explicit(self):
        assert VMConfig(arch="x86_64", machine="pc").effective_machine == "pc"

    def test_effective_machine_unknown_arch(self):
        with pytest.raises(ValueError, match="No default machine"):
            VMConfig(arch="riscv64").effective_machine


def test_find_free_port():
    port = find_free_port()
    assert isinstance(port, int)
    assert port > 0
