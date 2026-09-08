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
    / "ae2_premarket_robustness_v1"
    / "ae2_premarket_robustness_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_calendar_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_calendar_features_v1.parquet"
)

WEEKDAY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_calendar_weekday_v1.csv"
)

WEEKDAY_DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_calendar_weekday_direction_v1.csv"
)

MONTH_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_calendar_month_v1.csv"
)

MONTH_YEAR_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_calendar_month_year_v1.csv"
)

SENSITIVITY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_calendar_sensitivity_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_calendar_weekday_symbol_v1.csv"
)

CONCENTRATION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_calendar_weekday_concentration_v1.csv"
)

AUDIT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_calendar_time_invariance_audit_v1.csv"
)

EXCLUDE_SYMBOLS = {
    "SPY",
    "QQQ",
    "TQQQ",
}

WEEKDAY_ORDER = [
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
]


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
        observed=False,
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
        "c3_confirmed",
        "final_mfe_pct",
        "final_mae_pct",
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
    ] = (
        pd.to_datetime(
            df[
                "trade_date"
            ],
            errors="coerce",
        )
        .dt
        .normalize()
    )

    if (
        df[
            "trade_date"
        ].isna().any()
    ):

        raise RuntimeError(
            "trade_date contains invalid/null "
            "values after conversion."
        )

    print(
        "=" * 80
    )

    print(
        "AE2 TIME / CALENDAR RESEARCH V1"
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

    print(
        f"Dates:      "
        f"{df['trade_date'].nunique():,}"
    )

    print(
        f"Earliest:   "
        f"{df['trade_date'].min().date()}"
    )

    print(
        f"Latest:     "
        f"{df['trade_date'].max().date()}"
    )

    # =========================================================================
    # R11 TIME-OF-DAY APPLICABILITY AUDIT
    #
    # AE2 is structurally the C2 architecture.
    #
    # It should not be subjected to artificial early/middle/late-RTH testing
    # because entry timing is fixed by architecture.
    #
    # We inspect timestamp-like columns if available solely as a parity audit.
    # =========================================================================

    timestamp_candidates = [
        "signal_timestamp",
        "event_timestamp",
        "c2_timestamp",
        "entry_timestamp",
    ]

    timestamp_col = None

    for col in timestamp_candidates:

        if col in df.columns:

            timestamp_col = col
            break

    audit_rows = []

    if timestamp_col is not None:

        ts = pd.to_datetime(
            df[
                timestamp_col
            ],
            utc=True,
            errors="coerce",
        )

        valid_ts = ts.dropna()

        if not valid_ts.empty:

            eastern = (
                valid_ts
                .dt
                .tz_convert(
                    "America/New_York"
                )
            )

            hhmm_counts = (
                eastern
                .dt
                .strftime(
                    "%H:%M"
                )
                .value_counts()
                .sort_index()
            )

            for hhmm, n in (
                hhmm_counts.items()
            ):

                audit_rows.append(
                    {
                        "audit_type":
                            "SIGNAL_TIME_ET",

                        "value":
                            hhmm,

                        "event_n":
                            int(n),

                        "event_pct":
                            (
                                100.0
                                * n
                                / len(valid_ts)
                            ),
                    }
                )

    # Architectural record regardless of whether a timestamp exists.
    audit_rows.extend(
        [
            {
                "audit_type":
                    "ROADMAP_FACTOR",

                "value":
                    "TIME_OF_DAY",

                "event_n":
                    len(df),

                "event_pct":
                    100.0,

                "disposition":
                    "NOT_APPLICABLE_FIXED_C2_ARCHITECTURE",
            },
            {
                "audit_type":
                    "ROADMAP_FACTOR",

                "value":
                    "EARLY_MIDDLE_LATE_RTH",

                "event_n":
                    len(df),

                "event_pct":
                    100.0,

                "disposition":
                    "NOT_APPLICABLE_FIXED_C2_ARCHITECTURE",
            },
            {
                "audit_type":
                    "ROADMAP_FACTOR",

                "value":
                    "MINUTES_SINCE_RTH_OPEN",

                "event_n":
                    len(df),

                "event_pct":
                    100.0,

                "disposition":
                    "NOT_APPLICABLE_FIXED_C2_ARCHITECTURE",
            },
        ]
    )

    audit = pd.DataFrame(
        audit_rows
    )

    audit.to_csv(
        AUDIT_OUTPUT,
        index=False,
    )

    # =========================================================================
    # CALENDAR FEATURES
    # =========================================================================

    df[
        "weekday_number"
    ] = (
        df[
            "trade_date"
        ]
        .dt
        .weekday
    )

    df[
        "weekday"
    ] = (
        df[
            "trade_date"
        ]
        .dt
        .day_name()
        .str
        .upper()
    )

    # Defensive check: equities should not contain weekends.
    invalid_weekdays = df.loc[
        ~df[
            "weekday"
        ].isin(
            WEEKDAY_ORDER
        )
    ]

    if not invalid_weekdays.empty:

        raise RuntimeError(
            "Unexpected non-Monday-Friday "
            f"trade dates: {len(invalid_weekdays):,}"
        )

    df[
        "month_number"
    ] = (
        df[
            "trade_date"
        ]
        .dt
        .month
    )

    df[
        "month_name"
    ] = (
        df[
            "trade_date"
        ]
        .dt
        .month_name()
        .str
        .upper()
    )

    df[
        "year"
    ] = (
        df[
            "trade_date"
        ]
        .dt
        .year
    )

    df[
        "month_year"
    ] = (
        df[
            "trade_date"
        ]
        .dt
        .to_period(
            "M"
        )
        .astype(str)
    )

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
    # WEEKDAY — DISCOVERY / VALIDATION
    # =========================================================================

    weekday_summary = summarize(
        df,
        [
            "research_period",
            "weekday",
        ],
    )

    weekday_summary[
        "weekday_order"
    ] = weekday_summary[
        "weekday"
    ].map(
        {
            name:
                i
            for i, name in enumerate(
                WEEKDAY_ORDER
            )
        }
    )

    weekday_summary = (
        weekday_summary
        .sort_values(
            [
                "research_period",
                "weekday_order",
            ]
        )
        .drop(
            columns=[
                "weekday_order",
            ]
        )
    )

    weekday_summary.to_csv(
        WEEKDAY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # WEEKDAY × DIRECTION
    #
    # This is allowed because direction is a primary architecture split, not
    # an exploratory higher-dimensional context interaction.
    # =========================================================================

    weekday_direction = summarize(
        df,
        [
            "research_period",
            "direction",
            "weekday",
        ],
    )

    weekday_direction[
        "weekday_order"
    ] = weekday_direction[
        "weekday"
    ].map(
        {
            name:
                i
            for i, name in enumerate(
                WEEKDAY_ORDER
            )
        }
    )

    weekday_direction = (
        weekday_direction
        .sort_values(
            [
                "research_period",
                "direction",
                "weekday_order",
            ]
        )
        .drop(
            columns=[
                "weekday_order",
            ]
        )
    )

    weekday_direction.to_csv(
        WEEKDAY_DIRECTION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # MONTH
    #
    # Low-priority exploratory calendar context.
    #
    # We report it but do not promote isolated high/low months because the
    # history spans only portions of 2025 and 2026.
    # =========================================================================

    month_summary = summarize(
        df,
        [
            "research_period",
            "month_number",
            "month_name",
        ],
    )

    month_summary = (
        month_summary
        .sort_values(
            [
                "research_period",
                "month_number",
            ]
        )
    )

    month_summary.to_csv(
        MONTH_OUTPUT,
        index=False,
    )

    # =========================================================================
    # MONTH-YEAR
    #
    # Important distinction:
    # "September" seasonality across two years is not the same thing as a
    # particular September 2025 regime.
    #
    # Month-year output lets us detect that distinction.
    # =========================================================================

    month_year_summary = summarize(
        df,
        [
            "month_year",
        ],
    )

    month_year_summary = (
        month_year_summary
        .sort_values(
            "month_year"
        )
    )

    month_year_summary.to_csv(
        MONTH_YEAR_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SENSITIVITY
    # =========================================================================

    sensitivity_rows = []

    sensitivity_specs = [
        (
            "BASE",
            df,
        ),
        (
            "EXCLUDE_SPY_QQQ_TQQQ",
            df.loc[
                ~df[
                    "symbol"
                ].isin(
                    EXCLUDE_SYMBOLS
                )
            ],
        ),
    ]

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

    for (
        sensitivity_name,
        subset,
    ) in sensitivity_specs:

        for (
            period_col,
            period_value,
        ) in period_specs:

            period_subset = subset.loc[
                subset[
                    period_col
                ]
                == period_value
            ]

            if period_subset.empty:
                continue

            for weekday in (
                WEEKDAY_ORDER
            ):

                x = period_subset.loc[
                    period_subset[
                        "weekday"
                    ]
                    == weekday
                ]

                if x.empty:
                    continue

                row = {
                    "sensitivity":
                        sensitivity_name,

                    "period_type":
                        period_col,

                    "period":
                        period_value,

                    "weekday":
                        weekday,
                }

                row.update(
                    summarize_group(x)
                )

                sensitivity_rows.append(
                    row
                )

    sensitivity = pd.DataFrame(
        sensitivity_rows
    )

    sensitivity[
        "weekday_order"
    ] = sensitivity[
        "weekday"
    ].map(
        {
            name:
                i
            for i, name in enumerate(
                WEEKDAY_ORDER
            )
        }
    )

    sensitivity = (
        sensitivity
        .sort_values(
            [
                "sensitivity",
                "period",
                "weekday_order",
            ]
        )
        .drop(
            columns=[
                "weekday_order",
            ]
        )
    )

    sensitivity.to_csv(
        SENSITIVITY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SYMBOL BREADTH BY WEEKDAY
    # =========================================================================

    symbol_summary = summarize(
        df,
        [
            "weekday",
            "symbol",
        ],
    )

    symbol_summary[
        "weekday_order"
    ] = symbol_summary[
        "weekday"
    ].map(
        {
            name:
                i
            for i, name in enumerate(
                WEEKDAY_ORDER
            )
        }
    )

    symbol_summary = (
        symbol_summary
        .sort_values(
            [
                "weekday_order",
                "total_n",
                "symbol",
            ],
            ascending=[
                True,
                False,
                True,
            ],
        )
        .drop(
            columns=[
                "weekday_order",
            ]
        )
    )

    symbol_summary.to_csv(
        SYMBOL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SYMBOL CONCENTRATION BY WEEKDAY
    # =========================================================================

    concentration_rows = []

    for weekday in (
        WEEKDAY_ORDER
    ):

        subset = df.loc[
            df[
                "weekday"
            ]
            == weekday
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
                "weekday":
                    weekday,

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

    concentration[
        "weekday_order"
    ] = concentration[
        "weekday"
    ].map(
        {
            name:
                i
            for i, name in enumerate(
                WEEKDAY_ORDER
            )
        }
    )

    concentration = (
        concentration
        .sort_values(
            "weekday_order"
        )
        .drop(
            columns=[
                "weekday_order",
            ]
        )
    )

    concentration.to_csv(
        CONCENTRATION_OUTPUT,
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
        "A32 TIME-OF-DAY APPLICABILITY AUDIT"
    )

    print(
        "=" * 80
    )

    print(
        audit.to_string(
            index=False,
        )
    )

    print()

    print(
        "=" * 80
    )

    print(
        "WEEKDAY — DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    print(
        weekday_summary[
            [
                "research_period",
                "weekday",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
                "symbol_n",
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
        "WEEKDAY — VALIDATION DIRECTIONAL"
    )

    print(
        "=" * 80
    )

    x = weekday_direction.loc[
        weekday_direction[
            "research_period"
        ]
        == "VALIDATION"
    ]

    print(
        x[
            [
                "direction",
                "weekday",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "symbol_n",
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
        "WEEKDAY — VALIDATION SUBPERIOD / SENSITIVITY"
    )

    print(
        "=" * 80
    )

    print(
        sensitivity[
            [
                "sensitivity",
                "period",
                "weekday",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "symbol_n",
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
        "MONTH — DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    print(
        month_summary[
            [
                "research_period",
                "month_number",
                "month_name",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "symbol_n",
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
        "MONTH-YEAR STABILITY"
    )

    print(
        "=" * 80
    )

    print(
        month_year_summary[
            [
                "month_year",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "symbol_n",
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
        "WEEKDAY SYMBOL CONCENTRATION"
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
        "WEEKDAY SYMBOL BREADTH — TOP 10 EACH"
    )

    print(
        "=" * 80
    )

    display_symbols = (
        symbol_summary
        .sort_values(
            [
                "weekday",
                "total_n",
            ],
            ascending=[
                True,
                False,
            ],
        )
        .groupby(
            "weekday",
            group_keys=False,
        )
        .head(10)
    )

    print(
        display_symbols[
            [
                "weekday",
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
        f"Weekday:        "
        f"{WEEKDAY_OUTPUT}"
    )

    print(
        f"Direction:      "
        f"{WEEKDAY_DIRECTION_OUTPUT}"
    )

    print(
        f"Month:          "
        f"{MONTH_OUTPUT}"
    )

    print(
        f"Month-year:     "
        f"{MONTH_YEAR_OUTPUT}"
    )

    print(
        f"Sensitivity:    "
        f"{SENSITIVITY_OUTPUT}"
    )

    print(
        f"Symbols:        "
        f"{SYMBOL_OUTPUT}"
    )

    print(
        f"Concentration:  "
        f"{CONCENTRATION_OUTPUT}"
    )

    print(
        f"Time audit:     "
        f"{AUDIT_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()