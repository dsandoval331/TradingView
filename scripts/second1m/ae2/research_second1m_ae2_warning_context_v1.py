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
    / "ae2_warning_exit_utility_v1"
    / "ae2_warning_exit_utility_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_warning_context_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_context_features_v1.parquet"
)

INVENTORY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_context_feature_inventory_v1.csv"
)

PARENT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_context_parent_states_v1.csv"
)

CONTEXT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_context_conditional_v1.csv"
)

VALIDATED_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_context_validated_candidates_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_context_direction_v1.csv"
)

TEMPORAL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_context_temporal_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_context_quarter_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_context_symbol_breadth_v1.csv"
)

CONCENTRATION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_warning_context_concentration_v1.csv"
)


MIN_DISCOVERY_BINARY_N = 75
MIN_VALIDATION_BINARY_N = 75

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
# PRE-REGISTERED CONTEXT FEATURES
#
# IMPORTANT:
#
# These are existing states from prior Alternative C2 research.
# A33.4 does NOT create new thresholds from outcome.
#
# Some branches of the research pipeline may not contain every historical
# feature. Missing optional context features are reported explicitly and
# skipped rather than fabricated.
# =============================================================================

CONTEXT_FEATURE_CANDIDATES = [
    # -------------------------------------------------------------------------
    # Market context
    # -------------------------------------------------------------------------
    "market_prior_5d_consensus",

    # -------------------------------------------------------------------------
    # Previously derived candidate architectures
    # -------------------------------------------------------------------------
    "positive_candidate_state",
    "negative_candidate_state",

    # -------------------------------------------------------------------------
    # PM / AH / Previous-Day structural levels
    # -------------------------------------------------------------------------
    "session_level_clear_state",
    "pd_level_structure_state",
    "c2_break_count_state",
    "relevant_level_cluster_state",
    "nearest_ahead_level",

    # -------------------------------------------------------------------------
    # Premarket context
    # -------------------------------------------------------------------------
    "premarket_rvol_20d_discovery_state",
    "low_premarket_rvol_candidate",
    "low_premarket_rvol_market_aligned_candidate",

    # -------------------------------------------------------------------------
    # Calendar
    # -------------------------------------------------------------------------
    "weekday",

    # -------------------------------------------------------------------------
    # Possible inherited MA states.
    # Exact historical branch names varied, so each is optional.
    # -------------------------------------------------------------------------
    "continuous_short_ma_state",
    "short_ma_state",
    "rth_short_ma_state",

    # -------------------------------------------------------------------------
    # C2 structural/exhaustion candidates if carried into this branch.
    # -------------------------------------------------------------------------
    "exhaustion_state",
    "composite_exhaustion_state",
]


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
        (
            100.0
            * favorable_n
            / binary_n
        )
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


def safe_difference(
    value: float,
    baseline: float,
) -> float:

    if (
        pd.isna(value)
        or pd.isna(baseline)
    ):
        return np.nan

    return float(
        value
        - baseline
    )


# =============================================================================
# WARNING COHORT BUILDERS
# =============================================================================

