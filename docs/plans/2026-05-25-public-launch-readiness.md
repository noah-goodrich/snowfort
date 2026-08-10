# snowfort public-launch readiness

Date: 2026-05-25
Branch: `plan/public-launch-readiness-2026-05-25`
Author: Noah Goodrich (with research support from Claude)

## What this doc is

Two related questions, one combined plan:

1. What needs to happen for snowfort-audit to reach the next level as a product (better for Noah and a small set of invited users)?
2. What needs to happen to release it to the broader public (anyone can find it, install it, run it, get value)?

The first question is mostly engineering work. The second is mostly go-to-market work. This doc bridges both into a single decision-shaped plan.

A few terms used throughout, defined here so the doc stands alone for someone who hasn't lived in this space:

- **WAF** = Well-Architected Framework. Snowflake's six-pillar framework (Security, Cost, Performance, Reliability, Operations, Governance) for evaluating how well a Snowflake account is set up.
- **ICP** = ideal customer profile. The kind of person or company most likely to buy or adopt a tool.
- **CAC** = customer acquisition cost. What it costs in time or money to get one new user.
- **FinOps** = financial operations for cloud spend. The practice of managing and optimizing cloud costs.
- **GTM** = go-to-market. The motion of getting a product in front of the people it's for.
- **OSS** = open-source software.
- **PaC** = policy-as-code. Writing rules and policies as code that can be version-controlled and tested.
- **SPN** = Snowflake Partner Network.

## 1. The two horizons

There's a meaningful difference between "next level" and "public release," and conflating them is how launches go sideways.

**Next level.** snowfort gets sharper as a tool Noah actively uses on real Snowflake accounts. A few trusted people Noah invites also use it and feed back bugs. The README gets tightened. A handful of rules that need work get fixed. The Streamlit dashboard gets a small polish pass. The audit logs get cleaner. This is internal compounding work. It doesn't require a launch sequence, content, or a support model. Most of this work is already in motion.

**Public release.** A stranger lands on the snowfort GitHub repo from a Google search or a blog post. Inside ten minutes they install it, scan their Snowflake account, and get a scorecard that tells them something they didn't already know. They have somewhere to ask questions when they're stuck. They have some sense of who built this thing and why. Within thirty days, a few of them have suggested rule additions. None of them have ragequit because the install broke on their machine.

The "next level" work is necessary for the public release. It's not sufficient. The public release also needs distribution, support tooling, a content motion, and decisions about pricing and license that don't matter when the only user is you.

This doc treats both horizons but explicitly separates them in the checklist and calendar.

## 2. Current state vs public-ready state

### What snowfort is today

snowfort-audit is a Python CLI at v1.1.0, MIT-licensed, published to PyPI as `snowfort-audit`. It runs around 164 deterministic rules across all six Snowflake WAF pillars (Security has the most, ~26; Cost has ~35; Performance ~15; Reliability ~10; Operations ~14; Governance ~9) plus 7 static analysis rules. It runs against either a live Snowflake account (via the snowflake-connector with SSO, key-pair, or password auth) or offline against SQL files. Output is a 0-100 scorecard, a letter grade A through F, and a JSON manifest that can be consumed by CI/CD.

The CLI surface today: `snowfort login`, `snowfort audit scan`, `snowfort audit show`, `snowfort audit rules`, `snowfort audit bootstrap`, `snowfort audit demo-setup`, `snowfort audit demo-teardown`, `snowfort audit deploy-dashboard`, `snowfort audit calculator-inputs`.

Architecture is Clean Architecture with import-linter contracts enforcing the layer boundaries. The pre-merge gate requires ruff lint + mypy + pytest with coverage at or above 80%. The package is hatchling-built.

v1.1.0 also ships a Streamlit-in-Snowflake dashboard (three pages: Dashboard, Explorer, Trends), persistence of scan results into `SNOWFORT.AUDIT.SCAN_*` tables, and a one-command deploy via `snowfort audit deploy-dashboard`.

