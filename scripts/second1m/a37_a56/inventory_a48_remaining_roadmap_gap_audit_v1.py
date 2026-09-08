from pathlib import Path
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1")
OUTDIR = ROOT / "ae2_remaining_roadmap_gap_audit_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "a48_existing_evidence_family_inventory_v1.csv"

# Broad, outcome-free inventory of research artifacts. This does not infer
# "tested" merely from a column name; it gives us a concrete map for A48.2.
FAMILY_TOKENS = {
    "CANDLE_MORPHOLOGY": ["body", "wick", "clv", "c1_", "c2_", "close_progress"],
    "VWAP_MA_CONTEXT": ["vwap", "ema9", "ema20", "sma20", "sma50", "slope"],
    "DAILY_WEEKLY_TREND": ["daily", "weekly", "prior_ret", "trend"],
    "MARKET_REGIME": ["spy_", "qqq_", "dia_", "market_"],
    "RELATIVE_STRENGTH": ["relative_", "rel_", "stock_vs_market"],
    "VOLUME_PARTICIPATION": ["volume", "rvol", "participation"],
    "PREMARKET_GAP": ["premarket", "pre_", "gap"],
    "SESSION_LEVELS": ["pmh", "pml", "pdh", "pdl", "ahh", "ahl", "session_level"],
    "CALENDAR_TIME": ["weekday", "month", "calendar", "trade_date"],
    "EXHAUSTION": ["exhaust", "extreme_count"],
    "POST_SIGNAL_PATH": ["c3_", "c4_", "warning", "recovery", "deterior"],
    "GEOMETRY_TIMING": ["cluster", "spacing", "penetration", "cleared", "burden", "ordering"],
}

def main():
    print("=" * 132)
    print("A48.1 - REMAINING-ROADMAP GAP AUDIT: OUTCOME-FREE ARTIFACT/FAMILY INVENTORY")
    print("=" * 132)

    parquet_files = sorted(ROOT.rglob("*.parquet"))
    rows = []
    scanned = 0

    for p in parquet_files:
        # Avoid recursively scanning A48 output if rerun.
        if OUTDIR in p.parents:
            continue
        try:
            df = pd.read_parquet(p)
        except Exception as e:
            rows.append({
                "artifact": str(p), "rows": None, "columns": None,
                "family": "READ_ERROR", "matched_columns": str(e)[:500]
            })
            continue

        scanned += 1
        cols = list(df.columns)
        low = {c: c.lower() for c in cols}

        for family, tokens in FAMILY_TOKENS.items():
            matches = [c for c in cols if any(t in low[c] for t in tokens)]
            if matches:
                rows.append({
                    "artifact": str(p),
                    "rows": len(df),
                    "columns": len(cols),
                    "family": family,
                    "matched_columns": " | ".join(matches[:80]),
                })

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)

    print(f"Parquet artifacts scanned: {scanned:,}")
    if len(out):
        print("\nFAMILY COVERAGE COUNTS (artifact matches, not claims of independent testing)")
        cov = (out[out.family != "READ_ERROR"]
               .groupby("family")["artifact"].nunique()
               .sort_values(ascending=False))
        print(cov.to_string())

        print("\nRECENT/RESEARCH ARTIFACT DIRECTORIES")
        dirs = sorted({str(Path(a).parent) for a in out["artifact"].dropna()})
        for d in dirs:
            print(d)

    print("\nIMPORTANT INTERPRETATION RULE")
    print("Column/artifact presence != proven completed hypothesis.")
    print("A48.2 must reconcile this inventory with the documented completed-family roadmap.")
    print("Do not expose outcomes or create new thresholds during this audit.")
    print(f"\nInventory CSV: {OUT}")
    print("RESULT: A48.1 OUTCOME-FREE GAP-AUDIT INVENTORY COMPLETE")
    print("No Candidate Model V1 or prospective data modified.")

if __name__ == "__main__":
    main()
