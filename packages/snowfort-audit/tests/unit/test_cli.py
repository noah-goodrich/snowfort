from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from snowfort_audit.interface.cli import main


def test_scan_offline_command():
    runner = CliRunner()
    mock_use_case = MagicMock()
    mock_use_case.execute.return_value = []
    mock_container = MagicMock()
    mock_container.get.side_effect = lambda k: (
        mock_use_case if k == "OfflineScanUseCase" else (MagicMock() if k == "ensure_account_config" else MagicMock())
    )
    mock_container.get_rules.return_value = []
    mock_container.get.return_value = mock_use_case

    result = runner.invoke(main, ["audit", "scan", "--offline"], obj=mock_container)
    assert result.exit_code == 0
    mock_use_case.execute.assert_called_once()


def test_scan_offline_with_violations_reports_manifest():
    """Scan with violations and --manifest prints JSON and hits _report_findings_guided manifest branch."""
    from snowfort_audit.domain.rule_definitions import Severity, Violation

    runner = CliRunner()
    violations = [
        Violation("COST_001", "WH_X", "Auto-suspend high", Severity.MEDIUM),
    ]
    mock_rule = MagicMock()
    mock_rule.id = "COST_001"
    mock_rule.name = "Auto-suspend"
    mock_rule.severity.value = "MEDIUM"
    mock_rule.pillar = "Cost"
    mock_rule.rationale = "Rationale"
    mock_rule.remediation = "Fix it"

    mock_use_case = MagicMock()
    mock_use_case.execute.return_value = violations
    mock_container = MagicMock()
    mock_container.get.side_effect = lambda k: mock_use_case if k == "OfflineScanUseCase" else MagicMock()
    mock_container.get_rules.return_value = [mock_rule]

    result = runner.invoke(main, ["audit", "scan", "--offline", "--manifest", "--path", "."], obj=mock_container)
    assert result.exit_code == 1
    assert "rule_id" in result.output and "COST_001" in result.output


def test_scan_offline_with_violations_auto_flat_report():
    """Scan with violations and --auto hits _report_findings (flat table)."""
    from snowfort_audit.domain.rule_definitions import Severity, Violation

    runner = CliRunner()
    violations = [
        Violation("COST_001", "WH_X", "Auto-suspend high", Severity.MEDIUM),
    ]
    mock_rule = MagicMock()
    mock_rule.id = "COST_001"
    mock_rule.name = "Auto-suspend"
    mock_rule.severity.value = "MEDIUM"
    mock_rule.pillar = "Cost"
    mock_rule.rationale = "Rationale"
    mock_rule.remediation = "Fix it"

    mock_container = MagicMock()
    mock_use_case = MagicMock()
    mock_use_case.execute.return_value = violations
    mock_container.get.side_effect = lambda k: mock_use_case if k == "OfflineScanUseCase" else MagicMock()
    mock_container.get_rules.return_value = [mock_rule]

    result = runner.invoke(main, ["audit", "scan", "--offline", "--auto", "--path", "."], obj=mock_container)
    assert result.exit_code == 1  # violations -> exit 1
    assert "COST_001" in result.output
    assert "Score" in result.output or "Violations" in result.output


def test_scan_online_command_interactive_mock():
    runner = CliRunner()
    mock_use_case = MagicMock()

    def get_side_effect(key):
        if key == "OnlineScanUseCase":
            return mock_use_case
        if key == "TelemetryPort":
            return MagicMock()
        return MagicMock()

    mock_container = MagicMock()
    mock_container.get.side_effect = get_side_effect

    with (
        patch("snowfort_audit.interface.cli.scan.get_connection_options"),
        patch("rich.prompt.Prompt.ask") as mock_ask,
    ):
        mock_ask.side_effect = ["my_org-my_acc", "my_user", "AUDITOR", "externalbrowser"]
        result = runner.invoke(main, ["audit", "scan"], obj=mock_container)
    assert result.exit_code == 0
    mock_use_case.execute.assert_called_once()


