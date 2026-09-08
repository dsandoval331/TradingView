from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
targets=["pm_pd_spacing_pct","a42_priorclose_to_outer_consumed_ratio","vwap_distance_change_pp"]
dirs=[
 ROOT/"ae2_session_level_geometry_v1",
 ROOT/"ae2_opening_location_geometry_v1",
 ROOT/"ae2_preferred_level_timing_v1",
]
print("="*132)
print("A51.2C - FROZEN QUINTILE ASSIGNMENT / CUTPOINT INVENTORY")
print("="*132)
for d in dirs:
    print(f"\nDIRECTORY: {d}")
    for p in sorted(d.glob("*")):
        if p.suffix.lower() not in {".csv",".parquet"}: continue
        try:
            x=pd.read_csv(p) if p.suffix.lower()==".csv" else pd.read_parquet(p)
        except Exception: continue
        cols=list(x.columns)
        hit=[c for c in cols if any(t in c.lower() for t in ["quint","bucket","cut","edge","threshold","bin"])]
        targethit=[c for c in cols if any(t in c.lower() for t in targets)]
        if hit or (targethit and any("research_period"==c for c in cols)):
            print(f"\nFILE: {p.name} rows={len(x):,}")
            print("  TARGET FIELDS:", " | ".join(targethit) if targethit else "(none)")
            print("  ENCODING FIELDS:", " | ".join(hit) if hit else "(none)")
            for c in hit:
                s=x[c].dropna()
                if len(s) and s.nunique()<=30:
                    print(f"    {c}: "+" | ".join(f"{k}={v}" for k,v in s.astype(str).value_counts().head(30).items()))
print("\nRESULT: INVENTORY COMPLETE. No cutpoints recomputed.")
