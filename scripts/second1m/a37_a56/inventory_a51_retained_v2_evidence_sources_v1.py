from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1")
BASE = ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OUTDIR = ROOT/"ae2_v2_evidence_consolidation_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR/"a51_retained_evidence_source_inventory_v1.csv"

# Retained V2 evidence and likely source tokens. Inventory only: no outcomes and
# no new candidate states are computed here.
CANDIDATES = {
    "A37_G_N1_PM_PD_SPACING_Q4": {
        "source_hint": "ae2_session_level_geometry_v1",
        "tokens": ["pm", "pd", "spacing"],
    },
    "A37_G_P2_PD_AH_PM_ORDERING": {
        "source_hint": "ae2_session_level_geometry_v1",
        "tokens": ["order", "ordering", "pm", "ah", "pd"],
    },
    "A38_T_P1_PM_REMAINS_FOR_C2": {
        "source_hint": "ae2_preferred_level_timing_v1",
        "tokens": ["pm", "remain", "c1", "c2", "clear"],
    },
    "A38_T_N1_PD_REMAINS_FOR_C2": {
        "source_hint": "ae2_preferred_level_timing_v1",
        "tokens": ["pd", "remain", "c1", "c2", "clear"],
    },
    "A39_T_V1_VWAP_EXPANSION_Q3": {
        "source_hint": "ae2_preferred_level_timing_v1",
        "tokens": ["vwap", "change", "expansion", "c1", "c2"],
    },
    "A42_N2_OPEN_CONSUMED_RATIO_Q2": {
        "source_hint": "ae2_opening_location_geometry_v1",
        "tokens": ["consum", "ratio", "open", "outer"],
    },
}

def main():
    print("="*132)
    print("A51.1 - V2 RETAINED-EVIDENCE CONSOLIDATION SOURCE INVENTORY")
    print("="*132)
    print("Purpose: locate exact frozen source fields/artifacts for the six retained V2 candidates.")
    print("No outcomes analyzed. No candidate combinations constructed.\n")

    files = sorted(ROOT.rglob("*.parquet"))
    rows = []

    for cid, spec in CANDIDATES.items():
        print(f"\n[{cid}]")
        hits = 0
        for p in files:
            if OUTDIR in p.parents:
                continue
            # Prioritize likely source directories but also allow token-based discovery elsewhere.
            try:
                cols = list(pd.read_parquet(p).columns)
            except Exception:
                continue
            low = {c:c.lower() for c in cols}
            matches = [c for c in cols if any(t in low[c] for t in spec["tokens"])]
            hint_match = spec["source_hint"].lower() in str(p).lower()
            if matches and (hint_match or len(matches) >= 2):
                hits += 1
                print(f"  SOURCE: {p}")
                print("    " + "\n    ".join(matches[:60]))
                rows.append({
                    "candidate_id": cid,
                    "source_hint": spec["source_hint"],
                    "artifact": str(p),
                    "hint_match": hint_match,
                    "matched_columns": " | ".join(matches[:100]),
                })
        if hits == 0:
            print("  NO MATCHING ARTIFACT FOUND")

    # Also expose exact baseline anchors needed later for a one-row-per-event consolidation.
    b = pd.read_parquet(BASE)
    print("\n\nBASELINE JOIN / FIREWALL ANCHORS")
    anchors = [
        "symbol","trade_date","direction","architecture","decision_candle","entry_timestamp",
        "research_period","session_level_clear_state","market_prior_5d_consensus",
        "outcome"
    ]
    for c in anchors:
        print(f"{c}: {'YES' if c in b.columns else 'NO'}")

    pd.DataFrame(rows).to_csv(OUT,index=False)
    print(f"\nInventory CSV: {OUT}")
    print("RESULT: A51.1 RETAINED-EVIDENCE SOURCE INVENTORY COMPLETE")
    print("No outcomes exposed in candidate selection; no thresholds recomputed.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__ == "__main__":
    main()
