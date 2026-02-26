import pandas as pd
import streamlit as st

from snowfort_audit.domain.protocols import AuditRepositoryProtocol
from snowfort_audit.domain.rule_definitions import PILLAR_DISPLAY_ORDER, pillar_from_rule_id

# --- Page Config & Styling ---
st.set_page_config(
    page_title="Snowfort | WAF Audit",
    page_icon="❄️",
    layout="wide",
)

# Custom CSS
st.markdown(
    """
<style>
    :root {
        --starbase-cyan: #29B5E8;
    }
    .main {
        background-color: #000000;
        color: #FFFFFF;
    }
    h1, h2, h3 {
        color: var(--starbase-cyan) !important;
    }
    .stMetric label {
        color: #29B5E8 !important;
    }
    div[data-testid="stMetricValue"] {
        color: #FFFFFF !important;
    }
    .stDataFrame {
        border: 1px solid #11567F;
    }
</style>
""",
    unsafe_allow_html=True,
)


# --- Dependency Injection Setup ---
def get_snowpark_session():
    """Lazy import and fetch of Snowpark session to avoid top-level dependency."""
    try:
        from snowflake.snowpark.context import get_active_session  # noqa: PLC0415

        return get_active_session()
    except ImportError:
        return None
    except Exception:
        # Fallback for local development or if not in Snowflake target environment
        return None


def get_container():
    """Initialize and configure the DI container (wired via run.get_wired_container)."""
    from snowfort_audit.run import get_wired_container

    container = get_wired_container()
    container.register_factory("SnowparkSession", get_snowpark_session)
    return container


# --- Data Loading ---
def load_audit_result(container):
    repo: AuditRepositoryProtocol = container.get("AuditRepository")
    return repo.get_latest_audit_result()


def violations_to_display_data(violations):
    """Build list of dicts for violations table display. Testable without Streamlit."""
    return [
        {
            "RULE_ID": v.rule_id,
            "RESOURCE_NAME": v.resource_name,
            "MESSAGE": v.message,
            "SEVERITY": v.severity.value,
            "PILLAR": v.pillar or pillar_from_rule_id(v.rule_id),
        }
        for v in violations
    ]


# --- UI Header ---
with st.sidebar:
    try:
        st.image("assets/hero-dark.png", width=200)
    except Exception:
        st.title("Snowfort")

    st.divider()
    st.subheader("Navigation")
    st.info("Connected to Snowflake Fleet")

st.title("🛡️ Snowfort WAF Scorecard")
st.caption("Well-Architected Toolkit for Snowflake")

# Initialize and Load
app_container = get_container()
audit_result = load_audit_result(app_container)
scorecard = audit_result.scorecard
audit_metadata = getattr(audit_result, "metadata", None) or {}

# --- Metrics Row ---
col1, col2, col3, col4 = st.columns(4)

col1.metric("Compliance Score", f"{scorecard.compliance_score}/100", delta=None)
col2.metric("Total Deficiencies", scorecard.total_violations, delta=None)
col3.metric("Critical Risks", scorecard.critical_count, delta=None, delta_color="inverse")
col4.metric("High Priority", scorecard.high_count, delta=None)

if audit_metadata.get("billing_model"):
    st.caption(f"Billing model: {audit_metadata['billing_model'].replace('_', ' ').title()}")

st.divider()

# --- Per-pillar and severity charts (Plotly) ---
try:
    import plotly.express as px  # noqa: PLC0415
    import plotly.graph_objects as go  # noqa: PLC0415

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Score by pillar")
        if scorecard.pillar_scores:
            pillars = list(scorecard.pillar_scores.keys())
            scores = [scorecard.pillar_scores[p] for p in pillars]
            grades = [scorecard.pillar_grades.get(p, "-") for p in pillars]
            fig_pillar = go.Figure(
                data=[
                    go.Bar(
                        x=pillars,
                        y=scores,
                        text=[f"{s:.0f} ({g})" for s, g in zip(scores, grades, strict=True)],
                        textposition="outside",
                        marker_color=[min(1, s / 100) for s in scores],
                    )
                ]
            )
            fig_pillar.update_layout(
                yaxis_title="Score",
                yaxis_range=[0, 105],
                showlegend=False,
                margin=dict(t=20, b=40),
                height=320,
            )
            st.plotly_chart(fig_pillar, use_container_width=True)
        else:
            st.info("No pillar breakdown (no violations).")

    with chart_col2:
        st.subheader("Severity distribution")
        if scorecard.total_violations > 0:
            sev_counts = [
                scorecard.critical_count,
                scorecard.high_count,
                scorecard.medium_count,
                scorecard.low_count,
            ]
            sev_labels = ["Critical", "High", "Medium", "Low"]
            fig_sev = go.Figure(
                data=[
                    go.Pie(
                        labels=sev_labels,
                        values=sev_counts,
                        hole=0.4,
                        marker_colors=["#dc3545", "#fd7e14", "#ffc107", "#6c757d"],
                    )
                ]
            )
            fig_sev.update_layout(margin=dict(t=20, b=20), height=320, showlegend=True)
            st.plotly_chart(fig_sev, use_container_width=True)
        else:
            st.info("No violations.")

    # Violations by pillar (bar)
    if audit_result.violations:
        st.subheader("Violations by pillar")
        pillar_counts: dict[str, int] = {}
        for v in audit_result.violations:
            p = v.pillar or pillar_from_rule_id(v.rule_id)
            pillar_counts[p] = pillar_counts.get(p, 0) + 1
        p_names = [p for p in PILLAR_DISPLAY_ORDER if p in pillar_counts]
        p_names += [k for k in pillar_counts if k not in PILLAR_DISPLAY_ORDER]
        p_vals = [pillar_counts[p] for p in p_names]
        fig_pcount = px.bar(x=p_names, y=p_vals, labels={"x": "Pillar", "y": "Count"})
        fig_pcount.update_layout(margin=dict(t=20, b=40), height=280, showlegend=False)
        st.plotly_chart(fig_pcount, use_container_width=True)

except ImportError:
    st.caption("Install plotly for charts: pip install plotly")

st.divider()

# --- Search & Filtering ---
st.subheader("Hull Deficiencies (Violations)")
search_query = st.text_input("🔍 Search by Resource or Rule ID", "")

if audit_result.violations:
    data = violations_to_display_data(audit_result.violations)
    violations_df: pd.DataFrame = pd.DataFrame(data)

    resource_match = violations_df["RESOURCE_NAME"].str.contains(search_query, case=False)
    rule_match = violations_df["RULE_ID"].str.contains(search_query, case=False)

    filtered_df = violations_df[resource_match | rule_match]

    severity_config = st.column_config.SelectboxColumn(
        "Severity",
        options=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
    )

    st.dataframe(
        filtered_df,
        use_container_width=True,
        column_config={
            "SEVERITY": severity_config,
            "RULE_ID": "Rule ID",
            "RESOURCE_NAME": "Resource",
            "MESSAGE": "Violation Details",
        },
    )
else:
    st.success("Perfect Score: No hull deficiencies detected in the fleet!")

# Footer
st.divider()
st.caption("Generated by Snowfort Audit")
