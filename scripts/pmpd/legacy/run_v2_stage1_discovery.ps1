# PMPD V5 9J — VWAP Event-Path V2 Stage 1
# Integrity-gated Discovery characterization only.
# Run from C:\Users\DirtySouth\TradingResearch with .venv active.
$ErrorActionPreference="Stop"

python -c @'
import json, math
from pathlib import Path
import numpy as np
import pandas as pd

root=Path(".").resolve()
parent_path=root/"pmpd_v5_9h_research_dataset_v1"/"decision_research.csv"
v2_path=root/"pmpd_v5_9j_vwap_event_path_v2_full"/"decision_vwap_event_path_v2.csv"
outdir=root/"pmpd_v5_9j_vwap_event_path_v2_discovery"
outdir.mkdir(parents=True,exist_ok=True)

parent=pd.read_csv(parent_path)
v2=pd.read_csv(v2_path)

# Hard integrity gate before outcome join.
assert len(parent)==450491, f"Unexpected parent rows {len(parent)}"
assert parent.decision_id.nunique()==450491
assert len(v2)==450491, f"Unexpected V2 rows {len(v2)}"
assert v2.decision_id.nunique()==450491
assert set(parent.decision_id)==set(v2.decision_id)
assert v2.event_id.nunique()==44627
assert v2.symbol.nunique()==112

for c in ["timestamp_utc","dp1_timestamp_utc","source_max_timestamp_utc"]:
    v2[c]=pd.to_datetime(v2[c],utc=True,errors="raise")
assert (v2.dp1_timestamp_utc<=v2.timestamp_utc).all()
assert (v2.source_max_timestamp_utc<=v2.timestamp_utc).all()
assert (pd.to_numeric(v2.event_minutes_from_dp1,errors="raise")>=0).all()

# Outcomes are joined only after integrity passes.
keep_parent=[
    "decision_id","event_id","symbol","trade_date","direction","decision_type",
    "primary_decision_unit","primary_inference_eligible","resolved_primary",
    "favorable_first","outcome","split","reference_price"
]
d=parent[keep_parent].merge(v2,on=[
    "decision_id","event_id","symbol","trade_date","direction","decision_type",
    "primary_decision_unit"
],how="inner",validate="one_to_one")

# Primary analysis unit from frozen 9H protocol.
x=d[
    d.primary_decision_unit.astype(bool)
    & d.primary_inference_eligible.astype(bool)
    & d.resolved_primary.astype(bool)
].copy()
disc=x[x.split.eq("DISCOVERY")].copy()

features_cont=[
    "directional_vwap_distance_pct",
    "directional_vwap_distance_min_from_dp1_pct",
    "directional_vwap_distance_max_from_dp1_pct",
    "event_minutes_from_dp1",
    "event_bars_from_dp1_inclusive",
    "event_vwap_touch_count_from_dp1",
    "event_vwap_cross_count_from_dp1",
    "event_favorable_close_fraction",
    "event_adverse_close_fraction",
    "event_consecutive_favorable_closes_at_decision",
    "event_consecutive_adverse_closes_at_decision",
    "event_directional_rejection_count",
    "event_reclaim_count",
    "event_loss_count",
    "event_minutes_since_last_touch",
    "event_minutes_since_last_cross",
    "event_minutes_since_last_reclaim",
    "event_minutes_since_last_loss",
    "event_minutes_since_last_rejection",
]
features_cat=[
    "directional_vwap_side",
    "event_vwap_touch_from_dp1",
    "event_vwap_cross_from_dp1",
    "event_directional_rejection_seen",
    "event_reclaim_seen",
    "event_loss_seen",
    "event_vwap_side_changed_from_dp1",
    "event_vwap_loss_after_structural_clearance",
]

rows=[]
cutpoints={}
for feat in features_cont:
    s=pd.to_numeric(disc[feat],errors="coerce")
    z=disc.loc[s.notna(),["direction","decision_type","favorable_first"]].copy()
    z["value"]=s[s.notna()].values
    if len(z)<100:
        continue
    # Discovery-only descriptive quartiles; these are candidate cutpoints, not production thresholds.
    qs=np.nanquantile(z.value,[0.25,0.50,0.75])
    cutpoints[feat]=[float(q) for q in qs if np.isfinite(q)]
    rows.append({
        "feature":feat,"kind":"continuous","n":len(z),
        "q25":qs[0],"q50":qs[1],"q75":qs[2],
        "mean":z.value.mean(),"std":z.value.std(),
        "favorable_rate":pd.to_numeric(z.favorable_first,errors="coerce").mean()
    })

cat_rows=[]
for feat in features_cat:
    for val,g in disc.groupby(feat,dropna=False):
        if len(g)<50:
            continue
        cat_rows.append({
            "feature":feat,"value":str(val),"n":len(g),
            "favorable_rate":pd.to_numeric(g.favorable_first,errors="coerce").mean()
        })

# Also freeze the analysis scopes; do not search all arbitrary combinations.
scopes=(
    disc.groupby(["direction","decision_type"],dropna=False)
    .size().reset_index(name="n")
)
scopes=scopes[scopes.n>=200].copy()

pd.DataFrame(rows).to_csv(outdir/"discovery_continuous_summary.csv",index=False)
pd.DataFrame(cat_rows).to_csv(outdir/"discovery_categorical_summary.csv",index=False)
scopes.to_csv(outdir/"eligible_direction_decision_scopes.csv",index=False)

freeze={
  "protocol":"PMPD_V5_9J_VWAP_EVENT_PATH_V2",
  "stage":"DISCOVERY_CUTPOINT_PROPOSAL",
  "source_partition":"DISCOVERY_ONLY",
  "cutpoint_rule":"Q25_Q50_Q75_DESCRIPTIVE_CANDIDATES_ONLY",
  "cutpoints":cutpoints,
  "continuous_features":features_cont,
  "categorical_features":features_cat,
  "scope_min_n":200,
  "production_rule_authorized":False,
  "validation_peeked":False
}
(outdir/"DISCOVERY_CUTPOINT_PROPOSAL.json").write_text(json.dumps(freeze,indent=2,sort_keys=True),encoding="utf-8")

print("STAGE1_INTEGRITY_GATE=PASS")
print("PRIMARY_RESOLVED_ROWS=",len(x))
print("DISCOVERY_ROWS=",len(disc))
print("ELIGIBLE_SCOPES=",len(scopes))
print("CUTPOINT_FEATURES=",len(cutpoints))
print("OUTPUT_DIR=",outdir)
print("STOP: review/freeze Discovery proposal before Validation A/B.")
'@
