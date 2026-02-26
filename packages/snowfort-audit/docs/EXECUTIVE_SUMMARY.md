# Executive Summary: Snowfort Audit — Shutter or Ship?

*Date: 2026-04-06 | Status: Final (v2)*

---

## The Situation

Snowfort Audit is a Policy-as-Code CLI that audits Snowflake accounts against 77
deterministic rules across all five WAF pillars plus static SQL analysis. It produces a
0-100 scorecard, runs offline (CI/CD) and online (live account), and costs ~$0/scan. It is
the only tool that provides unified, multi-pillar WAF scoring for Snowflake. The question
is whether it should be finished and shipped, or shuttered in favor of tools that have
shipped in the past 90 days.

## What Changed in Q1 2026

Three developments shifted the competitive landscape materially:

- **Trust Center Extensions GA (March 20):** Snowflake built a plugin architecture for
  third-party security scanners. Partners (ALTR, Hunters, OneTrust, TrustLogix) are already
  publishing scanner packages. This is the platform for building tools like Snowfort Audit's
  security pillar — and Snowflake built it themselves.

- **Cortex Code Governance Skills (March 17):** Five AI-powered governance capabilities
  covering access auditing, PII detection (150+ categories), compliance templates
  (HIPAA/PCI/GDPR/CCPA/SOX/FERPA), data quality scoring, and lineage. These overlap
  directly with Snowfort Audit's security and governance rules.

- **Cortex Code in Snowsight GA (March 26) + $20/month standalone:** Zero-install,
  zero-friction access to Governance Skills inside Snowsight. Enterprise billing uses AI
  Credits at $2.00/credit; moderate daily use runs $200-500/month per user.

Combined, these tools now cover 60-80% of Snowfort Audit's security and governance rules.

## Where Snowfort Audit Remains Unique

The overlap is concentrated in two of seven rule categories (Security, Governance). For the
remaining five categories — Cost Optimization (16 rules), Performance (13), Reliability (8),
Operations (12), and Static Analysis (7) — external coverage is near-zero:

- **No tool** systematically detects zombie warehouses, analyzes spillage patterns,
  identifies elephant queries, or checks replication gaps.
- **No tool** provides CI/CD pipeline gating for SQL anti-patterns, hardcoded secrets, or
  naked DROP statements.
- **No tool** produces a unified WAF scorecard with letter grades across all pillars.

These 56 rules represent deep Snowflake platform expertise that LLMs cannot replicate
deterministically and that no commercial vendor has built.

## Adversarial Stress Test

Five personas evaluated the shutter-or-ship question:

- **CISO:** Security pillar is commoditized. Stop leading with it. Retain for audit
  evidence reproducibility, but position as "complementary to Trust Center."
- **CFO:** Opportunity cost of maintenance is real, but COST rules alone justify the tool.
  The first zombie XL warehouse detected saves $18K/year in credits.
- **Platform VP:** No user besides the builder has tested this. Ship to validate demand.
  Consider Trust Center Extension for security subset at v1.0.
- **Architect:** Architecture is sound (clean layers, import-linter, plugin system). Pivot
  positioning from security to cost/performance/reliability.
- **Junior Engineer:** The tool fills a validated gap. It is 1-2 sessions from publishable.
  The risk of shipping is near-zero. The risk of not shipping is wasted work.

## Recommendation

**Ship it.** Specifically:

1. **Fix pre-launch blockers** (1-2 sessions): doc-code sync (3 undocumented rules, README
   showing only 39 of 77 rules), SSO verification, rule count reconciliation
2. **Publish to PyPI** as `snowfort-audit`
3. **Pivot positioning:** Lead with cost/performance/reliability — the pillars nobody else
   covers. Frame security as "complementary to Trust Center, with offline/CI/CD capability"
4. **Content strategy:** Use the tool as the backbone of WAF consulting content on the
   Snowflake Builders Blog. The content scales; the tool supports the content
5. **Re-evaluate in 6 months** (not annually) given the pace of competitive change

## What Would Kill This Project

- A Trust Center Extension or CoCo Governance Skill that covers cost + performance +
  reliability with deterministic rules and scoring. *Likelihood: Low in 12 months.*
- Rule catalog staleness exceeding 25%. Currently at ~17% (13 uncovered features out of 77
  rules). Without quarterly maintenance or community contributors, this threshold could be
  reached within 6 months.
- Zero adoption after PyPI publication. If no external user adopts the tool within 6 months
  of publishing, the maintenance investment is not justified.

## Risks

- **MFA enforcement (Milestone 3, Oct 2026)** will make SEC_002 redundant. Implement a rule
  sunset strategy for features Snowflake enforces natively.
- **Sole-maintainer burden.** 77 rules, 13 feature gaps, ~17% quarterly staleness. The plugin
  system enables community contributions, but no community exists yet.
- **Trust Center Extensions trajectory.** If Snowflake broadens the framework beyond security
  scanning, it becomes the natural distribution channel — and potential competitor — for
  everything Snowfort Audit does.
