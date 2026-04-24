"""Comprehensive tests for interface/cli.py: report functions, show command, rules detail, guided report."""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from snowfort_audit.domain.conventions import SnowfortConventions
from snowfort_audit.domain.results import AuditResult
from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation
from snowfort_audit.interface.cli import _sh_escape, _warn_externalbrowser_headless, main
from snowfort_audit.interface.cli.report import (
    build_yaml_report,
    conventions_for_pillar,
    pillar_style,
    report_findings,
    report_findings_guided,
    report_pillar_detail,
    report_rule_detail,
    severity_border_style,
    show_filtered_table,
    write_audit_cache,
)

# --- helper function tests ---


def test_severity_border_style_all():
    assert severity_border_style(Severity.CRITICAL) == "red"
    assert severity_border_style(Severity.HIGH) == "red"
    assert severity_border_style(Severity.MEDIUM) == "yellow"
    assert severity_border_style(Severity.LOW) == "yellow"


def test_pillar_style_known():
    r = pillar_style("Security")
    assert "Security" in r


def test_pillar_style_unknown():
    r = pillar_style("NonExistent")
    assert "NonExistent" in r


def test_conventions_for_performance():
    conv = SnowfortConventions()
    lines = conventions_for_pillar("Performance", conv)
    keys = [k for k, _ in lines]
    assert "warehouse.auto_suspend_seconds" in keys


def test_conventions_for_reliability():
    conv = SnowfortConventions()
    lines = conventions_for_pillar("Reliability", conv)
    assert len(lines) > 0


def test_sh_escape_backslash():
    r = _sh_escape("a\\b")
    assert "a" in r


def test_write_audit_cache_with_violations(tmp_path):
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    result = AuditResult.from_violations([v])
    write_audit_cache(tmp_path, result, "target")
    data = json.loads((tmp_path / ".snowfort" / "audit_results.json").read_text())
    assert data["target_name"] == "target"
    assert len(data["violations"]) == 1
    assert data["violations"][0]["severity"] == "CRITICAL"


# ── AC-5: manifest/cache/YAML enrichment for Cortex consumption ──────────────


def test_write_audit_cache_includes_enrichment(tmp_path):
    """AC-5: cache violations include category, context, blast_radius, quick_win."""
    r = Rule("SEC_001", "Admin Exposure", Severity.CRITICAL, rationale="Admins are high-value targets.")
    v = r.violation("Account", "msg")
    result = AuditResult.from_violations([v])
    write_audit_cache(tmp_path, result, "target", rules=[r])
    data = json.loads((tmp_path / ".snowfort" / "audit_results.json").read_text())
    violation = data["violations"][0]
    assert violation["category"] == "ACTIONABLE"
    assert "admins are high-value" in violation["context"].lower()
    assert "blast_radius" in violation
    assert "quick_win" in violation
    assert "remediation_key" in violation


def test_write_audit_cache_includes_adjusted_scorecard(tmp_path):
    """AC-5: cache scorecard includes adjusted_score/grade/counts."""
    r = Rule("SEC_001", "X", Severity.CRITICAL)
    result = AuditResult.from_violations([r.violation("A", "m")])
    write_audit_cache(tmp_path, result, "t", rules=[r])
    sc = json.loads((tmp_path / ".snowfort" / "audit_results.json").read_text())["scorecard"]
    assert "adjusted_score" in sc
    assert "adjusted_grade" in sc
    assert "actionable_count" in sc
    assert "expected_count" in sc
    assert "informational_count" in sc


def test_write_audit_cache_backward_compatible_without_rules(tmp_path):
    """AC-5/AC-6: cache still works if rules=None; context defaults to empty string."""
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL)
    result = AuditResult.from_violations([v])
    write_audit_cache(tmp_path, result, "target")  # no rules kwarg
    data = json.loads((tmp_path / ".snowfort" / "audit_results.json").read_text())
    violation = data["violations"][0]
    assert violation["context"] == ""
    assert violation["category"] == "ACTIONABLE"


def test_build_yaml_report_includes_adjusted_and_enrichment(tmp_path):
    """AC-5: YAML summary includes adjusted_score/grade; findings include enrichment."""
    r = Rule("SEC_001", "Admin Exposure", Severity.CRITICAL, rationale="Admins are high-value.")
    v = r.violation("Account", "msg")
    result = AuditResult.from_violations([v])
    y = build_yaml_report(result, [r], tmp_path)
    summary = y["snowfort_audit_report"]["summary"]
    assert "adjusted_score" in summary
    assert "adjusted_grade" in summary
    finding = y["snowfort_audit_report"]["findings"][0]
    assert "category" in finding
    assert "context" in finding and "admins are high-value" in finding["context"].lower()
    assert "blast_radius" in finding
    assert "quick_win" in finding


# --- _report_findings ---


