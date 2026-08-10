# Security Policy

## Reporting a vulnerability

If you've found a security vulnerability in snowfort, please **do not** open a public
GitHub issue. Two responsible-disclosure channels:

- **GitHub Security Advisories** (preferred). Open a private advisory at
  <https://github.com/noah-goodrich/snowfort/security/advisories/new>. GitHub will
  notify the maintainer and keep the report private until a fix ships.
- **Email.** Send the details to
  [goodrich.noah@gmail.com](mailto:goodrich.noah@gmail.com) with `[snowfort security]`
  in the subject line.

Whichever channel you use, include:

- A description of the vulnerability.
- A minimal proof of concept or reproduction steps.
- The version of snowfort you reproduced it on (`snowfort --version`).
- The Snowflake context if relevant (edition, region, role used).
- Your assessment of impact and exploitability.

## What to expect

- **Acknowledgement within 7 days.** A solo maintainer with a day job runs this project,
  so the response is best-effort, not contractual. Security-tagged reports jump the
  line in front of feature work and routine triage.
- **Coordinated disclosure.** Once a fix is ready, the maintainer will work with you on
  a coordinated disclosure timeline. Standard window is 30 days from confirmation, but
  flexible if you have a different need.
- **Credit.** Reporters are credited in the release notes for the fix unless they ask
  to remain anonymous.

## Scope

**In scope.** Anything that would let a malicious actor:

- Exfiltrate Snowflake credentials, key material, or session tokens through snowfort.
- Trick snowfort into running SQL against a Snowflake account other than the one the
  user intended.
- Leak sensitive output (PII, account contents) through normal snowfort commands or
  the JSON manifest format.
- Execute arbitrary code through a snowfort plugin, custom rule, or config file.
- Privilege-escalate inside the snowfort process itself.

**Out of scope.** Issues that aren't actually snowfort's problem:

- Snowflake account misconfigurations that snowfort correctly flags as violations.
- Vulnerabilities in upstream dependencies that don't surface through a snowfort entry
  point. Report those upstream; snowfort will pick up the fix on its next release.
- Social-engineering attacks against the maintainer or against contributors.
- Denial-of-service through pathological input on a developer's own machine.

## Hardening notes for users

If you run snowfort against a live Snowflake account, the minimum-trust setup is:

- Use the dedicated `AUDITOR` role created by `snowfort audit bootstrap`, not
  `ACCOUNTADMIN` or any role with write privileges.
- Authenticate with key-pair or SSO, not password+MFA. Key material lives in your
  local keyring or filesystem, never in snowfort logs.
- Audit the JSON manifest before piping it to any external system. Resource names can
  surface in violation messages and the JSON, and they may be sensitive.

That's it. Thank you for taking the time to report responsibly.