def build_warning_cohorts(
    df: pd.DataFrame,
) -> pd.DataFrame:

    # -------------------------------------------------------------------------
    # C3 adverse warning
    # -------------------------------------------------------------------------

    df[
        "warning_c3_state"
    ] = np.where(
        df[
            "first_adverse_close_candle"
        ]
        == 3,
        "C3_ADVERSE_WARNING",
        "OTHER",
    )

    # -------------------------------------------------------------------------
    # C3 + C4 both adverse.
    #
    # Equivalent to first two consecutive adverse closes being detected at C4.
    # -------------------------------------------------------------------------

    df[
        "warning_c3_c4_state"
    ] = np.where(
        df[
            "first_two_consecutive_adverse_candle"
        ]
        == 4,
        "C3_C4_ADVERSE",
        "OTHER",
    )

    # -------------------------------------------------------------------------
    # Warning followed by immediate one-bar recovery.
    # -------------------------------------------------------------------------

    recovery_delay = (
        df[
            "first_recovery_after_adverse_candle"
        ]
        -
        df[
            "first_adverse_close_candle"
        ]
    )

    df[
        "warning_fast_recovery_state"
    ] = np.where(
        (
            df[
                "first_adverse_close_candle"
            ].notna()
        )
        &
        (
            recovery_delay
            == 1
        ),
        "RECOVERED_IN_1_BAR",
        "OTHER",
    )

    # -------------------------------------------------------------------------
    # Warning not recovered on the immediately following bar.
    #
    # This is real-time observable one bar after the initial warning.
    # -------------------------------------------------------------------------

    def one_bar_nonrecovery(
        r: pd.Series,
    ) -> str:

        first_warning = r[
            "first_adverse_close_candle"
        ]

        if pd.isna(
            first_warning
        ):
            return "OTHER"

        next_candle = (
            int(first_warning)
            + 1
        )

        if next_candle > 10:
            return "OTHER"

        next_state = r[
            f"post_c{next_candle}_close_side_state"
        ]

        if (
            next_state
            != "FAVORABLE_SIDE"
        ):
            return "ONE_BAR_NONRECOVERY"

        return "OTHER"

    df[
        "warning_one_bar_nonrecovery_state"
    ] = df.apply(
        one_bar_nonrecovery,
        axis=1,
    )

    # -------------------------------------------------------------------------
    # Slow recovery: first recovery takes at least 3 bars.
    # Primarily research state, not immediate live rule.
    # -------------------------------------------------------------------------

    df[
        "warning_slow_recovery_state"
    ] = np.where(
        (
            df[
                "first_adverse_close_candle"
            ].notna()
        )
        &
        (
            recovery_delay
            >= 3
        ),
        "RECOVERED_IN_3PLUS_BARS",
        "OTHER",
    )

    # -------------------------------------------------------------------------
    # No recovery through C10.
    # Research endpoint / persistence state.
    # -------------------------------------------------------------------------

    df[
        "warning_no_recovery_state"
    ] = np.where(
        (
            df[
                "first_adverse_close_candle"
            ].notna()
        )
        &
        (
            df[
                "first_recovery_after_adverse_candle"
            ].isna()
        ),
        "NO_RECOVERY_THROUGH_C10",
        "OTHER",
    )

    return df


