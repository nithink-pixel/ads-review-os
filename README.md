# Ads Review OS

A self-contained advertising business review platform. The goal was to build the thing a Strategy & Planning analyst actually leans on every month: a place to check revenue, see which advertisers are healthy versus slipping, and trust that the numbers on screen are the same numbers everyone else on the team is looking at.

## Why this exists

Most internal dashboards I've used or built have the same failure mode. Two people pull "CTR" for the same period and get different numbers, because somewhere along the line someone wrote a slightly different query, or a different team's definition of "active advertiser" doesn't match yours. Nobody notices until a leadership review goes sideways over a number nobody can explain.

This project is my attempt at fixing that end to end rather than patching it dashboard by dashboard. Every metric has exactly one formula, one owner, and one source table. Bad data gets caught and quarantined before it ever reaches a chart, not silently dropped, not silently included. And the whole pipeline is auditable, so if someone asks "why does this number look off," there's an actual answer instead of a shrug.

## How it's put together

```
raw csv data (synthetic ad marketplace)
      |
      v
ETL pipeline -- validates, quarantines bad rows, derives CTR/CVR/CPC once
      |
      v
DuckDB warehouse
      |
      v
KPI catalog -- formula + owner + source + refresh cadence, per metric
      |
      v
Streamlit dashboard -- scorecard, MBR, QBR, advertiser health, data trust panel
```

### The data (data/generate_data.py)

41 advertisers spread across 7 industries, 127 campaigns, and around 8,600 rows of daily performance data covering two years. I didn't want this to be obviously fake uniform-random data, so each industry has its own CTR/CVR/CPC benchmark range, there's weekday/weekend seasonality plus a holiday bump in November/December, and each advertiser gets randomly assigned a lifecycle, growing, stable, declining, or churned, that actually plays out across their daily numbers over time. I also seeded in a handful of bad rows on purpose so the validation layer downstream has something real to catch.

### ETL (etl/run_etl.py)

Four rules get checked on every load: clicks can't exceed impressions, conversions can't exceed clicks, spend can't go negative, and none of the key fields can be null. Anything that fails gets pulled into a quarantine table along with which rule it broke, rather than just getting deleted. Last run caught all 13 of the anomalies I'd seeded in. CTR, CVR, CPC, and the week/month/quarter rollups all get computed once here, at the warehouse layer, so every dashboard query downstream pulls from the same definition.

### KPI catalog (etl/build_kpi_catalog.py)

Six metrics, each with its formula spelled out, a plain definition, who owns it, which table it comes from, and how often it refreshes. There's a data quality score on here too, currently around 99.85%, computed live from the ETL log rather than typed in.

### Dashboard (dashboard/app.py)

Five tabs. An executive scorecard for the quick view. An MBR tab comparing the current month against the prior one. A QBR tab doing the same at the quarter level, plus year-over-year where there's enough history. An advertiser health tab that buckets every advertiser into Growing, Stable, At Risk, or Churned based on how their spend over the last 60 days compares to the 60 before that. A data trust tab, which makes the KPI catalog and validation log visible, so anyone using the dashboard can check exactly how a number was calculated. All filtering (industry, region, tier, date range) is point-and-click, no SQL needed.

## Something it actually surfaced

Filtering down to Retail and looking at the advertiser health tab, a cluster of Retail accounts show up At Risk, spend down more than 15% over the trailing 60 days. Cross-checking that against the QBR tab lines up with a broader dip that quarter. That's the point of this, not just saying revenue is down, but letting you find which segment is driving it.

## What's not in here

I left out a natural-language query layer. I thought about it, but decided against shipping something half-built that could give a wrong answer if someone actually tried it. The KPI catalog is structured so that layer could be added cleanly later, every metric already has its formula and source defined, which is the actual prerequisite for it.

## Stack

Python, Pandas, DuckDB, Streamlit, Plotly. Nothing calls out to an external API, runs fully locally once the data's generated.

## Running it

pip install -r requirements.txt
python3 data/generate_data.py
python3 etl/run_etl.py
python3 etl/build_kpi_catalog.py
streamlit run dashboard/app.py
