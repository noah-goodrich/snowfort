"""Tests for reliability rules."""

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.reliability import (
    AdequateTimeTravelRetentionCheck,
    FailedTaskDetectionCheck,
    FailoverGroupCompletenessCheck,
    PipelineObjectReplicationCheck,
    ReplicationCheck,
    ReplicationLagMonitoringCheck,
    RetentionSafetyCheck,
    SchemaEvolutionCheck,
)


def test_replication_gap():
    c = MagicMock()
    c.fetchall.side_effect = [
        [("PRD_GOLD", "other")],
        [],
    ]
    c.description = [("name",), ("other",)]
    v = ReplicationCheck().check_online(c)
    assert len(v) == 1
    assert "PRD_GOLD" in v[0].resource_name


def test_replication_no_prd():
    c = MagicMock()
    c.fetchall.return_value = [("DEV_BRONZE",)]
    c.description = [("name",)]
    assert ReplicationCheck().check_online(c) == []


def test_replication_replicated():
    c = MagicMock()
    c.fetchall.side_effect = [
        [("PRD_GOLD",)],
        [("x", "PRD_GOLD")],
    ]
    c.description = [("name",)]
    assert ReplicationCheck().check_online(c) == []


def test_replication_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        ReplicationCheck().check_online(c)


def test_retention_zero():
    c = MagicMock()
    c.fetchall.return_value = [("PRD_GOLD", "PUBLIC", "TBL")]
    assert len(RetentionSafetyCheck().check_online(c)) == 1


def test_retention_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        RetentionSafetyCheck().check_online(c)


def test_adequate_retention():
    c = MagicMock()
    c.fetchall.return_value = [("PRD_GOLD", "PUBLIC", "TBL")]
    assert len(AdequateTimeTravelRetentionCheck().check_online(c)) == 1


def test_adequate_retention_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        AdequateTimeTravelRetentionCheck().check_online(c)


def test_schema_evolution_static():
    r = SchemaEvolutionCheck()
    v = r.check({"type": "TABLE", "enable_schema_evolution": True}, "TBL")
    assert len(v) == 1


def test_schema_evolution_static_off():
    r = SchemaEvolutionCheck()
    assert r.check({"type": "TABLE", "enable_schema_evolution": False}, "TBL") == []


def test_schema_evolution_non_table():
    assert SchemaEvolutionCheck().check({"type": "DATABASE"}, "DB") == []


def test_schema_evolution_online():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "TBL")]
    assert len(SchemaEvolutionCheck().check_online(c)) == 1


def test_schema_evolution_online_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        SchemaEvolutionCheck().check_online(c)


def test_failover_group_missing_objects():
    c = MagicMock()
    c.fetchall.return_value = [("FG1", "DATABASES")]
    c.description = [("name",), ("object_types",)]
    v = FailoverGroupCompletenessCheck().check_online(c)
    assert len(v) == 1


def test_failover_group_complete():
    c = MagicMock()
    c.fetchall.return_value = [("FG1", "DATABASES, ROLES, USERS")]
    c.description = [("name",), ("object_types",)]
    assert FailoverGroupCompletenessCheck().check_online(c) == []


def test_failover_group_none():
    c = MagicMock()
    c.fetchall.return_value = []
    c.description = [("name",), ("object_types",)]
    assert FailoverGroupCompletenessCheck().check_online(c) == []


def test_failover_group_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        FailoverGroupCompletenessCheck().check_online(c)


def test_replication_lag_high():
    c = MagicMock()
    c.fetchall.return_value = [("GRP1", "2024-01-01T00:00:00", 120)]
    v = ReplicationLagMonitoringCheck().check_online(c)
    assert len(v) == 1
    assert "120" in v[0].message


def test_replication_lag_none():
    c = MagicMock()
    c.fetchall.return_value = []
    assert ReplicationLagMonitoringCheck().check_online(c) == []


def test_replication_lag_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        ReplicationLagMonitoringCheck().check_online(c)


def test_failed_task():
    c = MagicMock()
    c.fetchall.return_value = [("TASK1", "DB", "SCH", 5)]
    assert len(FailedTaskDetectionCheck().check_online(c)) == 1


def test_failed_task_none():
    c = MagicMock()
    c.fetchall.return_value = []
    assert FailedTaskDetectionCheck().check_online(c) == []


def test_failed_task_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        FailedTaskDetectionCheck().check_online(c)


def test_pipeline_replication():
    c = MagicMock()
    c.fetchall.return_value = [("PRD_DB",)]
    v = PipelineObjectReplicationCheck().check_online(c)
    assert len(v) == 1
    assert "PRD_DB" in v[0].resource_name


def test_pipeline_replication_empty():
    c = MagicMock()
    c.fetchall.return_value = []
    assert PipelineObjectReplicationCheck().check_online(c) == []


def test_pipeline_replication_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        PipelineObjectReplicationCheck().check_online(c)


def test_pipeline_replication_dedup():
    c = MagicMock()
    c.fetchall.return_value = [("PRD_DB",), ("PRD_DB",)]
    v = PipelineObjectReplicationCheck().check_online(c)
    assert len(v) == 1
