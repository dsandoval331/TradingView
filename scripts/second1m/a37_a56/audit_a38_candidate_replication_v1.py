from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

SRC = Path("data/second1m_alt_entry_research_v1/ae2_preferred_level_timing_v1/a38_preferred_level_timing_events_v1.parquet")
OUTDIR = SRC.parent
BINARY = {"FAVORABLE_FIRST", "ADVERSE_FIRST"}

def stats(x):
    x=x[x["outcome"].isin(BINARY)]
    n=len(x); fav=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n, fav, (100.0*fav/n if n else np.nan)

def main():
    e=pd.read_parquet(SRC)
    e=e[e["outcome"].isin(BINARY)].copy()
    e["trade_date"]=pd.to_datetime(e["trade_date"])
    e["quarter"]=e["trade_date"].dt.to_period("Q").astype(str)

    # Predeclared A38 states only; no new threshold search.
    e["A38_P_PM_REMAINS"] = e["c1_levels_cleared_n"].eq(2) & e["c1_cleared_pattern"].eq("AH+PD")
    e["A38_N_PD_REMAINS"] = e["c1_levels_cleared_n"].eq(2) & e["c1_cleared_pattern"].eq("PM+AH")
    e["A38_N_HEAVY_BURDEN"] = e["levels_newly_cleared_by_c2_n"].eq(3)

    candidates=["A38_P_PM_REMAINS","A38_N_PD_REMAINS","A38_N_HEAVY_BURDEN"]
    rows=[]
    for cand in candidates:
        for period in ["DISCOVERY","VALIDATION"]:
            p=e[e["research_period"].eq(period)]
            bn,bf,br=stats(p)
            h=p[p[cand]]
            n,f,r=stats(h)
            rows.append([cand,period,"POOLED","ALL",n,r,bn,br,r-br if n else np.nan])
            for direction, d in p.groupby("direction"):
                dbn,dbf,dbr=stats(d); dh=d[d[cand]]
                dn,df,dr=stats(dh)
                rows.append([cand,period,"DIRECTION",direction,dn,dr,dbn,dbr,dr-dbr if dn else np.nan])

    # Quarter stress against each quarter's Preferred baseline.
    for cand in candidates:
        for quarter, q in e.groupby("quarter"):
            qn,qf,qr=stats(q); h=q[q[cand]]
            n,f,r=stats(h)
            if n >= 8:
                rows.append([cand,quarter,"QUARTER",quarter,n,r,qn,qr,r-qr])

    out=pd.DataFrame(rows,columns=[
        "candidate","period_or_quarter","split_type","split_value",
        "candidate_n","candidate_ff_pct","baseline_n","baseline_ff_pct","lift_pp"
    ])
    out.to_csv(OUTDIR/"a38_candidate_replication_audit_v1.csv",index=False)

    print("="*112)
    print("A38.3 - REMAINING-LEVEL / HEAVY-BURDEN REPLICATION AUDIT")
    print("="*112)
    print("\nDISCOVERY / VALIDATION POOLED")
    print("-"*112)
    print(out[out["split_type"].eq("POOLED")].to_string(index=False,float_format=lambda x:f"{x:.2f}"))
    print("\nDIRECTION STRESS")
    print("-"*112)
    print(out[out["split_type"].eq("DIRECTION")].to_string(index=False,float_format=lambda x:f"{x:.2f}"))
    print("\nQUARTER STRESS (candidate N >= 8)")
    print("-"*112)
    q=out[out["split_type"].eq("QUARTER")]
    print(q.to_string(index=False,float_format=lambda x:f"{x:.2f}") if len(q) else "NONE")
    print(f"\nFull output: {OUTDIR/'a38_candidate_replication_audit_v1.csv'}")
    print("RESULT: A38 REPLICATION AUDIT COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__":
    main()
