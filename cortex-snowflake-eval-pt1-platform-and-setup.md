# Cortex Code CLI Handoff — Snowflake Platform Evaluation (Part 1 of 2)

**Prepared for:** Cortex Code CLI
**Prepared by:** Noah Goodrich, via Claude Code
**Date:** 2026-04-14
**Part:** 1 of 2 — Strategic decisions (platform fit, account setup, OAuth, IaC tool selection)
**Companion document:** `cortex-snowflake-eval-pt2-audit-and-orchestration.md` — tactical execution
(codebase audit, DCM/DMF/Native App patterns, cross-cloud orchestration, project template). Part 2
will be drafted in a follow-up session *after* your Part 1 response is reviewed, so your answers
here will shape its question framing. You do **not** need to answer Part 2's questions here.

**Standing instruction — be the skeptic in the room.** I already have strong opinions about most
of what follows. A yes-man answer from a Snowflake agent is worth nothing to me. I want you to
**question every assumption** I've embedded in these questions, including the framing itself. If
I'm asking the wrong question, say so. If I'm biased toward a platform because I'm familiar with
it or because it's trendy, call it out. If my "already-decided" answers are wrong, push back
harder than feels polite. Every section below has an explicit **"Challenge this framing"**
subsection — use it.

---

## Why You're Being Asked

I'm a solo founder bootstrapping a portfolio of small startup apps on a tight budget. I have
significant accumulated Snowflake-adjacent work (detailed below) and I need an honest, outside
evaluation of whether Snowflake is the right foundation for this portfolio — or whether some of
these projects should live on Postgres-native providers, generic clouds, or be rebuilt entirely.

You're Snowflake's own coding agent. That's the reason I'm asking *you*: you have direct
visibility into current Snowflake product docs, pricing, and best practices that Claude Code
cannot verify as authoritatively. But that also creates a bias risk — a Snowflake agent might
default to "yes, Snowflake is the right tool" when it isn't. **I am explicitly inviting you to
argue against Snowflake where another tool wins. Recommendations of non-Snowflake platforms are
not just allowed — they are required when they're the honest answer.**

---

## Who I Am (Abbreviated Context)

- Solo founder, ADHD-aware, bootstrap budget — target is ≤$200/mo total infra cost across the
  portfolio at Stage 1, ramping only as revenue justifies.
- Strong Snowflake community ties and domain expertise, but willing to take the L on that if the
  honest answer is "use Postgres elsewhere."
- Prefer CLI-first, declarative, reproducible workflows. Prefer fewer moving parts over clever
  abstractions.
- Use Claude Code as primary development agent; Cortex Code for Snowflake-specific work.
- Portfolio orchestrated via `borg-collective` — a custom framework that manages multiple
  parallel Claude/Cortex sessions across projects. Each project gets a devcontainer, a tmux
  window, session debriefs, and a knowledge graph. This orchestration layer is **outside your
  scope** — I mention it only so you understand how new projects plug into a standard.

---

## The Portfolio (Active Projects Only)

**Project paths:**
- `wayfinderai-waypoint` → `/Users/noah/dev/wayfinderai-waypoint`
- `wallpaper-kit` → `/Users/noah/dev/wallpaper-kit`

| Project | Purpose | Snowflake status |
|---|---|---|
| `wayfinderai-waypoint` | Multi-tenant SaaS grocery manager (v0.2.0 alpha) | Planned: Snowflake Postgres BURST_XS |
| `wallpaper-kit` | AI photo enhancement SaaS, prosumer tier ($9–$49/mo) | **Evaluated and rejected** — see below |
| Future startup apps | Unknown shape; will share portfolio standards | Unknown |

**Important — `wallpaper-kit` status has changed.** An earlier version of this doc described it
as "pure Python image processing, no Snowflake code." That is no longer accurate. As of
2026-04-12:

- wallpaper-kit has a **working Postgres schema** at
  `/Users/noah/dev/wallpaper-kit/wallpaper_kit/db.py` with 350+ lines of integration tests in
  `tests/test_db.py`. Tables: `processing_runs`, `images`, `processing_attempts`, `step_results`,
  `reference_images`, `analysis_runs`. This is production persistence, not optional instrumentation.
- wallpaper-kit has a **fully-designed SPCS + Snowflake Postgres + Cortex architecture** at
  `/Users/noah/dev/wallpaper-kit/docs/snowflake_architecture.md` that was evaluated and
  **explicitly rejected** in `/Users/noah/dev/wallpaper-kit/docs/platform_consolidation.md`
  (drafted 2026-04-12).
- The current locked-in recommendation is **Supabase (auth + Postgres + storage + edge functions +
  static hosting) + Fly.io (heavy enhance worker)**. Snowflake is reserved for `wayfinderai-waypoint`
  only and is expected to be revisited as an *analytics layer* for wallpaper-kit only after it has
  ≥1K paying users.
- wallpaper-kit is mid-GTM — pricing experiments, beachhead positioning, hallucination detection
  for content moderation, pitch deck work, and closed-beta planning. The platform decision is
  load-bearing for Week 1 of the rollout.

**This changes Question 1 entirely.** Instead of "does Snowflake offer anything useful for
wallpaper-kit," the real question is: **was the rejection justified, or did we miss something?**
Please be prepared to argue for Snowflake there if the reasoning in `platform_consolidation.md`
has a hole — that's exactly the kind of pushback I'm hiring you for.

**Inventory of existing Snowflake-adjacent work** (audited by you in Part 2, listed here for
platform-fit context only):

