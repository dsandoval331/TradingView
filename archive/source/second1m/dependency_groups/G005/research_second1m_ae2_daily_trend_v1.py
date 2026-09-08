from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


# =============================================================================
# CONFIG
# =============================================================================

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

CACHE_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_cache_v1"
)

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

INPUT_PATH = (
    RESEARCH_ROOT
    / "ae2_short_ma_warning_v1"
    / "ae2_short_ma_warning_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_daily_trend_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_daily_trend_features_v1.parquet"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_daily_trend_summary_v1.csv"
)

CONTINUOUS_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_daily_trend_continuous_v1.csv"
)

TEMPORAL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_daily_trend_temporal_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_daily_trend_quarter_v1.csv"
)


EXPECTED_SYMBOLS = 112


# =============================================================================
# SUMMARY HELPERS
# =============================================================================

def summarize_group(x: pd.DataFrame) -> dict:

    favorable_n = int(
        (x["outcome"] == "FAVORABLE_FIRST").sum()
    )

    adverse_n = int(
        (x["outcome"] == "ADVERSE_FIRST").sum()
    )

    both_n = int(
        (x["outcome"] == "BOTH_SAME_BAR").sum()
    )

    unresolved_n = int(
        (x["outcome"] == "UNRESOLVED").sum()
    )

    binary_n = favorable_n + adverse_n

    favorable_first_pct = (
        100.0 * favorable_n / binary_n
        if binary_n
        else np.nan
    )

    c3_confirmed_n = int(
        x["c3_confirmed"].sum()
    )

    c3_confirmation_pct = (
        100.0 * c3_confirmed_n / len(x)
        if len(x)
        else np.nan
    )

    return {
        "total_n": int(len(x)),
        "binary_n": binary_n,
        "favorable_n": favorable_n,
        "adverse_n": adverse_n,
        "both_n": both_n,
        "unresolved_n": unresolved_n,
        "favorable_first_pct": favorable_first_pct,
        "c3_confirmed_n": c3_confirmed_n,
        "c3_confirmation_pct": c3_confirmation_pct,
        "avg_mfe_pct": x["final_mfe_pct"].mean(),
        "avg_mae_pct": x["final_mae_pct"].mean(),
        "median_mfe_pct": x["final_mfe_pct"].median(),
        "median_mae_pct": x["final_mae_pct"].median(),
        "symbol_n": x["symbol"].nunique(),
        "trade_date_n": x["trade_date"].nunique(),
    }


def summarize(
    df: pd.DataFrame,
    group_cols: list[str],
) -> pd.DataFrame:

    rows = []

    for keys, x in df.groupby(
        group_cols,
        dropna=False,
    ):

        if not isinstance(keys, tuple):
            keys = (keys,)

        row = dict(zip(group_cols, keys))
        row.update(summarize_group(x))
        rows.append(row)

    return pd.DataFrame(rows)


def directional_value(
    direction: str,
    raw_value: float,
) -> float:

    if pd.isna(raw_value):
        return np.nan

    if direction == "BULL":
        return raw_value

    if direction == "BEAR":
        return -raw_value

    return np.nan


def aligned_state(
    value: float,
) -> str:

    if pd.isna(value):
        return "UNKNOWN"

    if value > 0:
        return "ALIGNED"

    if value < 0:
        return "OPPOSING"

    return "FLAT"


# =============================================================================
# DAILY BAR RECONSTRUCTION
# =============================================================================

