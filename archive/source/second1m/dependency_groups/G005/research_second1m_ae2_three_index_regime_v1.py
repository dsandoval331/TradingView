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
    / "ae2_market_regime_v1"
    / "ae2_market_regime_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_three_index_regime_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_three_index_regime_features_v1.parquet"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_three_index_regime_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_three_index_regime_direction_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_three_index_regime_quarter_v1.csv"
)

INTERACTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_three_index_regime_interactions_v1.csv"
)

INCREMENTAL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_dia_incremental_value_v1.csv"
)

COVERAGE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_three_index_regime_coverage_v1.csv"
)

SYMBOL = "DIA"


# =============================================================================
# HELPERS
# =============================================================================

def summarize_group(
    x: pd.DataFrame,
) -> dict:

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

    ff_pct = (
        100.0
        * favorable_n
        / binary_n
        if binary_n
        else np.nan
    )

    confirmed_n = int(
        x["c3_confirmed"].sum()
    )

    confirm_pct = (
        100.0
        * confirmed_n
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
            ff_pct,

        "c3_confirmation_pct":
            confirm_pct,

        "avg_mfe_pct":
            x["final_mfe_pct"].mean(),

        "avg_mae_pct":
            x["final_mae_pct"].mean(),

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
# DIA CACHE LOAD
# =============================================================================

def load_dia_intraday() -> pd.DataFrame:

    paths = sorted(
        CACHE_ROOT.rglob(
            "DIA_*.parquet"
        )
    )

    if not paths:
        raise RuntimeError(
            "No DIA cache files found."
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

    df = pd.concat(
        frames,
        ignore_index=True,
    )

    df["trade_date"] = (
        pd.to_datetime(
            df["trade_date"]
        )
        .dt
        .normalize()
    )

    df["timestamp_utc"] = pd.to_datetime(
        df["timestamp_utc"],
        utc=True,
    )

    df = (
        df
        .sort_values(
            "timestamp_utc"
        )
        .drop_duplicates(
            subset=["timestamp_utc"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return df


# =============================================================================
# DIA DAILY CONTEXT
# =============================================================================

def build_dia_daily() -> pd.DataFrame:

    intraday = load_dia_intraday()

    rth = intraday.loc[
        intraday["session"] == "RTH"
    ].copy()

    daily = (
        rth
        .sort_values(
            [
                "trade_date",
                "timestamp_utc",
            ]
        )
        .groupby(
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

    daily["ret_1d_pct"] = (
        100.0
        * (
            close
            / close.shift(1)
            - 1.0
        )
    )

    daily["ret_5d_pct"] = (
        100.0
        * (
            close
            / close.shift(5)
            - 1.0
        )
    )

    daily["ret_10d_pct"] = (
        100.0
        * (
            close
            / close.shift(10)
            - 1.0
        )
    )

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

    source_cols = [
        "close",
        "ret_1d_pct",
        "ret_5d_pct",
        "ret_10d_pct",
        "ema9",
        "ema20",
        "close_vs_ema20_pct",
        "ema9_vs_ema20_pct",
    ]

    for col in source_cols:

        daily[
            f"prior_{col}"
        ] = daily[col].shift(1)

    keep = [
        "trade_date",
        *[
            f"prior_{col}"
            for col in source_cols
        ],
    ]

    result = daily[keep].rename(
        columns={
            f"prior_{col}":
                f"dia_daily_{col}"
            for col in source_cols
        }
    )

    return result


# =============================================================================
# DIA WEEKLY CONTEXT
# =============================================================================

def build_dia_weekly() -> pd.DataFrame:

    intraday = load_dia_intraday()

    rth = intraday.loc[
        intraday["session"] == "RTH"
    ].copy()

    daily = (
        rth
        .sort_values(
            [
                "trade_date",
                "timestamp_utc",
            ]
        )
        .groupby(
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

    daily["week_end"] = (
        daily["trade_date"]
        .dt
        .to_period("W-FRI")
        .dt
        .end_time
        .dt
        .normalize()
    )

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
        )
    )

    weekly = weekly.sort_values(
        "week_end"
    ).reset_index(drop=True)

    close = (
        weekly["week_close"]
        .astype(float)
    )

    weekly["ret_1w_pct"] = (
        100.0
        * (
            close
            / close.shift(1)
            - 1.0
        )
    )

    weekly["ret_4w_pct"] = (
        100.0
        * (
            close
            / close.shift(4)
            - 1.0
        )
    )

    weekly["ret_8w_pct"] = (
        100.0
        * (
            close
            / close.shift(8)
            - 1.0
        )
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

    weekly["close_vs_ema20_pct"] = (
        100.0
        * (
            close
            / weekly["ema20"]
            - 1.0
        )
    )

    weekly = weekly.rename(
        columns={
            "week_end":
                "dia_market_week_end",

            "ret_1w_pct":
                "dia_weekly_ret_1w_pct",

            "ret_4w_pct":
                "dia_weekly_ret_4w_pct",

            "ret_8w_pct":
                "dia_weekly_ret_8w_pct",

            "close_vs_ema20_pct":
                "dia_weekly_close_vs_ema20_pct",
        }
    )

    return weekly[
        [
            "dia_market_week_end",
            "dia_weekly_ret_1w_pct",
            "dia_weekly_ret_4w_pct",
            "dia_weekly_ret_8w_pct",
            "dia_weekly_close_vs_ema20_pct",
        ]
    ]


# =============================================================================
# THREE-INDEX STATE
# =============================================================================

def three_index_state(
    spy_state: str,
    qqq_state: str,
    dia_state: str,
) -> str:

    states = [
        spy_state,
        qqq_state,
        dia_state,
    ]

    if any(
        x == "UNKNOWN"
        for x in states
    ):
        return "UNKNOWN"

    aligned_n = sum(
        x == "ALIGNED"
        for x in states
    )

    opposing_n = sum(
        x == "OPPOSING"
        for x in states
    )

    if aligned_n == 3:
        return "ALL_3_ALIGNED"

    if opposing_n == 3:
        return "ALL_3_OPPOSING"

    if aligned_n == 2:
        return "MAJORITY_ALIGNED"

    if opposing_n == 2:
        return "MAJORITY_OPPOSING"

    return "MIXED"


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

    df = pd.read_parquet(
        INPUT_PATH
    )

    df["trade_date"] = (
        pd.to_datetime(
            df["trade_date"]
        )
        .dt
        .normalize()
    )

    print("=" * 80)
    print("AE2 SPY + QQQ + DIA THREE-INDEX REGIME V1")
    print("=" * 80)

    print(
        f"AE2 events: "
        f"{len(df):,}"
    )

    # =========================================================================
    # MERGE DIA DAILY
    # =========================================================================

    print(
        "Building DIA daily context..."
    )

    dia_daily = build_dia_daily()

    df = df.merge(
        dia_daily,
        on="trade_date",
        how="left",
    )

    # =========================================================================
    # MERGE DIA WEEKLY
    # =========================================================================

    print(
        "Building DIA weekly context..."
    )

    dia_weekly = build_dia_weekly()

    df = pd.merge_asof(
        df.sort_values(
            "trade_date"
        ),
        dia_weekly.sort_values(
            "dia_market_week_end"
        ),
        left_on="trade_date",
        right_on="dia_market_week_end",
        direction="backward",
        allow_exact_matches=False,
    )

    # =========================================================================
    # DIA DIRECTION-NORMALIZED FEATURES
    # =========================================================================

    dia_raw_features = [
        "dia_daily_ret_1d_pct",
        "dia_daily_ret_5d_pct",
        "dia_daily_ret_10d_pct",
        "dia_daily_close_vs_ema20_pct",
        "dia_daily_ema9_vs_ema20_pct",
        "dia_weekly_ret_1w_pct",
        "dia_weekly_ret_4w_pct",
        "dia_weekly_ret_8w_pct",
        "dia_weekly_close_vs_ema20_pct",
    ]

    for feature in dia_raw_features:

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

        df[
            directional_col
            + "__state"
        ] = df[
            directional_col
        ].apply(
            alignment_state
        )

    # =========================================================================
    # THREE-INDEX STATES
    # =========================================================================

    state_specs = {
        "market_3idx_prior_1d_state": (
            "directional_spy_daily_ret_1d_pct__state",
            "directional_qqq_daily_ret_1d_pct__state",
            "directional_dia_daily_ret_1d_pct__state",
        ),

        "market_3idx_prior_5d_state": (
            "directional_spy_daily_ret_5d_pct__state",
            "directional_qqq_daily_ret_5d_pct__state",
            "directional_dia_daily_ret_5d_pct__state",
        ),

        "market_3idx_daily_ema20_state": (
            "directional_spy_daily_close_vs_ema20_pct__state",
            "directional_qqq_daily_close_vs_ema20_pct__state",
            "directional_dia_daily_close_vs_ema20_pct__state",
        ),

        "market_3idx_prior_1w_state": (
            "directional_spy_weekly_ret_1w_pct__state",
            "directional_qqq_weekly_ret_1w_pct__state",
            "directional_dia_weekly_ret_1w_pct__state",
        ),

        "market_3idx_prior_4w_state": (
            "directional_spy_weekly_ret_4w_pct__state",
            "directional_qqq_weekly_ret_4w_pct__state",
            "directional_dia_weekly_ret_4w_pct__state",
        ),

        "market_3idx_weekly_ema20_state": (
            "directional_spy_weekly_close_vs_ema20_pct__state",
            "directional_qqq_weekly_close_vs_ema20_pct__state",
            "directional_dia_weekly_close_vs_ema20_pct__state",
        ),
    }

    for output_col, (
        spy_col,
        qqq_col,
        dia_col,
    ) in (
        state_specs.items()
    ):

        df[
            output_col
        ] = df.apply(
            lambda r:
                three_index_state(
                    r[spy_col],
                    r[qqq_col],
                    r[dia_col],
                ),
            axis=1,
        )

    # =========================================================================
    # PERIOD / QUARTER
    # =========================================================================

    df["quarter"] = (
        df["trade_date"]
        .dt
        .to_period("Q")
        .astype(str)
    )

    # =========================================================================
    # COVERAGE
    # =========================================================================

    coverage_rows = []

    coverage_features = [
        *dia_raw_features,
        "dia_market_week_end",
        *state_specs.keys(),
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
    # PRIMARY SUMMARY
    # =========================================================================

    summary_frames = []

    for feature in (
        state_specs.keys()
    ):

        all_dir = summarize(
            df,
            [
                "research_period",
                feature,
            ],
        )

        all_dir[
            "direction"
        ] = "ALL"

        all_dir[
            "feature"
        ] = feature

        all_dir = all_dir.rename(
            columns={
                feature:
                    "state"
            }
        )

        by_dir = summarize(
            df,
            [
                "research_period",
                "direction",
                feature,
            ],
        )

        by_dir[
            "feature"
        ] = feature

        by_dir = by_dir.rename(
            columns={
                feature:
                    "state"
            }
        )

        summary_frames.extend(
            [
                all_dir,
                by_dir,
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
    # DIRECTION OUTPUT
    # =========================================================================

    direction_summary = (
        summary.loc[
            summary[
                "direction"
            ]
            != "ALL"
        ]
        .copy()
    )

    direction_summary.to_csv(
        DIRECTION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # QUARTER — 5D PRIMARY
    # =========================================================================

    quarter_summary = summarize(
        df,
        [
            "quarter",
            "market_3idx_prior_5d_state",
        ],
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # DIA INCREMENTAL VALUE
    #
    # Primary question:
    #
    # When SPY+QQQ are already both opposing,
    # does DIA agreement improve AE2?
    # =========================================================================

    def dia_incremental_state(r):

        two_index = r[
            "market_prior_5d_consensus"
        ]

        dia_state = r[
            "directional_dia_daily_ret_5d_pct__state"
        ]

        if (
            two_index
            == "CONSENSUS_OPPOSING"
        ):

            if (
                dia_state
                == "OPPOSING"
            ):
                return "SPY_QQQ_OPPOSING_DIA_OPPOSING"

            if (
                dia_state
                == "ALIGNED"
            ):
                return "SPY_QQQ_OPPOSING_DIA_ALIGNED"

            return "SPY_QQQ_OPPOSING_DIA_OTHER"

        if (
            two_index
            == "CONSENSUS_ALIGNED"
        ):

            if (
                dia_state
                == "ALIGNED"
            ):
                return "SPY_QQQ_ALIGNED_DIA_ALIGNED"

            if (
                dia_state
                == "OPPOSING"
            ):
                return "SPY_QQQ_ALIGNED_DIA_OPPOSING"

            return "SPY_QQQ_ALIGNED_DIA_OTHER"

        return "OTHER"

    df[
        "dia_incremental_5d_state"
    ] = df.apply(
        dia_incremental_state,
        axis=1,
    )

    incremental = summarize(
        df,
        [
            "research_period",
            "dia_incremental_5d_state",
        ],
    )

    incremental.to_csv(
        INCREMENTAL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # INTERACTIONS
    # =========================================================================

    interaction_frames = []

    interaction_specs = [
        (
            "market_3idx_prior_5d_state",
            "trend_5d_binary_state",
        ),
        (
            "market_3idx_prior_5d_state",
            "aligned_exhaustion_state",
        ),
        (
            "market_3idx_prior_4w_state",
            "weekly_trend_state",
        ),
    ]

    for (
        market_feature,
        stock_feature,
    ) in interaction_specs:

        x = summarize(
            df,
            [
                "research_period",
                market_feature,
                stock_feature,
            ],
        )

        x[
            "market_feature"
        ] = market_feature

        x[
            "stock_feature"
        ] = stock_feature

        x = x.rename(
            columns={
                market_feature:
                    "market_state",

                stock_feature:
                    "stock_state",
            }
        )

        interaction_frames.append(
            x
        )

    interactions = pd.concat(
        interaction_frames,
        ignore_index=True,
        sort=False,
    )

    interactions.to_csv(
        INTERACTION_OUTPUT,
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
    print("DIA / THREE-INDEX COVERAGE")
    print("=" * 80)

    print(
        coverage.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    print()

    print("=" * 80)
    print("THREE-INDEX 5D MARKET STATE — DISCOVERY VS VALIDATION")
    print("=" * 80)

    x = summary.loc[
        (
            summary[
                "feature"
            ]
            == "market_3idx_prior_5d_state"
        )
        &
        (
            summary[
                "direction"
            ]
            == "ALL"
        )
    ]

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
    print("THREE-INDEX 5D MARKET STATE — VALIDATION DIRECTIONAL")
    print("=" * 80)

    x = direction_summary.loc[
        (
            direction_summary[
                "feature"
            ]
            == "market_3idx_prior_5d_state"
        )
        &
        (
            direction_summary[
                "research_period"
            ]
            == "VALIDATION"
        )
    ]

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
    print("DIA INCREMENTAL VALUE — 5D")
    print("=" * 80)

    print(
        incremental[
            [
                "research_period",
                "dia_incremental_5d_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "dia_incremental_5d_state",
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
    print("THREE-INDEX 5D — QUARTER STABILITY")
    print("=" * 80)

    print(
        quarter_summary[
            [
                "quarter",
                "market_3idx_prior_5d_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
            ]
        ]
        .sort_values(
            [
                "quarter",
                "market_3idx_prior_5d_state",
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
    print("THREE-INDEX MARKET × STOCK — VALIDATION")
    print("=" * 80)

    x = interactions.loc[
        interactions[
            "research_period"
        ]
        == "VALIDATION"
    ]

    print(
        x[
            [
                "market_feature",
                "stock_feature",
                "market_state",
                "stock_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "market_feature",
                "stock_feature",
                "market_state",
                "stock_state",
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
        f"Features:    "
        f"{FEATURE_OUTPUT}"
    )

    print(
        f"Summary:     "
        f"{SUMMARY_OUTPUT}"
    )

    print(
        f"Direction:   "
        f"{DIRECTION_OUTPUT}"
    )

    print(
        f"Quarter:     "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Interactions:"
        f" {INTERACTION_OUTPUT}"
    )

    print(
        f"DIA value:   "
        f"{INCREMENTAL_OUTPUT}"
    )

    print(
        f"Coverage:    "
        f"{COVERAGE_OUTPUT}"
    )

    print()

    print("RESULT: COMPLETE")


if __name__ == "__main__":
    main()