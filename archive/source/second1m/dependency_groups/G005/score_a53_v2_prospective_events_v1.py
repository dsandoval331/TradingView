from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd

V1=Path("data/second1m_alt_entry_prospective_v1/events/altc2_prospective_event_ledger_v1.parquet")
PROTOCOL=Path("data/second1m_alt_entry_prospective_v2/protocol/ALT_C2_PROSPECTIVE_VALIDATION_V2.json")
OUTD=Path("data/second1m_alt_entry_prospective_v2/events"); OUTD.mkdir(parents=True,exist_ok=True)
OUT=OUTD/"altc2_prospective_event_ledger_v2.parquet"
CSV=OUTD/"altc2_prospective_event_ledger_v2.csv"

A37_EDGES=[-np.inf,0.1020628696615283,0.2518676743696417,0.4945934680138955,1.0113381556269037,np.inf]
A42_EDGES=[-np.inf,0.1741358024691308,0.5300536672629688,0.7230447883321438,0.9065349585303464,np.inf]

def beyond(close,level,direction):
    close=pd.to_numeric(close,errors="coerce"); level=pd.to_numeric(level,errors="coerce")
    return np.where(direction.astype(str).str.upper().eq("BULL"),close>level,close<level)

def main():
    proto=json.loads(PROTOCOL.read_text(encoding="utf-8"))
    x=pd.read_parquet(V1).copy()
    x["trade_date"]=pd.to_datetime(x["trade_date"])
    # V1 PREFERRED only, as frozen by the authoritative prospective ledger.
    if "candidate_triage_state" not in x.columns: raise KeyError("candidate_triage_state")
    x=x[x["candidate_triage_state"].astype(str).eq("PREFERRED")].copy()
    print("="*140)
    print("A53.3 - SCORE FROZEN CANDIDATE MODEL V2 ON V1-PREFERRED PROSPECTIVE EVENTS")
    print("="*140)
    print("Protocol hash:",proto["sha256"])
    print("V1 ledger rows:",len(pd.read_parquet(V1))," V1 PREFERRED cohort:",len(x))

    # Require all 3 relevant levels.
    lv=["pm_directional_level","ah_directional_level","pd_directional_level"]
    incomplete=x[lv].isna().any(axis=1)
    if incomplete.any(): raise RuntimeError(f"Incomplete structural levels in {int(incomplete.sum())} V1-PREFERRED rows")

    sign=np.where(x.direction.astype(str).str.upper().eq("BULL"),1.0,-1.0)

    # A37 G-N1: PM-PD absolute spacing as % of entry price, frozen Q4.
    # Historical geometry definition is pairwise absolute price spacing normalized by entry price.
    x["v2_pm_pd_spacing_pct"]=(x.pm_directional_level-x.pd_directional_level).abs()/pd.to_numeric(x.entry_price)*100.0
    x["v2_a37_spacing_q"]=pd.cut(x.v2_pm_pd_spacing_pct,A37_EDGES,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)
    x["A37_G_N1_PM_PD_SPACING_Q4"]=x.v2_a37_spacing_q.astype("object").eq("Q4")

    # A37 G-P2: directional inner->outer ordering. Smaller directional distance from entry = inner.
    # Sort levels by sign*(level-entry); exact frozen target PD>AH>PM.
    def order(r):
        s=1.0 if str(r.direction).upper()=="BULL" else -1.0
        vals={"PM":s*(r.pm_directional_level-r.entry_price),
              "AH":s*(r.ah_directional_level-r.entry_price),
              "PD":s*(r.pd_directional_level-r.entry_price)}
        return ">".join(k for k,v in sorted(vals.items(),key=lambda kv:kv[1]))
    x["v2_directional_level_order_inner_to_outer"]=x.apply(order,axis=1)
    x["A37_G_P2_PD_AH_PM_ORDERING"]=x.v2_directional_level_order_inner_to_outer.eq("PD>AH>PM")

    # A38: exact historical definition = C1 CLOSE beyond each directional level.
    x["v2_c1_pm_beyond"]=beyond(x.c1_close,x.pm_directional_level,x.direction)
    x["v2_c1_ah_beyond"]=beyond(x.c1_close,x.ah_directional_level,x.direction)
    x["v2_c1_pd_beyond"]=beyond(x.c1_close,x.pd_directional_level,x.direction)
    x["A38_T_P1_PM_REMAINS_FOR_C2"]=(x.v2_c1_ah_beyond & x.v2_c1_pd_beyond & ~x.v2_c1_pm_beyond)
    x["A38_T_N1_PD_REMAINS_FOR_C2"]=(x.v2_c1_pm_beyond & x.v2_c1_ah_beyond & ~x.v2_c1_pd_beyond)

    # A42: exact historical consumed-ratio formula.
    dn=pd.DataFrame({
        "PM":sign*(x.pm_directional_level-x.c1_open),
        "AH":sign*(x.ah_directional_level-x.c1_open),
        "PD":sign*(x.pd_directional_level-x.c1_open)},index=x.index)
    outer=dn.idxmax(axis=1)
    outer_price=np.select([outer.eq("PM"),outer.eq("AH"),outer.eq("PD")],
                          [x.pm_directional_level,x.ah_directional_level,x.pd_directional_level],default=np.nan)
    denom=sign*(outer_price-x.prior_rth_close)
    numer=sign*(x.c1_open-x.prior_rth_close)
    x["v2_a42_priorclose_to_outer_consumed_ratio"]=np.where(np.abs(denom)>1e-12,numer/denom,np.nan)
    x["v2_a42_consumed_q"]=pd.cut(x.v2_a42_priorclose_to_outer_consumed_ratio,A42_EDGES,
                                  labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)
    x["A42_N2_OPEN_CONSUMED_RATIO_Q2"]=x.v2_a42_consumed_q.astype("object").eq("Q2")

    pos=["A37_G_P2_PD_AH_PM_ORDERING","A38_T_P1_PM_REMAINS_FOR_C2"]
    neg=["A37_G_N1_PM_PD_SPACING_Q4","A38_T_N1_PD_REMAINS_FOR_C2","A42_N2_OPEN_CONSUMED_RATIO_Q2"]
    x["v2_positive_count"]=x[pos].astype(int).sum(axis=1)
    x["v2_negative_count"]=x[neg].astype(int).sum(axis=1)
    p=x.v2_positive_count.gt(0); n=x.v2_negative_count.gt(0)
    x["v2_state"]=np.select([p&~n,n&~p,p&n],["UPGRADE","DOWNGRADE","CONFLICT"],default="BASE")
    x["v2_candidate_model_id"]=proto["candidate_model_id"]
    x["v2_protocol_id"]=proto["protocol_id"]
    x["v2_protocol_sha256"]=proto["sha256"]

    # Stable V2 event ID based on V1 event id when available.
    if "event_id" in x.columns:
        x["v2_event_id"]=x.event_id.astype(str).map(lambda s:hashlib.sha256(("V2|"+s).encode()).hexdigest())
    else:
        x["v2_event_id"]=x.apply(lambda r:hashlib.sha256(
            f"V2|{r.symbol}|{r.trade_date.date()}|{r.direction}|{r.entry_timestamp}".encode()).hexdigest(),axis=1)

    # Write separate V2 ledger. V1 is read-only.
    x.to_parquet(OUT,index=False); x.to_csv(CSV,index=False)

    print("\nV2 STATE COUNTS (OUTCOME-BLIND)")
    print(x.v2_state.value_counts(dropna=False).to_string())
    print("\nCandidate firing counts:")
    for c in pos+neg: print(f"{c:44s} {int(x[c].sum())}")
    print("\nA38 reconstructed C1 patterns:")
    def pat(r):
        a=[]
        if r.v2_c1_pm_beyond:a.append("PM")
        if r.v2_c1_ah_beyond:a.append("AH")
        if r.v2_c1_pd_beyond:a.append("PD")
        return "+".join(a) if a else "NONE"
    print(x.apply(pat,axis=1).value_counts().to_string())
    print("\nV2 ledger:",OUT)
    print("RESULT: A53.3 V2 PROSPECTIVE SCORING COMPLETE.")
    print("No outcome rates analyzed. V1 ledger not modified.")

if __name__=="__main__": main()
