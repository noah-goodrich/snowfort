"""Tests for domain/rules/op_excellence.py."""

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.op_excellence import (
    AlertConfigurationCheck,
    AlertExecutionReliabilityCheck,
    DataMetricFunctionsCoverageCheck,
    EventTableConfigurationCheck,
    IaCDriftReadinessCheck,
    MandatoryTaggingCheck,
    NotificationIntegrationCheck,
    ObjectCommentCheck,
    ObservabilityInfrastructureCheck,
    ResourceMonitorCheck,
)


def test_resource_monitor_no_monitors():
    c = MagicMock()
    c.fetchall.side_effect = [[], []]
    v = ResourceMonitorCheck().check_online(c)
    assert any("No Resource Monitors" in x.message for x in v)


def test_resource_monitor_wh_no_monitor():
    c = MagicMock()
    c.fetchall.side_effect = [
        [("mon1",)],
        [("MY_WH",) + ("",) * 15 + ("null",)],
    ]
    v = ResourceMonitorCheck().check_online(c)
    assert len(v) == 1


def test_resource_monitor_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        ResourceMonitorCheck().check_online(c)


def test_object_comment_missing():
    c = MagicMock()
    c.fetchall.return_value = [
        ("created",) + ("MY_DB",) + ("",) * 7 + ("",),
    ]
    v = ObjectCommentCheck().check_online(c)
    assert len(v) == 1
    assert "missing" in v[0].message.lower()


def test_object_comment_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        ObjectCommentCheck().check_online(c)


def test_mandatory_tagging_no_tags():
    c = MagicMock()
    c.fetchall.side_effect = [
        [("MY_WH",)],
        [("created", "MY_DB")],
        [],
    ]
    v = MandatoryTaggingCheck().check_online(c)
    assert len(v) >= 1


def test_mandatory_tagging_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        MandatoryTaggingCheck().check_online(c)


def test_mandatory_tagging_severity_and_exclusion():
    """B4: severity is MEDIUM; COMPUTE_SERVICE_WH_* warehouses are excluded by default."""
    from snowfort_audit.domain.rule_definitions import Severity
    from snowfort_audit.domain.scan_context import ScanContext

    warehouses = (
        ("ANALYTICS_WH",),  # should be flagged (no tags)
        ("COMPUTE_SERVICE_WH_ETL",),  # excluded by default pattern
    )
    ctx = ScanContext()
    object.__setattr__(ctx, "warehouses", warehouses)
    object.__setattr__(ctx, "warehouses_cols", {"name": 0})
    object.__setattr__(ctx, "databases", ())
    object.__setattr__(ctx, "databases_cols", {})
    object.__setattr__(ctx, "tag_refs_index", {})  # no tags for anything

    c = MagicMock()
    rule = MandatoryTaggingCheck()
    violations = rule.check_online(c, scan_context=ctx)

    names = {v.resource_name for v in violations}
    assert any("ANALYTICS_WH" in n for n in names), f"Expected ANALYTICS_WH in violations, got {names}"
    assert not any("COMPUTE_SERVICE_WH" in n for n in names), "COMPUTE_SERVICE_WH_* should be excluded"

    for v in violations:
        assert v.severity == Severity.MEDIUM, f"Expected MEDIUM, got {v.severity}"


def test_alert_config_no_alerts():
    c = MagicMock()
    c.fetchall.return_value = []
    c.description = [("name",), ("state",)]
    v = AlertConfigurationCheck().check_online(c)
    assert len(v) == 1


def test_alert_config_not_resumed():
    c = MagicMock()
    c.fetchall.return_value = [("alert1", "suspended")]
    c.description = [("name",), ("state",)]
    v = AlertConfigurationCheck().check_online(c)
    assert len(v) == 1


def test_alert_config_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        AlertConfigurationCheck().check_online(c)


def test_notification_none():
    c = MagicMock()
    c.fetchall.return_value = []
    v = NotificationIntegrationCheck().check_online(c)
    assert len(v) == 1


def test_notification_exists():
    c = MagicMock()
    c.fetchall.return_value = [("notif1",)]
    assert NotificationIntegrationCheck().check_online(c) == []


def test_notification_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        NotificationIntegrationCheck().check_online(c)


def test_observability_none():
    c = MagicMock()
    c.fetchall.return_value = [("created", "ANALYTICS")]
    v = ObservabilityInfrastructureCheck().check_online(c)
    assert len(v) == 1


def test_observability_exists():
    c = MagicMock()
    c.fetchall.return_value = [("created", "MONITORING")]
    assert ObservabilityInfrastructureCheck().check_online(c) == []


def test_observability_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        ObservabilityInfrastructureCheck().check_online(c)


def test_iac_drift_no_tags():
    c = MagicMock()
    c.fetchall.side_effect = [
        [],
        [("MY_WH",)],
        [("created", "MY_DB")],
    ]
    v = IaCDriftReadinessCheck().check_online(c)
    assert len(v) == 1


def test_iac_drift_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        IaCDriftReadinessCheck().check_online(c)


def test_event_table_none():
    c = MagicMock()
    c.fetchall.return_value = []
    c.description = [("owner",)]
    v = EventTableConfigurationCheck().check_online(c)
    assert len(v) == 1


def test_event_table_exists():
    c = MagicMock()
    c.fetchall.return_value = [("MY_EVENT_TBL",)]
    c.description = [("owner",)]
    assert EventTableConfigurationCheck().check_online(c) == []


def test_event_table_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        EventTableConfigurationCheck().check_online(c)


def test_alert_execution_failures():
    c = MagicMock()
    c.fetchall.return_value = [("my_alert", "DB", "SCH", 3, 10)]
    v = AlertExecutionReliabilityCheck().check_online(c)
    assert len(v) == 1


def test_alert_execution_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        AlertExecutionReliabilityCheck().check_online(c)


def test_dmf_none():
    c = MagicMock()
    c.fetchone.return_value = (0,)
    v = DataMetricFunctionsCoverageCheck().check_online(c)
    assert len(v) == 1


def test_dmf_exists():
    c = MagicMock()
    c.fetchone.return_value = (5,)
    assert DataMetricFunctionsCoverageCheck().check_online(c) == []


def test_dmf_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        DataMetricFunctionsCoverageCheck().check_online(c)
