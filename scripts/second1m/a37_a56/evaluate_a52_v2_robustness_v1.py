from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
A52=ROOT/"ae2_v2_model_architecture_v1"
STATE=A52/"a52_v2_state_matrix_OUTCOME_FREE_v1.parquet"
SRC=ROOT/"ae2_preferred_level_timing_v1"/"a38_preferred_level_timing_events_v1.parquet"
OUT=A52/"a52_v2_robustness_direction_quarter_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}
STATES=["UPGRADE","BASE","CONFLICT","DOWNGRADE"]

def st(z):
    n=len(z); f=int(z.outcome.eq("FAVORABLE_FIRST").sum())
    return n,100*f/n if n else np.nan

def main():
    s=pd.read_parquet(STATE); assert len(s)==753 and "outcome" not in s.columns
    y=pd.read_parquet(SRC)
    y=y[y.outcome.isin(BINARY)][["symbol","trade_date","direction","outcome"]].drop_duplicates(["symbol","trade_date","direction"])
    x=s.merge(y,on=["symbol","trade_date","direction"],how="left",validate="one_to_one")
    assert len(x)==753 and x.outcome.notna().all()

    rows=[]
    for dim in ["direction","quarter","research_period"]:
        for val,z in x.groupby(dim):
            bn,br=st(z)
            for state in STATES:
                q=z[z.a52_state.eq(state)]
                n,r=st(q)
                rows.append({"dimension":dim.upper(),"value":str(val),"state":state,
                             "n":n,"ff_pct":r,"group_baseline_n":bn,"group_baseline_ff_pct":br,
                             "lift_pp":r-br if n else np.nan})
    o=pd.DataFrame(rows); o.to_csv(OUT,index=False)

    print("="*136)
    print("A52.3 - FROZEN V2 ROBUSTNESS: DIRECTION / QUARTER / PERIOD")
    print("="*136)
    for dim in ["DIRECTION","QUARTER"]:
        print("\n"+dim)
        print("-"*110)
        z=o[o.dimension.eq(dim)]
        print(z.to_string(index=False,float_format=lambda v:f"{v:.2f}"))

    print("\nORDERING CHECKS (UPGRADE > BASE > DOWNGRADE)")
    for dim in ["DIRECTION","QUARTER","RESEARCH_PERIOD"]:
        for val,z in o[o.dimension.eq(dim)].groupby("value"):
            q=z.set_index("state")
            vals=[q.loc[s,"ff_pct"] for s in ["UPGRADE","BASE","DOWNGRADE"]]
            ok=all(pd.notna(vals)) and vals[0]>vals[1]>vals[2]
            spread=vals[0]-vals[2] if all(pd.notna(vals)) else np.nan
            print(f"{dim:15s} {val:12s} {'PASS' if ok else 'FAIL':4s} spread={spread:7.2f}pp "
                  f"N(up/base/down)={int(q.loc['UPGRADE','n'])}/{int(q.loc['BASE','n'])}/{int(q.loc['DOWNGRADE','n'])}")

    print("\nCONFLICT remains descriptive; no reassignment.")
    print("Output:",OUT)
    print("RESULT: A52.3 ROBUSTNESS AUDIT COMPLETE.")
    print("No thresholds changed. No weights fitted. No prospective data used. Candidate Model V1 unchanged.")

if __name__=="__main__": main()
