"""Tests for RuleThresholdConventions and nested threshold dataclasses."""

from snowfort_audit.domain.conventions import (
    CortexThresholds,
    HighChurnThresholds,
    MandatoryTaggingThresholds,
    NetworkPerimeterThresholds,
    RuleThresholdConventions,
    SnowfortConventions,
)
from snowfort_audit.infrastructure.config_loader import load_conventions

# ── Default values ────────────────────────────────────────────────────────────


def test_rule_threshold_conventions_defaults():
    t = RuleThresholdConventions()
    assert t.warehouse_auto_suspend_max_seconds == 3600
    assert t.zombie_user_days == 90
    assert isinstance(t.high_churn, HighChurnThresholds)
    assert isinstance(t.mandatory_tagging, MandatoryTaggingThresholds)
    assert isinstance(t.network_perimeter, NetworkPerimeterThresholds)
    assert isinstance(t.cortex, CortexThresholds)


def test_high_churn_thresholds_defaults():
    h = HighChurnThresholds()
    assert h.rows_per_day_threshold == 1_000_000
    assert h.exclude_name_patterns == ()


def test_mandatory_tagging_thresholds_defaults():
    m = MandatoryTaggingThresholds()
    assert "COMPUTE_SERVICE_WH_*" in m.exclude_warehouse_patterns


def test_network_perimeter_thresholds_defaults():
    n = NetworkPerimeterThresholds()
    assert n.sso_downgrade is False


def test_cortex_thresholds_defaults():
    c = CortexThresholds()
    assert c.daily_credit_hard_limit == 100.0
    assert c.daily_credit_soft_limit == 50.0
    assert c.model_allowlist_expected == ()
    assert c.analyst_max_requests_per_user_per_day == 1000
    assert c.snowflake_intelligence_max_daily_credits == 50.0


def test_snowfort_conventions_has_thresholds():
    c = SnowfortConventions()
    assert isinstance(c.thresholds, RuleThresholdConventions)
    assert c.thresholds.zombie_user_days == 90


# ── load_conventions with [tool.snowfort.conventions.thresholds] overrides ────


def test_load_conventions_threshold_scalar_override(tmp_path):
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    (tmp_path / "pyproject.toml").write_text(
        "[tool.snowfort.conventions.thresholds]\nzombie_user_days = 120\n",
        encoding="utf-8",
    )
    c = load_conventions(tmp_path)
    assert c.thresholds.zombie_user_days == 120
    # Unaffected defaults preserved
    assert c.thresholds.warehouse_auto_suspend_max_seconds == 3600


def test_load_conventions_high_churn_override(tmp_path):
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    (tmp_path / "pyproject.toml").write_text(
        '[tool.snowfort.conventions.thresholds.high_churn]\nexclude_name_patterns = ["CDC_*", "STG_*"]\n',
        encoding="utf-8",
    )
    c = load_conventions(tmp_path)
    assert "CDC_*" in c.thresholds.high_churn.exclude_name_patterns
    assert "STG_*" in c.thresholds.high_churn.exclude_name_patterns
    assert isinstance(c.thresholds.high_churn.exclude_name_patterns, tuple)


def test_load_conventions_mandatory_tagging_override(tmp_path):
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    (tmp_path / "pyproject.toml").write_text(
        '[tool.snowfort.conventions.thresholds.mandatory_tagging]\nexclude_warehouse_patterns = ["SYS_*"]\n',
        encoding="utf-8",
    )
    c = load_conventions(tmp_path)
    assert "SYS_*" in c.thresholds.mandatory_tagging.exclude_warehouse_patterns


def test_load_conventions_network_perimeter_sso_override(tmp_path):
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    (tmp_path / "pyproject.toml").write_text(
        "[tool.snowfort.conventions.thresholds.network_perimeter]\nsso_downgrade = true\n",
        encoding="utf-8",
    )
    c = load_conventions(tmp_path)
    assert c.thresholds.network_perimeter.sso_downgrade is True


def test_load_conventions_cortex_override(tmp_path):
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    (tmp_path / "pyproject.toml").write_text(
        "[tool.snowfort.conventions.thresholds.cortex]\n"
        "daily_credit_hard_limit = 200.0\n"
        'model_allowlist_expected = ["llama3.1-70b", "mistral-7b"]\n',
        encoding="utf-8",
    )
    c = load_conventions(tmp_path)
    assert c.thresholds.cortex.daily_credit_hard_limit == 200.0
    assert "llama3.1-70b" in c.thresholds.cortex.model_allowlist_expected
    assert isinstance(c.thresholds.cortex.model_allowlist_expected, tuple)


def test_load_conventions_thresholds_does_not_affect_other_fields(tmp_path):
    """Threshold overrides must not clobber warehouse/naming/security/tags."""
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    (tmp_path / "pyproject.toml").write_text(
        "[tool.snowfort.conventions.thresholds]\nzombie_user_days = 60\n"
        "[tool.snowfort.conventions.warehouse]\nauto_suspend_seconds = 30\n",
        encoding="utf-8",
    )
    c = load_conventions(tmp_path)
    assert c.thresholds.zombie_user_days == 60
    assert c.warehouse.auto_suspend_seconds == 30
    assert c.naming.service_account_prefix == "SVC_"
