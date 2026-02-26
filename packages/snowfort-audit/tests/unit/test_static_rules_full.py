"""Tests for domain/rules/static.py."""

from unittest.mock import MagicMock

from snowfort_audit.domain.rules.static import (
    AntiPatternSQLDetectionCheck,
    DynamicTableComplexityCheck,
    HardcodedEnvCheck,
    MergePatternRecommendationCheck,
    NakedDropCheck,
    SecretExposureCheck,
    SelectStarCheck,
)


def test_hardcoded_env_dev():
    r = HardcodedEnvCheck()
    v = r.check_static("CREATE DATABASE MY_DEV", "file.sql")
    assert len(v) == 1


def test_hardcoded_env_prod():
    r = HardcodedEnvCheck()
    v = r.check_static("SELECT * FROM MY_PROD.TABLE", "file.sql")
    assert len(v) == 1


def test_hardcoded_env_clean():
    r = HardcodedEnvCheck()
    assert r.check_static("SELECT 1", "file.sql") == []


def test_naked_drop_table():
    r = NakedDropCheck()
    assert len(r.check_static("DROP TABLE MY_TABLE;", "file.sql")) == 1


def test_naked_drop_schema():
    r = NakedDropCheck()
    assert len(r.check_static("DROP SCHEMA MY_SCHEMA;", "file.sql")) == 1


def test_naked_drop_clean():
    r = NakedDropCheck()
    assert r.check_static("CREATE TABLE t (id INT);", "file.sql") == []


def test_secret_exposure():
    r = SecretExposureCheck()
    assert len(r.check_static('password: "my_secret"', "cfg.yaml")) == 1


def test_secret_exposure_clean():
    r = SecretExposureCheck()
    assert r.check_static("SELECT 1", "file.sql") == []


def test_merge_pattern_recommendation():
    r = MergePatternRecommendationCheck()
    sql = "INSERT INTO tbl SELECT * FROM src"
    v = r.check_static(sql, "load.sql")
    assert len(v) == 1


def test_merge_pattern_with_merge():
    r = MergePatternRecommendationCheck()
    sql = "MERGE INTO tbl USING src ON key = key"
    assert r.check_static(sql, "load.sql") == []


def test_merge_pattern_no_insert():
    r = MergePatternRecommendationCheck()
    assert r.check_static("SELECT 1", "f.sql") == []


def test_dt_complexity_many_joins():
    r = DynamicTableComplexityCheck()
    sql = "CREATE DYNAMIC TABLE dt AS SELECT * FROM a JOIN b ON 1=1 JOIN c ON 1=1 JOIN d ON 1=1 JOIN e ON 1=1 JOIN f ON 1=1 JOIN g ON 1=1"
    v = r.check_static(sql, "dt.sql")
    assert len(v) == 1
    assert "JOIN" in v[0].message


def test_dt_complexity_few_joins():
    r = DynamicTableComplexityCheck()
    sql = "CREATE DYNAMIC TABLE dt AS SELECT * FROM a JOIN b ON 1=1"
    assert r.check_static(sql, "dt.sql") == []


def test_dt_complexity_no_dt():
    r = DynamicTableComplexityCheck()
    assert r.check_static("SELECT 1", "f.sql") == []


def test_anti_pattern_order_by_no_limit():
    r = AntiPatternSQLDetectionCheck()
    v = r.check_static("SELECT * FROM t ORDER BY id", "q.sql")
    assert any("ORDER BY" in x.message for x in v)


def test_anti_pattern_or_in_join():
    r = AntiPatternSQLDetectionCheck()
    v = r.check_static("SELECT * FROM a JOIN b ON a.id = b.id OR a.name = b.name", "q.sql")
    assert any("OR" in x.message for x in v)


def test_anti_pattern_union():
    r = AntiPatternSQLDetectionCheck()
    v = r.check_static("SELECT 1 UNION SELECT 2", "q.sql")
    assert any("UNION" in x.message for x in v)


def test_anti_pattern_clean():
    r = AntiPatternSQLDetectionCheck()
    assert r.check_static("SELECT 1", "f.sql") == []


def test_select_star_sql():
    validator = MagicMock()
    mock_v = MagicMock()
    mock_v.code = "AM04"
    mock_v.line = 1
    mock_v.description = "Wildcard"
    mock_v.matches.return_value = True
    validator.validate.return_value = [mock_v]
    r = SelectStarCheck(validator)
    v = r.check_static("SELECT * FROM t", "q.sql")
    assert len(v) == 1


def test_select_star_python():
    validator = MagicMock()
    mock_v = MagicMock()
    mock_v.code = "AM04"
    mock_v.line = 1
    mock_v.description = "Wildcard"
    mock_v.matches.return_value = True
    validator.validate.return_value = [mock_v]
    r = SelectStarCheck(validator)
    py_code = 'query = "SELECT * FROM t"'
    v = r.check_static(py_code, "load.py")
    assert len(v) == 1


def test_select_star_clean():
    validator = MagicMock()
    validator.validate.return_value = []
    r = SelectStarCheck(validator)
    assert r.check_static("SELECT id FROM t", "q.sql") == []


def test_select_star_check_online_no_resource():
    validator = MagicMock()
    r = SelectStarCheck(validator)
    assert r.check_online(MagicMock()) == []


def test_select_star_check_online_with_view():
    validator = MagicMock()
    validator.validate.return_value = []
    r = SelectStarCheck(validator)
    cursor = MagicMock()
    cursor.fetchone.return_value = ("CREATE VIEW v AS SELECT id FROM t",)
    v = r.check_online(cursor, "MY_DB.MY_VIEW")
    assert v == []
