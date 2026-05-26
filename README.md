# snowfort

Your Snowflake account is bleeding money in places you can't see. snowfort scans it and shows you
where.

It also checks how safe your account is, how fast queries run, whether backups will work when you
need them, and a few other things you probably haven't had time to look at.

You run it, it gives you a letter grade (A through F) and a list of things to fix. That's the whole
idea.

## Install

```bash
pipx install snowfort-audit
```

(If you don't have pipx, `pip install snowfort-audit` works too. pipx just keeps things tidy.)

## 5-minute quickstart

1. **Tell snowfort how to log in to Snowflake.** This sets a few environment variables in your
   current shell:

   ```bash
   eval "$(snowfort login)"
   ```

   It will ask for your account, user, role, and how you sign in (SSO, key-pair, or MFA password).

2. **Run a scan.**

   ```bash
   snowfort audit scan
   ```

   It connects to your account, runs the checks, and prints a scorecard with your grade plus a list
   of things to fix.

3. **(Optional) Save the results as JSON** for CI or for your own tooling:

   ```bash
   snowfort audit scan --manifest > scan.json
   ```

That's it. A first scan takes a few minutes on a busy account.

## What it actually checks

snowfort runs 164 checks across six areas (Snowflake calls them WAF pillars):

- **Cost** — warehouses that never sleep, oversized clusters, Cortex AI runaway spend, stale tables
  costing you fail-safe storage.
- **Security** — admins with too much access, missing MFA, open network policies, password-only
  users, leaky data shares.
- **Performance** — queries that spill to disk, undersized warehouses, missing cluster keys, slow
  queues.
- **Reliability** — missing replication, zero-day time travel on production tables, dynamic tables
  that keep failing.
- **Operations** — missing resource monitors, missing tags, no alert wiring, no notifications.
- **Governance** — undocumented objects, sensitive columns with no masking, future grants spread
  everywhere, no account budget.

Run `snowfort audit rules` to see the full list with rule IDs. _Rule count last verified 2026-05-26._

## Try it without a Snowflake account

There's an offline mode that scans SQL files and project configs. No login needed:

```bash
git clone https://github.com/noah-goodrich/snowfort
cd snowfort/packages/snowfort-audit
snowfort audit scan --offline --path examples/offline_showcase
```

You'll see a sample scorecard with intentional violations to play with.

## What this is for

Engineers who got handed a Snowflake bill and a vague mandate to "clean it up." FinOps folks who
want a single grade per account. Platform leads who want one tool to check security, cost, and
reliability instead of three.

The output is plain JSON. You can pipe it into a dashboard, drop it into a Jira ticket, hand it to
an LLM for fix suggestions, or stick it in a CI pipeline that blocks bad deploys.

## More docs

- [Full rule catalog](packages/snowfort-audit/docs/RULES_CATALOG.md) — every rule, every ID, every
  severity.
- [Scoring rubric](packages/snowfort-audit/docs/SEVERITY_AND_GRADING.md) — how the letter grade is
  computed.
- [Performance and concurrency](packages/snowfort-audit/docs/PERFORMANCE.md) — how to run scans
  faster on big accounts.
- [Package README](packages/snowfort-audit/README.md) — deeper notes on each mode, custom rules,
  Cortex augmentation.
- [Contributing](CONTRIBUTING.md) — how to file a bug or open a PR.
- [Security policy](SECURITY.md) — how to report a vulnerability.

## Support

I respond to issues within 7 days when life and the day job allow. I treat
security-tagged issues as priority. I do not promise specific fixes within specific
windows. If your business depends on a specific response time, please email me
([goodrich.noah@gmail.com](mailto:goodrich.noah@gmail.com)) for a paid support
arrangement.

Snowfort is maintained by one person with a family and a full-time job. Filing a clear,
reproducible bug report is the single highest-leverage thing you can do to help yours
get fixed quickly. See [CONTRIBUTING.md](CONTRIBUTING.md) for what makes a useful issue.

## License

MIT. Built by Noah Goodrich. If snowfort saves you money, a GitHub star or a sponsor
click goes a long way.
