"""Tests for ScanContext.get_or_fetch() generalized prefetch cache."""

from unittest.mock import MagicMock

from snowfort_audit.domain.scan_context import ScanContext


def test_get_or_fetch_calls_fetcher_once():
    """get_or_fetch must call the fetcher exactly once for a given (view, window)."""
    ctx = ScanContext()
    fetcher = MagicMock(return_value=(("row1",), ("row2",)))

    result1 = ctx.get_or_fetch("GRANTS_TO_ROLES", 30, fetcher)
    result2 = ctx.get_or_fetch("GRANTS_TO_ROLES", 30, fetcher)

    assert fetcher.call_count == 1
    assert result1 == result2 == (("row1",), ("row2",))


def test_get_or_fetch_different_views_fetch_independently():
    """Different view names produce independent cache entries."""
    ctx = ScanContext()
    fetcher_a = MagicMock(return_value=(("a",),))
    fetcher_b = MagicMock(return_value=(("b",),))

    rows_a = ctx.get_or_fetch("VIEW_A", 30, fetcher_a)
    rows_b = ctx.get_or_fetch("VIEW_B", 30, fetcher_b)

    fetcher_a.assert_called_once_with("VIEW_A", 30)
    fetcher_b.assert_called_once_with("VIEW_B", 30)
    assert rows_a != rows_b


def test_get_or_fetch_different_windows_fetch_independently():
    """Same view with different window_days produces independent cache entries."""
    ctx = ScanContext()
    calls = []

    def fetcher(view: str, window: int):
        calls.append((view, window))
        return ((window,),)

    r30 = ctx.get_or_fetch("GRANTS_TO_ROLES", 30, fetcher)
    r7 = ctx.get_or_fetch("GRANTS_TO_ROLES", 7, fetcher)

    assert len(calls) == 2
    assert r30 == ((30,),)
    assert r7 == ((7,),)


def test_get_or_fetch_empty_result_is_cached():
    """An empty result tuple is cached — fetcher is not called again."""
    ctx = ScanContext()
    fetcher = MagicMock(return_value=())

    r1 = ctx.get_or_fetch("EMPTY_VIEW", 30, fetcher)
    r2 = ctx.get_or_fetch("EMPTY_VIEW", 30, fetcher)

    assert fetcher.call_count == 1
    assert r1 == r2 == ()


def test_get_or_fetch_passes_correct_args_to_fetcher():
    """Fetcher receives (view, window_days) as positional args."""
    ctx = ScanContext()
    fetcher = MagicMock(return_value=())

    ctx.get_or_fetch("CORTEX_AI_FUNCTIONS_USAGE_HISTORY", 14, fetcher)

    fetcher.assert_called_once_with("CORTEX_AI_FUNCTIONS_USAGE_HISTORY", 14)


def test_get_or_fetch_independent_contexts_do_not_share_cache():
    """Each ScanContext instance has its own cache."""
    ctx1 = ScanContext()
    ctx2 = ScanContext()
    fetcher = MagicMock(return_value=(("row",),))

    ctx1.get_or_fetch("VIEW_X", 30, fetcher)
    ctx2.get_or_fetch("VIEW_X", 30, fetcher)

    assert fetcher.call_count == 2


def test_get_or_fetch_fetcher_exception_propagates():
    """If the fetcher raises, the exception propagates to the caller (not swallowed)."""
    import pytest

    ctx = ScanContext()
    fetcher = MagicMock(side_effect=RuntimeError("network error"))

    with pytest.raises(RuntimeError, match="network error"):
        ctx.get_or_fetch("BAD_VIEW", 30, fetcher)

    # Cache should NOT store a failed result — subsequent call should try again.
    fetcher2 = MagicMock(return_value=(("ok",),))
    result = ctx.get_or_fetch("BAD_VIEW", 30, fetcher2)
    assert result == (("ok",),)
