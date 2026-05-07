# Project Plan: Security Posture Rules (Article Gap Analysis)
*Established: 2026-05-07*

## Objective
Add 8 new security-posture rules to snowfort-audit (SEC_030–SEC_036 + COST_047) covering Trust Center scanner
status, session policy enforcement, brute-force login detection, private link ratio, large export volume monitoring,
periodic rekeying, threat intelligence findings, and inactive user license impact — filling gaps identified by the
leadership committee's review of the Snowflake Security Scanner article.

## Acceptance Criteria
- [ ] 8 new rules registered and discoverable in `get_all_rules()` output (SEC_030–SEC_036, COST_047)
  - Verify: `drone exec snowfort -- python -c "from snowfort_audit.infrastructure.rule_registry import get_all_rules; from snowfort_audit.domain.financials import FinancialEvaluator; rules = get_all_rules(FinancialEvaluator()); ids = [r.id for r in rules]; assert all(x in ids for x in ['SEC_030','SEC_031','SEC_032','SEC_033','SEC_034','SEC_035','SEC_036','COST_047'])"`
- [ ] Graceful degradation: Trust Center and LOGIN_HISTORY rules return `[]` on errno 2003
  - Verify: Unit tests assert `check_online()` returns `[]` when cursor raises error with errno=2003
- [ ] Each rule has pass/fail/degradation unit tests
  - Verify: `drone exec snowfort -- make test`
- [ ] Coverage ≥ 80%
  - Verify: `drone exec snowfort -- make coverage-check`
- [ ] Full CI gate passes (lint + mypy + tests + coverage)
  - Verify: `drone exec snowfort -- make check`

## Scope Boundaries
- NOT building: HTML report generation or new output formats
- NOT building: Rule base class schema changes (verification_query, rollback_guidance, sla_hours)
- NOT building: Historical manifest tracking or scan cadence metadata
- If done early: Ship, don't expand.

## Ship Definition
PR opened → CI passes (`drone exec snowfort -- make check`) → merged to main.

## Timeline
Target: this session
Estimated effort: 1 session (~2 hours)

## Risks
- Trust Center views (`SNOWFLAKE.TRUST_CENTER.*`) have inconsistent schema paths across Snowflake versions
  (LOCAL vs TRUST_CENTER). Mitigated by trying both paths with fallback, following SEC_017 pattern.
- LOGIN_HISTORY may not be available to AUDITOR role without IMPORTED PRIVILEGES. Mitigated by graceful
  degradation (errno 2003 → []).
- COPY_HISTORY view schema may differ between editions. Mitigated by defensive column indexing and
  allowlisted error handling.