- `/Users/noah/dev/snowflake-projects/` — large monorepo with DCM Projects IaC, medallion
  architecture, Native App scaffolding (compass-app, waypoint-app), RBAC platform (COSMERE),
  trading project (sextant), architecture linter (excelsior-architect), UI kit (stellar-ui-kit).
  Archives include budget-app (with historical Google OAuth Snowpark procedure), trading,
  wayfinder, grocery-app, waypoint-app variants.
- `/Users/noah/dev/snowfort/` — active monorepo containing a published `snowfort-audit` CLI
  (Snowflake Well-Architected Framework compliance auditor).
- `/Users/noah/dev/snowfort-old/` — archived legacy implementation with medallion + RBAC reference
  patterns.
- `/Users/noah/dev/SnowDDL/` — third-party declarative DDL management tool, cloned locally for
  evaluation as an alternative to DCM Projects.

---

## Required Reading (Attachments)

Please read these files before answering. They are input, not output — do not re-derive their
contents. When a question references one of these, use its numbers and recommendations directly.

### Waypoint (wayfinderai-waypoint) documents

1. **`/Users/noah/dev/wayfinderai-waypoint/postgres-cost-analysis-handoff.md`** — A 400-line cost
   model for WayfinderAI Waypoint's Postgres hosting decision. Covers 9 providers (Supabase,
   Neon, Railway, Render, RDS, DigitalOcean, Snowflake Postgres, Databricks Lakebase) across
   three growth stages (100 → 50,000 households) with per-household data footprints, query
   patterns, and both BYO-DB and SaaS deployment models. **Includes Snowflake Postgres pricing
   from the March 2026 Service Consumption Table** (BURST_XS at 0.0068 credits/hr → ~$10/mo
   floor; STANDARD_M at 0.0356 credits/hr → ~$78/mo Enterprise). **Includes Databricks Lakebase
   pricing** at both promotional ($0.092/CU-hr) and post-promotional ($0.184/CU-hr) rates, with
   scale-to-zero modeling. Use this as your cost input for Question 1.

2. **`/Users/noah/dev/wayfinderai-waypoint/PROJECT_PLAN.md`** — WayfinderAI v0.2.0 roadmap.
   Architecture is locked in: Snowflake Postgres BURST_XS, single instance, multi-tenant via
   `household_id` + Postgres RLS (fail-closed), Clerk for OAuth with Google + Microsoft,
   Node/TypeScript MCP server deployed to Railway, secrets via macOS Keychain → `secrets.zsh`
   → docker-compose env block. 8-session roadmap, 9 acceptance criteria. **I am not asking you
   to redesign this — I am asking whether the platform choices embedded in it (Snowflake
   Postgres specifically) are defensible given the cost analysis, and whether the whole
   architecture is biased because I'm a Snowflake person.**

### Wallpaper-kit platform-decision documents (all 2026-04-12)

3. **`/Users/noah/dev/wallpaper-kit/docs/platform_consolidation.md`** — The decisive
   recommendation that locks wallpaper-kit onto Supabase + Fly.io and explicitly excludes
   Snowflake from the MVP. Argues Snowflake is "a data warehouse first, container host second"
   and wallpaper-kit is the inverse, with a $60/mo floor on Snowflake (BURST_XS Postgres + kept-warm
   SPCS pool) vs. $0 floor on Supabase. Also includes a 90-day rollout schedule and a stage-by-stage
   cost table. **This is the decision you are being asked to validate or break.**

4. **`/Users/noah/dev/wallpaper-kit/docs/snowflake_for_bootstrappers.md`** — Longer-form versus
   analysis comparing Snowflake, Supabase, Cloudflare, and AWS for a bootstrapped solo-founder
   SaaS. Has a "workload profile" table that breaks wallpaper-kit into seven distinct pieces
   (frontend, auth, photo storage, OLTP metadata, heavy worker, billing, analytics) and
   concludes Snowflake is world-class at the one piece (analytics) that doesn't matter until
   after revenue.

5. **`/Users/noah/dev/wallpaper-kit/docs/snowflake_architecture.md`** — The full engineering
   design for the *rejected* Snowflake-only architecture (SPCS + Snowflake Postgres + Cortex +
   Stages). This exists so you can audit the architecture and tell me if we designed Snowflake
   wrong for this workload, or if the shape is genuinely bad regardless of how we designed it.

6. **`/Users/noah/dev/wallpaper-kit/docs/executive_meeting_gtm.md`** and
   **`/Users/noah/dev/wallpaper-kit/docs/pricing_experiments.md`** — GTM context: prosumer
   photographer beachhead, $9–$49/mo pricing tiers, CAC/LTV modeling, photo-ownership and GDPR
   questions. Skim for platform implications (billing/webhooks, content moderation).

7. **`/Users/noah/dev/wallpaper-kit/wallpaper_kit/db.py`** and
   **`/Users/noah/dev/wallpaper-kit/tests/test_db.py`** — The actual Postgres schema and tests
   that exist today. Confirms wallpaper-kit already has real DB needs, not hypothetical ones.

### Snowflake-projects conventions and security (**with caveat**)

