# JUSTIFICATION: Snowflake Connector uses C-extensions or is missing stubs in this environment.
from snowflake.connector.errors import (  # pylint: disable=import-error,no-name-in-module
    Error as SnowflakeConnectorError,
)

from snowfort_audit._vendor.exceptions import InfrastructureError


class DatabaseError(InfrastructureError):
    """Wrapper for database driver errors."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


__all__ = ["DatabaseError", "SnowflakeConnectorError"]
