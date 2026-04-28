"""Regression tests for the security-hardening pass.

Each test pins one of the P0/P1 fixes from the adversarial review so a future
refactor can't silently un-do the protection.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.results import AuditResult
from snowfort_audit.domain.rule_definitions import Severity, Violation
from snowfort_audit.domain.sql_safety import (
    escape_string_literal,
    is_safe_unquoted_identifier,
    quote_fqdn,
    quote_identifier,
)
from snowfort_audit.infrastructure.cortex_synthesizer import CortexSynthesizer, _redact_message
from snowfort_audit.interface.cli.report import write_audit_cache

# ---------------------------------------------------------------------------
# P0-2: Cortex synthesizer must redact fully-qualified Snowflake names
# ---------------------------------------------------------------------------


def test_redact_message_replaces_fqdn_with_token():
    msg = "Column PRD_DB.PHI.PATIENTS.PATIENT_SSN has no masking policy."
    redacted = _redact_message(msg)
    assert "PRD_DB" not in redacted
    assert "PATIENT_SSN" not in redacted
    assert "<RESOURCE_1>" in redacted


def test_redact_message_stable_token_per_unique_resource():
    msg = "Column DB1.S1.T1.C1 conflicts with DB1.S1.T1.C1; also see DB2.S2.T2."
    redacted = _redact_message(msg)
    # Same resource → same token; different resource → different token.
    assert redacted.count("<RESOURCE_1>") == 2
    assert "<RESOURCE_2>" in redacted


def test_cortex_synthesizer_does_not_leak_fqdns_in_prompt():
    cur = MagicMock()
    cur.fetchall.return_value = [("ok",)]
    syn = CortexSynthesizer(cur)
    syn.summarize(
        [
            Violation("GOV_009", "PRD.PHI.PATIENTS", "Column PRD.PHI.PATIENTS.PATIENT_SSN unprotected.", Severity.HIGH),
        ]
    )
    args, _ = cur.execute.call_args
    prompt = args[1][1]  # bind params: (model, prompt)
    assert "PATIENT_SSN" not in prompt
    assert "PRD.PHI.PATIENTS" not in prompt
    assert "<RESOURCE_" in prompt


# ---------------------------------------------------------------------------
# P1-1: Cortex synthesizer must use bind parameters, not f-string interpolation
# ---------------------------------------------------------------------------


def test_cortex_synthesizer_uses_bind_parameters():
    cur = MagicMock()
    cur.fetchall.return_value = [("ok",)]
    syn = CortexSynthesizer(cur)
    syn.summarize([Violation("X", "r", "msg", Severity.LOW)])
    args, _ = cur.execute.call_args
    sql = args[0]
    params = args[1]
    assert sql == "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)"
    assert isinstance(params, tuple)
    assert len(params) == 2


# ---------------------------------------------------------------------------
# P2: SNOWFORT_DISABLE_CORTEX env hard-disable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "Yes"])
def test_cortex_disabled_by_env_var(monkeypatch, value):
    monkeypatch.setenv("SNOWFORT_DISABLE_CORTEX", value)
    cur = MagicMock()
    syn = CortexSynthesizer(cur)
    summary = syn.summarize_structured([Violation("X", "r", "msg", Severity.LOW)])
    cur.execute.assert_not_called()
    assert "disabled" in summary.tl_dr.lower()


# ---------------------------------------------------------------------------
# P1-2: Audit cache file must be mode 0600 (user-only readable)
# ---------------------------------------------------------------------------


def test_audit_cache_is_user_only_readable(tmp_path: Path):
    result = AuditResult.from_violations([])
    write_audit_cache(tmp_path, result, target_name="test")
    cache_file = tmp_path / ".snowfort" / "audit_results.json"
    assert cache_file.exists()
    # Skip on Windows where chmod doesn't translate.
    if os.name != "posix":
        return
    mode = cache_file.stat().st_mode
    # Group + other bits must be zero.
    assert mode & 0o077 == 0, f"cache file mode {oct(mode)} grants group/other access"


# ---------------------------------------------------------------------------
# P1-3: SQL identifier / literal safety helpers
# ---------------------------------------------------------------------------


def test_is_safe_unquoted_identifier_grammar():
    assert is_safe_unquoted_identifier("MY_TABLE")
    assert is_safe_unquoted_identifier("a")
    assert is_safe_unquoted_identifier("_underscore")
    assert is_safe_unquoted_identifier("col$dollar")
    assert not is_safe_unquoted_identifier("starts-with-dash")
    assert not is_safe_unquoted_identifier("1leading_digit")
    assert not is_safe_unquoted_identifier('contains"quote')
    assert not is_safe_unquoted_identifier("contains space")
    assert not is_safe_unquoted_identifier("")


def test_quote_identifier_doubles_embedded_quotes():
    assert quote_identifier('foo"bar') == '"foo""bar"'
    assert quote_identifier("normal") == '"normal"'
    assert quote_identifier('attack")') == '"attack"")"'


def test_quote_fqdn_quotes_each_part():
    assert quote_fqdn("DB", "SCHEMA", "TABLE") == '"DB"."SCHEMA"."TABLE"'
    # Malicious input cannot break out — quote chars are doubled.
    assert quote_fqdn('foo"); DROP', "x", "y") == '"foo""); DROP"."x"."y"'


def test_escape_string_literal_blocks_injection():
    assert escape_string_literal("normal") == "normal"
    assert escape_string_literal("o'brien") == "o''brien"
    assert escape_string_literal("'); DROP TABLE x; --") == "''); DROP TABLE x; --"
    assert escape_string_literal("back\\slash") == "back\\\\slash"


def test_clustering_depth_escapes_malicious_table_name():
    """PERF_001 _check_clustering_depth must escape FQDNs before f-string interpolation."""
    from snowfort_audit.domain.rules.perf import ClusterKeyValidationCheck

    rule = ClusterKeyValidationCheck()
    cur = MagicMock()
    cur.fetchone.return_value = (None,)
    # quote_fqdn produces double-quoted FQDN; pass that as the resource_name
    malicious_fqdn = quote_fqdn('foo"); DELETE FROM x; --', "S", "T")
    rule._check_clustering_depth(cur, malicious_fqdn)
    sql = cur.execute.call_args[0][0]
    # Single quotes inside the literal must be doubled.
    assert "DELETE FROM x" in sql  # the bytes are present...
    # ...but they're inside a literal that doesn't break out:
    assert sql.count("'") % 2 == 0, "unbalanced quotes — string literal not properly escaped"


# ---------------------------------------------------------------------------
# P0-1: Cortex fetcher must drop sensitive payload columns at SQL level
# ---------------------------------------------------------------------------


def test_cortex_fetcher_excludes_sensitive_payload_columns():
    """_cortex_fetcher discovers sensitive cols and EXCLUDEs them from SELECT."""
    from snowfort_audit.domain.rules.cortex_cost import _cortex_fetcher

    cur = MagicMock()
    # First execute = column-discovery; mock it to return one sensitive column.
    cur.fetchall.side_effect = [
        [("REQUEST_BODY",), ("RESPONSE_BODY",), ("USER_NAME",)],  # discovery result
        [],  # data fetch
    ]
    fetcher = _cortex_fetcher(cur, "CORTEX_ANALYST_USAGE_HISTORY")
    fetcher("CORTEX_ANALYST_USAGE_HISTORY", 30)
    # Find the data-fetch SQL (not the columns query).
    fetch_sqls = [
        call[0][0]
        for call in cur.execute.call_args_list
        if "CORTEX_ANALYST_USAGE_HISTORY" in call[0][0] and "INFORMATION_SCHEMA" not in call[0][0].upper()
    ]
    assert fetch_sqls, "Expected a fetch against the Cortex view"
    sql = fetch_sqls[-1]
    assert "EXCLUDE" in sql.upper()
    assert "REQUEST_BODY" in sql.upper()
    assert "RESPONSE_BODY" in sql.upper()


def test_cortex_fetcher_no_exclude_when_no_sensitive_cols():
    """Views without payload columns get a plain SELECT * with no EXCLUDE."""
    from snowfort_audit.domain.rules.cortex_cost import _cortex_fetcher

    cur = MagicMock()
    cur.fetchall.side_effect = [
        [("USER_NAME",), ("CREDITS_USED",)],  # discovery: nothing sensitive
        [],
    ]
    fetcher = _cortex_fetcher(cur, "CORTEX_AI_FUNCTIONS_USAGE_HISTORY")
    fetcher("CORTEX_AI_FUNCTIONS_USAGE_HISTORY", 30)
    fetch_sqls = [
        call[0][0]
        for call in cur.execute.call_args_list
        if "CORTEX_AI_FUNCTIONS_USAGE_HISTORY" in call[0][0] and "INFORMATION_SCHEMA" not in call[0][0].upper()
    ]
    assert fetch_sqls
    sql = fetch_sqls[-1]
    assert "EXCLUDE" not in sql.upper()
