"""Tests for perf rules, governance rules, and infrastructure."""

from unittest.mock import MagicMock

from snowfort_audit.domain.models import PricingConfig
from snowfort_audit.domain.rule_definitions import Severity, Violation
from snowfort_audit.domain.rules.governance import (
    AccountBudgetEnforcement,
    FutureGrantsAntiPatternCheck,
    ObjectDocumentationCheck,
    SensitiveDataClassificationCoverageCheck,
)
from snowfort_audit.domain.rules.perf import (
    ClusteringKeyQualityCheck,
    ClusterKeyValidationCheck,
    DynamicTableLagCheck,
    LocalSpillageCheck,
    PoorPartitionPruningDetectionCheck,
    QueryLatencySLOCheck,
    QueryQueuingDetectionCheck,
    RemoteSpillageCheck,
    WarehouseWorkloadIsolationCheck,
)
from snowfort_audit.infrastructure.calculator_interrogator import CalculatorInterrogator
from snowfort_audit.infrastructure.cortex_synthesizer import CortexSynthesizer
from snowfort_audit.infrastructure.pricing_repository import YamlPricingRepository

# --- Performance Rules ---


def test_cluster_key_no_key():
    r = ClusterKeyValidationCheck()
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "BIG_TBL", None)]
    v = r.check_online(c)
    assert len(v) == 1
    assert "missing" in v[0].message.lower()


def test_cluster_key_high_depth():
    r = ClusterKeyValidationCheck()
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "TBL", "LINEAR(col1)")]
    c.fetchone.return_value = (3.5,)
    v = r.check_online(c)
    assert len(v) == 1
    assert "depth" in v[0].message.lower()


def test_cluster_key_exc():
    r = ClusterKeyValidationCheck()
    c = MagicMock()
    c.execute.side_effect = RuntimeError("err")
    assert r.check_online(c) == []


def test_remote_spillage():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 10)]
    assert len(RemoteSpillageCheck().check_online(c)) == 1


def test_remote_spillage_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert RemoteSpillageCheck().check_online(c) == []


def test_local_spillage():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 5)]
    assert len(LocalSpillageCheck().check_online(c)) == 1


def test_local_spillage_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert LocalSpillageCheck().check_online(c) == []


def test_query_queuing():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 120.5)]
    assert len(QueryQueuingDetectionCheck().check_online(c)) == 1


def test_query_queuing_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert QueryQueuingDetectionCheck().check_online(c) == []


def test_dynamic_table_lag():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "DT", 5)]
    assert len(DynamicTableLagCheck().check_online(c)) == 1


def test_dynamic_table_lag_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert DynamicTableLagCheck().check_online(c) == []


def test_clustering_key_quality_many_expressions():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "TBL", "LINEAR(a,b,c,d,e)")]
    v = ClusteringKeyQualityCheck().check_online(c)
    assert len(v) == 1
    assert "more than 4" in v[0].message


def test_clustering_key_quality_mod():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "TBL", "LINEAR(MOD(id, 10))")]
    v = ClusteringKeyQualityCheck().check_online(c)
    assert len(v) == 1
    assert "MOD" in v[0].message


def test_clustering_key_quality_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert ClusteringKeyQualityCheck().check_online(c) == []


def test_workload_isolation():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 100, 50)]
    assert len(WarehouseWorkloadIsolationCheck().check_online(c)) == 1


def test_workload_isolation_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert WarehouseWorkloadIsolationCheck().check_online(c) == []


def test_poor_pruning():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "TBL", 1000, 50, 1050)]
    assert len(PoorPartitionPruningDetectionCheck().check_online(c)) == 1


def test_poor_pruning_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert PoorPartitionPruningDetectionCheck().check_online(c) == []


def test_query_latency_slo():
    c = MagicMock()
    c.fetchall.return_value = [("WH", "SELECT", 0.5, 5.0, 45.0, 100)]
    assert len(QueryLatencySLOCheck().check_online(c)) == 1


def test_query_latency_slo_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert QueryLatencySLOCheck().check_online(c) == []


# --- Governance Rules ---


def test_future_grants():
    c = MagicMock()
    c.fetchall.return_value = [("LOADER_ROLE", "FUTURE_TABLES")]
    assert len(FutureGrantsAntiPatternCheck().check_online(c)) == 1


def test_future_grants_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert FutureGrantsAntiPatternCheck().check_online(c) == []


def test_object_documentation():
    c = MagicMock()
    c.fetchall.return_value = [("PUBLIC", "TBL")]
    assert len(ObjectDocumentationCheck().check_online(c)) == 1


def test_object_documentation_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert ObjectDocumentationCheck().check_online(c) == []


def test_budget_no_budgets():
    c = MagicMock()
    c.fetchone.return_value = (0,)
    assert len(AccountBudgetEnforcement().check_online(c)) == 1


def test_budget_has_budgets():
    c = MagicMock()
    c.fetchone.return_value = (3,)
    assert AccountBudgetEnforcement().check_online(c) == []


def test_budget_both_fail():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("err")
    v = AccountBudgetEnforcement().check_online(c)
    assert len(v) == 1


def test_sensitive_data_classification():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "TBL", "EMAIL")]
    assert len(SensitiveDataClassificationCoverageCheck().check_online(c)) == 1


def test_sensitive_data_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert SensitiveDataClassificationCoverageCheck().check_online(c) == []


# --- Infrastructure ---


def test_cortex_empty():
    c = MagicMock()
    assert CortexSynthesizer(c).summarize([]) == "No content to summarize."


def test_cortex_summarize():
    c = MagicMock()
    c.fetchall.return_value = [("Executive summary here",)]
    v = [Violation("X", "R", "msg", Severity.HIGH)]
    result = CortexSynthesizer(c).summarize(v)
    assert result == "Executive summary here"


def test_cortex_exception():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("cortex fail")
    v = [Violation("X", "R", "msg", Severity.HIGH)]
    result = CortexSynthesizer(c).summarize(v)
    assert "Error" in result or "cortex" in result.lower()


def test_calculator_get_inputs():
    c = MagicMock()
    c.fetchall.side_effect = [
        [(1.5,)],  # storage
        [("SMALL", 100.0)],  # compute
        [(50.0,)],  # transfer
    ]
    result = CalculatorInterrogator(c).get_inputs()
    assert "storage" in result
    assert "compute" in result
    assert "data_transfer" in result


def test_calculator_storage_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    result = CalculatorInterrogator(c)._get_storage()
    assert result == {"average_tb": 0.0}


def test_calculator_compute_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert CalculatorInterrogator(c)._get_compute() == {}


def test_calculator_transfer_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert CalculatorInterrogator(c)._get_data_transfer() == {"transfer_gb": 0.0}


def test_pricing_repo_valid():
    fs = MagicMock()
    fs.exists.return_value = True
    fs.read_text.return_value = "currency: EUR\ncompute:\n  SMALL: 2.0\n"
    repo = YamlPricingRepository(fs, "/pricing.yml")
    config = repo.get_pricing_config()
    assert config.currency == "EUR"


def test_pricing_repo_not_found():
    fs = MagicMock()
    fs.exists.return_value = False
    config = YamlPricingRepository(fs, "/missing.yml").get_pricing_config()
    assert isinstance(config, PricingConfig)


def test_pricing_repo_invalid():
    fs = MagicMock()
    fs.exists.return_value = True
    fs.read_text.return_value = "invalid: [yaml"
    config = YamlPricingRepository(fs, "/bad.yml").get_pricing_config()
    assert isinstance(config, PricingConfig)
