from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_candidates(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    json_cols = [
        "raw_features_json",
        "context_states_json",
        "gate_results_json",
        "missing_data_json",
        "explanation_json",
        "lineage_json",
    ]
    for col in json_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: json.loads(x) if isinstance(x, str) and x.strip() else {}
            )
    return df


def one_row_per_symbol(df: pd.DataFrame) -> pd.DataFrame:
    # Candidate JSON is repeated across strategy/direction rows. One row per symbol
    # is sufficient for snapshot-quality diagnostics.
    return (
        df.sort_values(["symbol", "strategy_family", "direction"])
          .drop_duplicates(subset=["symbol"], keep="first")
          .reset_index(drop=True)
    )


def extract_symbol_diagnostics(df: pd.DataFrame, snapshot_code: str) -> pd.DataFrame:
    base = one_row_per_symbol(df)

    rows = []
    for _, r in base.iterrows():
        raw = r["raw_features_json"] if isinstance(r["raw_features_json"], dict) else {}
        pm = raw.get("premarket", {}) if isinstance(raw, dict) else {}
        missing = r["missing_data_json"] if isinstance(r["missing_data_json"], dict) else {}
        context = r["context_states_json"] if isinstance(r["context_states_json"], dict) else {}

        rows.append({
            "snapshot_code": snapshot_code,
            "symbol": r["symbol"],
            "eligibility_state": r["eligibility_state"],
            "gate_state": r.get("gate_state"),
            "pm_bar_count": pm.get("bar_count"),
            "pm_exact_cutoff_bar_present": pm.get("exact_cutoff_bar_present"),
            "pm_staleness_minutes_at_cutoff": pm.get("staleness_minutes_at_cutoff"),
            "pm_possible_minutes_to_cutoff": pm.get("possible_pm_minutes_to_cutoff"),
            "pm_observed_minute_density_pct": pm.get("observed_pm_minute_density_pct"),
            "pm_observation_state": pm.get("observation_state"),
            "pm_last_bar_time_ct": pm.get("last_bar_time_ct"),
            "missing_required_count": missing.get("required_core_missing_count"),
            "missing_items": json.dumps(missing.get("items", []), separators=(",", ":")),
            "sector_state": context.get("sector_state"),
            "sector_benchmark": (
                context.get("sector", {}).get("benchmark_symbol")
                if isinstance(context.get("sector"), dict)
                else None
            ),
        })

    out = pd.DataFrame(rows)
    numeric_cols = [
        "pm_bar_count",
        "pm_staleness_minutes_at_cutoff",
        "pm_possible_minutes_to_cutoff",
        "pm_observed_minute_density_pct",
        "missing_required_count",
    ]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def qstats(series: pd.Series) -> dict:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return {
            "count": 0,
            "min": None,
            "p05": None,
            "p10": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "max": None,
            "mean": None,
        }

    return {
        "count": int(s.size),
        "min": float(s.min()),
        "p05": float(s.quantile(0.05)),
        "p10": float(s.quantile(0.10)),
        "p25": float(s.quantile(0.25)),
        "median": float(s.median()),
        "p75": float(s.quantile(0.75)),
        "p90": float(s.quantile(0.90)),
        "p95": float(s.quantile(0.95)),
        "max": float(s.max()),
        "mean": float(s.mean()),
    }


def summarize(diag: pd.DataFrame, snapshot_code: str) -> dict:
    elig = diag["eligibility_state"].value_counts(dropna=False).to_dict()
    exact = diag["pm_exact_cutoff_bar_present"].value_counts(dropna=False).to_dict()

    insufficient = diag.loc[
        diag["eligibility_state"] == "INSUFFICIENT_DATA",
        ["symbol", "gate_state", "missing_required_count", "missing_items"]
    ].to_dict(orient="records")

    return {
        "snapshot_code": snapshot_code,
        "symbol_count": int(diag["symbol"].nunique()),
        "eligibility_counts": {str(k): int(v) for k, v in elig.items()},
        "exact_cutoff_counts": {str(k): int(v) for k, v in exact.items()},
        "pm_bar_count_stats": qstats(diag["pm_bar_count"]),
        "pm_density_pct_stats": qstats(diag["pm_observed_minute_density_pct"]),
        "pm_staleness_minutes_stats": qstats(diag["pm_staleness_minutes_at_cutoff"]),
        "insufficient_symbols": insufficient,
    }


