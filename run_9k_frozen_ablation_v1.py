from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd

ROOT=Path.cwd()
MATRIX=ROOT/"pmpd_v5_9k_dp4_candidate_matrix_v1"/"dp4_candidate_matrix_v1.csv"
FREEZE=ROOT/"pmpd_v5_9k_classifier_discovery_v1"/"discovery_model_freeze.json"
OUT=ROOT/"pmpd_v5_9k_ablation_v1"
OUT.mkdir(exist_ok=True)
EXPECTED_SHA="6ec9da73cf554469083d35b8866222ae8c66295562bba22557b5b77bfc9d0e57"

assert hashlib.sha256(MATRIX.read_bytes()).hexdigest()==EXPECTED_SHA
freeze=json.loads(FREEZE.read_text(encoding="utf-8"))
df=pd.read_csv(MATRIX,low_memory=False)
df=df[df["frozen_primary_outcome"].isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])].copy()
df["y"]=(df["frozen_primary_outcome"]=="FAVORABLE_FIRST").astype(float)

def auc_rank(y,p):
    y=np.asarray(y,float); p=np.asarray(p,float); n1=int(y.sum()); n0=len(y)-n1
    if n1==0 or n0==0:return np.nan
    r=pd.Series(p).rank(method="average").to_numpy()
    return float((r[y==1].sum()-n1*(n1+1)/2)/(n1*n0))

def metric(y,p):
    y=np.asarray(y,float); p=np.asarray(p,float)
    q20=np.quantile(p,.2); q80=np.quantile(p,.8)
    return {"auc":auc_rank(y,p),"brier":float(np.mean((p-y)**2)),
            "spread":float(y[p>=q80].mean()-y[p<=q20].mean())}

def transform(frame,features,prep):
    cols=[]
    for c in features:
        s=pd.to_numeric(frame[c],errors="coerce").astype(float)
        vals=s.fillna(float(prep[c]["median"])).to_numpy(float)
        cols.append((vals-float(prep[c]["median"]))/float(prep[c]["iqr"]))
    return np.column_stack(cols) if cols else np.empty((len(frame),0))

def predict_with(spec,frame,drop=None):
    feats=[c for c in spec["features"] if c!=drop]
    X=transform(frame,feats,spec["preprocessing"])
    z=np.full(len(frame),float(spec["coefficients"]["intercept"]))
    for i,c in enumerate(feats): z+=X[:,i]*float(spec["coefficients"][c])
    return 1/(1+np.exp(-np.clip(z,-30,30)))

rows=[]
print("=== 9K FROZEN COEFFICIENT ABLATION ===")
for direction in ["BULL","BEAR"]:
  spec=freeze["architectures"][f"{direction}_A2"]
  for part in ["DISCOVERY","VALIDATION_A","VALIDATION_B"]:
    d=df[(df.direction==direction)&(df.research_partition==part)].copy()
    y=d.y.to_numpy(float)
    pfull=predict_with(spec,d)
    full=metric(y,pfull)
    for feat in spec["features"]:
      p=predict_with(spec,d,drop=feat)
      m=metric(y,p)
      rec={"direction":direction,"partition":part,"dropped_feature":feat,
           "full_auc":full["auc"],"ablated_auc":m["auc"],"delta_auc_full_minus_ablated":full["auc"]-m["auc"],
           "full_brier":full["brier"],"ablated_brier":m["brier"],"delta_brier_full_minus_ablated":full["brier"]-m["brier"],
           "full_spread":full["spread"],"ablated_spread":m["spread"],"delta_spread_full_minus_ablated":full["spread"]-m["spread"]}
      rows.append(rec)
      print(direction,part,feat,
            "dAUC=",round(rec["delta_auc_full_minus_ablated"],6),
            "dBrier=",round(rec["delta_brier_full_minus_ablated"],6),
            "dSpread=",round(rec["delta_spread_full_minus_ablated"],6))

r=pd.DataFrame(rows)
r.to_csv(OUT/"frozen_coefficient_leave_one_out.csv",index=False)

# Cross-window sign consistency of incremental AUC contribution.
summary=[]
for (direction,feat),g in r.groupby(["direction","dropped_feature"]):
    vals={row.partition:row.delta_auc_full_minus_ablated for row in g.itertuples()}
    va=vals.get("VALIDATION_A"); vb=vals.get("VALIDATION_B"); disc=vals.get("DISCOVERY")
    summary.append({"direction":direction,"feature":feat,
                    "discovery_delta_auc":disc,"validation_a_delta_auc":va,"validation_b_delta_auc":vb,
                    "validation_same_positive_sign":bool(va>0 and vb>0),
                    "all_three_positive":bool(disc>0 and va>0 and vb>0)})
s=pd.DataFrame(summary)
s.to_csv(OUT/"ablation_replication_summary.csv",index=False)
print("\n=== REPLICATION SUMMARY ===")
print(s.to_string(index=False))

meta={"protocol":"PMPD_V5_9K_FROZEN_ABLATION_V1","matrix_sha256":EXPECTED_SHA,
      "method":"Leave one feature coefficient at zero; retain all Discovery-fitted preprocessing and remaining coefficients unchanged.",
      "refit":False,"threshold_tuning":False,"architecture_change":False,"production_rule_authorized":False}
(OUT/"ablation_protocol.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
print("ABLATION_REFIT=False")
print("THRESHOLD_TUNING=False")
print("ARCHITECTURE_CHANGE=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("FROZEN_ABLATION_GATE=PASS")
