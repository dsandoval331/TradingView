from pathlib import Path
import json, math, hashlib
import numpy as np
import pandas as pd

ROOT=Path.cwd()
MATRIX=ROOT/"pmpd_v5_9k_dp4_candidate_matrix_v1"/"dp4_candidate_matrix_v1.csv"
OUT=ROOT/"pmpd_v5_9k_classifier_discovery_v1"
OUT.mkdir(exist_ok=True)

EXPECTED_SHA="6ec9da73cf554469083d35b8866222ae8c66295562bba22557b5b77bfc9d0e57"
actual=hashlib.sha256(MATRIX.read_bytes()).hexdigest()
print("MATRIX_SHA256 =",actual)
assert actual==EXPECTED_SHA, f"Matrix fingerprint mismatch: {actual}"

A1=["six_level_scale_ratio","direction_normalized_overnight_gap_pct","decision_minutes_from_rth_open"]
A2=A1+[
    "directional_vwap_distance_pct",
    "event_minutes_since_last_cross",
    "event_minutes_since_last_touch",
    "event_vwap_touch_count_from_dp1",
    "event_vwap_touch_from_dp1",
]
ARCH={"A0":[],"A1":A1,"A2":A2}

df=pd.read_csv(MATRIX,low_memory=False)
d=df[df["research_partition"].eq("DISCOVERY")].copy()
d=d[d["frozen_primary_outcome"].isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])].copy()
d["y"]=(d["frozen_primary_outcome"]=="FAVORABLE_FIRST").astype(float)

def auc_rank(y,p):
    y=np.asarray(y,dtype=float); p=np.asarray(p,dtype=float)
    n1=int(y.sum()); n0=len(y)-n1
    if n1==0 or n0==0: return float("nan")
    ranks=pd.Series(p).rank(method="average").to_numpy()
    return float((ranks[y==1].sum()-n1*(n1+1)/2)/(n1*n0))

def metrics(y,p):
    eps=1e-12
    p=np.clip(np.asarray(p,float),eps,1-eps)
    y=np.asarray(y,float)
    q20=np.quantile(p,0.2); q80=np.quantile(p,0.8)
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

def prep_fit(frame,features):
    meta={}
    X=[]
    for c in features:
        s=pd.to_numeric(frame[c],errors="coerce").astype(float)
        med=float(s.median())
        q1=float(s.quantile(.25)); q3=float(s.quantile(.75)); iqr=q3-q1
        if not np.isfinite(iqr) or abs(iqr)<1e-12: iqr=1.0
        vals=s.fillna(med).to_numpy(float)
        X.append((vals-med)/iqr)
        meta[c]={"median":med,"q1":q1,"q3":q3,"iqr":float(iqr),"missing_n":int(s.isna().sum())}
    return (np.column_stack(X) if X else np.empty((len(frame),0))),meta

def fit_logit(X,y,max_iter=100):
    n=len(y)
    X1=np.column_stack([np.ones(n),X])
    beta=np.zeros(X1.shape[1],float)
    # tiny fixed numerical ridge; intercept unpenalized.
    ridge=np.eye(X1.shape[1])*1e-8; ridge[0,0]=0
    for _ in range(max_iter):
        z=np.clip(X1@beta,-30,30)
        p=1/(1+np.exp(-z))
        w=np.clip(p*(1-p),1e-8,None)
        g=X1.T@(y-p)-ridge@beta
        H=-(X1.T@(X1*w[:,None]))-ridge
        step=np.linalg.solve(H,g)
        beta_new=beta-step
        if np.max(np.abs(beta_new-beta))<1e-10:
            beta=beta_new; break
        beta=beta_new
    p=1/(1+np.exp(-np.clip(X1@beta,-30,30)))
    return beta,p

results=[]
freeze={"protocol":"PMPD_V5_9K_CLASSIFIER_PREREG_V1","matrix_sha256":actual,
        "partition_fit":"DISCOVERY_ONLY","validation_refit_allowed":False,
        "architectures":{}}

print("DISCOVERY_RESOLVED_ROWS =",len(d))
print("DISCOVERY_DIRECTION_COUNTS =",d["direction"].value_counts().to_dict())

for direction in ["BULL","BEAR"]:
    dd=d[d["direction"].eq(direction)].copy()
    y=dd["y"].to_numpy(float)
    for name,features in ARCH.items():
        X,prep=prep_fit(dd,features)
        beta,p=fit_logit(X,y)
        m=metrics(y,p)
        rec={"direction":direction,"architecture":name,**m}
        results.append(rec)
        freeze["architectures"][f"{direction}_{name}"]={
            "features":features,
            "preprocessing":prep,
            "coefficients":{"intercept":float(beta[0]),**{c:float(beta[i+1]) for i,c in enumerate(features)}},
            "discovery_metrics":m,
        }
        print(direction,name,json.dumps(m,sort_keys=True))

res=pd.DataFrame(results)
res.to_csv(OUT/"discovery_architecture_metrics.csv",index=False)
(OUT/"discovery_model_freeze.json").write_text(json.dumps(freeze,indent=2),encoding="utf-8")

print("\n=== INCREMENTAL DISCOVERY SUMMARY ===")
for direction in ["BULL","BEAR"]:
    z=res[res.direction.eq(direction)].set_index("architecture")
    for a,b in [("A0","A1"),("A1","A2")]:
        print(direction,f"{a}->{b}",
              "delta_auc=",round(float(z.loc[b,"auc"]-z.loc[a,"auc"]),6),
              "delta_brier=",round(float(z.loc[b,"brier"]-z.loc[a,"brier"]),6),
              "delta_spread=",round(float(z.loc[b,"top_minus_bottom"]-z.loc[a,"top_minus_bottom"]),6))

print("VALIDATION_OUTCOMES_USED=False")
print("VALIDATION_REFIT=False")
print("THRESHOLDS_FIT=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("DISCOVERY_MODEL_FIT_GATE=PASS")
