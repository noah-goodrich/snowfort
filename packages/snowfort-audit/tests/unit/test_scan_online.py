from unittest.mock import ANY, MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import Severity, Violation
from snowfort_audit.use_cases.online_scan import OnlineScanUseCase


@pytest.fixture
def telemetry() -> MagicMock:
    return MagicMock()


def test_scan_online_success(telemetry):
    """Test scan_online with successful connection and rule violations."""

    # Mock gateway
    mock_gateway = MagicMock()
    mock_cursor = MagicMock()
    mock_gateway.get_cursor.return_value = mock_cursor

    # Mock rule behavior
    mock_rule = MagicMock()
    mock_rule.check_online.return_value = [Violation("TEST_001", "TestResource", "Test Message", Severity.HIGH)]

    use_case = OnlineScanUseCase(mock_gateway, [mock_rule], telemetry)
    violations = use_case.execute()

    # Verify usage (get_cursor is called for initial connection, rule execution, and SHOW VIEWS)
    assert mock_gateway.get_cursor.called
    mock_rule.check_online.assert_called_with(mock_cursor, scan_context=ANY)

    # Verify output
    assert len(violations) == 1
    assert violations[0].rule_id == "TEST_001"
    assert violations[0].message == "Test Message"


def test_scan_online_connection_failure(telemetry):
    """Test scan_online handles connection errors gracefully."""

    mock_gateway = MagicMock()
    mock_gateway.get_cursor.side_effect = Exception("Connection failed")
    mock_rule = MagicMock()

    use_case = OnlineScanUseCase(mock_gateway, [mock_rule], telemetry)

    with pytest.raises(Exception, match="Connection failed") as excinfo:
        use_case.execute()

    assert "Connection failed" in str(excinfo.value)


def test_scan_online_no_violations(telemetry):
    """Test scan_online with no violations found."""
    mock_gateway = MagicMock()
    mock_cursor = MagicMock()
    mock_gateway.get_cursor.return_value = mock_cursor

    mock_rule = MagicMock()
    mock_rule.check_online.return_value = []

    use_case = OnlineScanUseCase(mock_gateway, [mock_rule], telemetry)
    violations = use_case.execute()

    assert not violations
