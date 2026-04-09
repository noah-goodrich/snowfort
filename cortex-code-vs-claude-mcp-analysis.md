# Cortex Code vs. Claude + Snowflake MCP Server: A Comprehensive Analysis

**Prepared for:** Noah Goodrich, Snowflake Data Superhero
**Date:** April 3, 2026 (v4 — restructured pricing section, added markup analysis, added CoCo deployment blueprint)
**Purpose:** Objective comparison to inform strategic technology recommendations

---

## Executive Summary

This analysis compares two approaches to AI-assisted data engineering on Snowflake: **Cortex Code (CoCo)**, Snowflake's native AI coding agent, and **Claude + Snowflake MCP Server**, an open-standards approach using Anthropic's Claude with the Model Context Protocol. Both approaches are viable and each has distinct strengths. Cortex Code wins on Snowflake-native depth, governance, and data engineering task accuracy. Claude + MCP wins on flexibility, cross-system reach, cost, and breadth of use cases beyond Snowflake.

**On pricing specifically:** Cortex Code is now charging for usage (it is no longer free). The per-token premium is 10–21% over direct Claude API rates (verified from Snowflake's Service Consumption Table). But the bigger cost story is the **billing model gap**: CoCo has no flat-rate heavy-use plan. Claude Code Max at $100–200/month absorbs thousands of dollars in API-equivalent usage into a fixed fee. CoCo charges per-token for every interaction with no ceiling. For heavy daily users, this can mean 5–10x higher monthly spend through CoCo vs. a Claude Max subscription doing the same work.

---

## 1. What Each Approach Actually Is

### Cortex Code (CoCo)

Cortex Code is Snowflake's native AI coding agent, available in two forms:

- **Cortex Code in Snowsight** (GA as of March 9, 2026): An agentic assistant embedded directly in Snowflake's web interface. It helps with SQL and Python notebook authoring, data exploration, account administration, and governance queries—all within the Snowsight UI.

- **Cortex Code CLI** (GA as of February 2, 2026): A terminal-based agent that connects to your Snowflake account and operates across local files, Git repos, dbt projects, Streamlit apps, and Airflow DAGs. It can execute SQL, run bash commands, and manage multi-step workflows. It ships with built-in "skills" for ML, data engineering, and governance tasks.

CoCo uses frontier models (Claude Opus 4.6, Claude Sonnet 4.6, and now GPT 5.2) under the hood, but wraps them with Snowflake-specific context: metadata awareness, RBAC enforcement, and purpose-built data engineering tooling.

### Claude + Snowflake MCP Server

This approach uses Anthropic's Claude (via Claude Code CLI, Claude Desktop, or API) connected to Snowflake through the Model Context Protocol (MCP). The Snowflake MCP server (available from Snowflake Labs on GitHub, plus a Snowflake-managed version in public preview) provides Claude with structured access to:

- **Cortex Search** — RAG over unstructured data
- **Cortex Analyst** — Natural language queries over structured data
- **Cortex Agent** — Agentic orchestration across both
- **Object Management** — DDL operations (create, drop, alter)
- **SQL Execution** — Run queries with configurable permission controls
- **Semantic Views** — Discovery and querying

Claude connects to Snowflake as one of potentially many data sources, alongside Google Drive, Slack, Jira, GitHub, and dozens of other MCP-compatible services.

---

## 2. Pricing Comparison

**Important note:** This section uses verified data from the **Snowflake Service Consumption Table** (the official legal pricing document) and the **Anthropic API pricing page**, both accessed April 3, 2026. Snowflake IS now charging for Cortex Code — this is no longer free.

### The Headline: It's the Billing Model, Not the Markup

Before diving into per-token rates, here's the finding that matters most: **Snowflake's per-token markup on CoCo is reasonable and in line with industry norms. The cost problem is the billing model, not the markup.** CoCo charges a 10–21% premium over direct Claude API rates, which is comparable to what Google Vertex AI charges (10% regional premium) and actually lower than Azure OpenAI's all-in premium (15–40% when you factor in infrastructure and support). AWS Bedrock charges zero per-token markup but monetizes through ecosystem lock-in. Snowflake's premium pays for real value: metadata-aware context injection, RBAC enforcement, Snowsight integration, and keeping processing within Snowflake's security perimeter. That's a defensible charge.

The problem is that CoCo has no flat-rate heavy-use subscription. Claude Max at $100–200/month absorbs thousands of dollars in API-equivalent usage into a fixed fee. Cursor's Auto mode gives unlimited access to a model the company owns. CoCo charges for every token with no ceiling and no "unlimited" tier. For interactive, session-based usage (which is the whole point of an AI coding agent), this billing model produces monthly bills 3–10x higher than alternatives doing the same work. The markup is fair; the model is the issue.

### Cortex Code Pricing (Verified from Service Consumption Table)

Cortex Code billing uses **AI Credits** (not regular Snowflake credits). AI Credits have their own pricing schedule separate from compute credits.

**AI Credit → Dollar conversion (Table 2(b) from Service Consumption Table):**

| Pricing Type | Global Rate | Regional Rate |
|-------------|-------------|---------------|
| On Demand | $2.00/AI Credit | $2.20/AI Credit |
| Capacity Tier 1 ($0–$1.2M ACV) | $2.00 | $2.20 |
| Capacity Tier 3 ($3M–$5M ACV) | $1.94 | $2.13 |
| Capacity Tier 7 ($40M+ ACV) | $1.88 | $2.07 |

**Table 6(e): Cortex Code — AI Credits per million tokens:**

| Model | Input | Output | Cache Read |
|-------|-------|--------|------------|
| claude-opus-4-6 | 2.75 | 13.75 | 0.28 |
| claude-opus-4-5 | 2.75 | 13.75 | 0.28 |
| claude-sonnet-4-6 | 1.65 | 8.25 | 0.17 |
| claude-sonnet-4-5 | 1.65 | 8.25 | 0.17 |
| claude-4-sonnet | 1.50 | 7.50 | 0.15 |
| openai-gpt-5.4 | 1.38 | 8.25 | 0.14 |
| openai-gpt-5.2 | 0.97 | 7.70 | 0.10 |

**Converting to dollars (On Demand, Global rate of $2.00/AI Credit):**

| Model | Input $/MTok | Output $/MTok | Cache Read $/MTok |
|-------|-------------|---------------|-------------------|
| claude-opus-4-6 | **$5.50** | **$27.50** | $0.56 |
| claude-opus-4-5 | **$5.50** | **$27.50** | $0.56 |
| claude-sonnet-4-6 | **$3.30** | **$16.50** | $0.34 |
| claude-sonnet-4-5 | **$3.30** | **$16.50** | $0.34 |
| openai-gpt-5.4 | **$2.76** | **$16.50** | $0.28 |
| openai-gpt-5.2 | **$1.94** | **$15.40** | $0.20 |

**CLI — Individual Subscription:**
- 30-day free trial with $40 USD in inference credits
- After trial: $20/month subscription with a fixed (undisclosed) token allowance
- If you exceed the allowance, the CLI becomes unavailable until the next billing period — a hard cap, not overage billing
- Does NOT require an existing Snowflake account

**Additional cost considerations:**
- Cortex AI functions (which CoCo may invoke) have caused surprise bills — one documented case hit $5K on a single query processing 1.18B records
- CoCo is described as the "fastest-growing cost center in the Cortex family" because it's interactive and session-based
- Premium model selection dramatically impacts cost — Opus output costs ~$27.50/MTok vs. GPT 5.2 at ~$15.40/MTok
- Any warehouses or storage CoCo uses are billed separately at standard Snowflake rates

**Cost controls available (all GA):**
- **Hard daily per-user caps:** Admins can set `CORTEX_CODE_CLI_DAILY_EST_CREDIT_LIMIT_PER_USER` and `CORTEX_CODE_SNOWSIGHT_DAILY_EST_CREDIT_LIMIT_PER_USER` to block access when a user's rolling 24-hour credit usage exceeds the threshold. Set to 0 to block access entirely. Requires ACCOUNTADMIN role; can be overridden per-user for tiered access.
- **Dedicated monitoring views:** `CORTEX_CODE_CLI_USAGE_HISTORY` and `CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY` provide granular token and credit breakdowns by model, user, and request type (input, output, cache read/write). 365 days of retention.
- **Important limitations:** Traditional Snowflake resource monitors do NOT cover AI credit consumption. The resource budgets available for Cortex Agents do not apply to Cortex Code (separate products). There is no native alerting tied to the daily limits — when a user hits the cap, access is blocked immediately with no advance warning. Building "approaching budget" alerts requires custom monitoring on top of the usage history views.

### Claude + MCP Pricing (Verified from Anthropic Pricing Page)

**Claude API (Direct):**

| Model | Input $/MTok | Output $/MTok | Cache Hit $/MTok |
|-------|-------------|---------------|------------------|
| Claude Opus 4.6 | **$5.00** | **$25.00** | $0.50 |
| Claude Sonnet 4.6 | **$3.00** | **$15.00** | $0.30 |
| Claude Haiku 4.5 | **$1.00** | **$5.00** | $0.10 |

**Cost optimization levers:**
- Prompt caching: 5-min cache write at 1.25x, 1-hour cache write at 2x, cache reads at 0.1x base input — pays off after just one read on 5-min cache
- Batch API: 50% discount (e.g., Sonnet 4.6 drops to $1.50 input / $7.50 output)
- Combined caching + batch: significant savings in specific scenarios (not the "up to 95%" I previously overstated — that's a theoretical ceiling for highly repetitive, batch-friendly workloads)
- Model selection flexibility — Haiku at $1/$5 for simple queries, Opus at $5/$25 for complex reasoning
- Full 1M context window at standard pricing (no surcharge for long context on Opus/Sonnet 4.6)

**Claude subscription plans (for Claude Code access):**

| Plan | Monthly Cost | Notes |
|------|-------------|-------|
| Pro | $20/month | Includes Claude Code access |
| Max 5x | $100/month | 5x Pro usage limits |
| Max 20x | $200/month | 20x Pro usage limits |
| Team | $25–30/user/month | Standard seats |
| Team Premium | $150/user/month | Includes Claude Code |
| Enterprise | Custom | SSO, audit logs, HIPAA, compliance |

**MCP Server costs:** The Snowflake MCP server itself is free (open source from Snowflake Labs). The managed version is in public preview. The underlying Snowflake compute for queries you run through MCP is billed at standard Snowflake rates.

### Per-Token Markup: CoCo vs. Direct API vs. Other Cloud Platforms

The condensed version: CoCo charges a 10% premium on Global inference, 21% on Regional, over direct Anthropic API rates for the same model. Here's the side-by-side for the two models that matter most:

| Model + Direction | Direct Anthropic | CoCo Global (+10%) | CoCo Regional (+21%) |
|---|---|---|---|
| Sonnet 4.6 Input/MTok | $3.00 | $3.30 | $3.63 |
| Sonnet 4.6 Output/MTok | $15.00 | $16.50 | $18.15 |
| Opus 4.6 Input/MTok | $5.00 | $5.50 | $6.05 |
| Opus 4.6 Output/MTok | $25.00 | $27.50 | $30.25 |

### Is That Markup Reasonable? Comparing Cloud AI Platforms

Snowflake is not the only cloud platform that wraps third-party AI models with value-added infrastructure and charges a premium. Here's how the markup compares:

| Platform | Per-Token Markup | What You Get for It |
|---|---|---|
| **AWS Bedrock** | **0%** (token parity with provider) | IAM, CloudWatch, VPC endpoints, unified billing. AWS monetizes through ecosystem, not per-token |
| **Azure OpenAI** | **0% base, 15–40% all-in** | Base token pricing matches OpenAI, but infrastructure, support plans, and data transfer add 15–40% total cost |
| **Google Vertex AI** | **10% regional premium** | Data residency controls, Google Cloud IAM, Vertex AI pipelines |
| **Snowflake Cortex Code** | **10% global, 21% regional** | Snowflake metadata injection, RBAC, Snowsight integration, security perimeter, cost controls |

**The assessment:** Snowflake's markup is in line with the industry. It's comparable to Google Vertex AI's regional premium and lower than Azure's all-in cost premium. AWS Bedrock is the outlier at zero markup, but AWS makes its money on the broader cloud ecosystem (compute, storage, networking) that supports Bedrock usage. Snowflake's premium is paying for genuine value: the metadata awareness, RBAC enforcement, and context injection that give CoCo its 7-point benchmark advantage over raw Claude on Snowflake tasks. If you're evaluating CoCo purely on per-token rates, the markup is not the problem. It's reasonable for what you get.

### The Billing Model Gap: Where the Real Cost Difference Lives

There are four distinct ways to access the same Claude models, and they produce wildly different monthly bills. This is the section that matters most:

**Model 1: CoCo Enterprise — Pure consumption, no ceiling, no floor**
Every token costs AI Credits. No flat-rate option. No "unlimited" tier. The $20/month CLI subscription includes an undisclosed token allowance with a hard cap (CoCo stops working when you hit it). For enterprise Snowflake customers, it's purely consumption-based at the AI Credit rates above. There is no CoCo equivalent of a "Max" plan.

**Model 2: Claude Code via Max Subscription — Flat rate, massively subsidized**
This is the game-changer. Claude Max 5x costs $100/month. Max 20x costs $200/month. These are flat-rate plans with generous usage limits that are dramatically cheaper than equivalent API consumption. Real-world data from tracked usage:

| Period | Tokens Consumed | API Equivalent Cost | Max Subscription Cost |
|--------|----------------|--------------------|-----------------------|
| One heavy month | 2.4B tokens | ~$5,623 | $100 |
| 8-month total | ~10B tokens | ~$15,000+ | ~$800 |

That's not a typo. One developer documented consuming $15,000+ worth of API-equivalent tokens for $800 on a Max subscription over 8 months. The reason: ~90% of tokens in Claude Code sessions are cache reads (at 0.1x the input price), and the Max subscription absorbs this entire pattern into a flat fee.

**Model 3: Claude API Direct — Pay per token, transparent**
Standard API rates ($3/$15 Sonnet, $5/$25 Opus per MTok). Caching and batch discounts available. Predictable but potentially expensive at high volumes.

**Model 4: Cursor — Credit pool with subsidized tiers**
Cursor Pro ($20/month) gives you $20 in credits at API rates. Cursor Ultra ($200/month) gives you $400 in credits — a 2x multiplier. Auto mode (which routes to the best model automatically) is unlimited on all paid plans and doesn't consume credits. This means routine coding work is effectively free, with credits reserved for when you manually select premium models.

### The Real Comparison: Monthly Cost at Equivalent Usage

For a developer doing moderate-to-heavy daily data engineering work (the kind of person who loves CoCo and uses it all day):

| Approach | Billing Model | Estimated Monthly Cost | Notes |
|----------|--------------|----------------------|-------|
| **CoCo (Enterprise)** | Per-token AI Credits | **$200–500+/month** | Purely consumption; grows with use |
| **CoCo CLI (Individual)** | $20/month subscription | **$20/month** (hard cap) | CLI stops working when allowance exceeded |
| **Claude Code (Max 5x)** | Flat subscription | **$100/month** | Covers $500–5,000+ in API-equivalent use |
| **Claude Code (Max 20x)** | Flat subscription | **$200/month** | Covers even heavier use |
| **Claude Code (API direct)** | Per-token | **$130–260/month** | Medium usage estimate |
| **Cursor Pro** | $20 credit pool + free Auto | **$20/month** | ~225 Sonnet requests; Auto unlimited |
| **Cursor Ultra** | $200 credit pool + free Auto | **$200/month** | $400 credit value; Auto unlimited |

**The bottom line:** CoCo's lack of a flat-rate heavy-use subscription is arguably its biggest cost disadvantage. Claude Code Max at $100–200/month provides effectively unlimited interactive AI coding for a fixed fee. CoCo charges you for every token at a 10–21% premium over the same model's API rate, with no ceiling. For a heavy daily user, the difference can be 5–10x or more in monthly spend.

This is likely what Snowflake customers are complaining about: not just the per-token rate, but the fact that CoCo has no plan that absorbs heavy interactive use into a predictable monthly fee the way Claude Max and Cursor Auto do.

### What CoCo's Token Consumption Actually Looks Like

CoCo's token consumption is interactive and session-based. Every prompt, every follow-up, every "try again" burns tokens. The Snowflake community has flagged CoCo as the "fastest-growing cost center in the Cortex family" precisely because developers love it and use it heavily. Unlike a warehouse you can suspend, every CoCo interaction is a token spend event.

That said, Snowflake has shipped real cost controls to manage this (all GA). Admins can set hard daily per-user credit caps that block access immediately when the threshold is reached. These operate on a rolling 24-hour window and can be configured at the account level or overridden per-user, so you can give your senior engineers a higher ceiling than your juniors. Combined with the dedicated usage history views (which track every token by model, user, and request type with 365-day retention), an admin has the tools to set guardrails, monitor trends, and adjust limits over time.

The honest assessment: these controls are functional but not sophisticated. You get a hard daily cap and a monitoring view. You don't get monthly team budgets, graduated warnings ("you're at 80%"), integration with Snowflake resource monitors, or the kind of automated alerting (email notifications, role revocation) that Cortex Agents resource budgets offer. For a small team where an admin can manually tune per-user limits, it's workable. For a 50-person org that wants fine-grained FinOps governance, you'll need to build custom tooling on top of the usage history views. The underlying billing model remains purely consumption-based, but "consumption-based with hard daily caps" is a meaningfully different risk profile than "consumption-based with no guardrails."

---

## 3. Feature Comparison

### Data Engineering Capabilities

| Capability | Cortex Code | Claude + MCP |
|-----------|-------------|--------------|
| SQL generation & optimization | Native, context-aware | Via MCP SQL execution tool |
| dbt project management | Built-in CLI skill | Via file system access + MCP |
| Apache Airflow DAG authoring | Built-in CLI skill (new) | Via file system access |
| Python notebook authoring | Native in Snowsight | Via file tools, not native |
| Data discovery & metadata | Deep Snowflake metadata access | Via MCP object management |
| Semantic model validation | Native | Via MCP Cortex Analyst tool |
| Streamlit app building | Built-in skill | Via file system + deployment scripts |
| Agent Teams (parallel work) | Native feature | Supported via Claude Code subagents |

**Benchmark data:** When tested on 43 dbt + Snowflake tasks using the same underlying model (Claude Opus 4.6), Cortex Code completed 28 (65%) vs. Claude Code at 25 (58%). This 7-point advantage reflects CoCo's Snowflake-specific context injection, not a difference in model capability.

### Governance & Security

| Capability | Cortex Code | Claude + MCP |
|-----------|-------------|--------------|
| Runs within Snowflake perimeter | Yes (Snowsight) / Partial (CLI) | No — data transits to Claude API |
| RBAC enforcement | Native, Snowflake-integrated | Via MCP server role configuration |
| Data residency control | Within Snowflake (with cross-region caveat) | Data sent to Anthropic's infrastructure |
| Audit logging | Snowflake-native query history | Anthropic API logs + Snowflake query logs |
| Admin access controls | Snowflake roles + CoCo-specific permissions | MCP permission config + Claude plan controls |
| Sandboxing & risk assessment | Built into CLI | Configurable via MCP SQL permissions |
| Gov/VPS/Sovereign deployment | Not available | Not applicable (external service) |

**This is the single biggest differentiator.** For organizations with strict data governance requirements, the fact that Cortex Code operates within (or close to) the Snowflake security perimeter is a significant advantage. With Claude + MCP, your data context and query results transit through Anthropic's API infrastructure, which may be a non-starter for regulated industries or sensitive datasets.

However, note the irony: Cortex Code itself requires cross-region inference to be enabled, meaning your data may leave your account's geographic region even within Snowflake. And CoCo is explicitly unavailable on Government, VPS, and Sovereign deployments.

### Flexibility & Ecosystem

| Capability | Cortex Code | Claude + MCP |
|-----------|-------------|--------------|
| Cross-system integration | Snowflake + dbt + Airflow | Any MCP-compatible system |
| Non-Snowflake data sources | Limited (expanding) | Google Drive, Slack, Jira, GitHub, etc. |
| General-purpose coding | Limited to data stack | Full general-purpose coding agent |
| Document/content creation | No | Full capability (docs, slides, analysis) |
| Browser automation | No | Via Claude in Chrome |
| Custom tool creation | AGENTS.md + built-in skills | MCP servers + Claude Code skills |
| IDE integration | VS Code, Cursor | VS Code, Cursor, JetBrains, Neovim, etc. |
| Model choice | Claude Opus/Sonnet, GPT 5.2 | Any Claude model, tunable per task |

This is where Claude + MCP pulls ahead decisively. CoCo is a specialist; Claude is a generalist that can specialize. If your workflow involves pulling data from Snowflake, cross-referencing with a Google Sheet, drafting a Slack message, and updating a Jira ticket, Claude can do all of that in one session. CoCo can only do the Snowflake part.

---

## 4. Delivery Capability Assessment

"Can we actually deliver with this?" is the question that matters most. Here's how each approach performs across real delivery scenarios:

### Scenario 1: Building a new dbt project from scratch

**Cortex Code:** Strong. Purpose-built for this. The CLI has native dbt skills, understands your Snowflake metadata, and can generate staging models, tests, and documentation from natural language prompts. The 65% task completion rate on dbt benchmarks is solid for an AI tool.

**Claude + MCP:** Capable but requires more setup. Claude Code can read your file system, understand dbt project structure, and generate models. But it lacks CoCo's automatic Snowflake metadata context — you'd need to explicitly query metadata through MCP or provide context manually. Expect slightly more iteration and prompt engineering.

**Winner:** Cortex Code, by a meaningful margin for pure dbt-on-Snowflake work.

### Scenario 2: Cross-platform data pipeline debugging

**Cortex Code:** Limited. If the issue spans Snowflake + Airflow + external APIs + a Python service, CoCo can help with the Snowflake and Airflow portions but can't debug the external components.

**Claude + MCP:** Strong. Claude can read your Airflow DAGs, query Snowflake via MCP, examine your Python code, search logs, and reason across the full stack. It's a single agent that understands the entire pipeline.

**Winner:** Claude + MCP, decisively.

### Scenario 3: FinOps and cost investigation

**Cortex Code:** Excellent. Native access to Snowflake account usage views, credit consumption history, and warehouse performance metrics. Purpose-built queries for cost investigation.

**Claude + MCP:** Good. Can run the same queries via MCP SQL execution, but lacks CoCo's pre-built cost investigation skills and contextual knowledge of Snowflake's billing model.

**Winner:** Cortex Code, with a meaningful but not insurmountable lead.

### Scenario 4: Client-facing deliverables (reports, presentations, documentation)

**Cortex Code:** Not applicable. CoCo generates code, not content.

**Claude + MCP:** Strong. Can query Snowflake for data, analyze results, and produce formatted reports, slide decks, Word documents, and visualizations—all in one workflow.

**Winner:** Claude + MCP, by default.

### Scenario 5: Ongoing team productivity for a Snowflake-centric data team

**Cortex Code:** This is its sweet spot. The Snowsight integration means every team member gets an AI assistant inside their daily tool. No additional setup, no API keys to manage, no MCP configuration. It just works within Snowflake.

**Claude + MCP:** Requires more infrastructure. Each team member needs Claude access (subscriptions or API keys), MCP server configuration, and potentially custom tooling. The setup investment is higher but the capability ceiling is also higher.

**Winner:** Cortex Code for pure Snowflake teams with minimal setup appetite. Claude + MCP for teams that value flexibility and already use Claude.

---

## 5. Risk Assessment

### Risks of Backing Cortex Code

1. **Pricing opacity (partially mitigated):** Enterprise pricing is credit-based and harder to predict than flat-rate subscriptions. Snowflake has shipped hard daily per-user caps (GA) that block access when thresholds are reached, which eliminates the risk of truly runaway bills. However, traditional resource monitors don't cover AI credits, there's no native alerting before caps are hit, and fine-grained FinOps governance (monthly team budgets, graduated warnings) requires custom tooling. The documented $5K single-query incident was a Cortex AI function, not CoCo specifically, but it illustrates the broader Cortex cost awareness teams need.

2. **Vendor lock-in:** CoCo is Snowflake-only. If your organization ever diversifies data platforms (Databricks, BigQuery, etc.), CoCo doesn't travel with you.

3. **Limited scope:** CoCo solves data engineering problems. It doesn't help with documentation, communication, general coding, or cross-system automation. You'll still need other tools for those tasks.

4. **Maturity:** CoCo went GA in Feb/March 2026. It has ~4,400 users since November 2025 launch. That's respectable but early. The tool is evolving rapidly, which means both opportunity and instability.

5. **Availability gaps:** No support for Gov, VPS, or Sovereign deployments. Requires cross-region inference.

### Risks of Backing Claude + MCP

1. **Data governance:** Query results and context transit through Anthropic's infrastructure. For regulated industries or sensitive data, this may require legal review, DPAs, or may be a blocker entirely.

2. **Setup complexity:** The MCP approach requires more configuration, infrastructure management, and team training compared to CoCo's built-in Snowsight experience.

3. **Snowflake-specific depth:** Claude doesn't have CoCo's deep metadata awareness. The 7-point benchmark gap on dbt tasks reflects real limitations in automatic context.

4. **MCP maturity:** The Snowflake managed MCP server is still in public preview. The open-source version is functional but requires self-management.

5. **Dependency on Anthropic:** If Anthropic changes pricing, rate limits, or API terms, you're exposed. (Though the same applies to Snowflake changing CoCo pricing.)

---

## 6. The BYOM Question: Bring Your Own Model

This is an increasingly important cost lever that widens the gap between the two approaches.

### Claude Code: Full BYOM Support

Claude Code supports redirecting to any LLM that speaks the Anthropic Messages API format. This is not theoretical — it's well-documented and actively used:

- **Ollama integration** (native since v0.14): Set `ANTHROPIC_BASE_URL=http://localhost:11434` and run Claude Code against any local model. Recommended models include Qwen 3.5, GLM-4.7-Flash, and Kimi K2.5. Minimum requirement: 64K token context window.
- **LM Studio**: Provides an Anthropic-compatible `/v1/messages` endpoint — any model hosted in LM Studio works with Claude Code via a base URL change.
- **OpenRouter, vLLM, llama.cpp**: All supported through the same environment variable swap.
- **Cloud variants**: Ollama offers `:cloud` model variants that run on cloud infrastructure but use the same local workflow — no API keys needed.

The practical impact: a team can use Claude Code's full tooling (skills, plugins, MCP servers, subagents) with a self-hosted Qwen 3.5 or DeepSeek model at zero per-token cost beyond their own compute. For routine tasks that don't need frontier model quality, this is a massive cost reduction. Reserve the Anthropic API or Max subscription for complex reasoning tasks.

### Cortex Code: No BYOM

CoCo uses Snowflake-hosted models exclusively. You can choose between Claude Opus 4.6, Claude Sonnet 4.6, Claude Sonnet 4.5, and OpenAI GPT-5.2 — but you cannot bring your own model, point CoCo at a local inference server, or use open-weight alternatives. Every token goes through Snowflake's infrastructure at Snowflake's AI Credit rates.

This is by design (Snowflake controls the security perimeter and context injection), but it means there's no escape valve for cost-conscious teams who want the CoCo workflow at lower cost.

### Frosty: The Open-Source Wild Card

Frosty (github.com/Gyrus-Dev/frosty) is an open-source, self-hosted alternative that attempts to replicate much of what CoCo does. Key details:

- **153 specialist agents** organized across six pillars: data engineering (34 agents), administration (16), security (14), governance (8), inspection (56), and cost monitoring (25)
- **Supports Claude, GPT, and Gemini** — swap providers with a single `.env` change
- **72 Snowflake object types** supported (databases, schemas, tables, views, warehouses, roles, policies, etc.)
- **Safety mechanisms**: Hard-coded gates block DROP statements unconditionally; CREATE OR REPLACE requires user approval. This is code-level enforcement, not prompt-level — it can't be bypassed by prompt injection
- **Cost model**: You host it, you pay only LLM token costs. No per-seat fees, no SaaS platform charges
- **Full audit trail**: Every executed query logged and exportable as .sql files

Frosty's limitations: no parallel execution (sequential by design for safety), Streamlit generation only works with Gemini, session persistence requires manual configuration, and you own the ops burden (hosting, updates, debugging).

**What Frosty means for this analysis:** It proves that CoCo's core value proposition (natural language Snowflake operations with metadata awareness) can be replicated at commodity LLM token costs. The question is whether your team has the appetite to self-manage it vs. paying CoCo's premium for a fully managed experience.

### BYOM Cost Impact at Scale

For a 30-person data team:

| Approach | Model Cost | Platform Cost | Total Monthly |
|----------|-----------|---------------|---------------|
| CoCo (Sonnet 4.6, moderate use) | ~$330/person | $0 (in Snowflake) | **~$9,900/month** |
| Claude Code Max 5x (all users) | Included | $100/person | **~$3,000/month** |
| Claude Code + self-hosted Qwen 3.5 | ~$0 (local compute) | $0 | **Compute costs only** |
| Frosty + Claude API (Sonnet) | ~$100/person | $0 | **~$3,000/month** |
| Frosty + self-hosted model | ~$0 (local compute) | $0 | **Compute costs only** |

The BYOM option doesn't work for every task (frontier models genuinely outperform on complex reasoning), but for the 60–70% of daily data engineering work that's routine — metadata queries, basic SQL generation, documentation — a self-hosted model through Claude Code or Frosty is more than adequate. The teams that are figuring this out are spending a fraction of what CoCo-only shops pay.

---

## 7. Org-Level Cost Modeling: What Does This Actually Cost at Scale?

For Noah's company and for any organization evaluating this decision, here are realistic annual cost projections across different team sizes and usage patterns. These use the verified pricing from Sections 2 and 6.

### Small Team (10 data engineers, moderate daily use)

| Approach | Annual Cost | Notes |
|----------|------------|-------|
| CoCo Enterprise (Sonnet 4.6) | **~$39,600** | $330/person/month × 12 |
| CoCo CLI Individual ($20 sub) | **~$2,400** | Hard cap may limit heavy users |
| Claude Max 5x (all users) | **~$12,000** | $100/person/month × 12 |
| Claude Max 20x (heavy users) | **~$24,000** | $200/person/month × 12 |
| Claude API Direct + MCP | **~$36,000** | $300/person/month × 12 |
| Hybrid: CoCo Snowsight + Claude Max 5x | **~$12,000+** | CoCo Snowsight pricing TBD |

### Medium Team (30 data engineers, mixed usage)

| Approach | Annual Cost | Notes |
|----------|------------|-------|
| CoCo Enterprise (Sonnet 4.6) | **~$118,800** | Scales linearly with no volume break |
| Claude Max 5x (all users) | **~$36,000** | Fixed, predictable |
| Claude Max 20x (power users only, 10) + Max 5x (20) | **~$48,000** | Tiered by usage pattern |
| Hybrid with BYOM for routine tasks | **~$20,000–30,000** | Self-hosted handles 60%+ of work |

### Large Team (50+ data engineers)

At 50 users on CoCo Enterprise with moderate Sonnet 4.6 usage, you're looking at ~$198,000/year in AI Credits alone (before any warehouse or storage costs). The same team on Claude Max 5x costs $60,000/year. That's a **$138,000/year gap** — enough to fund additional headcount, tooling, or infrastructure.

The gap widens further if CoCo users gravitate toward Opus 4.6 (output at $27.50/MTok vs. Sonnet's $16.50/MTok) or if usage increases as the team gets comfortable with the tool.

---

## 8. The Strategic Angle for a Snowflake DSH

Noah, here's the part specific to your position, updated for the full pricing and BYOM picture:

**As a DSH recommending to the Snowflake community:** You can champion CoCo's strengths (native integration, governance, zero-friction Snowsight experience) while being honest about its cost structure. The community will respect a nuanced take far more than a blanket endorsement. "CoCo is excellent for X but expensive for Y, and here's how to manage that" is a more credible DSH position than "CoCo is the answer to everything."

**As someone advising your company:** The billing model gap is the decisive factor for cost-conscious organizations. CoCo Enterprise at $330/person/month (moderate Sonnet 4.6 use) vs. Claude Max 5x at $100/person/month is a 3.3x cost difference for comparable capability. For a 30-person team, that's ~$82,800/year in savings by going Claude Max. If governance permits it, this is hard to argue against.

**The recommended architecture for most organizations:**

1. **Claude Max subscriptions** as the primary AI platform for all data engineers ($100–200/person/month, fixed and predictable)
2. **Snowflake MCP server** connecting Claude to your Snowflake environment (free, open source or managed preview)
3. **CoCo in Snowsight** as a complementary tool for quick Snowflake-native queries (pricing TBD but currently accessible)
4. **BYOM via Ollama/local models** for routine tasks that don't need frontier quality (reduces even Max subscription pressure)
5. **Frosty** worth evaluating if your team has ops appetite and wants to eliminate per-token costs entirely for Snowflake operations

This architecture gives you the best of both worlds: CoCo's Snowflake-native intelligence where it matters most (Snowsight), Claude's flat-rate economics and cross-system reach for daily heavy use, and a BYOM escape valve for cost management.

**What makes this a strong DSH play:** You're not anti-Snowflake — you're pro-optimization. CoCo is part of the stack, not the whole stack. The $200M Anthropic-Snowflake partnership means Claude models will keep improving inside Snowflake regardless. Recommending the cost-optimal way to use Claude on Snowflake is a service to the community, not a betrayal of it.

---

## 9. Revised Recommendation Matrix

| If your priority is... | Go with... | Why |
|------------------------|------------|-----|
| Snowflake-native data engineering | Cortex Code (Snowsight) | Zero friction, deep metadata awareness |
| Cross-system automation | Claude + MCP | Only option that spans the full stack |
| Enterprise data governance | Cortex Code | Data stays in Snowflake infrastructure |
| **Cost control at scale** | **Claude Max subscriptions** | **3–5x cheaper than CoCo Enterprise for equivalent use** |
| Lowest setup friction | Cortex Code (Snowsight) | Built-in, nothing to configure |
| Broadest capability set | Claude + MCP | Coding, content, cross-system, BYOM |
| dbt/Airflow acceleration | Cortex Code (slight edge) | 65% vs 58% on benchmarks |
| Client deliverables + data work | Claude + MCP | CoCo can't create docs/presentations |
| **Maximum cost efficiency** | **Claude Code + BYOM (Ollama)** | **Near-zero token cost for routine work** |
| **Open source, self-hosted** | **Frosty** | **153 agents, zero platform fees** |
| Team already on Claude | Claude + MCP | Leverage existing investment |
| Pure Snowflake shop, cost is no object | Cortex Code | Deepest native integration |

---

## 10. Final Verdict: Is CoCo a Money Pit?

**Not inherently — but its billing model creates that risk.** CoCo is a genuinely excellent tool for Snowflake-native data engineering. The 65% benchmark score, zero-friction Snowsight integration, and deep metadata awareness are real differentiators that the Claude + MCP approach hasn't fully matched.

But the pricing structure is the problem. Three specific issues:

1. **No flat-rate heavy-use plan.** Claude Max absorbs $5,000+ in API-equivalent usage for $100–200/month. CoCo charges for every token. For the interactive, session-based usage pattern that makes AI coding tools valuable, this is a structural disadvantage.

2. **10–21% premium on the same models.** You're paying more per token for the same Claude Opus/Sonnet you'd access directly from Anthropic — and you can't opt out of this markup.

3. **No BYOM escape valve.** Claude Code lets you route routine work to free local models. CoCo locks you into Snowflake-hosted frontier models at premium rates for everything, including simple metadata queries that a Qwen 3.5 could handle.

**For a single developer** experimenting with CoCo on the $20/month CLI plan, it's fine — competitive with Claude Pro and Cursor Pro. The hard cap protects you from surprise bills.

**For an organization of dozens of users**, CoCo Enterprise's consumption-based model costs significantly more than flat-rate alternatives. A 30-person team could easily spend $120K+/year on CoCo vs. $36K–48K on Claude Max subscriptions. That's not a rounding error — it's a headcount. The daily per-user caps (GA) mean this spend is governable, not runaway; an admin can set hard ceilings that block access when reached. But "governable" and "cheap" are different things. The caps let you control the bleeding, not eliminate the cost gap.

**The honest answer for your company:** Use CoCo where it's best (Snowsight, governance-sensitive work), Claude Max where it's cheapest (everything else), and BYOM where it's free (routine tasks). Don't go all-in on any single approach. The organizations that will win this transition are the ones that treat AI tooling like a portfolio, not a religion.

---

## 11. The Structural Economics Question: Who Owns the Inference?

Everything in this analysis so far has compared what these tools cost today. But the sharper question is: *why* do they cost what they cost, and what happens to those prices over the next 12–24 months? The answer comes down to one thing: who owns their inference costs, and who is renting someone else's.

### The Gym Membership Model: How Flat-Rate AI Subscriptions Actually Work

Claude Max at $100–200/month is not a charity. It's a gym membership. Most subscribers use 20–40% of their capacity. The moderate users subsidize the heavy users. Anthropic's real cost to serve a power user (50–100M tokens/month) is estimated at $500–1,200/month, meaning the heaviest Max subscribers are getting 3–10x more compute than they pay for. Sam Altman publicly admitted in January 2025 that OpenAI was *losing money* on their $200/month Pro subscriptions because "people use it much more than we expected."

So yes, heavy users are getting a subsidy. But the business model works because the usage distribution works. Anthropic isn't losing money on the Max plan as a whole; they're losing money on the specific users who treat it like an all-you-can-eat buffet. The weekly caps and overflow billing at API rates are the safety valves that prevent truly unlimited losses.

The more important question is whether this pricing is sustainable long-term, or whether heavy users should expect the rug to get pulled.

### Why the "Free Lunch" Is Getting *More* Sustainable, Not Less

This is counterintuitive, but the math supports it. LLM inference costs are dropping at roughly 10x per year for equivalent model performance. Some analyses of the most recent data show closer to 200x per year when you factor in hardware improvements, quantization, and algorithmic efficiency gains. What cost $60/million tokens in 2021 costs approximately $0.06/million tokens today. Gartner projects 90%+ cost reduction for trillion-parameter models by 2030.

What this means in practice: the gap between what Anthropic charges ($200/month for Max) and what it costs them to serve you is closing *from their side*, not yours. The subscription price stays flat (or even drops) while their margins improve. This isn't a loss-leader startup hoping to raise prices once you're locked in. It's a company whose unit economics improve every quarter as hardware gets cheaper and inference gets more efficient. Anthropic's actual compute cost is estimated at roughly 10% of their retail API pricing, meaning there's already meaningful margin on the API side, and that margin is growing.

The real risk isn't a sudden price hike. It's tighter caps, throttling during peak hours, or model routing that sends you to cheaper (less capable) models for routine tasks. We're already seeing early signs of this with weekly usage limits on Max plans and Anthropic's publicly reported drop from 50% to 40% projected gross margins as inference costs exceeded expectations by 23%.

### Cursor's Strategic Advantage: Owning the Model

This is where Noah's Cursor observation cuts to the bone. Cursor doesn't just route to third-party APIs. They fine-tuned their own model (Composer 2) on top of the open-source Kimi K2.5, doing roughly 75% of the training work themselves. Their Tab autocomplete feature runs on a specialized fine-tuned model that outperforms frontier models on its specific task. Auto mode routes to whatever is cheapest for the job, and for most routine coding operations, that's their own model.

This is why Cursor can offer "unlimited" Auto mode. When you're not paying anyone per-token for the majority of your inference, "unlimited" is a rounding error on your compute bill, not an open-ended liability. Cursor's cost floor is their own GPU spend, not a third-party API price they can't control.

Anthropic has a similar structural advantage: they own the model. Their marginal cost is compute, not licensing. API pricing includes substantial margin (estimated 90%), which means they can absorb heavy Max usage and still not bleed. The subscription model works because they control both the product and the cost of goods.

### Snowflake's Structural Problem: The Reseller Trap

Snowflake doesn't own a competitive frontier model. Every CoCo token routes through Claude (Anthropic) or GPT (OpenAI) at a fixed API price that Snowflake pays to the model provider, then marks up 10–21% for their infrastructure, context injection, and governance features. They cannot offer an "unlimited" CoCo tier without writing a blank check to Anthropic and OpenAI.

Snowflake *does* have their own model: **Arctic**, released April 2024. It's a 480B parameter MoE (Mixture of Experts) architecture, open-sourced under Apache 2.0, built for enterprise SQL and coding tasks. It was trained in three months on 1,000 GPUs for approximately $2 million. But Arctic is not frontier-competitive for the complex reasoning that makes CoCo valuable. It was designed for efficiency on specific enterprise tasks, not for the kind of open-ended agentic coding where Opus and Sonnet shine.

For CoCo to break out of the reseller trap, Snowflake would need an Arctic 2.0 (or 3.0) that approaches Sonnet-level quality on data engineering tasks. That's a multi-year, multi-hundred-million-dollar bet, and Snowflake seems more focused on partnering ($200M investment in Anthropic) than competing on the model layer. This is a rational strategy (building frontier models is brutally expensive and uncertain), but it means CoCo will always be structurally more expensive than tools built by companies that own their inference.

### What This Means for the Pricing Forecast

**For Claude Max subscribers:** Expect the flat-rate model to survive, but with gradually tighter guardrails. The economics work because inference costs are falling, most users are moderate, and Anthropic owns the model. The risk is cap tightening, not price hikes. If you're a heavy user today getting $5,000/month of API-equivalent value for $200, you might get $3,000/month of value for $200 in two years. Still a great deal. Not quite as absurd as it is today.

**For Cursor users:** The model is sustainable and possibly the most defensible of all. Cursor's investment in their own fine-tuned models gives them structural cost control that even Anthropic doesn't fully have (Anthropic still needs expensive frontier training runs). Unlimited Auto mode will likely remain unlimited.

**For CoCo users:** The reseller economics are the long-term problem. Even as inference costs drop 10x per year, CoCo's pricing is set by Snowflake's contract with Anthropic and OpenAI, not by the raw cost of inference. Those contracts may or may not pass through cost reductions at the same rate. The AI Credit pricing in the Service Consumption Table gets updated periodically, but there's no guarantee it tracks the actual decline in inference costs. CoCo users are one contract negotiation removed from the cost curve that benefits everyone else directly.

**The strategic implication for organizations:** The companies that will win the AI tooling pricing war are the ones that own their model, own their distribution, or both. Anthropic owns the model. Cursor owns fine-tuned models plus distribution. Snowflake owns distribution (every data team lives in Snowsight) but doesn't own a competitive model. That distribution advantage is real and significant, but it doesn't solve the unit economics problem. For organizations choosing where to invest, the question isn't just "which tool is better today?" but "which tool's pricing structure is architecturally sound for the next three to five years?"

---

## 12. Adversarial Review: What Three Independent Reviewers Found

This analysis was subjected to adversarial review by three independent agents: a pro-CoCo advocate, a pro-Claude advocate, and a neutral fact-checker. Their combined feedback surfaced important corrections, blind spots, and strengthened arguments that I've incorporated below.

### Corrections Applied

**Governance claims needed stronger language.** The original analysis called CoCo's cross-region inference requirement an "irony." All three reviewers flagged this as underselling the issue. The reality: CoCo requires cross-region inference as a hard requirement, meaning data leaves your account's geographic region within Snowflake infrastructure. This substantially narrows the governance gap between CoCo and Claude + MCP. For organizations with strict data residency requirements (HIPAA, FedRAMP adjacency), neither solution fully satisfies without additional review. CoCo's data stays within Snowflake's infrastructure (a meaningful distinction), but it does leave your region. Claude + MCP's data leaves Snowflake entirely. Both require governance sign-off; CoCo's is a softer ask, but it's not zero.

**The 65% vs. 58% benchmark needs context.** Both the pro-Claude advocate and neutral reviewer correctly noted: this is a 43-task sample using the same underlying model, and the gap reflects CoCo's context injection, not fundamental capability. The pro-CoCo advocate countered that the context injection IS the product — a fair point. Net assessment: the benchmark gap is real and meaningful for dbt-on-Snowflake work, but it's narrower than it appears, likely to close over time as MCP matures, and says nothing about non-Snowflake tasks where Claude dominates.

**Enterprise credit consolidation — partially valid, with important caveats.** The pro-CoCo advocate argued that for organizations with large Snowflake contracts, CoCo's cost is lower because it draws from the same credit pool. This is partially true: capacity tier pricing (Table 2(b)) drops AI Credit costs from $2.00 to as low as $1.88 at $40M+ ACV, narrowing the premium gap over direct API. However, the v2 pricing analysis shows CoCo still carries a 10–21% markup over direct API pricing for the same models even at the best capacity tier. CoCo costs are additive to your existing Snowflake spend — they don't come "free" from your credit pool. They're just billed through the same contract.

**Snowsight zero-friction adoption was undersold.** CoCo in Snowsight requires literally zero setup for existing Snowflake users. The original analysis called this "nice-to-have." The pro-CoCo advocate argued convincingly that for a 50-person data team, zero-friction adoption compounds into a massive productivity advantage. Point taken.

**Claude + MCP's "cross-system integration" was overframed.** The pro-CoCo reviewer noted that much of Claude's cross-system integration is read-heavy with human approval gates — you can draft a Slack message but still need to send it, you can propose a Jira update but still need to confirm it. This is a fair nuance. CoCo's narrower scope actually enables deeper autonomous action within Snowflake's trusted perimeter.

**Claude's cost optimization claims need qualification.** The neutral reviewer correctly flagged that "up to 95% savings" from combined caching + batch API is a theoretical ceiling, not a typical scenario. Most workloads won't achieve this. Additionally, Sonnet 4.6 pricing doubles for inputs exceeding 200K tokens — relevant for large metadata context windows.

### Blind Spots Identified

**Learning curves and team adoption friction:** Neither CoCo nor Claude + MCP is self-evident. CoCo requires learning Snowflake-specific AI patterns; Claude + MCP requires MCP configuration and multi-tool orchestration. The analysis didn't adequately address adoption velocity — CoCo's Snowsight integration gives it a massive head start for teams already in Snowflake daily.

**Support and debugging complexity:** CoCo bugs route through Snowflake support (one vendor). Claude + MCP issues span Anthropic support, Snowflake Labs (for MCP server), and potentially community forums. This operational complexity matters for production use.

**The $200M Anthropic-Snowflake partnership:** The original analysis mentioned this but didn't unpack its implications. This partnership suggests deep strategic alignment — Anthropic models will continue improving within Snowflake, and CoCo's model options will expand. Conversely, it also means Claude + MCP benefits from the same model improvements on the Anthropic side. The partnership is a rising tide for both approaches, not a CoCo-only advantage.

**Snowsight pricing uncertainty:** CoCo in Snowsight is free today with promised advance notice before charging begins. The analysis should flag this more prominently: teams adopting Snowsight CoCo now could face unknown pricing later. The managed MCP server has a similar preview-to-production pricing risk.

**DSH conflict of interest:** The neutral reviewer noted that the "DSH recommending CoCo aligns with the platform you champion" line is honest but creates an inherent bias worth acknowledging explicitly. A DSH recommending a non-Snowflake tool carries more credibility precisely because it goes against type. Noah, your audience will trust a nuanced "use both" recommendation more than an all-in endorsement of the native product.

### Where All Three Reviewers Agreed

All three reviewers — despite arguing from opposing positions — converged on these points:

1. **The "both" strategy is genuinely the strongest recommendation** for most teams. CoCo in Snowsight for Snowflake-native work; Claude + MCP for cross-system workflows and content creation. At $20/month each, the combined cost is trivial against the combined capability.

2. **Governance is the real decision fork.** If your data cannot leave Snowflake infrastructure under any circumstances, CoCo is the only viable option (with the cross-region caveat acknowledged). If you can execute DPAs with Anthropic, Claude + MCP unlocks dramatically more capability.

3. **The scenario-based assessment (Section 4) is the most useful part of the analysis.** Real delivery scenarios matter more than feature checklists.

4. **Both tools are early.** CoCo has been GA for 4 weeks (Snowsight) to 2 months (CLI). The MCP managed server is in preview. Making an irreversible all-in bet on either is premature. Maintain optionality.

### Reliability Rating

The neutral fact-checker rated the original analysis 7/10 for a high-stakes business decision. With these corrections and additions incorporated, the combined analysis earns an **8/10** — strong enough to inform strategy, with the caveat that both products are evolving rapidly and any recommendation should be revisited quarterly.

---

## 13. Deployment Recommendation: Setting Up CoCo with Effective Cost Controls

This section provides an operational blueprint for deploying Cortex Code across a data engineering team with cost governance that maximizes self-service access without creating budget risk. Every parameter, SQL statement, and role grant below is GA and verified against current Snowflake documentation.

### Step 1: Access Control — Who Gets CoCo

Cortex Code access is controlled through Snowflake database roles, not account roles. Two roles matter:

- **SNOWFLAKE.CORTEX_USER** — Required for CLI access and (along with COPILOT_USER) for Snowsight access
- **SNOWFLAKE.COPILOT_USER** — Required for Snowsight access

By default, these roles are granted through PUBLIC, meaning everyone in your account has access. For controlled rollout, revoke from PUBLIC and grant to specific roles:

```sql
-- Revoke default access
REVOKE DATABASE ROLE SNOWFLAKE.CORTEX_USER FROM ROLE PUBLIC;
REVOKE DATABASE ROLE SNOWFLAKE.COPILOT_USER FROM ROLE PUBLIC;

-- Grant to your data engineering roles
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE DATA_ENGINEERS;
GRANT DATABASE ROLE SNOWFLAKE.COPILOT_USER TO ROLE DATA_ENGINEERS;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE ANALYTICS_ENGINEERS;
GRANT DATABASE ROLE SNOWFLAKE.COPILOT_USER TO ROLE ANALYTICS_ENGINEERS;
```

CoCo respects all existing RBAC, row-level security policies, and dynamic data masking. Users can only access data their current role permits, even through CoCo.

### Step 2: Model Access — Control Cost at the Source

The single most impactful cost lever is controlling which models your team can use. Opus 4.6 output costs $27.50/MTok through CoCo; Sonnet 4.6 costs $16.50/MTok; GPT 5.2 costs $15.40/MTok. Restricting to Sonnet saves 40% per output token vs. Opus with minimal quality loss on routine data engineering work.

```sql
-- Restrict available models account-wide (ACCOUNTADMIN required)
ALTER ACCOUNT SET CORTEX_MODELS_ALLOWLIST = 'claude-sonnet-4-6,claude-sonnet-4-5,openai-gpt-5.2';
```

Valid values: `'All'` (default, everything available), `'None'` (block all), or a comma-separated list of specific model names.

**Important limitation:** This is account-level only. You cannot set different model allowlists per user or per role. If your senior engineers need Opus for complex reasoning tasks, you'll either need to allow it account-wide or have them use Claude Code directly (via Max subscription) for Opus-tier work while CoCo handles the Sonnet-tier Snowflake operations.

**Recommended approach:** Start with Sonnet-only for the first 30 days. Monitor quality of CoCo's output. If specific use cases genuinely need Opus (complex multi-step reasoning, ambiguous schema interpretation), add it to the allowlist and rely on daily credit caps (Step 3) to manage the cost impact.

### Step 3: Daily Credit Caps — Set the Budget Guardrails

Two parameters control daily per-user spending, one for each CoCo surface:

```sql
-- Set conservative account-wide defaults (ACCOUNTADMIN required)
ALTER ACCOUNT SET CORTEX_CODE_CLI_DAILY_EST_CREDIT_LIMIT_PER_USER = 25;
ALTER ACCOUNT SET CORTEX_CODE_SNOWSIGHT_DAILY_EST_CREDIT_LIMIT_PER_USER = 15;

-- Grant higher limits to power users who need them
ALTER USER senior_engineer_1 SET CORTEX_CODE_CLI_DAILY_EST_CREDIT_LIMIT_PER_USER = 75;
ALTER USER senior_engineer_1 SET CORTEX_CODE_SNOWSIGHT_DAILY_EST_CREDIT_LIMIT_PER_USER = 50;

-- Remove per-user override (user falls back to account default)
ALTER USER senior_engineer_1 UNSET CORTEX_CODE_CLI_DAILY_EST_CREDIT_LIMIT_PER_USER;

-- Block a specific user entirely
ALTER USER contractor_temp SET CORTEX_CODE_CLI_DAILY_EST_CREDIT_LIMIT_PER_USER = 0;
```

**How it works:** These track estimated credit usage over a rolling 24-hour window. When a user hits the threshold, access is blocked immediately until their rolling usage drops below the limit. Default value of -1 means unlimited.

**Setting the right limits:** At $2.00/AI Credit (On Demand Global) with Sonnet 4.6, a daily cap of 25 AI Credits translates to roughly $50/day or ~$1,100/month maximum per user. A cap of 15 AI Credits for Snowsight translates to ~$30/day or ~$660/month. Combined, that's a worst-case ceiling of ~$1,760/month per user, which is still meaningfully higher than a Claude Max subscription but puts a hard floor under budget risk.

**Tiered access example for a 30-person team:**

| Tier | Users | CLI Limit | Snowsight Limit | Max Monthly/User | Max Monthly Total |
|------|-------|-----------|----------------|-----------------|-------------------|
| Standard (most engineers) | 20 | 15 credits | 10 credits | ~$1,100 | ~$22,000 |
| Power users (senior/leads) | 8 | 40 credits | 25 credits | ~$2,860 | ~$22,880 |
| Admin/architect | 2 | 75 credits | 50 credits | ~$5,500 | ~$11,000 |
| **Team total (worst case)** | **30** | | | | **~$55,880** |
| **Realistic (60% utilization)** | **30** | | | | **~$33,500** |

**Reality check:** Most users won't hit their daily cap most days. The "worst case" column assumes every user maxes out every business day. Actual spend will likely be 40–60% of the ceiling, which puts a 30-person team at roughly $22K–$34K/month on CoCo. Compare to $3,000/month for Claude Max 5x for the same team size.

### Step 4: Monitoring — Build Visibility Before You Need It

Set up monitoring from day one, not after the first surprise bill.

**Daily usage by user (last 30 days):**
```sql
SELECT
  u.NAME AS USERNAME,
  DATE(h.USAGE_TIME) AS USAGE_DATE,
  SUM(h.TOKEN_CREDITS) AS DAILY_CREDITS,
  ROUND(SUM(h.TOKEN_CREDITS) * 2.00, 2) AS DAILY_COST_USD,
  COUNT(*) AS REQUEST_COUNT
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY h
JOIN SNOWFLAKE.ACCOUNT_USAGE.USERS u ON h.USER_ID = u.USER_ID
WHERE h.USAGE_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY u.NAME, DATE(h.USAGE_TIME)
ORDER BY USAGE_DATE DESC, DAILY_CREDITS DESC;
```

**Combined CLI + Snowsight spend, top users (last 7 days):**
```sql
SELECT
  u.NAME AS USERNAME,
  SUM(combined.TOKEN_CREDITS) AS TOTAL_CREDITS,
  ROUND(SUM(combined.TOKEN_CREDITS) * 2.00, 2) AS TOTAL_COST_USD,
  COUNT(*) AS TOTAL_REQUESTS
FROM (
  SELECT USER_ID, TOKEN_CREDITS, USAGE_TIME
  FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
  UNION ALL
  SELECT USER_ID, TOKEN_CREDITS, USAGE_TIME
  FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY
) combined
JOIN SNOWFLAKE.ACCOUNT_USAGE.USERS u ON combined.USER_ID = u.USER_ID
WHERE combined.USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY u.NAME
ORDER BY TOTAL_CREDITS DESC;
```

### Step 5: Automated Alerts — The Missing Piece You Build Yourself

Snowflake's daily credit caps block access but don't warn users. You can build graduated alerts using Snowflake's native ALERT and NOTIFICATION INTEGRATION features:

```sql
-- Step 5a: Create email notification integration
CREATE OR REPLACE NOTIFICATION INTEGRATION cortex_code_alerts
  TYPE = EMAIL
  ENABLED = TRUE
  ALLOWED_RECIPIENTS = ('admin@yourcompany.com', 'finops@yourcompany.com')
  DEFAULT_RECIPIENTS = ('admin@yourcompany.com')
  DEFAULT_SUBJECT = 'Cortex Code Usage Alert';

-- Step 5b: Alert when any user exceeds 75% of their daily budget
-- (runs every 6 hours; adjust SCHEDULE and threshold to taste)
CREATE OR REPLACE ALERT cortex_code_approaching_limit
  WAREHOUSE = MONITORING_WH
  SCHEDULE = '360 MINUTE'
  IF(EXISTS(
    SELECT USER_ID, SUM(TOKEN_CREDITS) AS daily_total
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
    WHERE USAGE_TIME >= DATEADD('hour', -24, CURRENT_TIMESTAMP())
    GROUP BY USER_ID
    HAVING SUM(TOKEN_CREDITS) > 18.75  -- 75% of 25-credit default limit
  ))
  THEN
    CALL SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
      'One or more users approaching daily Cortex Code credit limit. Review usage in CORTEX_CODE_CLI_USAGE_HISTORY.',
      'cortex_code_alerts'
    );

-- Step 5c: Weekly team spend summary (Monday 9 AM)
CREATE OR REPLACE ALERT cortex_code_weekly_summary
  WAREHOUSE = MONITORING_WH
  SCHEDULE = 'USING CRON 0 9 * * MON America/New_York'
  IF(EXISTS(
    SELECT 1 FROM (
      SELECT SUM(TOKEN_CREDITS) AS weekly_total
      FROM (
        SELECT TOKEN_CREDITS, USAGE_TIME FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
        UNION ALL
        SELECT TOKEN_CREDITS, USAGE_TIME FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY
      )
      WHERE USAGE_TIME >= DATEADD('week', -1, CURRENT_TIMESTAMP())
    )
    WHERE weekly_total > 0
  ))
  THEN
    CALL SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
      'Weekly Cortex Code spend report ready. Query CORTEX_CODE_CLI_USAGE_HISTORY and CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY for details.',
      'cortex_code_alerts'
    );

-- Step 5d: Activate the alerts
ALTER ALERT cortex_code_approaching_limit RESUME;
ALTER ALERT cortex_code_weekly_summary RESUME;
```

**Alert constraints worth knowing:** Recipients must be verified Snowflake account users. Max 50 recipients per integration. Alerts are suspended by default and must be explicitly resumed. The alert warehouse will consume credits when it runs (keep the schedule reasonable).

### Step 6: Recommended Rollout Timeline

**Week 1–2 (Pilot):** Grant CoCo access to 5–8 early adopters. Set model allowlist to Sonnet-only. Set conservative daily caps (15 CLI, 10 Snowsight). Deploy monitoring queries. Activate alerts. Collect baseline usage data.

**Week 3–4 (Calibrate):** Review actual usage patterns from monitoring views. Adjust daily caps based on real consumption (most users will be well under the ceiling). Identify power users who need higher limits. Evaluate whether Opus is needed for specific use cases.

**Month 2 (Expand):** Roll out to full data engineering team with tiered limits (Standard / Power / Admin). Refine alert thresholds based on observed patterns. Build a Snowsight dashboard from the usage history views for ongoing FinOps visibility.

**Month 3+ (Optimize):** Compare CoCo spend against Claude Max subscription costs for the same team. Identify users who would be better served by Claude Max (heavy daily users) vs. CoCo (light-to-moderate Snowflake-focused users). Adjust the portfolio.

### The Honest Sizing Question

For a team that will use CoCo as their primary AI tool all day, the math still favors Claude Max subscriptions on pure cost. CoCo's value proposition for enterprise deployment is not "cheaper than Claude Max" — it's "zero-friction Snowsight integration, governance perimeter, deep Snowflake metadata awareness, and unified Snowflake billing." Those are real organizational benefits that justify a cost premium for the right use cases. The deployment strategy above ensures that premium stays governable and visible, not open-ended.

---

## Sources

- [Snowflake Service Consumption Table (PDF)](https://www.snowflake.com/legal-files/CreditConsumptionTable.pdf) — **Primary pricing source for all Cortex Code and AI Credit rates**
- [Anthropic Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing) — **Primary pricing source for direct Claude API rates**
- [Cortex Code Documentation](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code)
- [Cortex Code in Snowsight GA Release Notes](https://docs.snowflake.com/en/release-notes/2026/other/2026-03-09-cortex-code-snowsight-ga)
- [Cortex Code CLI GA Release Notes](https://docs.snowflake.com/en/release-notes/2026/other/2026-02-02-cortex-code-cli)
- [Cortex Code CLI Expands Support](https://www.snowflake.com/en/blog/cortex-code-cli-expands-support/)
- [Snowflake Standalone Subscription for Cortex Code](https://www.crnasia.com/india/news/2026/snowflake-introduces-standalone-subscription-for-cortex-code-signals-shift-toward-developer-led-ai-monetisation)
- [Cortex Code Capabilities and Pricing — Keyrus](https://keyrus.com/us/en/insights/snowflake-cortex-code-explained-capabilities-pricing-and-real-world-use)
- [The Hidden Cost of Snowflake Cortex AI — Seemore Data](https://seemoredata.io/blog/snowflake-cortex-ai/)
- [Snowflake Cortex Cost Comparison 2026 — DataEngineer Hub](https://dataengineerhub.blog/articles/snowflake-cortex-cost-comparison)
- [Snowflake MCP Server — GitHub](https://github.com/Snowflake-Labs/mcp)
- [Snowflake Managed MCP Servers](https://www.snowflake.com/en/blog/managed-mcp-servers-secure-data-agents/)
- [Snowflake + Anthropic $200M Partnership](https://www.anthropic.com/news/snowflake-anthropic-expanded-partnership)
- [Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Claude Plans & Pricing](https://claude.com/pricing)
- [What is Cortex Code — phData](https://www.phdata.io/blog/what-is-cortex-code-and-why-does-it-matter/)
- [Cortex Code vs Claude Code Benchmarks](https://www.snowflake.com/en/blog/cortex-code-snowsight/)
- [Claude Code Pricing Guide: Which Plan Saves You Money](https://www.ksred.com/claude-code-pricing-guide-which-plan-actually-saves-you-money/) — **Real-world 10B token usage tracking**
- [Cursor Pricing 2026 — PE Collective](https://pecollective.com/tools/cursor-pricing/)
- [Cursor Pricing, Credits & Cost Breakdown — Get AI Perks](https://www.getaiperks.com/en/articles/cursor-pricing)
- [Claude Code Pro vs Max 2026](https://blog.laozhang.ai/en/posts/claude-code-pro-vs-max)
- [Frosty: AI Agent for Snowflake — GitHub](https://github.com/Gyrus-Dev/frosty)
- [Claude Code with Ollama Local Models](https://docs.ollama.com/integrations/claude-code)
- [Running Claude Code with Local LLM — Shawn Mayzes](https://www.shawnmayzes.com/product-engineering/running-claude-code-with-local-llm/)
- [Claude Code BYOM Feature Request — GitHub](https://github.com/anthropics/claude-code/issues/7178)
- [Use Claude Code with Your Own Model — RunPod](https://www.runpod.io/blog/use-claude-code-with-your-own-model-on-runpod-no-anthropic-account-required)
- [No, it doesn't cost Anthropic $5k per Claude Code user — Martin Alderson](https://martinalderson.com/posts/no-it-doesnt-cost-anthropic-5k-per-claude-code-user/)
- [Are OpenAI and Anthropic Really Losing Money on Inference? — Martin Alderson](https://martinalderson.com/posts/are-openai-and-anthropic-really-losing-money-on-inference/)
- [Anthropic Lowers Gross Margin Projection — The Information](https://www.theinformation.com/articles/anthropic-lowers-profit-margin-projection-revenue-skyrockets)
- [Sam Altman says OpenAI is losing money on Pro subscriptions — Fortune](https://fortune.com/2025/01/07/sam-altman-openai-chatgpt-pro-subscription-losing-money-tech/)
- [Cursor quietly built its new coding model on top of Chinese open-source Kimi K2.5 — The Decoder](https://the-decoder.com/cursor-quietly-built-its-new-coding-model-on-top-of-chinese-open-source-kimi-k2-5/)
- [What Cursor's fine-tuned model means for the AI ecosystem — PromptHub](https://prompthub.substack.com/p/what-cursors-fine-tuned-model-means)
- [Welcome to LLMflation — a16z](https://a16z.com/llmflation-llm-inference-cost/)
- [Gartner Predicts 90% Cost Reduction by 2030](https://www.gartner.com/en/newsroom/press-releases/2026-03-25-gartner-predicts-that-by-2030-performing-inference-on-an-llm-with-1-trillion-parameters-will-cost-genai-providers-over-90-percent-less-than-in-2025)
- [LLM inference prices have fallen rapidly — Epoch AI](https://epoch.ai/data-insights/llm-inference-price-trends)
- [Snowflake Arctic — Open Efficient Foundation Language Models](https://www.snowflake.com/en/blog/arctic-open-efficient-foundation-language-models-snowflake/)
- [New LLM: Snowflake Arctic Model for SQL and Code Generation — NVIDIA](https://developer.nvidia.com/blog/new-llm-snowflake-arctic-model-for-sql-and-code-generation/)
- [Cost Controls for Cortex Code — Snowflake Docs](https://docs.snowflake.com/en/user-guide/cortex-code/credit-usage-limit)
- [CORTEX_CODE_CLI_USAGE_HISTORY — Snowflake Docs](https://docs.snowflake.com/en/sql-reference/account-usage/cortex_code_cli_usage_history)
- [CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY — Snowflake Docs](https://docs.snowflake.com/en/sql-reference/account-usage/cortex_code_snowsight_usage_history)
- [Managing Cortex AI Function Costs — Snowflake Docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/ai-func-cost-management)
- [Cortex Code Settings — Snowflake Docs](https://docs.snowflake.com/en/user-guide/cortex-code/settings)
- [Cortex Code Security Best Practices — Snowflake Docs](https://docs.snowflake.com/en/user-guide/cortex-code/security)
- [Cortex Code in Snowsight — Snowflake Docs](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-snowsight)
- [Snowflake CREATE ALERT — Snowflake Docs](https://docs.snowflake.com/en/sql-reference/sql/create-alert)
- [Snowflake Email Notification Integration — Snowflake Docs](https://docs.snowflake.com/en/sql-reference/sql/create-notification-integration-email)
- [AWS Bedrock vs Azure OpenAI vs Google Vertex AI — CloudOptimo](https://www.cloudoptimo.com/blog/amazon-bedrock-vs-azure-openai-vs-google-vertex-ai-an-in-depth-analysis/)
- [Azure OpenAI vs OpenAI API Pricing — OreateAI](https://www.oreateai.com/blog/navigating-the-ai-cost-maze-azure-openai-vs-openai-api-pricing/)
- [Google Vertex AI Claude Pricing Comparison — Skywork AI](https://skywork.ai/blog/claude-haiku-4-5-vertex-ai-vs-anthropic-api-2025-comparison-guide/)
