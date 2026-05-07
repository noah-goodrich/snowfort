# Project Plan: Security Posture Rules (Article Gap Analysis)
*Established: 2026-05-07*
*Shipped: 2026-05-07 — PR #19 merged to main*

## Objective
Add 8 new security-posture rules to snowfort-audit (SEC_030–SEC_036 + COST_047) covering Trust Center scanner
status, session policy enforcement, brute-force login detection, private link ratio, large export volume monitoring,
periodic rekeying, threat intelligence findings, and inactive user license impact — filling gaps identified by the
leadership committee's review of the Snowflake Security Scanner article.

## Acceptance Criteria
- [x] 8 new rules registered and discoverable in `get_all_rules()` output (SEC_030–SEC_036, COST_047)
- [x] Graceful degradation: Trust Center and LOGIN_HISTORY rules return `[]` on errno 2003
- [x] Each rule has pass/fail/degradation unit tests
- [x] Coverage ≥ 80%
- [x] Full CI gate passes (lint + mypy + tests + coverage)

## Scope Boundaries
- NOT building: HTML report generation or new output formats
- NOT building: Rule base class schema changes (verification_query, rollback_guidance, sla_hours)
- NOT building: Historical manifest tracking or scan cadence metadata
- If done early: Ship, don't expand.

## Ship Definition
PR opened → CI passes (`drone exec snowfort -- make check`) → merged to main.

## Risks
- Trust Center views (`SNOWFLAKE.TRUST_CENTER.*`) have inconsistent schema paths across Snowflake versions
  (LOCAL vs TRUST_CENTER). Mitigated by trying both paths with fallback, following SEC_017 pattern.
- LOGIN_HISTORY may not be available to AUDITOR role without IMPORTED PRIVILEGES. Mitigated by graceful
  degradation (errno 2003 → []).
- COPY_HISTORY view schema may differ between editions. Mitigated by defensive column indexing and
  allowlisted error handling.
