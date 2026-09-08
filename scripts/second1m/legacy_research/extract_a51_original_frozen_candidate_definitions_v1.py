from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
FILES=[
 ROOT/"ae2_session_level_geometry_v1"/"a37_preferred_discovery_quintile_performance_v1.csv",
 ROOT/"ae2_session_level_geometry_v1"/"a37_geometry_replication_audit_v1.csv",
 ROOT/"ae2_session_level_geometry_v1"/"a37_preferred_level_order_performance_v1.csv",
 ROOT/"ae2_preferred_level_timing_v1"/"a38_candidate_replication_audit_v1.csv",
 ROOT/"ae2_preferred_level_timing_v1"/"a38_remaining_level_performance_v1.csv",
 ROOT/"ae2_preferred_level_timing_v1"/"a38_preferred_level_timing_events_v1.parquet",
 ROOT/"ae2_opening_location_geometry_v1"/"a42_predeclared_quintile_screen_v1.csv",
]
print("="*132)
print("A51.2B - EXACT FROZEN CANDIDATE DEFINITION EXTRACTION")
print("="*132)
for p in FILES:
    print(f"\nFILE: {p}")
    if not p.exists():
        print("MISSING"); continue
    x=pd.read_csv(p) if p.suffix==".csv" else pd.read_parquet(p)
    print("COLUMNS:", " | ".join(x.columns))
    if p.suffix==".csv":
        print(x.to_string(index=False))
    else:
        # We need schema/value encodings only, not outcomes.
        cols=[c for c in x.columns if c not in {"outcome","final_mfe_pct","final_mae_pct"}]
        for c in cols:
            s=x[c].dropna()
            if s.nunique() <= 20:
                print(f"{c}: " + " | ".join(f"{k}={v}" for k,v in s.astype(str).value_counts().items()))
print("\nRESULT: EXACT-DEFINITION EXTRACTION COMPLETE")
print("No thresholds recomputed. No prospective data touched.")
