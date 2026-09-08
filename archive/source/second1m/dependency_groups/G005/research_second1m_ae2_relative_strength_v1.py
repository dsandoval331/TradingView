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
    / "ae2_three_index_regime_v1"
    / "ae2_three_index_regime_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_relative_strength_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_relative_strength_features_v1.parquet"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_relative_strength_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_relative_strength_direction_v1.csv"
)

CONTINUOUS_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_relative_strength_continuous_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_relative_strength_quarter_v1.csv"
)

INTERACTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_relative_strength_interactions_v1.csv"
)

COVERAGE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_relative_strength_coverage_v1.csv"
)


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


def directional_value(
    direction: str,
    value: float,
) -> float:

    if pd.isna(value):
        return np.nan

    if direction == "BULL":
        return float(value)

    if direction == "BEAR":
        return -float(value)

    return np.nan


def relative_state(
    value: float,
) -> str:

    if pd.isna(value):
        return "UNKNOWN"

    if value > 0:
        return "RELATIVE_ALIGNED"

    if value < 0:
        return "RELATIVE_OPPOSING"

    return "FLAT"


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

    df["trade_date"] = (
        pd.to_datetime(
            df["trade_date"]
        )
        .dt
        .normalize()
    )

    df["symbol"] = (
        df["symbol"]
        .astype(str)
        .str.upper()
    )

    print(
        "=" * 80
    )

    print(
        "AE2 STOCK RELATIVE STRENGTH "
        "VS SPY / QQQ V1"
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
    # REQUIRED INPUT CONTRACT
    # =========================================================================

    required_cols = [
        # Stock daily
        "prior_ret_1d_pct",
        "prior_ret_5d_pct",
        "prior_ret_10d_pct",

        # Stock weekly
        "weekly_ret_1w_pct",
        "weekly_ret_4w_pct",

        # SPY
        "spy_daily_ret_1d_pct",
        "spy_daily_ret_5d_pct",
        "spy_daily_ret_10d_pct",
        "spy_weekly_ret_1w_pct",
        "spy_weekly_ret_4w_pct",

        # QQQ
        "qqq_daily_ret_1d_pct",
        "qqq_daily_ret_5d_pct",
        "qqq_daily_ret_10d_pct",
        "qqq_weekly_ret_1w_pct",
        "qqq_weekly_ret_4w_pct",

        # Existing research states
        "market_prior_5d_consensus",
        "market_daily_regime_state",
        "aligned_exhaustion_state",
        "trend_5d_binary_state",
        "weekly_trend_state",
        "research_period",
    ]

    missing = [
        col
        for col in required_cols
        if col not in df.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing required columns: "
            + ", ".join(
                missing
            )
        )

    # =========================================================================
    # RAW RELATIVE PERFORMANCE
    #
    # Positive means stock outperformed benchmark in absolute return terms.
    #
    # Example:
    # stock +3%, SPY +1% -> +2%
    # stock -1%, SPY -4% -> +3%
    # =========================================================================

    horizons = {
        "1d": (
            "prior_ret_1d_pct",
            "spy_daily_ret_1d_pct",
            "qqq_daily_ret_1d_pct",
        ),

        "5d": (
            "prior_ret_5d_pct",
            "spy_daily_ret_5d_pct",
            "qqq_daily_ret_5d_pct",
        ),

        "10d": (
            "prior_ret_10d_pct",
            "spy_daily_ret_10d_pct",
            "qqq_daily_ret_10d_pct",
        ),

        "1w": (
            "weekly_ret_1w_pct",
            "spy_weekly_ret_1w_pct",
            "qqq_weekly_ret_1w_pct",
        ),

        "4w": (
            "weekly_ret_4w_pct",
            "spy_weekly_ret_4w_pct",
            "qqq_weekly_ret_4w_pct",
        ),
    }

    created_relative_features = []

    for horizon, (
        stock_col,
        spy_col,
        qqq_col,
    ) in horizons.items():

        spy_rel_col = (
            f"stock_vs_spy_{horizon}_pct"
        )

        qqq_rel_col = (
            f"stock_vs_qqq_{horizon}_pct"
        )

        avg_rel_col = (
            f"stock_vs_market_avg_"
            f"{horizon}_pct"
        )

        df[
            spy_rel_col
        ] = (
            df[
                stock_col
            ]
            -
            df[
                spy_col
            ]
        )

        df[
            qqq_rel_col
        ] = (
            df[
                stock_col
            ]
            -
            df[
                qqq_col
            ]
        )

        df[
            avg_rel_col
        ] = (
            df[
                stock_col
            ]
            -
            (
                (
                    df[
                        spy_col
                    ]
                    +
                    df[
                        qqq_col
                    ]
                )
                / 2.0
            )
        )

        # ---------------------------------------------------------------------
        # Direction normalize.
        #
        # BULL:
        #   positive relative performance = aligned
        #
        # BEAR:
        #   negative raw relative performance = aligned
        #
        # So after normalization, positive always means the stock has behaved
        # relatively in the proposed AE2 trade direction.
        # ---------------------------------------------------------------------

        for raw_col in [
            spy_rel_col,
            qqq_rel_col,
            avg_rel_col,
        ]:

            directional_col = (
                f"directional_{raw_col}"
            )

            df[
                directional_col
            ] = df.apply(
                lambda r:
                    directional_value(
                        r[
                            "direction"
                        ],
                        r[
                            raw_col
                        ],
                    ),
                axis=1,
            )

            state_col = (
                directional_col
                + "__state"
            )

            df[
                state_col
            ] = df[
                directional_col
            ].apply(
                relative_state
            )

            created_relative_features.append(
                directional_col
            )

    # =========================================================================
    # SPY + QQQ RELATIVE CONSENSUS
    #
    # Does relative behavior agree versus BOTH benchmarks?
    # =========================================================================

    consensus_features = []

    for horizon in horizons:

        spy_state = (
            f"directional_"
            f"stock_vs_spy_"
            f"{horizon}_pct__state"
        )

        qqq_state = (
            f"directional_"
            f"stock_vs_qqq_"
            f"{horizon}_pct__state"
        )

        output_col = (
            f"relative_consensus_"
            f"{horizon}"
        )

        def classify_consensus(
            r,
            spy_col=spy_state,
            qqq_col=qqq_state,
        ):

            a = r[
                spy_col
            ]

            b = r[
                qqq_col
            ]

            if (
                a == "UNKNOWN"
                or b == "UNKNOWN"
            ):
                return "UNKNOWN"

            if (
                a == "RELATIVE_ALIGNED"
                and
                b == "RELATIVE_ALIGNED"
            ):
                return "BOTH_RELATIVE_ALIGNED"

            if (
                a == "RELATIVE_OPPOSING"
                and
                b == "RELATIVE_OPPOSING"
            ):
                return "BOTH_RELATIVE_OPPOSING"

            return "MIXED"

        df[
            output_col
        ] = df.apply(
            classify_consensus,
            axis=1,
        )

        consensus_features.append(
            output_col
        )

    # =========================================================================
    # MULTI-HORIZON RELATIVE STRENGTH
    #
    # Uses the averaged SPY/QQQ relative measure across:
    #
    # 1D, 5D, 10D, 1W, 4W
    #
    # This is NOT weighted or outcome-optimized.
    # =========================================================================

    avg_directional_cols = [
        f"directional_"
        f"stock_vs_market_avg_"
        f"{h}_pct"
        for h in horizons
    ]

    def relative_horizon_score(
        r,
    ):

        values = [
            r[col]
            for col in (
                avg_directional_cols
            )
        ]

        available = [
            x
            for x in values
            if not pd.isna(x)
        ]

        if len(
            available
        ) < 3:

            return np.nan

        return sum(
            1 if x > 0
            else -1 if x < 0
            else 0
            for x in available
        )

    df[
        "relative_multi_horizon_score"
    ] = df.apply(
        relative_horizon_score,
        axis=1,
    )

    def multi_horizon_state(
        score,
    ):

        if pd.isna(score):
            return "UNKNOWN"

        if score >= 3:
            return "RELATIVE_ALIGNED"

        if score <= -3:
            return "RELATIVE_OPPOSING"

        return "MIXED"

    df[
        "relative_multi_horizon_state"
    ] = df[
        "relative_multi_horizon_score"
    ].apply(
        multi_horizon_state
    )

    # =========================================================================
    # PERIOD / QUARTER
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

    # =========================================================================
    # COVERAGE
    # =========================================================================

    coverage_rows = []

    coverage_features = [
        *created_relative_features,
        *consensus_features,
        "relative_multi_horizon_score",
        "relative_multi_horizon_state",
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
    # STATE SUMMARY
    # =========================================================================

    summary_frames = []

    # Individual continuous relative features converted to binary states.
    for feature in (
        created_relative_features
    ):

        state_col = (
            feature
            + "__state"
        )

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

    # Consensus states.
    for feature in (
        consensus_features
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

    # Multi-horizon relative state.
    multi_all = summarize(
        df,
        [
            "research_period",
            "relative_multi_horizon_state",
        ],
    )

    multi_all[
        "direction"
    ] = "ALL"

    multi_all[
        "feature"
    ] = (
        "RELATIVE_MULTI_HORIZON"
    )

    multi_all = (
        multi_all.rename(
            columns={
                "relative_multi_horizon_state":
                    "state"
            }
        )
    )

    multi_dir = summarize(
        df,
        [
            "research_period",
            "direction",
            "relative_multi_horizon_state",
        ],
    )

    multi_dir[
        "feature"
    ] = (
        "RELATIVE_MULTI_HORIZON"
    )

    multi_dir = (
        multi_dir.rename(
            columns={
                "relative_multi_horizon_state":
                    "state"
            }
        )
    )

    summary_frames.extend(
        [
            multi_all,
            multi_dir,
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
    # CONTINUOUS WINNER / LOSER ANALYSIS
    # =========================================================================

    continuous_rows = []

    for feature in (
        created_relative_features
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
    # QUARTER STABILITY — PRIMARY 5D RELATIVE CONSENSUS
    # =========================================================================

    quarter_summary = summarize(
        df,
        [
            "quarter",
            "relative_consensus_5d",
        ],
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # INTERACTIONS
    #
    # Primary relative-strength state = 5D SPY+QQQ consensus.
    # =========================================================================

    interaction_specs = [
        (
            "relative_consensus_5d",
            "market_prior_5d_consensus",
        ),
        (
            "relative_consensus_5d",
            "aligned_exhaustion_state",
        ),
        (
            "relative_consensus_5d",
            "trend_5d_binary_state",
        ),
        (
            "relative_multi_horizon_state",
            "market_daily_regime_state",
        ),
    ]

    interaction_frames = []

    for (
        relative_feature,
        context_feature,
    ) in interaction_specs:

        x = summarize(
            df,
            [
                "research_period",
                relative_feature,
                context_feature,
            ],
        )

        x[
            "relative_feature"
        ] = (
            relative_feature
        )

        x[
            "context_feature"
        ] = (
            context_feature
        )

        x = x.rename(
            columns={
                relative_feature:
                    "relative_state",

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
        "RELATIVE STRENGTH COVERAGE"
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

    # =========================================================================
    # 5D SPY / QQQ / AVG
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "5D RELATIVE PERFORMANCE — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    primary_features = [
        "directional_stock_vs_spy_5d_pct",
        "directional_stock_vs_qqq_5d_pct",
        "directional_stock_vs_market_avg_5d_pct",
        "relative_consensus_5d",
    ]

    x = summary.loc[
        (
            summary[
                "feature"
            ].isin(
                primary_features
            )
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

    # =========================================================================
    # MULTI-HORIZON
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "MULTI-HORIZON RELATIVE STATE — "
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
            == "RELATIVE_MULTI_HORIZON"
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

    # =========================================================================
    # VALIDATION DIRECTIONAL
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "5D RELATIVE CONSENSUS — "
        "VALIDATION DIRECTIONAL"
    )

    print(
        "=" * 80
    )

    x = direction_summary.loc[
        (
            direction_summary[
                "feature"
            ]
            == "relative_consensus_5d"
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

    # =========================================================================
    # QUARTER
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "5D RELATIVE CONSENSUS — "
        "QUARTER STABILITY"
    )

    print(
        "=" * 80
    )

    print(
        quarter_summary[
            [
                "quarter",
                "relative_consensus_5d",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "quarter",
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

    # =========================================================================
    # CONTINUOUS
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "CONTINUOUS RELATIVE METRICS"
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

    # =========================================================================
    # INTERACTIONS
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "RELATIVE STRENGTH × CONTEXT — "
        "VALIDATION"
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
                "relative_feature",
                "context_feature",
                "relative_state",
                "context_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "relative_feature",
                "context_feature",
                "relative_state",
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
        f"Direction:    "
        f"{DIRECTION_OUTPUT}"
    )

    print(
        f"Continuous:   "
        f"{CONTINUOUS_OUTPUT}"
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
        f"Coverage:     "
        f"{COVERAGE_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()