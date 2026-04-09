"""Unit tests for keypair_bootstrap module (C2)."""

from __future__ import annotations

import shutil
import stat
import tempfile
from pathlib import Path

import pytest

from snowfort_audit.infrastructure.gateways.keypair_bootstrap import (
    _check_key_path,
    generate_keypair,
)


@pytest.fixture()
def safe_tmp(request):
    """Temp directory outside /tmp (uses HOME dir) so security check passes."""
    base = Path.home() / ".snowfort_test_tmp"
    base.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(dir=base))
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestCheckKeyPath:
    def test_rejects_tmp(self):
        with pytest.raises(ValueError, match="/tmp"):
            _check_key_path(Path("/tmp/rsa_key.p8"))

    def test_rejects_var_tmp(self):
        with pytest.raises(ValueError, match="/tmp"):
            _check_key_path(Path("/var/tmp/rsa_key.p8"))

    def test_rejects_existing_key_with_bad_permissions(self, safe_tmp):
        key_path = safe_tmp / "rsa_key.p8"
        key_path.write_bytes(b"dummy")
        key_path.chmod(0o644)
        with pytest.raises(ValueError, match="insecure permissions"):
            _check_key_path(key_path)

    def test_accepts_existing_key_mode_0600(self, safe_tmp):
        key_path = safe_tmp / "rsa_key.p8"
        key_path.write_bytes(b"dummy")
        key_path.chmod(0o600)
        _check_key_path(key_path)  # should not raise

    def test_accepts_nonexistent_path(self, safe_tmp):
        _check_key_path(safe_tmp / "new_key.p8")  # should not raise


class TestGenerateKeypair:
    def test_dry_run_returns_alter_sql_no_file(self, safe_tmp):
        """dry_run=True: generates SQL but does NOT write to disk."""
        key_path = safe_tmp / "test_rsa.p8"
        sql = generate_keypair(key_path, username="TESTUSER", dry_run=True)
        assert not key_path.exists()
        assert sql.startswith("ALTER USER TESTUSER SET RSA_PUBLIC_KEY='")
        assert sql.endswith(";")
        key_content = sql.split("'")[1]
        assert len(key_content) > 100

    def test_writes_key_file_mode_0600(self, safe_tmp):
        """Non-dry-run: writes private key with mode 0600."""
        key_path = safe_tmp / "rsa_key.p8"
        generate_keypair(key_path, username="TESTUSER", dry_run=False)
        assert key_path.exists()
        mode = stat.S_IMODE(key_path.stat().st_mode)
        assert mode == 0o600, f"Expected 0600, got {oct(mode)}"

    def test_key_file_is_valid_pem(self, safe_tmp):
        """Written key must be a valid unencrypted RSA PEM."""
        key_path = safe_tmp / "rsa_key.p8"
        generate_keypair(key_path, username="TESTUSER", dry_run=False)
        content = key_path.read_text()
        assert "BEGIN RSA PRIVATE KEY" in content or "BEGIN PRIVATE KEY" in content

    def test_alter_sql_contains_username(self, safe_tmp):
        """ALTER USER SQL must reference the given username."""
        key_path = safe_tmp / "rsa_key.p8"
        sql = generate_keypair(key_path, username="NOAH_AUDITOR", dry_run=True)
        assert "NOAH_AUDITOR" in sql

    def test_rejects_tmp_path(self):
        """Refuses to write private key to /tmp."""
        with pytest.raises(ValueError, match="/tmp"):
            generate_keypair("/tmp/rsa_key.p8", username="TESTUSER", dry_run=False)

    def test_rejects_existing_key_with_bad_permissions(self, safe_tmp):
        """Refuses to use an existing key file with group/world read bits."""
        key_path = safe_tmp / "rsa_key.p8"
        key_path.write_bytes(b"dummy")
        key_path.chmod(0o644)
        with pytest.raises(ValueError, match="insecure permissions"):
            generate_keypair(key_path, username="TESTUSER", dry_run=False)

    def test_accepts_existing_key_with_good_permissions(self, safe_tmp):
        """Overwrites an existing 0600 key file without error."""
        key_path = safe_tmp / "rsa_key.p8"
        key_path.write_bytes(b"dummy")
        key_path.chmod(0o600)
        sql = generate_keypair(key_path, username="TESTUSER", dry_run=False)
        assert "TESTUSER" in sql

    def test_creates_parent_directory(self, safe_tmp):
        """Creates intermediate directories if they do not exist."""
        key_path = safe_tmp / "subdir" / "nested" / "rsa_key.p8"
        generate_keypair(key_path, username="TESTUSER", dry_run=False)
        assert key_path.exists()

    def test_dry_run_rejects_tmp_path(self):
        """Even in dry_run, /tmp path is rejected."""
        with pytest.raises(ValueError, match="/tmp"):
            generate_keypair("/tmp/rsa_key.p8", username="TESTUSER", dry_run=True)
