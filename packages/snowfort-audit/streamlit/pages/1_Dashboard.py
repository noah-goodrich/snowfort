"""Page 1: Dashboard — Scorecard KPIs, pillar charts, severity distribution."""

import plotly.graph_objects as go
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.header("📊 Dashboard")

session = get_active_session()


@st.cache_data(ttl=300)
def load_latest_scan():
    """Load the most recent scan metadata."""
    df = session.sql(
        "SELECT * FROM SNOWFORT.AUDIT.SCAN_METADATA ORDER BY scanned_at DESC LIMIT 1"
    ).to_pandas()
    return df


@st.cache_data(ttl=300)
def load_previous_scan():
    """Load the second most recent scan for delta comparison."""
    df = session.sql(
        "SELECT * FROM SNOWFORT.AUDIT.SCAN_METADATA ORDER BY scanned_at DESC LIMIT 1 OFFSET 1"
    ).to_pandas()
    return df


@st.cache_data(ttl=300)
def load_score_history():
    """Load last 10 scans for sparkline."""
    df = session.sql(
        "SELECT scanned_at, compliance_score, grade "
        "FROM SNOWFORT.AUDIT.SCAN_METADATA ORDER BY scanned_at DESC LIMIT 10"
    ).to_pandas()
    return df


latest = load_latest_scan()

if latest.empty:
    st.warning("No scan results found. Run `snowfort audit scan --persist` to populate the dashboard.")
    st.stop()

row = latest.iloc[0]
prev = load_previous_scan()

# Compute deltas
score_delta = None
violations_delta = None
if not prev.empty:
    prev_row = prev.iloc[0]
    score_delta = round(row["COMPLIANCE_SCORE"] - prev_row["COMPLIANCE_SCORE"], 1)
    violations_delta = int(row["TOTAL_VIOLATIONS"] - prev_row["TOTAL_VIOLATIONS"])

# KPI Row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Compliance Score", f"{row['COMPLIANCE_SCORE']:.0f}/100", delta=score_delta)
col2.metric("Total Violations", int(row["TOTAL_VIOLATIONS"]), delta=violations_delta, delta_color="inverse")
col3.metric("Critical", int(row["CRITICAL_COUNT"]), delta_color="inverse")
col4.metric("High", int(row["HIGH_COUNT"]), delta_color="inverse")

st.caption(f"Last scanned: {row['SCANNED_AT']} | Grade: **{row['GRADE']}** | "
           f"Billing: {row['BILLING_MODEL'] or 'N/A'}")
st.divider()

# Charts
import json

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Score by Pillar")
    pillar_scores = json.loads(row["PILLAR_SCORES"]) if row["PILLAR_SCORES"] else {}
    pillar_grades = json.loads(row["PILLAR_GRADES"]) if row["PILLAR_GRADES"] else {}
    if pillar_scores:
        pillars = list(pillar_scores.keys())
        scores = [pillar_scores[p] for p in pillars]
        grades = [pillar_grades.get(p, "-") for p in pillars]
        fig = go.Figure(data=[go.Bar(
            x=pillars, y=scores,
            text=[f"{s:.0f} ({g})" for s, g in zip(scores, grades)],
            textposition="outside",
            marker_color="#29B5E8",
        )])
        fig.update_layout(yaxis_range=[0, 105], height=320, margin=dict(t=20, b=40))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No pillar breakdown available.")

with chart_col2:
    st.subheader("Severity Distribution")
    sev_counts = [int(row["CRITICAL_COUNT"]), int(row["HIGH_COUNT"]),
                  int(row["MEDIUM_COUNT"]), int(row["LOW_COUNT"])]
    if sum(sev_counts) > 0:
        fig_sev = go.Figure(data=[go.Pie(
            labels=["Critical", "High", "Medium", "Low"],
            values=sev_counts,
            hole=0.4,
            marker_colors=["#dc3545", "#fd7e14", "#ffc107", "#6c757d"],
        )])
        fig_sev.update_layout(height=320, margin=dict(t=20, b=20))
        st.plotly_chart(fig_sev, use_container_width=True)
    else:
        st.success("No violations!")

# Score trend sparkline
st.divider()
st.subheader("Recent Score Trend")
history = load_score_history()
if len(history) > 1:
    st.line_chart(history.set_index("SCANNED_AT")["COMPLIANCE_SCORE"], height=200)
else:
    st.info("Run multiple scans with `--persist` to see trends.")
