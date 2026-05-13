# Directive D: Sensitive Data Detection

**Depends on:** Project A (Foundation) — requires `FindingCategory`, adjusted scoring,
enriched manifest, and reliable error handling.

**Priority:** Lowest effort, highest payoff for end users. Column-name heuristics are
cheap to run and catch the most common gaps. Cross-referencing existing classification
tags means we only flag what's actually unprotected.

---

## Objective

Add dynamic sensitive data detection via configurable column-name regex patterns,
cross-reference detected sensitive columns against existing Snowflake classification
tags and masking/row-access policies, and flag only the unprotected gaps. Optionally
support sample-based content detection (opt-in, not default).

## Scope

### Column-Name Heuristic Detection

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| GOV_030 | Unprotected Sensitive Columns | Detect columns whose names match sensitive-data patterns (SSN, email, phone, DOB, salary, etc.) that have no classification tag AND no masking policy attached. | HIGH |
| GOV_031 | Classification Coverage Gap | For tables with some classified columns, flag columns that match sensitive patterns but were missed by the classifier. Partial classification is worse than none — it creates false confidence. | MEDIUM |
| GOV_032 | Masking Policy Gap | Columns with classification tags indicating sensitivity (IDENTIFIER, QUASI_IDENTIFIER, SENSITIVE) but no masking or row-access policy attached. Tagged but unprotected. | HIGH |
| GOV_033 | Unprotected High-Access Tables | Cross-reference GOV_030 findings with `ACCESS_HISTORY` to identify sensitive-column tables that are also heavily queried (>100 queries/week). Higher blast radius = higher priority. | CRITICAL |

### Sample-Based Detection (Opt-In)

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| GOV_034 | Content-Based Sensitive Data | For tables flagged by GOV_030, optionally sample N rows (configurable, default 100) and run regex patterns against string columns to detect actual sensitive content (email format, SSN format, phone format). Opt-in via convention. | HIGH |

### Conventions

```toml
[tool.snowfort.thresholds.sensitive_data]
# Regex patterns for column names that likely contain sensitive data.
# Each pattern maps to a sensitivity category.
# NOT a hard-coded list — fully configurable via pyproject.toml.
column_patterns = [
    { pattern = "(?i)(ssn|social.?security|sin|national.?id)", category = "IDENTIFIER" },
    { pattern = "(?i)(email|e.?mail)", category = "QUASI_IDENTIFIER" },
    { pattern = "(?i)(phone|mobile|cell|fax|tel)", category = "QUASI_IDENTIFIER" },
    { pattern = "(?i)(dob|date.?of.?birth|birth.?date|birthday)", category = "IDENTIFIER" },
    { pattern = "(?i)(salary|compensation|pay.?rate|wage|income)", category = "SENSITIVE" },
    { pattern = "(?i)(credit.?card|card.?num|ccn|pan)", category = "IDENTIFIER" },
    { pattern = "(?i)(passport|driver.?lic|dl.?num)", category = "IDENTIFIER" },
    { pattern = "(?i)(password|passwd|secret|token|api.?key)", category = "SENSITIVE" },
    { pattern = "(?i)(address|street|zip|postal|city|state)", category = "QUASI_IDENTIFIER" },
    { pattern = "(?i)(ip.?addr|ipv4|ipv6|mac.?addr)", category = "QUASI_IDENTIFIER" },
]

# Content sampling (opt-in)
enable_content_sampling = false
sample_row_count = 100

# Content patterns (regex for actual values, not column names)
content_patterns = [
    { pattern = "\\b\\d{3}-\\d{2}-\\d{4}\\b", category = "SSN" },
    { pattern = "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b", category = "EMAIL" },
    { pattern = "\\b\\d{3}[-.\\s]?\\d{3}[-.\\s]?\\d{4}\\b", category = "PHONE" },
]
```

### Data Sources

| View / Command | Purpose |
|----------------|---------|
| `INFORMATION_SCHEMA.COLUMNS` | Column names and data types per table |
| `ACCOUNT_USAGE.TAG_REFERENCES` | Existing classification tags |
| `ACCOUNT_USAGE.POLICY_REFERENCES` | Existing masking/row-access policies |
| `ACCOUNT_USAGE.ACCESS_HISTORY` | Query frequency for blast-radius scoring |
| Direct `SELECT` (opt-in only) | Content sampling for GOV_034 |

## Key Design Decisions

1. **Column-name regex, not hard-coded lists.** Patterns are fully configurable
   via `pyproject.toml`. Defaults cover common PII patterns. Organizations can
   add domain-specific patterns (e.g., `(?i)patient.?id` for healthcare).

2. **Only flag the gaps.** Cross-reference against existing classification tags
   AND masking policies. If a column is already tagged + masked, it's not a
   finding. If tagged but not masked → GOV_032. If neither → GOV_030.

3. **Content sampling is opt-in.** Running `SELECT` against production tables is
   invasive. Default is off. When enabled, uses `TABLESAMPLE` for efficiency and
   limits to `sample_row_count` rows.

4. **Blast radius from ACCESS_HISTORY.** GOV_033 promotes findings to CRITICAL
   when the table is heavily queried. An unprotected SSN column on a table
   queried 1,000 times/week is materially different from one on a table queried
   once/month.

5. **Sensitivity categories align with Snowflake's classification system.**
   IDENTIFIER / QUASI_IDENTIFIER / SENSITIVE match the categories used by
   `SYSTEM$CLASSIFY` and the DATA_CLASSIFICATION_LATEST view. This allows
   seamless comparison between our heuristic detection and Snowflake's built-in
   classifier.

## TDD Requirements

Every rule requires:
1. Unit test with mock column metadata + mock tag/policy references asserting
   correct gap detection
2. Unit test: column already tagged + masked → no violation
3. Unit test: column tagged but no policy → GOV_032 violation
4. Unit test: column matching pattern but not tagged → GOV_030 violation
5. Unit test: configurable patterns from conventions override defaults

GOV_033 additionally requires:
6. Unit test: same column, high-access table → CRITICAL; low-access → stays HIGH

GOV_034 additionally requires:
7. Unit test: `enable_content_sampling=False` → rule skipped entirely
8. Unit test: mock sample data with SSN pattern → detection + finding

## Ship Definition

1. PR with all new GOV_030-034 rules
2. `make check` passes
3. Default convention patterns detect at least SSN, email, phone, DOB, salary,
   credit card, passport, password, address, IP address column name patterns
4. Manual: run against test account, verify cross-reference with existing tags
   correctly excludes protected columns

## Risks

| Risk | Mitigation |
|------|------------|
| `INFORMATION_SCHEMA.COLUMNS` is per-database, not account-wide | Iterate databases from `ScanContext.databases`; parallelize |
| Column name patterns produce false positives (e.g., `EMAIL_TEMPLATE`) | Category is INFORMATIONAL for ambiguous matches; HIGH only for strong matches |
| Content sampling on large tables is slow | `TABLESAMPLE` + row limit; opt-in only; skip tables >10GB by default |
| Organizations with non-English column names | Document that patterns are configurable; provide examples for other languages |
| `ACCESS_HISTORY` has 365-day retention but can be huge | Aggregate server-side with date filter; never fetch raw rows |
