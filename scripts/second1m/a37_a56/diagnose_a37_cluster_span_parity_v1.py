from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

SRC = Path(
    "data/second1m_alt_entry_research_v1/"
    "ae2_session_levels_robustness_v1/"
    "ae2_session_levels_robustness_features_v1.parquet"
)

df = pd.read_parquet(SRC)

cols = [
    "direction",
    "entry_price",
    "c2_close",
    "pm_directional_level",
    "ah_directional_level",
    "pd_directional_level",
    "pm_directional_distance_pct",
    "ah_directional_distance_pct",
    "pd_directional_distance_pct",
    "relevant_level_cluster_span_pct",
]
x = df[cols].dropna().copy()

pm = pd.to_numeric(x["pm_directional_level"], errors="coerce")
ah = pd.to_numeric(x["ah_directional_level"], errors="coerce")
pdlev = pd.to_numeric(x["pd_directional_level"], errors="coerce")
entry = pd.to_numeric(x["entry_price"], errors="coerce")
c2 = pd.to_numeric(x["c2_close"], errors="coerce")
frozen = pd.to_numeric(x["relevant_level_cluster_span_pct"], errors="coerce")

levels = np.column_stack([pm.to_numpy(), ah.to_numpy(), pdlev.to_numpy()])
hi = np.nanmax(levels, axis=1)
lo = np.nanmin(levels, axis=1)
mid = (hi + lo) / 2.0

directional_dist = x[
    [
        "pm_directional_distance_pct",
        "ah_directional_distance_pct",
        "pd_directional_distance_pct",
    ]
].apply(pd.to_numeric, errors="coerce")

candidates = {
    "raw_span_over_midpoint": (hi - lo) / mid * 100.0,
    "raw_span_over_entry": (hi - lo) / entry.to_numpy() * 100.0,
    "raw_span_over_c2_close": (hi - lo) / c2.to_numpy() * 100.0,
    "distance_max_minus_min": (
        directional_dist.max(axis=1) - directional_dist.min(axis=1)
    ).to_numpy(),
    "distance_abs_max_minus_min": (
        directional_dist.abs().max(axis=1) - directional_dist.abs().min(axis=1)
    ).to_numpy(),
}

rows = []
for name, vals in candidates.items():
    vals = pd.Series(vals, index=x.index, dtype="float64")
    d = (vals - frozen).abs()
    rows.append(
        {
            "candidate_formula": name,
            "n": int(d.notna().sum()),
            "max_abs_diff": float(d.max()),
            "mean_abs_diff": float(d.mean()),
            "median_abs_diff": float(d.median()),
            "p99_abs_diff": float(d.quantile(0.99)),
        }
    )

result = pd.DataFrame(rows).sort_values(
    ["max_abs_diff", "mean_abs_diff"]
)

print("=" * 100)
print("A37.6A - FROZEN CLUSTER-SPAN FORMULA PARITY DIAGNOSTIC")
print("=" * 100)
print(result.to_string(index=False, float_format=lambda v: f"{v:.12f}"))

best_name = result.iloc[0]["candidate_formula"]
best_vals = pd.Series(candidates[best_name], index=x.index, dtype="float64")
diff = (best_vals - frozen).abs()

print()
print(f"BEST CANDIDATE: {best_name}")
print(f"Rows within 1e-9: {(diff <= 1e-9).sum():,} / {len(diff):,}")
print(f"Rows within 1e-6: {(diff <= 1e-6).sum():,} / {len(diff):,}")

print()
print("TOP 10 MISMATCHES FOR BEST CANDIDATE")
print("-" * 100)
audit = x.loc[diff.nlargest(10).index].copy()
audit["candidate_value"] = best_vals.loc[audit.index]
audit["abs_diff"] = diff.loc[audit.index]
print(audit.to_string(index=False))

print()
print("RESULT: PARITY DIAGNOSTIC COMPLETE")
