from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
TOK=["vwap_distance_change_pp","c2_favorable_vwap_distance_pct","c1_favorable_vwap_distance_pct"]
print("="*132)
print("A51.3D - A39 PREFERRED EVENT-SOURCE VALUE AUDIT")
print("="*132)

# Find event-level artifacts with raw A39 VWAP change and keys.
for p in sorted(ROOT.rglob("*.parquet")):
    try:
        x=pd.read_parquet(p)
    except Exception: continue
    exact=[c for c in x.columns if c in TOK or "vwap_distance_change_pp" in c.lower()]
    keys=[c for c in ["symbol","trade_date","direction","research_period","outcome"] if c in x.columns]
    if exact and {"symbol","trade_date","direction"}.issubset(x.columns):
        print(f"\nFILE: {p} rows={len(x):,} cols={len(x.columns):,}")
        print("  KEYS:", " | ".join(keys))
        print("  VWAP:", " | ".join(exact))
        for c in exact:
            s=pd.to_numeric(x[c],errors="coerce")
            print(f"    {c}: nonnull={s.notna().sum():,} min={s.min():.12g} max={s.max():.12g}")

# Print full frozen A39 summary rows for Q3 so exact target framing is visible.
for name in ["a39_transition_frozen_quintile_performance_v1.csv",
             "a39_transition_candidate_robustness_v1.csv"]:
    p=ROOT/"ae2_c1_c2_transition_v1"/name
    if p.exists():
        x=pd.read_csv(p)
        print(f"\nSUMMARY: {name}")
        print(x.to_string(index=False))

print("\nRESULT: SOURCE-VALUE AUDIT COMPLETE. No thresholds recomputed.")
