"""Tests for SnowflakeGovernanceRepository."""

from unittest.mock import MagicMock

from snowfort_audit.infrastructure.repositories.governance import SnowflakeGovernanceRepository


def test_provision_auditor_role_calls_gateway():
    """provision_auditor_role executes role, warehouse, and SNOWFORT.AUDIT schema provisioning."""
    mock_gateway = MagicMock()
    repo = SnowflakeGovernanceRepository(mock_gateway)
    repo.provision_auditor_role("AUDITOR", "audit_user", "AUDIT_WH")
    # 4 original + 6 new (CREATE DB, CREATE SCHEMA, 4 GRANTs) = 10
    assert mock_gateway.execute.call_count == 10
    calls = [str(c) for c in mock_gateway.execute.call_args_list]
    assert any("CREATE ROLE" in c and "AUDITOR" in c for c in calls)
    assert any("GRANT ROLE" in c and "audit_user" in c for c in calls)
    assert any("IMPORTED PRIVILEGES" in c and "SNOWFLAKE" in c for c in calls)
    assert any("USAGE ON WAREHOUSE" in c and "AUDIT_WH" in c for c in calls)
    assert any("CREATE DATABASE IF NOT EXISTS SNOWFORT" in c for c in calls)
    assert any("CREATE SCHEMA IF NOT EXISTS SNOWFORT.AUDIT" in c for c in calls)
    assert any("USAGE ON DATABASE SNOWFORT" in c for c in calls)
    assert any("USAGE ON SCHEMA SNOWFORT.AUDIT" in c for c in calls)
