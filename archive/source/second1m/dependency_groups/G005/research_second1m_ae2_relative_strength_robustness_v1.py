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
    / "ae2_relative_strength_v1"
    / "ae2_relative_strength_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_relative_strength_robustness_v1"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "relative_strength_robustness_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "relative_strength_robustness_direction_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "relative_strength_robustness_quarter_v1.csv"
)

SENSITIVITY_OUTPUT = (
    OUTPUT_ROOT
    / "relative_strength_robustness_sensitivity_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "relative_strength_robustness_symbol_v1.csv"
)

DECOMPOSITION_OUTPUT = (
    OUTPUT_ROOT
    / "relative_strength_robustness_decomposition_v1.csv"
)

EXHAUSTION_OUTPUT = (
    OUTPUT_ROOT
    / "relative_strength_robustness_exhaustion_v1.csv"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "relative_strength_robustness_features_v1.parquet"
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

    confirmed_n = int(
        x["c3_confirmed"].sum()
    )

    c3_confirmation_pct = (
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
# PRIMARY STATE BUILDERS
# =============================================================================

def positive_candidate_state(
    r: pd.Series,
) -> str:

    market = r[
        "market_prior_5d_consensus"
    ]

    relative = r[
        "relative_consensus_5d"
    ]

    if (
        market
        == "CONSENSUS_OPPOSING"
        and
        relative
        == "BOTH_RELATIVE_OPPOSING"
    ):
        return "POSITIVE_CANDIDATE"

    return "OTHER"


def negative_candidate_state(
    r: pd.Series,
) -> str:

    stock = r[
        "trend_5d_binary_state"
    ]

    relative = r[
        "relative_consensus_5d"
    ]

    if (
        stock
        == "ALIGNED"
        and
        relative
        == "BOTH_RELATIVE_OPPOSING"
    ):
        return "NEGATIVE_CANDIDATE"

    return "OTHER"


def combined_candidate_state(
    r: pd.Series,
) -> str:

    positive = (
        r[
            "positive_candidate_state"
        ]
        == "POSITIVE_CANDIDATE"
    )

    negative = (
        r[
            "negative_candidate_state"
        ]
        == "NEGATIVE_CANDIDATE"
    )

    if positive and negative:
        return "BOTH_POSITIVE_AND_NEGATIVE"

    if positive:
        return "POSITIVE_ONLY"

    if negative:
        return "NEGATIVE_ONLY"

    return "NEITHER"


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
        "market_prior_5d_consensus",
        "market_daily_regime_state",
        "relative_consensus_5d",
        "relative_multi_horizon_state",
        "trend_5d_binary_state",
        "aligned_exhaustion_state",
    ]

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

    print(
        "=" * 80
    )

    print(
        "AE2 RELATIVE STRENGTH "
        "INTERACTION ROBUSTNESS V1"
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
    # PRIMARY STATES
    # =========================================================================

    df[
        "positive_candidate_state"
    ] = df.apply(
        positive_candidate_state,
        axis=1,
    )

    df[
        "negative_candidate_state"
    ] = df.apply(
        negative_candidate_state,
        axis=1,
    )

    df[
        "combined_candidate_state"
    ] = df.apply(
        combined_candidate_state,
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
    # PRIMARY DISCOVERY / VALIDATION
    # =========================================================================

    summary_frames = []

    for feature in [
        "positive_candidate_state",
        "negative_candidate_state",
        "combined_candidate_state",
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

    for feature in [
        "positive_candidate_state",
        "negative_candidate_state",
    ]:

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

    for feature in [
        "positive_candidate_state",
        "negative_candidate_state",
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
    # VALIDATION SUBPERIOD / SENSITIVITY
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

                for feature, target_state in [
                    (
                        "positive_candidate_state",
                        "POSITIVE_CANDIDATE",
                    ),
                    (
                        "negative_candidate_state",
                        "NEGATIVE_CANDIDATE",
                    ),
                ]:

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

    for feature, target_state in [
        (
            "positive_candidate_state",
            "POSITIVE_CANDIDATE",
        ),
        (
            "negative_candidate_state",
            "NEGATIVE_CANDIDATE",
        ),
    ]:

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
    # EXHAUSTION INTERACTION
    # =========================================================================

    exhaustion_frames = []

    for feature in [
        "positive_candidate_state",
        "negative_candidate_state",
    ]:

        x = summarize(
            df,
            [
                "research_period",
                feature,
                "aligned_exhaustion_state",
            ],
        )

        x[
            "feature"
        ] = feature

        x = x.rename(
            columns={
                feature:
                    "candidate_state"
            }
        )

        exhaustion_frames.append(
            x
        )

    exhaustion = pd.concat(
        exhaustion_frames,
        ignore_index=True,
        sort=False,
    )

    exhaustion.to_csv(
        EXHAUSTION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # DECOMPOSITION
    #
    # This is the critical redundancy check.
    #
    # We explicitly cross:
    #
    #   stock 5D state
    #   market 5D consensus
    #   relative 5D consensus
    #
    # No thresholds, no weights.
    # =========================================================================

    decomposition = summarize(
        df,
        [
            "research_period",
            "trend_5d_binary_state",
            "market_prior_5d_consensus",
            "relative_consensus_5d",
        ],
    )

    decomposition.to_csv(
        DECOMPOSITION_OUTPUT,
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
        "PRIMARY CANDIDATES — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    print(
        summary[
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
        "PRIMARY CANDIDATES — "
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
        "PRIMARY CANDIDATES — "
        "QUARTER STABILITY"
    )

    print(
        "=" * 80
    )

    print(
        quarter_summary[
            [
                "feature",
                "quarter",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
            ]
        ]
        .sort_values(
            [
                "feature",
                "quarter",
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
        "VALIDATION SUBPERIOD / "
        "SENSITIVITY"
    )

    print(
        "=" * 80
    )

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

    print(
        "=" * 80
    )

    print(
        "CANDIDATE × EXHAUSTION — "
        "VALIDATION"
    )

    print(
        "=" * 80
    )

    x = exhaustion.loc[
        exhaustion[
            "research_period"
        ]
        == "VALIDATION"
    ]

    print(
        x[
            [
                "feature",
                "candidate_state",
                "aligned_exhaustion_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "feature",
                "candidate_state",
                "aligned_exhaustion_state",
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
        "STOCK × MARKET × RELATIVE "
        "DECOMPOSITION — VALIDATION"
    )

    print(
        "=" * 80
    )

    x = decomposition.loc[
        decomposition[
            "research_period"
        ]
        == "VALIDATION"
    ]

    print(
        x[
            [
                "trend_5d_binary_state",
                "market_prior_5d_consensus",
                "relative_consensus_5d",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "market_prior_5d_consensus",
                "trend_5d_binary_state",
                "relative_consensus_5d",
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
        "SYMBOL BREADTH — TOP 20"
    )

    print(
        "=" * 80
    )

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
        f"Decomposition: "
        f"{DECOMPOSITION_OUTPUT}"
    )

    print(
        f"Exhaustion:    "
        f"{EXHAUSTION_OUTPUT}"
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