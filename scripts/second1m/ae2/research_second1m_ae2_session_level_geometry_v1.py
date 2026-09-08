from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_INPUT = Path(
    "data/second1m_alt_entry_research_v1/"
    "ae2_session_levels_robustness_v1/"
    "ae2_session_levels_robustness_features_v1.parquet"
)
DEFAULT_OUTDIR = Path(
    "data/second1m_alt_entry_research_v1/"
    "ae2_session_level_geometry_v1"
)

BINARY_OUTCOMES = {"FAVORABLE_FIRST", "ADVERSE_FIRST"}


def directional_pct(a: pd.Series, b: pd.Series, direction: pd.Series) -> pd.Series:
    """Signed move from b to a; positive means favorable direction."""
    sign = np.where(direction.astype(str).str.upper().eq("BULL"), 1.0, -1.0)
    return sign * (a.astype(float) / b.astype(float) - 1.0) * 100.0


def abs_pair_pct(a: pd.Series, b: pd.Series) -> pd.Series:
    mid = (a.astype(float) + b.astype(float)) / 2.0
    return (a.astype(float) - b.astype(float)).abs() / mid * 100.0


def outcome_summary(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    x = df[df["outcome"].isin(BINARY_OUTCOMES)].copy()
    if x.empty:
        return pd.DataFrame()

    x["ff"] = x["outcome"].eq("FAVORABLE_FIRST").astype(int)
    out = (
        x.groupby(group_cols, dropna=False)
        .agg(
            binary_n=("ff", "size"),
            favorable_n=("ff", "sum"),
        )
        .reset_index()
    )
    out["adverse_n"] = out["binary_n"] - out["favorable_n"]
    out["favorable_first_pct"] = 100.0 * out["favorable_n"] / out["binary_n"]
    return out


def continuous_summary(df: pd.DataFrame, metrics: list[str], group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, g in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = dict(zip(group_cols, keys))
        for metric in metrics:
            s = pd.to_numeric(g[metric], errors="coerce").dropna()
            if s.empty:
                continue
            rows.append(
                {
                    **base,
                    "metric": metric,
                    "n": int(s.size),
                    "mean": float(s.mean()),
                    "median": float(s.median()),
                    "p25": float(s.quantile(0.25)),
                    "p75": float(s.quantile(0.75)),
                    "p10": float(s.quantile(0.10)),
                    "p90": float(s.quantile(0.90)),
                }
            )
    return pd.DataFrame(rows)


def add_discovery_quintiles(df: pd.DataFrame, metric: str) -> tuple[pd.Series, list[float] | None]:
    disc = pd.to_numeric(
        df.loc[df["research_period"].eq("DISCOVERY"), metric],
        errors="coerce",
    ).dropna()

    if disc.nunique() < 5:
        return pd.Series(pd.NA, index=df.index, dtype="object"), None

    edges = disc.quantile([0, .2, .4, .6, .8, 1]).to_numpy(dtype=float)
    edges = np.unique(edges)
    if len(edges) < 3:
        return pd.Series(pd.NA, index=df.index, dtype="object"), None

    edges[0] = -np.inf
    edges[-1] = np.inf
    labels = [f"Q{i+1}" for i in range(len(edges) - 1)]
    bins = pd.cut(
        pd.to_numeric(df[metric], errors="coerce"),
        bins=edges,
        labels=labels,
        include_lowest=True,
        duplicates="drop",
    )
    return bins.astype("object"), edges.tolist()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A37.6 historical session-level geometry / Preferred failure anatomy."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    args = parser.parse_args()

    src = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(src)
    df["direction"] = df["direction"].astype(str).str.upper()
    df["outcome"] = df["outcome"].astype(str).str.upper()

    required = [
        "symbol", "trade_date", "direction", "outcome", "research_period",
        "c2_close", "pm_directional_level", "ah_directional_level",
        "pd_directional_level", "relevant_levels_available_n",
        "session_level_clear_state", "market_prior_5d_consensus",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    # Complete three-level population.
    g = df[
        df["relevant_levels_available_n"].eq(3)
        & df["pm_directional_level"].notna()
        & df["ah_directional_level"].notna()
        & df["pd_directional_level"].notna()
    ].copy()

    # Existing frozen Preferred family definition, historical only.
    g["preferred_family"] = (
        g["session_level_clear_state"].eq("ALL_3_CLEARED")
        & g["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")
    )

    pm = pd.to_numeric(g["pm_directional_level"], errors="coerce")
    ah = pd.to_numeric(g["ah_directional_level"], errors="coerce")
    pdlev = pd.to_numeric(g["pd_directional_level"], errors="coerce")
    c2 = pd.to_numeric(g["c2_close"], errors="coerce")

    # Pairwise spacing: absolute geometry, independent of direction.
    g["pm_ah_spacing_pct"] = abs_pair_pct(pm, ah)
    g["pm_pd_spacing_pct"] = abs_pair_pct(pm, pdlev)
    g["ah_pd_spacing_pct"] = abs_pair_pct(ah, pdlev)

    levels = np.column_stack([pm.to_numpy(), ah.to_numpy(), pdlev.to_numpy()])
    max_level = np.nanmax(levels, axis=1)
    min_level = np.nanmin(levels, axis=1)
    midpoint = (max_level + min_level) / 2.0
    g["level_cluster_span_pct_calc"] = (max_level - min_level) / midpoint * 100.0
    g["mean_pairwise_spacing_pct"] = g[
        ["pm_ah_spacing_pct", "pm_pd_spacing_pct", "ah_pd_spacing_pct"]
    ].mean(axis=1)
    g["closest_pair_spacing_pct"] = g[
        ["pm_ah_spacing_pct", "pm_pd_spacing_pct", "ah_pd_spacing_pct"]
    ].min(axis=1)

    pair_cols = {
        "PM_AH": "pm_ah_spacing_pct",
        "PM_PD": "pm_pd_spacing_pct",
        "AH_PD": "ah_pd_spacing_pct",
    }
    pair_frame = pd.DataFrame(
        {name: g[col] for name, col in pair_cols.items()},
        index=g.index,
    )
    g["closest_pair"] = pair_frame.idxmin(axis=1)

    # Direction-normalized C2 penetration beyond each structural level.
    g["c2_beyond_pm_pct"] = directional_pct(c2, pm, g["direction"])
    g["c2_beyond_ah_pct"] = directional_pct(c2, ah, g["direction"])
    g["c2_beyond_pd_pct"] = directional_pct(c2, pdlev, g["direction"])

    sign = np.where(g["direction"].eq("BULL"), 1.0, -1.0)
    normalized = levels * sign[:, None]
    names = np.array(["PM", "AH", "PD"])
    outer_idx = np.nanargmax(normalized, axis=1)
    inner_idx = np.nanargmin(normalized, axis=1)
    g["outermost_level"] = names[outer_idx]
    g["innermost_level"] = names[inner_idx]

    outer_price = levels[np.arange(len(g)), outer_idx]
    g["c2_beyond_outermost_pct"] = (
        sign * (c2.to_numpy() / outer_price - 1.0) * 100.0
    )

    # Six possible directional orderings.
    orderings = []
    for row in normalized:
        idx = np.argsort(row)  # inner -> outer in favorable direction
        orderings.append(">".join(names[idx]))
    g["directional_level_order_inner_to_outer"] = orderings

    # Retain original frozen cluster metric for audit comparison if present.
    if "relevant_level_cluster_span_pct" in g.columns:
        g["cluster_span_diff_vs_frozen"] = (
            pd.to_numeric(g["level_cluster_span_pct_calc"], errors="coerce")
            - pd.to_numeric(g["relevant_level_cluster_span_pct"], errors="coerce")
        )

    keep = [
        "symbol", "trade_date", "direction", "architecture", "decision_candle",
        "entry_timestamp", "entry_price", "outcome", "research_period",
        "market_prior_5d_consensus", "session_level_clear_state",
        "relevant_levels_available_n", "relevant_levels_cleared_n",
        "preferred_family", "pm_directional_level", "ah_directional_level",
        "pd_directional_level", "c2_close",
        "pm_directional_distance_pct", "ah_directional_distance_pct",
        "pd_directional_distance_pct", "relevant_level_cluster_span_pct",
        "level_cluster_span_pct_calc", "cluster_span_diff_vs_frozen",
        "pm_ah_spacing_pct", "pm_pd_spacing_pct", "ah_pd_spacing_pct",
        "mean_pairwise_spacing_pct", "closest_pair_spacing_pct", "closest_pair",
        "outermost_level", "innermost_level",
        "directional_level_order_inner_to_outer",
        "c2_beyond_pm_pct", "c2_beyond_ah_pct", "c2_beyond_pd_pct",
        "c2_beyond_outermost_pct",
    ]
    keep = [c for c in keep if c in g.columns]
    geometry = g[keep].copy()

    geometry.to_parquet(outdir / "a37_session_level_geometry_events_v1.parquet", index=False)
    geometry.to_csv(outdir / "a37_session_level_geometry_events_v1.csv", index=False)

    # Main populations.
    all3 = geometry[geometry["session_level_clear_state"].eq("ALL_3_CLEARED")].copy()
    pref = all3[all3["preferred_family"]].copy()
    pref_binary = pref[pref["outcome"].isin(BINARY_OUTCOMES)].copy()

    metrics = [
        "level_cluster_span_pct_calc",
        "pm_ah_spacing_pct",
        "pm_pd_spacing_pct",
        "ah_pd_spacing_pct",
        "mean_pairwise_spacing_pct",
        "closest_pair_spacing_pct",
        "c2_beyond_pm_pct",
        "c2_beyond_ah_pct",
        "c2_beyond_pd_pct",
        "c2_beyond_outermost_pct",
    ]

    cont = continuous_summary(
        pref_binary,
        metrics,
        ["research_period", "direction", "outcome"],
    )
    cont.to_csv(outdir / "a37_preferred_geometry_continuous_summary_v1.csv", index=False)

    order_perf = outcome_summary(
        pref_binary,
        ["research_period", "direction", "directional_level_order_inner_to_outer"],
    )
    order_perf.to_csv(outdir / "a37_preferred_level_order_performance_v1.csv", index=False)

    outer_perf = outcome_summary(
        pref_binary,
        ["research_period", "direction", "outermost_level"],
    )
    outer_perf.to_csv(outdir / "a37_preferred_outermost_level_performance_v1.csv", index=False)

    closest_perf = outcome_summary(
        pref_binary,
        ["research_period", "direction", "closest_pair"],
    )
    closest_perf.to_csv(outdir / "a37_preferred_closest_pair_performance_v1.csv", index=False)

    # Discovery-defined quintiles, applied unchanged to validation.
    quintile_rows = []
    threshold_rows = []
    for metric in metrics:
        bins, edges = add_discovery_quintiles(pref_binary, metric)
        if edges is None:
            continue
        tmp = pref_binary.copy()
        tmp["geometry_quintile"] = bins
        q = outcome_summary(
            tmp,
            ["research_period", "direction", "geometry_quintile"],
        )
        if not q.empty:
            q.insert(0, "metric", metric)
            quintile_rows.append(q)

        for i in range(1, len(edges) - 1):
            threshold_rows.append(
                {
                    "metric": metric,
                    "cutpoint": f"q{i*20}",
                    "value": edges[i],
                    "derived_from": "DISCOVERY_PREFERRED_BINARY_ONLY",
                }
            )

    quintiles = (
        pd.concat(quintile_rows, ignore_index=True)
        if quintile_rows else pd.DataFrame()
    )
    quintiles.to_csv(outdir / "a37_preferred_discovery_quintile_performance_v1.csv", index=False)
    pd.DataFrame(threshold_rows).to_csv(
        outdir / "a37_geometry_discovery_quintile_thresholds_v1.csv",
        index=False,
    )

    # Population counts / sanity checks.
    rows = []
    populations = {
        "COMPLETE_3_LEVEL": geometry,
        "ALL_3_CLEARED": all3,
        "PREFERRED_FAMILY": pref,
    }
    for name, pop in populations.items():
        for period in ["DISCOVERY", "VALIDATION"]:
            p = pop[pop["research_period"].eq(period)]
            b = p[p["outcome"].isin(BINARY_OUTCOMES)]
            fav = int(b["outcome"].eq("FAVORABLE_FIRST").sum())
            rows.append(
                {
                    "population": name,
                    "research_period": period,
                    "total_n": len(p),
                    "binary_n": len(b),
                    "favorable_n": fav,
                    "adverse_n": int(len(b) - fav),
                    "favorable_first_pct": (
                        100.0 * fav / len(b) if len(b) else np.nan
                    ),
                }
            )
    counts = pd.DataFrame(rows)
    counts.to_csv(outdir / "a37_population_counts_v1.csv", index=False)

    print("=" * 92)
    print("A37.6 - SESSION-LEVEL GEOMETRY / PREFERRED FAILURE ANATOMY V1")
    print("=" * 92)
    print(f"Input:  {src}")
    print(f"Output: {outdir}")
    print()
    print("POPULATION CHECK")
    print("-" * 92)
    print(counts.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print()

    if "cluster_span_diff_vs_frozen" in geometry.columns:
        diff = pd.to_numeric(
            geometry["cluster_span_diff_vs_frozen"], errors="coerce"
        ).abs().dropna()
        print("FROZEN CLUSTER-SPAN PARITY")
        print("-" * 92)
        print(f"Rows compared: {len(diff):,}")
        print(f"Max absolute difference: {diff.max() if len(diff) else np.nan:.12f}")
        print()

    print("PREFERRED BINARY GEOMETRY - MEDIANS")
    print("-" * 92)
    if not cont.empty:
        med = cont[
            cont["metric"].isin([
                "level_cluster_span_pct_calc",
                "mean_pairwise_spacing_pct",
                "c2_beyond_outermost_pct",
            ])
        ][
            ["research_period", "direction", "outcome", "metric", "n", "median", "p25", "p75"]
        ]
        print(med.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    else:
        print("No binary Preferred observations found.")

    print()
    print("RESULT: DESCRIPTIVE GEOMETRY DATASET COMPLETE")
    print(
        "No Candidate Model V1 rule or prospective ledger was modified. "
        "Discovery quintiles are descriptive candidate-generation aids only."
    )


if __name__ == "__main__":
    main()
