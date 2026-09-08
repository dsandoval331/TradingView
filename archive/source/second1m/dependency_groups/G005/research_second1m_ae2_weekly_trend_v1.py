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
    / "ae2_trend_exhaustion_robustness_v1"
    / "trend_exhaustion_states_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_weekly_trend_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_weekly_trend_features_v1.parquet"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_weekly_trend_summary_v1.csv"
)

CONTINUOUS_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_weekly_trend_continuous_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_weekly_trend_quarter_v1.csv"
)

COVERAGE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_weekly_trend_coverage_v1.csv"
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

    binary_n = (
        favorable_n
        + adverse_n
    )

    favorable_first_pct = (
        100.0
        * favorable_n
        / binary_n
        if binary_n
        else np.nan
    )

    c3_confirmed_n = int(
        x["c3_confirmed"].sum()
    )

    c3_confirmation_pct = (
        100.0
        * c3_confirmed_n
        / len(x)
        if len(x)
        else np.nan
    )

    return {
        "total_n":
            int(len(x)),

        "binary_n":
            binary_n,

        "favorable_n":
            favorable_n,

        "adverse_n":
            adverse_n,

        "both_n":
            both_n,

        "unresolved_n":
            unresolved_n,

        "favorable_first_pct":
            favorable_first_pct,

        "c3_confirmed_n":
            c3_confirmed_n,

        "c3_confirmation_pct":
            c3_confirmation_pct,

        "avg_mfe_pct":
            x["final_mfe_pct"].mean(),

        "avg_mae_pct":
            x["final_mae_pct"].mean(),

        "median_mfe_pct":
            x["final_mfe_pct"].median(),

        "median_mae_pct":
            x["final_mae_pct"].median(),

        "symbol_n":
            x["symbol"].nunique(),

        "trade_date_n":
            x["trade_date"].nunique(),
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

        row = dict(
            zip(
                group_cols,
                keys,
            )
        )

        row.update(
            summarize_group(x)
        )

        rows.append(row)

    return pd.DataFrame(rows)


def directional_value(
    direction: str,
    raw_value: float,
) -> float:

    if pd.isna(raw_value):
        return np.nan

    if direction == "BULL":
        return float(raw_value)

    if direction == "BEAR":
        return -float(raw_value)

    return np.nan


def alignment_state(
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
# RECONSTRUCT COMPLETED WEEKLY BARS
# =============================================================================

def load_symbol_weekly(
    symbol: str,
) -> pd.DataFrame:

    paths = sorted(
        CACHE_ROOT.rglob(
            f"{symbol}_*.parquet"
        )
    )

    if not paths:
        raise RuntimeError(
            f"No cache partitions found for {symbol}"
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

    intraday["trade_date"] = pd.to_datetime(
        intraday["trade_date"]
    )

    intraday["timestamp_utc"] = pd.to_datetime(
        intraday["timestamp_utc"],
        utc=True,
    )

    # Weekly context is reconstructed from completed RTH sessions only.
    rth = intraday.loc[
        intraday["session"] == "RTH"
    ].copy()

    rth = rth.sort_values(
        [
            "trade_date",
            "timestamp_utc",
        ]
    )

    # -------------------------------------------------------------------------
    # Reconstruct daily RTH bars.
    # -------------------------------------------------------------------------

    daily = (
        rth.groupby(
            "trade_date",
            as_index=False,
        )
        .agg(
            daily_open=("open", "first"),
            daily_high=("high", "max"),
            daily_low=("low", "min"),
            daily_close=("close", "last"),
            daily_volume=("volume", "sum"),
        )
    )

    daily = daily.sort_values(
        "trade_date"
    ).reset_index(drop=True)

    # Friday-ended calendar week.
    daily["week_end"] = (
        daily["trade_date"]
        .dt
        .to_period("W-FRI")
        .dt
        .end_time
        .dt
        .normalize()
    )

    # -------------------------------------------------------------------------
    # Reconstruct weekly OHLCV.
    # -------------------------------------------------------------------------

    weekly = (
        daily.groupby(
            "week_end",
            as_index=False,
        )
        .agg(
            week_open=("daily_open", "first"),
            week_high=("daily_high", "max"),
            week_low=("daily_low", "min"),
            week_close=("daily_close", "last"),
            week_volume=("daily_volume", "sum"),
            trading_days_in_week=("trade_date", "nunique"),
            actual_last_trade_date=("trade_date", "max"),
        )
    )

    weekly = weekly.sort_values(
        "week_end"
    ).reset_index(drop=True)

    close = weekly[
        "week_close"
    ].astype(float)

    # -------------------------------------------------------------------------
    # Completed-week returns.
    # -------------------------------------------------------------------------

    for lookback in [
        1,
        2,
        4,
        8,
    ]:

        weekly[
            f"ret_{lookback}w_pct"
        ] = (
            100.0
            * (
                close
                / close.shift(lookback)
                - 1.0
            )
        )

    # -------------------------------------------------------------------------
    # Weekly moving averages.
    # -------------------------------------------------------------------------

    weekly["ema9"] = (
        close
        .ewm(
            span=9,
            adjust=False,
            min_periods=9,
        )
        .mean()
    )

    weekly["ema20"] = (
        close
        .ewm(
            span=20,
            adjust=False,
            min_periods=20,
        )
        .mean()
    )

    weekly["sma9"] = (
        close
        .rolling(
            window=9,
            min_periods=9,
        )
        .mean()
    )

    weekly["sma20"] = (
        close
        .rolling(
            window=20,
            min_periods=20,
        )
        .mean()
    )

    weekly["close_vs_ema9_pct"] = (
        100.0
        * (
            close
            / weekly["ema9"]
            - 1.0
        )
    )

    weekly["close_vs_ema20_pct"] = (
        100.0
        * (
            close
            / weekly["ema20"]
            - 1.0
        )
    )

    weekly["ema9_vs_ema20_pct"] = (
        100.0
        * (
            weekly["ema9"]
            / weekly["ema20"]
            - 1.0
        )
    )

    weekly["close_vs_sma20_pct"] = (
        100.0
        * (
            close
            / weekly["sma20"]
            - 1.0
        )
    )

    weekly["ema9_slope_1w_pct"] = (
        100.0
        * (
            weekly["ema9"]
            / weekly["ema9"].shift(1)
            - 1.0
        )
    )

    weekly["ema20_slope_1w_pct"] = (
        100.0
        * (
            weekly["ema20"]
            / weekly["ema20"].shift(1)
            - 1.0
        )
    )

    weekly["range_pct"] = (
        100.0
        * (
            weekly["week_high"]
            - weekly["week_low"]
        )
        / weekly["week_open"]
    )

    # -------------------------------------------------------------------------
    # IMPORTANT:
    #
    # The AE2 input file already contains daily/intraday MA columns with names
    # such as:
    #
    #   ema9
    #   ema20
    #   close_vs_ema9_pct
    #   close_vs_ema20_pct
    #   ema9_vs_ema20_pct
    #
    # Prefix every weekly-derived field so merge_asof cannot create _x / _y
    # collisions.
    #
    # week_end remains unprefixed because it is the as-of merge key.
    # -------------------------------------------------------------------------

    weekly = weekly.rename(
        columns={
            col: f"weekly_{col}"
            for col in weekly.columns
            if col != "week_end"
        }
    )

    return weekly


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
            f"Input not found: {INPUT_PATH}"
        )

    events = pd.read_parquet(
        INPUT_PATH
    )

    events["symbol"] = (
        events["symbol"]
        .astype(str)
        .str.upper()
    )

    events["trade_date"] = (
        pd.to_datetime(
            events["trade_date"]
        )
        .dt
        .normalize()
    )

    symbols = sorted(
        events["symbol"].unique()
    )

    if len(symbols) != EXPECTED_SYMBOLS:
        raise RuntimeError(
            f"Expected {EXPECTED_SYMBOLS} symbols, "
            f"found {len(symbols)}"
        )

    print("=" * 80)
    print("AE2 WEEKLY STOCK TREND CONTEXT V1")
    print("=" * 80)

    print(
        f"AE2 events: "
        f"{len(events):,}"
    )

    print(
        f"Symbols:    "
        f"{len(symbols):,}"
    )

    enriched_frames = []

    # =========================================================================
    # ENRICH SYMBOL BY SYMBOL
    # =========================================================================

    for i, symbol in enumerate(
        symbols,
        start=1,
    ):

        symbol_events = (
            events.loc[
                events["symbol"]
                == symbol
            ]
            .copy()
            .sort_values(
                "trade_date"
            )
        )

        weekly = load_symbol_weekly(
            symbol
        )

        weekly = weekly.sort_values(
            "week_end"
        )

        # ---------------------------------------------------------------------
        # LEAKAGE GUARD
        #
        # merge_asof chooses the most recent week_end strictly before the trade
        # date.
        #
        # Friday 09:31 cannot use Friday's completed weekly bar.
        # Monday-Thursday cannot use the unfinished current week's bar either.
        # ---------------------------------------------------------------------

        merged = pd.merge_asof(
            symbol_events,
            weekly,
            left_on="trade_date",
            right_on="week_end",
            direction="backward",
            allow_exact_matches=False,
        )

        enriched_frames.append(
            merged
        )

        if (
            i % 10 == 0
            or i == len(symbols)
        ):

            enriched_n = sum(
                len(x)
                for x in enriched_frames
            )

            print(
                f"Processed "
                f"{i:>3}/{len(symbols)} "
                f"| enriched="
                f"{enriched_n:,}"
            )

    df = pd.concat(
        enriched_frames,
        ignore_index=True,
    )

    if len(df) != len(events):
        raise RuntimeError(
            "Weekly enrichment changed event count: "
            f"{len(events):,} -> {len(df):,}"
        )

    # =========================================================================
    # DIRECTION-NORMALIZED WEEKLY FEATURES
    # =========================================================================

    raw_features = [
        "weekly_ret_1w_pct",
        "weekly_ret_2w_pct",
        "weekly_ret_4w_pct",
        "weekly_ret_8w_pct",
        "weekly_close_vs_ema9_pct",
        "weekly_close_vs_ema20_pct",
        "weekly_ema9_vs_ema20_pct",
        "weekly_close_vs_sma20_pct",
        "weekly_ema9_slope_1w_pct",
        "weekly_ema20_slope_1w_pct",
    ]

    directional_features = []

    for feature in raw_features:

        directional_col = (
            f"directional_prior_{feature}"
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
    # SIMPLE ALIGNMENT STATES
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
            alignment_state
        )

        state_features[
            feature
        ] = state_col

    # =========================================================================
    # WEEKLY TREND COMPOSITE
    #
    # Deliberately simple and not outcome optimized:
    #
    #   completed 4-week return
    #   prior completed-week close vs weekly EMA9
    #   weekly EMA9 vs EMA20
    #
    # All are direction-normalized.
    # =========================================================================

    composite_components = [
        "directional_prior_weekly_ret_4w_pct",
        "directional_prior_weekly_close_vs_ema9_pct",
        "directional_prior_weekly_ema9_vs_ema20_pct",
    ]

    def weekly_score(r):

        values = [
            r[x]
            for x in composite_components
        ]

        if any(
            pd.isna(x)
            for x in values
        ):
            return np.nan

        return sum(
            1 if x > 0
            else -1 if x < 0
            else 0
            for x in values
        )

    df[
        "weekly_trend_score"
    ] = df.apply(
        weekly_score,
        axis=1,
    )

    def weekly_state(score):

        if pd.isna(score):
            return "UNKNOWN"

        if score >= 2:
            return "ALIGNED"

        if score <= -2:
            return "OPPOSING"

        return "MIXED"

    df[
        "weekly_trend_state"
    ] = df[
        "weekly_trend_score"
    ].apply(
        weekly_state
    )

    # =========================================================================
    # PERIOD
    # =========================================================================

    if "research_period" not in df.columns:

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
    # COVERAGE
    # =========================================================================

    coverage_rows = []

    coverage_features = [
        "weekly_ret_1w_pct",
        "weekly_ret_2w_pct",
        "weekly_ret_4w_pct",
        "weekly_ret_8w_pct",
        "weekly_ema9",
        "weekly_ema20",
        "weekly_close_vs_ema9_pct",
        "weekly_close_vs_ema20_pct",
        "weekly_ema9_vs_ema20_pct",
        "weekly_close_vs_sma20_pct",
        "weekly_ema9_slope_1w_pct",
        "weekly_ema20_slope_1w_pct",
        "weekly_trend_score",
    ]

    for feature in coverage_features:

        n = int(
            df[
                feature
            ].notna().sum()
        )

        coverage_rows.append(
            {
                "feature":
                    feature,

                "available_n":
                    n,

                "coverage_pct":
                    (
                        100.0
                        * n
                        / len(df)
                    ),
            }
        )

    coverage = pd.DataFrame(
        coverage_rows
    )

    coverage.to_csv(
        COVERAGE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # STATE SUMMARIES
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

    # -------------------------------------------------------------------------
    # Composite.
    # -------------------------------------------------------------------------

    composite_all = summarize(
        df,
        [
            "research_period",
            "weekly_trend_state",
        ],
    )

    composite_all[
        "direction"
    ] = "ALL"

    composite_all[
        "feature"
    ] = (
        "WEEKLY_TREND_COMPOSITE"
    )

    composite_all = (
        composite_all.rename(
            columns={
                "weekly_trend_state":
                    "state"
            }
        )
    )

    composite_dir = summarize(
        df,
        [
            "research_period",
            "direction",
            "weekly_trend_state",
        ],
    )

    composite_dir[
        "feature"
    ] = (
        "WEEKLY_TREND_COMPOSITE"
    )

    composite_dir = (
        composite_dir.rename(
            columns={
                "weekly_trend_state":
                    "state"
            }
        )
    )

    summary_frames.extend(
        [
            composite_all,
            composite_dir,
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
    # CONTINUOUS ANALYSIS
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
                        (
                            winners[
                                feature
                            ].mean()
                            -
                            losers[
                                feature
                            ].mean()
                        ),

                    "confirmed_mean":
                        confirmed[
                            feature
                        ].mean(),

                    "not_confirmed_mean":
                        not_confirmed[
                            feature
                        ].mean(),

                    "confirmation_difference":
                        (
                            confirmed[
                                feature
                            ].mean()
                            -
                            not_confirmed[
                                feature
                            ].mean()
                        ),
                }
            )

    continuous = pd.DataFrame(
        continuous_rows
    )

    continuous.to_csv(
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
            "weekly_trend_state",
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
            "weekly_trend_state",
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
    # SAVE
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
    print("WEEKLY FEATURE COVERAGE")
    print("=" * 80)

    print(
        coverage.to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    print()

    print("=" * 80)
    print("WEEKLY TREND COMPOSITE — DISCOVERY VS VALIDATION")
    print("=" * 80)

    x = summary.loc[
        (
            summary[
                "feature"
            ]
            == "WEEKLY_TREND_COMPOSITE"
        )
        &
        (
            summary[
                "direction"
            ]
            == "ALL"
        )
    ].copy()

    print(
        x[
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
                lambda z:
                    f"{z:.2f}",
        )
    )

    print()

    print("=" * 80)
    print("WEEKLY TREND COMPOSITE — VALIDATION DIRECTIONAL")
    print("=" * 80)

    x = summary.loc[
        (
            summary[
                "feature"
            ]
            == "WEEKLY_TREND_COMPOSITE"
        )
        &
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
            != "ALL"
        )
    ].copy()

    print(
        x[
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
                lambda z:
                    f"{z:.2f}",
        )
    )

    print()

    print("=" * 80)
    print("INDIVIDUAL WEEKLY STATES — VALIDATION")
    print("=" * 80)

    x = summary.loc[
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
            != "WEEKLY_TREND_COMPOSITE"
        )
    ].copy()

    print(
        x[
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
                lambda z:
                    f"{z:.2f}",
        )
    )

    print()

    print("=" * 80)
    print("CONTINUOUS WEEKLY METRICS")
    print("=" * 80)

    print(
        continuous.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.4f}",
        )
    )

    print()

    print("=" * 80)
    print("WEEKLY TREND — QUARTER STABILITY")
    print("=" * 80)

    x = quarter_summary.loc[
        quarter_summary[
            "direction"
        ]
        == "ALL"
    ].copy()

    print(
        x[
            [
                "quarter",
                "weekly_trend_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
            ]
        ]
        .sort_values(
            [
                "quarter",
                "weekly_trend_state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
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
        f"Quarter:    "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Coverage:   "
        f"{COVERAGE_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()