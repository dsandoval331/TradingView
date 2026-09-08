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
    / "ae2_daily_trend_v1"
    / "ae2_daily_trend_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_trend_exhaustion_robustness_v1"
)

THRESHOLD_OUTPUT = (
    OUTPUT_ROOT
    / "trend_exhaustion_discovery_thresholds_v1.csv"
)

STATE_OUTPUT = (
    OUTPUT_ROOT
    / "trend_exhaustion_states_v1.parquet"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "trend_exhaustion_summary_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "trend_exhaustion_quarter_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "trend_exhaustion_symbol_v1.csv"
)

SENSITIVITY_OUTPUT = (
    OUTPUT_ROOT
    / "trend_exhaustion_sensitivity_v1.csv"
)

LOOKBACKS = [3, 5, 10, 20]

LEVERAGED_ETFS = {
    "TQQQ",
}


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

    favorable_first_pct = (
        100.0 * favorable_n / binary_n
        if binary_n
        else np.nan
    )

    c3_confirmed_n = int(
        x["c3_confirmed"].sum()
    )

    c3_confirmation_pct = (
        100.0 * c3_confirmed_n / len(x)
        if len(x)
        else np.nan
    )

    return {
        "total_n": int(len(x)),
        "binary_n": binary_n,
        "favorable_n": favorable_n,
        "adverse_n": adverse_n,
        "both_n": both_n,
        "unresolved_n": unresolved_n,
        "favorable_first_pct": favorable_first_pct,
        "c3_confirmed_n": c3_confirmed_n,
        "c3_confirmation_pct": c3_confirmation_pct,
        "avg_mfe_pct": x["final_mfe_pct"].mean(),
        "avg_mae_pct": x["final_mae_pct"].mean(),
        "median_mfe_pct": x["final_mfe_pct"].median(),
        "median_mae_pct": x["final_mae_pct"].median(),
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


def classify_trend(
    value: float,
    q20: float,
    q80: float,
) -> str:

    if pd.isna(value):
        return "UNKNOWN"

    # Direction-normalized:
    # positive = prior trend aligned with AE2
    # negative = prior trend opposed to AE2.

    if value >= q80:
        return "STRONG_ALIGNED"

    if value > 0:
        return "MODERATE_ALIGNED"

    if value <= q20:
        return "STRONG_OPPOSING"

    if value < 0:
        return "MODERATE_OPPOSING"

    return "FLAT"


def binary_trend_state(
    value: float,
) -> str:

    if pd.isna(value):
        return "UNKNOWN"

    if value > 0:
        return "ALIGNED"

    if value < 0:
        return "OPPOSING"

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
            f"Input not found: {INPUT_PATH}"
        )

    df = pd.read_parquet(INPUT_PATH)

    df["symbol"] = (
        df["symbol"]
        .astype(str)
        .str.upper()
    )

    df["trade_date"] = pd.to_datetime(
        df["trade_date"]
    )

    # -------------------------------------------------------------------------
    # Ensure research-period labels.
    # -------------------------------------------------------------------------

    if "research_period" not in df.columns:

        df["research_period"] = (
            df["temporal_half"]
            .map(
                {
                    "OLDEST_HALF": "DISCOVERY",
                    "NEWEST_HALF": "VALIDATION",
                }
            )
        )

    df["quarter"] = (
        df["trade_date"]
        .dt
        .to_period("Q")
        .astype(str)
    )

    discovery = df.loc[
        df["research_period"] == "DISCOVERY"
    ].copy()

    validation = df.loc[
        df["research_period"] == "VALIDATION"
    ].copy()

    print("=" * 80)
    print("AE2 MULTI-DAY TREND / EXHAUSTION ROBUSTNESS V1")
    print("=" * 80)

    print(f"AE2 events:       {len(df):,}")
    print(f"Discovery events: {len(discovery):,}")
    print(f"Validation events:{len(validation):,}")

    # =========================================================================
    # DISCOVERY-FROZEN THRESHOLDS
    #
    # q20/q80 are calculated ONLY from discovery.
    # They are then applied unchanged to validation.
    # =========================================================================

    threshold_rows = []

    for lookback in LOOKBACKS:

        col = (
            f"directional_prior_ret_"
            f"{lookback}d_pct"
        )

        values = (
            discovery[col]
            .dropna()
            .astype(float)
        )

        q20 = values.quantile(0.20)
        q80 = values.quantile(0.80)

        threshold_rows.append(
            {
                "lookback_days": lookback,
                "feature": col,
                "discovery_q20": q20,
                "discovery_q80": q80,
                "discovery_n": len(values),
            }
        )

        state_col = (
            f"trend_{lookback}d_state"
        )

        binary_col = (
            f"trend_{lookback}d_binary_state"
        )

        df[state_col] = df[col].apply(
            lambda x:
                classify_trend(
                    x,
                    q20,
                    q80,
                )
        )

        df[binary_col] = df[col].apply(
            binary_trend_state
        )

    thresholds = pd.DataFrame(
        threshold_rows
    )

    thresholds.to_csv(
        THRESHOLD_OUTPUT,
        index=False,
    )

    # =========================================================================
    # EXHAUSTION SCORE
    #
    # Count how many horizons show STRONG same-direction prior trend.
    #
    # This tests the exhaustion hypothesis directly:
    #
    #   0 = no strong aligned prior trend
    #   1 = one horizon
    #   2+ = multiple horizons
    #
    # No outcome-derived weights.
    # =========================================================================

    aligned_strong_cols = []

    opposing_strong_cols = []

    for lookback in LOOKBACKS:

        state_col = (
            f"trend_{lookback}d_state"
        )

        aligned_col = (
            f"trend_{lookback}d_"
            f"strong_aligned"
        )

        opposing_col = (
            f"trend_{lookback}d_"
            f"strong_opposing"
        )

        df[aligned_col] = (
            df[state_col]
            == "STRONG_ALIGNED"
        ).astype(int)

        df[opposing_col] = (
            df[state_col]
            == "STRONG_OPPOSING"
        ).astype(int)

        aligned_strong_cols.append(
            aligned_col
        )

        opposing_strong_cols.append(
            opposing_col
        )

    df[
        "strong_aligned_horizon_n"
    ] = df[
        aligned_strong_cols
    ].sum(axis=1)

    df[
        "strong_opposing_horizon_n"
    ] = df[
        opposing_strong_cols
    ].sum(axis=1)

    def exhaustion_state(n):

        if n == 0:
            return "NONE"

        if n == 1:
            return "ONE"

        return "MULTIPLE"

    df[
        "aligned_exhaustion_state"
    ] = df[
        "strong_aligned_horizon_n"
    ].apply(
        exhaustion_state
    )

    df[
        "opposing_strength_state"
    ] = df[
        "strong_opposing_horizon_n"
    ].apply(
        exhaustion_state
    )

    # =========================================================================
    # PRIMARY LOOKBACK SUMMARIES
    # =========================================================================

    summary_frames = []

    for lookback in LOOKBACKS:

        state_col = (
            f"trend_{lookback}d_state"
        )

        all_dir = summarize(
            df,
            [
                "research_period",
                state_col,
            ],
        )

        all_dir["direction"] = "ALL"
        all_dir["lookback_days"] = lookback

        all_dir = all_dir.rename(
            columns={
                state_col: "state"
            }
        )

        by_dir = summarize(
            df,
            [
                "research_period",
                "direction",
                state_col,
            ],
        )

        by_dir["lookback_days"] = lookback

        by_dir = by_dir.rename(
            columns={
                state_col: "state"
            }
        )

        summary_frames.extend(
            [
                all_dir,
                by_dir,
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
    # QUARTER STABILITY — 5D
    # =========================================================================

    quarter_all = summarize(
        df,
        [
            "quarter",
            "trend_5d_state",
        ],
    )

    quarter_all["direction"] = "ALL"

    quarter_all = quarter_all.rename(
        columns={
            "trend_5d_state":
                "state"
        }
    )

    quarter_direction = summarize(
        df,
        [
            "quarter",
            "direction",
            "trend_5d_state",
        ],
    )

    quarter_direction = (
        quarter_direction.rename(
            columns={
                "trend_5d_state":
                    "state"
            }
        )
    )

    quarter_summary = pd.concat(
        [
            quarter_all,
            quarter_direction,
        ],
        ignore_index=True,
        sort=False,
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SYMBOL BREADTH — 5D
    # =========================================================================

    symbol_summary = summarize(
        df,
        [
            "symbol",
            "trend_5d_binary_state",
        ],
    )

    symbol_summary.to_csv(
        SYMBOL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SENSITIVITY TESTS
    # =========================================================================

    sensitivity_rows = []

    def add_sensitivity(
        label: str,
        subset: pd.DataFrame,
    ):

        for period in [
            "DISCOVERY",
            "VALIDATION",
        ]:

            x = subset.loc[
                subset[
                    "research_period"
                ] == period
            ]

            if x.empty:
                continue

            for state in [
                "ALIGNED",
                "OPPOSING",
            ]:

                y = x.loc[
                    x[
                        "trend_5d_binary_state"
                    ] == state
                ]

                row = {
                    "sensitivity":
                        label,

                    "research_period":
                        period,

                    "state":
                        state,
                }

                row.update(
                    summarize_group(y)
                )

                sensitivity_rows.append(
                    row
                )

    # Base population.
    add_sensitivity(
        "BASE",
        df,
    )

    # Remove leveraged ETF.
    add_sensitivity(
        "EXCLUDE_LEVERAGED_ETF",
        df.loc[
            ~df["symbol"].isin(
                LEVERAGED_ETFS
            )
        ],
    )

    # Remove SPY / QQQ.
    add_sensitivity(
        "EXCLUDE_SPY_QQQ",
        df.loc[
            ~df["symbol"].isin(
                {"SPY", "QQQ"}
            )
        ],
    )

    # Individual stocks only:
    # remove benchmark ETFs and leveraged ETF.
    add_sensitivity(
        "INDIVIDUAL_STOCKS_CORE",
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

    # Mature-history population:
    # removes first 20 trading days of each symbol.
    df = df.sort_values(
        [
            "symbol",
            "trade_date",
        ]
    )

    unique_days = (
        df[
            [
                "symbol",
                "trade_date",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            [
                "symbol",
                "trade_date",
            ]
        )
    )

    unique_days[
        "symbol_day_index"
    ] = (
        unique_days
        .groupby("symbol")
        .cumcount()
    )

    df = df.merge(
        unique_days,
        on=[
            "symbol",
            "trade_date",
        ],
        how="left",
    )

    add_sensitivity(
        "EXCLUDE_FIRST_20_SYMBOL_DAYS",
        df.loc[
            df["symbol_day_index"]
            >= 20
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
    # SAVE EVENT STATES
    # =========================================================================

    df.to_parquet(
        STATE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # REPORT
    # =========================================================================

    print()
    print("=" * 80)
    print("DISCOVERY-FROZEN THRESHOLDS")
    print("=" * 80)

    print(
        thresholds.to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.4f}",
        )
    )

    # -------------------------------------------------------------------------
    # 5D primary
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("5D TREND MAGNITUDE — DISCOVERY VS VALIDATION")
    print("=" * 80)

    display = summary.loc[
        (
            summary[
                "lookback_days"
            ] == 5
        )
        &
        (
            summary[
                "direction"
            ] == "ALL"
        )
    ]

    print(
        display[
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
                lambda x:
                    f"{x:.2f}",
        )
    )

    # -------------------------------------------------------------------------
    # Directional validation
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("5D TREND MAGNITUDE — VALIDATION DIRECTIONAL")
    print("=" * 80)

    display = summary.loc[
        (
            summary[
                "lookback_days"
            ] == 5
        )
        &
        (
            summary[
                "research_period"
            ] == "VALIDATION"
        )
        &
        (
            summary[
                "direction"
            ] != "ALL"
        )
    ]

    print(
        display[
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
                lambda x:
                    f"{x:.2f}",
        )
    )

    # -------------------------------------------------------------------------
    # Multi-horizon aligned exhaustion
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("MULTI-HORIZON SAME-DIRECTION EXHAUSTION")
    print("=" * 80)

    exhaustion_all = summarize(
        df,
        [
            "research_period",
            "aligned_exhaustion_state",
        ],
    )

    print(
        exhaustion_all[
            [
                "research_period",
                "aligned_exhaustion_state",
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
                "aligned_exhaustion_state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    # -------------------------------------------------------------------------
    # Opposing strength
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("MULTI-HORIZON OPPOSING TREND STRENGTH")
    print("=" * 80)

    opposing_all = summarize(
        df,
        [
            "research_period",
            "opposing_strength_state",
        ],
    )

    print(
        opposing_all[
            [
                "research_period",
                "opposing_strength_state",
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
                "opposing_strength_state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    # -------------------------------------------------------------------------
    # Sensitivity
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("5D BINARY TREND — SENSITIVITY")
    print("=" * 80)

    print(
        sensitivity[
            [
                "sensitivity",
                "research_period",
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
                "research_period",
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    # -------------------------------------------------------------------------
    # Quarter
    # -------------------------------------------------------------------------

    print()
    print("=" * 80)
    print("5D TREND — QUARTER STABILITY")
    print("=" * 80)

    quarter_display = (
        quarter_summary.loc[
            quarter_summary[
                "direction"
            ] == "ALL"
        ]
    )

    print(
        quarter_display[
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
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("OUTPUTS")
    print("=" * 80)

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
        f"Symbols:    "
        f"{SYMBOL_OUTPUT}"
    )

    print(
        f"Sensitivity:"
        f" {SENSITIVITY_OUTPUT}"
    )

    print()
    print("RESULT: COMPLETE")


if __name__ == "__main__":
    main()