WARNING_SPECS = [
    (
        "warning_c3_state",
        "C3_ADVERSE_WARNING",
    ),

    (
        "warning_c3_c4_state",
        "C3_C4_ADVERSE",
    ),

    (
        "warning_fast_recovery_state",
        "RECOVERED_IN_1_BAR",
    ),

    (
        "warning_one_bar_nonrecovery_state",
        "ONE_BAR_NONRECOVERY",
    ),

    (
        "warning_slow_recovery_state",
        "RECOVERED_IN_3PLUS_BARS",
    ),

    (
        "warning_no_recovery_state",
        "NO_RECOVERY_THROUGH_C10",
    ),
]


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

        "first_adverse_close_candle",
        "first_two_consecutive_adverse_candle",
        "first_recovery_after_adverse_candle",
    ]

    for candle_number in (
        POST_BARS
    ):

        required.append(
            f"post_c{candle_number}_close_side_state"
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
        "AE2 CONDITIONAL WARNING RESCUE / "
        "STRUCTURAL CONFIRMATION V1"
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
    # FEATURE INVENTORY
    # =========================================================================

    inventory_rows = []

    available_context_features = []

    for feature in (
        CONTEXT_FEATURE_CANDIDATES
    ):

        exists = (
            feature
            in df.columns
        )

        if exists:

            available_n = int(
                df[
                    feature
                ]
                .notna()
                .sum()
            )

            unique_n = int(
                df[
                    feature
                ]
                .dropna()
                .nunique()
            )

            available_context_features.append(
                feature
            )

        else:

            available_n = 0
            unique_n = 0

        inventory_rows.append(
            {
                "feature":
                    feature,

                "available":
                    exists,

                "available_n":
                    available_n,

                "unique_state_n":
                    unique_n,
            }
        )

    inventory = pd.DataFrame(
        inventory_rows
    )

    inventory.to_csv(
        INVENTORY_OUTPUT,
        index=False,
    )

    print()

    print(
        "=" * 80
    )

    print(
        "CONTEXT FEATURE INVENTORY"
    )

    print(
        "=" * 80
    )

    print(
        inventory.to_string(
            index=False,
        )
    )

    if not available_context_features:

        raise RuntimeError(
            "None of the preregistered context "
            "features are present."
        )

    # =========================================================================
    # WARNING COHORTS
    # =========================================================================

    df = build_warning_cohorts(
        df
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
    # PARENT WARNING BASELINES
    # =========================================================================

    parent_rows = []

    parent_baseline_lookup = {}

    for (
        warning_feature,
        warning_state,
    ) in WARNING_SPECS:

        subset = df.loc[
            df[
                warning_feature
            ]
            == warning_state
        ]

        for period in [
            "DISCOVERY",
            "VALIDATION",
        ]:

            x = subset.loc[
                subset[
                    "research_period"
                ]
                == period
            ]

            if x.empty:
                continue

            stats = summarize_group(
                x
            )

            row = {
                "warning_feature":
                    warning_feature,

                "warning_state":
                    warning_state,

                "research_period":
                    period,
            }

            row.update(
                stats
            )

            parent_rows.append(
                row
            )

            parent_baseline_lookup[
                (
                    warning_feature,
                    warning_state,
                    period,
                )
            ] = stats[
                "favorable_first_pct"
            ]

    parents = pd.DataFrame(
        parent_rows
    )

    parents.to_csv(
        PARENT_OUTPUT,
        index=False,
    )

    # =========================================================================
    # CONDITIONAL CONTEXT
    #
    # For every warning cohort:
    #   warning cohort × one previously researched context state
    #
    # This remains a two-factor analysis.
    # =========================================================================

    context_rows = []

    for (
        warning_feature,
        warning_state,
    ) in WARNING_SPECS:

        warning_population = df.loc[
            df[
                warning_feature
            ]
            == warning_state
        ]

        if warning_population.empty:
            continue

        for context_feature in (
            available_context_features
        ):

            for (
                period,
                context_state,
            ), x in warning_population.groupby(
                [
                    "research_period",
                    context_feature,
                ],
                dropna=False,
            ):

                if x.empty:
                    continue

                stats = summarize_group(
                    x
                )

                baseline = (
                    parent_baseline_lookup.get(
                        (
                            warning_feature,
                            warning_state,
                            period,
                        ),
                        np.nan,
                    )
                )

                row = {
                    "warning_feature":
                        warning_feature,

                    "warning_state":
                        warning_state,

                    "context_feature":
                        context_feature,

                    "context_state":
                        context_state,

                    "research_period":
                        period,

                    "parent_favorable_first_pct":
                        baseline,

                    "context_effect_pp":
                        safe_difference(
                            stats[
                                "favorable_first_pct"
                            ],
                            baseline,
                        ),
                }

                row.update(
                    stats
                )

                context_rows.append(
                    row
                )

    context_summary = pd.DataFrame(
        context_rows
    )

    context_summary.to_csv(
        CONTEXT_OUTPUT,
        index=False,
    )

    # =========================================================================
    # DISCOVERY -> VALIDATION PAIRING
    #
    # No state is selected because it has the "best" validation result.
    #
    # We simply pair every same warning/context state across both periods and
    # apply minimum sample-size gates.
    # =========================================================================

    discovery_rows = context_summary.loc[
        context_summary[
            "research_period"
        ]
        == "DISCOVERY"
    ].copy()

    validation_rows = context_summary.loc[
        context_summary[
            "research_period"
        ]
        == "VALIDATION"
    ].copy()

    pair_keys = [
        "warning_feature",
        "warning_state",
        "context_feature",
        "context_state",
    ]

    paired = discovery_rows.merge(
        validation_rows,
        on=pair_keys,
        how="inner",
        suffixes=(
            "_discovery",
            "_validation",
        ),
    )

    paired[
        "passes_sample_gate"
    ] = (
        (
            paired[
                "binary_n_discovery"
            ]
            >= MIN_DISCOVERY_BINARY_N
        )
        &
        (
            paired[
                "binary_n_validation"
            ]
            >= MIN_VALIDATION_BINARY_N
        )
    )

    paired[
        "same_effect_direction"
    ] = (
        np.sign(
            paired[
                "context_effect_pp_discovery"
            ]
        )
        ==
        np.sign(
            paired[
                "context_effect_pp_validation"
            ]
        )
    )

    paired[
        "effect_difference_pp"
    ] = (
        paired[
            "context_effect_pp_validation"
        ]
        -
        paired[
            "context_effect_pp_discovery"
        ]
    )

    paired[
        "effect_type"
    ] = np.where(
        (
            paired[
                "context_effect_pp_discovery"
            ]
            > 0
        )
        &
        (
            paired[
                "context_effect_pp_validation"
            ]
            > 0
        ),
        "RESCUE_CONTEXT",
        np.where(
            (
                paired[
                    "context_effect_pp_discovery"
                ]
                < 0
            )
            &
            (
                paired[
                    "context_effect_pp_validation"
                ]
                < 0
            ),
            "ESCALATION_CONTEXT",
            "NON_REPLICATING",
        ),
    )

    paired.to_csv(
        VALIDATED_OUTPUT,
        index=False,
    )

    # =========================================================================
    # DIRECTIONAL ROBUSTNESS
    #
    # Only sample-gated replicating states advance into this table.
    # =========================================================================

    qualified = paired.loc[
        (
            paired[
                "passes_sample_gate"
            ]
        )
        &
        (
            paired[
                "same_effect_direction"
            ]
        )
        &
        (
            paired[
                "effect_type"
            ]
            != "NON_REPLICATING"
        )
    ].copy()

    direction_rows = []

    for _, candidate in (
        qualified.iterrows()
    ):

        warning_feature = candidate[
            "warning_feature"
        ]

        warning_state = candidate[
            "warning_state"
        ]

        context_feature = candidate[
            "context_feature"
        ]

        context_state = candidate[
            "context_state"
        ]

        candidate_population = df.loc[
            (
                df[
                    warning_feature
                ]
                == warning_state
            )
            &
            (
                df[
                    context_feature
                ]
                == context_state
            )
        ]

        for (
            period,
            direction,
        ), x in candidate_population.groupby(
            [
                "research_period",
                "direction",
            ],
            dropna=False,
        ):

            stats = summarize_group(
                x
            )

            direction_rows.append(
                {
                    "warning_feature":
                        warning_feature,

                    "warning_state":
                        warning_state,

                    "context_feature":
                        context_feature,

                    "context_state":
                        context_state,

                    "effect_type":
                        candidate[
                            "effect_type"
                        ],

                    "research_period":
                        period,

                    "direction":
                        direction,

                    **stats,
                }
            )

    direction_summary = pd.DataFrame(
        direction_rows
    )

    direction_summary.to_csv(
        DIRECTION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # TEMPORAL ROBUSTNESS
    # =========================================================================

    temporal_rows = []

    for _, candidate in (
        qualified.iterrows()
    ):

        warning_feature = candidate[
            "warning_feature"
        ]

        warning_state = candidate[
            "warning_state"
        ]

        context_feature = candidate[
            "context_feature"
        ]

        context_state = candidate[
            "context_state"
        ]

        candidate_population = df.loc[
            (
                df[
                    warning_feature
                ]
                == warning_state
            )
            &
            (
                df[
                    context_feature
                ]
                == context_state
            )
            &
            (
                df[
                    "research_period"
                ]
                == "VALIDATION"
            )
        ]

        for subperiod in [
            "VALIDATION_OLDER",
            "VALIDATION_NEWER",
        ]:

            x = candidate_population.loc[
                candidate_population[
                    "validation_subperiod"
                ]
                == subperiod
            ]

            if x.empty:
                continue

            stats = summarize_group(
                x
            )

            temporal_rows.append(
                {
                    "warning_feature":
                        warning_feature,

                    "warning_state":
                        warning_state,

                    "context_feature":
                        context_feature,

                    "context_state":
                        context_state,

                    "effect_type":
                        candidate[
                            "effect_type"
                        ],

                    "validation_subperiod":
                        subperiod,

                    **stats,
                }
            )

    temporal_summary = pd.DataFrame(
        temporal_rows
    )

    temporal_summary.to_csv(
        TEMPORAL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # QUARTER STABILITY
    # =========================================================================

    quarter_rows = []

    for _, candidate in (
        qualified.iterrows()
    ):

        warning_feature = candidate[
            "warning_feature"
        ]

        warning_state = candidate[
            "warning_state"
        ]

        context_feature = candidate[
            "context_feature"
        ]

        context_state = candidate[
            "context_state"
        ]

        candidate_population = df.loc[
            (
                df[
                    warning_feature
                ]
                == warning_state
            )
            &
            (
                df[
                    context_feature
                ]
                == context_state
            )
        ]

        for quarter, x in (
            candidate_population.groupby(
                "quarter",
                dropna=False,
            )
        ):

            stats = summarize_group(
                x
            )

            quarter_rows.append(
                {
                    "warning_feature":
                        warning_feature,

                    "warning_state":
                        warning_state,

                    "context_feature":
                        context_feature,

                    "context_state":
                        context_state,

                    "effect_type":
                        candidate[
                            "effect_type"
                        ],

                    "quarter":
                        quarter,

                    **stats,
                }
            )

    quarter_summary = pd.DataFrame(
        quarter_rows
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SYMBOL BREADTH / CONCENTRATION
    # =========================================================================

    symbol_rows = []
    concentration_rows = []

    for _, candidate in (
        qualified.iterrows()
    ):

        warning_feature = candidate[
            "warning_feature"
        ]

        warning_state = candidate[
            "warning_state"
        ]

        context_feature = candidate[
            "context_feature"
        ]

        context_state = candidate[
            "context_state"
        ]

        candidate_population = df.loc[
            (
                df[
                    warning_feature
                ]
                == warning_state
            )
            &
            (
                df[
                    context_feature
                ]
                == context_state
            )
            &
            (
                df[
                    "research_period"
                ]
                == "VALIDATION"
            )
        ]

        if candidate_population.empty:
            continue

        # ---------------------------------------------------------------------
        # Per-symbol
        # ---------------------------------------------------------------------

        for symbol, x in (
            candidate_population.groupby(
                "symbol"
            )
        ):

            stats = summarize_group(
                x
            )

            symbol_rows.append(
                {
                    "warning_feature":
                        warning_feature,

                    "warning_state":
                        warning_state,

                    "context_feature":
                        context_feature,

                    "context_state":
                        context_state,

                    "effect_type":
                        candidate[
                            "effect_type"
                        ],

                    "symbol":
                        symbol,

                    **stats,
                }
            )

        # ---------------------------------------------------------------------
        # Concentration
        # ---------------------------------------------------------------------

        counts = (
            candidate_population[
                "symbol"
            ]
            .value_counts()
            .sort_values(
                ascending=False
            )
        )

        total_n = int(
            len(
                candidate_population
            )
        )

        top1_n = int(
            counts.head(1).sum()
        )

        top5_n = int(
            counts.head(5).sum()
        )

        top10_n = int(
            counts.head(10).sum()
        )

        concentration_rows.append(
            {
                "warning_feature":
                    warning_feature,

                "warning_state":
                    warning_state,

                "context_feature":
                    context_feature,

                "context_state":
                    context_state,

                "effect_type":
                    candidate[
                        "effect_type"
                    ],

                "total_n":
                    total_n,

                "symbol_n":
                    candidate_population[
                        "symbol"
                    ].nunique(),

                "top1_n":
                    top1_n,

                "top1_share_pct":
                    (
                        100.0
                        * top1_n
                        / total_n
                    ),

                "top5_n":
                    top5_n,

                "top5_share_pct":
                    (
                        100.0
                        * top5_n
                        / total_n
                    ),

                "top10_n":
                    top10_n,

                "top10_share_pct":
                    (
                        100.0
                        * top10_n
                        / total_n
                    ),
            }
        )

    symbol_summary = pd.DataFrame(
        symbol_rows
    )

    symbol_summary.to_csv(
        SYMBOL_OUTPUT,
        index=False,
    )

    concentration = pd.DataFrame(
        concentration_rows
    )

    concentration.to_csv(
        CONCENTRATION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # ETF EXCLUSION CHECK
    #
    # Add simple validation-only sensitivity fields to qualified candidates.
    # =========================================================================

    etf_rows = []

    for _, candidate in (
        qualified.iterrows()
    ):

        warning_feature = candidate[
            "warning_feature"
        ]

        warning_state = candidate[
            "warning_state"
        ]

        context_feature = candidate[
            "context_feature"
        ]

        context_state = candidate[
            "context_state"
        ]

        base = df.loc[
            (
                df[
                    warning_feature
                ]
                == warning_state
            )
            &
            (
                df[
                    context_feature
                ]
                == context_state
            )
            &
            (
                df[
                    "research_period"
                ]
                == "VALIDATION"
            )
        ]

        for label, x in [
            (
                "BASE",
                base,
            ),
            (
                "EXCLUDE_SPY_QQQ_TQQQ",
                base.loc[
                    ~base[
                        "symbol"
                    ].isin(
                        EXCLUDE_SYMBOLS
                    )
                ],
            ),
        ]:

            if x.empty:
                continue

            stats = summarize_group(
                x
            )

            etf_rows.append(
                {
                    "warning_feature":
                        warning_feature,

                    "warning_state":
                        warning_state,

                    "context_feature":
                        context_feature,

                    "context_state":
                        context_state,

                    "effect_type":
                        candidate[
                            "effect_type"
                        ],

                    "sensitivity":
                        label,

                    **stats,
                }
            )

    etf_summary = pd.DataFrame(
        etf_rows
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
        "PARENT WARNING COHORTS"
    )

    print(
        "=" * 80
    )

    print(
        parents[
            [
                "warning_state",
                "research_period",
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
                "warning_state",
                "research_period",
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
        "DISCOVERY -> VALIDATION CONTEXT PAIRS"
    )

    print(
        "=" * 80
    )

    display_pairs = paired.loc[
        paired[
            "passes_sample_gate"
        ]
    ].copy()

    display_pairs = display_pairs.sort_values(
        [
            "warning_state",
            "context_feature",
            "context_effect_pp_validation",
        ],
        ascending=[
            True,
            True,
            False,
        ],
    )

    print(
        display_pairs[
            [
                "warning_state",
                "context_feature",
                "context_state",
                "binary_n_discovery",
                "favorable_first_pct_discovery",
                "context_effect_pp_discovery",
                "binary_n_validation",
                "favorable_first_pct_validation",
                "context_effect_pp_validation",
                "same_effect_direction",
                "effect_type",
            ]
        ]
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
        "QUALIFIED REPLICATING WARNING CONTEXTS"
    )

    print(
        "=" * 80
    )

    if qualified.empty:

        print(
            "No context states passed both the "
            "sample and replication gates."
        )

    else:

        print(
            qualified[
                [
                    "warning_state",
                    "context_feature",
                    "context_state",
                    "binary_n_discovery",
                    "favorable_first_pct_discovery",
                    "context_effect_pp_discovery",
                    "binary_n_validation",
                    "favorable_first_pct_validation",
                    "context_effect_pp_validation",
                    "effect_type",
                ]
            ]
            .sort_values(
                [
                    "effect_type",
                    "context_effect_pp_validation",
                ],
                ascending=[
                    True,
                    False,
                ],
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
        "QUALIFIED CONTEXTS — VALIDATION DIRECTION"
    )

    print(
        "=" * 80
    )

    if direction_summary.empty:

        print(
            "No qualified directional rows."
        )

    else:

        print(
            direction_summary[
                [
                    "warning_state",
                    "context_feature",
                    "context_state",
                    "effect_type",
                    "direction",
                    "binary_n",
                    "favorable_first_pct",
                    "symbol_n",
                ]
            ]
            .loc[
                direction_summary[
                    "research_period"
                ]
                == "VALIDATION"
            ]
            .sort_values(
                [
                    "warning_state",
                    "context_feature",
                    "context_state",
                    "direction",
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
        "QUALIFIED CONTEXTS — "
        "OLDER VS NEWER VALIDATION"
    )

    print(
        "=" * 80
    )

    if temporal_summary.empty:

        print(
            "No qualified temporal rows."
        )

    else:

        print(
            temporal_summary[
                [
                    "warning_state",
                    "context_feature",
                    "context_state",
                    "effect_type",
                    "validation_subperiod",
                    "binary_n",
                    "favorable_first_pct",
                    "symbol_n",
                ]
            ]
            .sort_values(
                [
                    "warning_state",
                    "context_feature",
                    "context_state",
                    "validation_subperiod",
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
        "QUALIFIED CONTEXTS — ETF SENSITIVITY"
    )

    print(
        "=" * 80
    )

    if etf_summary.empty:

        print(
            "No qualified ETF-sensitivity rows."
        )

    else:

        print(
            etf_summary[
                [
                    "warning_state",
                    "context_feature",
                    "context_state",
                    "effect_type",
                    "sensitivity",
                    "binary_n",
                    "favorable_first_pct",
                    "symbol_n",
                ]
            ]
            .sort_values(
                [
                    "warning_state",
                    "context_feature",
                    "context_state",
                    "sensitivity",
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
        f"Features:       "
        f"{FEATURE_OUTPUT}"
    )

    print(
        f"Inventory:      "
        f"{INVENTORY_OUTPUT}"
    )

    print(
        f"Parents:        "
        f"{PARENT_OUTPUT}"
    )

    print(
        f"Conditional:    "
        f"{CONTEXT_OUTPUT}"
    )

    print(
        f"Validated:      "
        f"{VALIDATED_OUTPUT}"
    )

    print(
        f"Direction:      "
        f"{DIRECTION_OUTPUT}"
    )

    print(
        f"Temporal:       "
        f"{TEMPORAL_OUTPUT}"
    )

    print(
        f"Quarter:        "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Symbols:        "
        f"{SYMBOL_OUTPUT}"
    )

    print(
        f"Concentration:  "
        f"{CONCENTRATION_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()