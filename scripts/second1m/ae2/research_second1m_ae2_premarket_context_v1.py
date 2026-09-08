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
    / "partitions"
)

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

INPUT_PATH = (
    RESEARCH_ROOT
    / "ae2_session_levels_robustness_v1"
    / "ae2_session_levels_robustness_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_premarket_context_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_context_features_v1.parquet"
)

THRESHOLD_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_context_thresholds_v1.csv"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_context_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_context_direction_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_context_quarter_v1.csv"
)

CONTINUOUS_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_context_continuous_v1.csv"
)

INTERACTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_context_interactions_v1.csv"
)

COVERAGE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_context_coverage_v1.csv"
)

PRIOR_CLOSE_AUDIT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_premarket_prior_close_audit_v1.csv"
)

EXPECTED_SYMBOLS = 112

RVOL_WINDOW = 20
RVOL_MIN_PERIODS = 10


# =============================================================================
# GENERIC HELPERS
# =============================================================================

def normalize_date_ns(
    series: pd.Series,
) -> pd.Series:

    return (
        pd.to_datetime(
            series,
            errors="coerce",
        )
        .dt
        .normalize()
        .astype(
            "datetime64[ns]"
        )
    )


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


def aligned_state(
    value: float,
) -> str:

    if pd.isna(value):
        return "UNKNOWN"

    if value > 0:
        return "ALIGNED"

    if value < 0:
        return "OPPOSING"

    return "FLAT"


