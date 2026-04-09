#!/usr/bin/env python3
"""Lint rule files for sensitive substrings in violation messages.

Scans all Python files under src/snowfort_audit/domain/rules/ for string literals
that contain patterns associated with credential material.  Intended as a
pre-commit / CI gate — exits non-zero if any matches are found.

Usage:
    python scripts/check_sensitive_outputs.py [PATH ...]

    # Scan all rule files (default):
    python scripts/check_sensitive_outputs.py

    # Scan a specific file:
    python scripts/check_sensitive_outputs.py src/snowfort_audit/domain/rules/security.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Patterns that must not appear in string literals inside violation message
# construction (self.violation(...), Violation(...)).  Case-insensitive.
_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bpassword\b", re.IGNORECASE),
    re.compile(r"\bsecret\b", re.IGNORECASE),
    re.compile(r"\bprivate[_\s]?key\b", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
    re.compile(r"-----BEGIN", re.IGNORECASE),
    re.compile(r"-----END", re.IGNORECASE),
    # Raw hex-encoded material (32+ hex chars in a row — likely a hash or key)
    re.compile(r"[0-9a-fA-F]{32,}"),
]

# File-level comment allowlist: lines containing these strings are not checked.
# Add entries here only for deliberate references (e.g., "token" in SQL column names).
_ALLOWLIST_COMMENTS = ("# sensitive-output-ok",)

# Context window: we flag a line if it's inside a violation-construction call.
# We detect this by looking for the call pattern in the surrounding lines.
_VIOLATION_CALL_PATTERN = re.compile(
    r"(self\.violation|Violation\(|remediation_instruction\s*=)", re.IGNORECASE
)


def _is_allowlisted(line: str) -> bool:
    return any(marker in line for marker in _ALLOWLIST_COMMENTS)


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (lineno, pattern_name, line) for suspicious lines."""
    findings: list[tuple[int, str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"  ERROR reading {path}: {exc}", file=sys.stderr)
        return findings

    # Simple heuristic: scan string literals (lines with quotes) that are near
    # a violation construction call.  We look at a 10-line context window.
    for i, line in enumerate(lines):
        if _is_allowlisted(line):
            continue
        # Only care about string literal lines
        if '"' not in line and "'" not in line:
            continue
        # Check if we're in a violation-construction context (10-line window)
        window_start = max(0, i - 5)
        window_end = min(len(lines), i + 5)
        window = "\n".join(lines[window_start:window_end])
        if not _VIOLATION_CALL_PATTERN.search(window):
            continue
        for pattern in _SENSITIVE_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append((i + 1, pattern.pattern, line.rstrip()))
                break  # One finding per line is enough

    return findings


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if args:
        paths = [Path(p) for p in args]
    else:
        repo_root = Path(__file__).resolve().parent.parent
        rules_dir = repo_root / "src" / "snowfort_audit" / "domain" / "rules"
        paths = sorted(rules_dir.rglob("*.py"))

    if not paths:
        print("No files to scan.")
        return 0

    total_findings = 0
    for path in paths:
        if not path.is_file():
            print(f"  SKIP {path} (not a file)")
            continue
        findings = _scan_file(path)
        if findings:
            total_findings += len(findings)
            print(f"\nFAIL {path}")
            for lineno, pattern, line in findings:
                print(f"  line {lineno}: matched /{pattern}/")
                print(f"    {line[:120]}")

    if total_findings:
        print(f"\n{total_findings} sensitive-output finding(s). Review and fix, or add # sensitive-output-ok comment.")
        return 1

    print(f"OK — scanned {len(paths)} file(s), no sensitive-output findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