8. **`/Users/noah/dev/snowflake-projects/docs/CONVENTIONS.md`** — **Caveat: partially stale.**
   Last updated 2025-10-08. Establishes `{ENV}_{OBJECT}` prefix naming, explicit warehouse
   sizing in names (`DEV_INGESTION_MEDIUM`), minimal `manifest.yml`, Jinja restrictions. **The
   "whimsical" role and database names it documents (COSMERE, HOID, THAIDAKAR, Stormlight-
   Archive-inspired layer names) have since been abandoned in favor of content-based names
   matching the actual purpose of each object.** I'll expand on this in Question 2. Treat the
   structural patterns in this doc as still current, but ignore the specific whimsical names —
   those are a historical artifact.

9. **`/Users/noah/dev/snowflake-projects/archive/snowfort/docs/SECURITY.md`** — Target-state
   security model. Role hierarchy: `ACCOUNTADMIN → SYSADMIN → ADMIN → {ENV}_{PROJECT}_DEPLOYER`
   with database roles (`SCHEMA_ADMIN`, `READ_WRITE`, `READ_ONLY`). RSA-key auth only for
   service users, 90-day rotation, Snowflake Secrets as primary secret storage with GitHub
   Secrets as supporting CI/CD storage. Account-level objects (Network Policies, Resource
   Monitors, Integrations, External Access Integrations) restricted to admin/ACCOUNTADMIN only.
   **Also 2025-vintage — I'd like you to validate against current Snowflake guidance.**

10. **`/Users/noah/dev/snowflake-projects/docs/`** — Also contains `DEPLOYMENT_GUIDE.md`,
    `DEPLOYMENT_STAGES.md`, `SCHEMA_DEFINITION_STANDARD.md`,
    `SNOWFLAKE_NATIVE_APP_COMPREHENSIVE_GUIDE.md`, `SNOWFLAKE_API_REFERENCE.md`, and
    `MIGRATION_FROM_PYTHON.md`. Skim for the four-stage deployment pattern referenced in
    Question 4.

---

## Response Format Expected

- A single markdown document, one top-level section per question (Q1, Q2, Q3, Q4)
- Each recommendation must include rationale + a specific number (cost, complexity, effort) where
  the data supports it
- Anti-recommendations are welcome and expected — call out every case where a non-Snowflake tool
  wins cleanly
- For any Snowflake feature or pattern you recommend, cite the current Snowflake doc URL so I can
  verify
- If anything in the required reading is outdated relative to current Snowflake docs (CONVENTIONS
  and SECURITY were written 2025-10-08), flag it but do not rewrite those docs — just note what
  has moved
- Wrap at 120 characters per line

---

# Question 1 — Platform Fit: The Honest Evaluation

**The question:** For the three categories below, is Snowflake the right foundation, and if so
*which part* of Snowflake? Use the cost analyses as input and give an anti-Snowflake
recommendation where one is warranted — but also push *for* Snowflake where my already-made
decisions look biased against it.

## Required taxonomy in your answer

Please distinguish these three Snowflake offerings — they are often conflated and mean different
things for this evaluation:

- **Snowflake Postgres** (Feb 2026 GA): transactional, wire-compatible PostgreSQL running on
  dedicated instances inside Snowflake. Billed via credits/hour. BURST_XS ≈ $10/mo floor per the
  cost analysis. This is a *managed BYO-DB replacement*, not a data platform.
- **Snowflake AI Data Cloud**: the analytics platform — warehouses, medallion, Cortex ML /
  Cortex AISQL / Cortex Search, Streamlit-in-Snowflake, Notebooks, Openflow, Snowpark.
  Credit-based, bursty workloads, serverless options. This is where ML pipelines and analytics
  live. **Snowpark Container Services (SPCS)** — with GPU pools and External Network Access —
  is the container-hosting sub-feature that matters for wallpaper-kit's rejected architecture.
- **Snowflake Native Apps**: a distribution mechanism for shipping applications that run inside a
  customer's Snowflake account (via application package + consumer install). Useful when your
  customers are already Snowflake accounts.

Any recommendation must be explicit about *which of these three* it refers to. Conflating them is
the main way this evaluation goes wrong.

## Context for Q1 — wayfinderai-waypoint

- Grocery management SaaS. 13-table schema. ~10 MB/household over 5 years. ~175 queries/week/
  household, entirely bursty (heavy weekends, idle weekdays). Auth via Clerk (Google + Microsoft).
- `PROJECT_PLAN.md` has Snowflake Postgres BURST_XS locked as the Stage-1 choice. **I want you
  to tell me whether that choice is actually defensible or whether I picked it because I'm a
  Snowflake person and it felt loyal.** The honest answer may be Neon, Supabase, or Lakebase —
  cite specific crossover points from the cost analysis.
- Lakebase's scale-to-zero is a real advantage for bursty grocery traffic on paper; the cost
  analysis models both promotional ($0.092/CU-hr) and post-promotional ($0.184/CU-hr) rates.
  Does Lakebase actually beat BURST_XS in practice at Stage 1, Stage 2, Stage 3?
- **Key bias to examine:** I keep choosing Snowflake Postgres here partly because "I know
  Snowflake" and partly because it lets me keep waypoint inside one platform. Those might be
  the wrong reasons. If Neon's free tier carries Stage 1 with zero friction and Neon's Scale
  plan carries Stage 2 with half the cost, I need to hear that plainly.

## Context for Q1 — wallpaper-kit (**the decision to challenge**)

- AI photo enhancement SaaS. Prosumer tier ($9–$49/mo). Current decision: **Supabase + Fly.io,
  Snowflake explicitly rejected.** See `platform_consolidation.md` for the rationale.
