from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import Severity, Violation
from snowfort_audit.use_cases.offline_scan import OfflineScanUseCase


@pytest.fixture
def telemetry() -> MagicMock:
    return MagicMock()


# JUSTIFICATION: Orchestration test requires mocking multiple infrastructure components (fs, manifest, rules).
def test_scan_offline_orchestration(tmp_path, telemetry):  # pylint: disable=fragile-test-mocks
    # Setup dummy directory
    (tmp_path / "manifest.yml").write_text("definitions: {}", encoding="utf-8")

    mock_rule = MagicMock()
    mock_rule.id = "TEST_STATIC"
    # check() returns a list of Violations
    mock_rule.check.return_value = [Violation("TEST_STATIC", "Res", "Msg", Severity.LOW)]
    # check_static() is also called for SQL files, mock it too just in case
    mock_rule.check_static.return_value = []

    mock_fs = MagicMock()
    mock_fs.join_path.return_value = str(tmp_path / "manifest.yml")
    mock_fs.exists.return_value = True
    mock_fs.read_text.return_value = "definitions: {}"
    mock_fs.walk.return_value = []

    # 1. Test empty definitions case
    mock_manifest_repo = MagicMock()
    mock_manifest_repo.load_definitions.return_value = {}

    use_case = OfflineScanUseCase(mock_fs, mock_manifest_repo, [mock_rule], telemetry)
    violations = use_case.execute(str(tmp_path))
    assert isinstance(violations, list)

    # 2. Test with resource definitions
    (tmp_path / "manifest.yml").write_text("definitions:\n  my_wh:\n    type: WAREHOUSE", encoding="utf-8")

    # Refresh mock fs for the new content
    mock_fs = MagicMock()
    mock_fs.join_path.return_value = str(tmp_path / "manifest.yml")
    mock_fs.exists.return_value = True
    mock_fs.read_text.return_value = "definitions:\n  my_wh:\n    type: WAREHOUSE"
    mock_fs.walk.return_value = []  # No sql files

    mock_manifest_repo = MagicMock()
    mock_manifest_repo.load_definitions.return_value = {"my_wh": {"type": "WAREHOUSE"}}

    use_case = OfflineScanUseCase(mock_fs, mock_manifest_repo, [mock_rule], telemetry)
    violations = use_case.execute(str(tmp_path))

    mock_rule.check.assert_called()
    assert len(violations) >= 1
    assert violations[0].rule_id == "TEST_STATIC"


def test_scan_offline_sql_files(tmp_path, telemetry):
    """OfflineScanUseCase calls _scan_sql_files and runs check_static on SQL content."""
    mock_manifest_repo = MagicMock()
    mock_manifest_repo.load_definitions.return_value = {}

    mock_rule = MagicMock()
    mock_rule.id = "STAT_001"
    mock_rule.check.return_value = []
    mock_rule.check_static.return_value = [
        Violation("STAT_001", "foo.sql", "Hardcoded env", Severity.LOW),
    ]

    sql_file = tmp_path / "definitions" / "foo.sql"
    sql_file.parent.mkdir(parents=True, exist_ok=True)
    sql_file.write_text("SELECT * FROM DB_DEV.TBL", encoding="utf-8")

    mock_fs = MagicMock()
    mock_fs.walk.return_value = [(str(tmp_path / "definitions"), [], ["foo.sql"])]
    mock_fs.join_path.side_effect = lambda a, b: str(tmp_path / "definitions" / b)
    mock_fs.read_text.return_value = "SELECT * FROM DB_DEV.TBL"

    use_case = OfflineScanUseCase(mock_fs, mock_manifest_repo, [mock_rule], telemetry)
    violations = use_case.execute(str(tmp_path))

    mock_rule.check_static.assert_called()
    assert any(v.rule_id == "STAT_001" for v in violations)


def test_scan_offline_analyze_sql_file_read_error(telemetry):
    """_analyze_single_sql_file calls telemetry.error on OSError."""
    mock_manifest_repo = MagicMock()
    mock_manifest_repo.load_definitions.return_value = {}
    mock_rule = MagicMock()
    mock_rule.check.return_value = []
    mock_rule.check_static.return_value = []

    mock_fs = MagicMock()
    mock_fs.walk.return_value = [("/root", [], ["bad.sql"])]
    mock_fs.join_path.return_value = "/root/bad.sql"
    mock_fs.read_text.side_effect = OSError("Permission denied")

    use_case = OfflineScanUseCase(mock_fs, mock_manifest_repo, [mock_rule], telemetry)
    violations = use_case.execute("/root")
    telemetry.error.assert_called()
    assert "Failed to read SQL file" in telemetry.error.call_args[0][0]
    assert len(violations) == 0


def test_scan_offline_rule_throws_in_execute(telemetry):
    """When a rule raises in execute(), telemetry.error is called and other rules still run."""
    mock_manifest_repo = MagicMock()
    mock_manifest_repo.load_definitions.return_value = {"r1": {"type": "WAREHOUSE"}}

    good_rule = MagicMock()
    good_rule.id = "GOOD"
    good_rule.check.return_value = [Violation("GOOD", "r1", "Ok", Severity.LOW)]
    good_rule.check_static.return_value = []

    bad_rule = MagicMock()
    bad_rule.id = "BAD"
    bad_rule.check.side_effect = ValueError("bad rule")
    bad_rule.check_static.return_value = []

    mock_fs = MagicMock()
    mock_fs.walk.return_value = []

    use_case = OfflineScanUseCase(mock_fs, mock_manifest_repo, [bad_rule, good_rule], telemetry)
    violations = use_case.execute("/path")
    telemetry.error.assert_called()
    assert any(v.rule_id == "GOOD" for v in violations)


def test_scan_offline_rule_returns_single_violation(telemetry):
    """When rule.check returns a single Violation (non-list), it is still collected."""
    mock_manifest_repo = MagicMock()
    mock_manifest_repo.load_definitions.return_value = {"r1": {"type": "WAREHOUSE"}}

    mock_rule = MagicMock()
    mock_rule.id = "SINGLE"
    mock_rule.check.return_value = Violation("SINGLE", "r1", "One", Severity.LOW)
    mock_rule.check_static.return_value = []

    mock_fs = MagicMock()
    mock_fs.walk.return_value = []

    use_case = OfflineScanUseCase(mock_fs, mock_manifest_repo, [mock_rule], telemetry)
    violations = use_case.execute("/path")
    assert len(violations) == 1
    assert violations[0].rule_id == "SINGLE"


def test_scan_offline_analyze_sql_file_rule_raises(telemetry):
    """_analyze_single_sql_file calls telemetry.error when check_static raises."""
    mock_manifest_repo = MagicMock()
    mock_manifest_repo.load_definitions.return_value = {}
    mock_rule = MagicMock()
    mock_rule.check.return_value = []
    mock_rule.check_static.side_effect = RuntimeError("parse error")

    mock_fs = MagicMock()
    mock_fs.walk.return_value = [("/root", [], ["x.sql"])]
    mock_fs.join_path.return_value = "/root/x.sql"
    mock_fs.read_text.return_value = "SELECT 1"

    use_case = OfflineScanUseCase(mock_fs, mock_manifest_repo, [mock_rule], telemetry)
    violations = use_case.execute("/root")
    telemetry.error.assert_called()
    assert "Unexpected error analyzing" in telemetry.error.call_args[0][0]
    assert len(violations) == 0
