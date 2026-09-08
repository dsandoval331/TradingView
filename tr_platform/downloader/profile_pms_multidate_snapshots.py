from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from tr_platform.downloader.generate_pms_historical_snapshot import (
    MARKET_CACHE_VERSION,
    PMPD_112_V1,
    PartitionStore,
    generate_snapshot,
    repo_root,
)
from tr_platform.downloader.validate_pms_snapshot_canary import (
    extract_symbol_diagnostics,
)


def trading_dates_from_spy(
    store: PartitionStore,
    start_date: date,
    end_date: date,
) -> list[date]:
    frames = []
    for year in range(start_date.year, end_date.year + 1):
        try:
            df, _ = store.load("SPY", year)
            frames.append(df)
        except FileNotFoundError:
            continue

    if not frames:
        raise FileNotFoundError("No SPY partitions available for requested range.")

    spy = pd.concat(frames, ignore_index=True)
    mask = (
        (spy["_trade_date"] >= start_date)
        & (spy["_trade_date"] <= end_date)
    )

    # RTH presence defines a trading day for replay sampling.
    t = spy["_local_ts"].dt.time
    rth = spy.loc[
        mask
        & (t >= pd.Timestamp("08:30").time())
        & (t <= pd.Timestamp("15:00").time())
    ]

    return sorted(pd.unique(rth["_trade_date"]).tolist())


def deterministic_sample(dates: list[date], sample_size: int | None) -> list[date]:
    if not dates:
        return []
    if sample_size is None or sample_size >= len(dates):
        return dates
    if sample_size <= 0:
        raise ValueError("--sample-size must be > 0.")

    idx = np.linspace(0, len(dates) - 1, sample_size)
    idx = np.unique(np.rint(idx).astype(int))
    return [dates[i] for i in idx]