- The rejection rationale in `platform_consolidation.md`:
  1. Mental-model mismatch — Snowflake is a data warehouse with container services bolted on;
     wallpaper-kit is a consumer SaaS with a container worker bolted on. Inverted shapes.
  2. $60/mo floor on Snowflake (BURST_XS Postgres + kept-warm SPCS pool) vs. $0 floor on Supabase
     + Fly.io.
  3. No bootstrapper community on Snowflake. Public case studies are Capital One / BlackRock /
     DoorDash, not consumer SaaS.
  4. Photo UX friction — Snowflake Stages not built for "browser drag-and-drop 10MB JPEG → watch
     progress bar." You'd end up building presigned uploads against an underlying S3 bucket,
     which defeats the purpose.
  5. SPCS cold starts on bursty consumer traffic — either keep min-1 warm ($50/mo idle) or eat
     10–30s cold start on every job.
- **The design that was rejected** is documented at `snowflake_architecture.md`. It is not a
  napkin sketch — it's a full engineering design for SPCS + Snowflake Postgres + Cortex + Stages.
  If the rejection was *because the design was wrong*, not because the platform is wrong, I
  need to know.
- **The real ongoing question wallpaper-kit is still asking:** "where do we run Postgres?" is
  open — Supabase is the leading answer but not committed. If Cortex has a reason to push
  Snowflake Postgres specifically (not the full SPCS architecture, just the DB layer) for
  wallpaper-kit's OLTP needs, now is the moment to make that case.
- **Potential Snowflake role for wallpaper-kit post-revenue:** `platform_consolidation.md` says
  "revisit Snowflake as an analytics layer once wallpaper-kit has ≥1K paying users." That's
  the concession. Is the concession right? What would the pipeline look like? (Fivetran?
  Supabase CDC → Snowpipe Streaming? Direct dbt on Postgres shadow?) When does the analytics
  layer become worth adding?

## Context for Q1 — future startup apps

- Unknown shape. The portfolio standard needs a decision tree that lets me route a new idea to
  the right foundation in < 5 minutes without running another full evaluation.
- The output should be concrete: "if the new project has characteristic X, use Snowflake;
  otherwise use Supabase/Neon/etc." Not a decision matrix with ten axes — a short set of
  sharp rules.

## What I want from Cortex

- **For wayfinderai-waypoint:** A defensible answer to "is Snowflake Postgres BURST_XS the right
  choice here, or does Neon / Supabase / Lakebase / Railway / something else win?" Numbers from
  the cost analysis at Stage 1 (100 households), Stage 2 (1,000 households), and Stage 3
  (10,000 households). Identify crossover points. **Address my bias directly — am I picking
  Snowflake because it's right or because I know it?**
- **For wallpaper-kit:** An honest verdict on the `platform_consolidation.md` rejection. Agree,
  disagree, or "agree with the rejection but for different reasons." If you disagree, walk
  through which of the five rejection arguments above is wrong. Specifically:
  - Is SPCS's mental-model mismatch real, or was the design bad?
  - Is the $60/mo floor avoidable with scale-to-zero or a different instance choice?
  - Is the "no bootstrapper community" objection overstated if Cortex Code CLI itself is the
    answer to that objection?
  - Does Snowflake Stages + presigned URL tooling actually exist today in a way I missed?
  - What does the right hybrid look like — is there a case for Supabase-for-auth-and-storage
    but Snowflake-Postgres-for-OLTP, or does that just give you the worst of both?
- **Post-revenue analytics layer for wallpaper-kit:** If the MVP is Supabase + Fly.io, and we
  add Snowflake later as analytics, what's the right pipeline and when does it earn its keep?
- **For future startup apps:** A short set of "when is a new project a Snowflake project"
  decision rules (not a decision matrix).

## Challenge this framing

- Am I conflating "is Snowflake right for this app" with "is Snowflake right for this founder
  right now"? Those might be different answers. Call it out if so.
