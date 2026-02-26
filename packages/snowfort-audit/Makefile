# Snowfort-audit: development targets
# Requires: pip install -e ".[dev]"
#
# Session-only Snowflake password (e.g. after copying from NordPass):
#   eval "$(make snowfort-env-password)"

.PHONY: check clean lint test coverage coverage-check coverage-impact sync-agent-docs snowfort-env-password

check: lint mypy test coverage-check  ## Full pre-merge gate (lint + mypy + test + coverage threshold)

clean:  ## Remove caches and build artifacts (__pycache__, .pytest_cache, .mypy_cache, .ruff_cache, .import_linter_cache, dist, eggs, coverage)
	rm -rf .pytest_cache .mypy_cache .ruff_cache .import_linter_cache
	find . -type d -name __pycache__ -print0 | xargs -0 rm -rf 2>/dev/null || true
	rm -rf build dist *.egg-info .eggs
	rm -rf .coverage htmlcov coverage_impact.json report.yaml

lint:  ## Run all linters (ruff + pylint-clean-architecture + import-linter)
	ruff check src/ tests/
	pylint src/ --load-plugins=clean_architecture_linter --disable=all --enable=W9001,W9013,W9301,W9201,W9003,W9014
	lint-imports

mypy:  ## Run mypy type checker
	mypy src/ tests/ examples/

test:  ## Run tests
	pytest tests/ -v --tb=short

coverage:  ## Run tests with full coverage report
	pytest tests/ --cov=src/snowfort_audit --cov-report=term-missing --cov-report=html -v --tb=short

coverage-check:  ## Run tests with coverage threshold (must stay >= 80%)
	pytest tests/ --cov=src/snowfort_audit --cov-fail-under=80 --cov-report=term-missing -q --tb=short

coverage-impact:  ## Full coverage + ML impact report. Writes coverage_impact.json.
	@echo "Running pytest with coverage-impact..."
	pytest tests/ \
		--cov=src/snowfort_audit \
		--cov-report=term-missing \
		--cov-report=json \
		--coverage-impact \
		--coverage-impact-top=50 \
		--coverage-impact-json=coverage_impact.json \
		-v --tb=short

sync-agent-docs:  ## Sync .agent/instructions.md to editor-specific locations
	@echo "Syncing agent instructions..."
	@mkdir -p .cortex/skills/snowfort-audit
	@cp .agent/instructions.md .cortex/skills/snowfort-audit/SKILL.md 2>/dev/null || true
	@echo "Done. Synced to .cortex/skills/"

snowfort-env-password:
	@read -s p; echo "export SNOWFLAKE_PASSWORD=$$(printf '%q' "$$p")"
