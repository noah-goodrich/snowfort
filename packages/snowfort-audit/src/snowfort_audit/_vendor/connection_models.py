"""Connection options and auth (vendored)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthCredentials:
    """Groups sensitive authentication parameters."""

    password: str | None = None
    passcode: str | None = None
    private_key_path: str | None = None


@dataclass(frozen=True)
class ConnectionOptions:
    """Encapsulates connection parameters for Snowflake."""

    account: str
    user: str
    auth: AuthCredentials
    role: str | None = None
    warehouse: str | None = None
    authenticator: str | None = None
