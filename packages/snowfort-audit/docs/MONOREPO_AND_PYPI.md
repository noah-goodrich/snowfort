# Migrating snowfort-audit to a Monorepo and PyPI Deployment

Summary and step-by-step instructions for (1) moving snowfort-audit into a monorepo and (2) publishing to PyPI so users can `pip install snowfort-audit`.

---

## Summary

- **Current state:** snowfort-audit is a standalone package (single `pyproject.toml`, `src/snowfort_audit/`, entry point `snowfort`). It can be run from source or installed in editable mode.
- **Goal:** (1) Place it inside a monorepo (e.g. `packages/snowfort-audit/` or `snowfort/packages/snowfort-audit/`) so it lives alongside other tools (admin, scaffold, etc.). (2) Publish releases to PyPI so production installs use `pip install snowfort-audit`.
- **Main steps:** Create or adopt a monorepo layout → move the package → adjust paths and optional deps → add version/CHANGELOG workflow → build wheel/sdist → publish with Twine (manual or CI).

---

## Part 1: Monorepo layout and moving the package

### 1.1 Choose monorepo structure

Two common patterns:

**A. New monorepo from scratch**

- Create a new repo (e.g. `snowfort` or `snowarch`).
- Root can have a root `pyproject.toml` (optional, for shared dev tooling) and a `packages/` (or `apps/`) directory.
- Put snowfort-audit under e.g. `packages/snowfort-audit/` with its current contents (`pyproject.toml`, `src/`, `tests/`, `docs/`, `examples/`, etc.).

**B. Add to an existing monorepo**

- If you already have a monorepo (e.g. `snowarch` with `packages/snowarch-admin`, `packages/snowarch-scaffold`), add a sibling: `packages/snowfort-audit/`.
- Copy or move the full snowfort-audit tree into that directory (preserve `src/snowfort_audit`, `pyproject.toml`, tests, docs).

### 1.2 Move the package

1. **Create the target directory** in the monorepo, e.g. `packages/snowfort-audit/`.
2. **Copy or move** into it:
   - `pyproject.toml`
   - `src/`
   - `tests/`
   - `docs/`
   - `examples/`
   - `README.md`
   - Any other files (e.g. `Makefile`, `scripts/`, `.cursor/`) you want to keep.
3. **Do not** copy repo-specific dirs like `.git`, `.pytest_cache`, `.snowfort` (local cache), or `venv`/`.venv`.
4. **Root `pyproject.toml` (optional):** If the monorepo root has one, you can add a workspace or reference to `packages/snowfort-audit` for local dev; otherwise each package is installed independently (e.g. `pip install -e packages/snowfort-audit`).

### 1.3 Fix optional dev dependencies for PyPI

The current `[project.optional-dependencies]` dev includes:

```toml
"pytest-coverage-impact @ file:///development/pytest-coverage-impact"
```

- **For PyPI:** This path is not valid on PyPI. Either:
  - Remove that line from `[project.optional-dependencies].dev`, or
  - Make it conditional (e.g. only when that package is present in the monorepo) or replace with a PyPI-published package name if one exists.
- **Local monorepo dev:** If pytest-coverage-impact lives in the same monorepo (e.g. `packages/pytest-coverage-impact`), use a relative path or a workspace dependency if your tooling supports it (e.g. `pytest-coverage-impact @ file:///${PROJECT_ROOT}/../pytest-coverage-impact` in a script, or omit from published extras).

### 1.4 Verify the package from the new location

From the monorepo root or from `packages/snowfort-audit/`:

```bash
cd packages/snowfort-audit   # or your path
pip install -e ".[dev]"      # if you removed or fixed the file:// dev dep
snowfort audit --help
snowfort audit scan --offline --path .
```

Tests:

```bash
pytest tests/ -v
```

---

## Part 2: Versioning and changelog

1. **Version in one place:** Keep `version = "0.1.0"` (or your next version) in `packages/snowfort-audit/pyproject.toml` under `[project]`.
2. **Bump before release:** For each PyPI release, bump the version (e.g. 0.1.0 → 0.1.1 or 0.2.0). Optionally maintain a `CHANGELOG.md` in the package or at monorepo root.
3. **Tagging:** Tag releases in git (e.g. `snowfort-audit/v0.1.0` or `v0.1.0` if single-package repo) so you can correlate PyPI releases with source.