def test_report_findings_manifest(capsys):
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    tel = MagicMock()
    report_findings([v], [], tel, manifest=True, target_name="T")
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert len(parsed) == 1


def test_report_findings_manifest_with_meta(capsys):
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    tel = MagicMock()
    report_findings([v], [], tel, manifest=True, target_name="T", audit_metadata={"billing_model": "on_demand"})
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "violations" in parsed
    assert "metadata" in parsed


def test_report_findings_no_violations():
    tel = MagicMock()
    report_findings([], [], tel, manifest=False, target_name="T")


def test_report_findings_with_violations():
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    tel = MagicMock()
    report_findings([v], [], tel, manifest=False, target_name="T", verbose=True)


def test_report_findings_billing_model():
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    tel = MagicMock()
    result = AuditResult.from_violations([v], metadata={"billing_model": "reserved"})
    report_findings(
        [v], [], tel, manifest=False, target_name="T", audit_metadata={"billing_model": "reserved"}, result=result
    )


# --- _report_findings_guided ---


def test_report_findings_guided_manifest(capsys):
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    tel = MagicMock()
    report_findings_guided([v], [], tel, manifest=True)
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert isinstance(parsed, list)


def test_report_findings_guided_no_violations():
    tel = MagicMock()
    report_findings_guided([], [], tel, manifest=False)


def test_report_findings_guided_with_violations():
    v1 = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    v2 = Violation("COST_001", "WH", "msg2", Severity.MEDIUM, pillar="Cost")
    rules = [
        Rule("SEC_001", "Admin Exposure", Severity.CRITICAL),
        Rule("COST_001", "Auto-Suspend", Severity.MEDIUM),
    ]
    tel = MagicMock()
    report_findings_guided([v1, v2], rules, tel, manifest=False)


def test_report_findings_guided_billing():
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    rules = [Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)]
    tel = MagicMock()
    result = AuditResult.from_violations([v], metadata={"billing_model": "on_demand"})
    report_findings_guided(
        [v], rules, tel, manifest=False, audit_metadata={"billing_model": "on_demand"}, result=result
    )


# --- _report_pillar_detail ---


def test_report_pillar_detail_unknown_pillar():
    report_pillar_detail([], [], "Nonexistent")


def test_report_pillar_detail_no_violations():
    r = Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)
    report_pillar_detail([], [r], "Security")


def test_report_pillar_detail_with_violations():
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    r = Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)
    report_pillar_detail([v], [r], "Security")


# --- _report_rule_detail ---


def test_report_rule_detail_not_found():
    report_rule_detail([], [], "FAKE_001")


def test_report_rule_detail_no_violations():
    r = Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)
    report_rule_detail([], [r], "SEC_001")


def test_report_rule_detail_with_violations():
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    r = Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)
    report_rule_detail([v], [r], "SEC_001")


# --- _show_filtered_table ---


def test_show_filtered_table_empty():
    show_filtered_table([], "target", "2024-01-01")


def test_show_filtered_table_with_items():
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    show_filtered_table([v], "target", "2024-01-01")


# --- _build_yaml_report ---


def test_build_yaml_report(tmp_path):
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    r = Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)
    result = AuditResult.from_violations([v], metadata={"account_id": "ACC123"})
    report = build_yaml_report(result, [r], tmp_path)
    assert "snowfort_audit_report" in report
    assert report["snowfort_audit_report"]["summary"]["score"] == result.scorecard.compliance_score
    assert len(report["snowfort_audit_report"]["findings"]) == 1


# --- _warn_externalbrowser_headless ---


def test_warn_headless_not_externalbrowser():
    opts = MagicMock()
    opts.authenticator = "username_password_mfa"
    tel = MagicMock()
    _warn_externalbrowser_headless(opts, tel)
    tel.warning.assert_not_called()


def test_warn_headless_with_display():
    opts = MagicMock()
    opts.authenticator = "externalbrowser"
    tel = MagicMock()
    with patch.dict("os.environ", {"DISPLAY": ":0"}):
        _warn_externalbrowser_headless(opts, tel)
    tel.warning.assert_not_called()


def test_warn_headless_no_display():
    opts = MagicMock()
    opts.authenticator = "externalbrowser"
    tel = MagicMock()
    with patch.dict("os.environ", {}, clear=True):
        _warn_externalbrowser_headless(opts, tel)
    tel.warning.assert_called_once()


# --- CLI command tests ---


def test_main_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0


def test_audit_no_subcommand():
    runner = CliRunner()
    m = MagicMock()
    m.get.return_value = MagicMock()
    result = runner.invoke(main, ["audit"], obj=m)
    assert result.exit_code == 0


def test_scan_offline_with_violations():
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    mock_c = MagicMock()
    mock_c.get.side_effect = lambda key: (
        MagicMock(execute=MagicMock(return_value=[v])) if key == "OfflineScanUseCase" else MagicMock()
    )
    mock_c.get_rules.return_value = [Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)]
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["audit", "scan", "--offline", "--path", ".", "--auto"], obj=mock_c)
    assert result.exit_code == 1