- Is my three-way Snowflake taxonomy (Postgres vs. AI Data Cloud vs. Native Apps) actually the
  right decomposition, or am I missing a dimension that matters more (e.g., pricing
  commitment models, edition tiers, Enterprise-only features I can't use)?
- The wallpaper-kit rejection doc leans heavily on "mental-model mismatch." That's a soft
  argument. If you think it's wrong, say so — is the "consumer SaaS on Snowflake" pattern
  actually viable with the right architectural guidance, and I just didn't find it?
- I'm treating waypoint as "already locked to Snowflake Postgres" and wallpaper-kit as
  "already locked to Supabase." Should I actually reopen one of those decisions?

## Anti-asks

- **Do not re-derive the cost model** — use the pricing tables already in the cost analysis.
- **Do not rewrite any existing document** — validate or flag, don't replace.
- **Do not default to "use Snowflake"** — if Neon's free tier beats Snowflake Postgres at 100
  households, say so loudly.
- **Do not default to "don't use Snowflake" either** — if my bias is against Snowflake for
  wallpaper-kit and the rejection has holes, push back just as hard in the other direction.
- **Do not treat "Snowflake Postgres" and "SPCS" and "Cortex" as the same decision.** Wallpaper-kit
  rejected SPCS + Postgres + Cortex as a bundle. A different answer might be "reject SPCS but
  keep Postgres."

---

# Question 2 — Multi-Project Account Setup Best Practices

**The question:** What's the canonical Snowflake account architecture for a solo founder hosting
5–20 small projects in a single account, and how should that architecture evolve as the portfolio
grows to real revenue?

## Naming convention update — read this first

`CONVENTIONS.md` documents a whimsical, Stormlight-Archive-themed naming vocabulary — `COSMERE`
as the admin database, `HOID` as the platform-administration role, `THAIDAKAR` as the CI/CD
infrastructure role, and Cosmere-inspired names for medallion layers. **Those names have been
abandoned.** The current policy is: **names should describe what the object is, not reference
a book series.**

The new pattern is content-based naming. For example, the admin platform for the `snowfort`
project is now named with the project itself — a `SNOWFORT` database, a `SNOWFORT` role, a
`SNOWFORT` user. For a fresh project, the admin objects would be named after the project or
the component they administer. Whimsy is out. Descriptive is in.

**This means:** please do not bless the whimsical names in CONVENTIONS.md. Instead, validate (or
challenge) **content-based naming** as a principle, and give me Snowflake's current recommended
pattern for naming admin databases, platform roles, CI/CD roles, and service accounts in a
multi-project account. The structural patterns in CONVENTIONS.md (`{ENV}_{OBJECT}` prefix,
warehouse sizing in names, minimal manifest) are probably still right; I want you to focus on
challenging or confirming those *structural* rules rather than the specific names.

## Context for Q2

- I currently have one Snowflake account. I want to keep it that way for as long as reasonable.
  Creating a new account per project is not on the table — cost, operational overhead, and lack
  of a real isolation need kill that option at my scale.
- `snowflake-projects/docs/CONVENTIONS.md` establishes structural naming rules I believe are
  still correct: `{ENV}_{OBJECT}` prefix (`DEV_BRONZE`, not `BRONZE_DEV`), explicit warehouse
  sizing in names (`DEV_INGESTION_MEDIUM`), business-function warehouses
  (`INGESTION`, `REVOPS`, `FINANCE`, etc.), minimal `manifest.yml` with conventions over
  configuration, Jinja restricted to truly identical objects. **I want you to validate those
  structural rules** against current Snowflake guidance.
- `SECURITY.md` in `archive/snowfort/docs/` establishes an RBAC hierarchy. I'll refer to it
  here in abstract terms rather than citing the specific whimsical names: an emergency-only
  account admin, a system admin, a platform admin role for humans, per-project deployer roles,
  and three-tier database roles (`SCHEMA_ADMIN`, `READ_WRITE`, `READ_ONLY`). Validate the
  *structure* against current Snowflake Zero Trust / least-privilege guidance; I don't need
  you to preserve specific names.
- Most of my projects are *small*. `wayfinderai-waypoint` is targeting 100 households at Stage 1.
  The three-environment pattern (DEV/STG/PRD) that's standard in enterprise Snowflake may be
  overkill when a project has zero customers and one developer. **I want an opinion on when a
  small project earns its third environment.**
- Cost attribution matters more to me than access isolation at this stage — I want to be able to
  answer "how much did `<project>` cost me last month?" in one query.

## What I want from Cortex

- **Naming:** Validate (or challenge) content-based naming as the principle. Give me Snowflake's
  current recommended pattern for admin database name, platform-administration role name,
  CI/CD role name, and service-account naming in a multi-project account. Cite doc URLs.
- **Database/schema layout:** For a multi-project account, should I use database-per-project,
  schema-per-project inside a shared database, or some hybrid? Trade-offs for cost attribution,
  RBAC, and cross-project queries? Does the medallion pattern (shared BRONZE/SILVER/GOLD
  databases) work when multiple apps each have their own data concerns, or should application
  projects stay completely isolated from analytical projects? Specifically: should waypoint
  and a future grocery-analytics project share a medallion, or should each be fully isolated?
- **Warehouse strategy:** Does the business-function warehouse pattern (one `{ENV}_{FUNCTION}_{SIZE}`
  warehouse reused across projects) still make sense for a small portfolio, or is per-project
  warehouses better for cost attribution? At what project count does the answer flip? Is XSMALL
  still the right default for a new project with no customers yet?
- **Environment count:** Under what conditions does a new project earn DEV, DEV+PRD, or full
  DEV+STG+PRD? I want a decision rule I can apply per-project.
- **Cost attribution:** What's the current canonical way to attribute cost per project in a
  multi-project account — query tagging, resource monitors per project, database-level tagging,
  or account usage views? Which give me "cost per project per month" at my scale **without
  requiring Enterprise edition**?
- **Validate structural CONVENTIONS rules:** Confirm or challenge the `{ENV}_{OBJECT}` prefix,
  the size-in-the-name warehouse naming, the business-function warehouse vocabulary, and the
  minimal-manifest philosophy. Flag anything Snowflake has moved on since 2025-10-08.
- **Validate RBAC structure:** Confirm or challenge the hierarchy (account admin → sysadmin →
  platform admin → per-project deployer → database roles). Flag any gaps relative to Snowflake's
  current Zero Trust / least-privilege guidance.

## Challenge this framing

- **Is one-account-for-everything actually the right call at my scale**, or should I at least
  have a separate account for production vs. dev? I've been assuming one account to minimize
  overhead. Tell me if that's wrong.
- **Is my "small project doesn't earn three environments" intuition right**, or is shipping a
  new project without STG a foot-gun that catches up with me at the first real customer
  incident? Push back if I'm optimizing the wrong axis.
- **Is content-based naming actually the right principle**, or am I just reacting to the
  whimsical system by picking the opposite extreme? Is there a middle ground — a minimal shared
  vocabulary (`ADMIN`, `PLATFORM`, `DEPLOYER`, etc.) that's both descriptive and portable across
  projects?
- **Cost attribution obsession:** I'm spending cognitive cycles worrying about per-project cost
  attribution on a portfolio that costs maybe $60/mo total. Is this premature and am I better
  off just reading `SNOWFLAKE.ACCOUNT_USAGE` manually when I actually need to know?

## Anti-asks

- **Do not propose a multi-account setup** — that's a non-starter at my scale (but push back if
  you think I'm wrong about that; see "challenge this framing" above).
- **Do not recommend Enterprise-only features** unless Standard edition genuinely can't do the
  job, and flag it explicitly when you do.
- **Do not rewrite CONVENTIONS.md or SECURITY.md** — review and flag, don't replace.
- **Do not preserve whimsical names** in your recommendations — they're gone.

---

# Question 3 — OAuth / OpenID Identity & Federation

**The question:** What's the canonical 2026 pattern for setting up Snowflake account-level
OAuth/SAML federation with Google Workspace, Microsoft Entra, and arbitrary OpenID providers,
and how does that differ from the application-level OAuth that `wayfinderai-waypoint` needs?

## Context for Q3

- **Two distinct OAuth needs** exist in this portfolio, and I need the recommendation to separate
  them clearly:
  1. **Account-level federation:** "I" (the human admin) and any future team members need to sign
     into Snowflake itself via Google Workspace or Microsoft Entra rather than username/password.
     Also eventually: machine users that authenticate *into* Snowflake from external services on
     behalf of a user.
  2. **Application-level OAuth (wayfinderai-waypoint):** The *app* needs to authenticate *users*
     (household owners) via Google + Microsoft so the MCP server can validate a JWT and set an
     RLS session variable on the Postgres connection. This is Clerk in front of the MCP server —
     Snowflake is downstream of Clerk and has no direct role in user-facing auth. **But I want
     your opinion on whether that's the right split, or whether Snowflake's own OAuth support
     should be doing this work.**
- **Existing implementations in the repo:** There is a historical Google OAuth Snowpark Python
  procedure in `/Users/noah/dev/snowflake-projects/archive/budget-app/` and
  `/Users/noah/dev/snowflake-projects/archive/snowfort/snowfort/shared/services/authentication/strategies/oauth.py`.
  These are 2024–2025 vintage. **I want your opinion on whether that Snowpark-procedure pattern is
  still recommended for any use case, or has been superseded.**
- **There is also a GitHub OAuth security integration pattern** in
  `/Users/noah/dev/snowflake-projects/archive/budget-app-legacy/init.sql` (API_AUTHENTICATION with
  AUTH_TYPE = OAUTH2, pointing to github.com/login/oauth) used to wire DCM projects to Git. This
  is a *different kind* of OAuth — an outbound API auth, not user sign-in — and I'd like you to
  clarify where it fits in the taxonomy.
- **SCIM provisioning:** Nice to have, but the team is 1 person for now. I need to know if it's
  worth the setup cost at that scale, and at what team size it starts to earn its keep.
- **RSA key auth for service users:** SECURITY.md specifies RSA keypair auth with 90-day rotation
  for all service users and no passwords. Confirm this is still current Snowflake best practice
  or flag what's changed.

## What I want from Cortex

- **A decision tree for the three OAuth flavors** I'll need: user-to-Snowflake (human admin sign-in
  via Google/Microsoft IdP), app-to-Snowflake (user delegating an app like a BI tool to query
  Snowflake on their behalf), and service-to-Snowflake (machine user executing queries). For each,
  recommend the current canonical Snowflake feature: External OAuth, Snowflake OAuth, SAML2,
  Security Integrations, or something else. Include doc URLs.
