"""Executive business review dashboard. Run with: streamlit run dashboard/app.py"""

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ads_warehouse.duckdb")

st.set_page_config(page_title="Ads Review OS", layout="wide", page_icon="📊")


@st.cache_resource
def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)


con = get_connection()

# ---------- Sidebar: self-service filters ----------
st.sidebar.title("Ads Review OS")
st.sidebar.caption("Self-service filters — no SQL required")

industries = con.execute("SELECT DISTINCT industry FROM advertisers ORDER BY 1").df()["industry"].tolist()
regions = con.execute("SELECT DISTINCT region FROM advertisers ORDER BY 1").df()["region"].tolist()
tiers = con.execute("SELECT DISTINCT tier FROM advertisers ORDER BY 1").df()["tier"].tolist()

sel_industries = st.sidebar.multiselect("Industry", industries, default=industries)
sel_regions = st.sidebar.multiselect("Region", regions, default=regions)
sel_tiers = st.sidebar.multiselect("Tier", tiers, default=tiers)

date_bounds = con.execute("SELECT MIN(date), MAX(date) FROM daily_performance").fetchone()
date_range = st.sidebar.date_input("Date Range", value=(date_bounds[0], date_bounds[1]),
                                     min_value=date_bounds[0], max_value=date_bounds[1])

if len(date_range) != 2:
    st.stop()
start_d, end_d = date_range

industry_filter = "'" + "','".join(sel_industries) + "'" if sel_industries else "''"
region_filter = "'" + "','".join(sel_regions) + "'" if sel_regions else "''"
tier_filter = "'" + "','".join(sel_tiers) + "'" if sel_tiers else "''"

base_filter_sql = f"""
    a.industry IN ({industry_filter})
    AND a.region IN ({region_filter})
    AND a.tier IN ({tier_filter})
    AND CAST(p.date AS DATE) BETWEEN '{start_d}' AND '{end_d}'
"""

# ---------- Header ----------
st.title("📊 Ads Review OS")
st.caption("Internal advertising business review platform — Strategy & Planning")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Executive Scorecard", "MBR (Monthly)", "QBR (Quarterly)", "Advertiser Health", "Data Trust / KPI Catalog"]
)

# ---------- TAB 1: Executive Scorecard ----------
with tab1:
    st.subheader("Company Health — at a glance")

    scorecard = con.execute(f"""
        SELECT
            SUM(p.spend) AS revenue,
            SUM(p.clicks)::DOUBLE / NULLIF(SUM(p.impressions), 0) AS ctr,
            SUM(p.conversions)::DOUBLE / NULLIF(SUM(p.clicks), 0) AS cvr,
            SUM(p.spend)::DOUBLE / NULLIF(SUM(p.clicks), 0) AS cpc,
            COUNT(DISTINCT p.advertiser_id) AS active_advertisers
        FROM daily_performance p
        JOIN advertisers a ON p.advertiser_id = a.advertiser_id
        WHERE {base_filter_sql}
    """).df()

    if scorecard.empty or pd.isna(scorecard.loc[0, "revenue"]):
        st.warning("No data for the selected filters.")
    else:
        row = scorecard.iloc[0]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Revenue", f"${row['revenue']:,.0f}")
        c2.metric("CTR", f"{row['ctr']*100:.2f}%")
        c3.metric("CVR", f"{row['cvr']*100:.2f}%")
        c4.metric("Avg CPC", f"${row['cpc']:.2f}")
        c5.metric("Active Advertisers", f"{int(row['active_advertisers'])}")

        st.divider()
        st.subheader("Revenue Trend")
        trend = con.execute(f"""
            SELECT p.month, SUM(p.spend) AS revenue
            FROM daily_performance p
            JOIN advertisers a ON p.advertiser_id = a.advertiser_id
            WHERE {base_filter_sql}
            GROUP BY 1 ORDER BY 1
        """).df()
        fig = px.line(trend, x="month", y="revenue", markers=True, title="Monthly Revenue")
        fig.update_layout(yaxis_title="Revenue ($)", xaxis_title="Month")
        st.plotly_chart(fig, use_container_width=True)

