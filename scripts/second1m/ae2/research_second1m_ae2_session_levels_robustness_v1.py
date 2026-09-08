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
    / "ae2_session_levels_v1"
    / "ae2_session_level_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_session_levels_robustness_v1"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_levels_robustness_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_levels_robustness_direction_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_levels_robustness_quarter_v1.csv"
)

SENSITIVITY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_levels_robustness_sensitivity_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_levels_robustness_symbol_v1.csv"
)

CONCENTRATION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_levels_robustness_concentration_v1.csv"
)

INTERACTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_levels_robustness_interactions_v1.csv"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_levels_robustness_features_v1.parquet"
)

EXCLUDE_SYMBOLS = {
    "SPY",
    "QQQ",
    "TQQQ",
}


# =============================================================================
# HELPERS
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


# =============================================================================
# CANDIDATE BUILDERS
# =============================================================================

def pd_failed_break_state(
    r: pd.Series,
) -> str:

    if (
        r["pd_level_structure_state"]
        == "FAILED_BREAK"
    ):
        return "PD_FAILED_BREAK"

    return "OTHER"


def multiple_c2_break_state(
    r: pd.Series,
) -> str:

    if (
        r["c2_break_count_state"]
        == "MULTIPLE_C2_LEVEL_BREAKS"
    ):
        return "MULTIPLE_C2_BREAKS"

    return "OTHER"


def all3_market_opposing_state(
    r: pd.Series,
) -> str:

    if (
        r["session_level_clear_state"]
        == "ALL_3_CLEARED"
        and
        r["market_prior_5d_consensus"]
        == "CONSENSUS_OPPOSING"
    ):
        return "ALL3_CLEARED_MARKET_OPPOSING"

    return "OTHER"