- **The canonical setup for Google Workspace and Microsoft Entra** as IdPs for user sign-in today.
  Include the minimum SQL and whatever IdP-side config is required. Assume I'm starting from a
  fresh Standard-edition account with no existing integrations.
- **A verdict on the wayfinderai-waypoint auth architecture:** Clerk-in-front-of-MCP-server with
  Snowflake Postgres behind, vs. pushing user auth into Snowflake OAuth directly. Which is right
  for this shape of app, and why?
- **A verdict on the 2024–2025 Snowpark OAuth procedure pattern** found in the archive — still
  recommended, superseded, or actively discouraged?
- **SCIM recommendation:** skip at team-of-1, add at team-of-N (tell me N).
- **RSA key rotation:** confirm 90-day rotation is still the recommendation, or flag the current
  number. If there's a more modern alternative (key pair authentication with automatic rotation,
  workload identity federation, etc.), point at it.

## Challenge this framing

- **Clerk-in-front-of-MCP-server might be a trendy choice.** I picked Clerk because it's what
  indie-hacker Twitter recommends and because their OAuth + JWT + SCIM story is turnkey. If
  Snowflake's own OAuth support would do this better — or if a cheaper alternative (Auth0,
  Supabase Auth, WorkOS, Stytch) would — push back.
- **Is "Snowflake is downstream of Clerk" the right split at all**, or am I putting auth in the
  wrong layer by keeping it outside the database? Postgres RLS depends on the MCP server
  setting a session variable correctly every request. That's a footgun. What does Snowflake
  recommend for multi-tenant RLS with externally-minted JWTs today?
- **Am I overrating RSA-key rotation?** The 90-day-rotation story from SECURITY.md is 2025
  vintage. Is there a less-fiddly 2026 answer (workload identity federation, ephemeral
  tokens, automatic rotation)?
