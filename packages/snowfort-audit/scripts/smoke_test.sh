#!/usr/bin/env bash
# Smoke test: seed a Snowflake account with WAF violations, run scans, validate.
# Prerequisites: snowfort-audit installed, Snowflake env vars set (eval "$(snowfort login)").
#
# Usage: ./scripts/smoke_test.sh
set -euo pipefail

echo "=== Snowfort Audit v0.3.0 Smoke Test ==="

# 1. Seed the account
echo ""
echo "--- Step 1: Seeding test violations ---"
snowfort audit demo-setup
echo "Seed complete."

# 2. Sequential scan with profiling
echo ""
echo "--- Step 2: Sequential scan (--workers 1 --profile) ---"
snowfort audit scan --workers 1 --profile 2>&1 | tee /tmp/snowfort_smoke_seq.log
SEQ_EXIT=$?

# 3. Parallel scan with profiling
echo ""
echo "--- Step 3: Parallel scan (--workers 4 --profile) ---"
snowfort audit scan --workers 4 --profile 2>&1 | tee /tmp/snowfort_smoke_par.log
PAR_EXIT=$?

# 4. Validate
echo ""
echo "--- Step 4: Validation ---"

if [ $SEQ_EXIT -ne 0 ]; then
    echo "FAIL: Sequential scan exited with code $SEQ_EXIT"
    exit 1
fi

if [ $PAR_EXIT -ne 0 ]; then
    echo "FAIL: Parallel scan exited with code $PAR_EXIT"
    exit 1
fi

# Check that profile output is present
if ! grep -q "Profile" /tmp/snowfort_smoke_seq.log && ! grep -q "profile" /tmp/snowfort_smoke_seq.log; then
    echo "WARN: No profile output detected in sequential scan (may be in stderr)"
fi

echo ""
echo "PASS: Both scans completed successfully."
echo "Review logs at /tmp/snowfort_smoke_seq.log and /tmp/snowfort_smoke_par.log"
echo ""
echo "To clean up test objects: snowfort audit demo-teardown (or run demo_teardown.sql manually)"
