"""Raw CSVs -> validation -> transform -> warehouse (DuckDB). Bad rows get quarantined, not dropped."""

import duckdb
import pandas as pd
from datetime import datetime
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "ads_warehouse.duckdb")

VALIDATION_LOG = []


def log_issue(table, rule, count, action):
    VALIDATION_LOG.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "table": table,
        "rule": rule,
        "rows_affected": int(count),
        "action_taken": action,
    })
    print(f"  [{table}] {rule}: {count} rows -> {action}")


def validate_and_clean_performance(df):
    """clicks<=impressions, conversions<=clicks, spend>=0, no nulls. bad rows go to quarantine."""
    df = df.copy()
    quarantine_frames = []

    bad = df["clicks"] > df["impressions"]
    if bad.sum() > 0:
        q = df[bad].copy()
        q["violation"] = "clicks_exceed_impressions"
        quarantine_frames.append(q)
        log_issue("daily_performance", "clicks <= impressions", bad.sum(), "quarantined")
        df = df[~bad]

    bad = df["conversions"] > df["clicks"]
    if bad.sum() > 0:
        q = df[bad].copy()
        q["violation"] = "conversions_exceed_clicks"
        quarantine_frames.append(q)
        log_issue("daily_performance", "conversions <= clicks", bad.sum(), "quarantined")
        df = df[~bad]

    bad = df["spend"] < 0
    if bad.sum() > 0:
        q = df[bad].copy()
        q["violation"] = "negative_spend"
        quarantine_frames.append(q)
        log_issue("daily_performance", "spend >= 0", bad.sum(), "quarantined")
        df = df[~bad]

    key_cols = ["date", "campaign_id", "advertiser_id", "impressions", "clicks", "conversions", "spend"]
    bad = df[key_cols].isnull().any(axis=1)
    if bad.sum() > 0:
        q = df[bad].copy()
        q["violation"] = "null_in_key_field"
        quarantine_frames.append(q)
        log_issue("daily_performance", "no nulls in key columns", bad.sum(), "quarantined")
        df = df[~bad]

    quarantine_df = pd.concat(quarantine_frames, ignore_index=True) if quarantine_frames else pd.DataFrame()
    return df, quarantine_df


def validate_advertisers(df):
    df = df.copy()
    bad = pd.to_datetime(df["signup_date"]) > pd.Timestamp.now()
    if bad.sum() > 0:
        log_issue("advertisers", "signup_date not in future", bad.sum(), "dropped")
        df = df[~bad]
    return df


def transform(performance_df):
    """derives ctr, cvr, cpc, and date rollups once, so every query downstream agrees"""
    df = performance_df.copy()
    df["ctr"] = (df["clicks"] / df["impressions"]).where(df["impressions"] > 0, 0)
    df["cvr"] = (df["conversions"] / df["clicks"]).where(df["clicks"] > 0, 0)
    df["cpc"] = (df["spend"] / df["clicks"]).where(df["clicks"] > 0, 0)
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").apply(lambda p: p.start_time.date())
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").astype(str)
    df["quarter"] = pd.to_datetime(df["date"]).dt.to_period("Q").astype(str)
    return df


def run_etl():
    print("Loading raw CSVs...")
    advertisers = pd.read_csv(f"{DATA_DIR}/raw_advertisers.csv")
    campaigns = pd.read_csv(f"{DATA_DIR}/raw_campaigns.csv")
    performance = pd.read_csv(f"{DATA_DIR}/raw_daily_performance.csv")

    print("\nValidating advertisers...")
    advertisers_clean = validate_advertisers(advertisers)

    print("\nValidating daily_performance...")
    performance_clean, quarantine = validate_and_clean_performance(performance)

    print("\nTransforming (deriving CTR, CVR, CPC, date rollups)...")
    performance_final = transform(performance_clean)

    print(f"\nWriting to warehouse: {DB_PATH}")
    con = duckdb.connect(DB_PATH)
    con.execute("DROP TABLE IF EXISTS advertisers")
    con.execute("DROP TABLE IF EXISTS campaigns")
    con.execute("DROP TABLE IF EXISTS daily_performance")
    con.execute("DROP TABLE IF EXISTS quarantined_records")
    con.execute("DROP TABLE IF EXISTS etl_validation_log")

    con.register("adv_df", advertisers_clean)
    con.execute("CREATE TABLE advertisers AS SELECT * FROM adv_df")

    con.register("camp_df", campaigns)
    con.execute("CREATE TABLE campaigns AS SELECT * FROM camp_df")

    con.register("perf_df", performance_final)
    con.execute("CREATE TABLE daily_performance AS SELECT * FROM perf_df")

    if not quarantine.empty:
        con.register("quar_df", quarantine)
        con.execute("CREATE TABLE quarantined_records AS SELECT * FROM quar_df")
    else:
        con.execute("CREATE TABLE quarantined_records (date VARCHAR, campaign_id INTEGER, violation VARCHAR)")

    log_df = pd.DataFrame(VALIDATION_LOG)
    con.register("log_df", log_df)
    con.execute("CREATE TABLE etl_validation_log AS SELECT * FROM log_df")

    con.close()

    print(f"\nETL complete.")
    print(f"  Advertisers loaded: {len(advertisers_clean):,}")
    print(f"  Campaigns loaded: {len(campaigns):,}")
    print(f"  Performance rows loaded (clean): {len(performance_final):,}")
    print(f"  Quarantined rows: {len(quarantine):,}")
    print(f"  Validation log entries: {len(log_df)}")


if __name__ == "__main__":
    run_etl()