def load_symbol_daily(
    symbol: str,
) -> pd.DataFrame:

    paths = sorted(
        CACHE_ROOT.rglob(
            f"{symbol}_*.parquet"
        )
    )

    if not paths:
        raise RuntimeError(
            f"No partitions found for {symbol}"
        )

    frames = []

    for path in paths:

        table = pq.read_table(
            path,
            columns=[
                "symbol",
                "trade_date",
                "timestamp_utc",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "session",
            ],
        )

        frames.append(
            table.to_pandas()
        )

    intraday = pd.concat(
        frames,
        ignore_index=True,
    )

    intraday["symbol"] = (
        intraday["symbol"]
        .astype(str)
        .str.upper()
    )

    intraday["trade_date"] = (
        pd.to_datetime(
            intraday["trade_date"]
        )
        .dt.date
    )

    intraday["timestamp_utc"] = pd.to_datetime(
        intraday["timestamp_utc"],
        utc=True,
    )

    # Higher-timeframe stock trend is based on completed RTH sessions.
    rth = intraday.loc[
        intraday["session"] == "RTH"
    ].copy()

    rth = rth.sort_values(
        [
            "trade_date",
            "timestamp_utc",
        ]
    )

    daily = (
        rth.groupby(
            "trade_date",
            as_index=False,
        )
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
    )

    daily = daily.sort_values(
        "trade_date"
    ).reset_index(drop=True)

    close = daily["close"].astype(float)

    # -------------------------------------------------------------------------
    # Completed-day returns
    # -------------------------------------------------------------------------

    daily["ret_1d_pct"] = (
        100.0
        * (
            close
            / close.shift(1)
            - 1.0
        )
    )

    for lookback in [
        3,
        5,
        10,
        20,
    ]:

        daily[
            f"ret_{lookback}d_pct"
        ] = (
            100.0
            * (
                close
                / close.shift(lookback)
                - 1.0
            )
        )

    # -------------------------------------------------------------------------
    # Daily moving averages
    #
    # These are calculated from completed daily closes.
    # At the intraday AE2 decision we will join the PRIOR day's values.
    # -------------------------------------------------------------------------

    daily["ema9"] = (
        close
        .ewm(
            span=9,
            adjust=False,
            min_periods=9,
        )
        .mean()
    )

    daily["ema20"] = (
        close
        .ewm(
            span=20,
            adjust=False,
            min_periods=20,
        )
        .mean()
    )

    daily["sma20"] = (
        close
        .rolling(
            20,
            min_periods=20,
        )
        .mean()
    )

    daily["ema9_slope_1d_pct"] = (
        100.0
        * (
            daily["ema9"]
            / daily["ema9"].shift(1)
            - 1.0
        )
    )

    daily["ema20_slope_1d_pct"] = (
        100.0
        * (
            daily["ema20"]
            / daily["ema20"].shift(1)
            - 1.0
        )
    )

    daily["close_vs_ema9_pct"] = (
        100.0
        * (
            close
            / daily["ema9"]
            - 1.0
        )
    )

    daily["close_vs_ema20_pct"] = (
        100.0
        * (
            close
            / daily["ema20"]
            - 1.0
        )
    )

    daily["ema9_vs_ema20_pct"] = (
        100.0
        * (
            daily["ema9"]
            / daily["ema20"]
            - 1.0
        )
    )

    daily["range_pct"] = (
        100.0
        * (
            daily["high"]
            - daily["low"]
        )
        / daily["open"]
    )

    # -------------------------------------------------------------------------
    # Shift every completed-day feature by one trading session.
    #
    # Example:
    # trade on Tuesday 09:31 can only use Monday's completed daily context.
    # -------------------------------------------------------------------------

    feature_cols = [
        "close",
        "ret_1d_pct",
        "ret_3d_pct",
        "ret_5d_pct",
        "ret_10d_pct",
        "ret_20d_pct",
        "ema9",
        "ema20",
        "sma20",
        "ema9_slope_1d_pct",
        "ema20_slope_1d_pct",
        "close_vs_ema9_pct",
        "close_vs_ema20_pct",
        "ema9_vs_ema20_pct",
        "range_pct",
    ]

    for col in feature_cols:

        daily[
            f"prior_{col}"
        ] = daily[col].shift(1)

    return daily


# =============================================================================
# MAIN
# =============================================================================

