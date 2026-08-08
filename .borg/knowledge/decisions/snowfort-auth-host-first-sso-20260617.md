---
id: snowfort-auth-host-first-sso-20260617
date: '2026-06-18'
project: snowfort
domain: dev-environment
tags:
- auth
- sso
- secrets
- host-first
- devcontainer
- snowflake
- keyring
alternatives: []
applies_to: []
confidence: 0.9
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: 20260616-2201-snowfort
created_at: '2026-06-18 00:29:03.122904+00:00'
updated_at: '2026-06-18 00:29:03.122907+00:00'
---

# snowfort-auth-host-first-sso-20260617

## decision

Snowflake authentication, secret storage, and SSO for snowfort dev all run on the HOST, not inside the devcontainer. The container is only a drone exec dispatch target for the Python toolchain (lint/mypy/pytest/CLI).

## context

Repo-wide host-first switch (2026-05-01 directive 2026-05-01-host-first-running-things.md) and snowfort root CLAUDE.md Running things section. Folded into packages/snowfort-audit/docs/LOCAL_DEV_AUTH.md on 2026-06-17.

## reasoning

Secrets live in the host macOS keyring via env->keyring->prompt resolution in ConnectionResolver.resolve(). The devcontainer has no system keyring (uses keyrings.alt file backend) and is headless, so SSO via externalbrowser cannot pop a browser there; headless escape hatch is SNOWFLAKE_AUTH_FORCE_SERVER_URL=1 plus opening the printed URL. Learned bug: defaulting the authenticator to externalbrowser from env short-circuits the interactive prompt so password/MFA is never asked; fix is to use externalbrowser only as the displayed prompt default. Interactive auth (SSO/MFA) supports one connection so --workers N falls back to 1. Cortex CLI is host-only, never proxied through the container. Distinct unrelated meaning: sso_enforced and SEC_015 SSOCoverageCheck in the rules layer are an audit signal about the TARGET account, not dev login.
