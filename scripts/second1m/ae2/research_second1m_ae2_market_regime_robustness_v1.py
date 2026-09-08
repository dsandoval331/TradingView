from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# CONFIG
# =============================================================================

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

INPUT_PATH = (
    RESEARCH_ROOT
    / "ae2_market_regime_v1"
    / "ae2_market_regime_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_market_regime_robustness_v1"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "market_regime_robustness_summary_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "market_regime_robustness_quarter_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "market_regime_robustness_direction_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "market_regime_robustness_symbol_v1.csv"
)

SENSITIVITY_OUTPUT = (
    OUTPUT_ROOT
    / "market_regime_robustness_sensitivity_v1.csv"
)


# =============================================================================
# HELPERS
# =============================================================================

def summarize_group(x: pd.DataFrame) -> dict:

    favorable_n = int(
        (x["outcome"] == "FAVORABLE_FIRST").sum()
    )

    adverse_n = int(
        (x["outcome"] == "ADVERSE_FIRST").sum()
    )

    both_n = int(
        (x["outcome"] == "BOTH_SAME_BAR").sum()
    )

    unresolved_n = int(
        (x["outcome"] == "UNRESOLVED").sum()
    )

    binary_n = favorable_n + adverse_n

    ff_pct = (
        100.0 * favorable_n / binary_n
        if binary_n
        else np.nan
    )

    confirmed_n = int(
        x["c3_confirmed"].sum()
    )

    confirm_pct = (
        100.0 * confirmed_n / len(x)
        if len(x)
        else np.nan
    )

    return {
        "total_n": len(x),
        "binary_n": binary_n,
        "favorable_n": favorable_n,
        "adverse_n": adverse_n,
        "both_n": both_n,
        "unresolved_n": unresolved_n,
        "favorable_first_pct": ff_pct,
        "c3_confirmation_pct": confirm_pct,
        "avg_mfe_pct": x["final_mfe_pct"].mean(),
        "avg_mae_pct": x["final_mae_pct"].mean(),
        "symbol_n": x["symbol"].nunique(),
        "trade_date_n": x["trade_date"].nunique(),
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

        row = dict(zip(group_cols, keys))
        row.update(summarize_group(x))
        rows.append(row)

    return pd.DataFrame(rows)


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

    df["trade_date"] = pd.to_datetime(
        df["trade_date"]
    )

    df["symbol"] = (
        df["symbol"]
        .astype(str)
        .str.upper()
    )

    print("=" * 80)
    print("AE2 MARKET REGIME ROBUSTNESS V1")
    print("=" * 80)

    print(
        f"AE2 events: "
        f"{len(df):,}"
    )

    # =========================================================================
    # PRIMARY STATE 1 — SPY + QQQ 5D CONSENSUS
    # =========================================================================

    df[
        "market_5d_primary_state"
    ] = df[
        "market_prior_5d_consensus"
    ]

    # =========================================================================
    # PRIMARY STATE 2 — MARKET + STOCK 5D
    # =========================================================================

    def market_stock_5d_state(r):

        market = r[
            "market_daily_regime_state"
        ]

        stock = r[
            "trend_5d_binary_state"
        ]

        if (
            market == "OPPOSING"
            and stock == "OPPOSING"
        ):
            return "BOTH_OPPOSING"

        if (
            market == "OPPOSING"
            and stock == "ALIGNED"
        ):
            return "MARKET_OPPOSING_STOCK_ALIGNED"

        if (
            market == "ALIGNED"
            and stock == "OPPOSING"
        ):
            return "MARKET_ALIGNED_STOCK_OPPOSING"

        if (
            market == "ALIGNED"
            and stock == "ALIGNED"
        ):
            return "BOTH_ALIGNED"

        return "OTHER"

    df[
        "market_stock_5d_state"
    ] = df.apply(
        market_stock_5d_state,
        axis=1,
    )

    # =========================================================================
    # PRIMARY STATE 3 — MARKET OPPOSING × EXHAUSTION
    # =========================================================================

    def market_exhaustion_state(r):

        market = r[
            "market_daily_regime_state"
        ]

        exhaustion = r[
            "aligned_exhaustion_state"
        ]

        if market != "OPPOSING":
            return "MARKET_NOT_OPPOSING"

        if exhaustion == "MULTIPLE":
            return "OPPOSING_MARKET_MULTIPLE_EXHAUSTION"

        if exhaustion in {
            "NONE",
            "ONE",
        }:
            return "OPPOSING_MARKET_NOT_MULTIPLE_EXHAUSTION"

        return "UNKNOWN"

    df[
        "market_exhaustion_state"
    ] = df.apply(
        market_exhaustion_state,
        axis=1,
    )

    # =========================================================================
    # SPLITS
    # =========================================================================

    df["quarter"] = (
        df["trade_date"]
        .dt
        .to_period("Q")
        .astype(str)
    )

    # Split validation itself into older/newer halves.
    validation = df.loc[
        df["research_period"]
        == "VALIDATION"
    ].copy()

    validation_dates = sorted(
        validation[
            "trade_date"
        ].dropna().unique()
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
            df["research_period"]
            == "VALIDATION"
        )
        &
        (
            df["trade_date"]
            < validation_midpoint
        ),
        "validation_subperiod",
    ] = "VALIDATION_OLDER"

    df.loc[
        (
            df["research_period"]
            == "VALIDATION"
        )
        &
        (
            df["trade_date"]
            >= validation_midpoint
        ),
        "validation_subperiod",
    ] = "VALIDATION_NEWER"

    # =========================================================================
    # OVERALL DISCOVERY / VALIDATION SUMMARIES
    # =========================================================================

    frames = []

    primary_features = [
        "market_5d_primary_state",
        "market_stock_5d_state",
        "market_exhaustion_state",
    ]

    for feature in primary_features:

        x = summarize(
            df,
            [
                "research_period",
                feature,
            ],
        )

        x["feature"] = feature

        x = x.rename(
            columns={
                feature: "state"
            }
        )

        frames.append(x)

    summary = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
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

        x["feature"] = feature

        x = x.rename(
            columns={
                feature: "state"
            }
        )

        quarter_frames.append(x)

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

        x["feature"] = feature

        x = x.rename(
            columns={
                feature: "state"
            }
        )

        direction_frames.append(x)

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
    # SYMBOL BREADTH
    # =========================================================================

    symbol_summary = summarize(
        df,
        [
            "symbol",
            "market_5d_primary_state",
        ],
    )

    symbol_summary.to_csv(
        SYMBOL_OUTPUT,
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

        for period_col, period_values in [
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
        ]:

            for period_value in period_values:

                x = subset.loc[
                    subset[
                        period_col
                    ] == period_value
                ]

                if x.empty:
                    continue

                for state in [
                    "CONSENSUS_ALIGNED",
                    "CONSENSUS_OPPOSING",
                    "MIXED",
                ]:

                    y = x.loc[
                        x[
                            "market_5d_primary_state"
                        ] == state
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

                        "state":
                            state,
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
            ~df["symbol"].isin(
                {
                    "SPY",
                    "QQQ",
                    "TQQQ",
                }
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
    # PRINT
    # =========================================================================

    print()
    print("=" * 80)
    print("SPY+QQQ 5D CONSENSUS — DISCOVERY VS VALIDATION")
    print("=" * 80)

    x = summary.loc[
        summary["feature"]
        == "market_5d_primary_state"
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
            float_format=lambda z:
                f"{z:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("MARKET × STOCK 5D — DISCOVERY VS VALIDATION")
    print("=" * 80)

    x = summary.loc[
        summary["feature"]
        == "market_stock_5d_state"
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
            float_format=lambda z:
                f"{z:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("MARKET OPPOSITION × STOCK EXHAUSTION")
    print("=" * 80)

    x = summary.loc[
        summary["feature"]
        == "market_exhaustion_state"
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
            float_format=lambda z:
                f"{z:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("5D CONSENSUS — VALIDATION DIRECTIONAL")
    print("=" * 80)

    x = direction_summary.loc[
        (
            direction_summary[
                "feature"
            ]
            == "market_5d_primary_state"
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
            float_format=lambda z:
                f"{z:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("5D CONSENSUS — QUARTER STABILITY")
    print("=" * 80)

    x = quarter_summary.loc[
        quarter_summary[
            "feature"
        ]
        == "market_5d_primary_state"
    ]

    print(
        x[
            [
                "quarter",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
            ]
        ]
        .sort_values(
            [
                "quarter",
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=lambda z:
                f"{z:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("5D CONSENSUS — SENSITIVITY")
    print("=" * 80)

    print(
        sensitivity[
            [
                "sensitivity",
                "period",
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
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=lambda z:
                f"{z:.2f}",
        )
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
        f"Summary:     "
        f"{SUMMARY_OUTPUT}"
    )

    print(
        f"Quarter:     "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Direction:   "
        f"{DIRECTION_OUTPUT}"
    )

    print(
        f"Symbols:     "
        f"{SYMBOL_OUTPUT}"
    )

    print(
        f"Sensitivity: "
        f"{SENSITIVITY_OUTPUT}"
    )

    print()
    print("RESULT: COMPLETE")


if __name__ == "__main__":
    main()