def main():

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input not found: "
            f"{INPUT_PATH}"
        )

    ae2 = pd.read_parquet(
        INPUT_PATH
    )

    ae2["symbol"] = (
        ae2["symbol"]
        .astype(str)
        .str.upper()
    )

    ae2["trade_date"] = pd.to_datetime(
        ae2["trade_date"]
    )

    symbols = sorted(
        ae2["symbol"].unique()
    )

    if len(symbols) != EXPECTED_SYMBOLS:
        raise RuntimeError(
            f"Expected {EXPECTED_SYMBOLS} symbols, "
            f"found {len(symbols)}"
        )

    print("=" * 80)
    print("AE2 DAILY STOCK TREND CONTEXT V1")
    print("=" * 80)

    print(
        f"AE2 events: "
        f"{len(ae2):,}"
    )

    print(
        f"Symbols:    "
        f"{len(symbols):,}"
    )

    enriched = []

    # =========================================================================
    # PROCESS SYMBOL-BY-SYMBOL
    # =========================================================================

    for i, symbol in enumerate(
        symbols,
        start=1,
    ):

        events = (
            ae2.loc[
                ae2["symbol"]
                == symbol
            ]
            .copy()
        )

        daily = load_symbol_daily(
            symbol
        )

        daily["trade_date"] = pd.to_datetime(
            daily["trade_date"]
        )

        merged = events.merge(
            daily,
            on="trade_date",
            how="left",
            suffixes=(
                "",
                "_daily",
            ),
        )

        enriched.append(
            merged
        )

        if (
            i % 10 == 0
            or i == len(symbols)
        ):

            enriched_n = sum(
                len(x)
                for x in enriched
            )

            print(
                f"Processed "
                f"{i:>3}/{len(symbols)} "
                f"| enriched="
                f"{enriched_n:,}"
            )

    df = pd.concat(
        enriched,
        ignore_index=True,
    )

    # =========================================================================
    # OPENING GAP
    #
    # Current day's 09:30 open is known by the C2 decision.
    # Previous RTH close is from the completed prior day.
    # =========================================================================

    df["gap_from_prior_close_pct"] = (
        100.0
        * (
            df["c1_open"]
            / df["prior_close"]
            - 1.0
        )
    )

    # =========================================================================
    # DIRECTION-NORMALIZED DAILY FEATURES
    # =========================================================================

    raw_features = [
        "prior_ret_1d_pct",
        "prior_ret_3d_pct",
        "prior_ret_5d_pct",
        "prior_ret_10d_pct",
        "prior_ret_20d_pct",
        "prior_close_vs_ema9_pct",
        "prior_close_vs_ema20_pct",
        "prior_ema9_vs_ema20_pct",
        "prior_ema9_slope_1d_pct",
        "prior_ema20_slope_1d_pct",
        "gap_from_prior_close_pct",
    ]

    directional_features = []

    for feature in raw_features:

        directional_col = (
            f"directional_{feature}"
        )

        df[
            directional_col
        ] = df.apply(
            lambda r:
                directional_value(
                    r["direction"],
                    r[feature],
                ),
            axis=1,
        )

        directional_features.append(
            directional_col
        )

    # =========================================================================
    # BINARY ALIGNMENT STATES
    # =========================================================================

    state_features = {}

    for feature in directional_features:

        state_col = (
            feature
            + "__state"
        )

        df[
            state_col
        ] = df[
            feature
        ].apply(
            aligned_state
        )

        state_features[
            feature
        ] = state_col

    # =========================================================================
    # BROAD DAILY TREND STATE
    #
    # No optimized thresholds.
    #
    # Three independent components:
    #   5D return
    #   prior close vs EMA20
    #   EMA9 vs EMA20
    #
    # Score is direction-normalized.
    # =========================================================================

    trend_components = [
        "directional_prior_ret_5d_pct",
        "directional_prior_close_vs_ema20_pct",
        "directional_prior_ema9_vs_ema20_pct",
    ]

    def trend_score(r):

        available = [
            r[x]
            for x in trend_components
            if not pd.isna(r[x])
        ]

        if len(available) < 3:
            return np.nan

        return sum(
            1 if x > 0
            else -1 if x < 0
            else 0
            for x in available
        )

    df[
        "daily_trend_score"
    ] = df.apply(
        trend_score,
        axis=1,
    )

    def trend_state(score):

        if pd.isna(score):
            return "UNKNOWN"

        if score >= 2:
            return "ALIGNED"

        if score <= -2:
            return "OPPOSING"

        return "MIXED"

    df[
        "daily_trend_state"
    ] = df[
        "daily_trend_score"
    ].apply(
        trend_state
    )

    # =========================================================================
    # RESEARCH PERIOD / QUARTER
    # =========================================================================

    df[
        "research_period"
    ] = df[
        "temporal_half"
    ].map(
        {
            "OLDEST_HALF":
                "DISCOVERY",

            "NEWEST_HALF":
                "VALIDATION",
        }
    )

    df[
        "quarter"
    ] = (
        df[
            "trade_date"
        ]
        .dt
        .to_period("Q")
        .astype(str)
    )

    # =========================================================================
    # STATE SUMMARY
    # =========================================================================

    summary_frames = []

    for feature, state_col in (
        state_features.items()
    ):

        all_dir = summarize(
            df,
            [
                "research_period",
                state_col,
            ],
        )

        all_dir[
            "direction"
        ] = "ALL"

        all_dir[
            "feature"
        ] = feature

        all_dir = (
            all_dir.rename(
                columns={
                    state_col:
                        "state"
                }
            )
        )

        by_dir = summarize(
            df,
            [
                "research_period",
                "direction",
                state_col,
            ],
        )

        by_dir[
            "feature"
        ] = feature

        by_dir = (
            by_dir.rename(
                columns={
                    state_col:
                        "state"
                }
            )
        )

        summary_frames.extend(
            [
                all_dir,
                by_dir,
            ]
        )

    # Broad trend state.
    trend_all = summarize(
        df,
        [
            "research_period",
            "daily_trend_state",
        ],
    )

    trend_all[
        "direction"
    ] = "ALL"

    trend_all[
        "feature"
    ] = (
        "DAILY_TREND_COMPOSITE"
    )

    trend_all = trend_all.rename(
        columns={
            "daily_trend_state":
                "state"
        }
    )

    trend_dir = summarize(
        df,
        [
            "research_period",
            "direction",
            "daily_trend_state",
        ],
    )

    trend_dir[
        "feature"
    ] = (
        "DAILY_TREND_COMPOSITE"
    )

    trend_dir = trend_dir.rename(
        columns={
            "daily_trend_state":
                "state"
        }
    )

    summary_frames.extend(
        [
            trend_all,
            trend_dir,
        ]
    )

    summary = pd.concat(
        summary_frames,
        ignore_index=True,
        sort=False,
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # CONTINUOUS WINNER / LOSER ANALYSIS
    # =========================================================================

    continuous_rows = []

    for feature in directional_features:

        for period, x in df.groupby(
            "research_period",
            dropna=False,
        ):

            winners = x.loc[
                x["outcome"]
                == "FAVORABLE_FIRST"
            ]

            losers = x.loc[
                x["outcome"]
                == "ADVERSE_FIRST"
            ]

            confirmed = x.loc[
                x["c3_confirmed"]
            ]

            not_confirmed = x.loc[
                ~x["c3_confirmed"]
            ]

            continuous_rows.append(
                {
                    "feature":
                        feature,

                    "research_period":
                        period,

                    "n":
                        len(x),

                    "winner_mean":
                        winners[
                            feature
                        ].mean(),

                    "loser_mean":
                        losers[
                            feature
                        ].mean(),

                    "outcome_difference":
                        winners[
                            feature
                        ].mean()
                        -
                        losers[
                            feature
                        ].mean(),

                    "confirmed_mean":
                        confirmed[
                            feature
                        ].mean(),

                    "not_confirmed_mean":
                        not_confirmed[
                            feature
                        ].mean(),

                    "confirmation_difference":
                        confirmed[
                            feature
                        ].mean()
                        -
                        not_confirmed[
                            feature
                        ].mean(),
                }
            )

    continuous_summary = (
        pd.DataFrame(
            continuous_rows
        )
    )

    continuous_summary.to_csv(
        CONTINUOUS_OUTPUT,
        index=False,
    )

    # =========================================================================
    # QUARTER COMPOSITE
    # =========================================================================

    quarter_all = summarize(
        df,
        [
            "quarter",
            "daily_trend_state",
        ],
    )

    quarter_all[
        "direction"
    ] = "ALL"

    quarter_dir = summarize(
        df,
        [
            "quarter",
            "direction",
            "daily_trend_state",
        ],
    )

    quarter_summary = pd.concat(
        [
            quarter_all,
            quarter_dir,
        ],
        ignore_index=True,
        sort=False,
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # TEMPORAL COMPOSITE OUTPUT
    # =========================================================================

    temporal = summary.loc[
        summary["feature"]
        == "DAILY_TREND_COMPOSITE"
    ].copy()

    temporal.to_csv(
        TEMPORAL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SAVE FEATURE DATASET
    # =========================================================================

    df.to_parquet(
        FEATURE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # REPORT
    # =========================================================================

    print()

    print("=" * 80)
    print("FEATURE COVERAGE")
    print("=" * 80)

    coverage_cols = [
        "prior_ret_1d_pct",
        "prior_ret_3d_pct",
        "prior_ret_5d_pct",
        "prior_ret_10d_pct",
        "prior_ret_20d_pct",
        "prior_close_vs_ema9_pct",
        "prior_close_vs_ema20_pct",
        "prior_ema9_vs_ema20_pct",
        "gap_from_prior_close_pct",
    ]

    for col in coverage_cols:

        n = int(
            df[col]
            .notna()
            .sum()
        )

        pct = (
            100.0
            * n
            / len(df)
        )

        print(
            f"{col:<35} "
            f"{n:>6,} "
            f"{pct:>7.2f}%"
        )

    print()

    print("=" * 80)
    print("DAILY TREND COMPOSITE — DISCOVERY VS VALIDATION")
    print("=" * 80)

    trend_display = (
        summary.loc[
            (
                summary["feature"]
                == "DAILY_TREND_COMPOSITE"
            )
            &
            (
                summary["direction"]
                == "ALL"
            )
        ]
    )

    print(
        trend_display[
            [
                "research_period",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    print()

    print("=" * 80)
    print("DAILY TREND COMPOSITE — VALIDATION DIRECTIONAL")
    print("=" * 80)

    trend_direction = (
        summary.loc[
            (
                summary["feature"]
                == "DAILY_TREND_COMPOSITE"
            )
            &
            (
                summary["research_period"]
                == "VALIDATION"
            )
            &
            (
                summary["direction"]
                != "ALL"
            )
        ]
    )

    print(
        trend_direction[
            [
                "direction",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "direction",
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    print()

    print("=" * 80)
    print("INDIVIDUAL DAILY STATES — VALIDATION")
    print("=" * 80)

    validation_states = (
        summary.loc[
            (
                summary[
                    "research_period"
                ]
                == "VALIDATION"
            )
            &
            (
                summary[
                    "direction"
                ]
                == "ALL"
            )
            &
            (
                summary[
                    "feature"
                ]
                != "DAILY_TREND_COMPOSITE"
            )
        ]
    )

    print(
        validation_states[
            [
                "feature",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "feature",
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    print()

    print("=" * 80)
    print("CONTINUOUS DAILY METRICS")
    print("=" * 80)

    print(
        continuous_summary.to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.4f}",
        )
    )

    print()

    print("=" * 80)
    print("OUTPUTS")
    print("=" * 80)

    print(
        f"Features:   "
        f"{FEATURE_OUTPUT}"
    )

    print(
        f"Summary:    "
        f"{SUMMARY_OUTPUT}"
    )

    print(
        f"Continuous: "
        f"{CONTINUOUS_OUTPUT}"
    )

    print(
        f"Temporal:   "
        f"{TEMPORAL_OUTPUT}"
    )

    print(
        f"Quarter:    "
        f"{QUARTER_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()