# ---------- TAB 2: MBR ----------
with tab2:
    st.subheader("Monthly Business Review")

    monthly = con.execute(f"""
        SELECT
            p.month,
            SUM(p.spend) AS revenue,
            SUM(p.clicks)::DOUBLE / NULLIF(SUM(p.impressions),0) AS ctr,
            SUM(p.conversions)::DOUBLE / NULLIF(SUM(p.clicks),0) AS cvr
        FROM daily_performance p
        JOIN advertisers a ON p.advertiser_id = a.advertiser_id
        WHERE {base_filter_sql}
        GROUP BY 1 ORDER BY 1
    """).df()

    if len(monthly) >= 2:
        cur = monthly.iloc[-1]
        prev = monthly.iloc[-2]
        mom_rev = (cur["revenue"] - prev["revenue"]) / prev["revenue"] * 100 if prev["revenue"] else 0

        st.markdown(f"**Current Month: {cur['month']}**  |  **Prior Month: {prev['month']}**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Revenue (MoM)", f"${cur['revenue']:,.0f}", f"{mom_rev:+.1f}%")
        c2.metric("CTR (MoM)", f"{cur['ctr']*100:.2f}%", f"{(cur['ctr']-prev['ctr'])*100:+.2f} pp")
        c3.metric("CVR (MoM)", f"{cur['cvr']*100:.2f}%", f"{(cur['cvr']-prev['cvr'])*100:+.2f} pp")
    else:
        st.info("Not enough months in the selected range to compute MoM comparison.")

    st.divider()
    st.dataframe(monthly.style.format({"revenue": "${:,.0f}", "ctr": "{:.2%}", "cvr": "{:.2%}"}),
                 use_container_width=True)

# ---------- TAB 3: QBR ----------
with tab3:
    st.subheader("Quarterly Business Review")

    quarterly = con.execute(f"""
        SELECT
            p.quarter,
            SUM(p.spend) AS revenue,
            SUM(p.clicks)::DOUBLE / NULLIF(SUM(p.impressions),0) AS ctr,
            SUM(p.conversions)::DOUBLE / NULLIF(SUM(p.clicks),0) AS cvr
        FROM daily_performance p
        JOIN advertisers a ON p.advertiser_id = a.advertiser_id
        WHERE {base_filter_sql}
        GROUP BY 1 ORDER BY 1
    """).df()

    if len(quarterly) >= 2:
        cur = quarterly.iloc[-1]
        prev = quarterly.iloc[-2]
        qoq_rev = (cur["revenue"] - prev["revenue"]) / prev["revenue"] * 100 if prev["revenue"] else 0

        st.markdown(f"**Current Quarter: {cur['quarter']}**  |  **Prior Quarter: {prev['quarter']}**")
        c1, c2 = st.columns(2)
        c1.metric("Revenue (QoQ)", f"${cur['revenue']:,.0f}", f"{qoq_rev:+.1f}%")
        c2.metric("CTR (QoQ)", f"{cur['ctr']*100:.2f}%", f"{(cur['ctr']-prev['ctr'])*100:+.2f} pp")

        if len(quarterly) >= 5:
            yoy_prev = quarterly.iloc[-5]
            yoy_rev = (cur["revenue"] - yoy_prev["revenue"]) / yoy_prev["revenue"] * 100 if yoy_prev["revenue"] else 0
            st.metric("Revenue (YoY)", f"${cur['revenue']:,.0f}", f"{yoy_rev:+.1f}%")
    else:
        st.info("Not enough quarters in the selected range to compute QoQ comparison.")

    st.divider()
    fig = px.bar(quarterly, x="quarter", y="revenue", title="Revenue by Quarter")
    st.plotly_chart(fig, use_container_width=True)

