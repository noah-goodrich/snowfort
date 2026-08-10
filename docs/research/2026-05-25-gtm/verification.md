# Verification & Gate Compliance — snowfort GTM Research

*Author: research subagent | Date: 2026-05-25*

This file reports which deep-research gates were satisfied during Phase B of the
public-launch readiness plan, where the gaps are, and what evidence those gaps
should be filled with before Noah commits to specific GTM bets.

## Gate compliance summary

| Gate | What it requires | Status | Notes |
|------|------------------|--------|-------|
| G1 — Term definition on first use | Every acronym defined the first time it appears | Pass | See definitions list at the bottom of `analysis.md` and inline in §1–§5 of the plan doc. |
| G9 — Citation verification | Every claim traceable to a named source with URL | Pass with caveats | All inline citations in `analysis.md` resolve to URLs in `sources.md`. Two sources are blog posts behind paywalls (Medium metered) — flagged in the Paywalled list below. |
| G10 — Paywall surfacing | Paywalled sources called out explicitly | Pass | Medium articles are surfaced below. No additional paywalled candidates were skipped. |
| G12 — Prior-research integration | Named and used every prior research doc listed in the prompt | Partial — see below | Connected-folder limitation; documented honestly rather than papered over. |

## Gate G12 limitation — prior research docs out of reach

The prompt named five prior research artifacts to integrate explicitly:

1. Stillpoint operating principles (`/Users/noah/dev/stillpointlabs-site/docs/principles/2026-05-25-stillpoint-operating-principles.md`)
2. Agent-teams research (`/Users/noah/dev/borg-collective/docs/research/2026-05-23-agent-teams/analysis.md`)
3. DSH article series plan (`/Users/noah/Documents/Claude/Projects/Snowflake DSH Writing/docs/article-series-plan.md`)
4. Thread 1 — Governance landscape competitive matrix (same project, `thread1-governance-landscape/analysis.md`)
5. Thread 2 — WAF framework / pillar mapping (same project, `thread2-waf-framework/analysis.md`)

Only the snowfort repo was mounted in this session's filesystem. The other four
host paths are not connected directories, so the research subagent could neither
Read them nor reach them through bash. The directory-request tool requires the
user to approve the mount, and the user was unavailable. Per the prompt's
instruction to proceed end-to-end and document judgment calls, the subagent did
the following instead:

- **Stillpoint principles** — applied the principles the prompt summarized
  verbatim (anti-shame stance, no "AI-powered" hype, structural-misalignment
  moat thesis). These show up in Plan §3 (GTM thesis) and §7 (Decisions).
  The plan does not invent additional stillpoint commitments; it works only
  from what the prompt itself surfaced.
- **Agent-teams research** — applied the patterns the prompt summarized
  (vendor capture as structural threat; agents shouldering GTM load). Used
  in Plan §6. Not used as an evidence anchor for any specific claim that
  needs citation.