def json_to_obj(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


def prepare_for_diag(candidates: pd.DataFrame) -> pd.DataFrame:
    out = candidates.copy()
    for col in [
        "raw_features_json",
        "context_states_json",
        "gate_results_json",
        "missing_data_json",
        "explanation_json",
        "lineage_json",
    ]:
        if col in out.columns:
            out[col] = out[col].apply(json_to_obj)
    return out


def qstats(series: pd.Series) -> dict:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return {
            "count": 0, "min": None, "p05": None, "p10": None, "p25": None,
            "median": None, "p75": None, "p90": None, "p95": None,
            "max": None, "mean": None,
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


def summarize_snapshot(diag: pd.DataFrame) -> dict:
    return {
        "observations": int(len(diag)),
        "dates": int(diag["trade_date"].nunique()),
        "symbols": int(diag["symbol"].nunique()),
        "eligibility_counts": {
            str(k): int(v)
            for k, v in diag["eligibility_state"].value_counts().to_dict().items()
        },
        "eligibility_rate_pct": float(
            (diag["eligibility_state"] == "ELIGIBLE").mean() * 100
        ),
        "exact_cutoff_rate_pct": float(
            pd.to_numeric(
                diag["pm_exact_cutoff_bar_present"].astype("boolean"),
                errors="coerce",
            ).mean() * 100
        ),
        "pm_bar_count_stats": qstats(diag["pm_bar_count"]),
        "pm_density_pct_stats": qstats(diag["pm_observed_minute_density_pct"]),
        "pm_staleness_minutes_stats": qstats(diag["pm_staleness_minutes_at_cutoff"]),
    }


def symbol_profile(all_diag: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (snapshot_code, symbol), g in all_diag.groupby(
        ["snapshot_code", "symbol"], sort=True
    ):
        eligible = g["eligibility_state"] == "ELIGIBLE"
        insufficient = g["eligibility_state"] == "INSUFFICIENT_DATA"
        exact = g["pm_exact_cutoff_bar_present"].astype("boolean")

        rows.append({
            "snapshot_code": snapshot_code,
            "symbol": symbol,
            "dates_observed": int(g["trade_date"].nunique()),
            "eligible_days": int(eligible.sum()),
            "insufficient_days": int(insufficient.sum()),
            "eligible_rate_pct": float(eligible.mean() * 100),
            "exact_cutoff_rate_pct": float(exact.mean() * 100),
            "median_pm_bar_count": float(
                pd.to_numeric(g["pm_bar_count"], errors="coerce").median()
            ),
            "median_pm_density_pct": float(
                pd.to_numeric(
                    g["pm_observed_minute_density_pct"], errors="coerce"
                ).median()
            ),
            "median_staleness_minutes": float(
                pd.to_numeric(
                    g["pm_staleness_minutes_at_cutoff"], errors="coerce"
                ).median()
            ),
            "max_staleness_minutes": float(
                pd.to_numeric(
                    g["pm_staleness_minutes_at_cutoff"], errors="coerce"
                ).max()
            ),
        })

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic multi-date PMS-3 SCAN_A/SCAN_B replay and "
            "profile empirical premarket observation quality."
        )
    )
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help=(
            "Evenly spaced trading dates from the requested range. "
            "Use 0 only if you want an error; omit for default 20. "
            "Set >= total dates to replay all dates."
        ),
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Optional symbol subset. Default: PMPD_112_V1.",
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    if end_date < start_date:
        raise ValueError("--end-date must be >= --start-date.")

    root = repo_root()
    cache_root = (
        args.cache_root
        if args.cache_root is not None
        else root / "market_cache" / MARKET_CACHE_VERSION
    )
    output_root = (
        args.output_root
        if args.output_root is not None
        else root / "research_outputs" / "pms_multidate_profile"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    store = PartitionStore(cache_root)
    all_dates = trading_dates_from_spy(store, start_date, end_date)
    selected_dates = deterministic_sample(all_dates, args.sample_size)
    symbols = [s.upper().strip() for s in (args.symbols or PMPD_112_V1)]

    if not selected_dates:
        raise RuntimeError("No trading dates selected.")

    print("=== PMS MULTI-DATE REPLAY ===")
    print(f"Requested range: {start_date} -> {end_date}")
    print(f"Available trading dates: {len(all_dates)}")
    print(f"Selected trading dates: {len(selected_dates)}")
    print("Selected:")
    for d in selected_dates:
        print(f"  {d}")
    print(f"Symbols: {len(symbols)}")

    all_diag_frames = []
    replay_rows = []

    for date_idx, trade_date in enumerate(selected_dates, start=1):
        for snapshot_code in ["SCAN_A", "SCAN_B"]:
            print()
            print(
                f"=== [{date_idx}/{len(selected_dates)}] "
                f"{trade_date} {snapshot_code} ==="
            )

            candidates, meta = generate_snapshot(
                store=store,
                trade_date=trade_date,
                snapshot_code=snapshot_code,
                symbols=symbols,
            )

            diag = extract_symbol_diagnostics(
                prepare_for_diag(candidates),
                snapshot_code,
            )
            diag.insert(0, "trade_date", trade_date.isoformat())
            all_diag_frames.append(diag)

            elig_counts = (
                diag["eligibility_state"].value_counts().to_dict()
            )
            replay_rows.append({
                "trade_date": trade_date.isoformat(),
                "snapshot_code": snapshot_code,
                "symbols": len(symbols),
                "candidate_rows": int(len(candidates)),
                "eligible_symbols": int(
                    elig_counts.get("ELIGIBLE", 0)
                ),
                "insufficient_symbols": int(
                    elig_counts.get("INSUFFICIENT_DATA", 0)
                ),
            })

    all_diag = pd.concat(all_diag_frames, ignore_index=True)
    replay = pd.DataFrame(replay_rows)
    profiles = symbol_profile(all_diag)

    summary = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "available_trading_dates": len(all_dates),
        "selected_trading_dates": [d.isoformat() for d in selected_dates],
        "selected_date_count": len(selected_dates),
        "symbol_count": len(symbols),
        "scan_a": summarize_snapshot(
            all_diag.loc[all_diag["snapshot_code"] == "SCAN_A"]
        ),
        "scan_b": summarize_snapshot(
            all_diag.loc[all_diag["snapshot_code"] == "SCAN_B"]
        ),
        "persistent_insufficient": {},
        "notes": [
            "Premarket density and staleness are descriptive only.",
            "No STALE threshold is applied.",
            "The purpose of this replay is empirical quality profiling before policy selection.",
            "Composite strategy weights remain unassigned research hypotheses.",
        ],
    }

    for snapshot_code in ["SCAN_A", "SCAN_B"]:
        p = profiles.loc[profiles["snapshot_code"] == snapshot_code]
        persistent = p.loc[
            p["insufficient_days"] > 0,
            [
                "symbol",
                "dates_observed",
                "insufficient_days",
                "eligible_rate_pct",
                "median_pm_bar_count",
                "median_pm_density_pct",
                "median_staleness_minutes",
                "max_staleness_minutes",
            ],
        ].sort_values(
            ["insufficient_days", "symbol"],
            ascending=[False, True],
        )
        summary["persistent_insufficient"][snapshot_code] = (
            persistent.to_dict(orient="records")
        )

    stem = (
        f"{start_date.isoformat()}_{end_date.isoformat()}_"
        f"{len(selected_dates)}dates"
    )

    diag_path = output_root / f"{stem}_symbol_date_diagnostics.csv"
    profile_path = output_root / f"{stem}_symbol_profiles.csv"
    replay_path = output_root / f"{stem}_replay_summary.csv"
    summary_path = output_root / f"{stem}_summary.json"

    all_diag.to_csv(diag_path, index=False)
    profiles.to_csv(profile_path, index=False)
    replay.to_csv(replay_path, index=False)
    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print()
    print("=== PMS MULTI-DATE PROFILE COMPLETE ===")
    print(json.dumps(summary, indent=2))
    print()
    print("Outputs:")
    print(f"  {diag_path}")
    print(f"  {profile_path}")
    print(f"  {replay_path}")
    print(f"  {summary_path}")


if __name__ == "__main__":
    main()
