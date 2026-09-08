from __future__ import annotations

from pathlib import Path
from itertools import combinations
import numpy as np
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1/ae2_session_level_geometry_v1")
EVENTS = ROOT / "a37_session_level_geometry_events_v1.parquet"
THRESH = ROOT / "a37_geometry_discovery_quintile_thresholds_v1.csv"
OUT_OVERLAP = ROOT / "a37_geometry_candidate_overlap_v1.csv"
OUT_INTERACTIONS = ROOT / "a37_geometry_candidate_interactions_v1.csv"
OUT_INCREMENTAL = ROOT / "a37_geometry_candidate_incremental_v1.csv"

BINARY = {"FAVORABLE_FIRST", "ADVERSE_FIRST"}

CANDIDATES = {
    "N_PM_PD_Q4": ("pm_pd_spacing_pct", "Q4"),
    "N_OUTER_PEN_Q4": ("c2_beyond_outermost_pct", "Q4"),
    "P_MEAN_SPACE_Q2": ("mean_pairwise_spacing_pct", "Q2"),
    "P_CLUSTER_Q2": ("level_cluster_span_pct_calc", "Q2"),
    "P_ORDER_PD_AH_PM": ("directional_level_order_inner_to_outer", "PD>AH>PM"),
}

def stats(df: pd.DataFrame) -> tuple[int, int, float]:
    x = df[df["outcome"].isin(BINARY)]
    n = len(x)
    fav = int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n, fav, (100.0 * fav / n if n else np.nan)

def load_qmaps() -> dict[str, list[float]]:
    t = pd.read_csv(THRESH)
    out = {}
    for metric, g in t.groupby("metric"):
        m = dict(zip(g["cutpoint"], g["value"]))
        if all(k in m for k in ["q20", "q40", "q60", "q80"]):
            out[metric] = [-np.inf, m["q20"], m["q40"], m["q60"], m["q80"], np.inf]
    return out

def candidate_mask(e: pd.DataFrame, feature: str, state: str, qmaps) -> pd.Series:
    if state.startswith("Q"):
        bins = qmaps[feature]
        labels = ["Q1", "Q2", "Q3", "Q4", "Q5"]
        return pd.cut(
            pd.to_numeric(e[feature], errors="coerce"),
            bins=bins, labels=labels, include_lowest=True
        ).astype("object").eq(state)
    return e[feature].astype(str).eq(state)