- **Do I even need federated sign-in at my scale** (one human admin)? Or is username/password +
  MFA fine for the human and RSA keys for the machines, and am I over-engineering the IdP
  story for a future team that may never arrive?

## Anti-asks

- **Do not walk me through a full tutorial** — I want the decision tree and the minimum SQL.
- **Do not recommend a feature that's Enterprise or Business Critical edition** unless Standard
  genuinely can't do the job, and flag it explicitly when you do.
- **Do not conflate user auth with service-account auth** — the three OAuth flavors above must be
  treated as three separate decisions.

---

# Question 4 — IaC Tool Selection: Terraform vs DCM Projects vs Permifrost vs ???

**The question:** For a Snowflake account hosting 5–20 small projects, what is the **minimum
viable tool stack** that covers every object type I need to manage declaratively, and where
are the gaps? Specifically: what does Terraform manage, what does DCM Projects manage, where
do they overlap, where do they conflict, and what tools fill the gaps neither covers?

## Why this question is framed differently than it was before

An earlier draft of this doc framed the IaC question as "DCM Projects vs. SnowDDL vs. raw SQL."
That framing was wrong. I don't actually trust SnowDDL enough to bet the portfolio on it — it's
a third-party tool with a single maintainer and limited community adoption. The tools I'm
willing to bet on are:

- **Terraform** with the official `Snowflake-Labs/snowflake` provider (a real IaC tool with a
  real community, used across the entire cloud industry, and the one non-Snowflake-native
  option I actually trust for production infra).
- **DCM Projects** (Snowflake-native, covers object-level DDL well, ties to Git Integration,
  `snow dcm plan` for dry-run).
- **Permifrost** (a permissions-focused tool — GitLab's open-source RBAC-as-code framework for
  Snowflake). Recently on my radar. I know almost nothing about its current state.
- **Whatever else you know about** — `schemachange`, Titan (the newer IaC tool from the
  ex-Snowflake folks), Flyway, Liquibase, dbt, etc. I want the honest answer, not the "pick from
  this menu" answer.

## What I'm trying to understand

The core question isn't "which tool wins" — it's **which tool manages which object classes,
where the boundaries are, and how the tools compose.** My mental model is:

- **Terraform** is good at account-level infra that doesn't change often — databases, schemas,
  warehouses, resource monitors, network policies, integrations (storage, API, Git), external
  functions, roles at the account level. It's the tool cloud engineers reach for first.
- **DCM Projects** is good at object-level DDL inside a database — tables, views, functions,
  procedures, streams, tasks, pipes, dynamic tables, semantic views. It's the Snowflake-native
  tool with first-party `snow dcm plan` dry-run.
- **Permifrost** (or similar) is good at the complex RBAC graph — grants, role hierarchies,
  database roles, object-level privileges — which both Terraform and DCM Projects handle, but
  which gets unwieldy fast in either when you have many roles and many databases.

**I don't know if that mental model is right.** That's exactly what I want you to validate or
blow up.

## Context for Q4

- There is **existing Terraform scaffolding** in my workspace at
  `/Users/noah/dev/snowflake-projects/snowarch/packages/snowarch-scaffold/templates/admin/terraform/`
  — `bootstrap/main.tf`, `variables.tf`, `backend.tf`, and modules for network/storage/iam/compute.
  **This is AWS Terraform, not Snowflake Terraform.** It manages the cloud-side infra that
  surrounds a Snowflake account (S3 buckets for external stages, IAM roles for storage
  integrations, VPCs for PrivateLink). There's no `snowflake_*` Terraform resources in play yet.
- DCM Projects is in active use across `snowflake-projects/` — medallion, sextant, compass-app,
  waypoint-app, and the admin platform all deploy via `snow dcm plan` / `snow dcm deploy` with
  four-stage deployment pattern (init.sql → admin DCM → app DCM → apply.sql) documented in
  `snowflake-projects/docs/DEPLOYMENT_STAGES.md`.
- Permifrost is not in use anywhere in my workspace today. I'm curious if it's worth adding
  or if DCM Projects + Terraform cover grants well enough.
- I haven't adopted dbt yet but expect to for any transformation work that lands in a medallion.
- The four-stage deployment pattern in CONVENTIONS.md was written 2025-10-08 — **validate
  whether it's still current Snowflake canonical practice or has moved.**
- **On-ramp constraint:** my primary constraint is "minimum-viable IaC for a brand-new project
  on day 1." A new app in this portfolio starts with zero tables and one developer. I need
  the gentlest path from "nothing" to "running in DEV" that doesn't ship tech debt to production.

## What I want from Cortex

- **A clear division-of-labor recommendation:** for each Snowflake object class (database,
  schema, warehouse, resource monitor, network policy, storage integration, external function,
  git repo, role, database role, user, table, view, procedure, function, stream, task, pipe,
  dynamic table, semantic view, grant), tell me which tool in my candidate stack is the right
  home. A table would be fine.
- **Terraform vs DCM Projects head-to-head:** on the overlap zones (databases, schemas,
  warehouses, roles, grants), which tool wins and why? Under what conditions would the answer
  flip? Cite specific provider resource coverage — the `Snowflake-Labs/snowflake` provider has
  known gaps; call them out.
- **A verdict on Permifrost**: is it the right tool for managing RBAC at scale in a
  multi-project account today, or has its functionality been absorbed by DCM Projects / the
  Terraform provider / something else? If Permifrost is the answer, tell me that. If it's
  obsolete, say so.
