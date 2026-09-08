from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
D=ROOT/"ae2_c1_c2_transition_v1"
print("="*132)
print("A51.3C - A39 PERSISTED FROZEN CUTPOINT EXTRACTION")
print("="*132)

for p in sorted(D.glob("*")):
    if p.suffix.lower() not in {".csv",".parquet"}: continue
    try:
        x=pd.read_csv(p) if p.suffix.lower()==".csv" else pd.read_parquet(p)
    except Exception: continue
    cols=list(x.columns)
    enc=[c for c in cols if any(t in c.lower() for t in ["edge","cut","threshold","bucket"])]
    vwap=[c for c in cols if "vwap_distance_change_pp" in c.lower()]
    if enc and (vwap or "frozen" in p.name.lower() or "bucket" in p.name.lower()):
        print(f"\nFILE: {p.name} rows={len(x):,} cols={len(cols):,}")
        print("COLUMNS:", " | ".join(cols))
        # small artifacts only: print complete table to preserve exact mapping
        if len(x)<=100:
            print(x.to_string(index=False))
        else:
            print("ENCODING FIELDS:", " | ".join(enc))
            print("VWAP FIELDS:", " | ".join(vwap) if vwap else "(none)")

print("\nRESULT: A39 CUTPOINT EXTRACTION COMPLETE.")
print("No cutpoints recomputed. No outcomes newly analyzed. No prospective data touched.")
