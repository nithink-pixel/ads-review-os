"""Generate synthetic ad marketplace data: advertisers, campaigns, daily performance."""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import os

random.seed(42)
np.random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

INDUSTRIES = ["Retail", "Food & Beverage", "Travel", "Finance", "Auto", "Tech", "Entertainment"]
TIERS = ["Enterprise", "Mid-Market", "SMB"]
REGIONS = ["US-West", "US-East", "US-Central", "Canada", "LatAm"]
OBJECTIVES = ["Awareness", "Traffic", "Conversion", "App Install"]

# Industry-level baseline performance benchmarks (so numbers look real, not random)
INDUSTRY_BENCHMARKS = {
    "Retail":          {"ctr": 0.018, "cvr": 0.045, "cpc": 0.85},
    "Food & Beverage":  {"ctr": 0.022, "cvr": 0.060, "cpc": 0.65},
    "Travel":          {"ctr": 0.014, "cvr": 0.030, "cpc": 1.20},
    "Finance":         {"ctr": 0.009, "cvr": 0.025, "cpc": 2.10},
    "Auto":            {"ctr": 0.011, "cvr": 0.020, "cpc": 1.75},
    "Tech":            {"ctr": 0.016, "cvr": 0.038, "cpc": 1.40},
    "Entertainment":   {"ctr": 0.025, "cvr": 0.050, "cpc": 0.55},
}

START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)
ALL_DATES = pd.date_range(START_DATE, END_DATE, freq="D")

COMPANY_POOL = {
    "Retail": ["Urban Threads", "Nordic Home", "Bright Basket", "Pace Apparel", "Stonewell Goods",
               "Lattice Living", "Maple & Birch", "Coast Supply Co", "Verve Retail", "Daybreak Mart"],
    "Food & Beverage": ["Brewline Coffee", "Harvest Kitchen", "Salt & Stem", "Greenleaf Eats",
                        "Crumb Bakehouse", "Tideline Seafood", "Roasted Bean Co", "Forkful"],
    "Travel": ["Voyageur Trips", "Atlas Stays", "Wanderlight", "Northbound Travel", "Tripcrest"],
    "Finance": ["Ledgerline", "Northfield Bank", "Sunrise Capital", "Vault Finance", "Clearwater Credit"],
    "Auto": ["Driftline Motors", "Apex Auto Group", "Roadcrest", "Ferro Vehicles"],
    "Tech": ["Brightstack", "Loopwire", "Nimbus Cloud Co", "Vector Apps", "Pixel Forge"],
    "Entertainment": ["Echo Studios", "Reelhouse", "Cadence Media", "Playline Games"],
}


def generate_advertisers(n_per_industry_range=(5, 10)):
    rows = []
    advertiser_id = 1
    for industry in INDUSTRIES:
        companies = COMPANY_POOL[industry]
        for company in companies:
            tier = np.random.choice(TIERS, p=[0.25, 0.40, 0.35])
            signup_date = START_DATE + timedelta(days=int(np.random.uniform(0, 540)))
            # assign a lifecycle trajectory: growing, stable, declining/churning
            trajectory = np.random.choice(
                ["growing", "stable", "declining", "churned"],
                p=[0.30, 0.40, 0.20, 0.10]
            )
            rows.append({
                "advertiser_id": advertiser_id,
                "company": company,
                "industry": industry,
                "tier": tier,
                "region": np.random.choice(REGIONS, p=[0.30, 0.28, 0.20, 0.12, 0.10]),
                "signup_date": signup_date.date(),
                "trajectory": trajectory,  # internal field used for data gen, kept for QA reference
            })
            advertiser_id += 1
    return pd.DataFrame(rows)


def generate_campaigns(advertisers_df, campaigns_per_advertiser_range=(2, 6)):
    rows = []
    campaign_id = 1
    for _, adv in advertisers_df.iterrows():
        n_campaigns = np.random.randint(*campaigns_per_advertiser_range)
        last_end = pd.Timestamp(adv["signup_date"])
        for _ in range(n_campaigns):
            start = last_end + timedelta(days=int(np.random.uniform(1, 25)))
            if start > END_DATE - timedelta(days=14):
                break
            duration = int(np.random.uniform(14, 120))
            end = min(start + timedelta(days=duration), END_DATE)
            tier_budget_mult = {"Enterprise": 8000, "Mid-Market": 2500, "SMB": 600}[adv["tier"]]
            budget = round(np.random.uniform(0.5, 2.0) * tier_budget_mult, 2)
            rows.append({
                "campaign_id": campaign_id,
                "advertiser_id": adv["advertiser_id"],
                "campaign_name": f"{adv['company']} - {np.random.choice(OBJECTIVES)} {start.strftime('%b%y')}",
                "objective": np.random.choice(OBJECTIVES, p=[0.25, 0.30, 0.35, 0.10]),
                "budget": budget,
                "start_date": start.date(),
                "end_date": end.date(),
            })
            campaign_id += 1
            last_end = end
    return pd.DataFrame(rows)


