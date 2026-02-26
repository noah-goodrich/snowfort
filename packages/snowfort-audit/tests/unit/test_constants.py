"""Tests for interface.constants."""

from snowfort_audit.interface.constants import (
    SNOWFORT_BANNER,
    SNOWFORT_HEADER_MINIFIED,
    get_snowfort_splash,
)


def test_snowfort_banner_contains_snowfort():
    assert "Snowfort" in SNOWFORT_BANNER


def test_snowfort_header_minified_contains_snowfort():
    assert "snowfort" in SNOWFORT_HEADER_MINIFIED


def test_get_snowfort_splash_returns_string():
    s = get_snowfort_splash()
    assert isinstance(s, str)
    assert len(s) > 0
    assert "snowfort" in s.lower() or "Well-Architected" in s
