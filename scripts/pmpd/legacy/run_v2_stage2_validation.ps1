# PMPD V5 9J — VWAP Event-Path V2 Stage 2
# Validation A/B using ONLY the frozen Discovery proposal.
# Run only after Stage 1 has been reviewed and frozen.
$ErrorActionPreference="Stop"

python -c @'
import json
from pathlib import Path
import numpy as np
import pandas as pd

root=Path(".").resolve()
parent=pd.read_csv(root/"pmpd_v5_9h_research_dataset_v1"/"decision_research.csv")
v2=pd.read_csv(root/"pmpd_v5_9j_vwap_event_path_v2_full"/"decision_vwap_event_path_v2.csv")
freeze_path=root/"pmpd_v5_9j_vwap_event_path_v2_discovery"/"DISCOVERY_CUTPOINT_PROPOSAL.json"
f=json.loads(freeze_path.read_text(encoding="utf-8"))
assert f["source_partition"]=="DISCOVERY_ONLY"
assert f["validation_peeked"] is False

keep=[
 "decision_id","event_id","symbol","trade_date","direction","decision_type",
 "primary_decision_unit","primary_inference_eligible","resolved_primary",
 "favorable_first","outcome","split"
]
d=parent[keep].merge(v2,on=[
 "decision_id","event_id","symbol","trade_date","direction","decision_type",
 "primary_decision_unit"
],how="inner",validate="one_to_one")
x=d[
 d.primary_decision_unit.astype(bool)
 & d.primary_inference_eligible.astype(bool)
 & d.resolved_primary.astype(bool)
].copy()

rows=[]
for split in ["VALIDATION_A","VALIDATION_B"]:
    z=x[x.split.eq(split)].copy()
    for feat,cps in f["cutpoints"].items():
        vals=pd.to_numeric(z[feat],errors="coerce")
        for cp in cps:
            lo=z[vals<=cp]
            hi=z[vals>cp]
            if len(lo)<100 or len(hi)<100: 
                continue
            rows.append({
              "split":split,"feature":feat,"cutpoint":cp,
              "n_low":len(lo),"rate_low":pd.to_numeric(lo.favorable_first,errors="coerce").mean(),
              "n_high":len(hi),"rate_high":pd.to_numeric(hi.favorable_first,errors="coerce").mean(),
              "delta_high_minus_low":
                pd.to_numeric(hi.favorable_first,errors="coerce").mean()
                -pd.to_numeric(lo.favorable_first,errors="coerce").mean()
            })

for split in ["VALIDATION_A","VALIDATION_B"]:
    z=x[x.split.eq(split)].copy()
    for feat in f["categorical_features"]:
        for val,g in z.groupby(feat,dropna=False):
            if len(g)<100: continue
            rows.append({
              "split":split,"feature":feat,"cutpoint":f"CATEGORY={val}",
              "n_low":len(g),"rate_low":pd.to_numeric(g.favorable_first,errors="coerce").mean(),
              "n_high":np.nan,"rate_high":np.nan,"delta_high_minus_low":np.nan
            })

o=root/"pmpd_v5_9j_vwap_event_path_v2_validation"
o.mkdir(parents=True,exist_ok=True)
r=pd.DataFrame(rows)
r.to_csv(o/"validation_results.csv",index=False)
print("VALIDATION_STAGE_COMPLETE")
print("ROWS=",len(r))
print("OUTPUT=",o/"validation_results.csv")
print("No production rule is authorized by this script.")
'@
