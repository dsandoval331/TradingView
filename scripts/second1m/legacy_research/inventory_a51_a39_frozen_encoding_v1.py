from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
TOKENS=["vwap_distance_change","vwap","change_pp","transition","quint","bucket","threshold","candidate"]
print("="*132)
print("A51.3A - A39 FROZEN ENCODING INVENTORY")
print("="*132)
for p in sorted(ROOT.rglob("*")):
    if p.suffix.lower() not in {".csv",".parquet"}: continue
    # prioritize A39-ish artifacts or schemas containing exact target token
    if not any(x in str(p).lower() for x in ["transition","a39","vwap"]):
        continue
    try:
        x=pd.read_csv(p) if p.suffix.lower()==".csv" else pd.read_parquet(p)
    except Exception:
        continue
    hit=[c for c in x.columns if any(t in c.lower() for t in TOKENS)]
    if not hit: continue
    print(f"\nFILE: {p} rows={len(x):,} cols={len(x.columns):,}")
    print("  MATCH:", " | ".join(hit))
    for c in hit:
        s=x[c].dropna()
        if len(s) and (s.nunique()<=30 or s.dtype==object):
            vals=s.astype(str).value_counts().head(30)
            print(f"    {c}: "+" | ".join(f"{k}={v}" for k,v in vals.items()))
print("\nRESULT: A39 INVENTORY COMPLETE. No outcomes analyzed; no thresholds recomputed.")
