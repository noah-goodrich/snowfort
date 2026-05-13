"""Snowfort WAF Audit Dashboard — Main entry point for Streamlit-in-Snowflake."""

import streamlit as st

st.set_page_config(
    page_title="Snowfort WAF Audit",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .main { background-color: #0e1117; color: #fafafa; }
    h1, h2, h3 { color: #29B5E8 !important; }
    .stMetric label { color: #29B5E8 !important; }
</style>
""",
    unsafe_allow_html=True,
)

st.sidebar.title("Snowfort Audit")
st.sidebar.caption("Well-Architected Framework Scanner")
st.sidebar.divider()

st.title("🛡️ Snowfort WAF Audit Dashboard")
st.caption("Navigate using the sidebar to explore findings, drill into remediation, or view trends.")
st.info("Select a page from the sidebar: **Dashboard**, **Explorer**, or **Trends**.")
