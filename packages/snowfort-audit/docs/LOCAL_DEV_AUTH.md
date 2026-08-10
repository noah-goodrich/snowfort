# Local dev: auth, secrets, and the host/container split

Snowfort follows the repo-wide **host-first** convention (see root `CLAUDE.md` "Running things" and
`docs/plans/directives/2026-05-01-host-first-running-things.md`): you run on the host, and the devcontainer is only a
`drone exec` dispatch target for the Python toolchain (lint, mypy, pytest, the `snowfort audit` CLI). This doc records
how that split applies to Snowflake authentication and secrets — the place where host-vs-container actually bites.

## TL;DR

- Run auth on the **host**. Secrets live in the host keyring; SSO needs a real browser the container doesn't have.
- The container is headless: it can do file-backed keyring and password/keypair/PAT auth, but **not** interactive
  browser SSO without the `SNOWFLAKE_AUTH_FORCE_SERVER_URL` escape hatch.
- Cortex CLI is **host-only** — never proxy it through the container (per the host-first directive).

## Credential resolution and secrets

`ConnectionResolver.resolve()` resolves connection options in priority order: **env vars → keyring → interactive
prompt**.

- Secrets live on the **host keyring** (macOS keychain via the default `keyring` backend). This is why auth belongs on
  the host.
- The devcontainer has no system keyring, so `.devcontainer/devcontainer.json` sets `KEYRING_BACKEND` and
  `KEYRING_FILE_PATH`, and you must `pip install keyrings.alt` in the container to get the **file backend**.
  In-container auth therefore works, but against a file-based secret store — not your real keychain.
- Set the env vars in your shell by wrapping login in eval: **`eval $(snowfort login)`**. Without `eval`, the exports
  are only printed, not applied.

## Auth menu

`snowfort login` offers: **mfa, keypair, pat, and browser (SSO via `externalbrowser`)**. You can also set
`SNOWFLAKE_AUTHENTICATOR` to a custom IdP URL for SAML/SSO configurations.

Prompt order is **account → user → role → authenticator**, and password/passcode are requested *only* when the
authenticator is `snowflake` or `username_password_mfa`.

## SSO (externalbrowser) — host-only, and why

SSO completes via a browser IdP handshake, so it needs a display. A headless container can't pop a browser, which makes
**SSO effectively a host activity**.

- Headless fallback: set **`SNOWFLAKE_AUTH_FORCE_SERVER_URL=1`** and open the printed URL manually.
- **Gotcha we hit:** defaulting the authenticator to `externalbrowser` *from env* short-circuits the interactive
  prompt — it never asks for password/MFA and silently forces browser SSO. Fix: don't default from env; show
  `externalbrowser` only as the *displayed* prompt default, and fall back to it only after prompting (truly
  non-interactive).
- Concurrency: interactive auth (browser SSO, MFA) supports only one active connection, so `--workers N` auto-falls
  back to a single worker under SSO/MFA (see `docs/WAREHOUSE_SIZING.md`).

## Not to be confused with: SSO as an audit signal

"SSO" also appears in the rules layer in an unrelated sense: `sso_enforced` / `SEC_015 SSOCoverageCheck` downgrade rule
severity when the **audited** Snowflake account enforces SSO. That's about the target account, not your dev login —
easy to trip over when grepping for "sso".

## Tests

- `make check` — lint and tests (run via `drone exec snowfort -- ...`).
- `pytest tests/functional/test_login_flow.py -v` — login-flow tests; exported session vars for mfa/keypair/pat (and
  browser → `externalbrowser`). No real Snowflake connection or keyring is used; input is mocked via `_ask`.
