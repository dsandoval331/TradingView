from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd

ROOT=Path.cwd()
CAND=ROOT/"pmpd_v5_9m_oos_candidate_dp4_v1.parquet"
MAN=ROOT/"pmpd_v5_9m_oos_candidate_dp4_v1_manifest.json"
PROTOCOL=ROOT/"PMPD_V5_9M_OOS_PROTOCOL_V1.json"
OUT_JSON=ROOT/"pmpd_v5_9m_oos_results_v1.json"
OUT_MONTH=ROOT/"pmpd_v5_9m_oos_monthly_v1.csv"
OUT_SYMBOL=ROOT/"pmpd_v5_9m_oos_symbol_v1.csv"

EXPECTED_SHA="6006b19ae706f02ffced95ba0bef463d10171e90e75e2de8acf08f44540e6035"
EXPECTED_CAND="PMPD_V5_CANDIDATE_DP4_UNSCORED_V1"
EXPECTED_PROTOCOL="PMPD_V5_9M_OOS_PROTOCOL_V1"
SEED=9052026
REPS=10000
TEST_VALUE=0.50

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rate_summary(x):
    vc=x["outcome"].value_counts(dropna=False).to_dict()
    fav=int(vc.get("FAVORABLE_FIRST",0))
    adv=int(vc.get("ADVERSE_FIRST",0))
    unr=int(vc.get("UNRESOLVED",0))
    amb=int(vc.get("AMBIGUOUS_SAME_BAR",0))
    resolved=fav+adv
    rate=fav/resolved if resolved else float("nan")
    return {"rows":int(len(x)),"favorable_first":fav,"adverse_first":adv,
            "unresolved":unr,"ambiguous_same_bar":amb,"resolved":resolved,
            "favorable_first_rate":rate}

def symbol_cluster_bootstrap(x, reps=10000, seed=9052026):
    z=x[x["outcome"].isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])].copy()
    z["y"]=(z["outcome"]=="FAVORABLE_FIRST").astype(int)
    by={}
    for sym,g in z.groupby("symbol"):
        by[sym]=(int(g["y"].sum()),int(len(g)))
    syms=np.array(sorted(by),dtype=object)
    fav=np.array([by[s][0] for s in syms],dtype=float)
    n=np.array([by[s][1] for s in syms],dtype=float)
    rng=np.random.default_rng(seed)
    vals=np.empty(reps,dtype=float)
    k=len(syms)
    for i in range(reps):
        idx=rng.integers(0,k,size=k)
        den=n[idx].sum()
        vals[i]=fav[idx].sum()/den if den else np.nan
    vals=vals[np.isfinite(vals)]
    return {
        "replicates":int(len(vals)),
        "seed":seed,
        "lower_95":float(np.quantile(vals,0.025)),
        "median":float(np.quantile(vals,0.5)),
        "upper_95":float(np.quantile(vals,0.975))
    }

print("=== PMPD V5 9M-9 FROZEN OOS EVALUATION ===")

assert CAND.exists(), f"Missing {CAND}"
assert MAN.exists(), f"Missing {MAN}"
assert PROTOCOL.exists(), f"Missing {PROTOCOL}"
actual_sha=sha256(CAND)
print("CANDIDATE_SHA256 =",actual_sha)
assert actual_sha==EXPECTED_SHA, "Candidate artifact hash mismatch"

man=json.loads(MAN.read_text(encoding="utf-8"))
proto=json.loads(PROTOCOL.read_text(encoding="utf-8"))
assert man["candidate_code"]==EXPECTED_CAND
assert man["oos_protocol_id"]==EXPECTED_PROTOCOL
assert proto["protocol_id"]==EXPECTED_PROTOCOL
assert proto["candidate_code"]==EXPECTED_CAND

df=pd.read_parquet(CAND)
assert len(df)==16138, f"Unexpected candidate rows: {len(df)}"
assert set(df["decision_type"].dropna().unique())=={"DP4_FULL_STACK_FIRST_CLEAR"}
assert df["primary_decision_unit"].eq(True).all()
assert df["primary_inference_eligible"].eq(True).all()
assert df["price_scale_severe_flag"].eq(False).all()

