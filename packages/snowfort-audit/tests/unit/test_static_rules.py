from snowfort_audit.domain.rules.static import (
    AntiPatternSQLDetectionCheck,
    DynamicTableComplexityCheck,
    HardcodedEnvCheck,
    MergePatternRecommendationCheck,
    NakedDropCheck,
    SecretExposureCheck,
)


class TestStaticRules:
    def test_hardcoded_env_check(self):
        rule = HardcodedEnvCheck()

        # Violations
        assert len(rule.check_static("SELECT * FROM MY_DB_DEV", "test.sql")) == 1
        assert len(rule.check_static("CREATE DATABASE FOO_PROD", "test.sql")) == 1

        # Compliant
        assert len(rule.check_static("SELECT * FROM {{ env }}_DB", "test.sql")) == 0
        assert len(rule.check_static("my_variable_device", "test.py")) == 0  # False positive check? Rule is regex based

    def test_naked_drop_check(self):
        rule = NakedDropCheck()

        # Violations
        assert len(rule.check_static("DROP TABLE users", "drop.sql")) == 1
        assert len(rule.check_static("DROP SCHEMA raw", "utils.sql")) == 1

        # Compliant
        assert len(rule.check_static("SELECT * FROM users", "select.sql")) == 0

    def test_secret_exposure_check(self):
        rule = SecretExposureCheck()

        # Violations
        assert len(rule.check_static("password = 'supersecret'", "config.py")) == 1
        assert len(rule.check_static("private_key: '-----BEGIN'", "key.yml")) == 1

        # Compliant (Should be)
        assert len(rule.check_static("password_file = 'path/to/file'", "config.py")) == 0

    def test_merge_pattern_recommendation_check(self):
        rule = MergePatternRecommendationCheck()
        # Violation: INSERT INTO ... SELECT without MERGE
        sql = "INSERT INTO target_table SELECT * FROM source_table"
        assert len(rule.check_static(sql, "load.sql")) == 1
        # Compliant: MERGE present
        assert len(rule.check_static("MERGE INTO t USING s ON t.id = s.id", "merge.sql")) == 0

    def test_dynamic_table_complexity_check(self):
        rule = DynamicTableComplexityCheck()
        # No CREATE DYNAMIC TABLE -> no violation
        assert len(rule.check_static("SELECT 1", "x.sql")) == 0
        # Many JOINs -> violation
        sql = "CREATE DYNAMIC TABLE dt AS SELECT * FROM a JOIN b JOIN c JOIN d JOIN e JOIN f JOIN g"
        assert len(rule.check_static(sql, "dt.sql")) == 1

    def test_antipattern_sql_detection_check(self):
        rule = AntiPatternSQLDetectionCheck()
        # ORDER BY without LIMIT
        assert len(rule.check_static("SELECT * FROM t ORDER BY x", "q.sql")) == 1
        # UNION (not UNION ALL)
        assert len(rule.check_static("SELECT 1 UNION SELECT 2", "u.sql")) == 1
        # Compliant
        assert len(rule.check_static("SELECT 1 LIMIT 10", "q.sql")) == 0
