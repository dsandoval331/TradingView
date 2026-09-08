from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# CONFIG
# =============================================================================

ROOT = Path(
    r"C:\Users\DirtySouth\TradingResearch"
)

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

INPUT_PATH = (
    RESEARCH_ROOT
    / "ae2_postsignal_paths_v1"
    / "ae2_postsignal_path_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_warning_timing_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_timing_features_v1.parquet"
)

WARNING_SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_timing_summary_v1.csv"
)

FIRST_WARNING_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_first_warning_candle_v1.csv"
)

PERSISTENCE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_persistence_v1.csv"
)

RECOVERY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_recovery_v1.csv"
)

VWAP_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_vwap_v1.csv"
)

TRAJECTORY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_trajectory_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_direction_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_quarter_v1.csv"
)

SENSITIVITY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_sensitivity_v1.csv"
)

COVERAGE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_coverage_v1.csv"
)

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
# GENERIC HELPERS
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


def first_true_candle(
    row: pd.Series,
    columns: list[str],
) -> float:

    for candle_number, col in zip(
        POST_BARS,
        columns,
    ):

        value = row[
            col
        ]

        if (
            not pd.isna(value)
            and bool(value)
        ):
            return float(
                candle_number
            )

    return np.nan


def first_recovery_after(
    row: pd.Series,
    first_warning_candle: float,
) -> float:

    if pd.isna(
        first_warning_candle
    ):
        return np.nan

    start = int(
        first_warning_candle
    ) + 1

    for candle_number in range(
        start,
        11,
    ):

        state = row.get(
            f"post_c{candle_number}_close_side_state",
            "UNKNOWN",
        )

        if (
            state
            == "FAVORABLE_SIDE"
        ):
            return float(
                candle_number
            )

    return np.nan


