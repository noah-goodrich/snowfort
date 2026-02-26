from unittest.mock import MagicMock

from snowfort_audit.domain.rules.perf import (
    ClusteringKeyQualityCheck,
    ClusterKeyValidationCheck,
    DynamicTableLagCheck,
    QueryQueuingDetectionCheck,
)


def test_cluster_key_validation_check_no_clustering():
    rule = ClusterKeyValidationCheck()
    mock_cursor = MagicMock()

    # Mock INFORMATION_SCHEMA.TABLES response
    # TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, CLUSTERING_KEY
    mock_cursor.fetchall.return_value = [("DB", "PUBLIC", "LARGE_TABLE", None)]

    violations = rule.check_online(mock_cursor)
    assert len(violations) == 1
    assert violations[0].resource_name == '"DB"."PUBLIC"."LARGE_TABLE"'
    assert "missing a defined clustering key" in violations[0].message


def test_cluster_key_validation_check_high_depth():
    rule = ClusterKeyValidationCheck()
    mock_cursor = MagicMock()

    # Mock large table with clustering key
    mock_cursor.fetchall.return_value = [("DB", "PUBLIC", "CLUSTERED_TABLE", "LINEAR(COL1)")]

    # Mock SYSTEM$CLUSTERING_DEPTH response
    mock_cursor.fetchone.return_value = (5.5,)

    violations = rule.check_online(mock_cursor)
    assert len(violations) == 1
    assert "high clustering depth: 5.50" in violations[0].message


def test_cluster_key_validation_check_good_table():
    rule = ClusterKeyValidationCheck()
    mock_cursor = MagicMock()

    # Mock large table with good clustering
    mock_cursor.fetchall.return_value = [("DB", "PUBLIC", "GOOD_TABLE", "LINEAR(COL1)")]

    # Mock SYSTEM$CLUSTERING_DEPTH response
    mock_cursor.fetchone.return_value = (1.2,)

    violations = rule.check_online(mock_cursor)
    assert len(violations) == 0


def test_cluster_key_validation_check_error_handling():
    telemetry = MagicMock()
    rule = ClusterKeyValidationCheck(telemetry=telemetry)
    mock_cursor = MagicMock()

    # Query fails
    mock_cursor.execute.side_effect = Exception("Connection lost")

    violations = rule.check_online(mock_cursor)
    assert violations == []
    telemetry.error.assert_called_once()


def test_cluster_key_validation_depth_fetch_error():
    telemetry = MagicMock()
    rule = ClusterKeyValidationCheck(telemetry=telemetry)
    mock_cursor = MagicMock()

    # 1. First query (TABLES) succeeds
    mock_cursor.fetchall.return_value = [("DB", "PUBLIC", "PROBLEM_TABLE", "LINEAR(COL1)")]

    # 2. Second query (DEPTH) fails
    mock_cursor.execute.side_effect = [None, Exception("Depth fetch error")]

    violations = rule.check_online(mock_cursor)
    # Should skip the table but not crash the whole check
    assert violations == []
    telemetry.debug.assert_called_once()


def test_query_queuing_detection_check():
    rule = QueryQueuingDetectionCheck()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("HEAVY_WH", 120.5)]
    violations = rule.check_online(mock_cursor)
    assert len(violations) == 1
    assert violations[0].resource_name == "HEAVY_WH"
    assert "queuing" in violations[0].message.lower()


def test_dynamic_table_lag_check():
    rule = DynamicTableLagCheck()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("DB", "SCH", "DT1", 3)]
    violations = rule.check_online(mock_cursor)
    assert len(violations) == 1
    assert "DB.SCH.DT1" in violations[0].resource_name
    assert "TARGET_LAG" in violations[0].message


def test_clustering_key_quality_check_many_expressions():
    rule = ClusteringKeyQualityCheck()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("D", "S", "T", "A,B,C,D,E,F")]
    violations = rule.check_online(mock_cursor)
    assert len(violations) == 1
    assert "more than 4 expressions" in violations[0].message


def test_clustering_key_quality_check_mod_antipattern():
    rule = ClusteringKeyQualityCheck()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("D", "S", "T", "LINEAR(MOD(id, 10))")]
    violations = rule.check_online(mock_cursor)
    assert len(violations) == 1
    assert "MOD()" in violations[0].message


def test_clustering_key_quality_check_pass():
    rule = ClusteringKeyQualityCheck()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("D", "S", "T", "LINEAR(date_col)")]
    violations = rule.check_online(mock_cursor)
    assert len(violations) == 0
