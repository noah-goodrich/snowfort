"""Tests for domain/rules/op_excellence.py."""

from unittest.mock import MagicMock

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
    assert ResourceMonitorCheck().check_online(c) == []


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
    assert ObjectCommentCheck().check_online(c) == []


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
    assert MandatoryTaggingCheck().check_online(c) == []


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
    assert AlertConfigurationCheck().check_online(c) == []


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
    assert NotificationIntegrationCheck().check_online(c) == []


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
    assert ObservabilityInfrastructureCheck().check_online(c) == []


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
    assert IaCDriftReadinessCheck().check_online(c) == []


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
    assert EventTableConfigurationCheck().check_online(c) == []


def test_alert_execution_failures():
    c = MagicMock()
    c.fetchall.return_value = [("my_alert", "DB", "SCH", 3, 10)]
    v = AlertExecutionReliabilityCheck().check_online(c)
    assert len(v) == 1


def test_alert_execution_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert AlertExecutionReliabilityCheck().check_online(c) == []


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
    assert DataMetricFunctionsCoverageCheck().check_online(c) == []
