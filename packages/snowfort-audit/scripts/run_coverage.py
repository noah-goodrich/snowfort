#!/usr/bin/env python3
"""Run pytest with coverage and optionally coverage-impact; write reports to project root."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
term_path = root / "coverage_term.txt"
json_path = root / "coverage.json"

result = subprocess.run(
    [
        sys.executable, "-m", "pytest", "tests/",
        "--cov=src/snowfort_audit",
        "--cov-report=term-missing",
        f"--cov-report=json:{json_path}",
        "-q", "--tb=short",
    ],
    cwd=root,
    capture_output=True,
    text=True,
    timeout=180,
)
out = result.stdout + "\n" + result.stderr
term_path.write_text(out, encoding="utf-8")
print(out)
sys.exit(result.returncode)