# pylint: disable=fragile-test-mocks
def test_bootstrap_command():
    runner = CliRunner()
    mock_use_case = MagicMock()
    mock_gateway = MagicMock()
    mock_gateway.execute.return_value.fetchone.return_value = ["TEST_USER"]
    mock_container = MagicMock()
    mock_container.get.side_effect = lambda k: (
        mock_use_case
        if k == "BootstrapUseCase"
        else (
            (lambda opts: mock_gateway)
            if k == "SnowflakeGatewayFactory"
            else (Exception if k == "ConnectionErrorType" else MagicMock())
        )
    )
    with (
        patch("snowfort_audit.interface.cli.bootstrap.get_connection_options"),
        patch("rich.prompt.Prompt.ask") as mock_prompt_ask,
        patch("rich.prompt.Confirm.ask") as mock_confirm_ask,
    ):
        mock_prompt_ask.return_value = "COMPUTE_WH"
        mock_confirm_ask.return_value = True
        result = runner.invoke(main, ["audit", "bootstrap", "--role", "SYSADMIN"], obj=mock_container)
    assert result.exit_code == 0
    mock_use_case.execute.assert_called()


def test_audit_rules_list():
    """audit rules (no arg) lists rules in a table."""
    runner = CliRunner()
    mock_rule = MagicMock()
    mock_rule.id = "COST_001"
    mock_rule.name = "Auto-suspend"
    mock_rule.severity.value = "MEDIUM"
    mock_rule.pillar = "Cost"
    mock_rule.rationale = ""
    mock_rule.remediation = ""
    mock_rule.remediation_key = None
    mock_container = MagicMock()
    mock_container.get_rules.return_value = [mock_rule]

    result = runner.invoke(main, ["audit", "rules"], obj=mock_container)
    assert result.exit_code == 0
    assert "COST_001" in result.output
    assert "Auto-suspend" in result.output


def test_audit_rules_single():
    """audit rules COST_001 prints rule detail table."""
    runner = CliRunner()
    mock_rule = MagicMock()
    mock_rule.id = "COST_001"
    mock_rule.name = "Auto-suspend"
    mock_rule.severity.value = "MEDIUM"
    mock_rule.pillar = "Cost"
    mock_rule.rationale = "Rationale text"
    mock_rule.remediation = "Remediation text"
    mock_rule.remediation_key = None
    mock_container = MagicMock()
    mock_container.get_rules.return_value = [mock_rule]

    result = runner.invoke(main, ["audit", "rules", "COST_001"], obj=mock_container)
    assert result.exit_code == 0
    assert "COST_001" in result.output
    assert "Rationale text" in result.output


def test_audit_rules_unknown_exits_nonzero():
    """audit rules UNKNOWN_RULE prints error and exits 1."""
    runner = CliRunner()
    mock_container = MagicMock()
    mock_container.get_rules.return_value = []

    result = runner.invoke(main, ["audit", "rules", "UNKNOWN_RULE"], obj=mock_container)
    assert result.exit_code == 1
    assert "No rule found" in result.output


def test_audit_rules_fallback_when_get_rules_raises():
    """When container.get_rules() raises, fallback to get_all_rules and list rules."""
    runner = CliRunner()
    mock_rule = MagicMock()
    mock_rule.id = "COST_001"
    mock_rule.name = "X"
    mock_rule.severity.value = "MEDIUM"
    mock_rule.pillar = "Cost"
    mock_rule.rationale = ""
    mock_rule.remediation = ""
    mock_rule.remediation_key = None
    mock_evaluator = MagicMock()
    mock_telemetry = MagicMock()
    mock_container = MagicMock()
    mock_container.get_rules.side_effect = ValueError("not configured")
    mock_container.get.side_effect = lambda k: (
        mock_evaluator
        if k == "FinancialEvaluator"
        else (
            mock_telemetry
            if k == "TelemetryPort"
            else ((lambda *a, **kw: [mock_rule]) if k == "get_all_rules" else MagicMock())
        )
    )

    result = runner.invoke(main, ["audit", "rules"], obj=mock_container)
    assert result.exit_code == 0
    assert "COST_001" in result.output or "Rule ID" in result.output


def test_login_prints_exports():
    """snowfort login prints export lines when config has values (re-prompts with defaults)."""
    runner = CliRunner()
    mock_config = MagicMock()
    mock_config.get_env.side_effect = lambda k: {
        "SNOWFLAKE_ACCOUNT": "org-acc",
        "SNOWFLAKE_USER": "u1",
        "SNOWFLAKE_ROLE": "AUDITOR",
        "SNOWFLAKE_AUTHENTICATOR": "externalbrowser",
    }.get(k, None)
    mock_container = MagicMock()
    mock_container.get.side_effect = lambda k: mock_config if k == "ConfigurationProtocol" else MagicMock()
    with patch("snowfort_audit.interface.cli._ask") as mock_ask:
        mock_ask.side_effect = ["org-acc", "u1", "AUDITOR", "browser"]
        result = runner.invoke(main, ["login"], obj=mock_container)
    assert result.exit_code == 0
    assert mock_ask.call_count == 4
    assert "SNOWFLAKE_ACCOUNT" in result.output
    assert "org-acc" in result.output
    assert "externalbrowser" in result.output


