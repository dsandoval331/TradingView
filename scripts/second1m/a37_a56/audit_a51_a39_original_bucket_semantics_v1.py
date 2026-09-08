from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
TIM=ROOT/"ae2_preferred_level_timing_v1"/"a38_preferred_level_timing_events_v1.parquet"
SRC=ROOT/"ae2_c2_predictors_v1"/"ae2_c2_predictor_features_v1.parquet"
INV=ROOT/"ae2_c1_c2_transition_v1"/"a39_frozen_transition_bucket_inventory_v1.csv"

print("="*132)
print("A51.3E - A39 ORIGINAL BUCKET SEMANTICS AUDIT")
print("="*132)

t=pd.read_parquet(TIM)[["symbol","trade_date","direction","research_period"]]
x=pd.read_parquet(SRC)[["symbol","trade_date","direction","vwap_distance_change_pp"]]
u=t.merge(x,on=["symbol","trade_date","direction"],how="left",validate="one_to_one")
inv=pd.read_csv(INV)
z=inv[inv.feature.eq("vwap_distance_change_pp")].copy()

print("\nPersisted A39 bucket rows:")
print(z.to_string(index=False))

# Parse the literal persisted Interval strings, preserving their written semantics.
ivals=pd.arrays.IntervalArray.from_tuples([
    (-0.477,0.0175),(0.0175,0.0869),(0.0869,0.18),(0.18,0.343),(0.343,2.836)
],closed="right")
cats=pd.cut(u["vwap_distance_change_pp"],
            bins=[-0.477,0.0175,0.0869,0.18,0.343,2.836],
            labels=[1,2,3,4,5], include_lowest=True)

print("\nPreferred counts using literal persisted bucket labels:")
for period in ["DISCOVERY","VALIDATION"]:
    a=u.loc[u.research_period.eq(period)].copy()
    q=cats.loc[a.index]
    print(period, {i:int((q==i).sum()) for i in range(1,6)}, "missing", int(q.isna().sum()))

# Compare full-population counts to inventory's frozen n values.
full=pd.read_parquet(SRC)[["vwap_distance_change_pp"]]
fq=pd.cut(full["vwap_distance_change_pp"],
          bins=[-0.477,0.0175,0.0869,0.18,0.343,2.836],
          labels=[1,2,3,4,5], include_lowest=True)
print("\nFull 8,307 counts using literal labels:", {i:int((fq==i).sum()) for i in range(1,6)}, "missing",int(fq.isna().sum()))
print("Inventory frozen n:", z["n"].astype(int).tolist())

# Show exact values around the two Q3 boundaries in Preferred population, outcome-free.
for edge in [0.0869,0.18]:
    near=u.iloc[(u.vwap_distance_change_pp-edge).abs().argsort()[:12]]
    print(f"\nClosest Preferred values to edge {edge}:")
    print(near[["symbol","trade_date","direction","research_period","vwap_distance_change_pp"]].sort_values("vwap_distance_change_pp").to_string(index=False))

print("\nRESULT: BUCKET SEMANTICS AUDIT COMPLETE. No outcomes analyzed; no thresholds fitted.")
