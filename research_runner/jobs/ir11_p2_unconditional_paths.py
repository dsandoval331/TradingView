"""
IR-11 P2 — Unconditional Forward Paths

Research-only job for Extreme Premarket Gap Reversal Research.

Inputs
------
- market_cache/MARKET_CACHE_V1/1m/{SYMBOL}/{YEAR}.parquet
- research_outputs/ir11/p1/ir11_p1_dense_clock_observations_2025_v1.parquet

Outputs
-------
research_outputs/ir11/p2/
    ir11_p2_forward_paths_2025_v1.parquet
    ir11_p2_forward_paths_2025_v1.csv
    ir11_p2_pairwise_outcomes_2025_v1.parquet
    ir11_p2_pairwise_summary_by_clock_2025_v1.csv
    ir11_p2_pairwise_summary_by_clock_rawbin_2025_v1.csv
    ir11_p2_pairwise_summary_by_clock_relative_top5_2025_v1.csv
    ir11_p2_clock_path_summary_2025_v1.csv

Methodology notes
-----------------
1. No event threshold is selected from outcomes. P2 evaluates every P1 clock observation.
2. The P1 reference price is preserved exactly.
3. Massive 1-minute aggregate timestamps identify the minute bucket start. Therefore,
   if the reference bar is stamped exactly at the nominal clock, its close is only known
   at the end of that minute. `decision_time_et` is defined as the later of:
       nominal clock time
       reference_timestamp_et + 1 minute
   This prevents using a bar close before it is observable.
4. Future scanning starts at/after decision_time_et and ends at 16:00 ET.
5. Short-side favorable excursion = price DOWN from the reference.
   Adverse excursion = price UP from the reference.
6. If favorable and adverse thresholds are both touched inside the same 1-minute bar,
   intrabar order is unknowable from OHLC and the pair is classified
   AMBIGUOUS_SAME_BAR.
7. "PRE" versus "RTH" completion is determined from the timestamp of the first hit.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from datetime import time
import numpy as np
import pandas as pd


CACHE_ROOT = Path("market_cache/MARKET_CACHE_V1/1m")
P1_PATH = Path("research_outputs/ir11/p1/ir11_p1_dense_clock_observations_2025_v1.parquet")
OUT_ROOT = Path("research_outputs/ir11/p2")

FAVORABLE_THRESHOLDS = (0.10, 0.25, 0.50, 0.75, 1.00)
ADVERSE_THRESHOLDS = (0.10, 0.25, 0.50, 0.75, 1.00)

PRIMARY_PAIRS = (
    (0.50, 0.25),
    (0.50, 0.50),
    (0.75, 0.50),
    (1.00, 0.50),
)


def pct_tag(x: float) -> str:
    return f"{x:.2f}".replace(".", "p")


def target_clock_ts(trade_date, clock: str) -> pd.Timestamp:
    return pd.Timestamp(
        f"{trade_date} {clock}:00",
        tz="America/New_York",
    )


def classify_session(ts: pd.Timestamp | pd.NaT) -> str | None:
    if pd.isna(ts):
        return None
    t = ts.tz_convert("America/New_York").time()
    if t < time(9, 30):
        return "PRE"
    if t < time(16, 0):
        return "RTH"
    return "POST_RTH"


def first_hit_time(
    future: pd.DataFrame,
    *,
    reference_price: float,
    threshold_pct: float,
    favorable: bool,
) -> pd.Timestamp | pd.NaT:
    if future.empty:
        return pd.NaT

    if favorable:
        level = reference_price * (1.0 - threshold_pct / 100.0)
        hit = future["low"] <= level
    else:
        level = reference_price * (1.0 + threshold_pct / 100.0)
        hit = future["high"] >= level

    if not hit.any():
        return pd.NaT

    return future.loc[hit, "timestamp_et"].iloc[0]


def first_passage_outcome(
    fav_ts: pd.Timestamp | pd.NaT,
    adv_ts: pd.Timestamp | pd.NaT,
) -> str:
    if pd.isna(fav_ts) and pd.isna(adv_ts):
        return "NEITHER"
    if pd.isna(adv_ts):
        return "FAVORABLE_FIRST"
    if pd.isna(fav_ts):
        return "ADVERSE_FIRST"
    if fav_ts == adv_ts:
        return "AMBIGUOUS_SAME_BAR"
    if fav_ts < adv_ts:
        return "FAVORABLE_FIRST"
    return "ADVERSE_FIRST"


def minutes_from(decision_ts: pd.Timestamp, event_ts: pd.Timestamp | pd.NaT) -> float:
    if pd.isna(event_ts):
        return np.nan
    return (event_ts - decision_ts).total_seconds() / 60.0


def load_symbol_years(symbol: str, years: list[int]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for year in years:
        path = CACHE_ROOT / symbol / f"{year}.parquet"
        if path.exists():
            frames.append(
                pd.read_parquet(
                    path,
                    columns=[
                        "symbol",
                        "timestamp_et",
                        "trade_date",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "transactions",
                        "session",
                    ],
                )
            )

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values("timestamp_et").copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df


def build_paths(p1: pd.DataFrame, output_year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    p1 = p1.copy()
    p1["trade_date"] = pd.to_datetime(p1["trade_date"]).dt.date

    symbols = sorted(p1["symbol"].unique())
    path_rows: list[dict] = []
    pair_rows: list[dict] = []

    for i, symbol in enumerate(symbols, 1):
        obs_sym = p1[p1["symbol"] == symbol].sort_values(["trade_date", "clock"]).copy()

        # Output year is sufficient for forward paths because all decisions occur within
        # the same trade date and stop by 16:00 ET.
        raw = load_symbol_years(symbol, [output_year])

        if raw.empty:
            print(f"[{i:03d}/{len(symbols)}] {symbol}: CACHE MISSING")
            continue

        by_date = {
            d: g.sort_values("timestamp_et").copy()
            for d, g in raw.groupby("trade_date", sort=False)
        }

        built = 0

        for _, obs in obs_sym.iterrows():
            trade_date = obs["trade_date"]
            day = by_date.get(trade_date)

            if day is None or day.empty:
                continue

            clock_ts = target_clock_ts(trade_date, str(obs["clock"]))
            ref_bar_ts = pd.Timestamp(obs["reference_timestamp_et"])

            # 1-minute aggregates are start-stamped; close becomes observable one minute later.
            decision_time = max(clock_ts, ref_bar_ts + pd.Timedelta(minutes=1))

            rth_end = pd.Timestamp(
                f"{trade_date} 16:00:00",
                tz="America/New_York",
            )

            future = day[
                (day["timestamp_et"] >= decision_time)
                & (day["timestamp_et"] < rth_end)
                & (day["session"].isin(["PRE", "RTH"]))
            ].copy()

            reference_price = float(obs["reference_price"])

            base = {
                "symbol": symbol,
                "trade_date": trade_date,
                "clock": str(obs["clock"]),
                "reference_price": reference_price,
                "reference_timestamp_et": ref_bar_ts,
                "nominal_clock_et": clock_ts,
                "decision_time_et": decision_time,
                "decision_delay_from_clock_min": (
                    decision_time - clock_ts
                ).total_seconds() / 60.0,
                "staleness_minutes": float(obs["staleness_minutes"]),
                "displacement_pct": float(obs["displacement_pct"]),
                "pm_high_extension_pct": float(obs["pm_high_extension_pct"]),
                "from_pm_high_pct": float(obs["from_pm_high_pct"]),
                "reversal_consumed_pct": float(obs["reversal_consumed_pct"]),
                "trailing60_percentile": (
                    float(obs["trailing60_percentile"])
                    if pd.notna(obs["trailing60_percentile"])
                    else np.nan
                ),
                "trailing60_zscore": (
                    float(obs["trailing60_zscore"])
                    if pd.notna(obs["trailing60_zscore"])
                    else np.nan
                ),
                "raw_displacement_bin": str(obs["raw_displacement_bin"]),
                "relative_top5_trailing60": bool(obs["relative_top5_trailing60"]),
                "relative_top1_trailing60": bool(obs["relative_top1_trailing60"]),
                "future_bar_count": int(len(future)),
            }

            if future.empty:
                base.update(
                    {
                        "mfe_short_pct": np.nan,
                        "mae_short_pct": np.nan,
                        "time_to_mfe_min": np.nan,
                        "time_to_mae_min": np.nan,
                        "close_0930": np.nan,
                        "close_1600_last": np.nan,
                    }
                )
                for t in FAVORABLE_THRESHOLDS:
                    tag = pct_tag(t)
                    base[f"fav_{tag}_ts"] = pd.NaT
                    base[f"fav_{tag}_min"] = np.nan
                    base[f"fav_{tag}_session"] = None
                for t in ADVERSE_THRESHOLDS:
                    tag = pct_tag(t)
                    base[f"adv_{tag}_ts"] = pd.NaT
                    base[f"adv_{tag}_min"] = np.nan
                    base[f"adv_{tag}_session"] = None

                path_rows.append(base)
                continue

            future_min_idx = future["low"].idxmin()
            future_max_idx = future["high"].idxmax()

            min_low = float(future.loc[future_min_idx, "low"])
            max_high = float(future.loc[future_max_idx, "high"])
            min_low_ts = future.loc[future_min_idx, "timestamp_et"]
            max_high_ts = future.loc[future_max_idx, "timestamp_et"]

            mfe_short_pct = (reference_price - min_low) / reference_price * 100.0
            mae_short_pct = (max_high - reference_price) / reference_price * 100.0

            base.update(
                {
                    "mfe_short_pct": mfe_short_pct,
                    "mae_short_pct": mae_short_pct,
                    "time_to_mfe_min": minutes_from(decision_time, min_low_ts),
                    "time_to_mae_min": minutes_from(decision_time, max_high_ts),
                    "mfe_timestamp_et": min_low_ts,
                    "mae_timestamp_et": max_high_ts,
                }
            )

            # Opening state: last close available before 09:31, so the 09:30 bar
            # can contribute only after that minute has completed.
            after_open_cut = pd.Timestamp(
                f"{trade_date} 09:31:00",
                tz="America/New_York",
            )
            open_state = day[
                (day["timestamp_et"] < after_open_cut)
                & (day["session"] == "RTH")
            ]

            base["close_0930"] = (
                float(open_state["close"].iloc[-1])
                if not open_state.empty
                else np.nan
            )
            base["close_1600_last"] = float(future["close"].iloc[-1])

            fav_times: dict[float, pd.Timestamp | pd.NaT] = {}
            adv_times: dict[float, pd.Timestamp | pd.NaT] = {}

            for threshold in FAVORABLE_THRESHOLDS:
                ts = first_hit_time(
                    future,
                    reference_price=reference_price,
                    threshold_pct=threshold,
                    favorable=True,
                )
                fav_times[threshold] = ts
                tag = pct_tag(threshold)
                base[f"fav_{tag}_ts"] = ts
                base[f"fav_{tag}_min"] = minutes_from(decision_time, ts)
                base[f"fav_{tag}_session"] = classify_session(ts)

            for threshold in ADVERSE_THRESHOLDS:
                ts = first_hit_time(
                    future,
                    reference_price=reference_price,
                    threshold_pct=threshold,
                    favorable=False,
                )
                adv_times[threshold] = ts
                tag = pct_tag(threshold)
                base[f"adv_{tag}_ts"] = ts
                base[f"adv_{tag}_min"] = minutes_from(decision_time, ts)
                base[f"adv_{tag}_session"] = classify_session(ts)

            path_rows.append(base)

            for fav_t in FAVORABLE_THRESHOLDS:
                for adv_t in ADVERSE_THRESHOLDS:
                    outcome = first_passage_outcome(
                        fav_times[fav_t],
                        adv_times[adv_t],
                    )

                    pair_rows.append(
                        {
                            **{
                                k: base[k]
                                for k in [
                                    "symbol",
                                    "trade_date",
                                    "clock",
                                    "reference_price",
                                    "decision_time_et",
                                    "decision_delay_from_clock_min",
                                    "staleness_minutes",
                                    "displacement_pct",
                                    "pm_high_extension_pct",
                                    "from_pm_high_pct",
                                    "reversal_consumed_pct",
                                    "trailing60_percentile",
                                    "trailing60_zscore",
                                    "raw_displacement_bin",
                                    "relative_top5_trailing60",
                                    "relative_top1_trailing60",
                                ]
                            },
                            "favorable_threshold_pct": fav_t,
                            "adverse_threshold_pct": adv_t,
                            "favorable_hit_ts": fav_times[fav_t],
                            "adverse_hit_ts": adv_times[adv_t],
                            "favorable_hit_min": minutes_from(
                                decision_time, fav_times[fav_t]
                            ),
                            "adverse_hit_min": minutes_from(
                                decision_time, adv_times[adv_t]
                            ),
                            "favorable_hit_session": classify_session(
                                fav_times[fav_t]
                            ),
                            "adverse_hit_session": classify_session(
                                adv_times[adv_t]
                            ),
                            "first_passage_outcome": outcome,
                            "is_primary_pair": (fav_t, adv_t) in PRIMARY_PAIRS,
                        }
                    )

            built += 1

        print(
            f"[{i:03d}/{len(symbols)}] {symbol}: "
            f"{built:,} observation paths"
        )

    return pd.DataFrame(path_rows), pd.DataFrame(pair_rows)


def outcome_summary(
    pairs: pd.DataFrame,
    group_cols: list[str],
) -> pd.DataFrame:
    work = pairs.copy()
    work["resolved"] = work["first_passage_outcome"].isin(
        ["FAVORABLE_FIRST", "ADVERSE_FIRST"]
    )
    work["favorable_first"] = work["first_passage_outcome"] == "FAVORABLE_FIRST"
    work["adverse_first"] = work["first_passage_outcome"] == "ADVERSE_FIRST"
    work["ambiguous"] = work["first_passage_outcome"] == "AMBIGUOUS_SAME_BAR"
    work["neither"] = work["first_passage_outcome"] == "NEITHER"

    keys = group_cols + ["favorable_threshold_pct", "adverse_threshold_pct"]

    out = (
        work.groupby(keys, dropna=False)
        .agg(
            n=("symbol", "size"),
            symbols=("symbol", "nunique"),
            favorable_first=("favorable_first", "sum"),
            adverse_first=("adverse_first", "sum"),
            ambiguous_same_bar=("ambiguous", "sum"),
            neither=("neither", "sum"),
            resolved=("resolved", "sum"),
            median_favorable_hit_min=("favorable_hit_min", "median"),
            median_adverse_hit_min=("adverse_hit_min", "median"),
        )
        .reset_index()
    )

    out["favorable_first_rate_all"] = out["favorable_first"] / out["n"]
    out["favorable_first_rate_resolved"] = np.where(
        out["resolved"] > 0,
        out["favorable_first"] / out["resolved"],
        np.nan,
    )
    out["ambiguous_rate"] = out["ambiguous_same_bar"] / out["n"]
    out["neither_rate"] = out["neither"] / out["n"]

    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument(
        "--p1-path",
        type=Path,
        default=P1_PATH,
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=OUT_ROOT,
    )
    args = parser.parse_args()

    args.out_root.mkdir(parents=True, exist_ok=True)

    p1 = pd.read_parquet(args.p1_path)
    p1["trade_year"] = pd.to_datetime(p1["trade_date"]).dt.year
    p1 = p1[p1["trade_year"] == args.year].copy()

    print("=" * 110)
    print("IR-11 P2 — UNCONDITIONAL FORWARD PATHS")
    print("=" * 110)
    print(f"P1 observations: {len(p1):,}")
    print(f"Symbols: {p1['symbol'].nunique()}")
    print(f"Dates: {pd.to_datetime(p1['trade_date']).dt.date.nunique()}")
    print()

    paths, pairs = build_paths(p1, args.year)

    path_parquet = args.out_root / f"ir11_p2_forward_paths_{args.year}_v1.parquet"
    path_csv = args.out_root / f"ir11_p2_forward_paths_{args.year}_v1.csv"
    pair_parquet = args.out_root / f"ir11_p2_pairwise_outcomes_{args.year}_v1.parquet"

    paths.to_parquet(path_parquet, index=False)
    paths.to_csv(path_csv, index=False)
    pairs.to_parquet(pair_parquet, index=False)

    clock_path_summary = (
        paths.groupby("clock")
        .agg(
            observations=("symbol", "size"),
            symbols=("symbol", "nunique"),
            median_mfe_short_pct=("mfe_short_pct", "median"),
            p75_mfe_short_pct=("mfe_short_pct", lambda x: x.quantile(0.75)),
            median_mae_short_pct=("mae_short_pct", "median"),
            p75_mae_short_pct=("mae_short_pct", lambda x: x.quantile(0.75)),
            median_decision_delay_min=("decision_delay_from_clock_min", "median"),
            p90_decision_delay_min=("decision_delay_from_clock_min", lambda x: x.quantile(0.90)),
        )
        .reset_index()
    )

    summary_clock = outcome_summary(pairs, ["clock"])
    summary_clock_rawbin = outcome_summary(
        pairs,
        ["clock", "raw_displacement_bin"],
    )
    summary_clock_top5 = outcome_summary(
        pairs[pairs["relative_top5_trailing60"]],
        ["clock"],
    )

    clock_path_summary.to_csv(
        args.out_root / f"ir11_p2_clock_path_summary_{args.year}_v1.csv",
        index=False,
    )
    summary_clock.to_csv(
        args.out_root / f"ir11_p2_pairwise_summary_by_clock_{args.year}_v1.csv",
        index=False,
    )
    summary_clock_rawbin.to_csv(
        args.out_root / f"ir11_p2_pairwise_summary_by_clock_rawbin_{args.year}_v1.csv",
        index=False,
    )
    summary_clock_top5.to_csv(
        args.out_root / f"ir11_p2_pairwise_summary_by_clock_relative_top5_{args.year}_v1.csv",
        index=False,
    )

    print()
    print("=" * 110)
    print("IR-11 P2 BUILD COMPLETE")
    print("=" * 110)
    print(f"Forward-path rows: {len(paths):,}")
    print(f"Pairwise rows: {len(pairs):,}")
    print()
    print("CLOCK PATH SUMMARY")
    print(clock_path_summary.to_string(index=False))

    primary = summary_clock[
        summary_clock.apply(
            lambda r: (
                float(r["favorable_threshold_pct"]),
                float(r["adverse_threshold_pct"]),
            ) in PRIMARY_PAIRS,
            axis=1,
        )
    ].copy()

    print()
    print("PRIMARY FIRST-PASSAGE PAIRS — ALL OBSERVATIONS")
    print(primary.to_string(index=False))

    primary_top5 = summary_clock_top5[
        summary_clock_top5.apply(
            lambda r: (
                float(r["favorable_threshold_pct"]),
                float(r["adverse_threshold_pct"]),
            ) in PRIMARY_PAIRS,
            axis=1,
        )
    ].copy()

    print()
    print("PRIMARY FIRST-PASSAGE PAIRS — TRAILING-60 TOP-5% EVENTS")
    print(primary_top5.to_string(index=False))

    print()
    print("FILES WRITTEN:")
    for p in [
        path_parquet,
        path_csv,
        pair_parquet,
        args.out_root / f"ir11_p2_clock_path_summary_{args.year}_v1.csv",
        args.out_root / f"ir11_p2_pairwise_summary_by_clock_{args.year}_v1.csv",
        args.out_root / f"ir11_p2_pairwise_summary_by_clock_rawbin_{args.year}_v1.csv",
        args.out_root / f"ir11_p2_pairwise_summary_by_clock_relative_top5_{args.year}_v1.csv",
    ]:
        print(p)

    print()
    print("RESEARCH GUARDRAILS:")
    print("- All P1 observations were evaluated; no winning threshold was selected.")
    print("- First-passage same-bar dual touches are AMBIGUOUS_SAME_BAR.")
    print("- Decision time accounts for start-stamped 1-minute bar availability.")
    print("- Quote/spread/fill costs are NOT modeled in P2.")


if __name__ == "__main__":
    main()
