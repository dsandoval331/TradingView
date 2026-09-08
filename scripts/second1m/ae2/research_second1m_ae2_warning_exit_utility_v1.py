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
    / "ae2_warning_timing_v1"
    / "ae2_warning_timing_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_warning_exit_utility_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_exit_utility_features_v1.parquet"
)

POLICY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_exit_policy_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_exit_policy_direction_v1.csv"
)

TEMPORAL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_exit_policy_temporal_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_exit_policy_quarter_v1.csv"
)

OUTCOME_COST_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_exit_outcome_cost_v1.csv"
)

ACTIONABILITY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_exit_actionability_v1.csv"
)

RECOVERY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_exit_recovery_delay_v1.csv"
)

TARGET_PCT = 0.50

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

def normalize_date(
    series: pd.Series,
) -> pd.Series:

    return (
        pd.to_datetime(
            series,
            errors="coerce",
        )
        .dt
        .normalize()
    )


def hold_benchmark_return(
    outcome: str,
) -> float:

    if outcome == "FAVORABLE_FIRST":
        return TARGET_PCT

    if outcome == "ADVERSE_FIRST":
        return -TARGET_PCT

    return np.nan


def directional_return_pct(
    direction: str,
    entry_price: float,
    exit_price: float,
) -> float:

    if (
        pd.isna(entry_price)
        or pd.isna(exit_price)
        or entry_price == 0
    ):
        return np.nan

    if direction == "BULL":

        return (
            (
                exit_price
                - entry_price
            )
            / entry_price
            * 100.0
        )

    if direction == "BEAR":

        return (
            (
                entry_price
                - exit_price
            )
            / entry_price
            * 100.0
        )

    return np.nan


# =============================================================================
# WARNING-CANDLE HELPERS
# =============================================================================

def first_three_consecutive_adverse(
    row: pd.Series,
) -> float:

    for candle_number in range(
        5,
        11,
    ):

        s1 = row[
            f"post_c{candle_number - 2}_close_side_state"
        ]

        s2 = row[
            f"post_c{candle_number - 1}_close_side_state"
        ]

        s3 = row[
            f"post_c{candle_number}_close_side_state"
        ]

        if (
            s1 == "ADVERSE_SIDE"
            and s2 == "ADVERSE_SIDE"
            and s3 == "ADVERSE_SIDE"
        ):

            return float(
                candle_number
            )

    return np.nan


def first_no_recovery_within_one_bar(
    row: pd.Series,
) -> float:
    """
    Warning becomes actionable one candle AFTER the initial adverse close.

    Example:
        C3 adverse
        C4 still not favorable

    => warning action at C4 close.
    """

    first_warning = row[
        "first_adverse_close_candle"
    ]

    if pd.isna(
        first_warning
    ):
        return np.nan

    first_warning = int(
        first_warning
    )

    confirmation_candle = (
        first_warning
        + 1
    )

    if confirmation_candle > 10:
        return np.nan

    state = row[
        f"post_c{confirmation_candle}_close_side_state"
    ]

    if state != "FAVORABLE_SIDE":

        return float(
            confirmation_candle
        )

    return np.nan


def clean_actionable_at_candle(
    row: pd.Series,
    candle_number: int,
) -> bool:
    """
    Conservative actionability gate.

    To evaluate a warning exit at candle N:
      cumulative MFE through N must still be < +0.50%
      cumulative MAE through N must still be < +0.50%

    Therefore neither frozen benchmark has been touched through the warning bar.
    """

    mfe = row[
        f"post_c{candle_number}_cumulative_mfe_pct"
    ]

    mae = row[
        f"post_c{candle_number}_cumulative_mae_pct"
    ]

    if (
        pd.isna(mfe)
        or pd.isna(mae)
    ):
        return False

    return bool(
        mfe < TARGET_PCT
        and mae < TARGET_PCT
    )


def policy_exit_return(
    row: pd.Series,
    warning_candle: float,
) -> float:

    if pd.isna(
        warning_candle
    ):
        return np.nan

    candle_number = int(
        warning_candle
    )

    exit_price = row[
        f"post_c{candle_number}_close"
    ]

    return directional_return_pct(
        row[
            "direction"
        ],
        row[
            "c2_close"
        ],
        exit_price,
    )


