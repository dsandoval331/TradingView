from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


# =============================================================================
# CONFIG
# =============================================================================

ROOT = Path(
    r"C:\Users\DirtySouth\TradingResearch"
)

CACHE_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_cache_v1"
    / "partitions"
)

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

INPUT_PATH = (
    RESEARCH_ROOT
    / "ae2_calendar_v1"
    / "ae2_calendar_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_postsignal_paths_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_postsignal_path_features_v1.parquet"
)

PATH_SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_postsignal_path_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_postsignal_path_direction_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_postsignal_path_quarter_v1.csv"
)

SENSITIVITY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_postsignal_path_sensitivity_v1.csv"
)

TRAJECTORY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_postsignal_trajectory_v1.csv"
)

TRANSITION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_postsignal_transition_v1.csv"
)

COVERAGE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_postsignal_coverage_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_postsignal_path_symbol_v1.csv"
)

EXPECTED_SYMBOLS = 112

POST_BARS = list(
    range(
        3,
        11,
    )
)

EXCLUDE_SYMBOLS = {
    "SPY",
    "QQQ",
    "TQQQ",
}


# =============================================================================
# GENERAL HELPERS
# =============================================================================

def normalize_date_ns(
    series: pd.Series,
) -> pd.Series:

    return (
        pd.to_datetime(
            series,
            errors="coerce",
        )
        .dt
        .normalize()
        .astype(
            "datetime64[ns]"
        )
    )


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


# =============================================================================
# DIRECTIONAL PRICE HELPERS
# =============================================================================

def directional_close_delta_pct(
    direction: str,
    price: float,
    reference: float,
) -> float:

    if (
        pd.isna(price)
        or pd.isna(reference)
        or reference == 0
    ):
        return np.nan

    if direction == "BULL":

        return (
            (
                price
                - reference
            )
            / reference
            * 100.0
        )

    if direction == "BEAR":

        return (
            (
                reference
                - price
            )
            / reference
            * 100.0
        )

    return np.nan


def favorable_excursion_pct(
    direction: str,
    bar_high: float,
    bar_low: float,
    reference: float,
) -> float:

    if (
        pd.isna(bar_high)
        or pd.isna(bar_low)
        or pd.isna(reference)
        or reference == 0
    ):
        return np.nan

    if direction == "BULL":

        return max(
            0.0,
            (
                bar_high
                - reference
            )
            / reference
            * 100.0,
        )

    if direction == "BEAR":

        return max(
            0.0,
            (
                reference
                - bar_low
            )
            / reference
            * 100.0,
        )

    return np.nan


def adverse_excursion_pct(
    direction: str,
    bar_high: float,
    bar_low: float,
    reference: float,
) -> float:

    if (
        pd.isna(bar_high)
        or pd.isna(bar_low)
        or pd.isna(reference)
        or reference == 0
    ):
        return np.nan

    if direction == "BULL":

        return max(
            0.0,
            (
                reference
                - bar_low
            )
            / reference
            * 100.0,
        )

    if direction == "BEAR":

        return max(
            0.0,
            (
                bar_high
                - reference
            )
            / reference
            * 100.0,
        )

    return np.nan


def close_side_state(
    value: float,
) -> str:

    if pd.isna(value):
        return "UNKNOWN"

    if value > 0:
        return "FAVORABLE_SIDE"

    if value < 0:
        return "ADVERSE_SIDE"

    return "AT_REFERENCE"


# =============================================================================
# CACHE HELPERS
# =============================================================================

def symbol_paths(
    symbol: str,
) -> list[Path]:

    symbol_dir = (
        CACHE_ROOT
        / symbol
    )

    if not symbol_dir.exists():

        raise RuntimeError(
            f"Cache directory not found "
            f"for {symbol}: {symbol_dir}"
        )

    paths = sorted(
        symbol_dir.glob(
            f"{symbol}_*.parquet"
        )
    )

    if not paths:

        raise RuntimeError(
            f"No cache partitions found "
            f"for {symbol}"
        )

    return paths


# =============================================================================
# BUILD C3-C10 HISTORY
# =============================================================================

