"""SSH keys for logging into test VMs."""

from __future__ import annotations

from pathlib import Path

import paramiko

from .locks import exclusive_lock


def ensure_ssh_key(path: Path) -> str:
    """Create an RSA key pair at *path* unless it exists.

    Returns the public key in ``authorized_keys`` format. The key is kept
    across runs because Bakery caches layers containing it.
    """
    with exclusive_lock(path.with_name(f"{path.name}.lock")):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            paramiko.RSAKey.generate(3072).write_private_key_file(str(path))
        key = paramiko.RSAKey.from_private_key_file(str(path))
    return f"{key.get_name()} {key.get_base64()} rugix-testkit"
