from pathlib import Path
import pandas as pd

ROOT=Path(".").resolve()
PARENT=ROOT/"pmpd_v5_9h_research_dataset_v1"/"decision_research.csv"
V2=ROOT/"pmpd_v5_9j_vwap_event_path_v2_full50"/"decision_vwap_event_path_v2.csv"

p=pd.read_csv(PARENT, low_memory=False)
v=pd.read_csv(V2, low_memory=False)

for df in (p,v):
    df["timestamp_utc"]=pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")

print("=== DECISION TYPE TAXONOMY ===")
counts=(p.groupby("decision_type")
          .agg(rows=("decision_id","size"),events=("event_id","nunique"))
          .sort_index())
print(counts.to_string())

print("\n=== DP3 / DP4 / DP5 TYPES ===")
mask=p.decision_type.astype(str).str.match(r"DP[345]_",na=False)
dp=p.loc[mask,["event_id","decision_id","decision_type","timestamp_utc","direction"]].copy()
print(dp.groupby("decision_type").agg(rows=("decision_id","size"),events=("event_id","nunique")).sort_index().to_string())

print("\n=== FIRST DP3/4/5 PER EVENT ===")
first_any=(dp.sort_values(["event_id","timestamp_utc"])
             .groupby("event_id",as_index=False).first())
print(first_any.groupby("decision_type").agg(events=("event_id","nunique")).sort_index().to_string())

print("\n=== DP4 PRESENCE ===")
dp4=dp[dp.decision_type.astype(str).str.match(r"DP4_",na=False)].copy()
events_total=p.event_id.nunique()
events_dp4=dp4.event_id.nunique()
print("TOTAL_EVENTS=",events_total)
print("EVENTS_WITH_DP4=",events_dp4)
print("EVENTS_WITHOUT_DP4=",events_total-events_dp4)

print("\n=== EARLIEST DP3/4/5 VS EARLIEST DP4 ===")
first_dp4=(dp4.sort_values(["event_id","timestamp_utc"])
             .groupby("event_id",as_index=False).first()
             [["event_id","decision_type","timestamp_utc"]]
             .rename(columns={"decision_type":"first_dp4_type","timestamp_utc":"first_dp4_ts"}))
cmp=(first_any[["event_id","decision_type","timestamp_utc"]]
     .rename(columns={"decision_type":"first_any_type","timestamp_utc":"first_any_ts"})
     .merge(first_dp4,on="event_id",how="left"))
cmp["same_timestamp"]=cmp.first_any_ts.eq(cmp.first_dp4_ts)
cmp["minutes_any_before_dp4"]=(cmp.first_dp4_ts-cmp.first_any_ts).dt.total_seconds()/60.0
print("EVENTS_FIRST_ANY_EQUALS_FIRST_DP4=",int(cmp.same_timestamp.fillna(False).sum()))
print("EVENTS_FIRST_ANY_DIFFERS_FROM_DP4=",int((cmp.first_dp4_ts.notna() & ~cmp.same_timestamp.fillna(False)).sum()))
print("EVENTS_NO_DP4=",int(cmp.first_dp4_ts.isna().sum()))
print("\nFIRST_ANY_TYPE WHEN DIFFERENT FROM DP4:")
print(cmp.loc[cmp.first_dp4_ts.notna() & ~cmp.same_timestamp.fillna(False),"first_any_type"].value_counts().sort_index().to_string())
if cmp.first_dp4_ts.notna().any():
    z=cmp.loc[cmp.first_dp4_ts.notna(),"minutes_any_before_dp4"]
    print("\nMINUTES ANY BEFORE DP4 QUANTILES:")
    print(z.quantile([0,.25,.5,.75,.9,.95,.99,1]).to_string())

print("\n=== V2 STRUCTURAL-CLEARANCE FIELD PREVALENCE ===")
if "event_vwap_loss_after_structural_clearance" in v.columns:
    s=v["event_vwap_loss_after_structural_clearance"]
    if s.dtype!=bool:
        s=s.astype(str).str.lower().eq("true")
    print("TRUE_ROWS=",int(s.sum()))
    print("TRUE_EVENTS=",v.loc[s,"event_id"].nunique())
else:
    print("FIELD_ABSENT")

print("\n=== SAMPLE EVENTS WHERE FIRST ANY != DP4 ===")
sample=cmp.loc[cmp.first_dp4_ts.notna() & ~cmp.same_timestamp.fillna(False)].head(20)
print(sample.to_string(index=False))

print("\nTAXONOMY_GATE_COMPLETE")