def all3_positive_reversal_state(
    r: pd.Series,
) -> str:

    if (
        r["session_level_clear_state"]
        == "ALL_3_CLEARED"
        and
        r["positive_candidate_state"]
        == "POSITIVE_CANDIDATE"
    ):
        return "ALL3_CLEARED_POSITIVE_REVERSAL"

    return "OTHER"


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

    df[
        "trade_date"
    ] = pd.to_datetime(
        df[
            "trade_date"
        ]
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

    required = [
        "outcome",
        "c3_confirmed",
        "final_mfe_pct",
        "final_mae_pct",
        "symbol",
        "direction",
        "trade_date",
        "research_period",

        "pd_level_structure_state",
        "c2_break_count_state",
        "session_level_clear_state",

        "market_prior_5d_consensus",
        "positive_candidate_state",
        "negative_candidate_state",

        "pm_level_structure_state",
        "ah_level_structure_state",
        "relevant_level_cluster_state",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing required columns: "
            + ", ".join(missing)
        )

    print("=" * 80)
    print("AE2 SESSION LEVEL ROBUSTNESS V1")
    print("=" * 80)

    print(
        f"AE2 events: "
        f"{len(df):,}"
    )

    print(
        f"Symbols:    "
        f"{df['symbol'].nunique():,}"
    )

    # =========================================================================
    # DERIVE PRIMARY CANDIDATES
    # =========================================================================

    df[
        "pd_failed_break_candidate"
    ] = df.apply(
        pd_failed_break_state,
        axis=1,
    )

    df[
        "multiple_c2_break_candidate"
    ] = df.apply(
        multiple_c2_break_state,
        axis=1,
    )

    df[
        "all3_market_opposing_candidate"
    ] = df.apply(
        all3_market_opposing_state,
        axis=1,
    )

    df[
        "all3_positive_reversal_candidate"
    ] = df.apply(
        all3_positive_reversal_state,
        axis=1,
    )

    # =========================================================================
    # TIME SPLITS
    # =========================================================================

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
            len(validation_dates) // 2
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
    # PRIMARY SUMMARY
    # =========================================================================

    candidate_specs = [
        (
            "pd_failed_break_candidate",
            "PD_FAILED_BREAK",
        ),
        (
            "multiple_c2_break_candidate",
            "MULTIPLE_C2_BREAKS",
        ),
        (
            "all3_market_opposing_candidate",
            "ALL3_CLEARED_MARKET_OPPOSING",
        ),
        (
            "all3_positive_reversal_candidate",
            "ALL3_CLEARED_POSITIVE_REVERSAL",
        ),
    ]

    summary_frames = []

    for feature, _ in candidate_specs:

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

        summary_frames.append(
            x
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
    # DIRECTION
    # =========================================================================

    direction_frames = []

    for feature, _ in candidate_specs:

        x = summarize(
            df,
            [
                "research_period",
                "direction",
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

        direction_frames.append(
            x
        )

    direction_summary = pd.concat(
        direction_frames,
        ignore_index=True,
        sort=False,
    )

    direction_summary.to_csv(
        DIRECTION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # QUARTER
    # =========================================================================

    quarter_frames = []

    for feature, _ in candidate_specs:

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
    # SENSITIVITY
    # =========================================================================

    sensitivity_rows = []

    def add_sensitivity(
        label: str,
        subset: pd.DataFrame,
    ):

        period_specs = [
            (
                "research_period",
                [
                    "DISCOVERY",
                    "VALIDATION",
                ],
            ),
            (
                "validation_subperiod",
                [
                    "VALIDATION_OLDER",
                    "VALIDATION_NEWER",
                ],
            ),
        ]

        for (
            period_col,
            period_values,
        ) in period_specs:

            for period_value in period_values:

                x = subset.loc[
                    subset[
                        period_col
                    ]
                    == period_value
                ]

                if x.empty:
                    continue

                for (
                    feature,
                    target_state,
                ) in candidate_specs:

                    y = x.loc[
                        x[
                            feature
                        ]
                        == target_state
                    ]

                    if y.empty:
                        continue

                    row = {
                        "sensitivity":
                            label,

                        "period_type":
                            period_col,

                        "period":
                            period_value,

                        "feature":
                            feature,

                        "state":
                            target_state,
                    }

                    row.update(
                        summarize_group(y)
                    )

                    sensitivity_rows.append(
                        row
                    )

    add_sensitivity(
        "BASE",
        df,
    )

    add_sensitivity(
        "EXCLUDE_SPY_QQQ_TQQQ",
        df.loc[
            ~df[
                "symbol"
            ].isin(
                EXCLUDE_SYMBOLS
            )
        ],
    )

    sensitivity = pd.DataFrame(
        sensitivity_rows
    )

    sensitivity.to_csv(
        SENSITIVITY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SYMBOL BREADTH
    # =========================================================================

    symbol_frames = []

    for (
        feature,
        target_state,
    ) in candidate_specs:

        subset = df.loc[
            df[
                feature
            ]
            == target_state
        ].copy()

        if subset.empty:
            continue

        x = summarize(
            subset,
            [
                "symbol",
            ],
        )

        x[
            "feature"
        ] = feature

        x[
            "state"
        ] = target_state

        symbol_frames.append(
            x
        )

    if symbol_frames:

        symbol_summary = pd.concat(
            symbol_frames,
            ignore_index=True,
            sort=False,
        )

    else:

        symbol_summary = pd.DataFrame()

    symbol_summary.to_csv(
        SYMBOL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # CONCENTRATION
    # =========================================================================

    concentration_rows = []

    for (
        feature,
        target_state,
    ) in candidate_specs:

        subset = df.loc[
            df[
                feature
            ]
            == target_state
        ]

        if subset.empty:
            continue

        counts = (
            subset[
                "symbol"
            ]
            .value_counts()
            .sort_values(
                ascending=False
            )
        )

        total_n = int(
            len(subset)
        )

        top1 = int(
            counts.head(1).sum()
        )

        top5 = int(
            counts.head(5).sum()
        )

        top10 = int(
            counts.head(10).sum()
        )

        concentration_rows.append(
            {
                "feature":
                    feature,

                "state":
                    target_state,

                "total_n":
                    total_n,

                "symbol_n":
                    int(
                        subset[
                            "symbol"
                        ].nunique()
                    ),

                "top1_n":
                    top1,

                "top1_share_pct":
                    (
                        100.0
                        * top1
                        / total_n
                    ),

                "top5_n":
                    top5,

                "top5_share_pct":
                    (
                        100.0
                        * top5
                        / total_n
                    ),

                "top10_n":
                    top10,

                "top10_share_pct":
                    (
                        100.0
                        * top10
                        / total_n
                    ),
            }
        )

    concentration = pd.DataFrame(
        concentration_rows
    )

    concentration.to_csv(
        CONCENTRATION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # INTERACTIONS
    # =========================================================================

    interaction_specs = [
        (
            "pd_failed_break_candidate",
            "market_prior_5d_consensus",
        ),
        (
            "pd_failed_break_candidate",
            "positive_candidate_state",
        ),
        (
            "multiple_c2_break_candidate",
            "market_prior_5d_consensus",
        ),
        (
            "multiple_c2_break_candidate",
            "positive_candidate_state",
        ),
        (
            "all3_market_opposing_candidate",
            "direction",
        ),
        (
            "all3_positive_reversal_candidate",
            "direction",
        ),
        (
            "all3_positive_reversal_candidate",
            "relevant_level_cluster_state",
        ),
    ]

    interaction_frames = []

    for (
        candidate_feature,
        context_feature,
    ) in interaction_specs:

        x = summarize(
            df,
            [
                "research_period",
                candidate_feature,
                context_feature,
            ],
        )

        x[
            "candidate_feature"
        ] = candidate_feature

        x[
            "context_feature"
        ] = context_feature

        x = x.rename(
            columns={
                candidate_feature:
                    "candidate_state",

                context_feature:
                    "context_state",
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
    print("PRIMARY SESSION-LEVEL CANDIDATES — DISCOVERY VS VALIDATION")
    print("=" * 80)

    x = summary.loc[
        summary[
            "state"
        ]
        != "OTHER"
    ]

    print(
        x[
            [
                "feature",
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
                "feature",
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
    print("=" * 80)
    print("VALIDATION DIRECTIONAL")
    print("=" * 80)

    x = direction_summary.loc[
        (
            direction_summary[
                "research_period"
            ]
            == "VALIDATION"
        )
        &
        (
            direction_summary[
                "state"
            ]
            != "OTHER"
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
    print("QUARTER STABILITY")
    print("=" * 80)

    x = quarter_summary.loc[
        quarter_summary[
            "state"
        ]
        != "OTHER"
    ]

    print(
        x[
            [
                "feature",
                "quarter",
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
                "quarter",
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
    print("VALIDATION SUBPERIOD / SENSITIVITY")
    print("=" * 80)

    print(
        sensitivity[
            [
                "sensitivity",
                "period",
                "feature",
                "state",
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
                "feature",
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
    print("SYMBOL CONCENTRATION")
    print("=" * 80)

    print(
        concentration.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("SESSION-LEVEL CANDIDATE × CONTEXT — VALIDATION")
    print("=" * 80)

    x = interactions.loc[
        (
            interactions[
                "research_period"
            ]
            == "VALIDATION"
        )
        &
        (
            interactions[
                "candidate_state"
            ]
            != "OTHER"
        )
    ]

    print(
        x[
            [
                "candidate_feature",
                "context_feature",
                "candidate_state",
                "context_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "candidate_feature",
                "context_feature",
                "context_state",
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
    print("SYMBOL BREADTH — TOP 20")
    print("=" * 80)

    if not symbol_summary.empty:

        display_symbols = (
            symbol_summary
            .sort_values(
                [
                    "feature",
                    "total_n",
                ],
                ascending=[
                    True,
                    False,
                ],
            )
            .groupby(
                "feature",
                group_keys=False,
            )
            .head(20)
        )

        print(
            display_symbols[
                [
                    "feature",
                    "state",
                    "symbol",
                    "total_n",
                    "binary_n",
                    "favorable_first_pct",
                    "c3_confirmation_pct",
                ]
            ]
            .to_string(
                index=False,
                float_format=
                    lambda z:
                        f"{z:.2f}",
            )
        )

    else:

        print(
            "No symbol rows produced."
        )

    print()

    print(
        f"Validation midpoint: "
        f"{validation_midpoint.date()}"
    )

    print()
    print("=" * 80)
    print("OUTPUTS")
    print("=" * 80)

    print(
        f"Summary:       "
        f"{SUMMARY_OUTPUT}"
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
        f"Symbols:       "
        f"{SYMBOL_OUTPUT}"
    )

    print(
        f"Concentration: "
        f"{CONCENTRATION_OUTPUT}"
    )

    print(
        f"Interactions:  "
        f"{INTERACTION_OUTPUT}"
    )

    print(
        f"Features:      "
        f"{FEATURE_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()