def discovery_bucket(
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
# CACHE HELPERS
# =============================================================================

def symbol_paths(
    symbol: str,
) -> list[Path]:

    symbol_dir = (
        CACHE_ROOT
        / symbol
    )

    if not symbol_dir.exists():

        raise RuntimeError(
            f"Cache directory not found for "
            f"{symbol}: {symbol_dir}"
        )

    paths = sorted(
        symbol_dir.glob(
            f"{symbol}_*.parquet"
        )
    )

    if not paths:

        raise RuntimeError(
            f"No cache partitions found "
            f"for {symbol}"
        )

    return paths


# =============================================================================
# BUILD PREMARKET HISTORY
# =============================================================================

def build_symbol_premarket_history(
    symbol: str,
) -> pd.DataFrame:

    frames = []

    for path in symbol_paths(
        symbol
    ):

        table = pq.read_table(
            path,
            columns=[
                "symbol",
                "timestamp_et",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "session",
            ],
        )

        frames.append(
            table.to_pandas()
        )

    bars = pd.concat(
        frames,
        ignore_index=True,
    )

    bars[
        "symbol"
    ] = (
        bars[
            "symbol"
        ]
        .astype(str)
        .str.upper()
    )

    bars[
        "trade_date"
    ] = normalize_date_ns(
        bars[
            "trade_date"
        ]
    )

    bars[
        "timestamp_et"
    ] = (
        pd.to_datetime(
            bars[
                "timestamp_et"
            ],
            utc=True,
            errors="coerce",
        )
        .dt
        .tz_convert(
            "America/New_York"
        )
    )

    bars = (
        bars
        .dropna(
            subset=[
                "trade_date",
                "timestamp_et",
            ]
        )
        .sort_values(
            "timestamp_et"
        )
        .drop_duplicates(
            subset=[
                "timestamp_et"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    # =========================================================================
    # PREMARKET
    # =========================================================================

    pre = bars.loc[
        bars[
            "session"
        ]
        == "PRE"
    ].copy()

    pre_daily = (
        pre.groupby(
            "trade_date",
            as_index=False,
        )
        .agg(
            pre_open=(
                "open",
                "first",
            ),
            pre_high=(
                "high",
                "max",
            ),
            pre_low=(
                "low",
                "min",
            ),
            pre_close=(
                "close",
                "last",
            ),
            pre_volume=(
                "volume",
                "sum",
            ),
            pre_bar_n=(
                "close",
                "size",
            ),
        )
    )

    pre_daily[
        "trade_date"
    ] = normalize_date_ns(
        pre_daily[
            "trade_date"
        ]
    )

    pre_daily[
        "symbol"
    ] = symbol

    # =========================================================================
    # RTH DAILY CLOSE
    #
    # IMPORTANT:
    #
    # We deliberately namespace this as pmctx_prior_rth_close.
    #
    # The incoming A30 dataset already has a column named prior_rth_close.
    # Reusing that name here would cause pandas to produce _x/_y columns.
    # =========================================================================

    rth = bars.loc[
        bars[
            "session"
        ]
        == "RTH"
    ].copy()

    rth_daily = (
        rth.groupby(
            "trade_date",
            as_index=False,
        )
        .agg(
            rth_close=(
                "close",
                "last",
            )
        )
    )

    rth_daily[
        "trade_date"
    ] = normalize_date_ns(
        rth_daily[
            "trade_date"
        ]
    )

    rth_daily = (
        rth_daily
        .sort_values(
            "trade_date"
        )
        .reset_index(
            drop=True
        )
    )

    rth_daily[
        "pmctx_prior_rth_close"
    ] = (
        rth_daily[
            "rth_close"
        ]
        .shift(1)
    )

    pre_daily = (
        pre_daily.merge(
            rth_daily[
                [
                    "trade_date",
                    "pmctx_prior_rth_close",
                ]
            ],
            on="trade_date",
            how="left",
            validate="one_to_one",
        )
    )

    pre_daily = (
        pre_daily
        .sort_values(
            "trade_date"
        )
        .reset_index(
            drop=True
        )
    )

    # =========================================================================
    # PREMARKET RAW METRICS
    # =========================================================================

    pre_daily[
        "premarket_return_pct"
    ] = (
        (
            pre_daily[
                "pre_close"
            ]
            /
            pre_daily[
                "pre_open"
            ]
            - 1.0
        )
        * 100.0
    )

    pre_daily[
        "premarket_range_pct"
    ] = (
        (
            pre_daily[
                "pre_high"
            ]
            -
            pre_daily[
                "pre_low"
            ]
        )
        /
        pre_daily[
            "pmctx_prior_rth_close"
        ]
        * 100.0
    )

    pre_daily[
        "premarket_gap_from_prior_close_pct"
    ] = (
        (
            pre_daily[
                "pre_open"
            ]
            /
            pre_daily[
                "pmctx_prior_rth_close"
            ]
            - 1.0
        )
        * 100.0
    )

    pre_daily[
        "premarket_close_vs_prior_close_pct"
    ] = (
        (
            pre_daily[
                "pre_close"
            ]
            /
            pre_daily[
                "pmctx_prior_rth_close"
            ]
            - 1.0
        )
        * 100.0
    )

    pre_range = (
        pre_daily[
            "pre_high"
        ]
        -
        pre_daily[
            "pre_low"
        ]
    )

    pre_daily[
        "premarket_close_location_pct"
    ] = np.where(
        pre_range > 0,
        (
            (
                pre_daily[
                    "pre_close"
                ]
                -
                pre_daily[
                    "pre_low"
                ]
            )
            /
            pre_range
            * 100.0
        ),
        np.nan,
    )

    # =========================================================================
    # LEAKAGE-SAFE PREMARKET RVOL
    #
    # Today's premarket volume never participates in today's baseline.
    # =========================================================================

    prior_pre_volume = (
        pre_daily[
            "pre_volume"
        ]
        .shift(1)
    )

    pre_daily[
        "pre_volume_median_20d_prior"
    ] = (
        prior_pre_volume
        .rolling(
            window=RVOL_WINDOW,
            min_periods=RVOL_MIN_PERIODS,
        )
        .median()
    )

    pre_daily[
        "premarket_rvol_20d"
    ] = np.where(
        (
            pre_daily[
                "pre_volume_median_20d_prior"
            ]
            > 0
        ),
        (
            pre_daily[
                "pre_volume"
            ]
            /
            pre_daily[
                "pre_volume_median_20d_prior"
            ]
        ),
        np.nan,
    )

    return pre_daily


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
    ] = normalize_date_ns(
        events[
            "trade_date"
        ]
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

    required_cols = [
        "symbol",
        "trade_date",
        "direction",
        "research_period",
        "outcome",
        "c3_confirmed",
        "final_mfe_pct",
        "final_mae_pct",

        "c1_open",
        "c1_high",
        "c1_low",
        "c1_close",
        "c2_close",

        "market_prior_5d_consensus",
        "positive_candidate_state",
        "negative_candidate_state",
        "session_level_clear_state",
        "low_c2_rvol_market_opposition_state",
    ]

    missing = [
        col
        for col in required_cols
        if col not in events.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing required input columns: "
            + ", ".join(
                missing
            )
        )

    print(
        "=" * 80
    )

    print(
        "AE2 GAP + PREMARKET CONTEXT V1"
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
    # ENRICH
    # =========================================================================

    enriched_frames = []

    for i, symbol in enumerate(
        symbols,
        start=1,
    ):

        event_subset = (
            events.loc[
                events[
                    "symbol"
                ]
                == symbol
            ]
            .copy()
        )

        event_subset[
            "trade_date"
        ] = normalize_date_ns(
            event_subset[
                "trade_date"
            ]
        )

        pre = build_symbol_premarket_history(
            symbol
        )

        pre[
            "trade_date"
        ] = normalize_date_ns(
            pre[
                "trade_date"
            ]
        )

        event_subset = event_subset.merge(
            pre,
            on=[
                "symbol",
                "trade_date",
            ],
            how="left",
            validate="many_to_one",
        )

        enriched_frames.append(
            event_subset
        )

        if (
            i % 10 == 0
            or i == len(symbols)
        ):

            current_n = sum(
                len(x)
                for x in enriched_frames
            )

            print(
                f"Processed "
                f"{i:>3}/{len(symbols)} "
                f"| enriched="
                f"{current_n:,}"
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
            "premarket enrichment."
        )

    # =========================================================================
    # POST-MERGE INTEGRITY
    # =========================================================================

    required_pmctx_cols = [
        "pre_open",
        "pre_high",
        "pre_low",
        "pre_close",
        "pre_volume",
        "pmctx_prior_rth_close",
        "premarket_return_pct",
        "premarket_range_pct",
        "premarket_gap_from_prior_close_pct",
        "premarket_close_vs_prior_close_pct",
        "premarket_close_location_pct",
        "premarket_rvol_20d",
    ]

    missing_pmctx = [
        col
        for col in required_pmctx_cols
        if col not in df.columns
    ]

    if missing_pmctx:

        raise RuntimeError(
            "Missing premarket context columns: "
            + ", ".join(
                missing_pmctx
            )
        )

    # =========================================================================
    # OPTIONAL PRIOR CLOSE PARITY AUDIT
    #
    # A30 already generated prior_rth_close.
    #
    # We independently reconstructed pmctx_prior_rth_close above.
    # If both exist, verify that they agree.
    # =========================================================================

    if (
        "prior_rth_close"
        in df.columns
    ):

        audit = df.loc[
            (
                df[
                    "prior_rth_close"
                ].notna()
            )
            &
            (
                df[
                    "pmctx_prior_rth_close"
                ].notna()
            ),
            [
                "symbol",
                "trade_date",
                "prior_rth_close",
                "pmctx_prior_rth_close",
            ],
        ].copy()

        audit[
            "prior_close_abs_diff"
        ] = (
            audit[
                "prior_rth_close"
            ]
            -
            audit[
                "pmctx_prior_rth_close"
            ]
        ).abs()

        audit[
            "prior_close_match"
        ] = (
            audit[
                "prior_close_abs_diff"
            ]
            <= 0.000001
        )

        audit.to_csv(
            PRIOR_CLOSE_AUDIT_OUTPUT,
            index=False,
        )

        mismatch_n = int(
            (
                ~audit[
                    "prior_close_match"
                ]
            ).sum()
        )

        print()

        print(
            "PRIOR RTH CLOSE PARITY"
        )

        print(
            "-" * 80
        )

        print(
            f"Compared:    "
            f"{len(audit):,}"
        )

        print(
            f"Mismatches:  "
            f"{mismatch_n:,}"
        )

        if mismatch_n:

            print(
                "WARNING: Existing A30 prior_rth_close "
                "and A31 pmctx_prior_rth_close differ."
            )

        else:

            print(
                "Result:      PASS"
            )

    else:

        print()

        print(
            "PRIOR RTH CLOSE PARITY"
        )

        print(
            "-" * 80
        )

        print(
            "Existing prior_rth_close column not "
            "present; audit skipped."
        )

    # =========================================================================
    # TRUE RTH OPENING GAP
    #
    # C1 open versus independently reconstructed prior completed RTH close.
    # =========================================================================

    df[
        "rth_open_gap_pct"
    ] = (
        (
            df[
                "c1_open"
            ]
            /
            df[
                "pmctx_prior_rth_close"
            ]
            - 1.0
        )
        * 100.0
    )

    # =========================================================================
    # DIRECTION-NORMALIZED FEATURES
    # =========================================================================

    direction_features = [
        "rth_open_gap_pct",
        "premarket_gap_from_prior_close_pct",
        "premarket_return_pct",
        "premarket_close_vs_prior_close_pct",
    ]

    for feature in (
        direction_features
    ):

        output_col = (
            f"directional_{feature}"
        )

        df[
            output_col
        ] = df.apply(
            lambda r,
            col=feature:
                directional_value(
                    r[
                        "direction"
                    ],
                    r[
                        col
                    ],
                ),
            axis=1,
        )

        df[
            output_col
            + "_state"
        ] = df[
            output_col
        ].apply(
            aligned_state
        )

    # =========================================================================
    # DIRECTIONAL PREMARKET CLOSE LOCATION
    #
    # Raw:
    #   0   = near premarket low
    #   100 = near premarket high
    #
    # Direction normalized:
    #
    # BULL:
    #   unchanged
    #
    # BEAR:
    #   100 - raw
    #
    # Higher always means nearer the favorable directional extreme.
    # =========================================================================

    df[
        "directional_premarket_close_location_pct"
    ] = np.where(
        df[
            "direction"
        ]
        == "BULL",
        df[
            "premarket_close_location_pct"
        ],
        np.where(
            df[
                "direction"
            ]
            == "BEAR",
            (
                100.0
                -
                df[
                    "premarket_close_location_pct"
                ]
            ),
            np.nan,
        ),
    )

    # =========================================================================
    # GAP + PREMARKET STRUCTURE
    # =========================================================================

    def gap_structure(
        r: pd.Series,
    ) -> str:

        gap = r[
            "directional_rth_open_gap_pct"
        ]

        pm_move = r[
            "directional_premarket_return_pct"
        ]

        if (
            pd.isna(gap)
            or pd.isna(pm_move)
        ):
            return "UNKNOWN"

        if (
            gap > 0
            and pm_move > 0
        ):
            return "GAP_AND_PM_ALIGNED"

        if (
            gap < 0
            and pm_move < 0
        ):
            return "GAP_AND_PM_OPPOSING"

        if (
            gap > 0
            and pm_move < 0
        ):
            return "GAP_ALIGNED_PM_OPPOSING"

        if (
            gap < 0
            and pm_move > 0
        ):
            return "GAP_OPPOSING_PM_ALIGNED"

        return "MIXED_FLAT"

    df[
        "gap_premarket_structure_state"
    ] = df.apply(
        gap_structure,
        axis=1,
    )

    # =========================================================================
    # ABSOLUTE SIZE FEATURES
    # =========================================================================

    df[
        "abs_rth_open_gap_pct"
    ] = (
        df[
            "rth_open_gap_pct"
        ]
        .abs()
    )

    df[
        "abs_premarket_return_pct"
    ] = (
        df[
            "premarket_return_pct"
        ]
        .abs()
    )

    # =========================================================================
    # DISCOVERY-FROZEN q20 / q80
    # =========================================================================

    discovery = df.loc[
        df[
            "research_period"
        ]
        == "DISCOVERY"
    ].copy()

    bucket_features = [
        "premarket_range_pct",
        "premarket_rvol_20d",
        "directional_premarket_close_location_pct",
        "abs_rth_open_gap_pct",
        "abs_premarket_return_pct",
    ]

    threshold_rows = []

    state_features = []

    for feature in (
        bucket_features
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
                    int(
                        len(values)
                    ),
            }
        )

        state_col = (
            feature
            + "_discovery_state"
        )

        df[
            state_col
        ] = df[
            feature
        ].apply(
            lambda x,
            low=q20,
            high=q80:
                discovery_bucket(
                    x,
                    low,
                    high,
                )
        )

        state_features.append(
            state_col
        )

    thresholds = pd.DataFrame(
        threshold_rows
    )

    thresholds.to_csv(
        THRESHOLD_OUTPUT,
        index=False,
    )

    # =========================================================================
    # STRUCTURAL STATES
    # =========================================================================

    state_features.extend(
        [
            "directional_rth_open_gap_pct_state",
            "directional_premarket_gap_from_prior_close_pct_state",
            "directional_premarket_return_pct_state",
            "directional_premarket_close_vs_prior_close_pct_state",
            "gap_premarket_structure_state",
        ]
    )

    # =========================================================================
    # QUARTER
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
        "pre_open",
        "pre_high",
        "pre_low",
        "pre_close",
        "pre_volume",
        "pmctx_prior_rth_close",
        "premarket_return_pct",
        "premarket_range_pct",
        "premarket_gap_from_prior_close_pct",
        "premarket_close_vs_prior_close_pct",
        "premarket_close_location_pct",
        "premarket_rvol_20d",
        "rth_open_gap_pct",
        "abs_rth_open_gap_pct",
        "abs_premarket_return_pct",
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
    # SUMMARY
    # =========================================================================

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

        all_dir = all_dir.rename(
            columns={
                feature:
                    "state"
            }
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

        by_dir = by_dir.rename(
            columns={
                feature:
                    "state"
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
        "directional_rth_open_gap_pct",
        "directional_premarket_gap_from_prior_close_pct",
        "directional_premarket_return_pct",
        "directional_premarket_close_vs_prior_close_pct",
        "directional_premarket_close_location_pct",
        "premarket_range_pct",
        "premarket_rvol_20d",
        "abs_rth_open_gap_pct",
        "abs_premarket_return_pct",
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
                        int(
                            len(x)
                        ),

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
    # QUARTER — PRIMARY GAP/PREMARKET STRUCTURE
    # =========================================================================

    quarter_summary = summarize(
        df,
        [
            "quarter",
            "gap_premarket_structure_state",
        ],
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # INTERACTIONS WITH PRIOR VALIDATED CONTEXT
    # =========================================================================

    possible_interactions = [
        (
            "gap_premarket_structure_state",
            "market_prior_5d_consensus",
        ),

        (
            "gap_premarket_structure_state",
            "positive_candidate_state",
        ),

        (
            "gap_premarket_structure_state",
            "negative_candidate_state",
        ),

        (
            "gap_premarket_structure_state",
            "session_level_clear_state",
        ),

        (
            "premarket_rvol_20d_discovery_state",
            "market_prior_5d_consensus",
        ),

        (
            "premarket_range_pct_discovery_state",
            "positive_candidate_state",
        ),

        (
            "directional_premarket_close_location_pct_discovery_state",
            "session_level_clear_state",
        ),
    ]

    interaction_frames = []

    for (
        pm_feature,
        context_feature,
    ) in possible_interactions:

        if (
            pm_feature
            not in df.columns
            or context_feature
            not in df.columns
        ):
            continue

        x = summarize(
            df,
            [
                "research_period",
                pm_feature,
                context_feature,
            ],
        )

        x[
            "premarket_feature"
        ] = pm_feature

        x[
            "context_feature"
        ] = context_feature

        x = x.rename(
            columns={
                pm_feature:
                    "premarket_state",

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
        "PREMARKET CONTEXT COVERAGE"
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
        "DISCOVERY-FROZEN PREMARKET THRESHOLDS"
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
        "GAP + PREMARKET STRUCTURE — "
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
            == "gap_premarket_structure_state"
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
        "OPENING GAP DIRECTION — "
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
            == "directional_rth_open_gap_pct_state"
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
        "PREMARKET DIRECTION — "
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
            == "directional_premarket_return_pct_state"
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
        "PREMARKET RVOL — "
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
            == "premarket_rvol_20d_discovery_state"
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
        "PREMARKET RANGE — "
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
            == "premarket_range_pct_discovery_state"
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
        "GAP + PREMARKET STRUCTURE — "
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
            == "gap_premarket_structure_state"
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
        "CONTINUOUS PREMARKET METRICS"
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
        "GAP + PREMARKET STRUCTURE — "
        "QUARTER STABILITY"
    )

    print(
        "=" * 80
    )

    print(
        quarter_summary[
            [
                "quarter",
                "gap_premarket_structure_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "quarter",
                "gap_premarket_structure_state",
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
        "PREMARKET × CONTEXT — VALIDATION"
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
                    "premarket_feature",
                    "context_feature",
                    "premarket_state",
                    "context_state",
                    "total_n",
                    "binary_n",
                    "favorable_first_pct",
                    "c3_confirmation_pct",
                ]
            ]
            .sort_values(
                [
                    "premarket_feature",
                    "context_feature",
                    "premarket_state",
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

    print(
        f"Prior close audit: "
        f"{PRIOR_CLOSE_AUDIT_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()