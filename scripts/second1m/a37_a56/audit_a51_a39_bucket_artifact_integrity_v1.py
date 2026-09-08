from pathlib import Path
import pandas as pd
import sys
try: sys.stdout.reconfigure(encoding="utf-8",errors="backslashreplace")
except Exception: pass

ROOT=Path("data/second1m_alt_entry_research_v1")
PRED=ROOT/"ae2_c2_predictors_v1"/"ae2_c2_predictor_features_v1.parquet"
SESS=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
print("="*132)
print("A51.3J - A39 UPSTREAM BUCKET ARTIFACT INTEGRITY AUDIT")
print("="*132)

pred=pd.read_parquet(PRED)
sess=pd.read_parquet(SESS)
for d in (pred,sess):
    d["trade_date"]=pd.to_datetime(d["trade_date"])

b="vwap_distance_change_pp__bucket"
print(f"Predictor rows={len(pred):,}; bucket column present={b in pred.columns}")
if b in pred.columns:
    print("Predictor bucket dtype:",pred[b].dtype)
    print("Predictor bucket nonnull:",int(pred[b].notna().sum()))
    print("Predictor bucket unique values/counts:")
    print(pred[b].value_counts(dropna=False).to_string())

# Reproduce exact A39 v1.2 join/filter, but inspect bucket artifact only; no outcome rates.
keys=[k for k in ["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
      if k in pred.columns and k in sess.columns]
needed=["session_level_clear_state","market_prior_5d_consensus","research_period"]
pred2=pred.drop(columns=[c for c in needed if c in pred.columns],errors="ignore")
ss=sess[keys+needed].drop_duplicates(keys)
df=pred2.merge(ss,on=keys,how="left",validate="one_to_one")
binary={"FAVORABLE_FIRST","ADVERSE_FIRST"}
x=df[df["outcome"].isin(binary)
     & df["session_level_clear_state"].eq("ALL_3_CLEARED")
     & df["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")].copy()
print(f"\nExact A39 Preferred binary population={len(x):,}")
if b in x.columns:
    print("Preferred bucket nonnull:",int(x[b].notna().sum()))
    print("Preferred bucket counts:")
    print(x[b].value_counts(dropna=False).to_string())

# Compare current persisted bucket strings to fresh qcut strings event-by-event.
fresh=pd.qcut(pd.to_numeric(pred["vwap_distance_change_pp"],errors="coerce"),q=5,duplicates="drop")
freshs=fresh.astype(str).replace("nan",pd.NA)
if b in pred.columns:
    cur=pred[b].astype("string")
    fs=pd.Series(freshs,index=pred.index,dtype="string")
    both=cur.notna() & fs.notna()
    print("\nCurrent persisted vs fresh qcut:")
    print("both nonnull:",int(both.sum()))
    print("exact string matches:",int((cur[both]==fs[both]).sum()))
    print("mismatches:",int((cur[both]!=fs[both]).sum()))
    if (cur[both]!=fs[both]).any():
        z=pred.loc[both & cur.ne(fs),["symbol","trade_date","direction","vwap_distance_change_pp"]].copy()
        z["persisted_bucket"]=cur[both & cur.ne(fs)]
        z["fresh_qcut_bucket"]=fs[both & cur.ne(fs)]
        print("\nFirst 30 mismatches:")
        print(z.head(30).to_string(index=False))

print("\nRESULT: ARTIFACT INTEGRITY AUDIT COMPLETE.")
print("No thresholds fitted. No prospective data touched.")
