from pathlib import Path
import pandas as pd

V1=Path("data/second1m_alt_entry_prospective_v1")
WORK=Path("data/second1m_alt_entry_prospective_work_v1")

NEEDED={
"A37 geometry":["pm_directional_level","pd_directional_level","ah_directional_level"],
"A38 timing":["c1_cleared_pattern"],
"A42 opening location":["prior_rth_close","c1_open"],
"V1 cohort/outcome":["candidate_state","outcome","symbol","trade_date","direction"]
}

def cols_of(p):
    try:
        if p.suffix.lower()==".parquet":
            return list(pd.read_parquet(p).columns)
        if p.suffix.lower()==".csv":
            return list(pd.read_csv(p,nrows=0).columns)
    except Exception as e:
        return [f"<READ_ERROR:{e}>"]
    return []

def main():
    files=[]
    for root in [V1,WORK]:
        if root.exists():
            files += list(root.rglob("*.parquet")) + list(root.rglob("*.csv"))
    print("="*140)
    print("A53.2 - V2 PROSPECTIVE SCORING SOURCE INVENTORY")
    print("="*140)
    print("Files scanned:",len(files))
    hits={k:[] for k in NEEDED}
    for f in files:
        c=cols_of(f); cs=set(c)
        matched=False
        for fam,need in NEEDED.items():
            present=[x for x in need if x in cs]
            if present:
                hits[fam].append((str(f),len(c),present))
                matched=True
    for fam,items in hits.items():
        print("\n"+fam)
        print("-"*110)
        need=NEEDED[fam]
        print("Needed:",", ".join(need))
        for f,n,present in items:
            print(f"{f} | cols={n} | present={','.join(present)}")

    print("\nEXACT / NEAR-NAME SEARCH")
    tokens=["pm","pdh","pdl","ah","prior_rth_close","c1_open","cleared_pattern",
            "directional_level","candidate","outcome"]
    for f in files:
        c=cols_of(f)
        near=[x for x in c if any(t.lower() in x.lower() for t in tokens)]
        if near:
            print("\nFILE:",f)
            print("  "+", ".join(near[:120]))

    print("\nRESULT: INVENTORY COMPLETE. No scoring performed; no prospective outcomes analyzed.")

if __name__=="__main__": main()
