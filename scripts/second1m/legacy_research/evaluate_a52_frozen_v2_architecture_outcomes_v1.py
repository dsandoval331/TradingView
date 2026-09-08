from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
A52=ROOT/"ae2_v2_model_architecture_v1"
STATE=A52/"a52_v2_state_matrix_OUTCOME_FREE_v1.parquet"
SPEC=A52/"ALT_C2_V2_PREDECLARED_ARCHITECTURE_V1.json"
SRC=ROOT/"ae2_preferred_level_timing_v1"/"a38_preferred_level_timing_events_v1.parquet"
OUT=A52/"a52_frozen_architecture_outcome_evaluation_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}
ORDER=["UPGRADE","BASE","CONFLICT","DOWNGRADE"]

def stats(z):
    n=len(z); fav=int(z.outcome.eq("FAVORABLE_FIRST").sum())
    return n,fav,100*fav/n if n else np.nan

def main():
    print("="*136)
    print("A52.2 - FROZEN V2 ARCHITECTURE OUTCOME EVALUATION")
    print("="*136)
    spec=json.loads(SPEC.read_text(encoding="utf-8"))
    print("Frozen architecture:",spec["architecture_id"])
    print("Spec SHA256:",spec["sha256"])

    s=pd.read_parquet(STATE)
    assert len(s)==753 and "outcome" not in s.columns

    y=pd.read_parquet(SRC)
    y=y[y.outcome.isin(BINARY)].copy()
    keys=["symbol","trade_date","direction"]
    y=y[keys+["outcome"]].drop_duplicates(keys)
    x=s.merge(y,on=keys,how="left",validate="one_to_one")
    if x.outcome.isna().any(): raise RuntimeError(f"Missing outcomes after join: {x.outcome.isna().sum()}")
    assert len(x)==753

    rows=[]
    for period,z in [("ALL",x),("DISCOVERY",x[x.research_period.eq("DISCOVERY")]),("VALIDATION",x[x.research_period.eq("VALIDATION")])]:
        bn,bf,br=stats(z)
        for state in ORDER:
            q=z[z.a52_state.eq(state)]
            n,f,r=stats(q)
            rows.append({"period":period,"state":state,"n":n,"favorable_n":f,"ff_pct":r,
                         "period_baseline_n":bn,"period_baseline_ff_pct":br,"lift_vs_baseline_pp":r-br if n else np.nan})
    out=pd.DataFrame(rows)
    out.to_csv(OUT,index=False)

    print("\nFROZEN FOUR-STATE PERFORMANCE")
    print(out.to_string(index=False,float_format=lambda v:f"{v:.2f}"))

    print("\nPREDECLARED ORDERING CHECK: UPGRADE > BASE > DOWNGRADE")
    for period in ["DISCOVERY","VALIDATION","ALL"]:
        z=out[out.period.eq(period)].set_index("state")
        ok=z.loc["UPGRADE","ff_pct"] > z.loc["BASE","ff_pct"] > z.loc["DOWNGRADE","ff_pct"]
        spread=z.loc["UPGRADE","ff_pct"]-z.loc["DOWNGRADE","ff_pct"]
        print(f"{period:10s} ordering={'PASS' if ok else 'FAIL'}  UPGRADE-DOWNGRADE spread={spread:.2f}pp")

    print("\nCONFLICT is reported descriptively only; no post-hoc reassignment.")
    print("Output:",OUT)
    print("\nRESULT: A52.2 FROZEN OUTCOME EVALUATION COMPLETE.")
    print("No thresholds changed. No weights fitted. No prospective data used. Candidate Model V1 unchanged.")

if __name__=="__main__": main()