# =============================================================================
# POLICY SUMMARY
# =============================================================================

def summarize_policy(
    subset: pd.DataFrame,
) -> dict:

    binary = subset.loc[
        subset[
            "hold_return_pct"
        ]
        .notna()
    ].copy()

    actionable = binary.loc[
        binary[
            "policy_clean_actionable"
        ]
    ].copy()

    if actionable.empty:

        return {
            "total_signal_n":
                int(
                    len(subset)
                ),

            "binary_signal_n":
                int(
                    len(binary)
                ),

            "actionable_n":
                0,

            "actionable_pct":
                0.0,

            "avg_exit_return_pct":
                np.nan,

            "median_exit_return_pct":
                np.nan,

            "avg_hold_return_pct":
                np.nan,

            "avg_policy_improvement_pp":
                np.nan,

            "policy_better_n":
                0,

            "policy_better_pct":
                np.nan,

            "eventual_favorable_n":
                0,

            "eventual_adverse_n":
                0,

            "avg_saved_on_adverse_pp":
                np.nan,

            "avg_foregone_on_favorable_pp":
                np.nan,

            "symbol_n":
                0,
        }

    actionable[
        "policy_improvement_pp"
    ] = (
        actionable[
            "policy_exit_return_pct"
        ]
        -
        actionable[
            "hold_return_pct"
        ]
    )

    eventual_adverse = actionable.loc[
        actionable[
            "outcome"
        ]
        == "ADVERSE_FIRST"
    ]

    eventual_favorable = actionable.loc[
        actionable[
            "outcome"
        ]
        == "FAVORABLE_FIRST"
    ]

    return {
        "total_signal_n":
            int(
                len(subset)
            ),

        "binary_signal_n":
            int(
                len(binary)
            ),

        "actionable_n":
            int(
                len(actionable)
            ),

        "actionable_pct":
            (
                100.0
                * len(actionable)
                / len(binary)
                if len(binary)
                else np.nan
            ),

        "avg_exit_return_pct":
            actionable[
                "policy_exit_return_pct"
            ].mean(),

        "median_exit_return_pct":
            actionable[
                "policy_exit_return_pct"
            ].median(),

        "avg_hold_return_pct":
            actionable[
                "hold_return_pct"
            ].mean(),

        "avg_policy_improvement_pp":
            actionable[
                "policy_improvement_pp"
            ].mean(),

        "policy_better_n":
            int(
                (
                    actionable[
                        "policy_improvement_pp"
                    ]
                    > 0
                ).sum()
            ),

        "policy_better_pct":
            (
                100.0
                * (
                    actionable[
                        "policy_improvement_pp"
                    ]
                    > 0
                ).mean()
            ),

        "eventual_favorable_n":
            int(
                len(
                    eventual_favorable
                )
            ),

        "eventual_adverse_n":
            int(
                len(
                    eventual_adverse
                )
            ),

        "avg_saved_on_adverse_pp":
            (
                eventual_adverse[
                    "policy_exit_return_pct"
                ]
                + TARGET_PCT
            ).mean(),

        "avg_foregone_on_favorable_pp":
            (
                TARGET_PCT
                -
                eventual_favorable[
                    "policy_exit_return_pct"
                ]
            ).mean(),

        "symbol_n":
            actionable[
                "symbol"
            ].nunique(),
    }


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
        "c2_close",
        "first_adverse_close_candle",
        "first_two_consecutive_adverse_candle",
        "first_favorable_to_adverse_candle",
        "first_recovery_after_adverse_candle",
    ]

    for candle_number in (
        POST_BARS
    ):

        required.extend(
            [
                f"post_c{candle_number}_close",
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
        "symbol"
    ] = (
        df[
            "symbol"
        ]
        .astype(str)
        .str.upper()
    )

    df[
        "trade_date"
    ] = normalize_date(
        df[
            "trade_date"
        ]
    )

    print(
        "=" * 80
    )

    print(
        "AE2 REAL-TIME WARNING EXIT UTILITY V1"
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
    # FROZEN HOLD BENCHMARK
    # =========================================================================

    df[
        "hold_return_pct"
    ] = df[
        "outcome"
    ].apply(
        hold_benchmark_return
    )

    # =========================================================================
    # DERIVE WARNING POLICIES
    # =========================================================================

    df[
        "first_three_consecutive_adverse_candle"
    ] = df.apply(
        first_three_consecutive_adverse,
        axis=1,
    )

    df[
        "first_one_bar_nonrecovery_candle"
    ] = df.apply(
        first_no_recovery_within_one_bar,
        axis=1,
    )

    policy_specs = [
        (
            "FIRST_ADVERSE_CLOSE",
            "first_adverse_close_candle",
        ),

        (
            "TWO_CONSECUTIVE_ADVERSE",
            "first_two_consecutive_adverse_candle",
        ),

        (
            "THREE_CONSECUTIVE_ADVERSE",
            "first_three_consecutive_adverse_candle",
        ),

        (
            "FAVORABLE_TO_ADVERSE_TRANSITION",
            "first_favorable_to_adverse_candle",
        ),

        (
            "ONE_BAR_NONRECOVERY",
            "first_one_bar_nonrecovery_candle",
        ),
    ]

    # =========================================================================
    # LONG FORM POLICY DATASET
    # =========================================================================

    policy_frames = []

    for (
        policy_name,
        candle_col,
    ) in policy_specs:

        x = df.copy()

        x[
            "policy_name"
        ] = policy_name

        x[
            "policy_warning_candle"
        ] = x[
            candle_col
        ]

        x[
            "policy_triggered"
        ] = x[
            "policy_warning_candle"
        ].notna()

        x[
            "policy_clean_actionable"
        ] = False

        x[
            "policy_exit_return_pct"
        ] = np.nan

        triggered_idx = x.index[
            x[
                "policy_triggered"
            ]
        ]

        for idx in triggered_idx:

            candle = int(
                x.at[
                    idx,
                    "policy_warning_candle",
                ]
            )

            clean = clean_actionable_at_candle(
                x.loc[
                    idx
                ],
                candle,
            )

            x.at[
                idx,
                "policy_clean_actionable",
            ] = clean

            if clean:

                x.at[
                    idx,
                    "policy_exit_return_pct",
                ] = policy_exit_return(
                    x.loc[
                        idx
                    ],
                    candle,
                )

        policy_frames.append(
            x
        )

    policies = pd.concat(
        policy_frames,
        ignore_index=True,
    )

    # =========================================================================
    # POLICY SUMMARY — DISCOVERY VS VALIDATION
    # =========================================================================

    summary_rows = []

    for (
        period,
        policy_name,
    ), x in policies.groupby(
        [
            "research_period",
            "policy_name",
        ],
        dropna=False,
    ):

        row = {
            "research_period":
                period,

            "policy_name":
                policy_name,
        }

        row.update(
            summarize_policy(x)
        )

        summary_rows.append(
            row
        )

    policy_summary = pd.DataFrame(
        summary_rows
    )

    policy_summary.to_csv(
        POLICY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # DIRECTION
    # =========================================================================

    direction_rows = []

    for (
        period,
        direction,
        policy_name,
    ), x in policies.groupby(
        [
            "research_period",
            "direction",
            "policy_name",
        ],
        dropna=False,
    ):

        row = {
            "research_period":
                period,

            "direction":
                direction,

            "policy_name":
                policy_name,
        }

        row.update(
            summarize_policy(x)
        )

        direction_rows.append(
            row
        )

    direction_summary = pd.DataFrame(
        direction_rows
    )

    direction_summary.to_csv(
        DIRECTION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # VALIDATION SUBPERIOD
    # =========================================================================

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

    policies[
        "validation_subperiod"
    ] = "NOT_VALIDATION"

    policies.loc[
        (
            policies[
                "research_period"
            ]
            == "VALIDATION"
        )
        &
        (
            policies[
                "trade_date"
            ]
            < validation_midpoint
        ),
        "validation_subperiod",
    ] = "VALIDATION_OLDER"

    policies.loc[
        (
            policies[
                "research_period"
            ]
            == "VALIDATION"
        )
        &
        (
            policies[
                "trade_date"
            ]
            >= validation_midpoint
        ),
        "validation_subperiod",
    ] = "VALIDATION_NEWER"

    temporal_rows = []

    for (
        subperiod,
        policy_name,
    ), x in policies.loc[
        policies[
            "validation_subperiod"
        ]
        != "NOT_VALIDATION"
    ].groupby(
        [
            "validation_subperiod",
            "policy_name",
        ],
        dropna=False,
    ):

        row = {
            "validation_subperiod":
                subperiod,

            "policy_name":
                policy_name,
        }

        row.update(
            summarize_policy(x)
        )

        temporal_rows.append(
            row
        )

    temporal_summary = pd.DataFrame(
        temporal_rows
    )

    temporal_summary.to_csv(
        TEMPORAL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # QUARTER
    # =========================================================================

    policies[
        "quarter"
    ] = (
        policies[
            "trade_date"
        ]
        .dt
        .to_period(
            "Q"
        )
        .astype(str)
    )

    quarter_rows = []

    for (
        quarter,
        policy_name,
    ), x in policies.groupby(
        [
            "quarter",
            "policy_name",
        ],
        dropna=False,
    ):

        row = {
            "quarter":
                quarter,

            "policy_name":
                policy_name,
        }

        row.update(
            summarize_policy(x)
        )

        quarter_rows.append(
            row
        )

    quarter_summary = pd.DataFrame(
        quarter_rows
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # OUTCOME-SPECIFIC COST
    # =========================================================================

    outcome_rows = []

    actionable = policies.loc[
        policies[
            "policy_clean_actionable"
        ]
        &
        policies[
            "hold_return_pct"
        ]
        .notna()
    ].copy()

    actionable[
        "policy_improvement_pp"
    ] = (
        actionable[
            "policy_exit_return_pct"
        ]
        -
        actionable[
            "hold_return_pct"
        ]
    )

    for (
        period,
        policy_name,
        outcome,
    ), x in actionable.groupby(
        [
            "research_period",
            "policy_name",
            "outcome",
        ],
        dropna=False,
    ):

        outcome_rows.append(
            {
                "research_period":
                    period,

                "policy_name":
                    policy_name,

                "outcome":
                    outcome,

                "total_n":
                    int(
                        len(x)
                    ),

                "avg_exit_return_pct":
                    x[
                        "policy_exit_return_pct"
                    ].mean(),

                "median_exit_return_pct":
                    x[
                        "policy_exit_return_pct"
                    ].median(),

                "avg_hold_return_pct":
                    x[
                        "hold_return_pct"
                    ].mean(),

                "avg_policy_improvement_pp":
                    x[
                        "policy_improvement_pp"
                    ].mean(),

                "policy_better_pct":
                    (
                        100.0
                        * (
                            x[
                                "policy_improvement_pp"
                            ]
                            > 0
                        ).mean()
                    ),
            }
        )

    outcome_cost = pd.DataFrame(
        outcome_rows
    )

    outcome_cost.to_csv(
        OUTCOME_COST_OUTPUT,
        index=False,
    )

    # =========================================================================
    # ACTIONABILITY BY WARNING CANDLE
    # =========================================================================

    actionability_rows = []

    triggered = policies.loc[
        policies[
            "policy_triggered"
        ]
    ].copy()

    for (
        period,
        policy_name,
        warning_candle,
    ), x in triggered.groupby(
        [
            "research_period",
            "policy_name",
            "policy_warning_candle",
        ],
        dropna=False,
    ):

        clean_n = int(
            x[
                "policy_clean_actionable"
            ].sum()
        )

        actionability_rows.append(
            {
                "research_period":
                    period,

                "policy_name":
                    policy_name,

                "warning_candle":
                    warning_candle,

                "triggered_n":
                    int(
                        len(x)
                    ),

                "clean_actionable_n":
                    clean_n,

                "clean_actionable_pct":
                    (
                        100.0
                        * clean_n
                        / len(x)
                    ),

                "avg_exit_return_pct":
                    x.loc[
                        x[
                            "policy_clean_actionable"
                        ],
                        "policy_exit_return_pct",
                    ].mean(),
            }
        )

    actionability = pd.DataFrame(
        actionability_rows
    )

    actionability.to_csv(
        ACTIONABILITY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # RECOVERY DELAY
    # =========================================================================

    recovery_subset = df.loc[
        df[
            "first_adverse_close_candle"
        ]
        .notna()
    ].copy()

    recovery_subset[
        "recovery_delay_state"
    ] = "NO_RECOVERY_THROUGH_C10"

    mask_recovered = (
        recovery_subset[
            "first_recovery_after_adverse_candle"
        ]
        .notna()
    )

    recovery_subset.loc[
        mask_recovered,
        "recovery_delay_bars",
    ] = (
        recovery_subset.loc[
            mask_recovered,
            "first_recovery_after_adverse_candle",
        ]
        -
        recovery_subset.loc[
            mask_recovered,
            "first_adverse_close_candle",
        ]
    )

    recovery_subset.loc[
        (
            mask_recovered
            &
            (
                recovery_subset[
                    "recovery_delay_bars"
                ]
                == 1
            )
        ),
        "recovery_delay_state",
    ] = "RECOVERED_IN_1_BAR"

    recovery_subset.loc[
        (
            mask_recovered
            &
            (
                recovery_subset[
                    "recovery_delay_bars"
                ]
                == 2
            )
        ),
        "recovery_delay_state",
    ] = "RECOVERED_IN_2_BARS"

    recovery_subset.loc[
        (
            mask_recovered
            &
            (
                recovery_subset[
                    "recovery_delay_bars"
                ]
                >= 3
            )
        ),
        "recovery_delay_state",
    ] = "RECOVERED_IN_3PLUS_BARS"

    recovery_rows = []

    for (
        period,
        state,
    ), x in recovery_subset.groupby(
        [
            "research_period",
            "recovery_delay_state",
        ],
        dropna=False,
    ):

        binary_n = int(
            x[
                "outcome"
            ]
            .isin(
                [
                    "FAVORABLE_FIRST",
                    "ADVERSE_FIRST",
                ]
            )
            .sum()
        )

        favorable_n = int(
            (
                x[
                    "outcome"
                ]
                == "FAVORABLE_FIRST"
            )
            .sum()
        )

        recovery_rows.append(
            {
                "research_period":
                    period,

                "recovery_delay_state":
                    state,

                "total_n":
                    int(
                        len(x)
                    ),

                "binary_n":
                    binary_n,

                "favorable_first_pct":
                    (
                        100.0
                        * favorable_n
                        / binary_n
                        if binary_n
                        else np.nan
                    ),

                "avg_final_mfe_pct":
                    x[
                        "final_mfe_pct"
                    ].mean(),

                "avg_final_mae_pct":
                    x[
                        "final_mae_pct"
                    ].mean(),

                "symbol_n":
                    x[
                        "symbol"
                    ].nunique(),
            }
        )

    recovery_summary = pd.DataFrame(
        recovery_rows
    )

    recovery_summary.to_csv(
        RECOVERY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # ETF-EXCLUSION VALIDATION CHECK
    # =========================================================================

    etf_rows = []

    validation_policies = policies.loc[
        policies[
            "research_period"
        ]
        == "VALIDATION"
    ]

    for label, subset in [
        (
            "BASE",
            validation_policies,
        ),

        (
            "EXCLUDE_SPY_QQQ_TQQQ",
            validation_policies.loc[
                ~validation_policies[
                    "symbol"
                ].isin(
                    EXCLUDE_SYMBOLS
                )
            ],
        ),
    ]:

        for (
            policy_name,
            x,
        ) in subset.groupby(
            "policy_name"
        ):

            row = {
                "research_period":
                    "VALIDATION",

                "sensitivity":
                    label,

                "policy_name":
                    policy_name,
            }

            row.update(
                summarize_policy(x)
            )

            etf_rows.append(
                row
            )

    etf_sensitivity = pd.DataFrame(
        etf_rows
    )

    # append to temporal output as a second file not necessary;
    # print directly in report.

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
        "EXIT POLICY — DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    print(
        policy_summary[
            [
                "research_period",
                "policy_name",
                "binary_signal_n",
                "actionable_n",
                "actionable_pct",
                "avg_exit_return_pct",
                "avg_hold_return_pct",
                "avg_policy_improvement_pp",
                "policy_better_pct",
                "avg_saved_on_adverse_pp",
                "avg_foregone_on_favorable_pp",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "policy_name",
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
        "VALIDATION — DIRECTIONAL"
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
                "policy_name",
                "actionable_n",
                "avg_exit_return_pct",
                "avg_hold_return_pct",
                "avg_policy_improvement_pp",
                "policy_better_pct",
            ]
        ]
        .sort_values(
            [
                "direction",
                "policy_name",
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
        "VALIDATION — OLDER VS NEWER"
    )

    print(
        "=" * 80
    )

    print(
        temporal_summary[
            [
                "validation_subperiod",
                "policy_name",
                "actionable_n",
                "avg_exit_return_pct",
                "avg_hold_return_pct",
                "avg_policy_improvement_pp",
                "policy_better_pct",
            ]
        ]
        .sort_values(
            [
                "validation_subperiod",
                "policy_name",
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
        "VALIDATION — ETF SENSITIVITY"
    )

    print(
        "=" * 80
    )

    print(
        etf_sensitivity[
            [
                "sensitivity",
                "policy_name",
                "actionable_n",
                "avg_exit_return_pct",
                "avg_hold_return_pct",
                "avg_policy_improvement_pp",
                "policy_better_pct",
            ]
        ]
        .sort_values(
            [
                "sensitivity",
                "policy_name",
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
        "OUTCOME-SPECIFIC EXIT COST"
    )

    print(
        "=" * 80
    )

    x = outcome_cost.loc[
        outcome_cost[
            "research_period"
        ]
        == "VALIDATION"
    ]

    print(
        x[
            [
                "policy_name",
                "outcome",
                "total_n",
                "avg_exit_return_pct",
                "avg_hold_return_pct",
                "avg_policy_improvement_pp",
                "policy_better_pct",
            ]
        ]
        .sort_values(
            [
                "policy_name",
                "outcome",
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
        "WARNING ACTIONABILITY BY CANDLE"
    )

    print(
        "=" * 80
    )

    x = actionability.loc[
        actionability[
            "research_period"
        ]
        == "VALIDATION"
    ]

    print(
        x[
            [
                "policy_name",
                "warning_candle",
                "triggered_n",
                "clean_actionable_n",
                "clean_actionable_pct",
                "avg_exit_return_pct",
            ]
        ]
        .sort_values(
            [
                "policy_name",
                "warning_candle",
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
        "RECOVERY DELAY — DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    print(
        recovery_summary[
            [
                "research_period",
                "recovery_delay_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "avg_final_mfe_pct",
                "avg_final_mae_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "recovery_delay_state",
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
        "QUARTER STABILITY"
    )

    print(
        "=" * 80
    )

    print(
        quarter_summary[
            [
                "quarter",
                "policy_name",
                "actionable_n",
                "avg_exit_return_pct",
                "avg_hold_return_pct",
                "avg_policy_improvement_pp",
            ]
        ]
        .sort_values(
            [
                "quarter",
                "policy_name",
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
        f"Policies:      "
        f"{POLICY_OUTPUT}"
    )

    print(
        f"Direction:     "
        f"{DIRECTION_OUTPUT}"
    )

    print(
        f"Temporal:      "
        f"{TEMPORAL_OUTPUT}"
    )

    print(
        f"Quarter:       "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Outcome cost:  "
        f"{OUTCOME_COST_OUTPUT}"
    )

    print(
        f"Actionability: "
        f"{ACTIONABILITY_OUTPUT}"
    )

    print(
        f"Recovery:      "
        f"{RECOVERY_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()