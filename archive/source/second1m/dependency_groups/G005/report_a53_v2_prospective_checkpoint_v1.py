from pathlib import Path
import json
import pandas as pd
import numpy as np

P=Path("data/second1m_alt_entry_prospective_v2/protocol/ALT_C2_PROSPECTIVE_VALIDATION_V2.json")
L=Path("data/second1m_alt_entry_prospective_v2/events/altc2_prospective_event_ledger_v2.parquet")
R=Path("data/second1m_alt_entry_prospective_v2/reports"); R.mkdir(parents=True,exist_ok=True)
OUT=R/"altc2_prospective_status_v2.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}
STATES=["UPGRADE","BASE","CONFLICT","DOWNGRADE"]

def main():
    proto=json.loads(P.read_text(encoding="utf-8"))
    x=pd.read_parquet(L)
    b=x[x.outcome.isin(BINARY)].copy()

    rows=[]
    for s in STATES:
        z=x[x.v2_state.eq(s)]; q=b[b.v2_state.eq(s)]
        ff=int(q.outcome.eq("FAVORABLE_FIRST").sum())
        af=int(q.outcome.eq("ADVERSE_FIRST").sum())
        rows.append({"state":s,"total_n":len(z),"binary_n":len(q),"ff_n":ff,"af_n":af,
                     "ff_pct":100*ff/len(q) if len(q) else np.nan,
                     "minimum_binary_n":proto["minimum_binary_samples"][s],
                     "remaining_to_minimum":max(0,proto["minimum_binary_samples"][s]-len(q))})
    out=pd.DataFrame(rows); out.to_csv(OUT,index=False)

    print("="*132)
    print("A53.4 - CANDIDATE MODEL V2 PROSPECTIVE CHECKPOINT REPORT")
    print("="*132)
    print("Protocol:",proto["protocol_id"])
    print("Protocol hash:",proto["sha256"])
    print("V2 cohort total:",len(x),"binary:",len(b))
    print("\nSTATE STATUS")
    print(out.to_string(index=False,float_format=lambda v:f"{v:.2f}"))

    print("\nDIRECTION STATUS (descriptive; formal directional minimum=40 per state-direction cell)")
    for d in ["BULL","BEAR"]:
        print("\n",d)
        for s in STATES:
            q=b[(b.direction.astype(str).str.upper()==d)&b.v2_state.eq(s)]
            ff=int(q.outcome.eq("FAVORABLE_FIRST").sum())
            pct=100*ff/len(q) if len(q) else np.nan
            print(f"{s:10s} N={len(q):3d} FF={ff:3d} FF%={pct:6.2f}" if len(q) else f"{s:10s} N=  0 FF%=N/A")

    print("\nCHECKPOINT POLICY: descriptive only; no early stopping; no model changes.")
    print("Minimums:",proto["minimum_binary_samples"])
    print("Output:",OUT)
    print("RESULT: A53.4 REPORT COMPLETE. Candidate V1 unchanged.")

if __name__=="__main__": main()
