# Local dev: Keyring and browser auth

Run `make check` for lint and tests.

Run `pytest tests/functional/test_login_flow.py -v` for login flow tests (exported session vars for mfa/keypair/pat).

To set Snowflake env vars in your shell you must run login as an argument to eval: `eval $(snowfort login)` (otherwise the exports are only printed and not applied).

Keyring in devcontainer: .devcontainer/devcontainer.json sets KEYRING_BACKEND and KEYRING_FILE_PATH. Install keyrings.alt in the container (e.g. pip install keyrings.alt) so the file backend is available.

**Auth menu:** mfa, keypair, pat, and browser (SSO via externalbrowser) are offered. You can also set
`SNOWFLAKE_AUTHENTICATOR` to a custom IdP URL for SAML/SSO configurations. For headless environments
without a display, set `SNOWFLAKE_AUTH_FORCE_SERVER_URL=1` and open the printed URL manually.
