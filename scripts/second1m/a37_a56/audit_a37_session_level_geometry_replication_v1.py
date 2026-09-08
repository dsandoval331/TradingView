from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1/ae2_session_level_geometry_v1")
EVENTS = ROOT / "a37_session_level_geometry_events_v1.parquet"
QUINTILES = ROOT / "a37_preferred_discovery_quintile_performance_v1.csv"
ORDERS = ROOT / "a37_preferred_level_order_performance_v1.csv"
OUTER = ROOT / "a37_preferred_outermost_level_performance_v1.csv"
CLOSEST = ROOT / "a37_preferred_closest_pair_performance_v1.csv"
OUT = ROOT / "a37_geometry_replication_audit_v1.csv"

def weighted_rate(df):
    n = df["binary_n"].sum()
    return np.nan if n == 0 else 100.0 * df["favorable_n"].sum() / n

def audit_categorical(path, family, category_col):
    d = pd.read_csv(path)
    rows = []
    # Pool directions so discovery/validation replication is not driven by tiny directional cells.
    for category, g in d.groupby(category_col, dropna=False):
        disc = g[g["research_period"].eq("DISCOVERY")]
        val = g[g["research_period"].eq("VALIDATION")]
        if disc.empty or val.empty:
            continue
        dn, vn = int(disc["binary_n"].sum()), int(val["binary_n"].sum())
        if dn < 20 or vn < 20:
            continue
        dr, vr = weighted_rate(disc), weighted_rate(val)
        rows.append({
            "family": family,
            "feature": category_col,
            "state": category,
            "discovery_n": dn,
            "discovery_ff_pct": dr,
            "validation_n": vn,
            "validation_ff_pct": vr,
            "absolute_rate_change_pp": abs(vr-dr),
        })
    return rows

def main():
    rows = []

    q = pd.read_csv(QUINTILES)
    for (metric, quintile), g in q.groupby(["metric", "geometry_quintile"], dropna=False):
        disc = g[g["research_period"].eq("DISCOVERY")]
        val = g[g["research_period"].eq("VALIDATION")]
        if disc.empty or val.empty:
            continue
        dn, vn = int(disc["binary_n"].sum()), int(val["binary_n"].sum())
        if dn < 20 or vn < 20:
            continue
        dr, vr = weighted_rate(disc), weighted_rate(val)
        rows.append({
            "family": "DISCOVERY_QUINTILE",
            "feature": metric,
            "state": quintile,
            "discovery_n": dn,
            "discovery_ff_pct": dr,
            "validation_n": vn,
            "validation_ff_pct": vr,
            "absolute_rate_change_pp": abs(vr-dr),
        })

    rows += audit_categorical(ORDERS, "LEVEL_ORDER", "directional_level_order_inner_to_outer")
    rows += audit_categorical(OUTER, "OUTERMOST_LEVEL", "outermost_level")
    rows += audit_categorical(CLOSEST, "CLOSEST_PAIR", "closest_pair")

    out = pd.DataFrame(rows)
    if out.empty:
        print("No comparable cells found.")
        return

    # Baselines from event-level Preferred binary population.
    e = pd.read_parquet(EVENTS)
    e = e[e["preferred_family"] & e["outcome"].isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])].copy()
    base = {}
    for period in ["DISCOVERY","VALIDATION"]:
        z = e[e["research_period"].eq(period)]
        base[period] = 100.0 * z["outcome"].eq("FAVORABLE_FIRST").mean()

    out["discovery_lift_vs_baseline_pp"] = out["discovery_ff_pct"] - base["DISCOVERY"]
    out["validation_lift_vs_baseline_pp"] = out["validation_ff_pct"] - base["VALIDATION"]
    out["same_lift_direction"] = (
        np.sign(out["discovery_lift_vs_baseline_pp"]) ==
        np.sign(out["validation_lift_vs_baseline_pp"])
    )
    out["replicated_positive_3pp"] = (
        (out["discovery_lift_vs_baseline_pp"] >= 3.0) &
        (out["validation_lift_vs_baseline_pp"] >= 3.0)
    )
    out["replicated_negative_3pp"] = (
        (out["discovery_lift_vs_baseline_pp"] <= -3.0) &
        (out["validation_lift_vs_baseline_pp"] <= -3.0)
    )
    out = out.sort_values(
        ["replicated_positive_3pp","replicated_negative_3pp","same_lift_direction",
         "validation_lift_vs_baseline_pp"],
        ascending=[False, False, False, False]
    )
    out.to_csv(OUT, index=False)

    print("="*110)
    print("A37.9 - SESSION-LEVEL GEOMETRY REPLICATION AUDIT")
    print("="*110)
    print(f"Preferred discovery baseline:  {base['DISCOVERY']:.2f}%")
    print(f"Preferred validation baseline: {base['VALIDATION']:.2f}%")
    print()
    print("Comparable cells require >=20 binary observations in BOTH discovery and validation.")
    print("A 'replicated +/-3pp' cell must beat/miss its period-specific Preferred baseline by >=3pp in BOTH halves.")
    print()

    show = out[
        out["replicated_positive_3pp"] |
        out["replicated_negative_3pp"]
    ]
    print("REPLICATED >=3PP CELLS")
    print("-"*110)
    if show.empty:
        print("NONE")
    else:
        print(show.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print()
    print("ALL SAME-DIRECTION CELLS (top 25 by absolute validation lift)")
    print("-"*110)
    same = out[out["same_lift_direction"]].copy()
    same["abs_validation_lift"] = same["validation_lift_vs_baseline_pp"].abs()
    same = same.sort_values("abs_validation_lift", ascending=False).head(25)
    if same.empty:
        print("NONE")
    else:
        cols = ["family","feature","state","discovery_n","discovery_ff_pct",
                "discovery_lift_vs_baseline_pp","validation_n","validation_ff_pct",
                "validation_lift_vs_baseline_pp"]
        print(same[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print()
    print(f"Full audit: {OUT}")
    print("RESULT: REPLICATION AUDIT COMPLETE")
    print("This is a screening/diagnostic audit only. It does not modify Candidate Model V1.")

if __name__ == "__main__":
    main()