def compare_a_b(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "symbol",
        "eligibility_state",
        "gate_state",
        "pm_bar_count",
        "pm_exact_cutoff_bar_present",
        "pm_staleness_minutes_at_cutoff",
        "pm_observed_minute_density_pct",
        "missing_required_count",
    ]
    aa = a[cols].copy()
    bb = b[cols].copy()

    aa = aa.rename(columns={c: f"{c}_A" for c in cols if c != "symbol"})
    bb = bb.rename(columns={c: f"{c}_B" for c in cols if c != "symbol"})

    merged = aa.merge(bb, on="symbol", how="outer")
    merged["eligibility_transition"] = (
        merged["eligibility_state_A"].astype(str)
        + " -> "
        + merged["eligibility_state_B"].astype(str)
    )
    merged["pm_bar_count_delta"] = merged["pm_bar_count_B"] - merged["pm_bar_count_A"]
    return merged.sort_values("symbol").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate PMS full-universe SCAN_A/SCAN_B canary outputs."
    )
    parser.add_argument(
        "--trade-date",
        required=True,
        help="Trade date YYYY-MM-DD, e.g. 2025-08-15",
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("research_outputs") / "pms_snapshots",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("research_outputs") / "pms_snapshot_validation",
    )
    args = parser.parse_args()

    trade_date = args.trade_date
    input_root = args.input_root
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    a_path = input_root / f"{trade_date}_scan_a_candidates.csv"
    b_path = input_root / f"{trade_date}_scan_b_candidates.csv"

    if not a_path.exists():
        raise FileNotFoundError(a_path)
    if not b_path.exists():
        raise FileNotFoundError(b_path)

    a = extract_symbol_diagnostics(load_candidates(a_path), "SCAN_A")
    b = extract_symbol_diagnostics(load_candidates(b_path), "SCAN_B")
    ab = compare_a_b(a, b)

    summary = {
        "trade_date": trade_date,
        "scan_a": summarize(a, "SCAN_A"),
        "scan_b": summarize(b, "SCAN_B"),
        "eligibility_transitions": (
            ab["eligibility_transition"].value_counts().to_dict()
        ),
        "symbols_improved_A_to_B": ab.loc[
            (ab["eligibility_state_A"] == "INSUFFICIENT_DATA")
            & (ab["eligibility_state_B"] == "ELIGIBLE"),
            "symbol"
        ].tolist(),
        "symbols_insufficient_both": ab.loc[
            (ab["eligibility_state_A"] == "INSUFFICIENT_DATA")
            & (ab["eligibility_state_B"] == "INSUFFICIENT_DATA"),
            "symbol"
        ].tolist(),
        "notes": [
            "PM density and staleness statistics are descriptive only.",
            "No sparse/stale eligibility threshold is applied by this validator.",
            "Use empirical multi-date distributions before defining STALE thresholds.",
        ],
    }

    a_out = output_root / f"{trade_date}_scan_a_symbol_diagnostics.csv"
    b_out = output_root / f"{trade_date}_scan_b_symbol_diagnostics.csv"
    ab_out = output_root / f"{trade_date}_scan_a_vs_b.csv"
    summary_out = output_root / f"{trade_date}_validation_summary.json"

    a.to_csv(a_out, index=False)
    b.to_csv(b_out, index=False)
    ab.to_csv(ab_out, index=False)
    summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("=== PMS SNAPSHOT CANARY VALIDATION ===")
    print(json.dumps(summary, indent=2))
    print()
    print("Outputs:")
    print(f"  {a_out}")
    print(f"  {b_out}")
    print(f"  {ab_out}")
    print(f"  {summary_out}")


if __name__ == "__main__":
    main()
