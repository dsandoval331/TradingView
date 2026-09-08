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
    / "ae2_opening_volume_v1"
    / "ae2_opening_volume_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_volume_robustness_v1"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_volume_robustness_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_volume_robustness_direction_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_volume_robustness_quarter_v1.csv"
)

SENSITIVITY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_volume_robustness_sensitivity_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_volume_robustness_symbol_v1.csv"
)

OUTLIER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_volume_robustness_outlier_v1.csv"
)

INTERACTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_volume_robustness_interactions_v1.csv"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_volume_robustness_features_v1.parquet"
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

def build_low_c2_rvol_market_opposition_state(
    r: pd.Series,
) -> str:

    if (
        r["c2_rvol_20d_discovery_state"]
        == "LOW"
        and
        r["market_prior_5d_consensus"]
        == "CONSENSUS_OPPOSING"
    ):
        return "LOW_C2_RVOL_MARKET_OPPOSING"

    return "OTHER"


def build_positive_candidate_participation_state(
    r: pd.Series,
) -> str:

    positive = (
        r["positive_candidate_state"]
        == "POSITIVE_CANDIDATE"
    )

    if not positive:
        return "NOT_POSITIVE_CANDIDATE"

    participation = r[
        "opening_participation_state"
    ]

    if participation == "BOTH_ABOVE_BASELINE":
        return "POSITIVE_BOTH_ABOVE"

    if participation == "BOTH_BELOW_BASELINE":
        return "POSITIVE_BOTH_BELOW"

    if participation == "MIXED":
        return "POSITIVE_MIXED"

    return "POSITIVE_UNKNOWN"


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

        "c2_vs_c1_volume_ratio",
        "c2_vs_c1_volume_state",

        "c2_rvol_20d",
        "c2_rvol_20d_discovery_state",

        "opening_participation_state",

        "market_prior_5d_consensus",
        "positive_candidate_state",
        "negative_candidate_state",
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
        "AE2 VOLUME STRUCTURE ROBUSTNESS V1"
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
    # DERIVED PRIMARY STATES
    # =========================================================================

    df[
        "low_c2_rvol_market_opposition_state"
    ] = df.apply(
        build_low_c2_rvol_market_opposition_state,
        axis=1,
    )

    df[
        "positive_candidate_participation_state"
    ] = df.apply(
        build_positive_candidate_participation_state,
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
    # OUTLIER-ROBUST C2/C1 VOLUME RATIO
    #
    # The raw ratio can become huge when C1 volume is tiny.
    # Freeze trimming from DISCOVERY only.
    # =========================================================================

    discovery_ratio = (
        df.loc[
            df[
                "research_period"
            ]
            == "DISCOVERY",
            "c2_vs_c1_volume_ratio",
        ]
        .dropna()
        .astype(float)
    )

    ratio_q01 = (
        discovery_ratio
        .quantile(
            0.01
        )
    )

    ratio_q99 = (
        discovery_ratio
        .quantile(
            0.99
        )
    )

    df[
        "c2_vs_c1_volume_ratio_winsor"
    ] = (
        df[
            "c2_vs_c1_volume_ratio"
        ]
        .clip(
            lower=ratio_q01,
            upper=ratio_q99,
        )
    )

    # =========================================================================
    # PRIMARY SUMMARY
    # =========================================================================

    primary_features = [
        "c2_vs_c1_volume_state",
        "low_c2_rvol_market_opposition_state",
        "positive_candidate_participation_state",
    ]

    summary_frames = []

    for feature in primary_features:

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

    for feature in primary_features:

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

    for feature in primary_features:

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

        target_specs = [
            (
                "c2_vs_c1_volume_state",
                "C2_VOLUME_ACCELERATING",
            ),
            (
                "c2_vs_c1_volume_state",
                "C2_VOLUME_DECELERATING",
            ),
            (
                "low_c2_rvol_market_opposition_state",
                "LOW_C2_RVOL_MARKET_OPPOSING",
            ),
            (
                "positive_candidate_participation_state",
                "POSITIVE_BOTH_ABOVE",
            ),
            (
                "positive_candidate_participation_state",
                "POSITIVE_BOTH_BELOW",
            ),
            (
                "positive_candidate_participation_state",
                "POSITIVE_MIXED",
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
                ) in target_specs:

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

    symbol_specs = [
        (
            "c2_vs_c1_volume_state",
            "C2_VOLUME_ACCELERATING",
        ),
        (
            "low_c2_rvol_market_opposition_state",
            "LOW_C2_RVOL_MARKET_OPPOSING",
        ),
    ]

    for (
        feature,
        target_state,
    ) in symbol_specs:

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
    # OUTLIER-ROBUST RATIO ANALYSIS
    # =========================================================================

    outlier_rows = []

    for period, x in df.groupby(
        "research_period",
        dropna=False,
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

        outlier_rows.append(
            {
                "research_period":
                    period,

                "discovery_q01":
                    ratio_q01,

                "discovery_q99":
                    ratio_q99,

                "winner_raw_mean":
                    winners[
                        "c2_vs_c1_volume_ratio"
                    ].mean(),

                "loser_raw_mean":
                    losers[
                        "c2_vs_c1_volume_ratio"
                    ].mean(),

                "raw_difference":
                    (
                        winners[
                            "c2_vs_c1_volume_ratio"
                        ].mean()
                        -
                        losers[
                            "c2_vs_c1_volume_ratio"
                        ].mean()
                    ),

                "winner_winsor_mean":
                    winners[
                        "c2_vs_c1_volume_ratio_winsor"
                    ].mean(),

                "loser_winsor_mean":
                    losers[
                        "c2_vs_c1_volume_ratio_winsor"
                    ].mean(),

                "winsor_difference":
                    (
                        winners[
                            "c2_vs_c1_volume_ratio_winsor"
                        ].mean()
                        -
                        losers[
                            "c2_vs_c1_volume_ratio_winsor"
                        ].mean()
                    ),

                "winner_median":
                    winners[
                        "c2_vs_c1_volume_ratio"
                    ].median(),

                "loser_median":
                    losers[
                        "c2_vs_c1_volume_ratio"
                    ].median(),

                "median_difference":
                    (
                        winners[
                            "c2_vs_c1_volume_ratio"
                        ].median()
                        -
                        losers[
                            "c2_vs_c1_volume_ratio"
                        ].median()
                    ),
            }
        )

    outlier_summary = pd.DataFrame(
        outlier_rows
    )

    outlier_summary.to_csv(
        OUTLIER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # INTERACTIONS
    # =========================================================================

    interaction_specs = [
        (
            "c2_vs_c1_volume_state",
            "market_prior_5d_consensus",
        ),
        (
            "c2_vs_c1_volume_state",
            "positive_candidate_state",
        ),
        (
            "c2_vs_c1_volume_state",
            "negative_candidate_state",
        ),
        (
            "c2_vs_c1_volume_state",
            "aligned_exhaustion_state",
        ),
        (
            "low_c2_rvol_market_opposition_state",
            "direction",
        ),
    ]

    interaction_frames = []

    for (
        volume_feature,
        context_feature,
    ) in interaction_specs:

        x = summarize(
            df,
            [
                "research_period",
                volume_feature,
                context_feature,
            ],
        )

        x[
            "volume_feature"
        ] = volume_feature

        x[
            "context_feature"
        ] = context_feature

        x = x.rename(
            columns={
                volume_feature:
                    "volume_state",

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

    print(
        "=" * 80
    )

    print(
        "C2 VOLUME ACCELERATION — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    x = summary.loc[
        summary[
            "feature"
        ]
        == "c2_vs_c1_volume_state"
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
        "LOW C2 RVOL + MARKET OPPOSITION — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    x = summary.loc[
        summary[
            "feature"
        ]
        == "low_c2_rvol_market_opposition_state"
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
        "POSITIVE REVERSAL CANDIDATE × "
        "PARTICIPATION"
    )

    print(
        "=" * 80
    )

    x = summary.loc[
        summary[
            "feature"
        ]
        == "positive_candidate_participation_state"
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
        "C2/C1 VOLUME RATIO — "
        "OUTLIER ROBUSTNESS"
    )

    print(
        "=" * 80
    )

    print(
        outlier_summary.to_string(
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
        "VOLUME × CONTEXT — VALIDATION"
    )

    print(
        "=" * 80
    )

    x = interactions.loc[
        interactions[
            "research_period"
        ]
        == "VALIDATION"
    ]

    print(
        x[
            [
                "volume_feature",
                "context_feature",
                "volume_state",
                "context_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "volume_feature",
                "context_feature",
                "volume_state",
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
        f"Summary:      "
        f"{SUMMARY_OUTPUT}"
    )

    print(
        f"Direction:    "
        f"{DIRECTION_OUTPUT}"
    )

    print(
        f"Quarter:      "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Sensitivity:  "
        f"{SENSITIVITY_OUTPUT}"
    )

    print(
        f"Symbols:      "
        f"{SYMBOL_OUTPUT}"
    )

    print(
        f"Outlier:      "
        f"{OUTLIER_OUTPUT}"
    )

    print(
        f"Interactions: "
        f"{INTERACTION_OUTPUT}"
    )

    print(
        f"Features:     "
        f"{FEATURE_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()