from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
PRED=ROOT/"ae2_c2_predictors_v1"/"ae2_c2_predictor_features_v1.parquet"
SESS=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OLD=ROOT/"ae2_c1_c2_transition_v1"/"a39_transition_frozen_quintile_performance_v1.csv"
OUT=ROOT/"ae2_v2_evidence_consolidation_v1"/"a51_a39_summary_reproducibility_audit_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}

def ff_summary(df, group_cols):
    z=df[df["outcome"].isin(BINARY)].copy()
    z["ff"]=z["outcome"].eq("FAVORABLE_FIRST").astype(int)
    o=(z.groupby(group_cols,dropna=False,observed=True)
         .agg(binary_n=("ff","size"),favorable_n=("ff","sum")).reset_index())
    o["adverse_n"]=o["binary_n"]-o["favorable_n"]
    o["ff_pct"]=100*o["favorable_n"]/o["binary_n"]
    return o

def main():
    pred=pd.read_parquet(PRED); sess=pd.read_parquet(SESS)
    for d in (pred,sess): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=[k for k in ["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
          if k in pred.columns and k in sess.columns]
    needed=["session_level_clear_state","market_prior_5d_consensus","research_period"]
    pred2=pred.drop(columns=[c for c in needed if c in pred.columns],errors="ignore")
    ss=sess[keys+needed].drop_duplicates(keys)
    df=pred2.merge(ss,on=keys,how="left",validate="one_to_one")
    x=df[df.outcome.isin(BINARY)
         & df.session_level_clear_state.eq("ALL_3_CLEARED")
         & df.market_prior_5d_consensus.eq("CONSENSUS_OPPOSING")].copy()

    b="vwap_distance_change_pp__bucket"
    cats=sorted(x[b].dropna().unique(),key=lambda s: float(str(s).split(",")[0].lstrip("(").lstrip("[")))
    rank={c:i+1 for i,c in enumerate(cats)}
    q="vwap_distance_change_pp__frozen_quintile"
    x[q]=x[b].map(rank).astype("Int64")
    now=ff_summary(x,["research_period",q])
    now["feature"]="vwap_distance_change_pp"

    old=pd.read_csv(OLD)
    old=old[old["feature"].eq("vwap_distance_change_pp")].copy()
    cols=["research_period",q,"binary_n","favorable_n","adverse_n","ff_pct"]
    m=old[cols].merge(now[cols],on=["research_period",q],how="outer",suffixes=("_persisted","_reproduced"))
    for c in ["binary_n","favorable_n","adverse_n","ff_pct"]:
        m[c+"_delta"]=m[c+"_reproduced"]-m[c+"_persisted"]
    OUT.parent.mkdir(parents=True,exist_ok=True); m.to_csv(OUT,index=False)

    print("="*132)
    print("A51.3K - A39 PERSISTED-SUMMARY REPRODUCIBILITY AUDIT")
    print("="*132)
    print(f"Exact Preferred binary population: {len(x)}")
    print("\nPersisted historical A39 summary vs exact rerun from current authoritative artifacts:")
    print(m.to_string(index=False))
    exact=(m.filter(like="_delta").fillna(0).abs().to_numpy()<1e-12).all()
    print("\nEXACT SUMMARY REPRODUCTION:", "PASS" if exact else "FAIL")
    print("Audit CSV:",OUT)
    if not exact:
        print("\nINTERPRETATION: persisted A39 summary is not reproducible from the current authoritative source artifacts")
        print("using the original A39 code path. Treat the old 48/50 candidate evidence as provenance-conflicted;")
        print("do not fit thresholds or alter event assignments to recover it.")
    print("\nNo prospective data touched. No thresholds optimized.")

if __name__=="__main__": main()