### What's in flight

The three open feature branches Noah called out in the brief turn out to be stale. Their commits have already merged to main via PRs 16, 17, and 18. The branches just haven't been deleted. No active feature work is unmerged.

No Homebrew tap exists yet. The `Formula/` directory referenced in the brief is not in the tree.

### The April 2026 real-account scan, what it surfaced

The INCLOUDCOUNSEL scan produced about 3,764 raw violations that were stripped to roughly 454 real ones once duplicates and stale items were filtered. It surfaced critical security findings the team didn't know about, and it surfaced gaps in snowfort itself: missing Cortex governance rules, missing sandbox-sprawl detection, missing share-risk coverage, and one SQL bug (SEC_008 zombie roles errors during execution). Most of those snowfort gaps are now closed in v0.4.0 and later. The SQL bug is still open.

The adversarial review pass (PR #18) closed the major architectural findings. The remaining shaky items are mostly install-flow assumptions (pip + a working keyring backend) and cross-platform auth (SSO/externalbrowser hasn't been validated on every OS Python combo).

### The readiness gap

| What works for Noah | What needs work for a stranger |
|---|---|
| Noah knows which auth flow to use | First-run wizard doesn't exist |
| Noah knows what 164 rules means | README opens with "Policy-as-Code (PaC) and Well-Architected Framework (WAF) compliance tool" — that's an in-group sentence |
| Noah ignores SEC_008 because he knows it's broken | Stranger sees a SQL error on their first scan and bounces |
| Noah can read the JSON manifest | Stranger needs the dashboard or the show command to make the JSON make sense |
| Noah knows the rule count is fuzzy across docs | Stranger sees 83 in one place, 116 in another, 164 in a third, and loses trust |
| Noah is the only one filing issues | No issue templates, no CONTRIBUTING.md, no SECURITY.md, no triage system |
| Noah doesn't expect support | Public users expect a response within a week |

The gap is real but not enormous. Most of it is documentation, install polish, and support tooling rather than missing product functionality.

### Known-shaky vs known-solid

Known-solid: the rule engine, the manifest format, the scoring math, the dashboard surfaces, the Clean Architecture layering, the test coverage, the rule taxonomy across the six pillars.

Known-shaky: SEC_008 SQL error, install on machines without keyring, cross-platform SSO, documentation rule-count consistency, install-from-scratch new-user experience, any rule added after v1.0 that hasn't been run against a real account.

## 3. The GTM thesis

This section distills the deep research in `docs/research/2026-05-25-gtm/analysis.md`. The full reasoning and citations live there. Here's the operational thesis.

**Who buys.** The buyer is a triad. The data platform engineering manager owns the decision to install. The FinOps lead owns the dollar conversation. The security architect signs off when ACCOUNT_USAGE access becomes a question. For a free OSS pip-installable tool that produces a JSON manifest for CI/CD, the install decision happens at the engineer level in an afternoon. No procurement. The lead persona is the data platform engineer who got tagged with cost optimization and is looking for something they can run today.

**What snowfort is uniquely.** "The only WAF scorecard for Snowflake." Snowflake's own Trust Center plus Cortex Code Governance Skills now cover 60-80% of snowfort's security rules for free with zero install. That's the part of the original "no one else does this" thesis that no longer holds. Where snowfort still has no real competitor is the multi-pillar scorecard. No first-party tool, no commercial tool, and no other OSS tool produces a single scored output across all six WAF pillars. The closest OSS comparables (Sundeck OpsCenter, SELECT's dbt-snowflake-monitoring) are cost-only and have no rule engine. The positioning lead should be the multi-pillar scorecard. The hook in the article-series funnel should be the cost pillar (where the dollar pain is most visible).