- **What other tools am I missing?** If there's a better RBAC-as-code tool, a better migration
  tool, a better drift-detection tool — name it and give one paragraph on why. `schemachange`,
  Titan, dbt, Flyway, Liquibase, Chaos Genius, or whatever else you know about.
- **The "minimum viable IaC" answer:** for a brand-new project starting today, what are the
  minimum files and tools I need on day 1? Should it be "just DCM Projects," "just Terraform,"
  "both from day 1," or "DCM Projects now, Terraform when you outgrow it"?
- **Drift detection:** in a portfolio where multiple developers and agents might touch the
  account, what's the best drift-detection story? Does Terraform's `plan` catch drift DCM
  Projects' `plan` misses? Does either tool detect manual changes made via the Snowflake UI?
- **Validate the four-stage deployment pattern**: is it still current Snowflake guidance for
  DCM Projects, or has DCM evolved? Cite the current doc URLs.
- **dbt's place:** is dbt for *transformation* (models + tests on data already in Snowflake)
  and Terraform/DCM for *infrastructure* (databases, schemas, warehouses, roles)? Or does
  one subsume the other in Snowflake's current guidance?
- **On-ramp recommendation:** concrete file layout for a brand-new project's day-1 IaC.

## Challenge this framing

- **Is my trust in Terraform actually justified?** I like Terraform because it's the industry
  standard and because the `snowflake_*` provider is maintained by Snowflake Labs itself. But
  the Snowflake provider has historically lagged Snowflake feature releases by months. Is
  Terraform-for-Snowflake actually *worse* than DCM Projects for a solo founder who can't
  afford to wait six months for provider support of a new feature? Push back on my Terraform
  bias if you think it's wrong.
- **Is "Permifrost as the RBAC tool" even right?** I added Permifrost to this evaluation
  because I heard about it recently. If it's obsolete, or if its functionality has been
  absorbed by DCM Projects or the Terraform provider, say so and drop it from the stack.
- **Am I wrong to avoid SnowDDL?** I'm avoiding it because it's a third-party tool with a
  single maintainer. That's a defensible policy but it means I'm passing on a tool that might
  be legitimately better. Make the case for including it if you think I'm wrong.
- **Is the "minimum viable tool stack" framing wrong at all?** Maybe the answer isn't "pick
  three tools and have them compose" — maybe it's "use one tool that does 90% and accept
  that 10% is manual SQL in a runbook." Push back if a one-tool answer actually wins.
- **Am I underestimating dbt?** dbt started as a transformation tool but has absorbed more
  and more responsibilities. In 2026, is dbt actually the right home for a significant chunk
  of what I'm assigning to Terraform / DCM Projects?

## Anti-asks

- **Do not write a tutorial for any tool** — I want the routing decision, not a how-to.
- **Do not include SnowDDL as a primary contender** unless you're specifically making the case
  that I'm wrong to avoid it (see "challenge this framing").
- **Do not rewrite the CONVENTIONS.md four-stage pattern** — validate or flag, don't replace.
- **Do not treat "DCM" as synonymous with "DCM Projects"** — DCM is the broader database change
  management concept; DCM Projects is the specific Snowflake feature. Be precise about which
  you mean.
- **Do not recommend a tool I haven't named unless you're explicit about why it beats the
  named candidates.** And don't recommend tools Snowflake has publicly deprecated.

---

## Closing Notes

- This is **Part 1 of 2.** Part 2 will ask you to do a concrete codebase audit of
  `/Users/noah/dev/snowflake-projects/` (medallion, sextant, compass-app, waypoint-app,
  excelsior-architect, stellar-ui-kit, snowarch, the archive of historical projects), plus
  `/Users/noah/dev/snowfort/` (the active WAF auditor monorepo) and
  `/Users/noah/dev/snowfort-old/` (archived legacy implementation). Part 2 will also evaluate
  DCM Projects and DMF patterns in practice, recommend a cross-cloud orchestration strategy for
  Snowflake + Supabase + Fly.io + Railway + AWS + secrets, and propose a canonical project
  template for scaffolding new projects. **Your answers to Part 1 will shape Part 2's
  questions**, so please make the strategic recommendations here sharp enough that Part 2 can
  start from them as inputs.
- **Push back wherever you disagree with the framing of a question.** Every question has a
  "Challenge this framing" section for exactly this purpose. If I've conflated concepts or
  asked the wrong question, say so. Part 2 can be retargeted based on that feedback.
- **Don't be polite about it.** I already have a Claude Code that will happily agree with me
  when I'm wrong. The reason I'm asking *you* is that you're a Snowflake agent who can argue
  with authority on the Snowflake side, but also — if you're honest — tell me when I'm using
  Snowflake wrong. Both halves matter equally.
- Cite Snowflake doc URLs liberally — this evaluation needs to be verifiable against current
  docs six months from now.
- Thank you for the honest eval. I'd rather hear "you picked Snowflake Postgres for waypoint
  out of loyalty, not fit" or "you rejected Snowflake for wallpaper-kit because the design
  was bad, not because the platform is wrong" from Snowflake's own agent than discover it
  after I've committed to the wrong tool.

---

*End of Part 1. Drafted by Claude Code on behalf of Noah Goodrich, 2026-04-14.
Revised once following scope feedback — wallpaper-kit refreshed from stale framing, whimsical
naming acknowledged as abandoned, Q4 reframed as Terraform vs DCM Projects vs Permifrost +
gaps, and skeptic framing added throughout.*
