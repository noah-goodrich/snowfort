"""Tests for interface/cli.py helper functions and commands."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from snowfort_audit.domain.conventions import SnowfortConventions
from snowfort_audit.domain.results import AuditResult
from snowfort_audit.domain.rule_definitions import Severity
from snowfort_audit.interface.cli import _sh_escape, main
from snowfort_audit.interface.cli.report import (
    conventions_for_pillar,
    pillar_style,
    severity_border_style,
    write_audit_cache,
)


def test_severity_border_style_critical():
    assert severity_border_style(Severity.CRITICAL) == "red"


def test_severity_border_style_high():
    assert severity_border_style(Severity.HIGH) == "red"


def test_severity_border_style_medium():
    assert severity_border_style(Severity.MEDIUM) == "yellow"


def test_severity_border_style_low():
    assert severity_border_style(Severity.LOW) == "yellow"


def test_pillar_style():
    result = pillar_style("Security")
    assert "Security" in result


def test_conventions_for_cost():
    conv = SnowfortConventions()
    lines = conventions_for_pillar("Cost", conv)
    keys = [k for k, _ in lines]
    assert "warehouse.auto_suspend_seconds" in keys


def test_conventions_for_security():
    conv = SnowfortConventions()
    lines = conventions_for_pillar("Security", conv)
    keys = [k for k, _ in lines]
    assert "security.require_mfa_all_users" in keys


def test_conventions_for_governance():
    conv = SnowfortConventions()
    lines = conventions_for_pillar("Governance", conv)
    keys = [k for k, _ in lines]
    assert "tags.required_tags" in keys


def test_conventions_for_operations():
    conv = SnowfortConventions()
    lines = conventions_for_pillar("Operations", conv)
    keys = [k for k, _ in lines]
    assert "tags.required_tags" in keys
    assert "warehouse.auto_suspend_seconds" in keys


def test_conventions_for_unknown():
    conv = SnowfortConventions()
    lines = conventions_for_pillar("Unknown", conv)
    assert lines == []


def test_sh_escape_simple():
    assert _sh_escape("hello") == "'hello'"


def test_sh_escape_with_single_quote():
    result = _sh_escape("it's")
    assert '"' in result


def test_write_audit_cache(tmp_path):
    result = AuditResult.from_violations([])
    write_audit_cache(tmp_path, result, "test_target")
    cache_file = tmp_path / ".snowfort" / "audit_results.json"
    assert cache_file.exists()


def test_main_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "audit" in result.output.lower() or "Usage" in result.output


def test_audit_help():
    runner = CliRunner()
    result = runner.invoke(main, ["audit", "--help"])
    assert result.exit_code == 0


def test_scan_offline_no_violations():
    mock_use_case = MagicMock(execute=MagicMock(return_value=[]))
    mock_container = MagicMock()
    mock_container.get.side_effect = lambda key: mock_use_case if key == "OfflineScanUseCase" else MagicMock()
    mock_container.get_rules.return_value = []

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["audit", "scan", "--offline", "--path", "."], obj=mock_container)
    assert result.exit_code == 0


def test_rules_command():
    from snowfort_audit.domain.rule_definitions import Rule

    runner = CliRunner()
    mock_c = MagicMock()
    mock_c.get_rules.return_value = [
        Rule("SEC_001", "Admin Exposure", Severity.CRITICAL),
    ]
    result = runner.invoke(main, ["audit", "rules"], obj=mock_c)
    assert result.exit_code == 0
