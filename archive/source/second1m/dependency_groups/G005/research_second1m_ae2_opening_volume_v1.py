from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


# =============================================================================
# CONFIG
# =============================================================================

ROOT = Path(
    r"C:\Users\DirtySouth\TradingResearch"
)

CACHE_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_cache_v1"
)

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

INPUT_PATH = (
    RESEARCH_ROOT
    / "ae2_relative_strength_robustness_v1"
    / "relative_strength_robustness_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_opening_volume_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_opening_volume_features_v1.parquet"
)

THRESHOLD_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_opening_volume_discovery_thresholds_v1.csv"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_opening_volume_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_opening_volume_direction_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_opening_volume_quarter_v1.csv"
)

CONTINUOUS_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_opening_volume_continuous_v1.csv"
)

INTERACTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_opening_volume_interactions_v1.csv"
)

COVERAGE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_opening_volume_coverage_v1.csv"
)

WINDOW_20 = 20
WINDOW_60 = 60

MIN_20 = 10
MIN_60 = 20

EXPECTED_SYMBOLS = 112


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


def ratio_or_nan(
    numerator,
    denominator,
):

    if pd.isna(
        numerator
    ):
        return np.nan

    if pd.isna(
        denominator
    ):
        return np.nan

    if denominator <= 0:
        return np.nan

    return (
        float(numerator)
        / float(denominator)
    )


def classify_above_one(
    value: float,
) -> str:

    if pd.isna(value):
        return "UNKNOWN"

    if value > 1.0:
        return "ABOVE_BASELINE"

    if value < 1.0:
        return "BELOW_BASELINE"

    return "AT_BASELINE"


def classify_acceleration(
    value: float,
) -> str:

    if pd.isna(value):
        return "UNKNOWN"

    if value > 1.0:
        return "C2_VOLUME_ACCELERATING"

    if value < 1.0:
        return "C2_VOLUME_DECELERATING"

    return "C2_VOLUME_EQUAL"


def classify_discovery_state(
    value: float,
    q20: float,
    q80: float,
) -> str:

    if pd.isna(value):
        return "UNKNOWN"

    if value <= q20:
        return "LOW"

    if value >= q80:
        return "HIGH"

    return "MODERATE"


# =============================================================================
# BUILD HISTORICAL OPENING-VOLUME DATA
# =============================================================================

