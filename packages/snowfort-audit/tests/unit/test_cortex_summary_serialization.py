"""Tests for F2: CortexSummary dataclass + structured synthesizer + YAML serialization."""

from __future__ import annotations

from unittest.mock import MagicMock

from snowfort_audit.domain.results import AuditResult, CortexSummary
from snowfort_audit.domain.rule_definitions import Severity, Violation
from snowfort_audit.infrastructure.cortex_synthesizer import (
    CortexSynthesizer,
    _parse_structured_response,
)
from snowfort_audit.interface.cli.report import build_yaml_report

# ---------------------------------------------------------------------------
# CortexSummary dataclass
# ---------------------------------------------------------------------------


class TestCortexSummary:
    def test_to_dict_full(self):
        s = CortexSummary(
            tl_dr="Account has critical ACCOUNTADMIN overexposure.",
            top_risks=["Admin role overuse", "No MFA"],
            quick_wins=["Enable MFA", "Reduce ACCOUNTADMIN grants"],
        )
        d = s.to_dict()
        assert d["tl_dr"] == "Account has critical ACCOUNTADMIN overexposure."
        assert d["top_risks"] == ["Admin role overuse", "No MFA"]
        assert d["quick_wins"] == ["Enable MFA", "Reduce ACCOUNTADMIN grants"]

    def test_to_dict_empty(self):
        d = CortexSummary().to_dict()
        assert d["tl_dr"] == ""
        assert d["top_risks"] == []
        assert d["quick_wins"] == []


# ---------------------------------------------------------------------------
# _parse_structured_response
# ---------------------------------------------------------------------------


_SAMPLE_RESPONSE = """TL_DR: The account has critical security gaps including unscoped admin roles.
TOP_RISKS:
- ACCOUNTADMIN granted to 7 users
- No network policy on service users
- Zombie credentials older than 90 days
QUICK_WINS:
- Revoke ACCOUNTADMIN from dormant accounts
- Enable MFA enforcement
"""


class TestParseStructuredResponse:
    def test_parses_full_response(self):
        s = _parse_structured_response(_SAMPLE_RESPONSE)
        assert "critical security gaps" in s.tl_dr
        assert len(s.top_risks) == 3
        assert "ACCOUNTADMIN granted" in s.top_risks[0]
        assert len(s.quick_wins) == 2

    def test_fallback_on_unstructured(self):
        s = _parse_structured_response("Something went wrong, here is some text.")
        assert s.tl_dr == "Something went wrong, here is some text."
        assert s.top_risks == []
        assert s.quick_wins == []

    def test_partial_response_no_quick_wins(self):
        partial = "TL_DR: Big risk.\nTOP_RISKS:\n- Risk A\n- Risk B\n"
        s = _parse_structured_response(partial)
        assert s.tl_dr == "Big risk."
        assert s.top_risks == ["Risk A", "Risk B"]
        assert s.quick_wins == []


# ---------------------------------------------------------------------------
# CortexSynthesizer.summarize_structured
# ---------------------------------------------------------------------------


def _make_violation(rule_id="SEC_001"):
    return Violation(rule_id=rule_id, resource_name="ADMIN", message="Test violation", severity=Severity.HIGH)


class TestCortexSynthesizerStructured:
    def test_empty_violations_returns_summary(self):
        syn = CortexSynthesizer(MagicMock())
        result = syn.summarize_structured([])
        assert "No violations" in result.tl_dr

    def test_summarize_delegates_to_structured(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [(_SAMPLE_RESPONSE,)]
        syn = CortexSynthesizer(cursor)
        text = syn.summarize([_make_violation()])
        assert "critical security gaps" in text

    def test_summarize_structured_returns_cortex_summary(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [(_SAMPLE_RESPONSE,)]
        syn = CortexSynthesizer(cursor)
        s = syn.summarize_structured([_make_violation()])
        assert isinstance(s, CortexSummary)
        assert len(s.top_risks) == 3

    def test_error_returns_graceful_summary(self):
        cursor = MagicMock()
        cursor.execute.side_effect = RuntimeError("network error")
        syn = CortexSynthesizer(cursor)
        s = syn.summarize_structured([_make_violation()])
        assert "unavailable" in s.tl_dr

    def test_empty_result_returns_fallback(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        syn = CortexSynthesizer(cursor)
        s = syn.summarize_structured([_make_violation()])
        assert "no result" in s.tl_dr.lower()


# ---------------------------------------------------------------------------
# AuditResult.cortex_summary field
# ---------------------------------------------------------------------------


class TestAuditResultCortexSummaryField:
    def test_default_is_none(self):
        result = AuditResult()
        assert result.cortex_summary is None

    def test_field_stored(self):
        summary = CortexSummary(tl_dr="All good.")
        result = AuditResult(cortex_summary=summary)
        assert result.cortex_summary is summary

    def test_from_violations_no_summary(self):
        result = AuditResult.from_violations([])
        assert result.cortex_summary is None


# ---------------------------------------------------------------------------
# YAML report includes cortex_summary block
# ---------------------------------------------------------------------------


class TestYAMLReportCortexSummary:
    def _make_result(self, with_summary=True):
        summary = (
            CortexSummary(
                tl_dr="Critical risk.",
                top_risks=["Risk A"],
                quick_wins=["Fix A"],
            )
            if with_summary
            else None
        )
        return AuditResult(cortex_summary=summary)

    def test_yaml_includes_cortex_summary_when_present(self, tmp_path):
        result = self._make_result(with_summary=True)
        report = build_yaml_report(result, [], tmp_path)
        data = report["snowfort_audit_report"]
        assert "cortex_summary" in data
        assert data["cortex_summary"]["tl_dr"] == "Critical risk."
        assert data["cortex_summary"]["top_risks"] == ["Risk A"]

    def test_yaml_omits_cortex_summary_when_absent(self, tmp_path):
        result = self._make_result(with_summary=False)
        report = build_yaml_report(result, [], tmp_path)
        data = report["snowfort_audit_report"]
        assert "cortex_summary" not in data
