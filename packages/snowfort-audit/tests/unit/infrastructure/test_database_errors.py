"""Tests for database_errors module."""

from snowfort_audit._vendor.exceptions import InfrastructureError
from snowfort_audit.infrastructure.database_errors import DatabaseError, SnowflakeConnectorError


def test_database_error_is_infrastructure_error():
    e = DatabaseError("Connection failed")
    assert isinstance(e, InfrastructureError)
    assert str(e) == "Connection failed"
    assert e.original_error is None


def test_database_error_with_original():
    orig = ValueError("underlying")
    e = DatabaseError("Wrapper message", original_error=orig)
    assert e.original_error is orig


def test_snowflake_connector_error_imported():
    assert SnowflakeConnectorError is not None
