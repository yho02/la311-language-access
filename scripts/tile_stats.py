"""Median days to close by limited-English quintile, grouped into everyday vs slow services.

Feeds the "days to close" tile on the Power BI dashboard (tile_stats table).
Same filters as notebook 03: resident-reported, non-cancelled, valid dates, City of LA
tracts with 100+ households. Medians are Kaplan-Meier, so open requests count as still waiting.
"""
import duckdb
import pandas as pd
from lifelines import KaplanMeierFitter

PROC = "data/processed"
OUT = f"{PROC}/powerbi_web/tile_stats.csv"
MAIN = ["Bulky Items", "Illegal Dumping Pickup", "Metal/Household Appliances", "Electronic Waste", "Graffiti Removal"]
SLOW = ["Homeless Encampment", "Multiple Streetlight Issue", "Single Streetlight Issue"]

df = duckdb.connect().sql(f"""
SELECT r.request_type, r.closed_at, r.created_at, r.days_to_close, r.is_driver_report, c.lep_share, c.geoid
FROM '{PROC}/requests_clean.parquet' r
JOIN '{PROC}/request_tract.parquet' t USING (sr_number)
JOIN '{PROC}/tracts_city.parquet' c ON c.geoid = t.geoid
WHERE t.in_city_tract AND NOT r.bad_dates AND NOT r.is_cancelled
  AND c.households >= 100 AND c.median_income IS NOT NULL AND c.lep_share IS NOT NULL
""").df()

obs_end = df.closed_at.max()
df["closed"] = df.closed_at.notna()
df["duration"] = df.days_to_close.fillna((obs_end - df.created_at).dt.total_seconds() / 86400)

res = df[~df.is_driver_report & df.request_type.isin(MAIN + SLOW)].copy()
tr = res[["geoid", "lep_share"]].drop_duplicates()
tr["quintile"] = pd.qcut(tr.lep_share, 5, labels=[1, 2, 3, 4, 5]).astype(int)
res = res.merge(tr[["geoid", "quintile"]], on="geoid")
res["service_group"] = res.request_type.map(lambda t: "Everyday" if t in MAIN else "Slow")

rows = []
for group, sub_g in [("Everyday", res[res.service_group == "Everyday"]),
                     ("Slow", res[res.service_group == "Slow"]),
                     ("All", res)]:
    for q, sub in sub_g.groupby("quintile"):
        km = KaplanMeierFitter().fit(sub.duration, sub.closed)
        rows.append({"service_group": group, "quintile": q, "requests": len(sub),
                     "median_days": round(float(km.median_survival_time_), 2),
                     "still_open": round(float((~sub.closed).mean()), 4)})

pd.DataFrame(rows).to_csv(OUT, index=False)
print(pd.DataFrame(rows).to_string(index=False))