---

## Part 3: Build and publish to PyPI

### 3.1 One-time setup

1. **PyPI account:** Create an account on [pypi.org](https://pypi.org) (and optionally [test.pypi.org](https://test.pypi.org) for dry runs).
2. **API token:** On PyPI, create a project (or use “existing project” at first upload) and create an API token with scope for that project. Store it in a secret (e.g. `PYPI_API_TOKEN`) or in `~/.pypirc` (never commit tokens).
3. **Install build tools** (in a venv or CI image):
   ```bash
   pip install build twine
   ```

### 3.2 Build the distribution

From the **package directory** (e.g. `packages/snowfort-audit/`):

```bash
cd packages/snowfort-audit
python -m build
```

This produces:

- `dist/snowfort_audit-<version>.tar.gz` (sdist)
- `dist/snowfort_audit-<version>-py3-none-any.whl` (wheel, or platform-specific if you have binary deps)

Ensure `version` in `pyproject.toml` is what you want to publish.

### 3.3 Publish to PyPI

**Test PyPI (recommended first time):**

```bash
twine upload --repository testpypi dist/*
# When prompted, use __token__ and your Test PyPI token.
# Install test: pip install --index-url https://test.pypi.org/simple/ snowfort-audit
```

**Production PyPI:**

```bash
twine upload dist/*
# Use __token__ and your PyPI API token.
```

After a successful upload, users can:

```bash
pip install snowfort-audit
snowfort audit --help
```

### 3.4 Automate with CI (e.g. GitHub Actions)

Example pattern:

- **Trigger:** On push of a version tag (e.g. `v0.1.0`) or on release workflow dispatch.
- **Steps:**
  1. Check out repo (monorepo).
  2. Set up Python (e.g. 3.10 or 3.11).
  3. `pip install build twine`.
  4. `cd packages/snowfort-audit` (or the path where `pyproject.toml` lives).
  5. `python -m build`.
  6. `twine upload dist/*` (use `TWINE_PASSWORD` / `TWINE_USERNAME` or `TWINE_TOKEN` from secrets).

Example (minimal) job:

```yaml
# .github/workflows/publish-snowfort-audit.yml
name: Publish snowfort-audit to PyPI
on:
  release:
    types: [published]
  workflow_dispatch:
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build twine
      - name: Build
        run: python -m build
        working-directory: packages/snowfort-audit   # adjust path
      - name: Publish
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
        working-directory: packages/snowfort-audit
```

Adjust `working-directory` if your monorepo layout differs. For tag-based releases, you can derive the version from the tag and update `pyproject.toml` in a prior step, or keep version only in `pyproject.toml` and tag after release.

---

## Part 4: Post-migration checklist

- [ ] Package lives under monorepo path (e.g. `packages/snowfort-audit/`).
- [ ] `pip install -e packages/snowfort-audit` (or equivalent) works from monorepo root.
- [ ] Dev optional dependency on `pytest-coverage-impact` is removed or made non-blocking for PyPI.
- [ ] Version in `pyproject.toml` is set and bumped for each release.
- [ ] `python -m build` runs without errors from the package directory.
- [ ] Test upload to Test PyPI and install from it.
- [ ] Production upload to PyPI; `pip install snowfort-audit` works.
- [ ] CI workflow (optional) runs on tag or release and publishes to PyPI.
- [ ] README and docs reference the PyPI package and, if applicable, the monorepo structure.

---

## Quick reference

| Step | Command / action |
|------|-------------------|
| Build | `cd packages/snowfort-audit && python -m build` |
| Upload (Test) | `twine upload --repository testpypi dist/*` |
| Upload (PyPI) | `twine upload dist/*` |
| Install from PyPI | `pip install snowfort-audit` |
| Entry point | `snowfort` (invokes `snowfort_audit.interface.cli:main`) |

---

*Doc created for “migrating snowfort-audit to a monorepo and setting up deploying through PyPI.” Adjust paths and repo names to match your monorepo.*
