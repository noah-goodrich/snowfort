"""Minimal DI container (vendored)."""

from collections.abc import Callable
from typing import Any, TypeVar

from snowfort_audit._vendor.configuration import EnvConfigurationGateway
from snowfort_audit._vendor.connection import ConnectionResolver
from snowfort_audit._vendor.credentials import KeyringCredentialGateway
from snowfort_audit._vendor.filesystem import LocalFileSystemGateway
from snowfort_audit._vendor.snowflake_gateway import SnowflakeGateway
from snowfort_audit._vendor.telemetry import RichTelemetry

T = TypeVar("T")


class BaseContainer:
    """Minimal DI container for audit (no stellar_ui_kit, no ResourceGateway)."""

    def __init__(self):
        self._singletons: dict[str, Any] = {}
        self._factories: dict[str, Callable[..., Any]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_singleton("FileSystemProtocol", LocalFileSystemGateway())
        self.register_singleton("ConfigurationProtocol", EnvConfigurationGateway())
        self.register_factory("SnowflakeQueryProtocol", lambda: SnowflakeGateway(None))
        self.register_singleton("CredentialProtocol", KeyringCredentialGateway())
        self.register_factory(
            "ConnectionResolver",
            lambda: ConnectionResolver(
                self.get("CredentialProtocol"),
                self.get("TelemetryPort"),
                self.get("ConfigurationProtocol"),
            ),
        )

    def register_telemetry(
        self, project_name: str = "Snowfort", color: str = "cyan", welcome_msg: str = "WAF Audit"
    ) -> None:
        telemetry = RichTelemetry(project_name=project_name, color=color, welcome_msg=welcome_msg)
        self.register_singleton("TelemetryPort", telemetry)

    def register_singleton(self, key: str, instance: Any) -> None:
        self._singletons[key] = instance

    def register_factory(self, key: str, factory: Callable[..., Any]) -> None:
        self._factories[key] = factory

    def get(self, key: str) -> Any:
        if key in self._singletons:
            return self._singletons[key]
        if key in self._factories:
            return self._factories[key]()
        raise ValueError(f"Dependency '{key}' not registered in container.")
