"""Page 2: Explorer — Drill-down into violations with rationale and remediation."""

import streamlit as st
from snowflake.snowpark.context import get_active_session

st.header("🔍 Findings Explorer")

session = get_active_session()


@st.cache_data(ttl=300)
def get_latest_scan_id():
    """Get the most recent scan_id."""
    df = session.sql(
        "SELECT scan_id FROM SNOWFORT.AUDIT.SCAN_METADATA ORDER BY scanned_at DESC LIMIT 1"
    ).to_pandas()
    return df.iloc[0]["SCAN_ID"] if not df.empty else None


@st.cache_data(ttl=300)
def load_violations(scan_id: str):
    """Load all violations for a given scan."""
    df = session.sql(
        f"SELECT * FROM SNOWFORT.AUDIT.SCAN_VIOLATIONS WHERE scan_id = '{scan_id}' "
        "ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 "
        "WHEN 'MEDIUM' THEN 3 ELSE 4 END, rule_id"
    ).to_pandas()
    return df


scan_id = get_latest_scan_id()
if not scan_id:
    st.warning("No scan results found. Run `snowfort audit scan --persist` first.")
    st.stop()

violations_df = load_violations(scan_id)

if violations_df.empty:
    st.success("No violations found in the latest scan!")
    st.stop()

# Sidebar filters
st.sidebar.subheader("Filters")
pillars = sorted(violations_df["PILLAR"].dropna().unique().tolist())
selected_pillars = st.sidebar.multiselect("Pillar", pillars, default=pillars)

severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
selected_severities = st.sidebar.multiselect("Severity", severities, default=severities)

search = st.text_input("🔍 Search by Rule ID or Resource", "")

# Apply filters
filtered = violations_df[
    violations_df["PILLAR"].isin(selected_pillars)
    & violations_df["SEVERITY"].isin(selected_severities)
]
if search:
    mask = (
        filtered["RULE_ID"].str.contains(search, case=False, na=False)
        | filtered["RESOURCE_NAME"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

st.caption(f"Showing {len(filtered)} of {len(violations_df)} findings")
st.divider()

# Display violations with drill-down
for _, row in filtered.iterrows():
    severity_color = {
        "CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "⚪"
    }.get(row["SEVERITY"], "⚪")
    quick_win_badge = " ⚡" if row.get("QUICK_WIN") else ""
    header = f"{severity_color} **{row['RULE_ID']}** — {row['RESOURCE_NAME']}{quick_win_badge}"

    with st.expander(header, expanded=False):
        st.markdown(f"**Message:** {row['MESSAGE']}")
        st.markdown(f"**Severity:** {row['SEVERITY']} | **Pillar:** {row['PILLAR']} | "
                    f"**Category:** {row.get('CATEGORY', 'N/A')}")

        if row.get("RATIONALE"):
            st.markdown("---")
            st.markdown(f"**Why this matters:**\n\n{row['RATIONALE']}")

        if row.get("REMEDIATION_KEY"):
            st.markdown("---")
            st.markdown(f"**Remediation key:** `{row['REMEDIATION_KEY']}`")

        if row.get("QUICK_WIN"):
            st.success("⚡ Quick Win — this finding has a known remediation pattern.")