**How to price at v1.** Free, MIT-licensed, GitHub Sponsors button on the repo, an "available for consulting" link in the README. No pro tier at v1. The pattern reference is jdx/Mise (sponsorship plus two days a week of consulting). The constraint isn't revenue — it's Noah's time. A paid tier with a sales motion is off the table for a solo maintainer. Defer the pro-tier conversation until inbound paid-question signal arrives at least twice a week.

**How to get found.** Four channels in priority order. First, the WAF article series Noah is already writing — highest leverage, lowest marginal cost. Second, Snowflake Data Superhero amplification — institutional, already earned. Third, conference adjacency at Snowflake Summit (June 1-4, 2026, San Francisco) and dbt Coalesce (Sept 15-18, 2026, Las Vegas) — even without a speaking slot, hallway conversations and posts during the event windows are amplification opportunities. Fourth, GitHub README SEO — compounding over months, worth investing in but not the launch driver.

**The moat.** Three moats in declining order of durability. Speed (snowfort ships rules in days; Snowflake ships in quarters). Opinionated specificity (snowfort encodes a point of view; Snowflake ships generic documentation). Structural independence (Snowflake cannot credibly grade Snowflake). The third one is the durable moat. It maps directly to the Stillpoint structural-misalignment thesis and doesn't wear out the way speed eventually does.

## 4. Pre-launch checklist (prioritized)

### Must ship before any public surface goes live

1. **Rewrite the README open.** First paragraph names a stranger's problem in their own words. "Your Snowflake account is bleeding money in places you can't see. snowfort scans it and shows you where." Install command in the first 50 lines. Quickstart that gets a stranger to a scored report in five minutes.

2. **Fix the SEC_008 zombie-roles SQL error.** A v1.x launch with a known-broken rule is a credibility tax. Either fix it or disable it by default with a flag to re-enable.

3. **Reconcile the rule count across docs.** Pick one number, audit the rule registry, fix every README and CHANGELOG and STRATEGIC_ANALYSIS reference. The fuzziness (83 vs 116 vs 164) is the kind of small thing that makes a stranger quietly close the tab.

4. **Add CONTRIBUTING.md and SECURITY.md.** Both are GitHub-recognized files that lower the bar for community PRs and define how to report a security issue. Without SECURITY.md, Noah becomes the default mailbox for every vulnerability report.

5. **Enable GitHub Sponsors with the Sponsor button on the repo.** Fifteen minutes of work. One tier ($25/mo individual) plus a stretch tier ($500/mo company logo). Don't over-engineer.

6. **Write a response-time SLO into the README.** "I respond to issues within 7 days when I can. For urgent issues, here's how to flag them." Sets expectations honestly. Highest-leverage burnout-prevention move available.

7. **Auto-label GitHub issues by pillar and rule ID.** Scheduled GitHub Action that calls Claude API or uses a regex bot. Cuts triage time by something like 40% based on the OSS-maintainer research in analysis.md.

8. **One smoke-tested install path for non-developers.** Either `pipx install snowfort-audit` documented as the recommended path (handles the venv problem cleanly) or a Homebrew tap. Recommendation: pipx for v1, Homebrew for v1.x. The Homebrew tap mentioned in the brief doesn't exist yet and building it is a separate ship.

9. **A 90-second demo video or animated GIF embedded in the README.** Shows the install plus a scan plus the scorecard in real time. Highest-converting single README addition for OSS infra tools.

10. **A public landing page or doc site.** GitHub Pages off the repo or a `snowfort.dev`-style domain. Pure README is fine for v0. For a stranger-friendly launch, a styled landing page that ranks for "snowflake WAF audit" matters.

### Should ship in the first 30 days post-launch

