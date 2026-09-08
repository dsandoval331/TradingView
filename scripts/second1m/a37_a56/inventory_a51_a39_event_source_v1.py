from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
D=ROOT/"ae2_c1_c2_transition_v1"
print("="*132)
print("A51.3B - A39 EVENT-LEVEL FROZEN SOURCE INVENTORY")
print("="*132)
for p in sorted(D.glob("*")):
    if p.suffix.lower() not in {".csv",".parquet"}: continue
    try:
        x=pd.read_csv(p) if p.suffix.lower()==".csv" else pd.read_parquet(p)
    except Exception as e:
        print("READ ERROR",p.name,e); continue
    cols=list(x.columns)
    exact=[c for c in cols if "vwap_distance_change_pp" in c.lower()]
    keys=[c for c in ["symbol","trade_date","direction","research_period"] if c in cols]
    if exact or (keys and len(x)>=700):
        print(f"\nFILE: {p.name} rows={len(x):,} cols={len(cols):,}")
        print("  KEYS:", " | ".join(keys) if keys else "(none)")
        print("  VWAP FIELDS:", " | ".join(exact) if exact else "(none)")
        for c in exact:
            s=x[c].dropna()
            print(f"    {c}: dtype={s.dtype}, nonnull={len(s):,}, unique={s.nunique():,}")
            if s.nunique()<=20:
                print("      values: "+" | ".join(f"{k}={v}" for k,v in s.astype(str).value_counts().items()))
print("\nRESULT: A39 EVENT-SOURCE INVENTORY COMPLETE. No outcomes analyzed.")