# ---------- TAB 4: Advertiser Health ----------
with tab4:
    st.subheader("Advertiser Health Segmentation")
    st.caption("Growing / Stable / At Risk / Churned — based on revenue trend over the trailing 60 days vs prior 60 days")

    health = con.execute(f"""
        WITH recent AS (
            SELECT p.advertiser_id, SUM(p.spend) AS recent_spend
            FROM daily_performance p
            JOIN advertisers a ON p.advertiser_id = a.advertiser_id
            WHERE {base_filter_sql} AND CAST(p.date AS DATE) >= (DATE '{end_d}' - INTERVAL 60 DAY)
            GROUP BY 1
        ),
        prior AS (
            SELECT p.advertiser_id, SUM(p.spend) AS prior_spend
            FROM daily_performance p
            JOIN advertisers a ON p.advertiser_id = a.advertiser_id
            WHERE {base_filter_sql}
              AND CAST(p.date AS DATE) >= (DATE '{end_d}' - INTERVAL 120 DAY)
              AND CAST(p.date AS DATE) < (DATE '{end_d}' - INTERVAL 60 DAY)
            GROUP BY 1
        )
        SELECT
            a.advertiser_id, a.company, a.industry, a.tier,
            COALESCE(r.recent_spend, 0) AS recent_spend,
            COALESCE(p.prior_spend, 0) AS prior_spend
        FROM advertisers a
        LEFT JOIN recent r ON a.advertiser_id = r.advertiser_id
        LEFT JOIN prior p ON a.advertiser_id = p.advertiser_id
        WHERE a.industry IN ({industry_filter}) AND a.region IN ({region_filter}) AND a.tier IN ({tier_filter})
    """).df()

    def classify(row):
        if row["recent_spend"] == 0 and row["prior_spend"] > 0:
            return "Churned"
        if row["prior_spend"] == 0:
            return "Stable" if row["recent_spend"] == 0 else "Growing"
        change = (row["recent_spend"] - row["prior_spend"]) / row["prior_spend"]
        if change > 0.15:
            return "Growing"
        elif change < -0.15:
            return "At Risk"
        return "Stable"

    health["status"] = health.apply(classify, axis=1)

    counts = health["status"].value_counts().reindex(["Growing", "Stable", "At Risk", "Churned"], fill_value=0)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 Growing", int(counts["Growing"]))
    c2.metric("🔵 Stable", int(counts["Stable"]))
    c3.metric("🟡 At Risk", int(counts["At Risk"]))
    c4.metric("🔴 Churned", int(counts["Churned"]))

    counts_df = counts.reset_index()
    counts_df.columns = ["status_label", "count"]
    fig = px.pie(counts_df, names="status_label", values="count", title="Advertiser Health Mix",
                 color="status_label",
                 color_discrete_map={"Growing": "#2ecc71", "Stable": "#3498db", "At Risk": "#f39c12", "Churned": "#e74c3c"})
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.dataframe(
        health[["company", "industry", "tier", "status", "recent_spend", "prior_spend"]]
        .sort_values("recent_spend", ascending=False)
        .style.format({"recent_spend": "${:,.0f}", "prior_spend": "${:,.0f}"}),
        use_container_width=True
    )

# ---------- TAB 5: Data Trust / KPI Catalog ----------
with tab5:
    st.subheader("Data Trust & KPI Governance Catalog")
    st.caption("Every metric on this dashboard has one definition, one owner, and one source of truth.")

    catalog = con.execute("SELECT * FROM kpi_catalog").df()
    quality_score = catalog["current_data_quality_score_pct"].iloc[0]

    st.metric("Live Data Quality Score", f"{quality_score}%")

    st.dataframe(
        catalog[["kpi", "formula", "definition", "owner", "source_table", "refresh_cadence", "business_purpose"]],
        use_container_width=True
    )

    st.divider()
    st.subheader("ETL Validation Log")
    st.caption("Every record that failed a data quality rule was quarantined, not silently dropped.")
    val_log = con.execute("SELECT * FROM etl_validation_log").df()
    st.dataframe(val_log, use_container_width=True)
