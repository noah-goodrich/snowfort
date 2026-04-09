"""Snapshot regression harness for all registered rules.

Protects against behavioral regressions from the Session 3 column-name refactor
and any future mechanical refactors that touch 15+ rule files simultaneously.

Usage:
  Normal run (assert stability):
      pytest tests/unit/test_rules_snapshot.py

  Update snapshot (after intentional rule behavior changes):
      UPDATE_SNAPSHOT=1 pytest tests/unit/test_rules_snapshot.py

The snapshot file is committed to the repository.  A mismatch means a rule's
output changed — either a genuine regression or an intentional change that needs
the snapshot updated.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from tests.unit.fixtures.account_usage_fixture import make_fixture_context

SNAPSHOT_FILE = Path(__file__).parent / "fixtures" / "rules_snapshot.yaml"
UPDATE_SNAPSHOT = os.environ.get("UPDATE_SNAPSHOT", "").lower() in ("1", "true", "yes")


def _stub_cursor() -> Any:
    """Return a mock cursor that returns empty results for all queries."""
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    cursor.description = []
    cursor.rowcount = 0
    return cursor


def _run_all_rules(ctx) -> dict[str, Any]:
    """Execute every registered rule against the fixture context.

    Returns a dict mapping rule_id → list of violation dicts (or {"error": msg}).
    Rules that raise exceptions are recorded as errors so the snapshot captures
    stability of both successful and error paths.
    """
    from snowfort_audit.domain.financials import FinancialEvaluator
    from snowfort_audit.domain.protocols import TelemetryPort
    from snowfort_audit.infrastructure.rule_registry import get_all_rules

    telemetry = MagicMock(spec=TelemetryPort)
    evaluator = MagicMock(spec=FinancialEvaluator)
    evaluator.credit_price = 2.0

    rules = get_all_rules(evaluator=evaluator, telemetry=telemetry)
    cursor = _stub_cursor()
    results: dict[str, Any] = {}

    for rule in rules:
        try:
            violations = rule.check_online(cursor, scan_context=ctx)
            results[rule.id] = sorted(
                [
                    {
                        "resource": v.resource_name,
                        "severity": v.severity.value,
                        "message": v.message,
                    }
                    for v in (violations or [])
                ],
                key=lambda x: (x["resource"], x["message"]),
            )
        except Exception as exc:  # noqa: BLE001
            results[rule.id] = {"error": type(exc).__name__, "message": str(exc)[:120]}

    return dict(sorted(results.items()))


def test_rules_snapshot():
    """Assert that all rule outputs match the committed snapshot.

    On first run (no snapshot file), the snapshot is created and the test
    passes with a note.  Commit the generated file before merging.
    """
    ctx = make_fixture_context()
    actual = _run_all_rules(ctx)

    if UPDATE_SNAPSHOT:
        SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_FILE.write_text(
            yaml.dump(actual, sort_keys=True, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        return  # Updated — next run will assert

    if not SNAPSHOT_FILE.exists():
        SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_FILE.write_text(
            yaml.dump(actual, sort_keys=True, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        pytest.skip(
            f"Snapshot created at {SNAPSHOT_FILE.relative_to(Path(__file__).parent.parent.parent)}. "
            "Commit it and re-run to assert stability."
        )

    expected = yaml.safe_load(SNAPSHOT_FILE.read_text(encoding="utf-8")) or {}
    assert actual == expected, (
        "Rule snapshot mismatch — a rule's output changed.\n"
        "If intentional, regenerate with: UPDATE_SNAPSHOT=1 pytest tests/unit/test_rules_snapshot.py\n"
        "Then commit the updated snapshot file."
    )