def test_login_prompts_when_config_empty():
    """snowfort login uses _ask when config is empty and prints exports."""
    runner = CliRunner()
    mock_config = MagicMock()
    mock_config.get_env.return_value = None
    mock_container = MagicMock()
    mock_container.get.side_effect = lambda k: mock_config if k == "ConfigurationProtocol" else MagicMock()
    with patch("snowfort_audit.interface.cli._ask") as mock_ask:
        mock_ask.side_effect = ["my-org-acc", "myuser", "AUDITOR", "browser"]
        result = runner.invoke(main, ["login"], obj=mock_container)
    assert result.exit_code == 0
    assert mock_ask.call_count >= 4
    assert "SNOWFLAKE_ACCOUNT" in result.output
    assert "my-org-acc" in result.output


def test_audit_calculator_inputs():
    """audit calculator-inputs prints JSON from CalculatorInterrogator."""
    runner = CliRunner()
    mock_gw = MagicMock()
    mock_gw.get_cursor.return_value = MagicMock()
    mock_calc = MagicMock()
    mock_calc.get_inputs.return_value = {"warehouses": [], "storage_gb": 0}
    mock_container = MagicMock()

    def get_side_effect(k):
        if k == "SnowflakeGatewayFactory":
            return lambda opts: mock_gw
        if k == "ConnectionErrorType":
            return Exception
        if k == "CalculatorInterrogatorClass":
            return lambda cursor: mock_calc
        return MagicMock()

    mock_container.get.side_effect = get_side_effect
    with patch("snowfort_audit.interface.cli.get_connection_options"):
        result = runner.invoke(main, ["audit", "calculator-inputs"], obj=mock_container)
    assert result.exit_code == 0
    assert "warehouses" in result.output


def test_audit_demo_setup():
    """audit demo-setup runs with mocked connection and gateway."""
    runner = CliRunner()
    mock_gw = MagicMock()
    mock_gw.connect.return_value = None
    mock_gw.execute.return_value = MagicMock()
    mock_container = MagicMock()
    mock_container.get.side_effect = lambda k: (
        (lambda opts: mock_gw)
        if k == "SnowflakeGatewayFactory"
        else (Exception if k == "ConnectionErrorType" else MagicMock())
    )
    with patch("snowfort_audit.interface.cli.bootstrap.get_connection_options"):
        result = runner.invoke(main, ["audit", "demo-setup"], obj=mock_container)
    assert result.exit_code == 0
    assert "Well-Architected" in result.output or "snowfort" in result.output.lower()


def test_main_help():
    """main --help shows usage."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "audit" in result.output


def test_audit_help():
    """audit --help shows subcommands."""
    runner = CliRunner()
    result = runner.invoke(main, ["audit", "--help"])
    assert result.exit_code == 0
    assert "scan" in result.output
    assert "rules" in result.output


def test_audit_report_offline_writes_yaml(tmp_path):
    """audit show -o report.yaml --re-scan --offline runs offline scan and writes YAML report."""
    runner = CliRunner()
    out_file = tmp_path / "report.yaml"
    mock_use_case = MagicMock()
    mock_use_case.execute.return_value = []
    mock_rule = MagicMock()
    mock_rule.id = "COST_001"
    mock_rule.name = "Auto-Suspend"
    mock_rule.pillar = "Cost"
    mock_container = MagicMock()
    mock_container.get.side_effect = lambda k: (
        mock_use_case
        if k == "OfflineScanUseCase"
        else (
            (lambda proot: {"account_topology": "multi_env_single_account", "environments": ["DEV", "STG", "PRD"]})
            if k == "load_account_config"
            else MagicMock()
        )
    )
    mock_container.get_rules.return_value = [mock_rule]

    result = runner.invoke(
        main,
        ["audit", "show", "-o", str(out_file), "--re-scan", "--offline", "--path", str(tmp_path)],
        obj=mock_container,
    )
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "snowfort_audit_report" in content
    assert "summary" in content
    assert "findings" in content
