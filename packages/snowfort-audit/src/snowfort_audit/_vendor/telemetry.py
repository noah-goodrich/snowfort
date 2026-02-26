"""Minimal TelemetryPort implementation using Rich (no stellar_ui_kit)."""

__stellar_version__ = "1.1.1"

import os

from rich.console import Console
from rich.prompt import Confirm, Prompt

# Log level order: DEBUG (10) < INFO (20) < WARNING (30) < ERROR (40)
_LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}


class RichTelemetry:
    """Telemetry implementation using Rich for CLI output. info/debug respect log level."""

    def __init__(
        self,
        project_name: str = "Snowfort",
        color: str = "cyan",
        welcome_msg: str = "WAF Audit",
        log_level: str | None = None,
    ):
        self._console = Console()
        self._project_name = project_name
        self._color = color
        self._welcome_msg = welcome_msg
        raw = log_level or os.environ.get("SNOWFORT_LOG_LEVEL", "INFO")
        level = (raw or "INFO").upper()
        self._log_level_num = _LOG_LEVELS.get(level, _LOG_LEVELS["INFO"])

    def set_log_level(self, level: str) -> None:
        self._log_level_num = _LOG_LEVELS.get(level.upper(), _LOG_LEVELS["INFO"])

    def step(self, message: str) -> None:
        self._console.print(message)

    def error(self, message: str) -> None:
        self._console.print(f"[red]{message}[/red]")

    def warning(self, message: str) -> None:
        if self._log_level_num <= _LOG_LEVELS["WARNING"]:
            self._console.print(f"[yellow]{message}[/yellow]")

    def info(self, message: str) -> None:
        if self._log_level_num <= _LOG_LEVELS["INFO"]:
            self._console.print(f"[dim]{message}[/dim]")

    def debug(self, message: str) -> None:
        if self._log_level_num <= _LOG_LEVELS["DEBUG"]:
            self._console.print(f"[dim]{message}[/dim]")

    def ask(self, prompt: str, default: str | None = None) -> str:
        return Prompt.ask(prompt, default=default or "")

    def confirm(self, message: str) -> bool:
        return Confirm.ask(message, default=False)

    def handshake(self) -> None:
        self._console.print(f"[{self._color}]{self._project_name}[/{self._color}] {self._welcome_msg}")
