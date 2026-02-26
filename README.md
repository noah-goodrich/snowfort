# Snowfort monorepo

Monorepo for Snowfort tools. Packages live under `packages/`.

- **packages/snowfort-audit/** — WAF Policy Compliance auditor for Snowflake (`snowfort audit`).

**Local dev** (from repo root):

```bash
pip install -e packages/snowfort-audit
# or with dev extras:
pip install -e "packages/snowfort-audit[dev]"
snowfort audit --help
```

**Build for PyPI** (from package dir):

```bash
cd packages/snowfort-audit && python -m build
```
