from pathlib import Path
import pandas as pd
import numpy as np
import re

ROOT = Path("data/second1m_alt_entry_research_v1")
BASE = ROOT / "ae2_session_levels_robustness_v1" / "ae2_session_levels_robustness_features_v1.parquet"
GEO = ROOT / "ae2_session_level_geometry_v1" / "a37_session_level_geometry_events_v1.parquet"
TIMING = ROOT / "ae2_preferred_level_timing_v1" / "a38_preferred_level_timing_events_v1.parquet"
A42 = ROOT / "ae2_opening_location_geometry_v1" / "a42_opening_location_features_v1.parquet"

OUTDIR = ROOT / "ae2_v2_evidence_consolidation_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT_PARQUET = OUTDIR / "a51_retained_v2_evidence_matrix_v1.parquet"
OUT_CSV = OUTDIR / "a51_retained_v2_evidence_matrix_v1.csv"
META = OUTDIR / "a51_retained_v2_evidence_reconstruction_metadata_v1.csv"

KEYS = ["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]

def norm_dates(df):
    if "trade_date" in df:
        df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df

def qnum(s):
    if pd.isna(s):
        return np.nan
    m = re.search(r"Q\s*([1-5])", str(s).upper())
    return int(m.group(1)) if m else np.nan

def find_threshold(feature, preferred_dir):
    """
    Find a discovery-frozen threshold CSV containing the requested feature.
    Returns numeric cut edges. Does not fit/recompute anything.
    """
    candidates = sorted(preferred_dir.glob("*.csv")) + sorted(ROOT.rglob("*threshold*.csv"))
    seen = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        try:
            t = pd.read_csv(p)
        except Exception:
            continue

        # row-oriented threshold tables
        if "feature" in t.columns:
            z = t[t["feature"].astype(str).eq(feature)]
            if len(z):
                row = z.iloc[0]
                edge_cols = [c for c in t.columns if re.fullmatch(r"edge_\d+", c)]
                if edge_cols:
                    edge_cols = sorted(edge_cols, key=lambda c: int(c.split("_")[1]))
                    vals = [float(row[c]) for c in edge_cols if pd.notna(row[c])]
                    if len(vals) >= 2:
                        return p, vals

        # wide or generic threshold formats
        textcols = [c for c in t.columns if t[c].dtype == object]
        if any(t[c].astype(str).str.contains(feature, regex=False).any() for c in textcols):
            num_cols = [c for c in t.columns if pd.api.types.is_numeric_dtype(t[c])]
            for _, row in t.iterrows():
                if feature in " | ".join(str(row[c]) for c in textcols):
                    vals = [float(row[c]) for c in num_cols if pd.notna(row[c])]
                    vals = sorted(set(vals))
                    if len(vals) >= 6:
                        return p, vals[:6]
    raise FileNotFoundError(f"Could not locate frozen thresholds for {feature}")

def apply_quintile_from_edges(s, edges):
    bins = np.array(edges, dtype=float)
    bins[0] = -np.inf
    bins[-1] = np.inf
    return pd.cut(s, bins=bins, labels=["Q1","Q2","Q3","Q4","Q5"], include_lowest=True)

def main():
    print("="*132)
    print("A51.2 - BUILD OUTCOME-FREE RETAINED V2 EVIDENCE MATRIX")
    print("="*132)
    print("Frozen retained candidates only. No outcome field loaded into output. No thresholds recomputed.\n")

    b = norm_dates(pd.read_parquet(BASE))
    g = norm_dates(pd.read_parquet(GEO))
    t = norm_dates(pd.read_parquet(TIMING))
    a = norm_dates(pd.read_parquet(A42))

    # Preferred-family universe only: frozen Candidate V1 positive family P1.
    # Historical development showed no P1/negative overlap, but this is intentionally
    # described as the positive-family universe, not a re-scored V2 model.
    u = b[
        b["session_level_clear_state"].eq("ALL_3_CLEARED") &
        b["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")
    ][KEYS + ["research_period","direction"]].copy()

    # Remove duplicate direction from KEYS payload if needed.
    u = u.loc[:, ~u.columns.duplicated()].copy()
    print(f"Frozen Preferred-family events: {len(u):,}")

    # ---------------- A37 ----------------
    gcols = KEYS + [
        "pm_pd_spacing_pct",
        "directional_level_order_inner_to_outer"
    ]
    gg = g[gcols].drop_duplicates(KEYS)
    u = u.merge(gg, on=KEYS, how="left", validate="one_to_one")

    a37_thr_file, a37_edges = find_threshold("pm_pd_spacing_pct", GEO.parent)
    u["a51_a37_pm_pd_spacing_q"] = apply_quintile_from_edges(u["pm_pd_spacing_pct"], a37_edges)
    u["A37_G_N1_PM_PD_SPACING_Q4"] = u["a51_a37_pm_pd_spacing_q"].astype(str).eq("Q4")

    # Frozen positive ordering: exact normalized inner->outer ordering PD>AH>PM.
    order_clean = (
        u["directional_level_order_inner_to_outer"]
        .astype(str)
        .str.upper()
        .str.replace(" ", "", regex=False)
        .str.replace("→", ">", regex=False)
        .str.replace("-", ">", regex=False)
    )
    # Accept common serialized spellings while preserving the frozen ordering meaning.
    u["A37_G_P2_PD_AH_PM_ORDERING"] = order_clean.isin({
        "PD>AH>PM", "PD>AH>PM>", "PD|AH|PM", "PD,AH,PM"
    })

    # ---------------- A38 ----------------
    tcols = KEYS + [
        "c1_pm_beyond","c1_ah_beyond","c1_pd_beyond",
        "c2_pm_beyond_calc","c2_ah_beyond_calc","c2_pd_beyond_calc",
        "c1_cleared_pattern"
    ]
    tt = t[tcols].drop_duplicates(KEYS)
    u = u.merge(tt, on=KEYS, how="left", validate="one_to_one")

    # PM remains for C2: AH + PD already cleared by C1, PM not yet cleared.
    u["A38_T_P1_PM_REMAINS_FOR_C2"] = (
        u["c1_ah_beyond"].fillna(False).astype(bool) &
        u["c1_pd_beyond"].fillna(False).astype(bool) &
        ~u["c1_pm_beyond"].fillna(False).astype(bool) &
        u["c2_pm_beyond_calc"].fillna(False).astype(bool)
    )

    # PD remains for C2: PM + AH already cleared by C1, PD not yet cleared.
    u["A38_T_N1_PD_REMAINS_FOR_C2"] = (
        u["c1_pm_beyond"].fillna(False).astype(bool) &
        u["c1_ah_beyond"].fillna(False).astype(bool) &
        ~u["c1_pd_beyond"].fillna(False).astype(bool) &
        u["c2_pd_beyond_calc"].fillna(False).astype(bool)
    )

    # ---------------- A39 ----------------
    # Use the already-frozen upstream bucket; do NOT refit thresholds.
    if "vwap_distance_change_pp__bucket" not in b.columns:
        raise KeyError("Missing frozen vwap_distance_change_pp__bucket in baseline source")
    bb = b[KEYS + ["vwap_distance_change_pp__bucket"]].drop_duplicates(KEYS)
    u = u.merge(bb, on=KEYS, how="left", validate="one_to_one")
    u["A39_T_V1_VWAP_EXPANSION_Q3"] = (
        u["vwap_distance_change_pp__bucket"].map(qnum).eq(3)
    )

    # ---------------- A42 ----------------
    acols = KEYS + ["a42_priorclose_to_outer_consumed_ratio"]
    aa = a[acols].drop_duplicates(KEYS)
    u = u.merge(aa, on=KEYS, how="left", validate="one_to_one")

    a42_thr_file, a42_edges = find_threshold(
        "a42_priorclose_to_outer_consumed_ratio", A42.parent
    )
    u["a51_a42_consumed_ratio_q"] = apply_quintile_from_edges(
        u["a42_priorclose_to_outer_consumed_ratio"], a42_edges
    )
    u["A42_N2_OPEN_CONSUMED_RATIO_Q2"] = (
        u["a51_a42_consumed_ratio_q"].astype(str).eq("Q2")
    )

    candidate_cols = [
        "A37_G_N1_PM_PD_SPACING_Q4",
        "A37_G_P2_PD_AH_PM_ORDERING",
        "A38_T_P1_PM_REMAINS_FOR_C2",
        "A38_T_N1_PD_REMAINS_FOR_C2",
        "A39_T_V1_VWAP_EXPANSION_Q3",
        "A42_N2_OPEN_CONSUMED_RATIO_Q2",
    ]

    # Compact outcome-free matrix.
    outcols = KEYS + ["research_period"] + candidate_cols + [
        "pm_pd_spacing_pct",
        "a51_a37_pm_pd_spacing_q",
        "directional_level_order_inner_to_outer",
        "c1_cleared_pattern",
        "vwap_distance_change_pp__bucket",
        "a42_priorclose_to_outer_consumed_ratio",
        "a51_a42_consumed_ratio_q",
    ]
    out = u[outcols].copy()
    out.to_parquet(OUT_PARQUET, index=False)
    out.to_csv(OUT_CSV, index=False)

    meta = pd.DataFrame([
        {
            "candidate_id":"A37_G_N1_PM_PD_SPACING_Q4",
            "frozen_source":str(GEO),
            "definition":"pm_pd_spacing_pct in discovery-frozen Q4",
            "threshold_source":str(a37_thr_file),
            "threshold_edges":" | ".join(map(str,a37_edges)),
        },
        {
            "candidate_id":"A37_G_P2_PD_AH_PM_ORDERING",
            "frozen_source":str(GEO),
            "definition":"directional_level_order_inner_to_outer == PD>AH>PM",
            "threshold_source":"",
            "threshold_edges":"",
        },
        {
            "candidate_id":"A38_T_P1_PM_REMAINS_FOR_C2",
            "frozen_source":str(TIMING),
            "definition":"C1 clears AH+PD but not PM; C2 clears PM",
            "threshold_source":"",
            "threshold_edges":"",
        },
        {
            "candidate_id":"A38_T_N1_PD_REMAINS_FOR_C2",
            "frozen_source":str(TIMING),
            "definition":"C1 clears PM+AH but not PD; C2 clears PD",
            "threshold_source":"",
            "threshold_edges":"",
        },
        {
            "candidate_id":"A39_T_V1_VWAP_EXPANSION_Q3",
            "frozen_source":str(BASE),
            "definition":"existing frozen vwap_distance_change_pp bucket == Q3",
            "threshold_source":"upstream frozen bucket",
            "threshold_edges":"",
        },
        {
            "candidate_id":"A42_N2_OPEN_CONSUMED_RATIO_Q2",
            "frozen_source":str(A42),
            "definition":"a42_priorclose_to_outer_consumed_ratio in discovery-frozen Q2",
            "threshold_source":str(a42_thr_file),
            "threshold_edges":" | ".join(map(str,a42_edges)),
        },
    ])
    meta.to_csv(META, index=False)

    print("\nCANDIDATE PREVALENCE (OUTCOME-FREE)")
    print("-"*132)
    for c in candidate_cols:
        n = int(out[c].fillna(False).sum())
        pct = 100*n/len(out) if len(out) else np.nan
        print(f"{c:42s} N={n:4d}  {pct:6.2f}%")

    print("\nMISSINGNESS IN RECONSTRUCTION FIELDS")
    misscols = [
        "pm_pd_spacing_pct","directional_level_order_inner_to_outer","c1_cleared_pattern",
        "vwap_distance_change_pp__bucket","a42_priorclose_to_outer_consumed_ratio"
    ]
    print(out[misscols].isna().sum().to_string())

    print("\nFROZEN THRESHOLD SOURCES")
    print(f"A37 spacing Q4: {a37_thr_file}")
    print(f"A42 consumed Q2: {a42_thr_file}")

    print(f"\nParquet:  {OUT_PARQUET}")
    print(f"CSV:      {OUT_CSV}")
    print(f"Metadata: {META}")
    print("RESULT: A51.2 OUTCOME-FREE RETAINED-EVIDENCE MATRIX BUILT")
    print("No outcome column written. No thresholds recomputed. No combinations scored.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__ == "__main__":
    main()
