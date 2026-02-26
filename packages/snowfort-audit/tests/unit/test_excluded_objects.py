"""Tests for excluded_objects module."""

from snowfort_audit.domain.excluded_objects import (
    EXCLUDED_DATABASES_ALWAYS,
    EXCLUDED_DATABASES_DEFAULT,
    SYSTEM_OBJECT_PREFIXES,
    is_excluded_database,
    is_excluded_warehouse_or_object_name,
)


def test_excluded_databases_always():
    assert "SNOWFLAKE" in EXCLUDED_DATABASES_ALWAYS
    assert "SNOWFLAKE_SAMPLE_DATA" in EXCLUDED_DATABASES_ALWAYS


def test_excluded_databases_default_includes_snowfort():
    assert EXCLUDED_DATABASES_DEFAULT >= EXCLUDED_DATABASES_ALWAYS
    assert "SNOWFORT" in EXCLUDED_DATABASES_DEFAULT


def test_system_object_prefixes():
    assert "SYSTEM$" in SYSTEM_OBJECT_PREFIXES


def test_is_excluded_database_none():
    assert is_excluded_database(None) is False
    assert is_excluded_database(None, include_snowfort=True) is False


def test_is_excluded_database_always():
    assert is_excluded_database("SNOWFLAKE") is True
    assert is_excluded_database("snowflake") is True
    assert is_excluded_database("  SNOWFLAKE_SAMPLE_DATA  ") is True


def test_is_excluded_database_snowfort():
    assert is_excluded_database("SNOWFORT", include_snowfort=False) is True
    assert is_excluded_database("snowfort", include_snowfort=False) is True
    assert is_excluded_database("SNOWFORT", include_snowfort=True) is False


def test_is_excluded_database_user_db():
    assert is_excluded_database("MY_DB") is False
    assert is_excluded_database("DEV_BRONZE") is False


def test_is_excluded_warehouse_or_object_name_none():
    assert is_excluded_warehouse_or_object_name(None) is False


def test_is_excluded_warehouse_or_object_name_system():
    assert is_excluded_warehouse_or_object_name("SYSTEM$FOO") is True
    assert is_excluded_warehouse_or_object_name("system$bar") is True


def test_is_excluded_warehouse_or_object_name_excluded_dbs():
    assert is_excluded_warehouse_or_object_name("SNOWFLAKE") is True
    assert is_excluded_warehouse_or_object_name("SNOWFORT") is True


def test_is_excluded_warehouse_or_object_name_user():
    assert is_excluded_warehouse_or_object_name("DEV_WH") is False
    assert is_excluded_warehouse_or_object_name("MY_WAREHOUSE") is False
