"""Page 3: Trends — Score history, regression detection, scan comparison."""

import streamlit as st
from snowflake.snowpark.context import get_active_session

st.header("📈 Trends & History")

session = get_active_session()


@st.cache_data(ttl=300)
def load_scan_history():
    """Load all scan metadata for trending."""
    df = session.sql(
        "SELECT scan_id, scanned_at, compliance_score, grade, total_violations, "
        "critical_count, high_count, medium_count, low_count, pillar_scores "
        "FROM SNOWFORT.AUDIT.SCAN_METADATA ORDER BY scanned_at DESC LIMIT 90"
    ).to_pandas()
    return df


@st.cache_data(ttl=300)
def load_violations_for_scan(scan_id: str):
    """Load violations for a specific scan."""
    df = session.sql(
        f"SELECT rule_id, resource_name, severity, message "
        f"FROM SNOWFORT.AUDIT.SCAN_VIOLATIONS WHERE scan_id = '{scan_id}'"
    ).to_pandas()
    return df


history = load_scan_history()

if history.empty:
    st.warning("No scan history found. Run `snowfort audit scan --persist` multiple times to build history.")
    st.stop()

if len(history) < 2:
    st.info("Run at least 2 scans with `--persist` to see trends and comparisons.")

# Score over time
st.subheader("Compliance Score Over Time")
chart_data = history[["SCANNED_AT", "COMPLIANCE_SCORE"]].sort_values("SCANNED_AT")
st.line_chart(chart_data.set_index("SCANNED_AT")["COMPLIANCE_SCORE"], height=300)

# Regression detection
st.subheader("Regression Detection")
history_sorted = history.sort_values("SCANNED_AT").reset_index(drop=True)
regressions = []
for i in range(1, len(history_sorted)):
    prev_score = history_sorted.iloc[i - 1]["COMPLIANCE_SCORE"]
    curr_score = history_sorted.iloc[i]["COMPLIANCE_SCORE"]
    drop = prev_score - curr_score
    if drop > 5:
        regressions.append({
            "Date": history_sorted.iloc[i]["SCANNED_AT"],
            "Score": curr_score,
            "Drop": f"-{drop:.1f}",
            "Grade": history_sorted.iloc[i]["GRADE"],
        })

if regressions:
    st.warning(f"Found {len(regressions)} regression(s) (score drop > 5 points)")
    st.dataframe(regressions, use_container_width=True)
else:
    st.success("No significant regressions detected.")

st.divider()

# Scan comparison
st.subheader("Scan Comparison")
if len(history) >= 2:
    scan_options = {
        f"{row['SCANNED_AT']} (Score: {row['COMPLIANCE_SCORE']:.0f}, Grade: {row['GRADE']})": row["SCAN_ID"]
        for _, row in history.iterrows()
    }
    col1, col2 = st.columns(2)
    with col1:
        scan_a_label = st.selectbox("Baseline scan", list(scan_options.keys()), index=1)
    with col2:
        scan_b_label = st.selectbox("Current scan", list(scan_options.keys()), index=0)

    if scan_a_label and scan_b_label and scan_a_label != scan_b_label:
        scan_a_id = scan_options[scan_a_label]
        scan_b_id = scan_options[scan_b_label]

        violations_a = load_violations_for_scan(scan_a_id)
        violations_b = load_violations_for_scan(scan_b_id)

        # Compute diff using rule_id + resource_name as key
        keys_a = set(zip(violations_a["RULE_ID"], violations_a["RESOURCE_NAME"]))
        keys_b = set(zip(violations_b["RULE_ID"], violations_b["RESOURCE_NAME"]))

        new_findings = keys_b - keys_a
        resolved_findings = keys_a - keys_b

        res_col1, res_col2 = st.columns(2)
        with res_col1:
            st.metric("New Findings", len(new_findings), delta=len(new_findings), delta_color="inverse")
            if new_findings:
                new_df = violations_b[
                    violations_b.apply(lambda r: (r["RULE_ID"], r["RESOURCE_NAME"]) in new_findings, axis=1)
                ][["RULE_ID", "RESOURCE_NAME", "SEVERITY"]]
                st.dataframe(new_df, use_container_width=True, hide_index=True)

        with res_col2:
            st.metric("Resolved", len(resolved_findings), delta=f"-{len(resolved_findings)}", delta_color="normal")
            if resolved_findings:
                resolved_df = violations_a[
                    violations_a.apply(lambda r: (r["RULE_ID"], r["RESOURCE_NAME"]) in resolved_findings, axis=1)
                ][["RULE_ID", "RESOURCE_NAME", "SEVERITY"]]
                st.dataframe(resolved_df, use_container_width=True, hide_index=True)
else:
    st.info("Need at least 2 scans for comparison.")

# History table
st.divider()
st.subheader("Scan History")
display_cols = ["SCANNED_AT", "COMPLIANCE_SCORE", "GRADE", "TOTAL_VIOLATIONS",
                "CRITICAL_COUNT", "HIGH_COUNT", "MEDIUM_COUNT", "LOW_COUNT"]
st.dataframe(history[display_cols], use_container_width=True, hide_index=True)
