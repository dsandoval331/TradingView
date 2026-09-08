from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1")
CANDIDATES = [
    ROOT / "ae2_c2_predictors_v1" / "ae2_c2_predictor_features_v1.parquet",
    ROOT / "ae2_c2_predictors_v1" / "ae2_c2_predictors_v1.parquet",
]

KEYWORDS = (
    "c1", "c2", "body", "range", "wick", "clv", "progress",
    "return", "vwap", "atr", "volume", "close", "open", "high", "low"
)

def find_source():
    for p in CANDIDATES:
        if p.exists():
            return p
    # Fallback: search only likely C2 predictor parquet files.
    hits = sorted(ROOT.rglob("*c2*predict*.parquet"))
    if not hits:
        raise FileNotFoundError(
            "Could not locate the frozen C2 predictor parquet under "
            f"{ROOT}. Expected an ae2_c2_predictors_v1 artifact."
        )
    return hits[0]

def main():
    src = find_source()
    df = pd.read_parquet(src)
    cols = list(df.columns)

    selected = [
        c for c in cols
        if any(k in c.lower() for k in KEYWORDS)
    ]

    print("=" * 112)
    print("A39.1 - C1->C2 TRANSITION EXISTING-EVIDENCE INVENTORY")
    print("=" * 112)
    print(f"Source: {src}")
    print(f"Rows: {len(df):,}")
    print(f"Total columns: {len(cols):,}")
    print()

    print("TRANSITION-RELEVANT EXISTING COLUMNS")
    print("-" * 112)
    for c in selected:
        print(c)

    # Exact-value availability audit for core raw OHLC if present.
    raw = [
        "c1_open","c1_high","c1_low","c1_close",
        "c2_open","c2_high","c2_low","c2_close"
    ]
    present = [c for c in raw if c in df.columns]
    print()
    print("RAW C1/C2 OHLC AVAILABILITY")
    print("-" * 112)
    for c in raw:
        print(f"{c}: {'YES' if c in df.columns else 'NO'}")

    # Classify existing fields into broad evidence buckets without inventing formulas.
    buckets = {
        "C1_ONLY": [],
        "C2_ONLY": [],
        "EXPLICIT_C1_TO_C2": [],
        "OTHER_RELEVANT": [],
    }
    for c in selected:
        lc = c.lower()
        has1 = "c1" in lc
        has2 = "c2" in lc
        if has1 and has2:
            buckets["EXPLICIT_C1_TO_C2"].append(c)
        elif has1:
            buckets["C1_ONLY"].append(c)
        elif has2:
            buckets["C2_ONLY"].append(c)
        else:
            buckets["OTHER_RELEVANT"].append(c)

    print()
    print("EVIDENCE BUCKETS")
    print("-" * 112)
    for name, vals in buckets.items():
        print(f"\n{name} ({len(vals)})")
        for c in vals:
            print(f"  {c}")

    outdir = ROOT / "ae2_c1_c2_transition_v1"
    outdir.mkdir(parents=True, exist_ok=True)
    inv = []
    for c in selected:
        lc = c.lower()
        has1, has2 = "c1" in lc, "c2" in lc
        bucket = (
            "EXPLICIT_C1_TO_C2" if has1 and has2 else
            "C1_ONLY" if has1 else
            "C2_ONLY" if has2 else
            "OTHER_RELEVANT"
        )
        inv.append({
            "column": c,
            "dtype": str(df[c].dtype),
            "non_null_n": int(df[c].notna().sum()),
            "bucket": bucket,
        })
    out = pd.DataFrame(inv)
    outfile = outdir / "a39_c1_c2_existing_evidence_inventory_v1.csv"
    out.to_csv(outfile, index=False)

    print()
    print(f"Inventory CSV: {outfile}")
    print("RESULT: EXISTING-EVIDENCE INVENTORY COMPLETE")
    print("No thresholds were created and no Candidate Model V1/prospective data was modified.")

if __name__ == "__main__":
    main()
