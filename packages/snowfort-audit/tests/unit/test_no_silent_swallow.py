"""Architecture invariant: zero silent exception swallowing in rule entry points.

Every ``except Exception`` block under ``src/snowfort_audit/domain/rules/`` must end
with one of the canonical handling patterns:

  * ``raise RuleExecutionError(...)`` — propagate as ERRORED finding
  * ``if is_allowlisted_sf_error(exc): return []`` — narrow allowlist for views
    that may legitimately not exist on older accounts
  * ``raise`` (re-raise — used by some debug-logging helpers)
  * The handler is inside a private helper that's NOT a rule entry point and
    re-raises a wrapping error after logging — covered by the explicit allowlist
    below.

A new ``except Exception: pass`` (or ``return []`` without the allowlist guard)
WILL fail this test, blocking it at CI.
"""

from __future__ import annotations

import ast
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parents[2] / "src" / "snowfort_audit" / "domain" / "rules"

# Helper functions that are explicitly allowed to swallow inside their bodies because
# they're either (a) telemetry-only paths (debug log + continue) where the calling
# rule handles the real propagation, or (b) intentionally permissive resource probes.
# Pin them here by (file_basename, function_name) so a NEW silent swallow doesn't
# get a free pass.
_ALLOWLISTED_SWALLOW_SITES: frozenset[tuple[str, str]] = frozenset(
    {
        # SelectStarCheck.check_online wraps GET_DDL — failure logs at ERROR and returns [].
        # Per-view DDL probe; outer use_cases layer is the propagation point.
        ("static.py", "check_online"),
        # UserOwnershipCheck iterates SHOW DATABASES/WAREHOUSES/INTEGRATIONS; a single
        # failed sub-query logs at debug and the rule continues with the remaining types.
        ("security.py", "check_online"),
        # CIS Trust Center probe tries multiple view paths; logs and continues.
        ("security.py", "_probe_trust_center_view"),
        # OPS_014 PermifrostDriftCheck loads a user-provided YAML file. A malformed
        # spec is a config error, not a Snowflake error — log + skip is correct.
        ("op_excellence.py", "_load_spec"),
        # GOV_034 ContentPiiDetectionCheck samples each column individually.
        # A per-column query failure (access denied, unsupported type, etc.) is
        # skipped with `continue` so the rule can finish the remaining columns.
        # The outer try/except still raises RuleExecutionError for non-Snowflake errors.
        ("sensitive_data.py", "check_online"),
    }
)


def _swallow_pattern_in_handler(handler: ast.ExceptHandler) -> bool:
    """Return True if the handler body looks like a silent swallow (forbidden).

    A swallow is: ``pass`` / ``return []`` / ``return None`` / ``continue`` with
    no preceding call to ``is_allowlisted_sf_error`` and no ``raise``.
    """
    has_allowlist_check = False
    has_raise = False
    has_silent_terminator = False

    for node in ast.walk(handler):
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Name) and node.func.id == "is_allowlisted_sf_error") or (
                isinstance(node.func, ast.Attribute) and node.func.attr == "is_allowlisted_sf_error"
            ):
                has_allowlist_check = True
        if isinstance(node, ast.Raise):
            has_raise = True
        if isinstance(node, ast.Pass):
            has_silent_terminator = True
        if isinstance(node, ast.Return) and (
            node.value is None
            or (isinstance(node.value, ast.Constant) and node.value.value is None)
            or (isinstance(node.value, ast.List) and not node.value.elts)
        ):
            has_silent_terminator = True
        if isinstance(node, ast.Continue):
            has_silent_terminator = True

    if has_raise:
        return False
    if has_allowlist_check:
        return False
    return has_silent_terminator


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str | None:
    cursor = parents.get(node)
    while cursor is not None:
        if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cursor.name
        cursor = parents.get(cursor)
    return None


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def test_no_silent_exception_swallow_in_rules():
    offenders: list[str] = []
    for py_file in sorted(RULES_DIR.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        parents = _build_parent_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            type_node = node.type
            if not (
                type_node is None
                or (isinstance(type_node, ast.Name) and type_node.id == "Exception")
                or (
                    isinstance(type_node, ast.Tuple)
                    and any(isinstance(e, ast.Name) and e.id == "Exception" for e in type_node.elts)
                )
            ):
                continue
            if not _swallow_pattern_in_handler(node):
                continue
            enclosing = _enclosing_function(node, parents) or "<module>"
            site = (py_file.name, enclosing)
            if site in _ALLOWLISTED_SWALLOW_SITES:
                continue
            offenders.append(f"{py_file.relative_to(RULES_DIR.parent.parent.parent)}:{node.lineno} in {enclosing}")

    assert not offenders, (
        "Silent `except Exception` swallows found in rule code (architecture invariant violation):\n  "
        + "\n  ".join(offenders)
        + "\n\nFix: replace with `is_allowlisted_sf_error(exc) → return []` for narrow view-not-found"
        " cases, or `raise RuleExecutionError(self.id, str(exc), cause=exc) from exc` for everything else."
        " If the swallow is genuinely correct (e.g. a telemetry-only debug helper),"
        " add an entry to _ALLOWLISTED_SWALLOW_SITES with a one-line justification."
    )
