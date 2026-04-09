# Rule Authoring Checklist

Every new rule merged into snowfort-audit must satisfy all items in this checklist
before the PR is approved. The checklist enforces consistency, correctness, and
security across the rule catalog.

---

## 1. Class structure

- [ ] Class inherits from `Rule` (domain layer — no infrastructure imports).
- [ ] Constructor calls `super().__init__()` with all five fields:
  `rule_id`, `name`, `severity`, `rationale`, `remediation`.
- [ ] `rationale` cites the relevant briefing section or WAF pillar justification
  (e.g., "INCLOUDCOUNSEL briefing §3.2 — admin exposure").
- [ ] `remediation` is a full sentence with an actionable `ALTER` / `CREATE` /
  `GRANT` / `REVOKE` command where applicable.
- [ ] `remediation_key` is set (used by the YAML export for deduplication).

## 2. Thresholds as named constants

- [ ] Any numeric threshold appears as a named constant with a rationale comment,
  NOT as a magic literal inline.

  **Wrong:**
  ```python
  if suspend_val > 3600:
  ```

  **Right:**
  ```python
  # 3600s = 1 hour; warehouses idle longer than this waste credits without
  # performance benefit (INCLOUDCOUNSEL briefing §4.1 Cost findings).
  MAX_AUTO_SUSPEND_SECONDS = 3600
  ...
  if suspend_val > MAX_AUTO_SUSPEND_SECONDS:
  ```

- [ ] Thresholds that users may need to tune are read from
  `conventions.thresholds.*` (injected at construction time) rather than
  hardcoded as class-level constants.

## 3. Error handling

- [ ] `check_online` wraps cursor queries in try/except.
- [ ] Allowlisted Snowflake errors (view not found, `errno=2003`) are swallowed
  and return `[]` — use `is_allowlisted_sf_error(exc)` from `rule_definitions`.
- [ ] All other exceptions are re-raised as `RuleExecutionError`:
  ```python
  raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
  ```
- [ ] Rules **never** silently swallow `Exception` with a bare `except: pass`.

## 4. Sensitive-output review

No rule may include sensitive data in `Violation.message` or `Violation.details`.
Run `scripts/check_sensitive_outputs.py` against your rule file before submitting.

Forbidden substrings in violation messages:
- `token`, `password`, `secret`, `private_key`, `-----BEGIN`
- Raw bytes or hex-encoded credential material

If a rule must reference a credential object by name (e.g., a network policy or
secret name), include only the **name**, never the **value**.

## 5. Tests

Every new rule requires **at minimum** four test cases:

1. `scan_context=None` → returns `[]` (no crash when context not available).
2. View/object unavailable (`is_allowlisted_sf_error` path) → returns `[]`.
3. Threshold **crossed** → violation returned with correct `severity` and `rule_id`.
4. Threshold **not crossed** → returns `[]`.

For `ParameterizedRuleFamily` members, test each generated rule ID independently.

## 6. Snapshot update

After adding a new rule, regenerate the snapshot to include it:

```bash
UPDATE_SNAPSHOT=1 pytest tests/unit/test_rules_snapshot.py
```

Commit the updated `tests/unit/fixtures/rules_snapshot.yaml` alongside the rule.

## 7. Registration

- [ ] Rule is instantiated in `src/snowfort_audit/infrastructure/rule_registry.py`
  under the correct pillar section with the correct dependencies injected.
- [ ] `snowfort audit rules` output lists the new rule ID after registration.

## 8. Demo seed (if applicable)

If the rule checks for a condition that can be seeded in a Snowflake account:
- [ ] `src/snowfort_audit/resources/demo_setup.sql` includes a seed statement
  labeled with `-- <RULE_ID>: <brief description>`.
- [ ] `src/snowfort_audit/resources/demo_teardown.sql` includes the corresponding
  `DROP IF EXISTS` statement.

Cortex-cost rules are exempt from demo seeding (seeding real Cortex usage
costs real credits). Mark them in `docs/SMOKE_TEST.md` as unit-only.
