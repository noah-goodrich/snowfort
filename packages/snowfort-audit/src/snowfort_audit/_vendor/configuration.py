"""Environment configuration gateway (vendored)."""

import os


class EnvConfigurationGateway:
    """Read configuration from environment variables."""

    def get_env(self, key: str, default: str | None = None) -> str | None:
        return os.getenv(key, default)