def vwap_side_state(
    direction: str,
    close: float,
    vwap: float,
) -> str:

    if (
        pd.isna(close)
        or pd.isna(vwap)
    ):
        return "UNKNOWN"

    if direction == "BULL":

        if close > vwap:
            return "FAVORABLE_VWAP_SIDE"

        if close < vwap:
            return "ADVERSE_VWAP_SIDE"

        return "AT_VWAP"

    if direction == "BEAR":

        if close < vwap:
            return "FAVORABLE_VWAP_SIDE"

        if close > vwap:
            return "ADVERSE_VWAP_SIDE"

        return "AT_VWAP"

    return "UNKNOWN"


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

    required = [
        "symbol",
        "trade_date",
        "direction",
        "research_period",
        "outcome",
        "final_mfe_pct",
        "final_mae_pct",
        "early_path_state",
    ]

    for candle_number in (
        POST_BARS
    ):

        required.extend(
            [
                f"post_c{candle_number}_close",
                f"post_c{candle_number}_vwap",
                f"post_c{candle_number}_close_delta_pct",
                f"post_c{candle_number}_close_side_state",
                f"post_c{candle_number}_cumulative_mfe_pct",
                f"post_c{candle_number}_cumulative_mae_pct",
            ]
        )

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing required columns: "
            + ", ".join(
                missing
            )
        )

    df[
        "trade_date"
    ] = pd.to_datetime(
        df[
            "trade_date"
        ],
        errors="coerce",
    )

    df[
        "symbol"
    ] = (
        df[
            "symbol"
        ]
        .astype(str)
        .str.upper()
    )

    print(
        "=" * 80
    )

    print(
        "AE2 WARNING TIMING / DETERIORATION V1"
    )

    print(
        "=" * 80
    )

    print(
        f"AE2 events: "
        f"{len(df):,}"
    )

    print(
        f"Symbols:    "
        f"{df['symbol'].nunique():,}"
    )

    # =========================================================================
    # PER-CANDLE REFERENCE-SIDE WARNING STATES
    # =========================================================================

    adverse_flag_cols = []
    favorable_flag_cols = []

    for candle_number in (
        POST_BARS
    ):

        state_col = (
            f"post_c"
            f"{candle_number}"
            f"_close_side_state"
        )

        adverse_col = (
            f"post_c"
            f"{candle_number}"
            f"_adverse_close_flag"
        )

        favorable_col = (
            f"post_c"
            f"{candle_number}"
            f"_favorable_close_flag"
        )

        df[
            adverse_col
        ] = (
            df[
                state_col
            ]
            == "ADVERSE_SIDE"
        )

        df[
            favorable_col
        ] = (
            df[
                state_col
            ]
            == "FAVORABLE_SIDE"
        )

        adverse_flag_cols.append(
            adverse_col
        )

        favorable_flag_cols.append(
            favorable_col
        )

    # =========================================================================
    # FIRST ADVERSE CLOSE
    # =========================================================================

    df[
        "first_adverse_close_candle"
    ] = df.apply(
        lambda r:
            first_true_candle(
                r,
                adverse_flag_cols,
            ),
        axis=1,
    )

    df[
        "ever_adverse_close_c3_c10"
    ] = (
        df[
            adverse_flag_cols
        ]
        .any(
            axis=1
        )
    )

    # =========================================================================
    # FIRST TWO CONSECUTIVE ADVERSE CLOSES
    # =========================================================================

    consecutive_cols = []

    for candle_number in range(
        4,
        11,
    ):

        current_col = (
            f"post_c"
            f"{candle_number}"
            f"_adverse_close_flag"
        )

        prior_col = (
            f"post_c"
            f"{candle_number - 1}"
            f"_adverse_close_flag"
        )

        output_col = (
            f"post_c"
            f"{candle_number}"
            f"_two_consecutive_adverse_flag"
        )

        df[
            output_col
        ] = (
            df[
                prior_col
            ]
            &
            df[
                current_col
            ]
        )

        consecutive_cols.append(
            output_col
        )

    def first_two_adverse(
        r: pd.Series,
    ) -> float:

        for candle_number in range(
            4,
            11,
        ):

            col = (
                f"post_c"
                f"{candle_number}"
                f"_two_consecutive_adverse_flag"
            )

            if bool(
                r[
                    col
                ]
            ):
                return float(
                    candle_number
                )

        return np.nan

    df[
        "first_two_consecutive_adverse_candle"
    ] = df.apply(
        first_two_adverse,
        axis=1,
    )

    df[
        "ever_two_consecutive_adverse"
    ] = (
        df[
            consecutive_cols
        ]
        .any(
            axis=1
        )
    )

    # =========================================================================
    # FAVORABLE -> ADVERSE TRANSITION
    # =========================================================================

    transition_cols = []

    for candle_number in range(
        4,
        11,
    ):

        prior_state = (
            f"post_c"
            f"{candle_number - 1}"
            f"_close_side_state"
        )

        current_state = (
            f"post_c"
            f"{candle_number}"
            f"_close_side_state"
        )

        output_col = (
            f"post_c"
            f"{candle_number}"
            f"_fav_to_adv_transition_flag"
        )

        df[
            output_col
        ] = (
            (
                df[
                    prior_state
                ]
                == "FAVORABLE_SIDE"
            )
            &
            (
                df[
                    current_state
                ]
                == "ADVERSE_SIDE"
            )
        )

        transition_cols.append(
            output_col
        )

    def first_fav_to_adv(
        r: pd.Series,
    ) -> float:

        for candle_number in range(
            4,
            11,
        ):

            col = (
                f"post_c"
                f"{candle_number}"
                f"_fav_to_adv_transition_flag"
            )

            if bool(
                r[
                    col
                ]
            ):
                return float(
                    candle_number
                )

        return np.nan

    df[
        "first_favorable_to_adverse_candle"
    ] = df.apply(
        first_fav_to_adv,
        axis=1,
    )

    # =========================================================================
    # RECOVERY AFTER FIRST ADVERSE CLOSE
    # =========================================================================

    df[
        "first_recovery_after_adverse_candle"
    ] = df.apply(
        lambda r:
            first_recovery_after(
                r,
                r[
                    "first_adverse_close_candle"
                ],
            ),
        axis=1,
    )

    df[
        "recovered_after_adverse"
    ] = (
        df[
            "first_recovery_after_adverse_candle"
        ]
        .notna()
    )

    df[
        "adverse_warning_persisted_to_c10"
    ] = (
        df[
            "ever_adverse_close_c3_c10"
        ]
        &
        ~df[
            "recovered_after_adverse"
        ]
    )

    df[
        "recovery_delay_bars"
    ] = (
        df[
            "first_recovery_after_adverse_candle"
        ]
        -
        df[
            "first_adverse_close_candle"
        ]
    )

    # =========================================================================
    # MAE / MFE AT FIRST WARNING
    # =========================================================================

    def value_at_first_warning(
        r: pd.Series,
        suffix: str,
    ) -> float:

        candle = r[
            "first_adverse_close_candle"
        ]

        if pd.isna(
            candle
        ):
            return np.nan

        candle_number = int(
            candle
        )

        return r[
            f"post_c"
            f"{candle_number}"
            f"_{suffix}"
        ]

    df[
        "mfe_at_first_adverse_warning_pct"
    ] = df.apply(
        lambda r:
            value_at_first_warning(
                r,
                "cumulative_mfe_pct",
            ),
        axis=1,
    )

    df[
        "mae_at_first_adverse_warning_pct"
    ] = df.apply(
        lambda r:
            value_at_first_warning(
                r,
                "cumulative_mae_pct",
            ),
        axis=1,
    )

    df[
        "close_delta_at_first_adverse_warning_pct"
    ] = df.apply(
        lambda r:
            value_at_first_warning(
                r,
                "close_delta_pct",
            ),
        axis=1,
    )

    # =========================================================================
    # DETERIORATION SPEED
    #
    # Change in directional close delta from prior candle to warning candle.
    # More negative = faster deterioration.
    # =========================================================================

    def deterioration_speed(
        r: pd.Series,
    ) -> float:

        candle = r[
            "first_adverse_close_candle"
        ]

        if pd.isna(
            candle
        ):
            return np.nan

        candle_number = int(
            candle
        )

        current_delta = r[
            f"post_c"
            f"{candle_number}"
            f"_close_delta_pct"
        ]

        if candle_number == 3:

            prior_delta = 0.0

        else:

            prior_delta = r[
                f"post_c"
                f"{candle_number - 1}"
                f"_close_delta_pct"
            ]

        if (
            pd.isna(current_delta)
            or pd.isna(prior_delta)
        ):
            return np.nan

        return (
            current_delta
            -
            prior_delta
        )

    df[
        "first_warning_deterioration_speed_pct"
    ] = df.apply(
        deterioration_speed,
        axis=1,
    )

    # =========================================================================
    # VWAP SIDE STATES
    # =========================================================================

    vwap_adverse_cols = []

    for candle_number in (
        POST_BARS
    ):

        state_col = (
            f"post_c"
            f"{candle_number}"
            f"_vwap_side_state"
        )

        adverse_col = (
            f"post_c"
            f"{candle_number}"
            f"_vwap_adverse_flag"
        )

        df[
            state_col
        ] = df.apply(
            lambda r,
            n=candle_number:
                vwap_side_state(
                    r[
                        "direction"
                    ],
                    r[
                        f"post_c{n}_close"
                    ],
                    r[
                        f"post_c{n}_vwap"
                    ],
                ),
            axis=1,
        )

        df[
            adverse_col
        ] = (
            df[
                state_col
            ]
            == "ADVERSE_VWAP_SIDE"
        )

        vwap_adverse_cols.append(
            adverse_col
        )

    df[
        "first_vwap_loss_candle"
    ] = df.apply(
        lambda r:
            first_true_candle(
                r,
                vwap_adverse_cols,
            ),
        axis=1,
    )

    df[
        "ever_vwap_loss"
    ] = (
        df[
            vwap_adverse_cols
        ]
        .any(
            axis=1
        )
    )

    def first_vwap_reclaim(
        r: pd.Series,
    ) -> float:

        first_loss = r[
            "first_vwap_loss_candle"
        ]

        if pd.isna(
            first_loss
        ):
            return np.nan

        for candle_number in range(
            int(first_loss) + 1,
            11,
        ):

            state = r[
                f"post_c"
                f"{candle_number}"
                f"_vwap_side_state"
            ]

            if (
                state
                == "FAVORABLE_VWAP_SIDE"
            ):
                return float(
                    candle_number
                )

        return np.nan

    df[
        "first_vwap_reclaim_candle"
    ] = df.apply(
        first_vwap_reclaim,
        axis=1,
    )

    df[
        "vwap_reclaimed_after_loss"
    ] = (
        df[
            "first_vwap_reclaim_candle"
        ]
        .notna()
    )

    df[
        "vwap_loss_persisted_to_c10"
    ] = (
        df[
            "ever_vwap_loss"
        ]
        &
        ~df[
            "vwap_reclaimed_after_loss"
        ]
    )

    # =========================================================================
    # PRIMARY WARNING STATE
    # =========================================================================

    def warning_state(
        r: pd.Series,
    ) -> str:

        if not r[
            "ever_adverse_close_c3_c10"
        ]:

            return "NO_REFERENCE_WARNING"

        if r[
            "adverse_warning_persisted_to_c10"
        ]:

            return "PERSISTENT_REFERENCE_WARNING"

        if r[
            "recovered_after_adverse"
        ]:

            return "REFERENCE_WARNING_RECOVERED"

        return "REFERENCE_WARNING_OTHER"

    df[
        "reference_warning_state"
    ] = df.apply(
        warning_state,
        axis=1,
    )

    def vwap_warning_state(
        r: pd.Series,
    ) -> str:

        if not r[
            "ever_vwap_loss"
        ]:

            return "NO_VWAP_WARNING"

        if r[
            "vwap_loss_persisted_to_c10"
        ]:

            return "PERSISTENT_VWAP_WARNING"

        if r[
            "vwap_reclaimed_after_loss"
        ]:

            return "VWAP_WARNING_RECOVERED"

        return "VWAP_WARNING_OTHER"

    df[
        "vwap_warning_state"
    ] = df.apply(
        vwap_warning_state,
        axis=1,
    )

    # =========================================================================
    # COMBINED WARNING COUNT
    # =========================================================================

    df[
        "warning_component_n"
    ] = (
        df[
            [
                "ever_adverse_close_c3_c10",
                "ever_two_consecutive_adverse",
                "ever_vwap_loss",
            ]
        ]
        .astype(int)
        .sum(
            axis=1
        )
    )

    def warning_count_state(
        value: int,
    ) -> str:

        if value == 0:
            return "NO_WARNING_COMPONENTS"

        if value == 1:
            return "ONE_WARNING_COMPONENT"

        if value == 2:
            return "TWO_WARNING_COMPONENTS"

        return "THREE_WARNING_COMPONENTS"

    df[
        "warning_component_state"
    ] = df[
        "warning_component_n"
    ].apply(
        warning_count_state
    )

    # =========================================================================
    # CALENDAR / VALIDATION SUBPERIOD
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

        close_n = int(
            df[
                f"post_c{candle_number}_close"
            ]
            .notna()
            .sum()
        )

        vwap_n = int(
            df[
                f"post_c{candle_number}_vwap"
            ]
            .notna()
            .sum()
        )

        coverage_rows.append(
            {
                "candle":
                    f"C{candle_number}",

                "close_available_n":
                    close_n,

                "close_coverage_pct":
                    (
                        100.0
                        * close_n
                        / len(df)
                    ),

                "vwap_available_n":
                    vwap_n,

                "vwap_coverage_pct":
                    (
                        100.0
                        * vwap_n
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
    # PRIMARY WARNING SUMMARY
    # =========================================================================

    warning_frames = []

    for feature in [
        "reference_warning_state",
        "vwap_warning_state",
        "warning_component_state",
    ]:

        x = summarize(
            df,
            [
                "research_period",
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

        warning_frames.append(
            x
        )

    warning_summary = pd.concat(
        warning_frames,
        ignore_index=True,
        sort=False,
    )

    warning_summary.to_csv(
        WARNING_SUMMARY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # FIRST WARNING CANDLE
    # =========================================================================

    first_warning_frames = []

    for feature in [
        "first_adverse_close_candle",
        "first_two_consecutive_adverse_candle",
        "first_favorable_to_adverse_candle",
        "first_vwap_loss_candle",
    ]:

        temp = df.copy()

        temp[
            feature
        ] = temp[
            feature
        ].fillna(
            -1
        )

        x = summarize(
            temp,
            [
                "research_period",
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

        first_warning_frames.append(
            x
        )

    first_warning = pd.concat(
        first_warning_frames,
        ignore_index=True,
        sort=False,
    )

    first_warning.to_csv(
        FIRST_WARNING_OUTPUT,
        index=False,
    )

    # =========================================================================
    # WARNING PERSISTENCE
    # =========================================================================

    persistence = summarize(
        df,
        [
            "research_period",
            "adverse_warning_persisted_to_c10",
        ],
    )

    persistence.to_csv(
        PERSISTENCE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # RECOVERY
    # =========================================================================

    recovery = summarize(
        df.loc[
            df[
                "ever_adverse_close_c3_c10"
            ]
        ],
        [
            "research_period",
            "recovered_after_adverse",
        ],
    )

    recovery.to_csv(
        RECOVERY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # VWAP
    # =========================================================================

    vwap_summary = summarize(
        df,
        [
            "research_period",
            "vwap_warning_state",
        ],
    )

    vwap_summary.to_csv(
        VWAP_OUTPUT,
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
            "reference_warning_state",
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
            "reference_warning_state",
        ],
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # WARNING TRAJECTORY / SEVERITY
    # =========================================================================

    trajectory_rows = []

    warning_subset = df.loc[
        df[
            "first_adverse_close_candle"
        ]
        .notna()
    ]

    for (
        period,
        warning_candle,
    ), x in warning_subset.groupby(
        [
            "research_period",
            "first_adverse_close_candle",
        ],
        dropna=False,
    ):

        trajectory_rows.append(
            {
                "research_period":
                    period,

                "first_warning_candle":
                    warning_candle,

                "total_n":
                    int(len(x)),

                "binary_n":
                    int(
                        (
                            x[
                                "outcome"
                            ]
                            .isin(
                                [
                                    "FAVORABLE_FIRST",
                                    "ADVERSE_FIRST",
                                ]
                            )
                        )
                        .sum()
                    ),

                "favorable_first_pct":
                    (
                        100.0
                        *
                        (
                            x[
                                "outcome"
                            ]
                            == "FAVORABLE_FIRST"
                        ).sum()
                        /
                        max(
                            1,
                            (
                                x[
                                    "outcome"
                                ]
                                .isin(
                                    [
                                        "FAVORABLE_FIRST",
                                        "ADVERSE_FIRST",
                                    ]
                                )
                            )
                            .sum()
                        )
                    ),

                "avg_mfe_at_warning_pct":
                    x[
                        "mfe_at_first_adverse_warning_pct"
                    ].mean(),

                "avg_mae_at_warning_pct":
                    x[
                        "mae_at_first_adverse_warning_pct"
                    ].mean(),

                "avg_close_delta_at_warning_pct":
                    x[
                        "close_delta_at_first_adverse_warning_pct"
                    ].mean(),

                "avg_deterioration_speed_pct":
                    x[
                        "first_warning_deterioration_speed_pct"
                    ].mean(),

                "recovery_pct":
                    (
                        100.0
                        * x[
                            "recovered_after_adverse"
                        ].mean()
                    ),
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
    # SENSITIVITY
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

            for state in sorted(
                period_subset[
                    "reference_warning_state"
                ]
                .dropna()
                .unique()
            ):

                x = period_subset.loc[
                    period_subset[
                        "reference_warning_state"
                    ]
                    == state
                ]

                row = {
                    "sensitivity":
                        sensitivity_name,

                    "period_type":
                        period_col,

                    "period":
                        period_value,

                    "reference_warning_state":
                        state,
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
        "WARNING DATA COVERAGE"
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
        "REFERENCE WARNING STATE — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    x = warning_summary.loc[
        warning_summary[
            "feature"
        ]
        == "reference_warning_state"
    ]

    print(
        x[
            [
                "research_period",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
                "symbol_n",
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
        "VWAP WARNING STATE — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    print(
        vwap_summary[
            [
                "research_period",
                "vwap_warning_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "vwap_warning_state",
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
        "FIRST WARNING CANDLE"
    )

    print(
        "=" * 80
    )

    print(
        first_warning[
            [
                "feature",
                "research_period",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
            ]
        ]
        .sort_values(
            [
                "feature",
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
        "WARNING RECOVERY"
    )

    print(
        "=" * 80
    )

    print(
        recovery[
            [
                "research_period",
                "recovered_after_adverse",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "recovered_after_adverse",
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
        "WARNING TRAJECTORY / TIMING"
    )

    print(
        "=" * 80
    )

    print(
        trajectory.sort_values(
            [
                "research_period",
                "first_warning_candle",
            ]
        )
        .to_string(
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
        "REFERENCE WARNING — "
        "VALIDATION DIRECTIONAL"
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
                "reference_warning_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "direction",
                "reference_warning_state",
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
        "REFERENCE WARNING — "
        "QUARTER STABILITY"
    )

    print(
        "=" * 80
    )

    print(
        quarter_summary[
            [
                "quarter",
                "reference_warning_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
            ]
        ]
        .sort_values(
            [
                "quarter",
                "reference_warning_state",
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
        "REFERENCE WARNING — "
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
                "reference_warning_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "sensitivity",
                "period",
                "reference_warning_state",
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
        f"Warnings:      "
        f"{WARNING_SUMMARY_OUTPUT}"
    )

    print(
        f"First warning: "
        f"{FIRST_WARNING_OUTPUT}"
    )

    print(
        f"Persistence:   "
        f"{PERSISTENCE_OUTPUT}"
    )

    print(
        f"Recovery:      "
        f"{RECOVERY_OUTPUT}"
    )

    print(
        f"VWAP:          "
        f"{VWAP_OUTPUT}"
    )

    print(
        f"Trajectory:    "
        f"{TRAJECTORY_OUTPUT}"
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
        f"Coverage:      "
        f"{COVERAGE_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()