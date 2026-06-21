# Ads Review OS
**An internal advertising business review platform, built to mirror what a Strategy & Planning Analyst supports before every monthly and quarterly business review.**

## The Problem
A VP of Advertising needs a trusted, repeatable way to answer three questions every month: How is revenue trending? Which advertisers are healthy, at risk, or churning? And can I trust these numbers enough to make a budget call based on them?

Most internal dashboards fail at the third question. Numbers get recalculated slightly differently by different teams, nobody owns a metric's definition, and "data quality" is a vague aspiration rather than something measurable. This project builds the full pipeline, from raw data to governed, trusted, self-service reporting, to solve that end to end.

## Architecture
```
Raw Data (synthetic ad marketplace)
    -> ETL Pipeline (validation + quarantine, not silent deletion)
    -> Data Warehouse (DuckDB)
    -> KPI Governance Catalog (one definition, one owner, per metric)
    -> Executive Review Dashboard (MBR / QBR / Advertiser Health / Self-Service)
```

## What's Built (and verified working)

**Phase 1 — Data Generation** (`data/generate_data.py`)
41 advertisers across 7 industries, 127 campaigns, ~8,600 days of performance data spanning two years. Industry-specific CTR/CVR/CPC benchmarks (not uniform random noise), realistic weekday/weekend and holiday seasonality, and four advertiser lifecycle trajectories (growing, stable, declining, churned). A small number of intentional data anomalies are injected, so the validation layer has something real to catch.

**Phase 2 — ETL Pipeline** (`etl/run_etl.py`)
Four validation rules enforced on every load: clicks cannot exceed impressions, conversions cannot exceed clicks, spend cannot be negative, and no nulls in key fields. Violating records are **quarantined**, not silently deleted, every quarantine event is logged with a timestamp, rule, row count, and action taken. This run caught all 13 injected anomalies correctly. Derived metrics (CTR, CVR, CPC, week/month/quarter rollups) are computed once at the warehouse layer, so every downstream query uses an identical definition.

**Phase 3 — KPI Governance Catalog** (`etl/build_kpi_catalog.py`)
Six core KPIs, each with a formula, plain-language definition, business owner, source table, refresh cadence, and business purpose. A live data quality score (currently 99.85%) is computed directly from the ETL validation log, not hardcoded.

**Phase 4 — Executive Dashboard** (`dashboard/app.py`, Streamlit)
Five views: an Executive Scorecard (revenue, CTR, CVR, CPC, active advertisers at a glance), an MBR view (month-over-month comparison), a QBR view (quarter-over-quarter and year-over-year), an Advertiser Health segmentation (Growing / Stable / At Risk / Churned, based on trailing 60-day spend trend vs. the prior 60 days), and a Data Trust panel exposing the live KPI catalog and validation log. All filters (industry, region, tier, date range) are self-service, no SQL required.

## A Real Insight the Platform Surfaces
Filtering to the Retail industry and looking at the Advertiser Health tab, several Retail accounts show up in the "At Risk" segment with spend down more than 15% over the trailing 60 days. Cross-referencing against the QBR view, this tracks with a broader Q3 dip. The platform doesn't just show this, it's the kind of insight an MBR is built to surface: which segment is the actual driver, not just "revenue is down."

## What I Deliberately Did Not Build
A natural-language AI query layer ("ask why revenue declined") was considered, but cut from this version. Building it shallow, in a way that could give a wrong or hallucinated answer live in an interview, would have hurt more than helped. The KPI catalog and data model here are structured specifically so that layer could be added cleanly later: every metric already has a formula and source table defined, which is the actual prerequisite for a reliable AI assistant.

## Tech Stack
Python (Pandas, NumPy) for data generation and transformation, DuckDB as the warehouse, Streamlit and Plotly for the dashboard layer. No external API dependencies, runs fully locally.

## Running It
```bash
pip install pandas numpy duckdb streamlit plotly faker
python3 data/generate_data.py
python3 etl/run_etl.py
python3 etl/build_kpi_catalog.py
streamlit run dashboard/app.py
```
