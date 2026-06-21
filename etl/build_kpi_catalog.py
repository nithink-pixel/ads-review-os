"""KPI catalog — one definition, owner, and formula per metric. Avoids the "two teams calculate CTR differently" problem."""

import duckdb
import pandas as pd
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ads_warehouse.duckdb")

KPI_CATALOG = [
    {
        "kpi": "Revenue",
        "formula": "SUM(spend)",
        "definition": "Total advertiser spend recognized as platform revenue for the selected period.",
        "owner": "Finance",
        "source_table": "daily_performance",
        "refresh_cadence": "Daily",
        "business_purpose": "Primary top-line metric for MBR/QBR; tracks ad business health.",
    },
    {
        "kpi": "CTR (Click-Through Rate)",
        "formula": "SUM(clicks) / SUM(impressions)",
        "definition": "Share of served impressions that resulted in a click.",
        "owner": "Ads Ops",
        "source_table": "daily_performance",
        "refresh_cadence": "Daily",
        "business_purpose": "Leading indicator of creative and targeting relevance.",
    },
    {
        "kpi": "CVR (Conversion Rate)",
        "formula": "SUM(conversions) / SUM(clicks)",
        "definition": "Share of clicks that resulted in a conversion event.",
        "owner": "Ads Ops",
        "source_table": "daily_performance",
        "refresh_cadence": "Daily",
        "business_purpose": "Measures down-funnel ad effectiveness, not just engagement.",
    },
    {
        "kpi": "CPC (Cost Per Click)",
        "formula": "SUM(spend) / SUM(clicks)",
        "definition": "Average advertiser cost paid per click.",
        "owner": "Strategy & Planning",
        "source_table": "daily_performance",
        "refresh_cadence": "Daily",
        "business_purpose": "Pricing efficiency signal used in advertiser-facing benchmarking.",
    },
    {
        "kpi": "Advertiser Retention Rate",
        "formula": "Active advertisers this period / Active advertisers prior period",
        "definition": "Share of advertisers active in the prior period who remained active.",
        "owner": "Strategy & Planning",
        "source_table": "daily_performance, advertisers",
        "refresh_cadence": "Monthly",
        "business_purpose": "Core health metric for the advertiser base, used in QBR investment decisions.",
    },
    {
        "kpi": "Budget Utilization",
        "formula": "SUM(spend) / SUM(budget)",
        "definition": "Share of allocated campaign budget actually spent.",
        "owner": "Ads Ops",
        "source_table": "daily_performance, campaigns",
        "refresh_cadence": "Weekly",
        "business_purpose": "Identifies underspending campaigns, a direct revenue-recovery lever.",
    },
]


def compute_data_quality_score(con):
    """1 - (quarantined / total attempted)"""
    total_clean = con.execute("SELECT COUNT(*) FROM daily_performance").fetchone()[0]
    total_quarantined = con.execute("SELECT COUNT(*) FROM quarantined_records").fetchone()[0]
    total_attempted = total_clean + total_quarantined
    score = 1 - (total_quarantined / total_attempted) if total_attempted > 0 else 1.0
    return round(score * 100, 2)


def build_catalog():
    con = duckdb.connect(DB_PATH)
    quality_score = compute_data_quality_score(con)

    catalog_df = pd.DataFrame(KPI_CATALOG)
    catalog_df["current_data_quality_score_pct"] = quality_score

    con.execute("DROP TABLE IF EXISTS kpi_catalog")
    con.register("cat_df", catalog_df)
    con.execute("CREATE TABLE kpi_catalog AS SELECT * FROM cat_df")
    con.close()

    print("KPI Catalog built:")
    print(catalog_df[["kpi", "owner", "refresh_cadence", "current_data_quality_score_pct"]].to_string(index=False))
    print(f"\nOverall data quality score: {quality_score}%")


if __name__ == "__main__":
    build_catalog()
