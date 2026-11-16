"""
CartRecover-AI Enterprise Analytics & Monitoring Dashboard
Streamlit-based executive intelligence, campaign evaluation, consent compliance,
and anomaly surveillance console.
"""
import os
import json
from pathlib import Path
import pandas as pd
import streamlit as st
import altair as alt

from cart_recover.database.connection import get_db, load_dataset_to_sqlite
from cart_recover.database.repository import AnalyticsRepository
from cart_recover.analytics.metrics import METRIC_DEFINITIONS

# Page layout configuration
st.set_page_config(
    page_title="CartRecover-AI | Executive Console",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

@st.cache_resource
def init_database_if_needed(data_path: Path):
    db_file = data_path / "cart_recover.db"
    if not db_file.exists():
        load_dataset_to_sqlite(data_path, db_file)
    return db_file

def load_ground_truth(data_path: Path):
    gt_file = data_path / "ground_truth" / "ground_truth.json"
    if gt_file.exists():
        with open(gt_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def load_validation_summary(data_path: Path):
    val_file = data_path / "validation_summary.json"
    if val_file.exists():
        with open(val_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def render_chart(chart, use_container_width=True):
    """Safely renders Altair charts with graceful fallback if Vega/pyarrow has environment conflicts."""
    try:
        render_chart(chart, use_container_width=use_container_width)
    except Exception as e:
        st.warning(f"Visualization render notice: {e}")

# Sidebar Controls
st.sidebar.title("🛒 CartRecover-AI")
st.sidebar.caption("Forward Deployed Engineering Console")

scale_choice = st.sidebar.selectbox("Active Scale Dataset", ["starter", "full"], index=0)
active_data_dir = DATA_DIR / scale_choice

if not active_data_dir.exists():
    st.sidebar.error(f"Dataset '{scale_choice}' not found at {active_data_dir}")
    st.stop()

db_path = init_database_if_needed(active_data_dir)
st.sidebar.success(f"Connected to SQLite DB: `{scale_choice}`")

# Sidebar Action: Refresh DB
if st.sidebar.button("🔄 Reload Database from CSVs"):
    with st.spinner("Re-indexing SQLite tables..."):
        load_dataset_to_sqlite(active_data_dir, db_path)
    st.sidebar.success("Database reloaded successfully!")
    st.rerun()

st.sidebar.markdown("---")
show_formulas = st.sidebar.checkbox("Show KPI Mathematical Formulas", value=False)
st.sidebar.markdown(
    """
    **System Status:**  
    🟢 Deterministic Seed: `20261022`  
    🟢 SQLite Relational Store: `Active`  
    🟢 Audit Event History: `Preserved`  
    """
)

# Header
st.title("🛒 CartRecover-AI Intelligence Platform")
st.caption("Automated Cart Identification, Consent Compliance, Targeted Personalization & Revenue Attribution")

# Load repository
with get_db(db_path) as session:
    repo = AnalyticsRepository(session)
    kpis = repo.get_executive_kpis()
    val_summary = load_validation_summary(active_data_dir)
    gt_data = load_ground_truth(active_data_dir)

    # Main Tabs
    tabs = st.tabs([
        "📊 Executive Overview",
        "🛒 Cart Analytics",
        "📈 Campaign Analytics",
        "👥 Customer Analytics",
        "🔒 Consent Monitoring",
        "🚨 Anomaly Surveillance",
        "📑 Data Explorer & Export"
    ])

    # ---------------- TAB 1: EXECUTIVE OVERVIEW ----------------
    with tabs[0]:
        st.subheader("Executive Recovery Performance")
        
        # Row 1: KPI Cards
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Carts", f"{kpis['total_carts']:,}")
        c1.caption(f"{kpis['abandoned_carts']:,} abandoned ({kpis['abandonment_rate']}%)")
        
        c2.metric("Recovery Rate", f"{kpis['recovery_rate']}%")
        c2.caption(f"{kpis['recovered_carts']:,} carts converted")
        
        c3.metric("Sent Messages", f"{kpis['messages_sent']:,}")
        c3.caption(f"{kpis['messages_suppressed']:,} suppressed")
        
        c4.metric("Attributed Revenue", f"${kpis['attributed_revenue_dedup']:,.2f}")
        c4.caption("Deduplicated 7-day last click")
        
        c5.metric("Double-Count Bias", f"${kpis['double_counted_revenue']:,.2f}", delta=None)
        c5.caption("Naive collision inflation")

        if show_formulas:
            st.info("""
            **Documented Mathematical Formulas:**
            - **Abandonment Rate:** `Count(abandoned_at IS NOT NULL) / Total(carts) * 100`
            - **Recovery Rate:** `Count(status = 'recovered') / Count(abandoned_at IS NOT NULL) * 100`
            - **Attributed Revenue (Dedup):** `Sum(order_total for orders matching single primary attribution)`
            - **Double-Count Bias:** `Sum(naive attributions) - Sum(deduplicated attributions)`
            """)

        st.markdown("---")
        
        # Acceptance Badges
        st.write("##### Engine Acceptance & Rule Verification Status")
        if val_summary and "acceptance" in val_summary:
            acc = val_summary["acceptance"]
            b1, b2, b3, b4 = st.columns(4)
            b1.success("✅ Consent & Suppression Enforced" if acc.get("consent_and_suppression_enforced") else "❌ Consent Violations")
            b2.success("✅ Abandonment Time-Based" if acc.get("abandonment_time_based") else "❌ Abandonment Rule Error")
            b3.success("✅ Attribution Deterministic" if acc.get("attribution_deterministic") else "❌ Attribution Collision")
            b4.success("✅ Financial Reconciled" if acc.get("metrics_reconcile") else "❌ Ledger Discrepancy")
        else:
            st.warning("Run `python validate_data.py` to generate complete validation metrics.")

        # Funnel Visualization
        st.write("##### End-to-End Recovery Conversion Funnel")
        funnel_df = pd.DataFrame([
            {"Stage": "1. Carts Created", "Count": kpis["total_carts"]},
            {"Stage": "2. Carts Abandoned (60m+)", "Count": kpis["abandoned_carts"]},
            {"Stage": "3. Messages Scheduled", "Count": kpis["total_send_attempts"]},
            {"Stage": "4. Messages Sent (Unsuppressed)", "Count": kpis["messages_sent"]},
            {"Stage": "5. Recovered Orders", "Count": kpis["recovered_carts"]},
        ])
        chart = alt.Chart(funnel_df).mark_bar(cornerRadius=6, size=24).encode(
            x=alt.X("Count:Q", title="Volume"),
            y=alt.Y("Stage:N", sort=None, title="Funnel Stage"),
            color=alt.Color("Stage:N", legend=None, scale=alt.Scale(scheme="blues")),
            tooltip=["Stage", "Count"]
        ).properties(height=240)
        render_chart(chart, use_container_width=True)

    # ---------------- TAB 2: CART ANALYTICS ----------------
    with tabs[1]:
        st.subheader("Cart Abandonment & Recovery Dynamics")
        col_l, col_r = st.columns([1, 1])

        with col_l:
            st.write("##### Cart Status Breakdown")
            df_status = repo.get_cart_status_breakdown()
            st.dataframe(df_status, use_container_width=True, hide_index=True)

            status_pie = alt.Chart(df_status).mark_arc(innerRadius=50).encode(
                theta=alt.Theta("count:Q"),
                color=alt.Color("status:N", scale=alt.Scale(scheme="category10")),
                tooltip=["status", "count", "total_value"]
            ).properties(height=260)
            render_chart(status_pie, use_container_width=True)

        with col_r:
            st.write("##### Abandonment Decision Targeting Distribution")
            df_dec = pd.read_sql(
                "SELECT recovery_decision, reason, COUNT(*) as count FROM abandonment_decisions GROUP BY recovery_decision, reason ORDER BY count DESC",
                session.bind
            )
            st.dataframe(df_dec, use_container_width=True, hide_index=True)

            dec_bar = alt.Chart(df_dec).mark_bar().encode(
                x=alt.X("count:Q", title="Count"),
                y=alt.Y("recovery_decision:N", sort="-x", title="Decision"),
                color=alt.Color("recovery_decision:N", legend=None),
                tooltip=["recovery_decision", "reason", "count"]
            ).properties(height=260)
            render_chart(dec_bar, use_container_width=True)

    # ---------------- TAB 3: CAMPAIGN ANALYTICS ----------------
    with tabs[2]:
        st.subheader("Personalized Recovery Campaigns & Variant Performance")
        df_camp = repo.get_campaign_performance()
        
        st.write("##### Campaign Waves and Attribution Summary")
        st.dataframe(df_camp, use_container_width=True, hide_index=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.write("##### Revenue Generated by Variant")
            var_rev = df_camp.groupby("variant")["attributed_revenue"].sum().reset_index()
            c_bar = alt.Chart(var_rev).mark_bar(color="#2ca02c").encode(
                x=alt.X("variant:N", title="Variant"),
                y=alt.Y("attributed_revenue:Q", title="Attributed Revenue ($)"),
                tooltip=["variant", "attributed_revenue"]
            ).properties(height=260)
            render_chart(c_bar, use_container_width=True)

        with col_b:
            st.write("##### Conversion Efficiency (Orders per Sent Message)")
            var_eff = df_camp.groupby("variant").agg({"sent_count": "sum", "attributed_orders": "sum"}).reset_index()
            var_eff["conversion_rate"] = round(var_eff["attributed_orders"] / var_eff["sent_count"] * 100, 2)
            c_eff = alt.Chart(var_eff).mark_bar(color="#1f77b4").encode(
                x=alt.X("variant:N", title="Variant"),
                y=alt.Y("conversion_rate:Q", title="Conversion Rate (%)"),
                tooltip=["variant", "conversion_rate"]
            ).properties(height=260)
            render_chart(c_eff, use_container_width=True)

    # ---------------- TAB 4: CUSTOMER ANALYTICS ----------------
    with tabs[3]:
        st.subheader("Customer Segments, Regional Distribution & Multi-Device")
        df_cust = repo.get_customer_summary()
        st.dataframe(df_cust, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            st.write("##### Customers by Region")
            reg_df = df_cust.groupby("region")["customer_count"].sum().reset_index()
            reg_chart = alt.Chart(reg_df).mark_bar().encode(
                x=alt.X("region:N"),
                y=alt.Y("customer_count:Q"),
                color=alt.Color("region:N", legend=None)
            ).properties(height=240)
            render_chart(reg_chart, use_container_width=True)

        with col2:
            st.write("##### Signup Channel Breakdown")
            src_df = df_cust.groupby("signup_source")["customer_count"].sum().reset_index()
            src_chart = alt.Chart(src_df).mark_arc().encode(
                theta=alt.Theta("customer_count:Q"),
                color=alt.Color("signup_source:N")
            ).properties(height=240)
            render_chart(src_chart, use_container_width=True)

    # ---------------- TAB 5: CONSENT MONITORING ----------------
    with tabs[4]:
        st.subheader("Contact Consent Compliance & Suppression Surveillance")
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.write("##### Consent Status Timeline Distribution")
            df_consent = repo.get_consent_summary()
            st.dataframe(df_consent, use_container_width=True, hide_index=True)

        with col_c2:
            st.write("##### Recovery Send Suppression Reasons")
            df_sup = repo.get_suppression_reasons()
            st.dataframe(df_sup, use_container_width=True, hide_index=True)

            sup_chart = alt.Chart(df_sup).mark_bar(color="#d62728").encode(
                x=alt.X("count:Q", title="Count"),
                y=alt.Y("reason:N", sort="-x", title="Suppression Reason"),
                tooltip=["reason", "count", "percentage"]
            ).properties(height=220)
            render_chart(sup_chart, use_container_width=True)

    # ---------------- TAB 6: ANOMALY MONITORING ----------------
    with tabs[5]:
        st.subheader("Controlled Labelled Anomaly Surveillance")
        st.caption("Verification against independent ground_truth dataset (zero feature leakage)")

        if val_summary and "injected_anomaly_detection" in val_summary:
            anom_eval = val_summary["injected_anomaly_detection"]
            st.write("##### Injected Anomaly Detection Accuracy Scorecard")
            scorecard = []
            for k, res in anom_eval.items():
                if isinstance(res, dict) and "injected" in res:
                    scorecard.append({
                        "Scenario": k.replace("_", " ").title(),
                        "Injected Count": res["injected"],
                        "Detected Count": res["detected"],
                        "Exact Match": "PASS (100%)" if res["exact_match"] else "FAIL",
                    })
            st.dataframe(pd.DataFrame(scorecard), use_container_width=True, hide_index=True)

        st.write("##### Ground Truth Anomaly Audit Records")
        if gt_data:
            df_gt = pd.DataFrame(gt_data)
            st.dataframe(df_gt, use_container_width=True, hide_index=True)
            
            # Export Ground Truth
            csv_gt = df_gt.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download ground_truth.csv", csv_gt, "ground_truth.csv", "text/csv")
        else:
            st.info("No ground truth file found.")

    # ---------------- TAB 7: DATA EXPLORER & EXPORT ----------------
    with tabs[6]:
        st.subheader("Relational Database Explorer & Data Export")
        tables_list = [
            "customers", "consents", "products", "sessions", "carts",
            "cart_lines", "cart_events", "abandonment_decisions",
            "campaigns", "message_templates", "scheduled_messages",
            "send_attempts", "send_events", "orders", "attributions"
        ]
        sel_table = st.selectbox("Select Table to Inspect", tables_list)
        limit_rows = st.slider("Rows to Display", min_value=10, max_value=200, value=50, step=10)

        df_table = repo.get_table_sample(sel_table, limit=limit_rows)
        st.dataframe(df_table, use_container_width=True, hide_index=True)

        st.download_button(
            label=f"⬇️ Export {sel_table}.csv",
            data=df_table.to_csv(index=False).encode("utf-8"),
            file_name=f"{sel_table}_sample.csv",
            mime="text/csv"
        )