print("CANDIDATE_ROWS =",len(df))
print("DIRECTION_COUNTS =",df["direction"].value_counts().to_dict())
print("OUTCOME_COUNTS =",df["outcome"].value_counts(dropna=False).to_dict())

combined=rate_summary(df)
bull=rate_summary(df[df["direction"].eq("BULL")])
bear=rate_summary(df[df["direction"].eq("BEAR")])
boot=symbol_cluster_bootstrap(df,REPS,SEED)

# Monthly robustness.
m=df.copy()
m["month"]=pd.to_datetime(m["trade_date"]).dt.to_period("M").astype(str)
monthly=[]
for month,g in m.groupby("month",sort=True):
    s=rate_summary(g); s["month"]=month
    monthly.append(s)
monthly_df=pd.DataFrame(monthly)
monthly_df.to_csv(OUT_MONTH,index=False)

# Per-symbol robustness.
symrows=[]
for sym,g in df.groupby("symbol",sort=True):
    s=rate_summary(g); s["symbol"]=sym
    symrows.append(s)
symbol_df=pd.DataFrame(symrows)
symbol_df.to_csv(OUT_SYMBOL,index=False)
eligible_symbol_rates=symbol_df.loc[symbol_df["resolved"]>0,"favorable_first_rate"]
frac_symbols_gt_50=float((eligible_symbol_rates>0.50).mean()) if len(eligible_symbol_rates) else float("nan")

# Frozen classification.
combined_rate=combined["favorable_first_rate"]
lower=boot["lower_95"]
bull_rate=bull["favorable_first_rate"]
bear_rate=bear["favorable_first_rate"]

if combined_rate <= TEST_VALUE:
    classification="NOT_SUPPORTED"
elif lower > TEST_VALUE and bull_rate > TEST_VALUE and bear_rate > TEST_VALUE:
    classification="SUPPORTED"
else:
    classification="CONDITIONAL"

result={
    "protocol_id":EXPECTED_PROTOCOL,
    "candidate_code":EXPECTED_CAND,
    "candidate_sha256":actual_sha,
    "candidate_rows":int(len(df)),
    "combined":combined,
    "bull":bull,
    "bear":bear,
    "symbol_cluster_bootstrap_95":boot,
    "test_value":TEST_VALUE,
    "fraction_symbols_favorable_rate_gt_0_50":frac_symbols_gt_50,
    "symbols_with_resolved_events":int((symbol_df["resolved"]>0).sum()),
    "months_reported":int(len(monthly_df)),
    "frozen_classification":classification,
    "candidate_modified":False,
    "threshold_tuning":False,
    "score_fitting":False,
    "validation_refit":False,
    "production_rule_authorized":False
}
OUT_JSON.write_text(json.dumps(result,indent=2,default=str),encoding="utf-8")

print("\n=== PRIMARY OOS RESULT ===")
print("COMBINED =",combined)
print("BULL =",bull)
print("BEAR =",bear)
print("SYMBOL_CLUSTER_BOOTSTRAP_95 =",boot)
print("FRACTION_SYMBOLS_GT_0_50 =",frac_symbols_gt_50)
print("FROZEN_CLASSIFICATION =",classification)

print("\n=== MONTHLY ROBUSTNESS ===")
print(monthly_df[["month","rows","resolved","favorable_first_rate","unresolved","ambiguous_same_bar"]].to_string(index=False))

print("\nOUTPUT_JSON =",OUT_JSON)
print("OUTPUT_MONTHLY =",OUT_MONTH)
print("OUTPUT_SYMBOL =",OUT_SYMBOL)
print("CANDIDATE_MODIFIED=False")
print("THRESHOLD_TUNING=False")
print("SCORE_FITTING=False")
print("VALIDATION_REFIT=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9M_FROZEN_OOS_EVALUATION_GATE=PASS")
