from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
DIRS=[
 ROOT/"ae2_session_level_geometry_v1",
 ROOT/"ae2_preferred_level_timing_v1",
 ROOT/"ae2_opening_location_geometry_v1",
]
TOKENS=["spacing","order","ordering","remain","vwap","change","consum","quint","bucket","threshold","state","candidate","retained"]

print("="*132)
print("A51.2A - FROZEN CANDIDATE ENCODING INVENTORY")
print("="*132)
for d in DIRS:
    print(f"\nDIRECTORY: {d}")
    if not d.exists():
        print("  MISSING DIRECTORY"); continue
    for p in sorted(d.iterdir()):
        if p.suffix.lower() not in {".csv",".parquet"}: continue
        try:
            x=pd.read_csv(p,nrows=5) if p.suffix.lower()==".csv" else pd.read_parquet(p)
        except Exception as e:
            print(f"  READ ERROR {p.name}: {e}"); continue
        matches=[c for c in x.columns if any(t in c.lower() for t in TOKENS)]
        if matches:
            print(f"\n  FILE: {p.name}  rows={len(x):,} cols={len(x.columns):,}")
            for c in matches:
                print(f"    {c}")
                s=x[c].dropna()
                if len(s) and (s.dtype==object or str(s.dtype).startswith("category") or s.nunique()<=20):
                    vals=s.astype(str).value_counts().head(15)
                    print("      values: "+" | ".join(f"{k}={v}" for k,v in vals.items()))
print("\nRESULT: INVENTORY COMPLETE. No outcomes analyzed; no thresholds recomputed.")
