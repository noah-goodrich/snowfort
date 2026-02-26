"""Keyring credential gateway (vendored)."""

import contextlib

import keyring
import keyring.errors
from rich.console import Console
from rich.prompt import Prompt


class KeyringCredentialGateway:
    """Credential storage/retrieval via OS keyring when available; otherwise prompt-only."""

    def __init__(self):
        self._console = Console()

    def get_password(self, account: str, user: str) -> str:
        stored = self.get_stored_password(account, user)
        if not stored:
            self._console.print(f"[bold yellow]Credentials missing for {user}@{account}[/bold yellow]")
            stored = Prompt.ask(f"Enter Snowflake password for {user}", password=True)
            try:
                keyring.set_password(f"snowarch.{account}", user, stored)
            except (keyring.errors.KeyringError, RuntimeError):
                # No keyring backend (e.g. dev container); use password for this session only
                pass
        return stored

    def get_stored_password(self, account: str, user: str) -> str | None:
        try:
            return keyring.get_password(f"snowarch.{account}", user)
        except (keyring.errors.KeyringError, RuntimeError):
            return None

    def get_passcode(self, account: str, user: str) -> str | None:
        """Prompt for MFA passcode (TOTP). Leave empty for Duo Push. Not stored."""
        self._console.print(
            "[dim]MFA required. Enter 6-digit code from authenticator app, or leave empty for Duo Push.[/dim]"
        )
        value = Prompt.ask("MFA passcode", password=True, default="")
        return (value.strip() or None) if value else None

    def clear_credentials(self, account: str, user: str) -> None:
        with contextlib.suppress(keyring.errors.PasswordDeleteError, keyring.errors.KeyringError, RuntimeError):
            keyring.delete_password(f"snowarch.{account}", user)