def main():
    e = pd.read_parquet(EVENTS)
    e = e[e["preferred_family"] & e["outcome"].isin(BINARY)].copy()
    qmaps = load_qmaps()

    masks = {}
    for name, (feature, state) in CANDIDATES.items():
        masks[name] = candidate_mask(e, feature, state, qmaps)

    # 1) Pairwise overlap / Jaccard, separately by period.
    overlap_rows = []
    for period in ["DISCOVERY", "VALIDATION"]:
        idx = e["research_period"].eq(period)
        for a, b in combinations(CANDIDATES, 2):
            A = masks[a] & idx
            B = masks[b] & idx
            inter = A & B
            union = A | B
            na, nb, ni, nu = int(A.sum()), int(B.sum()), int(inter.sum()), int(union.sum())
            overlap_rows.append({
                "research_period": period,
                "candidate_a": a, "candidate_b": b,
                "a_n": na, "b_n": nb, "intersection_n": ni, "union_n": nu,
                "jaccard": ni / nu if nu else np.nan,
                "a_covered_by_b_pct": 100.0 * ni / na if na else np.nan,
                "b_covered_by_a_pct": 100.0 * ni / nb if nb else np.nan,
            })
    overlap = pd.DataFrame(overlap_rows)
    overlap.to_csv(OUT_OVERLAP, index=False)

    # 2) Pairwise 2x2 interaction cells: neither / A only / B only / both.
    interaction_rows = []
    for period in ["DISCOVERY", "VALIDATION"]:
        p = e[e["research_period"].eq(period)]
        for a, b in combinations(CANDIDATES, 2):
            ma = masks[a].loc[p.index]
            mb = masks[b].loc[p.index]
            cells = {
                "NEITHER": ~ma & ~mb,
                "A_ONLY": ma & ~mb,
                "B_ONLY": ~ma & mb,
                "BOTH": ma & mb,
            }
            base_n, base_f, base_r = stats(p)
            for cell, cmask in cells.items():
                z = p[cmask]
                n, fav, r = stats(z)
                interaction_rows.append({
                    "research_period": period,
                    "candidate_a": a, "candidate_b": b, "cell": cell,
                    "binary_n": n, "favorable_n": fav, "ff_pct": r,
                    "period_baseline_ff_pct": base_r,
                    "lift_vs_period_baseline_pp": r - base_r if n else np.nan,
                })
    interactions = pd.DataFrame(interaction_rows)
    interactions.to_csv(OUT_INTERACTIONS, index=False)

    # 3) Incremental information: candidate performance conditional on each other candidate.
    incremental_rows = []
    for period in ["DISCOVERY", "VALIDATION"]:
        p = e[e["research_period"].eq(period)]
        for target in CANDIDATES:
            for condition in CANDIDATES:
                if target == condition:
                    continue
                mt = masks[target].loc[p.index]
                mc = masks[condition].loc[p.index]
                for condition_state, csel in [
                    ("CONDITION_ABSENT", ~mc),
                    ("CONDITION_PRESENT", mc),
                ]:
                    base = p[csel]
                    hit = p[csel & mt]
                    bn, bf, br = stats(base)
                    hn, hf, hr = stats(hit)
                    incremental_rows.append({
                        "research_period": period,
                        "target_candidate": target,
                        "condition_candidate": condition,
                        "condition_state": condition_state,
                        "conditional_baseline_n": bn,
                        "conditional_baseline_ff_pct": br,
                        "target_n": hn,
                        "target_ff_pct": hr,
                        "incremental_lift_pp": hr - br if hn else np.nan,
                    })
    incremental = pd.DataFrame(incremental_rows)
    incremental.to_csv(OUT_INCREMENTAL, index=False)

    print("=" * 118)
    print("A37.12 - GEOMETRY REDUNDANCY / INTERACTION AUDIT")
    print("=" * 118)

    print("\nVALIDATION PAIRWISE OVERLAP")
    print("-" * 118)
    vo = overlap[overlap["research_period"].eq("VALIDATION")].sort_values("jaccard", ascending=False)
    print(vo.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print("\nVALIDATION BOTH-CELL PERFORMANCE (N >= 15)")
    print("-" * 118)
    vi = interactions[
        interactions["research_period"].eq("VALIDATION")
        & interactions["cell"].eq("BOTH")
        & interactions["binary_n"].ge(15)
    ].sort_values("lift_vs_period_baseline_pp", ascending=False)
    if len(vi):
        print(vi.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    else:
        print("NONE")

    print("\nREPLICATED BOTH-CELLS (N >= 15 in discovery and validation)")
    print("-" * 118)
    d = interactions[
        interactions["research_period"].eq("DISCOVERY")
        & interactions["cell"].eq("BOTH")
        & interactions["binary_n"].ge(15)
    ]
    v = interactions[
        interactions["research_period"].eq("VALIDATION")
        & interactions["cell"].eq("BOTH")
        & interactions["binary_n"].ge(15)
    ]
    m = d.merge(v, on=["candidate_a","candidate_b","cell"], suffixes=("_disc","_val"))
    if len(m):
        cols = [
            "candidate_a","candidate_b",
            "binary_n_disc","ff_pct_disc","lift_vs_period_baseline_pp_disc",
            "binary_n_val","ff_pct_val","lift_vs_period_baseline_pp_val",
        ]
        print(m[cols].sort_values("lift_vs_period_baseline_pp_val", ascending=False)
              .to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    else:
        print("NONE")

    print("\nVALIDATION INCREMENTAL EFFECTS (target N >= 15; top absolute lifts)")
    print("-" * 118)
    inc = incremental[
        incremental["research_period"].eq("VALIDATION")
        & incremental["target_n"].ge(15)
    ].copy()
    inc["abs_lift"] = inc["incremental_lift_pp"].abs()
    cols = [
        "target_candidate","condition_candidate","condition_state",
        "conditional_baseline_n","conditional_baseline_ff_pct",
        "target_n","target_ff_pct","incremental_lift_pp"
    ]
    print(inc.sort_values("abs_lift", ascending=False).head(30)[cols]
          .to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print()
    print(f"Overlap:      {OUT_OVERLAP}")
    print(f"Interactions: {OUT_INTERACTIONS}")
    print(f"Incremental:  {OUT_INCREMENTAL}")
    print("RESULT: REDUNDANCY / INTERACTION AUDIT COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
