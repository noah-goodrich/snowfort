"""Tests for the Streamlit app: DI helpers, data loading, and display data building."""

import types
from unittest.mock import MagicMock, patch

import pytest

from snowfort_audit.domain.results import AuditResult
from snowfort_audit.domain.rule_definitions import Severity, Violation

pandas: types.ModuleType | None = None
streamlit: types.ModuleType | None = None
try:
    import pandas as _pandas  # noqa: F401
    import streamlit as _streamlit  # noqa: F401

    pandas = _pandas
    streamlit = _streamlit
except ImportError:
    pass


@pytest.fixture(autouse=True)
def _skip_if_no_streamlit_deps():
    if pandas is None or streamlit is None:
        pytest.skip('pandas and streamlit required for streamlit_app tests (pip install -e ".[dev]")')


def test_violations_to_display_data_empty():
    from snowfort_audit.interface.streamlit_app import violations_to_display_data

    assert violations_to_display_data([]) == []


def test_violations_to_display_data_one():
    from snowfort_audit.interface.streamlit_app import violations_to_display_data

    v = Violation("COST_001", "WH_X", "Auto-suspend high", Severity.MEDIUM)
    rows = violations_to_display_data([v])
    assert len(rows) == 1
    assert rows[0]["RULE_ID"] == "COST_001"
    assert rows[0]["RESOURCE_NAME"] == "WH_X"
    assert rows[0]["SEVERITY"] == "MEDIUM"


def test_get_snowpark_session_returns_none_when_no_snowpark():
    """When snowflake.snowpark.context is not available, returns None."""
    import sys

    from snowfort_audit.interface.streamlit_app import get_snowpark_session

    key = "snowflake.snowpark.context"
    old = sys.modules.pop(key, None)
    try:
        result = get_snowpark_session()
        assert result is None
    finally:
        if old is not None:
            sys.modules[key] = old


def test_get_container_returns_audit_container():
    from snowfort_audit.interface.streamlit_app import get_container

    container = get_container()
    assert container is not None
    assert hasattr(container, "get")
    assert hasattr(container, "register_factory")


def test_load_audit_result():
    from snowfort_audit.interface.streamlit_app import load_audit_result

    mock_repo = MagicMock()
    mock_repo.get_latest_audit_result.return_value = AuditResult.from_violations([])
    mock_container = MagicMock()
    mock_container.get.return_value = mock_repo

    result = load_audit_result(mock_container)
    assert result.scorecard.compliance_score == 100
    mock_container.get.assert_called_once_with("AuditRepository")
    mock_repo.get_latest_audit_result.assert_called_once()


def test_streamlit_app_top_level_runs_with_mocked_st():
    """Import app with streamlit and AuditContainer mocked so top-level code executes (coverage)."""
    import importlib
    import sys

    mock_st = MagicMock()
    mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n)]
    mock_st.sidebar.__enter__ = MagicMock(return_value=MagicMock())
    mock_st.sidebar.__exit__ = MagicMock(return_value=False)
    mock_st.text_input.return_value = ""  # top-level code uses search_query in str.contains()

    mock_result = AuditResult.from_violations([])
    mock_repo = MagicMock()
    mock_repo.get_latest_audit_result.return_value = mock_result
    mock_container = MagicMock()
    mock_container.get.return_value = mock_repo

    mod_name = "snowfort_audit.interface.streamlit_app"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    with patch.dict(sys.modules, {"streamlit": mock_st}):
        with patch("snowfort_audit.di.container.AuditContainer", return_value=mock_container):
            importlib.import_module(mod_name)
    mock_st.set_page_config.assert_called_once()
    mock_st.title.assert_called()
