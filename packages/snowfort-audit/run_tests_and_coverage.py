#!/usr/bin/env python3
"""Run pytest with coverage and write report to coverage_report.txt."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
report_path = root / "coverage_report.txt"

result = subprocess.run(
    [
        sys.executable, "-m", "pytest", "tests/",
        "--cov=src/snowfort_audit",
        "--cov-report=term-missing:skip-covered",
        "--cov-report=html",
        "-v", "--tb=short",
    ],
    cwd=root,
    capture_output=True,
    text=True,
    timeout=120,
)
out = result.stdout + "\n" + result.stderr
report_path.write_text(out, encoding="utf-8")
print(f"Exit code: {result.returncode}, report written to {report_path}")
sys.exit(result.returncode)