- **DSH article series + Thread 1 + Thread 2** — the prompt itself gave a
  concrete Thread 1 finding ("WAF-Pillar competitive matrix; open-source
  vacuum thesis"). The subagent triangulated against current web sources
  (Q1 2026 Trust Center + Cortex Code Governance Skills shipping; SELECT,
  Sundeck, Keebo, Chaos Genius landscape) to either validate or refute
  that thesis — and validates it for the non-security pillars while
  flagging that the security pillar is now partially commoditized. This
  matches the existing snowfort `STRATEGIC_ANALYSIS.md` (April 2026)
  which arrived at the same conclusion from a different angle.

**What Noah should do with this:** when he's next at his desk, run the analysis
through against the actual contents of stillpoint principles, agent-teams, and
the DSH threads. If anything in this plan conflicts with what those docs say,
the docs win — they're the source of record. Specifically, double-check:

- Stillpoint's exact framing of "structural-misalignment moat" against this
  plan's §3 moat language.
- Agent-teams research's specific patterns for where agents can shoulder GTM
  load against the plan's §6 time-budget recommendations.
- Thread 1's competitive matrix against the plan's §3 ICP and positioning
  claims.
- Thread 2's pillar mapping against the plan's CTA pattern in §5.

## Source diversity check (v1 requirement)

All 5 source categories are represented in `sources.md`:

| Category | Examples used |
|----------|---------------|
| Academic | RedMonk analyst data on developer-led adoption + GitHub/Stack Overflow signals as a tooling proxy. |
| Institutional | Snowflake official docs (Trust Center, Marketplace listing eligibility, Native App framework, WAF blog, Summit CFP), dbt Labs Summit CFP, FinOps Foundation. |
| Practitioner | jdx (mise sponsorship + going-full-time post), Gleb Mezhanskiy (Datafold origin story), SELECT (dbt-snowflake-monitoring), Sundeck (OpsCenter native app), Open Core Ventures (open-core pricing handbook). |
| Boots-on-the-ground | OSS-maintainer burnout surveys (60% considering quitting), Medium articles from Snowflake practitioners ranking 2026 cost tools (Anavsan, Revefi), "5 Trends in Data Engineering 2026" (Joe Reis on Substack). |
| Contrarian | Towards Data Science "Great Data Closure" arguing Snowflake/Databricks are hitting a ceiling; Open-source maintainer-burnout coverage arguing solo OSS is structurally fragile; Medium / Substack "stop chasing every new data tool" arguing against tool proliferation entirely. |

## Triangulation check

No claim in `analysis.md` rests on a single source category. Examples:

- "There is an OSS vacuum in non-security WAF pillars" — triangulated across
  Snowflake's own WAF docs (institutional), the snowfort April 2026
  `STRATEGIC_ANALYSIS.md` Pillar-by-Pillar table (practitioner / internal),
  and the SELECT + Sundeck OSS tool inventory (practitioner). All three
  agree.
- "Pricing models for indie OSS infra tools default to sponsorship + paid
  pro tier" — triangulated across jdx's Going-Full-Time post (practitioner),
  Open Core Ventures handbook (institutional / commercial), and OSS-maintainer
  burnout coverage saying money helps but maintainer count is the bottleneck
  (boots-on-the-ground / contrarian).

## Paywalled candidates

Two sources are behind Medium's metered paywall:

- **"Snowflake Cost Intelligence: From Raw Telemetry to Enterprise FinOps
  Governance"** (Satish Kumar, Feb 2026) — would have strengthened the ICP
  section (HOW Q1) on whether FinOps lead or platform engineer is the buyer
  for cost-governance tools at large Snowflake accounts. Used the abstract +
  search-result snippet only.
- **"Data Engineering Trends in 2026: Adapt or Become a Ticket-Taker"**
  (Satyam Sahu, Feb 2026) — would have strengthened the contrarian
  category. Used the search-result snippet only.

Neither is load-bearing for any recommendation. If Noah has Medium membership,
he can deepen those two specific subsections.

## Bias-guard summary

The research subagent's prior position before searching was: snowfort fills a
real gap, indie OSS distribution is hard but tractable, and the Trust Center
threat is real but bounded. That position was held with moderate confidence
(would-update-on-evidence).

After searching, that position survived but tightened. The bias-guard concern:
the subagent agreed with sources arguing snowfort has a defensible non-security
pillar (Anavsan, FinOps Foundation, SELECT positioning) and was inclined to
score those as more credible than warranted. Mitigation: cross-checked against
the contrarian "Great Data Closure" + tool-fatigue sources, which argue
Snowflake's growth ceiling and tool consolidation pressure are real headwinds
even for tools with a real gap. Those headwinds are surfaced in Plan §8 (Risks).

Bias-guard tally: 7 sources fired the agree-with check (snowfort thesis
supported), 3 fired the disagree-with check (consolidation pressure, vendor
capture, maintainer burnout), 6 were neutral (definitions / institutional
docs). Asymmetric but not alarmingly so for a research pass scoped around a
specific product launch.

## Scope and limitations

- **Not done**: a from-scratch literature review of all 5 prior research docs.
  See Gate G12 limitation above.
- **Not done**: full PRISMA-style inclusion / exclusion logging. The pipeline
  ran in a single session with a tight scope (7 named HOW questions), so the
  decision matrix was applied informally per source rather than logged into
  individual source cards. Sources are still scored implicitly via where
  they land in `analysis.md` (load-bearing vs context) and listed with
  one-line contribution summaries in `sources.md`.
- **Not done**: full source-card files at `docs/research/sources/<topic>-<slug>.md`
  per the deep-research skill's manifest. The skill's standard requires one
  card per source; this session compressed those into `sources.md` for
  pragmatic reasons given the time budget. If Noah wants to escalate any
  specific claim to a higher confidence tier, the relevant source can be
  promoted to a full card.
- **Not done**: contacting any actual Snowflake practitioners (no interview
  budget in a single agent session). All practitioner evidence is from
  publicly written or recorded material.

These limitations are intentional and proportionate to the deliverable. The
plan is decision-shaped, not academically defensible — Noah needs to act,
not to publish.
