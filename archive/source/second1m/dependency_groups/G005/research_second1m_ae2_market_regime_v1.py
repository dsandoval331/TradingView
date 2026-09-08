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
    / "ae2_weekly_trend_v1"
    / "ae2_weekly_trend_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_market_regime_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_market_regime_features_v1.parquet"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_market_regime_summary_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_market_regime_quarter_v1.csv"
)

INTERACTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_market_regime_interactions_v1.csv"
)

CONTINUOUS_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_market_regime_continuous_v1.csv"
)

COVERAGE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_market_regime_coverage_v1.csv"
)

BENCHMARKS = [
    "SPY",
    "QQQ",
]


# =============================================================================
# SUMMARY HELPERS
# =============================================================================

def summarize_group(
    x: pd.DataFrame,
) -> dict:

    favorable_n = int(
        (
            x["outcome"]
            == "FAVORABLE_FIRST"
        ).sum()
    )

    adverse_n = int(
        (
            x["outcome"]
            == "ADVERSE_FIRST"
        ).sum()
    )

    both_n = int(
        (
            x["outcome"]
            == "BOTH_SAME_BAR"
        ).sum()
    )

    unresolved_n = int(
        (
            x["outcome"]
            == "UNRESOLVED"
        ).sum()
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

        if not isinstance(
            keys,
            tuple,
        ):
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

    return pd.DataFrame(
        rows
    )


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


def consensus_state(
    a: str,
    b: str,
) -> str:

    if (
        a == "UNKNOWN"
        or b == "UNKNOWN"
    ):
        return "UNKNOWN"

    if (
        a == "ALIGNED"
        and b == "ALIGNED"
    ):
        return "CONSENSUS_ALIGNED"

    if (
        a == "OPPOSING"
        and b == "OPPOSING"
    ):
        return "CONSENSUS_OPPOSING"

    return "MIXED"


# =============================================================================
# LOAD BENCHMARK HISTORY
# =============================================================================

def load_benchmark_intraday(
    symbol: str,
) -> pd.DataFrame:

    paths = sorted(
        CACHE_ROOT.rglob(
            f"{symbol}_*.parquet"
        )
    )

    if not paths:
        raise RuntimeError(
            f"No local cache found for {symbol}"
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

    df["symbol"] = (
        df["symbol"]
        .astype(str)
        .str.upper()
    )

    df["trade_date"] = (
        pd.to_datetime(
            df["trade_date"]
        )
        .dt
        .normalize()
    )

    df["timestamp_utc"] = (
        pd.to_datetime(
            df["timestamp_utc"],
            utc=True,
        )
    )

    df = (
        df
        .sort_values(
            "timestamp_utc"
        )
        .drop_duplicates(
            subset=[
                "timestamp_utc"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    return df


# =============================================================================
# DAILY BENCHMARK CONTEXT
# =============================================================================

def build_daily_context(
    symbol: str,
) -> pd.DataFrame:

    intraday = load_benchmark_intraday(
        symbol
    )

    rth = intraday.loc[
        intraday["session"]
        == "RTH"
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
    ).reset_index(
        drop=True
    )

    close = (
        daily["close"]
        .astype(float)
    )

    daily[
        "ret_1d_pct"
    ] = (
        100.0
        * (
            close
            / close.shift(1)
            - 1.0
        )
    )

    daily[
        "ret_5d_pct"
    ] = (
        100.0
        * (
            close
            / close.shift(5)
            - 1.0
        )
    )

    daily[
        "ret_10d_pct"
    ] = (
        100.0
        * (
            close
            / close.shift(10)
            - 1.0
        )
    )

    daily[
        "ema9"
    ] = (
        close
        .ewm(
            span=9,
            adjust=False,
            min_periods=9,
        )
        .mean()
    )

    daily[
        "ema20"
    ] = (
        close
        .ewm(
            span=20,
            adjust=False,
            min_periods=20,
        )
        .mean()
    )

    daily[
        "close_vs_ema20_pct"
    ] = (
        100.0
        * (
            close
            / daily["ema20"]
            - 1.0
        )
    )

    daily[
        "ema9_vs_ema20_pct"
    ] = (
        100.0
        * (
            daily["ema9"]
            / daily["ema20"]
            - 1.0
        )
    )

    # -------------------------------------------------------------------------
    # Shift all daily features by one trading day.
    #
    # This protects the 09:31 entry boundary:
    # Tuesday can only use Monday's completed daily state.
    # -------------------------------------------------------------------------

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
        ] = daily[
            col
        ].shift(1)

    prefix = (
        symbol.lower()
    )

    keep = [
        "trade_date",
    ]

    rename_map = {}

    for col in source_cols:

        prior_col = (
            f"prior_{col}"
        )

        keep.append(
            prior_col
        )

        rename_map[
            prior_col
        ] = (
            f"{prefix}_daily_{col}"
        )

    result = (
        daily[
            keep
        ]
        .rename(
            columns=rename_map
        )
    )

    return result


# =============================================================================
# WEEKLY BENCHMARK CONTEXT
# =============================================================================

def build_weekly_context(
    symbol: str,
) -> pd.DataFrame:

    intraday = load_benchmark_intraday(
        symbol
    )

    rth = intraday.loc[
        intraday["session"]
        == "RTH"
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
            daily_open=("open", "first"),
            daily_high=("high", "max"),
            daily_low=("low", "min"),
            daily_close=("close", "last"),
            daily_volume=("volume", "sum"),
        )
    )

    daily[
        "week_end"
    ] = (
        daily[
            "trade_date"
        ]
        .dt
        .to_period(
            "W-FRI"
        )
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

    weekly = (
        weekly
        .sort_values(
            "week_end"
        )
        .reset_index(
            drop=True
        )
    )

    close = (
        weekly[
            "week_close"
        ]
        .astype(float)
    )

    weekly[
        "ret_1w_pct"
    ] = (
        100.0
        * (
            close
            / close.shift(1)
            - 1.0
        )
    )

    weekly[
        "ret_4w_pct"
    ] = (
        100.0
        * (
            close
            / close.shift(4)
            - 1.0
        )
    )

    weekly[
        "ret_8w_pct"
    ] = (
        100.0
        * (
            close
            / close.shift(8)
            - 1.0
        )
    )

    weekly[
        "ema9"
    ] = (
        close
        .ewm(
            span=9,
            adjust=False,
            min_periods=9,
        )
        .mean()
    )

    weekly[
        "ema20"
    ] = (
        close
        .ewm(
            span=20,
            adjust=False,
            min_periods=20,
        )
        .mean()
    )

    weekly[
        "close_vs_ema20_pct"
    ] = (
        100.0
        * (
            close
            / weekly["ema20"]
            - 1.0
        )
    )

    weekly[
        "ema9_vs_ema20_pct"
    ] = (
        100.0
        * (
            weekly["ema9"]
            / weekly["ema20"]
            - 1.0
        )
    )

    prefix = (
        symbol.lower()
    )

    rename_map = {
        "ret_1w_pct":
            f"{prefix}_weekly_ret_1w_pct",

        "ret_4w_pct":
            f"{prefix}_weekly_ret_4w_pct",

        "ret_8w_pct":
            f"{prefix}_weekly_ret_8w_pct",

        "close_vs_ema20_pct":
            f"{prefix}_weekly_close_vs_ema20_pct",

        "ema9_vs_ema20_pct":
            f"{prefix}_weekly_ema9_vs_ema20_pct",
    }

    keep = [
        "week_end",
        *rename_map.keys(),
    ]

    result = (
        weekly[
            keep
        ]
        .rename(
            columns=rename_map
        )
    )

    return result


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

    df = pd.read_parquet(
        INPUT_PATH
    )

    df[
        "trade_date"
    ] = (
        pd.to_datetime(
            df[
                "trade_date"
            ]
        )
        .dt
        .normalize()
    )

    print(
        "=" * 80
    )

    print(
        "AE2 SPY/QQQ MARKET REGIME V1"
    )

    print(
        "=" * 80
    )

    print(
        f"AE2 events: "
        f"{len(df):,}"
    )

    # =========================================================================
    # DAILY CONTEXT
    # =========================================================================

    for symbol in BENCHMARKS:

        print(
            f"Building daily context: "
            f"{symbol}"
        )

        daily = (
            build_daily_context(
                symbol
            )
        )

        df = df.merge(
            daily,
            on="trade_date",
            how="left",
        )

    # =========================================================================
    # WEEKLY CONTEXT
    #
    # FIX:
    #
    # The incoming AE2 dataset already contains a stock-level "week_end"
    # column from A26.3. Each benchmark therefore receives a unique weekly
    # merge-key name.
    #
    # We intentionally KEEP these fields as audit metadata:
    #
    #   spy_market_week_end
    #   qqq_market_week_end
    #
    # =========================================================================

    for symbol in BENCHMARKS:

        print(
            f"Building weekly context: "
            f"{symbol}"
        )

        weekly = (
            build_weekly_context(
                symbol
            )
        )

        benchmark_week_end = (
            f"{symbol.lower()}_market_week_end"
        )

        weekly = weekly.rename(
            columns={
                "week_end":
                    benchmark_week_end
            }
        )

        df = pd.merge_asof(
            df.sort_values(
                "trade_date"
            ),
            weekly.sort_values(
                benchmark_week_end
            ),
            left_on="trade_date",
            right_on=benchmark_week_end,
            direction="backward",
            allow_exact_matches=False,
        )

    # Return to deterministic event ordering.
    sort_cols = [
        col
        for col in [
            "trade_date",
            "symbol",
            "direction",
        ]
        if col in df.columns
    ]

    if sort_cols:

        df = (
            df
            .sort_values(
                sort_cols
            )
            .reset_index(
                drop=True
            )
        )

    # =========================================================================
    # DIRECTION-NORMALIZED BENCHMARK FEATURES
    # =========================================================================

    market_raw_features = []

    for benchmark in [
        "spy",
        "qqq",
    ]:

        for feature in [
            "daily_ret_1d_pct",
            "daily_ret_5d_pct",
            "daily_ret_10d_pct",
            "daily_close_vs_ema20_pct",
            "daily_ema9_vs_ema20_pct",
            "weekly_ret_1w_pct",
            "weekly_ret_4w_pct",
            "weekly_ret_8w_pct",
            "weekly_close_vs_ema20_pct",
            "weekly_ema9_vs_ema20_pct",
        ]:

            market_raw_features.append(
                f"{benchmark}_{feature}"
            )

    missing_market_cols = [
        col
        for col in market_raw_features
        if col not in df.columns
    ]

    if missing_market_cols:
        raise RuntimeError(
            "Missing market feature columns: "
            + ", ".join(
                missing_market_cols
            )
        )

    directional_features = []

    for feature in market_raw_features:

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
    # SIMPLE STATES
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
    # SPY + QQQ CONSENSUS STATES
    # =========================================================================

    consensus_pairs = {
        "market_prior_1d_consensus": (
            "directional_spy_daily_ret_1d_pct__state",
            "directional_qqq_daily_ret_1d_pct__state",
        ),

        "market_prior_5d_consensus": (
            "directional_spy_daily_ret_5d_pct__state",
            "directional_qqq_daily_ret_5d_pct__state",
        ),

        "market_daily_ema20_consensus": (
            "directional_spy_daily_close_vs_ema20_pct__state",
            "directional_qqq_daily_close_vs_ema20_pct__state",
        ),

        "market_prior_1w_consensus": (
            "directional_spy_weekly_ret_1w_pct__state",
            "directional_qqq_weekly_ret_1w_pct__state",
        ),

        "market_prior_4w_consensus": (
            "directional_spy_weekly_ret_4w_pct__state",
            "directional_qqq_weekly_ret_4w_pct__state",
        ),

        "market_weekly_ema20_consensus": (
            "directional_spy_weekly_close_vs_ema20_pct__state",
            "directional_qqq_weekly_close_vs_ema20_pct__state",
        ),
    }

    for name, (
        left,
        right,
    ) in (
        consensus_pairs.items()
    ):

        df[
            name
        ] = df.apply(
            lambda r:
                consensus_state(
                    r[left],
                    r[right],
                ),
            axis=1,
        )

    # =========================================================================
    # BROAD DAILY MARKET REGIME
    #
    # Four preregistered components:
    #
    #   SPY prior 5D return
    #   QQQ prior 5D return
    #   SPY prior close vs daily EMA20
    #   QQQ prior close vs daily EMA20
    #
    # Each component is direction-normalized to the AE2 trade.
    # =========================================================================

    daily_components = [
        "directional_spy_daily_ret_5d_pct",
        "directional_qqq_daily_ret_5d_pct",
        "directional_spy_daily_close_vs_ema20_pct",
        "directional_qqq_daily_close_vs_ema20_pct",
    ]

    def regime_score(
        r,
        components,
    ):

        values = [
            r[x]
            for x in components
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
        "market_daily_regime_score"
    ] = df.apply(
        lambda r:
            regime_score(
                r,
                daily_components,
            ),
        axis=1,
    )

    def regime_state(
        score,
    ):

        if pd.isna(score):
            return "UNKNOWN"

        if score >= 2:
            return "ALIGNED"

        if score <= -2:
            return "OPPOSING"

        return "MIXED"

    df[
        "market_daily_regime_state"
    ] = df[
        "market_daily_regime_score"
    ].apply(
        regime_state
    )

    # =========================================================================
    # BROAD WEEKLY MARKET REGIME
    # =========================================================================

    weekly_components = [
        "directional_spy_weekly_ret_4w_pct",
        "directional_qqq_weekly_ret_4w_pct",
        "directional_spy_weekly_close_vs_ema20_pct",
        "directional_qqq_weekly_close_vs_ema20_pct",
    ]

    df[
        "market_weekly_regime_score"
    ] = df.apply(
        lambda r:
            regime_score(
                r,
                weekly_components,
            ),
        axis=1,
    )

    df[
        "market_weekly_regime_state"
    ] = df[
        "market_weekly_regime_score"
    ].apply(
        regime_state
    )

    # =========================================================================
    # PERIOD / QUARTER
    # =========================================================================

    if (
        "research_period"
        not in df.columns
    ):

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
        .to_period(
            "Q"
        )
        .astype(str)
    )

    # =========================================================================
    # COVERAGE
    # =========================================================================

    coverage_rows = []

    coverage_features = [
        *market_raw_features,
        "market_daily_regime_score",
        "market_weekly_regime_score",
        "spy_market_week_end",
        "qqq_market_week_end",
    ]

    for feature in coverage_features:

        available_n = int(
            df[
                feature
            ].notna().sum()
        )

        coverage_rows.append(
            {
                "feature":
                    feature,

                "available_n":
                    available_n,

                "coverage_pct":
                    (
                        100.0
                        * available_n
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
    # Consensus features.
    # -------------------------------------------------------------------------

    for feature in (
        consensus_pairs.keys()
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

        all_dir = (
            all_dir.rename(
                columns={
                    feature:
                        "state"
                }
            )
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

        by_dir = (
            by_dir.rename(
                columns={
                    feature:
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
    # Broad market regimes.
    # -------------------------------------------------------------------------

    for feature in [
        "market_daily_regime_state",
        "market_weekly_regime_state",
    ]:

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

        all_dir = (
            all_dir.rename(
                columns={
                    feature:
                        "state"
                }
            )
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

        by_dir = (
            by_dir.rename(
                columns={
                    feature:
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

    for feature in (
        directional_features
    ):

        for period, x in (
            df.groupby(
                "research_period",
                dropna=False,
            )
        ):

            winners = x.loc[
                x[
                    "outcome"
                ]
                == "FAVORABLE_FIRST"
            ]

            losers = x.loc[
                x[
                    "outcome"
                ]
                == "ADVERSE_FIRST"
            ]

            confirmed = x.loc[
                x[
                    "c3_confirmed"
                ]
            ]

            not_confirmed = x.loc[
                ~x[
                    "c3_confirmed"
                ]
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
    # INTERACTIONS WITH STOCK CONTEXT
    # =========================================================================

    interaction_frames = []

    interaction_specs = [
        (
            "market_daily_regime_state",
            "aligned_exhaustion_state",
        ),
        (
            "market_weekly_regime_state",
            "weekly_trend_state",
        ),
        (
            "market_daily_regime_state",
            "trend_5d_binary_state",
        ),
    ]

    for (
        market_feature,
        stock_feature,
    ) in interaction_specs:

        if (
            market_feature
            not in df.columns
        ):

            continue

        if (
            stock_feature
            not in df.columns
        ):

            continue

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
        ] = (
            market_feature
        )

        x[
            "stock_feature"
        ] = (
            stock_feature
        )

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

    if interaction_frames:

        interactions = pd.concat(
            interaction_frames,
            ignore_index=True,
            sort=False,
        )

    else:

        interactions = pd.DataFrame()

    interactions.to_csv(
        INTERACTION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # QUARTER — DAILY/WEEKLY MARKET REGIMES
    # =========================================================================

    quarter_frames = []

    for feature in [
        "market_daily_regime_state",
        "market_weekly_regime_state",
    ]:

        x = summarize(
            df,
            [
                "quarter",
                feature,
            ],
        )

        x[
            "feature"
        ] = feature

        x = x.rename(
            columns={
                feature:
                    "state"
            }
        )

        quarter_frames.append(
            x
        )

    quarter_summary = pd.concat(
        quarter_frames,
        ignore_index=True,
        sort=False,
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SAVE EVENT DATASET
    # =========================================================================

    df.to_parquet(
        FEATURE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # REPORT
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "MARKET FEATURE COVERAGE"
    )

    print(
        "=" * 80
    )

    print(
        coverage.to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    print()

    print(
        "=" * 80
    )

    print(
        "DAILY MARKET REGIME — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    x = summary.loc[
        (
            summary[
                "feature"
            ]
            == "market_daily_regime_state"
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

    print(
        "=" * 80
    )

    print(
        "WEEKLY MARKET REGIME — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    x = summary.loc[
        (
            summary[
                "feature"
            ]
            == "market_weekly_regime_state"
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

    print(
        "=" * 80
    )

    print(
        "VALIDATION — SPY/QQQ CONSENSUS STATES"
    )

    print(
        "=" * 80
    )

    for feature in (
        consensus_pairs.keys()
    ):

        print()

        print(
            feature
        )

        print(
            "-" * 80
        )

        x = summary.loc[
            (
                summary[
                    "feature"
                ]
                == feature
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
                == "ALL"
            )
        ]

        print(
            x[
                [
                    "state",
                    "total_n",
                    "binary_n",
                    "favorable_first_pct",
                    "c3_confirmation_pct",
                ]
            ]
            .sort_values(
                "state"
            )
            .to_string(
                index=False,
                float_format=
                    lambda z:
                        f"{z:.2f}",
            )
        )

    print()

    print(
        "=" * 80
    )

    print(
        "MARKET REGIME — "
        "VALIDATION DIRECTIONAL"
    )

    print(
        "=" * 80
    )

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
            != "ALL"
        )
        &
        (
            summary[
                "feature"
            ].isin(
                [
                    "market_daily_regime_state",
                    "market_weekly_regime_state",
                ]
            )
        )
    ]

    print(
        x[
            [
                "feature",
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
                "feature",
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

    print(
        "=" * 80
    )

    print(
        "CONTINUOUS MARKET METRICS"
    )

    print(
        "=" * 80
    )

    print(
        continuous.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.4f}",
        )
    )

    print()

    print(
        "=" * 80
    )

    print(
        "MARKET × STOCK INTERACTIONS — "
        "VALIDATION"
    )

    print(
        "=" * 80
    )

    if not interactions.empty:

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

    else:

        print(
            "No interaction rows produced."
        )

    print()

    print(
        "=" * 80
    )

    print(
        "OUTPUTS"
    )

    print(
        "=" * 80
    )

    print(
        f"Features:     "
        f"{FEATURE_OUTPUT}"
    )

    print(
        f"Summary:      "
        f"{SUMMARY_OUTPUT}"
    )

    print(
        f"Quarter:      "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Interactions: "
        f"{INTERACTION_OUTPUT}"
    )

    print(
        f"Continuous:   "
        f"{CONTINUOUS_OUTPUT}"
    )

    print(
        f"Coverage:     "
        f"{COVERAGE_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()