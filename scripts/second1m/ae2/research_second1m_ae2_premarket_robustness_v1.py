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
    / "ae2_premarket_context_v1"
    / "ae2_premarket_context_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_premarket_robustness_v1"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_robustness_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_robustness_direction_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_robustness_quarter_v1.csv"
)

SENSITIVITY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_robustness_sensitivity_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_robustness_symbol_v1.csv"
)

CONCENTRATION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_robustness_concentration_v1.csv"
)

CONTINUOUS_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_robustness_continuous_v1.csv"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_robustness_features_v1.parquet"
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
# CANDIDATE BUILDERS
# =============================================================================

def low_premarket_rvol_state(
    r: pd.Series,
) -> str:

    if (
        r[
            "premarket_rvol_20d_discovery_state"
        ]
        == "LOW"
    ):
        return "LOW_PREMARKET_RVOL"

    return "OTHER"


def low_premarket_rvol_market_aligned_state(
    r: pd.Series,
) -> str:

    if (
        r[
            "premarket_rvol_20d_discovery_state"
        ]
        == "LOW"
        and
        r[
            "market_prior_5d_consensus"
        ]
        == "CONSENSUS_ALIGNED"
    ):
        return "LOW_PREMARKET_RVOL_MARKET_ALIGNED"

    return "OTHER"


def high_premarket_rvol_state(
    r: pd.Series,
) -> str:

    if (
        r[
            "premarket_rvol_20d_discovery_state"
        ]
        == "HIGH"
    ):
        return "HIGH_PREMARKET_RVOL"

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

        "premarket_rvol_20d",
        "premarket_rvol_20d_discovery_state",

        "market_prior_5d_consensus",

        "directional_rth_open_gap_pct",
        "directional_premarket_gap_from_prior_close_pct",
        "directional_premarket_return_pct",
        "directional_premarket_close_vs_prior_close_pct",
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
        "AE2 PREMARKET CONTEXT ROBUSTNESS V1"
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
        "low_premarket_rvol_candidate"
    ] = df.apply(
        low_premarket_rvol_state,
        axis=1,
    )

    df[
        "low_premarket_rvol_market_aligned_candidate"
    ] = df.apply(
        low_premarket_rvol_market_aligned_state,
        axis=1,
    )

    df[
        "high_premarket_rvol_candidate"
    ] = df.apply(
        high_premarket_rvol_state,
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
    # PRIMARY SUMMARY
    # =========================================================================

    candidate_specs = [
        (
            "low_premarket_rvol_candidate",
            "LOW_PREMARKET_RVOL",
        ),
        (
            "low_premarket_rvol_market_aligned_candidate",
            "LOW_PREMARKET_RVOL_MARKET_ALIGNED",
        ),
        (
            "high_premarket_rvol_candidate",
            "HIGH_PREMARKET_RVOL",
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

    concentration = pd.DataFrame(
        concentration_rows
    )

    concentration.to_csv(
        CONCENTRATION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # OUTLIER-ROBUST CONTINUOUS ANALYSIS
    #
    # Thresholds are frozen from DISCOVERY only.
    # =========================================================================

    continuous_features = [
        "directional_rth_open_gap_pct",
        "directional_premarket_gap_from_prior_close_pct",
        "directional_premarket_return_pct",
        "directional_premarket_close_vs_prior_close_pct",
    ]

    winsor_limits = {}

    for feature in (
        continuous_features
    ):

        discovery_values = (
            df.loc[
                df[
                    "research_period"
                ]
                == "DISCOVERY",
                feature,
            ]
            .dropna()
            .astype(float)
        )

        if discovery_values.empty:

            raise RuntimeError(
                f"No discovery values for "
                f"{feature}"
            )

        q01 = (
            discovery_values
            .quantile(
                0.01
            )
        )

        q99 = (
            discovery_values
            .quantile(
                0.99
            )
        )

        winsor_limits[
            feature
        ] = (
            q01,
            q99,
        )

        df[
            feature
            + "_winsor"
        ] = (
            df[
                feature
            ]
            .clip(
                lower=q01,
                upper=q99,
            )
        )

    continuous_rows = []

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

    for feature in (
        continuous_features
    ):

        q01, q99 = winsor_limits[
            feature
        ]

        winsor_col = (
            feature
            + "_winsor"
        )

        for (
            period_col,
            period_value,
        ) in period_specs:

            x = df.loc[
                df[
                    period_col
                ]
                == period_value
            ]

            if x.empty:
                continue

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

            row = {
                "feature":
                    feature,

                "period_type":
                    period_col,

                "period":
                    period_value,

                "discovery_q01":
                    q01,

                "discovery_q99":
                    q99,

                "total_n":
                    int(
                        len(x)
                    ),

                "winner_raw_mean":
                    winners[
                        feature
                    ].mean(),

                "loser_raw_mean":
                    losers[
                        feature
                    ].mean(),

                "raw_difference":
                    (
                        winners[
                            feature
                        ].mean()
                        -
                        losers[
                            feature
                        ].mean()
                    ),

                "winner_winsor_mean":
                    winners[
                        winsor_col
                    ].mean(),

                "loser_winsor_mean":
                    losers[
                        winsor_col
                    ].mean(),

                "winsor_difference":
                    (
                        winners[
                            winsor_col
                        ].mean()
                        -
                        losers[
                            winsor_col
                        ].mean()
                    ),

                "winner_median":
                    winners[
                        feature
                    ].median(),

                "loser_median":
                    losers[
                        feature
                    ].median(),

                "median_difference":
                    (
                        winners[
                            feature
                        ].median()
                        -
                        losers[
                            feature
                        ].median()
                    ),
            }

            continuous_rows.append(
                row
            )

    continuous = pd.DataFrame(
        continuous_rows
    )

    continuous.to_csv(
        CONTINUOUS_OUTPUT,
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
        "PRIMARY PREMARKET CANDIDATES — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

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

    print(
        "=" * 80
    )

    print(
        "QUARTER STABILITY"
    )

    print(
        "=" * 80
    )

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
        "SYMBOL CONCENTRATION"
    )

    print(
        "=" * 80
    )

    print(
        concentration.to_string(
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
        "CONTINUOUS PREMARKET METRICS — "
        "OUTLIER ROBUSTNESS"
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
        f"Concentration: "
        f"{CONCENTRATION_OUTPUT}"
    )

    print(
        f"Continuous:    "
        f"{CONTINUOUS_OUTPUT}"
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