def build_symbol_postsignal_history(
    symbol: str,
) -> pd.DataFrame:

    frames = []

    for path in symbol_paths(
        symbol
    ):

        table = pq.read_table(
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
                "vwap",
                "session",
            ],
        )

        frames.append(
            table.to_pandas()
        )

    bars = pd.concat(
        frames,
        ignore_index=True,
    )

    bars[
        "symbol"
    ] = (
        bars[
            "symbol"
        ]
        .astype(str)
        .str.upper()
    )

    bars[
        "trade_date"
    ] = normalize_date_ns(
        bars[
            "trade_date"
        ]
    )

    bars[
        "timestamp_et"
    ] = (
        pd.to_datetime(
            bars[
                "timestamp_et"
            ],
            utc=True,
            errors="coerce",
        )
        .dt
        .tz_convert(
            "America/New_York"
        )
    )

    bars = (
        bars
        .dropna(
            subset=[
                "trade_date",
                "timestamp_et",
            ]
        )
        .sort_values(
            "timestamp_et"
        )
        .drop_duplicates(
            subset=[
                "timestamp_et",
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    # =========================================================================
    # C3 THROUGH C10
    #
    # C1 = 09:30
    # C2 = 09:31
    # C3 = 09:32
    # ...
    # C10 = 09:39
    # =========================================================================

    rth = bars.loc[
        bars[
            "session"
        ]
        == "RTH"
    ].copy()

    rth[
        "et_hour"
    ] = (
        rth[
            "timestamp_et"
        ]
        .dt
        .hour
    )

    rth[
        "et_minute"
    ] = (
        rth[
            "timestamp_et"
        ]
        .dt
        .minute
    )

    post = rth.loc[
        (
            rth[
                "et_hour"
            ]
            == 9
        )
        &
        (
            rth[
                "et_minute"
            ]
            .between(
                32,
                39,
            )
        )
    ].copy()

    post[
        "candle_number"
    ] = (
        post[
            "et_minute"
        ]
        - 29
    )

    keep_cols = [
        "trade_date",
        "candle_number",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
    ]

    post = post[
        keep_cols
    ].copy()

    # -------------------------------------------------------------------------
    # Convert to one row per trade_date.
    # -------------------------------------------------------------------------

    records = []

    for trade_date, x in post.groupby(
        "trade_date",
    ):

        row = {
            "symbol":
                symbol,

            "trade_date":
                trade_date,
        }

        for candle_number in (
            POST_BARS
        ):

            y = x.loc[
                x[
                    "candle_number"
                ]
                == candle_number
            ]

            prefix = (
                f"post_c"
                f"{candle_number}"
            )

            if y.empty:

                row[
                    f"{prefix}_open"
                ] = np.nan

                row[
                    f"{prefix}_high"
                ] = np.nan

                row[
                    f"{prefix}_low"
                ] = np.nan

                row[
                    f"{prefix}_close"
                ] = np.nan

                row[
                    f"{prefix}_volume"
                ] = np.nan

                row[
                    f"{prefix}_vwap"
                ] = np.nan

            else:

                z = y.iloc[-1]

                row[
                    f"{prefix}_open"
                ] = z[
                    "open"
                ]

                row[
                    f"{prefix}_high"
                ] = z[
                    "high"
                ]

                row[
                    f"{prefix}_low"
                ] = z[
                    "low"
                ]

                row[
                    f"{prefix}_close"
                ] = z[
                    "close"
                ]

                row[
                    f"{prefix}_volume"
                ] = z[
                    "volume"
                ]

                row[
                    f"{prefix}_vwap"
                ] = z[
                    "vwap"
                ]

        records.append(
            row
        )

    result = pd.DataFrame(
        records
    )

    if result.empty:

        raise RuntimeError(
            f"No C3-C10 RTH rows found "
            f"for {symbol}"
        )

    result[
        "trade_date"
    ] = normalize_date_ns(
        result[
            "trade_date"
        ]
    )

    return result


# =============================================================================
# PATH CLASSIFICATION
# =============================================================================

def classify_early_path(
    r: pd.Series,
) -> str:

    d3 = r[
        "post_c3_close_delta_pct"
    ]

    d4 = r[
        "post_c4_close_delta_pct"
    ]

    if (
        pd.isna(d3)
        or pd.isna(d4)
    ):
        return "INCOMPLETE"

    # -------------------------------------------------------------------------
    # No magnitude threshold is used.
    #
    # This prevents A33.1 from outcome-mining a "best" C3/C4 cutoff.
    # -------------------------------------------------------------------------

    if (
        d3 > 0
        and d4 > 0
    ):
        return "IMMEDIATE_CONTINUATION"

    if (
        d3 > 0
        and d4 <= 0
    ):
        return "CONTINUATION_THEN_REVERSAL"

    if (
        d3 < 0
        and d4 < 0
    ):
        return "IMMEDIATE_FAILURE"

    if (
        d3 < 0
        and d4 >= 0
    ):
        return "FAILURE_THEN_RECOVERY"

    return "STALLED_MIXED"


def classify_c3_c4_transition(
    r: pd.Series,
) -> str:

    c3 = r[
        "post_c3_close_side_state"
    ]

    c4 = r[
        "post_c4_close_side_state"
    ]

    if (
        c3 == "UNKNOWN"
        or c4 == "UNKNOWN"
    ):
        return "INCOMPLETE"

    return (
        c3
        + "__TO__"
        + c4
    )


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

    events = pd.read_parquet(
        INPUT_PATH
    )

    required = [
        "symbol",
        "trade_date",
        "direction",
        "research_period",
        "outcome",
        "c3_confirmed",
        "final_mfe_pct",
        "final_mae_pct",
        "c2_close",
    ]

    missing = [
        col
        for col in required
        if col not in events.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing required input columns: "
            + ", ".join(
                missing
            )
        )

    events[
        "symbol"
    ] = (
        events[
            "symbol"
        ]
        .astype(str)
        .str.upper()
    )

    events[
        "trade_date"
    ] = normalize_date_ns(
        events[
            "trade_date"
        ]
    )

    symbols = sorted(
        events[
            "symbol"
        ].unique()
    )

    if len(
        symbols
    ) != EXPECTED_SYMBOLS:

        raise RuntimeError(
            f"Expected "
            f"{EXPECTED_SYMBOLS} symbols, "
            f"found {len(symbols)}"
        )

    print(
        "=" * 80
    )

    print(
        "AE2 POST-SIGNAL PATH RESEARCH V1"
    )

    print(
        "=" * 80
    )

    print(
        f"AE2 events: "
        f"{len(events):,}"
    )

    print(
        f"Symbols:    "
        f"{len(symbols):,}"
    )

    # =========================================================================
    # ENRICH WITH C3-C10
    # =========================================================================

    enriched_frames = []

    for i, symbol in enumerate(
        symbols,
        start=1,
    ):

        event_subset = (
            events.loc[
                events[
                    "symbol"
                ]
                == symbol
            ]
            .copy()
        )

        post_history = (
            build_symbol_postsignal_history(
                symbol
            )
        )

        event_subset = event_subset.merge(
            post_history,
            on=[
                "symbol",
                "trade_date",
            ],
            how="left",
            validate="many_to_one",
        )

        enriched_frames.append(
            event_subset
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

    if len(
        df
    ) != len(
        events
    ):

        raise RuntimeError(
            "Event count changed after "
            "post-signal enrichment."
        )

    # =========================================================================
    # FROZEN REFERENCE PRICE
    #
    # AE2 enters at C2 close.
    # =========================================================================

    df[
        "postsignal_reference_price"
    ] = df[
        "c2_close"
    ]

    # =========================================================================
    # C3-C10 DIRECTIONAL FEATURES
    # =========================================================================

    for candle_number in (
        POST_BARS
    ):

        prefix = (
            f"post_c"
            f"{candle_number}"
        )

        delta_col = (
            f"{prefix}_close_delta_pct"
        )

        fav_col = (
            f"{prefix}_fav_excursion_pct"
        )

        adv_col = (
            f"{prefix}_adv_excursion_pct"
        )

        state_col = (
            f"{prefix}_close_side_state"
        )

        df[
            delta_col
        ] = df.apply(
            lambda r,
            p=prefix:
                directional_close_delta_pct(
                    r[
                        "direction"
                    ],
                    r[
                        f"{p}_close"
                    ],
                    r[
                        "postsignal_reference_price"
                    ],
                ),
            axis=1,
        )

        df[
            fav_col
        ] = df.apply(
            lambda r,
            p=prefix:
                favorable_excursion_pct(
                    r[
                        "direction"
                    ],
                    r[
                        f"{p}_high"
                    ],
                    r[
                        f"{p}_low"
                    ],
                    r[
                        "postsignal_reference_price"
                    ],
                ),
            axis=1,
        )

        df[
            adv_col
        ] = df.apply(
            lambda r,
            p=prefix:
                adverse_excursion_pct(
                    r[
                        "direction"
                    ],
                    r[
                        f"{p}_high"
                    ],
                    r[
                        f"{p}_low"
                    ],
                    r[
                        "postsignal_reference_price"
                    ],
                ),
            axis=1,
        )

        df[
            state_col
        ] = df[
            delta_col
        ].apply(
            close_side_state
        )

    # =========================================================================
    # CUMULATIVE MFE / MAE THROUGH EACH BAR
    # =========================================================================

    running_fav_cols = []
    running_adv_cols = []

    for candle_number in (
        POST_BARS
    ):

        prefix = (
            f"post_c"
            f"{candle_number}"
        )

        running_fav_cols.append(
            f"{prefix}_fav_excursion_pct"
        )

        running_adv_cols.append(
            f"{prefix}_adv_excursion_pct"
        )

        df[
            f"{prefix}_cumulative_mfe_pct"
        ] = (
            df[
                running_fav_cols
            ]
            .max(
                axis=1,
                skipna=True,
            )
        )

        df[
            f"{prefix}_cumulative_mae_pct"
        ] = (
            df[
                running_adv_cols
            ]
            .max(
                axis=1,
                skipna=True,
            )
        )

    # =========================================================================
    # C3/C4 FOUNDATIONAL PATH
    # =========================================================================

    df[
        "early_path_state"
    ] = df.apply(
        classify_early_path,
        axis=1,
    )

    df[
        "c3_c4_transition_state"
    ] = df.apply(
        classify_c3_c4_transition,
        axis=1,
    )

    # =========================================================================
    # ADDITIONAL EARLY PROGRESSION FEATURES
    # =========================================================================

    df[
        "c3_to_c4_close_progress_pct"
    ] = (
        df[
            "post_c4_close_delta_pct"
        ]
        -
        df[
            "post_c3_close_delta_pct"
        ]
    )

    def progression_state(
        value: float,
    ) -> str:

        if pd.isna(value):
            return "UNKNOWN"

        if value > 0:
            return "IMPROVING"

        if value < 0:
            return "DETERIORATING"

        return "UNCHANGED"

    df[
        "c3_to_c4_progression_state"
    ] = df[
        "c3_to_c4_close_progress_pct"
    ].apply(
        progression_state
    )

    # =========================================================================
    # C3-C10 CLOSE-SIDE COUNTS
    # =========================================================================

    favorable_side_cols = []

    adverse_side_cols = []

    for candle_number in (
        POST_BARS
    ):

        state_col = (
            f"post_c"
            f"{candle_number}"
            f"_close_side_state"
        )

        favorable_side_cols.append(
            (
                df[
                    state_col
                ]
                == "FAVORABLE_SIDE"
            )
            .astype(int)
        )

        adverse_side_cols.append(
            (
                df[
                    state_col
                ]
                == "ADVERSE_SIDE"
            )
            .astype(int)
        )

    df[
        "c3_c10_favorable_close_n"
    ] = sum(
        favorable_side_cols
    )

    df[
        "c3_c10_adverse_close_n"
    ] = sum(
        adverse_side_cols
    )

    # =========================================================================
    # QUARTER / VALIDATION SUBPERIOD
    # =========================================================================

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

    validation = df.loc[
        df[
            "research_period"
        ]
        == "VALIDATION"
    ].copy()

    validation_dates = sorted(
        validation[
            "trade_date"
        ]
        .dropna()
        .unique()
    )

    if not validation_dates:

        raise RuntimeError(
            "Validation population is empty."
        )

    validation_midpoint = pd.Timestamp(
        validation_dates[
            len(validation_dates)
            // 2
        ]
    )

    df[
        "validation_subperiod"
    ] = "NOT_VALIDATION"

    df.loc[
        (
            df[
                "research_period"
            ]
            == "VALIDATION"
        )
        &
        (
            df[
                "trade_date"
            ]
            < validation_midpoint
        ),
        "validation_subperiod",
    ] = "VALIDATION_OLDER"

    df.loc[
        (
            df[
                "research_period"
            ]
            == "VALIDATION"
        )
        &
        (
            df[
                "trade_date"
            ]
            >= validation_midpoint
        ),
        "validation_subperiod",
    ] = "VALIDATION_NEWER"

    # =========================================================================
    # COVERAGE
    # =========================================================================

    coverage_rows = []

    for candle_number in (
        POST_BARS
    ):

        close_col = (
            f"post_c"
            f"{candle_number}"
            f"_close"
        )

        n = int(
            df[
                close_col
            ]
            .notna()
            .sum()
        )

        coverage_rows.append(
            {
                "candle":
                    f"C{candle_number}",

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
    # PATH SUMMARY
    # =========================================================================

    path_summary = summarize(
        df,
        [
            "research_period",
            "early_path_state",
        ],
    )

    path_summary.to_csv(
        PATH_SUMMARY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # DIRECTION
    # =========================================================================

    direction_summary = summarize(
        df,
        [
            "research_period",
            "direction",
            "early_path_state",
        ],
    )

    direction_summary.to_csv(
        DIRECTION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # QUARTER
    # =========================================================================

    quarter_summary = summarize(
        df,
        [
            "quarter",
            "early_path_state",
        ],
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # TRANSITIONS
    # =========================================================================

    transition_summary = summarize(
        df,
        [
            "research_period",
            "c3_c4_transition_state",
        ],
    )

    transition_summary.to_csv(
        TRANSITION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # VALIDATION SENSITIVITY
    # =========================================================================

    sensitivity_rows = []

    subsets = [
        (
            "BASE",
            df,
        ),
        (
            "EXCLUDE_SPY_QQQ_TQQQ",
            df.loc[
                ~df[
                    "symbol"
                ].isin(
                    EXCLUDE_SYMBOLS
                )
            ],
        ),
    ]

    period_specs = [
        (
            "research_period",
            "DISCOVERY",
        ),
        (
            "research_period",
            "VALIDATION",
        ),
        (
            "validation_subperiod",
            "VALIDATION_OLDER",
        ),
        (
            "validation_subperiod",
            "VALIDATION_NEWER",
        ),
    ]

    for (
        sensitivity_name,
        subset,
    ) in subsets:

        for (
            period_col,
            period_value,
        ) in period_specs:

            period_subset = subset.loc[
                subset[
                    period_col
                ]
                == period_value
            ]

            if period_subset.empty:
                continue

            for path_state in sorted(
                period_subset[
                    "early_path_state"
                ].dropna().unique()
            ):

                x = period_subset.loc[
                    period_subset[
                        "early_path_state"
                    ]
                    == path_state
                ]

                row = {
                    "sensitivity":
                        sensitivity_name,

                    "period_type":
                        period_col,

                    "period":
                        period_value,

                    "early_path_state":
                        path_state,
                }

                row.update(
                    summarize_group(x)
                )

                sensitivity_rows.append(
                    row
                )

    sensitivity = pd.DataFrame(
        sensitivity_rows
    )

    sensitivity.to_csv(
        SENSITIVITY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # TRAJECTORY
    #
    # Mean cumulative MFE / MAE by path and research period.
    # =========================================================================

    trajectory_rows = []

    for (
        period,
        path_state,
    ), x in df.groupby(
        [
            "research_period",
            "early_path_state",
        ],
        dropna=False,
    ):

        for candle_number in (
            POST_BARS
        ):

            prefix = (
                f"post_c"
                f"{candle_number}"
            )

            trajectory_rows.append(
                {
                    "research_period":
                        period,

                    "early_path_state":
                        path_state,

                    "candle":
                        f"C{candle_number}",

                    "elapsed_after_c2":
                        (
                            candle_number
                            - 2
                        ),

                    "total_n":
                        int(
                            len(x)
                        ),

                    "avg_close_delta_pct":
                        x[
                            f"{prefix}_close_delta_pct"
                        ].mean(),

                    "avg_cumulative_mfe_pct":
                        x[
                            f"{prefix}_cumulative_mfe_pct"
                        ].mean(),

                    "avg_cumulative_mae_pct":
                        x[
                            f"{prefix}_cumulative_mae_pct"
                        ].mean(),

                    "median_cumulative_mfe_pct":
                        x[
                            f"{prefix}_cumulative_mfe_pct"
                        ].median(),

                    "median_cumulative_mae_pct":
                        x[
                            f"{prefix}_cumulative_mae_pct"
                        ].median(),
                }
            )

    trajectory = pd.DataFrame(
        trajectory_rows
    )

    trajectory.to_csv(
        TRAJECTORY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SYMBOL BREADTH
    # =========================================================================

    symbol_summary = summarize(
        df,
        [
            "early_path_state",
            "symbol",
        ],
    )

    symbol_summary.to_csv(
        SYMBOL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SAVE FEATURES
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
        "C3-C10 COVERAGE"
    )

    print(
        "=" * 80
    )

    print(
        coverage.to_string(
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
        "EARLY PATH — DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    print(
        path_summary[
            [
                "research_period",
                "early_path_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "early_path_state",
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
        "EARLY PATH — VALIDATION DIRECTIONAL"
    )

    print(
        "=" * 80
    )

    x = direction_summary.loc[
        direction_summary[
            "research_period"
        ]
        == "VALIDATION"
    ]

    print(
        x[
            [
                "direction",
                "early_path_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "direction",
                "early_path_state",
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
        "C3 → C4 TRANSITIONS"
    )

    print(
        "=" * 80
    )

    print(
        transition_summary[
            [
                "research_period",
                "c3_c4_transition_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "c3_c4_transition_state",
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
        "VALIDATION SUBPERIOD / SENSITIVITY"
    )

    print(
        "=" * 80
    )

    print(
        sensitivity[
            [
                "sensitivity",
                "period",
                "early_path_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "sensitivity",
                "period",
                "early_path_state",
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
        "EARLY PATH — QUARTER STABILITY"
    )

    print(
        "=" * 80
    )

    print(
        quarter_summary[
            [
                "quarter",
                "early_path_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "quarter",
                "early_path_state",
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
        "C3-C10 TRAJECTORY — VALIDATION"
    )

    print(
        "=" * 80
    )

    x = trajectory.loc[
        trajectory[
            "research_period"
        ]
        == "VALIDATION"
    ]

    x = x.sort_values(
        [
            "early_path_state",
            "elapsed_after_c2",
        ]
    )

    print(
        x[
            [
                "early_path_state",
                "candle",
                "total_n",
                "avg_close_delta_pct",
                "avg_cumulative_mfe_pct",
                "avg_cumulative_mae_pct",
            ]
        ]
        .to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.4f}",
        )
    )

    print()

    print(
        f"Validation midpoint: "
        f"{validation_midpoint.date()}"
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
        f"Features:      "
        f"{FEATURE_OUTPUT}"
    )

    print(
        f"Path summary:  "
        f"{PATH_SUMMARY_OUTPUT}"
    )

    print(
        f"Direction:     "
        f"{DIRECTION_OUTPUT}"
    )

    print(
        f"Quarter:       "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Sensitivity:   "
        f"{SENSITIVITY_OUTPUT}"
    )

    print(
        f"Trajectory:    "
        f"{TRAJECTORY_OUTPUT}"
    )

    print(
        f"Transitions:   "
        f"{TRANSITION_OUTPUT}"
    )

    print(
        f"Coverage:      "
        f"{COVERAGE_OUTPUT}"
    )

    print(
        f"Symbols:       "
        f"{SYMBOL_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()