def trajectory_multiplier(trajectory, day_index, total_days):
    """Returns a growth/decline multiplier over the advertiser's lifetime."""
    progress = day_index / max(total_days, 1)
    if trajectory == "growing":
        return 0.7 + 0.9 * progress  # ramps up to ~1.6x
    elif trajectory == "stable":
        return 0.95 + 0.1 * np.sin(progress * 6)  # mild seasonal wobble
    elif trajectory == "declining":
        return 1.3 - 0.9 * progress  # ramps down toward ~0.4x
    elif trajectory == "churned":
        # active then drops to near-zero in back half
        return 1.1 if progress < 0.55 else max(0.02, 0.15 - 0.1 * (progress - 0.55))
    return 1.0


def generate_daily_performance(advertisers_df, campaigns_df):
    rows = []
    adv_lookup = advertisers_df.set_index("advertiser_id").to_dict("index")

    for _, camp in campaigns_df.iterrows():
        adv = adv_lookup[camp["advertiser_id"]]
        bench = INDUSTRY_BENCHMARKS[adv["industry"]]
        camp_start = pd.Timestamp(camp["start_date"])
        camp_end = pd.Timestamp(camp["end_date"])
        camp_dates = pd.date_range(camp_start, camp_end, freq="D")
        total_days = len(camp_dates)
        total_budget = camp["budget"]
        daily_base_spend = total_budget / max(total_days, 1)

        signup = pd.Timestamp(adv["signup_date"])
        lifetime_span = (END_DATE - signup).days

        for i, d in enumerate(camp_dates):
            day_idx_in_life = (d - signup).days
            traj_mult = trajectory_multiplier(adv["trajectory"], day_idx_in_life, lifetime_span)

            dow_mult = 1.15 if d.weekday() < 5 else 0.80
            holiday_mult = 1.35 if d.month in (11, 12) else 1.0

            noise = np.random.normal(1.0, 0.12)
            spend = max(0, daily_base_spend * traj_mult * dow_mult * holiday_mult * noise)

            cpc = max(0.05, np.random.normal(bench["cpc"], bench["cpc"] * 0.15))
            clicks = int(spend / cpc) if cpc > 0 else 0
            ctr = max(0.001, np.random.normal(bench["ctr"], bench["ctr"] * 0.20))
            impressions = int(clicks / ctr) if ctr > 0 else 0
            cvr = max(0.001, np.random.normal(bench["cvr"], bench["cvr"] * 0.25))
            conversions = int(clicks * cvr)

            rows.append({
                "date": d.date(),
                "campaign_id": camp["campaign_id"],
                "advertiser_id": camp["advertiser_id"],
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "spend": round(spend, 2),
            })

    df = pd.DataFrame(rows)

    # a few bad rows on purpose, to test the validation layer later
    anomaly_idx = df.sample(frac=0.0015, random_state=7).index
    for idx in anomaly_idx:
        kind = np.random.choice(["clicks_exceed_impressions", "negative_spend", "conversions_exceed_clicks"])
        if kind == "clicks_exceed_impressions":
            df.loc[idx, "clicks"] = df.loc[idx, "impressions"] + np.random.randint(50, 500)
        elif kind == "negative_spend":
            df.loc[idx, "spend"] = -abs(df.loc[idx, "spend"])
        elif kind == "conversions_exceed_clicks":
            df.loc[idx, "conversions"] = df.loc[idx, "clicks"] + np.random.randint(10, 100)

    return df


if __name__ == "__main__":
    print("Generating advertisers...")
    advertisers = generate_advertisers()

    print("Generating campaigns...")
    campaigns = generate_campaigns(advertisers)

    print("Generating daily performance (this is the big one)...")
    performance = generate_daily_performance(advertisers, campaigns)

    # Save raw (pre-ETL) data — this simulates the "raw ingestion" layer
    advertisers.to_csv(f"{OUT_DIR}/raw_advertisers.csv", index=False)
    campaigns.to_csv(f"{OUT_DIR}/raw_campaigns.csv", index=False)
    performance.to_csv(f"{OUT_DIR}/raw_daily_performance.csv", index=False)

    print(f"\nAdvertisers: {len(advertisers):,}")
    print(f"Campaigns: {len(campaigns):,}")
    print(f"Daily performance rows: {len(performance):,}")
    print(f"\nSaved to {OUT_DIR}/raw_*.csv")