def test_scan_offline_manifest():
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    mock_c = MagicMock()
    mock_c.get.side_effect = lambda key: (
        MagicMock(execute=MagicMock(return_value=[v])) if key == "OfflineScanUseCase" else MagicMock()
    )
    mock_c.get_rules.return_value = [Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)]
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["audit", "scan", "--offline", "--path", ".", "--manifest", "--auto"], obj=mock_c)
    assert "SEC_001" in result.output


def test_scan_offline_with_rule_filter():
    mock_c = MagicMock()
    mock_c.get.side_effect = lambda key: (
        MagicMock(execute=MagicMock(return_value=[])) if key == "OfflineScanUseCase" else MagicMock()
    )
    mock_c.get_rules.return_value = []
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            ["audit", "scan", "--offline", "--path", ".", "--rule", "SEC_001", "--auto"],
            obj=mock_c,
        )
    assert result.exit_code == 0


def test_rules_with_id():
    runner = CliRunner()
    m = MagicMock()
    m.get_rules.return_value = [Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)]
    m.get.return_value = MagicMock()
    result = runner.invoke(main, ["audit", "rules", "SEC_001"], obj=m)
    assert result.exit_code == 0
    assert "Admin Exposure" in result.output


def test_rules_with_unknown_id():
    runner = CliRunner()
    m = MagicMock()
    m.get_rules.return_value = []
    m.get.return_value = MagicMock()
    result = runner.invoke(main, ["audit", "rules", "FAKE_999"], obj=m)
    assert result.exit_code == 1


def test_show_no_cache():
    runner = CliRunner()
    m = MagicMock()
    m.get.return_value = MagicMock()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["audit", "show", "--path", "."], obj=m)
    assert result.exit_code == 1


def test_show_with_cache(tmp_path):
    cache_dir = tmp_path / ".snowfort"
    cache_dir.mkdir()
    Violation("SEC_001", "Account", "msg", Severity.CRITICAL, pillar="Security")
    payload = {
        "target_name": "T",
        "timestamp_utc": "2024-01-01T00:00:00",
        "metadata": {},
        "scorecard": {
            "compliance_score": 80,
            "grade": "B",
            "total_violations": 1,
            "critical_count": 1,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "pillar_scores": {"Security": 60},
            "pillar_grades": {"Security": "D"},
        },
        "violations": [
            {
                "rule_id": "SEC_001",
                "resource_name": "Account",
                "message": "msg",
                "severity": "CRITICAL",
                "pillar": "Security",
            }
        ],
    }
    (cache_dir / "audit_results.json").write_text(json.dumps(payload))
    runner = CliRunner()
    m = MagicMock()
    m.get.side_effect = lambda k: (
        (lambda *a, **kw: [Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)])
        if k == "get_all_rules"
        else MagicMock()
    )
    result = runner.invoke(main, ["audit", "show", "--path", str(tmp_path)], obj=m)
    assert result.exit_code == 0


def test_show_count_only(tmp_path):
    cache_dir = tmp_path / ".snowfort"
    cache_dir.mkdir()
    payload = {
        "target_name": "T",
        "timestamp_utc": "2024-01-01T00:00:00",
        "metadata": {},
        "scorecard": {},
        "violations": [
            {"rule_id": "SEC_001", "resource_name": "A", "message": "m", "severity": "CRITICAL", "pillar": "Security"}
        ],
    }
    (cache_dir / "audit_results.json").write_text(json.dumps(payload))
    runner = CliRunner()
    m = MagicMock()
    m.get.side_effect = lambda k: (lambda *a, **kw: []) if k == "get_all_rules" else MagicMock()
    result = runner.invoke(main, ["audit", "show", "--path", str(tmp_path), "--count-only"], obj=m)
    assert result.exit_code == 0
    assert "1" in result.output


def test_show_severity_filter(tmp_path):
    cache_dir = tmp_path / ".snowfort"
    cache_dir.mkdir()
    payload = {
        "target_name": "T",
        "timestamp_utc": "2024-01-01",
        "metadata": {},
        "scorecard": {},
        "violations": [
            {"rule_id": "SEC_001", "resource_name": "A", "message": "m", "severity": "CRITICAL", "pillar": "Security"},
            {"rule_id": "COST_001", "resource_name": "B", "message": "m2", "severity": "LOW", "pillar": "Cost"},
        ],
    }
    (cache_dir / "audit_results.json").write_text(json.dumps(payload))
    runner = CliRunner()
    m = MagicMock()
    m.get.side_effect = lambda k: (lambda *a, **kw: []) if k == "get_all_rules" else MagicMock()
    result = runner.invoke(
        main,
        ["audit", "show", "--path", str(tmp_path), "--severity", "CRITICAL", "--count-only"],
        obj=m,
    )
    assert "1" in result.output
