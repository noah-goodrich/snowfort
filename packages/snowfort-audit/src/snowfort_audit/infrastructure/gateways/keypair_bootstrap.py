"""Keypair authentication bootstrap for Snowflake.

Generates an RSA-2048 keypair, writes the private key to disk with mode 0600,
and returns the ALTER USER SQL the operator must run to register the public key.

Security invariants:
- Private key is NEVER written to /tmp or world-readable locations.
- Key files with group-read or world-read bits are rejected on existence check.
- The ALTER USER SQL contains only the public key (no private material).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path


def _public_key_bytes_b64(public_key) -> str:  # type: ignore[return]
    """Return base64-only portion of the public key PEM (no header/footer)."""
    from cryptography.hazmat.primitives import serialization

    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    lines = [ln for ln in pem.splitlines() if not ln.startswith("-----")]
    return "".join(lines)


def _check_key_path(path: Path) -> None:
    """Raise ValueError if path is insecure or already exists with bad perms."""
    resolved = path.resolve()
    # Block /tmp and /var/tmp to prevent world-readable key leaks.
    if str(resolved).startswith("/tmp") or str(resolved).startswith("/var/tmp"):
        raise ValueError(
            f"Private key path '{path}' is inside /tmp. "
            "Choose a path within your home directory, e.g. ~/.snowflake/rsa_key.p8"
        )
    if path.exists():
        mode = path.stat().st_mode
        # Reject if group-read (0o040) or world-read (0o004) bits are set.
        if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH):
            oct_mode = oct(stat.S_IMODE(mode))
            raise ValueError(
                f"Existing key file '{path}' has insecure permissions ({oct_mode}). "
                "Expected mode 0600 (owner read/write only). "
                "Fix with: chmod 600 '{path}'"
            )


def generate_keypair(
    key_path: str | Path,
    username: str,
    dry_run: bool = False,
) -> str:
    """Generate RSA-2048 keypair and return the ALTER USER SQL.

    In dry-run mode the keypair is generated in memory but NOT written to disk.
    The ALTER USER SQL is returned in both modes so the caller can print it.

    Args:
        key_path: Path where the private key PEM file will be written.
        username: Snowflake username for the ALTER USER statement.
        dry_run: If True, generate keypair in memory but do not write to disk.

    Returns:
        ALTER USER SQL string (private key is NOT included).

    Raises:
        ValueError: If key_path is insecure or has bad permissions.
        ImportError: If cryptography package is not available.
    """
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError as exc:
        raise ImportError(
            "The 'cryptography' package is required for keypair bootstrap. "
            "Install it: pip install cryptography"
        ) from exc

    path = Path(key_path).expanduser()
    _check_key_path(path)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    private_pem: bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write with restrictive permissions — create with 0600 directly.
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, private_pem)
        finally:
            os.close(fd)
        # Double-check the file mode (umask might interfere on some systems).
        actual_mode = stat.S_IMODE(path.stat().st_mode)
        if actual_mode != 0o600:
            path.chmod(0o600)

    pub_b64 = _public_key_bytes_b64(private_key.public_key())
    alter_sql = f"ALTER USER {username} SET RSA_PUBLIC_KEY='{pub_b64}';"
    return alter_sql
