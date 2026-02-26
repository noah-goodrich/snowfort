"""Tests for SnowflakeGovernanceRepository."""

from unittest.mock import MagicMock

from snowfort_audit.infrastructure.repositories.governance import SnowflakeGovernanceRepository


def test_provision_auditor_role_calls_gateway_four_times():
    """provision_auditor_role executes CREATE ROLE, GRANT ROLE TO USER, GRANT IMPORTED PRIVILEGES, GRANT USAGE ON WAREHOUSE."""
    mock_gateway = MagicMock()
    repo = SnowflakeGovernanceRepository(mock_gateway)
    repo.provision_auditor_role("AUDITOR", "audit_user", "AUDIT_WH")
    assert mock_gateway.execute.call_count == 4
    calls = [str(c) for c in mock_gateway.execute.call_args_list]
    assert any("CREATE ROLE" in c and "AUDITOR" in c for c in calls)
    assert any("GRANT ROLE" in c and "audit_user" in c for c in calls)
    assert any("IMPORTED PRIVILEGES" in c and "SNOWFLAKE" in c for c in calls)
    assert any("USAGE ON WAREHOUSE" in c and "AUDIT_WH" in c for c in calls)
