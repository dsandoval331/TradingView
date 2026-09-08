from pathlib import Path
import json, hashlib, math
import numpy as np
import pandas as pd

ROOT=Path.cwd()
MATRIX=ROOT/"pmpd_v5_9k_dp4_candidate_matrix_v1"/"dp4_candidate_matrix_v1.csv"
FREEZE=ROOT/"pmpd_v5_9k_classifier_discovery_v1"/"discovery_model_freeze.json"
OUT=ROOT/"pmpd_v5_9k_classifier_validation_v1"
OUT.mkdir(exist_ok=True)

EXPECTED_SHA="6ec9da73cf554469083d35b8866222ae8c66295562bba22557b5b77bfc9d0e57"
actual=hashlib.sha256(MATRIX.read_bytes()).hexdigest()
print("MATRIX_SHA256 =",actual)
assert actual==EXPECTED_SHA, f"Matrix fingerprint mismatch: {actual}"

freeze=json.loads(FREEZE.read_text(encoding="utf-8"))
assert freeze["matrix_sha256"]==EXPECTED_SHA
assert freeze["partition_fit"]=="DISCOVERY_ONLY"
assert freeze["validation_refit_allowed"] is False

df=pd.read_csv(MATRIX,low_memory=False)

def auc_rank(y,p):
    y=np.asarray(y,dtype=float); p=np.asarray(p,dtype=float)
    n1=int(y.sum()); n0=len(y)-n1
    if n1==0 or n0==0: return float("nan")
    ranks=pd.Series(p).rank(method="average").to_numpy()
    return float((ranks[y==1].sum()-n1*(n1+1)/2)/(n1*n0))

def metrics(y,p):
    eps=1e-12
    y=np.asarray(y,float); p=np.clip(np.asarray(p,float),eps,1-eps)
    q20=np.quantile(p,.2); q80=np.quantile(p,.8)
    lo=y[p<=q20]; hi=y[p>=q80]
    return {
      "n":int(len(y)),
      "favorable_rate":float(y.mean()),
      "auc":auc_rank(y,p),
      "brier":float(np.mean((p-y)**2)),
      "log_loss":float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),
      "top20_rate":float(hi.mean()) if len(hi) else None,
      "bottom20_rate":float(lo.mean()) if len(lo) else None,
      "top_minus_bottom":float(hi.mean()-lo.mean()) if len(hi) and len(lo) else None,
    }

def transform(frame,features,prep):
    X=[]
    for c in features:
        s=pd.to_numeric(frame[c],errors="coerce").astype(float)
        med=float(prep[c]["median"]); iqr=float(prep[c]["iqr"])
        vals=s.fillna(med).to_numpy(float)
        X.append((vals-med)/iqr)
    return np.column_stack(X) if X else np.empty((len(frame),0))

def predict(frame,spec):
    feats=spec["features"]
    prep=spec["preprocessing"]
    coef=spec["coefficients"]
    X=transform(frame,feats,prep)
    z=np.full(len(frame),float(coef["intercept"]))
    for i,c in enumerate(feats):
        z += X[:,i]*float(coef[c])
    z=np.clip(z,-30,30)
    return 1/(1+np.exp(-z))

def symbol_cluster(frame,p):
    tmp=frame[["symbol","y"]].copy()
    tmp["p"]=p
    rows=[]
    for sym,g in tmp.groupby("symbol"):
        if len(g)<20 or g["y"].nunique()<2:
            continue
        rows.append({
          "symbol":sym,
          "n":len(g),
          "auc":auc_rank(g["y"].to_numpy(float),g["p"].to_numpy(float)),
          "brier":float(np.mean((g["p"].to_numpy(float)-g["y"].to_numpy(float))**2)),
        })
    if not rows:
        return {"symbols_eligible":0}
    r=pd.DataFrame(rows)
    return {
      "symbols_eligible":int(len(r)),
      "median_symbol_auc":float(r["auc"].median()),
      "fraction_symbol_auc_gt_0_5":float((r["auc"]>0.5).mean()),
      "median_symbol_brier":float(r["brier"].median()),
    }

records=[]; cluster_records=[]
print("=== FROZEN VALIDATION A/B ===")
for part in ["VALIDATION_A","VALIDATION_B"]:
    partdf=df[df["research_partition"].eq(part)].copy()
    partdf=partdf[partdf["frozen_primary_outcome"].isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])].copy()
    partdf["y"]=(partdf["frozen_primary_outcome"]=="FAVORABLE_FIRST").astype(float)
    print(part,"RESOLVED_ROWS =",len(partdf))
    for direction in ["BULL","BEAR"]:
        dd=partdf[partdf["direction"].eq(direction)].copy()
        print(part,direction,"N =",len(dd))
        for arch in ["A0","A1","A2"]:
            spec=freeze["architectures"][f"{direction}_{arch}"]
            p=predict(dd,spec)
            m=metrics(dd["y"].to_numpy(float),p)
            cl=symbol_cluster(dd,p)
            rec={"partition":part,"direction":direction,"architecture":arch,**m}
            records.append(rec)
            cluster_records.append({"partition":part,"direction":direction,"architecture":arch,**cl})
            print(part,direction,arch,json.dumps(m,sort_keys=True),json.dumps(cl,sort_keys=True))

res=pd.DataFrame(records)
clusters=pd.DataFrame(cluster_records)
res.to_csv(OUT/"validation_metrics.csv",index=False)
clusters.to_csv(OUT/"validation_symbol_clusters.csv",index=False)

print("\n=== VALIDATION REPLICATION SUMMARY ===")
for direction in ["BULL","BEAR"]:
  for arch in ["A1","A2"]:
    print(direction,arch)
    for part in ["VALIDATION_A","VALIDATION_B"]:
      r=res[(res.partition==part)&(res.direction==direction)&(res.architecture==arch)].iloc[0]
      b=res[(res.partition==part)&(res.direction==direction)&(res.architecture=="A0")].iloc[0]
      print(" ",part,
        "auc=",round(float(r.auc),6),
        "delta_auc_vs_A0=",round(float(r.auc-b.auc),6),
        "brier=",round(float(r.brier),6),
        "delta_brier_vs_A0=",round(float(r.brier-b.brier),6),
        "spread=",round(float(r.top_minus_bottom),6))

summary={
 "protocol":"PMPD_V5_9K_FROZEN_VALIDATION_V1",
 "matrix_sha256":actual,
 "validation_refit":False,
 "thresholds_fit":False,
 "architecture_changed":False,
 "production_rule_authorized":False,
 "metrics":records,
 "symbol_clusters":cluster_records,
}
(OUT/"validation_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

print("VALIDATION_REFIT=False")
print("THRESHOLDS_FIT=False")
print("ARCHITECTURE_CHANGED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("FROZEN_VALIDATION_GATE=PASS")
