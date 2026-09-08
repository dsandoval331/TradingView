from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# PATHS
# =============================================================================

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

INPUT_PATH = (
    RESEARCH_ROOT
    / "ae2_c2_predictors_v1"
    / "ae2_c2_predictor_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_robustness_v1"
)

THRESHOLD_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_discovery_thresholds_v1.csv"
)

STATE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_structural_states_v1.parquet"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_structural_state_summary_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_structural_state_quarter_v1.csv"
)

COMPOSITE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_composite_exhaustion_v1.csv"
)


# =============================================================================
# FEATURE CONTRACT
# =============================================================================

FEATURES = [
    "c2_favorable_vwap_distance_pct",
    "c2_favorable_body_return_pct",
    "c1_to_c2_close_progress_pct",
    "c2_favorable_clv_pct",
]

FEATURE_LABELS = {
    "c2_favorable_vwap_distance_pct":
        "C2_VWAP_DISTANCE",

    "c2_favorable_body_return_pct":
        "C2_BODY_RETURN",

    "c1_to_c2_close_progress_pct":
        "C1_TO_C2_PROGRESS",

    "c2_favorable_clv_pct":
        "C2_FAVORABLE_CLV",
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

    ff_pct = (
        100.0
        * favorable_n
        / binary_n
        if binary_n
        else np.nan
    )

    confirmed_n = int(
        x["c3_confirmed"].sum()
    )

    confirmation_pct = (
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
            ff_pct,

        "c3_confirmed_n":
            confirmed_n,

        "c3_confirmation_pct":
            confirmation_pct,

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


def structural_state(
    value: float,
    q20: float,
    q80: float,
) -> str:

    if pd.isna(value):
        return "UNKNOWN"

    if value < q20:
        return "LOW"

    if value >= q80:
        return "EXTREME"

    return "MODERATE"


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:

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

    required = [
        "symbol",
        "trade_date",
        "direction",
        "outcome",
        "c3_confirmed",
        "final_mfe_pct",
        "final_mae_pct",
        "temporal_half",
        *FEATURES,
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

    # =========================================================================
    # DISCOVERY / VALIDATION POPULATIONS
    # =========================================================================

    discovery = df.loc[
        df[
            "temporal_half"
        ]
        == "OLDEST_HALF"
    ].copy()

    validation = df.loc[
        df[
            "temporal_half"
        ]
        == "NEWEST_HALF"
    ].copy()

    if discovery.empty:
        raise RuntimeError(
            "Discovery population is empty."
        )

    if validation.empty:
        raise RuntimeError(
            "Validation population is empty."
        )

    # =========================================================================
    # FREEZE Q20 / Q80 FROM DISCOVERY ONLY
    # =========================================================================

    threshold_rows = []

    thresholds = {}

    for feature in FEATURES:

        q20 = float(
            discovery[
                feature
            ].quantile(
                0.20
            )
        )

        q80 = float(
            discovery[
                feature
            ].quantile(
                0.80
            )
        )

        thresholds[
            feature
        ] = {
            "q20":
                q20,

            "q80":
                q80,
        }

        threshold_rows.append(
            {
                "feature":
                    feature,

                "feature_label":
                    FEATURE_LABELS[
                        feature
                    ],

                "discovery_q20":
                    q20,

                "discovery_q80":
                    q80,

                "discovery_n":
                    int(
                        discovery[
                            feature
                        ].notna().sum()
                    ),
            }
        )

    thresholds_df = pd.DataFrame(
        threshold_rows
    )

    thresholds_df.to_csv(
        THRESHOLD_OUTPUT,
        index=False,
    )

    # =========================================================================
    # APPLY FROZEN STATES TO ALL DATA
    # =========================================================================

    for feature in FEATURES:

        label = FEATURE_LABELS[
            feature
        ]

        q20 = thresholds[
            feature
        ][
            "q20"
        ]

        q80 = thresholds[
            feature
        ][
            "q80"
        ]

        state_col = (
            f"{label}__STATE"
        )

        extreme_col = (
            f"{label}__EXTREME"
        )

        df[
            state_col
        ] = df[
            feature
        ].apply(
            lambda value:
                structural_state(
                    value,
                    q20,
                    q80,
                )
        )

        df[
            extreme_col
        ] = (
            df[
                state_col
            ]
            == "EXTREME"
        )

    # =========================================================================
    # COMPOSITE EXHAUSTION SCORE
    #
    # Count how many of the four independently frozen "extreme" conditions
    # are present at C2.
    # =========================================================================

    extreme_cols = [
        f"{FEATURE_LABELS[f]}__EXTREME"
        for f in FEATURES
    ]

    df[
        "exhaustion_extreme_count"
    ] = (
        df[
            extreme_cols
        ]
        .astype(int)
        .sum(axis=1)
    )

    def exhaustion_state(
        count: int,
    ) -> str:

        if count == 0:
            return "NONE"

        if count == 1:
            return "ONE"

        return "MULTIPLE"

    df[
        "exhaustion_state"
    ] = df[
        "exhaustion_extreme_count"
    ].apply(
        exhaustion_state
    )

    # =========================================================================
    # PERIOD LABEL
    # =========================================================================

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
        .to_period("Q")
        .astype(str)
    )

    # =========================================================================
    # SINGLE-FEATURE STRUCTURAL STATES
    # =========================================================================

    state_frames = []

    for feature in FEATURES:

        label = FEATURE_LABELS[
            feature
        ]

        state_col = (
            f"{label}__STATE"
        )

        # All directions combined.
        all_direction = summarize(
            df,
            [
                "research_period",
                state_col,
            ],
        )

        all_direction[
            "direction"
        ] = "ALL"

        all_direction[
            "feature"
        ] = feature

        all_direction[
            "feature_label"
        ] = label

        all_direction = (
            all_direction.rename(
                columns={
                    state_col:
                        "state"
                }
            )
        )

        # Direction split.
        by_direction = summarize(
            df,
            [
                "research_period",
                "direction",
                state_col,
            ],
        )

        by_direction[
            "feature"
        ] = feature

        by_direction[
            "feature_label"
        ] = label

        by_direction = (
            by_direction.rename(
                columns={
                    state_col:
                        "state"
                }
            )
        )

        state_frames.extend(
            [
                all_direction,
                by_direction,
            ]
        )

    state_summary = pd.concat(
        state_frames,
        ignore_index=True,
        sort=False,
    )

    state_summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # QUARTER STABILITY
    # =========================================================================

    quarter_frames = []

    for feature in FEATURES:

        label = FEATURE_LABELS[
            feature
        ]

        state_col = (
            f"{label}__STATE"
        )

        q_all = summarize(
            df,
            [
                "quarter",
                state_col,
            ],
        )

        q_all[
            "direction"
        ] = "ALL"

        q_all[
            "feature"
        ] = feature

        q_all[
            "feature_label"
        ] = label

        q_all = q_all.rename(
            columns={
                state_col:
                    "state"
            }
        )

        q_direction = summarize(
            df,
            [
                "quarter",
                "direction",
                state_col,
            ],
        )

        q_direction[
            "feature"
        ] = feature

        q_direction[
            "feature_label"
        ] = label

        q_direction = (
            q_direction.rename(
                columns={
                    state_col:
                        "state"
                }
            )
        )

        quarter_frames.extend(
            [
                q_all,
                q_direction,
            ]
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
    # COMPOSITE EXHAUSTION
    # =========================================================================

    composite_all = summarize(
        df,
        [
            "research_period",
            "exhaustion_state",
        ],
    )

    composite_all[
        "direction"
    ] = "ALL"

    composite_direction = summarize(
        df,
        [
            "research_period",
            "direction",
            "exhaustion_state",
        ],
    )

    composite_summary = pd.concat(
        [
            composite_all,
            composite_direction,
        ],
        ignore_index=True,
        sort=False,
    )

    composite_summary.to_csv(
        COMPOSITE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # PARQUET EXPORT
    # =========================================================================

    df.to_parquet(
        STATE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # REPORT
    # =========================================================================

    print(
        "=" * 80
    )

    print(
        "AE2 C2 EXHAUSTION / "
        "MODERATE-STRENGTH ROBUSTNESS V1"
    )

    print(
        "=" * 80
    )

    print(
        f"AE2 events:       "
        f"{len(df):,}"
    )

    print(
        f"Discovery events: "
        f"{len(discovery):,}"
    )

    print(
        f"Validation events:"
        f" {len(validation):,}"
    )

    print()

    print(
        "=" * 80
    )

    print(
        "DISCOVERY-FROZEN THRESHOLDS"
    )

    print(
        "=" * 80
    )

    print(
        thresholds_df[
            [
                "feature_label",
                "discovery_q20",
                "discovery_q80",
                "discovery_n",
            ]
        ].to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.4f}",
        )
    )

    # =========================================================================
    # PRINT SINGLE FEATURE RESULTS
    # =========================================================================

    for feature in FEATURES:

        label = FEATURE_LABELS[
            feature
        ]

        x = state_summary.loc[
            (
                state_summary[
                    "feature"
                ]
                == feature
            )
            &
            (
                state_summary[
                    "direction"
                ]
                == "ALL"
            )
        ].copy()

        print()

        print(
            "=" * 80
        )

        print(
            f"{label} — "
            f"DISCOVERY VS VALIDATION"
        )

        print(
            "=" * 80
        )

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
            ].to_string(
                index=False,
                float_format=
                    lambda z:
                        f"{z:.2f}",
            )
        )

    # =========================================================================
    # PRINT COMPOSITE
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "COMPOSITE EXHAUSTION — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    composite_display = (
        composite_summary.loc[
            composite_summary[
                "direction"
            ]
            == "ALL"
        ]
    )

    print(
        composite_display[
            [
                "research_period",
                "exhaustion_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
            ]
        ].to_string(
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
        "COMPOSITE EXHAUSTION — "
        "DIRECTIONAL VALIDATION ONLY"
    )

    print(
        "=" * 80
    )

    validation_direction = (
        composite_summary.loc[
            (
                composite_summary[
                    "research_period"
                ]
                == "VALIDATION"
            )
            &
            (
                composite_summary[
                    "direction"
                ]
                != "ALL"
            )
        ]
    )

    print(
        validation_direction[
            [
                "direction",
                "exhaustion_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ].to_string(
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
        "OUTPUTS"
    )

    print(
        "=" * 80
    )

    print(
        f"Thresholds: "
        f"{THRESHOLD_OUTPUT}"
    )

    print(
        f"States:     "
        f"{STATE_OUTPUT}"
    )

    print(
        f"Summary:    "
        f"{SUMMARY_OUTPUT}"
    )

    print(
        f"Quarter:    "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Composite:  "
        f"{COMPOSITE_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()