- An issue template with the fields needed to triage faster (Snowflake edition, Python version, OS, the failing scan or rule ID).
- A GitHub Actions install matrix across Python 3.10, 3.11, 3.12 on macOS, Linux, and Windows.
- A "scan output format" doc that explains the JSON manifest field by field, with examples a CI/CD pipeline can copy.
- A first "snowfort in the wild" case-study post (Noah's own INCLOUDCOUNSEL scan, anonymized) with permission.
- Three friendly companies recruited for paid or trade-for-feedback pre-launch-like scans. Even three more real-account scans would surface the install issues a maintainer can never find alone.

### Nice to have over the next quarter

- A Snowflake Marketplace Native App version (requires SPN Select tier, multi-month application, annual partner fees — gated on whether the Marketplace listing is actually the play, see Decision #2).
- A snowfort rule SDK so the community can contribute rules without learning the internal architecture.
- A Slack or Discord community channel, only after there's signal that one is wanted.
- A formal v1.0 announcement post on Hacker News, Lobsters, and r/snowflake (timed to land after the WAF article 3 publishes).

## 5. The launch sequence

Calendar in date order. The article publication dates are best-effort estimates from the existing DSH series plan and may need adjustment.

| Date | Milestone |
|---|---|
| **May 25, 2026** | Branch + research artifacts on disk. This plan synthesized. |
| **May 26 - Jun 7** | Pre-launch items 1-7. README rewrite, SEC_008 fix, rule-count reconciliation, CONTRIBUTING + SECURITY + Sponsors button, response-time SLO, auto-label action. |
| **Jun 1-4** | Snowflake Summit 26 in San Francisco. Even without a speaking slot, hallway conversations and LinkedIn posts during Summit are amplification windows. |
| **Jun 8 - Jun 21** | Pre-launch items 8-10. pipx-first install path, demo GIF, landing page. Soft-launch v1.2.0 with the pre-launch checklist applied. |
| **Jun 22 - Jun 28** | WAF article 1 publishes. Phase 1 CTA: snowfort as a footnote. |
| **July (weekly)** | WAF articles 2, 3, 4 publish. Phase 1 transitions to Phase 2 mid-month. |
| **August (weekly)** | WAF articles 5, 6 publish. Phase 2 transitions to Phase 3 by article 6. |
| **Sep 1-7** | WAF article 7 publishes. Phase 3 CTA: explicit "run snowfort against your account this afternoon." |
| **Sep 15-18** | dbt Coalesce 2026 in Las Vegas. If no speaking slot, attend and work the booth-and-hallway pattern. |
| **Sep or Oct** | Long Game Part 4 publishes. Strongest CTA of the series. |
| **Q4 2026** | 90-day post-launch retrospective. Decide on pro tier based on inbound paid-question signal. Begin SPN Select tier application if the Marketplace listing is the play. |

The three-phase CTA escalation is the thing to get right. Phase 1 articles (1-2) mention snowfort as a footnote when WAF is being introduced. Phase 2 articles (3-5) use snowfort as the concrete example when each pillar is being dug into — with SQL snippets and manifest output shown inline. Phase 3 articles (6-7) and Long Game Part 4 close with snowfort as the recommended next step, install command and all. The reason to escalate rather than promote in every article: every-article promotion reads as marketing; escalating prominence reads as teaching.

## 6. Noah's time budget reality check

Noah is solo and ships across multiple products. The deep research on OSS maintainer burnout is unambiguous: 80% of maintainer time goes to triage, and roughly 60% of solo maintainers report considering quitting. snowfort needs to be designed to not become that.

The realistic time commitment for the first 90 days post-launch, given the pre-launch checklist gets applied: 4-8 hours per 100 active users per week for triage, issue response, and small fixes. As docs and FAQs get fed by real user questions, that drops to 2-4 hours per 100 active users per week. Above roughly 500 active users without a second maintainer or a paid tier funding part-time help, the burnout wall hits.

Where agents can shoulder GTM load specifically:

- **Issue triage.** A Dosu-style or Claude-Code-based GitHub Action auto-labels by pillar and rule ID, auto-responds to the most common questions with doc links, and flags the 10-20% of issues that actually need Noah.
- **Doc maintenance.** A scheduled agent reads new issues and proposes README and FAQ edits.
- **Article-series scheduling and posting.** An agent drafts the LinkedIn promotion post and the cross-post version per article, surfaces engagement metrics weekly, and proposes the next article's hook.
- **Rule staleness watch.** A monthly agent scans Snowflake release notes and proposes rule additions or rule updates for Noah to review.
- **Community DM-style support.** An agent in the r/snowflake and Snowflake-community Slack channels can answer install questions if and only if Noah's voice is enforced; otherwise it reads as spam and damages the brand. Only worth it after enough trust has been built.

The agent-shouldered work is a hard requirement, not a nice-to-have. Without it, public launch at the WAF-article scale runs Noah straight into the maintainer-burnout pattern the research describes.

## 7. Decisions Noah needs to make

Seven decisions. Each has options, the relevant evidence, and a recommended call.

### Decision 1: Pricing at v1

Options:
- **(a)** Free MIT CLI with GitHub Sponsors only.
- **(b)** Free CLI plus a paid hosted dashboard or hosted scan service.
- **(c)** Free CLI plus a paid custom-rule SLA for enterprises.

Evidence: jdx/Mise, Datafold, and the Open Core Ventures playbook all converge on "free first, layer pro tier when signal arrives." A pro tier at v1 requires a sales motion Noah can't staff.

**Recommended call: (a).** Add the Sponsors page now. Defer pro tier until two or more inbound paid-question signals arrive per week.

### Decision 2: Marketplace listing

Options:
- **(a)** Apply for SPN Select tier and pursue a Snowflake Marketplace listing.
- **(b)** Skip Marketplace, lean on PyPI plus Homebrew.

Evidence: SPN application is a multi-month process with annual partner fees and is gated on enterprise sponsorship. The pip-install path matches engineer-led adoption, which is snowfort's profile. Marketplace matters when the buyer is Snowsight-only.

**Recommended call: (b) for v1. Revisit in Q4 2026** if engineer-led adoption is plateauing and Snowsight-only buyers are showing up in inbound.

### Decision 3: Positioning lead

Options:
- **(a)** "The only WAF scorecard for Snowflake."
- **(b)** "Find the warehouses bleeding money."
- **(c)** "Catch the Snowflake compliance gaps."

Evidence: Trust Center has commoditized (c). Cost has competitors but no rule engine (b). The multi-pillar scorecard is unique (a). Different audiences respond to different hooks.

**Recommended call: lead with (a) in the README headline; lead with (b) in the article-series funnel hook.** Same product, different doors.

### Decision 4: Support burden model

Options:
- **(a)** Solo plus agent triage (Dosu or Claude-based bot).
- **(b)** Invite a second maintainer from the DSH cohort or from early adopters.
- **(c)** Accept the burnout risk.

Evidence: 60% of solo maintainers report considering quitting. Agent triage cuts the load by roughly 40% but doesn't eliminate it.

**Recommended call: (a) for the first 90 days. Re-evaluate at the retrospective.** If active users exceed 200, actively recruit a co-maintainer.

### Decision 5: Rule update cadence

Options:
- **(a)** Quarterly major releases with rule additions.
- **(b)** Continuous deploy with weekly patch releases.

Evidence: snowfort's own staleness analysis shows roughly 17% rule staleness per quarter without updates. Snowflake ships around three relevant features per month.

**Recommended call: (b) for individual rule additions, (a) for breaking changes.** A tool that "knows about feature X within a week" is structurally more credible than one that batches.

### Decision 6: Article-series CTA pattern

Options:
- **(a)** Promote snowfort directly in every article.
- **(b)** Escalating prominence (footnote → example → CTA).

Evidence: Datafold's launch motion plus standard B2B SaaS funnel research support escalation.

**Recommended call: (b).** Every-article promotion reads as marketing. Escalating prominence reads as teaching.

### Decision 7: Pre-launch friendly scans

Options:
- **(a)** Launch with current internal-account-only testing.
- **(b)** Recruit 3-5 friendly Snowflake-using companies for pre-launch scans (paid or trade-for-feedback).

Evidence: the April 2026 INCLOUDCOUNSEL scan surfaced an entire missing pillar (Cortex governance) and one SQL bug. Three more such scans would close most of the v1.0 sharpness gap that a maintainer can never find alone.

**Recommended call: (b).** Even three friendly scans are worth the time.

## 8. Risks worth naming

Each risk has a probability estimate, an early-signal trigger, and a mitigation.

**Vendor capture: Snowflake ships a "WAF Scanner" Native App in 2027.** Probability low for the next 12 months, medium thereafter. Early signal: Snowflake job listings for "WAF compliance engineer" or "Trust Center extension PM with cost focus." Mitigation: ship faster, stay opinionated, lean into the structural-independence positioning.

**Maintainer burnout.** Probability medium if active users grow past 200 without agent triage. Early signal: issue-response time slipping past 14 days. Mitigation: agent triage from day one, scope limits in the README, recruit a co-maintainer at the 90-day mark.

**Rule staleness vs Snowflake feature velocity.** Probability high — snowfort already runs at roughly 17% staleness per quarter. Early signal: GitHub issue "your scanner doesn't know about Cortex feature Z." Mitigation: monthly rule-addition cadence plus community PRs.

**A Trust Center extension partner ships a multi-pillar scanner.** Probability low — Trust Center extension partners are security-focused. Early signal: TrustLogix or ALTR announcing a cost-coverage roadmap. Mitigation: ship faster and lean on structural independence.

**Article series underperforms expected reach.** Probability medium — Medium readership is unpredictable. Early signal: article 1 readership under 2K in the first 30 days. Mitigation: cross-post to a Noah-owned domain, LinkedIn long-form, selective r/snowflake posts.

**PyPI install breaks on a Python version or OS Noah hasn't tested.** Probability medium — there's no public install matrix yet. Early signal: GitHub issues like "ImportError on macOS Python 3.13." Mitigation: GitHub Actions install matrix on 3.10, 3.11, 3.12 across macOS, Linux, Windows before public launch.

## 9. What this surfaces for the Stillpoint operating principles

Two things worth folding back into the stillpoint principles doc on the `feat/stillpoint-principles-2026-05-25` branch:

First, the structural-misalignment moat has a clean concrete instantiation in snowfort. "Snowflake cannot credibly grade Snowflake" is a one-sentence version of the moat that's more vivid than the abstract framing. Worth pulling in as a canonical example.

Second, the anti-shame stance overlaps with the OSS-maintainer burnout research in a specific way. The principle: "If we ship something to the public, we name our scope limits and our response time honestly, even when that costs us users. The alternative is the maintainer burnout cycle, and that's a kind of self-harm we're choosing not to participate in." This is adjacent to anti-shame but specific enough to merit its own paragraph in the principles doc.

## 10. Paywalled sources surfaced

Two Medium articles came up as potentially load-bearing for the ICP research but sit behind Medium's metered paywall. The research uses abstract and search snippet only:

- "Snowflake Cost Intelligence: From Raw Telemetry to Enterprise FinOps Governance" (Satish Kumar, Feb 2026) — would deepen ICP evidence on FinOps-lead-as-buyer at large Snowflake accounts.
- "Data Engineering Trends in 2026: Adapt or Become a Ticket-Taker" (Satyam Sahu, Feb 2026) — contrarian DE-tools framing.

Neither is load-bearing for the recommendations above. If Noah has Medium membership, those two specific subsections in `analysis.md` can be deepened.

---

The full research, source list, and gate-compliance audit are in `docs/research/2026-05-25-gtm/analysis.md`, `sources.md`, and `verification.md`.
