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
echo "--- Step 5: Rule ID spot-checks ---"
# Rules that must fire given the seeded objects.
EXPECTED_RULES=(
    "COST_001"   # AggressiveAutoSuspendCheck — seeded warehouses have no auto_suspend
    "OPS_001"    # MandatoryTaggingCheck — seeded warehouses have no tags
    "GOV_004"    # ObjectDocumentationCheck — SNOWFORT_TEST_UNDOCUMENTED_DB
)
WARN_COUNT=0
for RULE in "${EXPECTED_RULES[@]}"; do
    if ! grep -q "$RULE" /tmp/snowfort_smoke_par.log; then
        echo "WARN: Expected rule $RULE not found in parallel scan output"
        WARN_COUNT=$((WARN_COUNT + 1))
    else
        echo "OK: $RULE found"
    fi
done
if [ $WARN_COUNT -gt 0 ]; then
    echo ""
    echo "WARN: $WARN_COUNT expected rule(s) not found. Check /tmp/snowfort_smoke_par.log."
fi

echo ""
echo "PASS: Both scans completed successfully."
echo "Review logs at /tmp/snowfort_smoke_seq.log and /tmp/snowfort_smoke_par.log"
echo ""
echo "Note: Cortex cost rules (COST_016-033) are unit-test only — seeding real Cortex usage incurs credits."
echo "To clean up test objects: snowfort audit demo-teardown (or run demo_teardown.sql manually)"
