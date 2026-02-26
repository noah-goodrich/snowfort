# Severity & Grading Rubric

How Snowfort Audit assigns severity to rules, calculates scores, and grades your Snowflake account.

---

## Severity Levels

Each rule has a fixed severity that reflects the potential impact if left unaddressed.

| Severity   | Criteria | Examples |
|------------|----------|----------|
| **CRITICAL** | Immediate risk of data loss, security breach, or uncontrolled spend. A single finding here can cause catastrophic damage. | Open network policy (0.0.0.0/0), no account budget, hardcoded secrets in code, remote spillage |
| **HIGH** | Significant risk that compounds over time. Likely to cause incidents if not remediated within weeks. | Public role grants, data exfiltration params disabled, runaway query timeout, naked DROP statements |
| **MEDIUM** | Best-practice gaps that increase operational risk or cost. Should be addressed during regular maintenance. | Missing password policy, loose auto-suspend, no clustering on large tables, missing resource monitors |
| **LOW** | Hygiene and polish items. Low individual impact but collectively indicate operational maturity gaps. | Missing object comments, no notification integration, no event table configured |

### How Severity Is Assigned

Severity is defined per-rule in the rule source code (`domain/rules/`). The assignment follows this decision tree:

1. **Can this cause immediate data loss or a breach?** → CRITICAL
2. **Can this cause a significant incident within weeks?** → HIGH
3. **Does this violate WAF best practices with measurable impact?** → MEDIUM
4. **Is this a hygiene/maturity improvement?** → LOW

The full mapping of rule → severity is in [`RULES_CATALOG.md`](RULES_CATALOG.md).

---

## Scoring

### Per-Pillar Score

Each of the six WAF pillars (Security, Cost, Reliability, Performance, Operations, Governance) starts at **100** and is reduced by the findings within that pillar:

| Severity   | Deduction per finding |
|------------|----------------------|
| CRITICAL   | −10 |
| HIGH       | −5  |
| MEDIUM     | −2  |
| LOW        | −1  |

Pillar scores are floored at **0** (never negative).

**Example**: Security pillar with 2 CRITICAL, 1 HIGH, 2 MEDIUM findings:
`100 − (2×10) − (1×5) − (2×2) = 71`

### Overall Score

The overall compliance score is the **mean of all six pillar scores**, equally weighted. This prevents a single pillar with many findings from overwhelming the total, and ensures every pillar matters.

**Source**: `domain/results.py` → `AuditScorecard.from_violations()`

---

## Letter Grades

| Grade | Score Range | Status Label |
|-------|------------|--------------|
| **A** | 90–100 | Healthy |
| **B** | 80–89  | Review |
| **C** | 70–79  | Review |
| **D** | 60–69  | Critical |
| **F** | 0–59   | Critical |

- **Healthy** (A): Meets or exceeds WAF best practices. Maintain current posture.
- **Review** (B/C): Gaps exist that should be addressed during regular sprint work.
- **Critical** (D/F): Significant risks require immediate remediation planning.

---

## Where This Lives in Code

| Concern | Location |
|---------|----------|
| Severity per rule | `domain/rules/*.py` — each rule class sets `self.severity` |
| Deduction formula | `domain/results.py` → `_pillar_deduction()` |
| Grade thresholds | `domain/results.py` → `_score_to_grade()` |
| Pillar + overall calculation | `domain/results.py` → `AuditScorecard.from_violations()` |
| Rule catalog (quick reference) | `docs/RULES_CATALOG.md` |
| Convention defaults | `docs/SNOWFORT_CONVENTIONS.md` |

---

## Overriding Conventions

Snowfort ships with opinionated defaults (e.g., `auto_suspend_seconds = 1`). Override any convention in your `pyproject.toml`:

```toml
[tool.snowfort.conventions.warehouse]
auto_suspend_seconds = 60

[tool.snowfort.conventions.security]
max_account_admins = 5
```

See [`SNOWFORT_CONVENTIONS.md`](SNOWFORT_CONVENTIONS.md) for all available settings.

---

## CLI Navigation

```
snowfort audit show                          Overview: scorecard + checklist
snowfort audit show --pillar Security        Drill into one pillar (WHY / AFFECTED / FIX)
snowfort audit scan                          TUI launches after scan by default (--no-tui to skip)
snowfort audit show --interactive            TUI for cached results: navigate with keyboard
snowfort audit show -o report.yaml           Export YAML report (from cache)
snowfort audit rules SEC_001                 Full rule definition and remediation
snowfort audit show --severity CRITICAL      Filter cached results
```