def load_symbol_opening_history(
    symbol: str,
) -> pd.DataFrame:

    paths = sorted(
        CACHE_ROOT.rglob(
            f"{symbol}_*.parquet"
        )
    )

    if not paths:

        raise RuntimeError(
            f"No cache partitions found for "
            f"{symbol}"
        )

    frames = []

    for path in paths:

        table = pq.read_table(
            path,
            columns=[
                "symbol",
                "trade_date",
                "timestamp_utc",
                "volume",
                "session",
            ],
        )

        frames.append(
            table.to_pandas()
        )

    df = pd.concat(
        frames,
        ignore_index=True,
    )

    df[
        "timestamp_utc"
    ] = pd.to_datetime(
        df[
            "timestamp_utc"
        ],
        utc=True,
    )

    df[
        "trade_date"
    ] = (
        pd.to_datetime(
            df[
                "trade_date"
            ]
        )
        .dt
        .normalize()
    )

    eastern = (
        df[
            "timestamp_utc"
        ]
        .dt
        .tz_convert(
            "America/New_York"
        )
    )

    df[
        "et_hour"
    ] = eastern.dt.hour

    df[
        "et_minute"
    ] = eastern.dt.minute

    # -------------------------------------------------------------------------
    # Only regular-session opening minutes:
    #
    # C1 = 09:30
    # C2 = 09:31
    # -------------------------------------------------------------------------

    opening = df.loc[
        (
            df[
                "session"
            ]
            == "RTH"
        )
        &
        (
            df[
                "et_hour"
            ]
            == 9
        )
        &
        (
            df[
                "et_minute"
            ].isin(
                [
                    30,
                    31,
                ]
            )
        )
    ].copy()

    opening[
        "opening_minute"
    ] = np.where(
        opening[
            "et_minute"
        ]
        == 30,
        "C1",
        "C2",
    )

    # -------------------------------------------------------------------------
    # One record per trading day/minute.
    # -------------------------------------------------------------------------

    pivot = (
        opening
        .pivot_table(
            index="trade_date",
            columns="opening_minute",
            values="volume",
            aggfunc="last",
        )
        .reset_index()
    )

    pivot.columns.name = None

    if "C1" not in pivot.columns:

        pivot[
            "C1"
        ] = np.nan

    if "C2" not in pivot.columns:

        pivot[
            "C2"
        ] = np.nan

    # -------------------------------------------------------------------------
    # IMPORTANT NAMESPACE FIX:
    #
    # The AE2 event dataset already contains c1_volume / c2_volume fields.
    # Historical-cache values therefore use hist_* names to avoid pandas
    # creating c1_volume_x / c1_volume_y and c2_volume_x / c2_volume_y.
    # -------------------------------------------------------------------------

    pivot = pivot.rename(
        columns={
            "C1":
                "hist_c1_volume",

            "C2":
                "hist_c2_volume",
        }
    )

    pivot = (
        pivot
        .sort_values(
            "trade_date"
        )
        .reset_index(
            drop=True
        )
    )

    # -------------------------------------------------------------------------
    # Combined first-two-minute volume.
    # -------------------------------------------------------------------------

    pivot[
        "opening_2m_volume"
    ] = (
        pivot[
            "hist_c1_volume"
        ]
        +
        pivot[
            "hist_c2_volume"
        ]
    )

    # -------------------------------------------------------------------------
    # C2/C1 volume change.
    # -------------------------------------------------------------------------

    pivot[
        "c2_vs_c1_volume_ratio"
    ] = pivot.apply(
        lambda r:
            ratio_or_nan(
                r[
                    "hist_c2_volume"
                ],
                r[
                    "hist_c1_volume"
                ],
            ),
        axis=1,
    )

    # =========================================================================
    # LEAKAGE-SAFE PRIOR-SESSION BASELINES
    #
    # shift(1) occurs BEFORE rolling median.
    #
    # Today's volume therefore never contributes to today's baseline.
    # =========================================================================

    for base_col in [
        "hist_c1_volume",
        "hist_c2_volume",
        "opening_2m_volume",
    ]:

        prior = (
            pivot[
                base_col
            ]
            .shift(1)
        )

        pivot[
            f"{base_col}_median_20d_prior"
        ] = (
            prior
            .rolling(
                window=WINDOW_20,
                min_periods=MIN_20,
            )
            .median()
        )

        pivot[
            f"{base_col}_median_60d_prior"
        ] = (
            prior
            .rolling(
                window=WINDOW_60,
                min_periods=MIN_60,
            )
            .median()
        )

    # =========================================================================
    # CURRENT-DAY RELATIVE OPENING VOLUME
    # =========================================================================

    pivot[
        "c1_rvol_20d"
    ] = pivot.apply(
        lambda r:
            ratio_or_nan(
                r[
                    "hist_c1_volume"
                ],
                r[
                    "hist_c1_volume_median_20d_prior"
                ],
            ),
        axis=1,
    )

    pivot[
        "c2_rvol_20d"
    ] = pivot.apply(
        lambda r:
            ratio_or_nan(
                r[
                    "hist_c2_volume"
                ],
                r[
                    "hist_c2_volume_median_20d_prior"
                ],
            ),
        axis=1,
    )

    pivot[
        "opening_2m_rvol_20d"
    ] = pivot.apply(
        lambda r:
            ratio_or_nan(
                r[
                    "opening_2m_volume"
                ],
                r[
                    "opening_2m_volume_median_20d_prior"
                ],
            ),
        axis=1,
    )

    pivot[
        "c1_rvol_60d"
    ] = pivot.apply(
        lambda r:
            ratio_or_nan(
                r[
                    "hist_c1_volume"
                ],
                r[
                    "hist_c1_volume_median_60d_prior"
                ],
            ),
        axis=1,
    )

    pivot[
        "c2_rvol_60d"
    ] = pivot.apply(
        lambda r:
            ratio_or_nan(
                r[
                    "hist_c2_volume"
                ],
                r[
                    "hist_c2_volume_median_60d_prior"
                ],
            ),
        axis=1,
    )

    pivot[
        "opening_2m_rvol_60d"
    ] = pivot.apply(
        lambda r:
            ratio_or_nan(
                r[
                    "opening_2m_volume"
                ],
                r[
                    "opening_2m_volume_median_60d_prior"
                ],
            ),
        axis=1,
    )

    pivot[
        "symbol"
    ] = symbol

    return pivot


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

    events = pd.read_parquet(
        INPUT_PATH
    )

    events[
        "symbol"
    ] = (
        events[
            "symbol"
        ]
        .astype(str)
        .str.upper()
    )

    events[
        "trade_date"
    ] = (
        pd.to_datetime(
            events[
                "trade_date"
            ]
        )
        .dt
        .normalize()
    )

    symbols = sorted(
        events[
            "symbol"
        ].unique()
    )

    if len(
        symbols
    ) != EXPECTED_SYMBOLS:

        raise RuntimeError(
            f"Expected "
            f"{EXPECTED_SYMBOLS} symbols, "
            f"found {len(symbols)}"
        )

    print(
        "=" * 80
    )

    print(
        "AE2 OPENING VOLUME / "
        "PARTICIPATION RESEARCH V1"
    )

    print(
        "=" * 80
    )

    print(
        f"AE2 events: "
        f"{len(events):,}"
    )

    print(
        f"Symbols:    "
        f"{len(symbols):,}"
    )

    # =========================================================================
    # BUILD PER-SYMBOL HISTORICAL VOLUME CONTEXT
    # =========================================================================

    enriched_frames = []

    for i, symbol in enumerate(
        symbols,
        start=1,
    ):

        symbol_events = (
            events.loc[
                events[
                    "symbol"
                ]
                == symbol
            ]
            .copy()
        )

        opening_history = (
            load_symbol_opening_history(
                symbol
            )
        )

        merged = (
            symbol_events
            .merge(
                opening_history,
                on=[
                    "symbol",
                    "trade_date",
                ],
                how="left",
            )
        )

        enriched_frames.append(
            merged
        )

        if (
            i % 10 == 0
            or i == len(symbols)
        ):

            enriched_n = sum(
                len(x)
                for x in enriched_frames
            )

            print(
                f"Processed "
                f"{i:>3}/{len(symbols)} "
                f"| enriched="
                f"{enriched_n:,}"
            )

    df = pd.concat(
        enriched_frames,
        ignore_index=True,
    )

    if len(
        df
    ) != len(
        events
    ):

        raise RuntimeError(
            "Event count changed after "
            "volume enrichment."
        )

    # =========================================================================
    # INTEGRITY CHECK
    #
    # Verify the reconstructed cache volume columns exist with their expected
    # non-colliding names.
    # =========================================================================

    required_volume_cols = [
        "hist_c1_volume",
        "hist_c2_volume",
        "opening_2m_volume",
        "c2_vs_c1_volume_ratio",
        "c1_rvol_20d",
        "c2_rvol_20d",
        "opening_2m_rvol_20d",
        "c1_rvol_60d",
        "c2_rvol_60d",
        "opening_2m_rvol_60d",
    ]

    missing_volume_cols = [
        col
        for col in required_volume_cols
        if col not in df.columns
    ]

    if missing_volume_cols:

        raise RuntimeError(
            "Missing reconstructed volume columns: "
            + ", ".join(
                missing_volume_cols
            )
        )

    # =========================================================================
    # INTERPRETABLE BINARY STATES
    # =========================================================================

    df[
        "c1_rvol_20d_state"
    ] = df[
        "c1_rvol_20d"
    ].apply(
        classify_above_one
    )

    df[
        "c2_rvol_20d_state"
    ] = df[
        "c2_rvol_20d"
    ].apply(
        classify_above_one
    )

    df[
        "opening_2m_rvol_20d_state"
    ] = df[
        "opening_2m_rvol_20d"
    ].apply(
        classify_above_one
    )

    df[
        "c2_vs_c1_volume_state"
    ] = df[
        "c2_vs_c1_volume_ratio"
    ].apply(
        classify_acceleration
    )

    # =========================================================================
    # DISCOVERY-FROZEN q20 / q80 STATES
    #
    # Thresholds are calculated from DISCOVERY only and then frozen.
    # =========================================================================

    discovery = df.loc[
        df[
            "research_period"
        ]
        == "DISCOVERY"
    ].copy()

    threshold_features = [
        "c1_rvol_20d",
        "c2_rvol_20d",
        "opening_2m_rvol_20d",
        "c2_vs_c1_volume_ratio",
    ]

    threshold_rows = []

    for feature in (
        threshold_features
    ):

        values = (
            discovery[
                feature
            ]
            .dropna()
            .astype(float)
        )

        if values.empty:

            raise RuntimeError(
                f"No discovery values for "
                f"{feature}"
            )

        q20 = (
            values
            .quantile(
                0.20
            )
        )

        q80 = (
            values
            .quantile(
                0.80
            )
        )

        threshold_rows.append(
            {
                "feature":
                    feature,

                "discovery_q20":
                    q20,

                "discovery_q80":
                    q80,

                "discovery_n":
                    len(values),
            }
        )

        state_col = (
            f"{feature}"
            f"_discovery_state"
        )

        df[
            state_col
        ] = df[
            feature
        ].apply(
            lambda x,
            low=q20,
            high=q80:
                classify_discovery_state(
                    x,
                    low,
                    high,
                )
        )

    thresholds = pd.DataFrame(
        threshold_rows
    )

    thresholds.to_csv(
        THRESHOLD_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SIMPLE COMPOSITE PARTICIPATION STATE
    #
    # No optimized weights.
    #
    # BOTH_ABOVE_BASELINE:
    #   C1 > historical C1 median
    #   C2 > historical C2 median
    #
    # BOTH_BELOW_BASELINE:
    #   C1 < historical C1 median
    #   C2 < historical C2 median
    #
    # Otherwise MIXED.
    # =========================================================================

    def participation_state(
        r,
    ):

        c1 = r[
            "c1_rvol_20d"
        ]

        c2 = r[
            "c2_rvol_20d"
        ]

        if (
            pd.isna(c1)
            or pd.isna(c2)
        ):
            return "UNKNOWN"

        if (
            c1 > 1.0
            and c2 > 1.0
        ):
            return "BOTH_ABOVE_BASELINE"

        if (
            c1 < 1.0
            and c2 < 1.0
        ):
            return "BOTH_BELOW_BASELINE"

        return "MIXED"

    df[
        "opening_participation_state"
    ] = df.apply(
        participation_state,
        axis=1,
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

    coverage_features = [
        "hist_c1_volume",
        "hist_c2_volume",
        "c2_vs_c1_volume_ratio",
        "c1_rvol_20d",
        "c2_rvol_20d",
        "opening_2m_rvol_20d",
        "c1_rvol_60d",
        "c2_rvol_60d",
        "opening_2m_rvol_60d",
    ]

    coverage_rows = []

    for feature in (
        coverage_features
    ):

        n = int(
            df[
                feature
            ]
            .notna()
            .sum()
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
    # SUMMARY STATES
    # =========================================================================

    state_features = [
        "c1_rvol_20d_state",
        "c2_rvol_20d_state",
        "opening_2m_rvol_20d_state",
        "c2_vs_c1_volume_state",
        "opening_participation_state",

        "c1_rvol_20d_discovery_state",
        "c2_rvol_20d_discovery_state",
        "opening_2m_rvol_20d_discovery_state",
        "c2_vs_c1_volume_ratio_discovery_state",
    ]

    summary_frames = []

    for feature in (
        state_features
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
            all_dir
            .rename(
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
            by_dir
            .rename(
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

    summary = pd.concat(
        summary_frames,
        ignore_index=True,
        sort=False,
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

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

    continuous_features = [
        "c2_vs_c1_volume_ratio",
        "c1_rvol_20d",
        "c2_rvol_20d",
        "opening_2m_rvol_20d",
        "c1_rvol_60d",
        "c2_rvol_60d",
        "opening_2m_rvol_60d",
    ]

    continuous_rows = []

    for feature in (
        continuous_features
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
    # QUARTER — PRIMARY PARTICIPATION STATE
    # =========================================================================

    quarter_summary = summarize(
        df,
        [
            "quarter",
            "opening_participation_state",
        ],
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # INTERACTIONS
    #
    # Reuse existing validated context states where available.
    # =========================================================================

    interaction_specs = []

    possible_specs = [
        (
            "opening_participation_state",
            "market_prior_5d_consensus",
        ),
        (
            "opening_participation_state",
            "positive_candidate_state",
        ),
        (
            "opening_participation_state",
            "negative_candidate_state",
        ),
        (
            "opening_participation_state",
            "aligned_exhaustion_state",
        ),
        (
            "c2_rvol_20d_discovery_state",
            "market_prior_5d_consensus",
        ),
    ]

    for left, right in (
        possible_specs
    ):

        if (
            left in df.columns
            and right in df.columns
        ):

            interaction_specs.append(
                (
                    left,
                    right,
                )
            )

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
        ] = (
            volume_feature
        )

        x[
            "context_feature"
        ] = (
            context_feature
        )

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

    if interaction_frames:

        interactions = pd.concat(
            interaction_frames,
            ignore_index=True,
            sort=False,
        )

    else:

        interactions = pd.DataFrame()

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
        "OPENING VOLUME COVERAGE"
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

    print()

    print(
        "=" * 80
    )

    print(
        "DISCOVERY-FROZEN "
        "VOLUME THRESHOLDS"
    )

    print(
        "=" * 80
    )

    print(
        thresholds.to_string(
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
        "OPENING PARTICIPATION — "
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
            == "opening_participation_state"
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

    print()

    print(
        "=" * 80
    )

    print(
        "C2 RELATIVE VOLUME — "
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
            == "c2_rvol_20d_discovery_state"
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

    print()

    print(
        "=" * 80
    )

    print(
        "C2 VS C1 VOLUME ACCELERATION — "
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
            == "c2_vs_c1_volume_state"
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
        "OPENING PARTICIPATION — "
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
            == "opening_participation_state"
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

    print()

    print(
        "=" * 80
    )

    print(
        "CONTINUOUS VOLUME METRICS"
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
        "OPENING PARTICIPATION — "
        "QUARTER STABILITY"
    )

    print(
        "=" * 80
    )

    print(
        quarter_summary[
            [
                "quarter",
                "opening_participation_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "quarter",
                "opening_participation_state",
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
        "VOLUME × CONTEXT — "
        "VALIDATION"
    )

    print(
        "=" * 80
    )

    if not interactions.empty:

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

    else:

        print(
            "No interaction rows produced."
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
        f"Thresholds:   "
        f"{THRESHOLD_OUTPUT}"
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
        f"Continuous:   "
        f"{CONTINUOUS_OUTPUT}"
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