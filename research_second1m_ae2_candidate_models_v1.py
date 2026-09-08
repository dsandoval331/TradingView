from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# A35.2 / R14 — ALTERNATIVE C2 FROZEN CANDIDATE MODEL LADDER V1
# =============================================================================
#
# PURPOSE
# -------
# Evaluate a SMALL, FROZEN set of candidate AE2 decision architectures built
# only from the A34.4 promoted interaction families.
#
# IMPORTANT METHODOLOGY NOTE
# --------------------------
# The A34.4 promotion step already used both discovery and validation evidence.
# Therefore this script is MODEL-DEVELOPMENT evaluation, NOT untouched OOS.
# Any model selected here must be frozen and tested prospectively / on future
# untouched data before production claims are made.
#
# NO new predictor mining occurs in this script.
#
# =============================================================================


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
    / "ae2_interactions_v1"
    / "ae2_interaction_events_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_candidate_models_v1"
)

EVENT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_candidate_model_events_v1.parquet"
)

MODEL_SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_candidate_model_summary_v1.csv"
)

STATE_SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_candidate_model_state_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_candidate_model_direction_v1.csv"
)

TEMPORAL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_candidate_model_temporal_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_candidate_model_quarter_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_candidate_model_symbol_v1.csv"
)

CONCENTRATION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_candidate_model_concentration_v1.csv"
)

OVERLAP_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_candidate_model_overlap_v1.csv"
)

REPORT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_candidate_model_report_v1.txt"
)

EXPECTED_EVENTS = 8307
EXPECTED_SYMBOLS = 112

EXCLUDE_SYMBOLS = {
    "SPY",
    "QQQ",
    "TQQQ",
}


# =============================================================================
# FROZEN PROMOTED INTERACTION FAMILIES
# =============================================================================
#
# POSITIVE FAMILY P1 — STRUCTURAL INDEPENDENCE
# Count as ONE positive family even if both H1A and H1B are true.
#
# H1A:
#   ALL_3_CLEARED + CONSENSUS_OPPOSING
#
# H1B:
#   ALL_3_CLEARED + ALL_3_OPPOSING
#
# NEGATIVE FAMILY N1 — MARKET/RELATIVE CONFLICT
# H5A:
#   MIXED relative_multi_horizon_state + ALL_3_ALIGNED
#
# NEGATIVE FAMILY N2 — NO-CLEARANCE WEAKNESS
# Count as ONE negative family even if both child rules are true:
#
# H4A:
#   exhaustion_state == ONE + NONE_CLEARED
#
# H2A:
#   NONE_CLEARED + RELATIVE_ALIGNED
#
# This grouping prevents correlated double counting.
# =============================================================================


# =============================================================================
# MODEL LADDER
# =============================================================================
#
# M0_BASELINE
#   All AE2 events.
#
# M1_AVOIDANCE_FILTER
#   Take AE2 only when no promoted negative family is present.
#
# M2_POSITIVE_ONLY
#   Take AE2 only when promoted positive family P1 is present.
#
# M3_TRIAGE_PREFERRED
#   Take only PREFERRED state:
#       positive family present AND no negative family.
#
# M4_TRIAGE_STANDARD_PLUS
#   Take PREFERRED + NEUTRAL, reject AVOID.
#   This is functionally similar to M1 but retained as a state-based model view.
#
# The live triage state is:
#   PREFERRED
#   NEUTRAL
#   AVOID
#
# =============================================================================


# =============================================================================
# HELPERS
# =============================================================================

def safe_arrow_patch() -> None:
    """
    Process-local compatibility guard for the pandas/pyarrow environment issue
    already encountered in A34.3/A34.4.
    """

    import pyarrow

    original_unregister = getattr(
        pyarrow,
        "unregister_extension_type",
        None,
    )

    if original_unregister is None:
        return

    def safe_unregister(name: str):
        try:
            return original_unregister(
                name
            )
        except Exception as exc:
            if (
                name == "arrow.py_extension_type"
                and exc.__class__.__name__
                == "ArrowKeyError"
            ):
                return None
            raise

    pyarrow.unregister_extension_type = safe_unregister


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["symbol"] = (
        df["symbol"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["direction"] = (
        df["direction"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["research_period"] = (
        df["research_period"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["trade_date"] = (
        pd.to_datetime(
            df["trade_date"],
            errors="coerce",
        )
        .dt
        .normalize()
    )

    for col in [
        "session_level_clear_state",
        "market_prior_5d_consensus",
        "market_3idx_prior_5d_state",
        "relative_multi_horizon_state",
        "exhaustion_state",
    ]:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
        )

    return df


def summarize_group(x: pd.DataFrame) -> dict:
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

    ff = (
        100.0
        * favorable_n
        / binary_n
        if binary_n
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
            ff,

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
            summarize_group(
                x
            )
        )

        rows.append(
            row
        )

    return pd.DataFrame(
        rows
    )


def retention_pct(
    selected_n: int,
    baseline_n: int,
) -> float:
    if baseline_n == 0:
        return np.nan

    return (
        100.0
        * selected_n
        / baseline_n
    )


# =============================================================================
# BUILD FROZEN FAMILY FLAGS
# =============================================================================

def build_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Positive child flags
    df[
        "p1_h1a_all3_consensus_opposing"
    ] = (
        (
            df[
                "session_level_clear_state"
            ]
            == "ALL_3_CLEARED"
        )
        &
        (
            df[
                "market_prior_5d_consensus"
            ]
            == "CONSENSUS_OPPOSING"
        )
    )

    df[
        "p1_h1b_all3_all3opposing"
    ] = (
        (
            df[
                "session_level_clear_state"
            ]
            == "ALL_3_CLEARED"
        )
        &
        (
            df[
                "market_3idx_prior_5d_state"
            ]
            == "ALL_3_OPPOSING"
        )
    )

    # Positive family collapses both related promoted interactions into one vote.
    df[
        "positive_family_p1"
    ] = (
        df[
            "p1_h1a_all3_consensus_opposing"
        ]
        |
        df[
            "p1_h1b_all3_all3opposing"
        ]
    )

    # Negative family N1
    df[
        "negative_family_n1_market_relative_conflict"
    ] = (
        (
            df[
                "relative_multi_horizon_state"
            ]
            == "MIXED"
        )
        &
        (
            df[
                "market_3idx_prior_5d_state"
            ]
            == "ALL_3_ALIGNED"
        )
    )

    # Negative family N2 children
    df[
        "n2_h4a_one_exhaustion_none_cleared"
    ] = (
        (
            df[
                "exhaustion_state"
            ]
            == "ONE"
        )
        &
        (
            df[
                "session_level_clear_state"
            ]
            == "NONE_CLEARED"
        )
    )

    df[
        "n2_h2a_none_cleared_relative_aligned"
    ] = (
        (
            df[
                "session_level_clear_state"
            ]
            == "NONE_CLEARED"
        )
        &
        (
            df[
                "relative_multi_horizon_state"
            ]
            == "RELATIVE_ALIGNED"
        )
    )

    # Collapse correlated no-clearance negatives into one vote.
    df[
        "negative_family_n2_no_clearance_weakness"
    ] = (
        df[
            "n2_h4a_one_exhaustion_none_cleared"
        ]
        |
        df[
            "n2_h2a_none_cleared_relative_aligned"
        ]
    )

    df[
        "negative_family_any"
    ] = (
        df[
            "negative_family_n1_market_relative_conflict"
        ]
        |
        df[
            "negative_family_n2_no_clearance_weakness"
        ]
    )

    df[
        "negative_family_count"
    ] = (
        df[
            [
                "negative_family_n1_market_relative_conflict",
                "negative_family_n2_no_clearance_weakness",
            ]
        ]
        .astype(int)
        .sum(
            axis=1
        )
    )

    # Frozen score: +1 max positive, -1 per negative family.
    # No double-counting of H1A/H1B or the two N2 children.
    df[
        "candidate_score"
    ] = (
        df[
            "positive_family_p1"
        ]
        .astype(int)
        -
        df[
            "negative_family_count"
        ]
    )

    def triage_state(r: pd.Series) -> str:
        if bool(
            r[
                "negative_family_any"
            ]
        ):
            return "AVOID"

        if bool(
            r[
                "positive_family_p1"
            ]
        ):
            return "PREFERRED"

        return "NEUTRAL"

    df[
        "candidate_triage_state"
    ] = df.apply(
        triage_state,
        axis=1,
    )

    return df


# =============================================================================
# MODEL DEFINITIONS
# =============================================================================

def model_mask(
    df: pd.DataFrame,
    model_id: str,
) -> pd.Series:
    if model_id == "M0_BASELINE":
        return pd.Series(
            True,
            index=df.index,
        )

    if model_id == "M1_AVOIDANCE_FILTER":
        return (
            ~df[
                "negative_family_any"
            ]
        )

    if model_id == "M2_POSITIVE_ONLY":
        return df[
            "positive_family_p1"
        ]

    if model_id == "M3_TRIAGE_PREFERRED":
        return (
            df[
                "candidate_triage_state"
            ]
            == "PREFERRED"
        )

    if model_id == "M4_TRIAGE_STANDARD_PLUS":
        return (
            df[
                "candidate_triage_state"
            ]
            .isin(
                [
                    "PREFERRED",
                    "NEUTRAL",
                ]
            )
        )

    raise ValueError(
        f"Unknown model_id: {model_id}"
    )


MODEL_IDS = [
    "M0_BASELINE",
    "M1_AVOIDANCE_FILTER",
    "M2_POSITIVE_ONLY",
    "M3_TRIAGE_PREFERRED",
    "M4_TRIAGE_STANDARD_PLUS",
]


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
            f"Input not found: {INPUT_PATH}"
        )

    safe_arrow_patch()

    needed_cols = [
        "symbol",
        "trade_date",
        "direction",
        "research_period",
        "outcome",
        "final_mfe_pct",
        "final_mae_pct",
        "session_level_clear_state",
        "market_prior_5d_consensus",
        "market_3idx_prior_5d_state",
        "relative_multi_horizon_state",
        "exhaustion_state",
        "validation_subperiod",
        "quarter",
    ]

    df = pd.read_parquet(
        INPUT_PATH,
        columns=needed_cols,
    )

    df = normalize(
        df
    )

    if len(
        df
    ) != EXPECTED_EVENTS:
        raise RuntimeError(
            f"Expected {EXPECTED_EVENTS:,} events, "
            f"found {len(df):,}."
        )

    if df[
        "symbol"
    ].nunique() != EXPECTED_SYMBOLS:
        raise RuntimeError(
            f"Expected {EXPECTED_SYMBOLS} symbols, "
            f"found {df['symbol'].nunique()}."
        )

    df = build_flags(
        df
    )

    print(
        "=" * 88
    )

    print(
        "A35.2 / R14 - ALTERNATIVE C2 FROZEN CANDIDATE MODEL LADDER V1"
    )

    print(
        "=" * 88
    )

    print(
        f"Events:  {len(df):,}"
    )

    print(
        f"Symbols: {df['symbol'].nunique():,}"
    )

    print()

    print(
        "METHODOLOGY NOTE:"
    )

    print(
        "This is model-development evaluation. "
        "A34.4 already used validation evidence."
    )

    print(
        "These results are NOT untouched out-of-sample validation."
    )

    # -------------------------------------------------------------------------
    # Overlap audit
    # -------------------------------------------------------------------------

    overlap_rows = []

    overlap_specs = [
        (
            "P1_H1A",
            "p1_h1a_all3_consensus_opposing",
        ),
        (
            "P1_H1B",
            "p1_h1b_all3_all3opposing",
        ),
        (
            "P1_FAMILY",
            "positive_family_p1",
        ),
        (
            "N1_MARKET_RELATIVE_CONFLICT",
            "negative_family_n1_market_relative_conflict",
        ),
        (
            "N2_H4A",
            "n2_h4a_one_exhaustion_none_cleared",
        ),
        (
            "N2_H2A",
            "n2_h2a_none_cleared_relative_aligned",
        ),
        (
            "N2_FAMILY",
            "negative_family_n2_no_clearance_weakness",
        ),
        (
            "ANY_NEGATIVE",
            "negative_family_any",
        ),
    ]

    for label, col in overlap_specs:
        x = df.loc[
            df[
                col
            ]
        ]

        stats = summarize_group(
            x
        )

        overlap_rows.append(
            {
                "flag":
                    label,
                **stats,
            }
        )

    # Explicit overlap counts
    overlap_rows.extend(
        [
            {
                "flag":
                    "P1_H1A_AND_H1B",

                **summarize_group(
                    df.loc[
                        df[
                            "p1_h1a_all3_consensus_opposing"
                        ]
                        &
                        df[
                            "p1_h1b_all3_all3opposing"
                        ]
                    ]
                ),
            },
            {
                "flag":
                    "N2_H4A_AND_H2A",

                **summarize_group(
                    df.loc[
                        df[
                            "n2_h4a_one_exhaustion_none_cleared"
                        ]
                        &
                        df[
                            "n2_h2a_none_cleared_relative_aligned"
                        ]
                    ]
                ),
            },
            {
                "flag":
                    "P1_AND_ANY_NEGATIVE",

                **summarize_group(
                    df.loc[
                        df[
                            "positive_family_p1"
                        ]
                        &
                        df[
                            "negative_family_any"
                        ]
                    ]
                ),
            },
        ]
    )

    overlap = pd.DataFrame(
        overlap_rows
    )

    overlap.to_csv(
        OVERLAP_OUTPUT,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Model summary by research period
    # -------------------------------------------------------------------------

    model_rows = []

    for period in [
        "DISCOVERY",
        "VALIDATION",
        "ALL",
    ]:
        if period == "ALL":
            period_df = df
        else:
            period_df = df.loc[
                df[
                    "research_period"
                ]
                == period
            ]

        base_binary_n = summarize_group(
            period_df
        )[
            "binary_n"
        ]

        for model_id in MODEL_IDS:
            x = period_df.loc[
                model_mask(
                    period_df,
                    model_id,
                )
            ]

            stats = summarize_group(
                x
            )

            model_rows.append(
                {
                    "research_period":
                        period,

                    "model_id":
                        model_id,

                    "binary_retention_pct":
                        retention_pct(
                            stats[
                                "binary_n"
                            ],
                            base_binary_n,
                        ),

                    **stats,
                }
            )

    model_summary = pd.DataFrame(
        model_rows
    )

    model_summary.to_csv(
        MODEL_SUMMARY_OUTPUT,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Triage-state summary
    # -------------------------------------------------------------------------

    state_summary = summarize(
        df,
        [
            "research_period",
            "candidate_triage_state",
        ],
    )

    state_summary.to_csv(
        STATE_SUMMARY_OUTPUT,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Directional robustness
    # -------------------------------------------------------------------------

    direction_rows = []

    validation = df.loc[
        df[
            "research_period"
        ]
        == "VALIDATION"
    ]

    for model_id in MODEL_IDS:
        selected = validation.loc[
            model_mask(
                validation,
                model_id,
            )
        ]

        for direction, x in selected.groupby(
            "direction"
        ):
            direction_rows.append(
                {
                    "model_id":
                        model_id,

                    "direction":
                        direction,

                    **summarize_group(
                        x
                    ),
                }
            )

    direction_summary = pd.DataFrame(
        direction_rows
    )

    direction_summary.to_csv(
        DIRECTION_OUTPUT,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Temporal robustness
    # -------------------------------------------------------------------------

    temporal_rows = []

    for model_id in MODEL_IDS:
        selected = validation.loc[
            model_mask(
                validation,
                model_id,
            )
        ]

        for subperiod, x in selected.groupby(
            "validation_subperiod"
        ):
            if subperiod == "NOT_VALIDATION":
                continue

            temporal_rows.append(
                {
                    "model_id":
                        model_id,

                    "validation_subperiod":
                        subperiod,

                    **summarize_group(
                        x
                    ),
                }
            )

    temporal_summary = pd.DataFrame(
        temporal_rows
    )

    temporal_summary.to_csv(
        TEMPORAL_OUTPUT,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Quarter
    # -------------------------------------------------------------------------

    quarter_rows = []

    for model_id in MODEL_IDS:
        selected = df.loc[
            model_mask(
                df,
                model_id,
            )
        ]

        for quarter, x in selected.groupby(
            "quarter"
        ):
            quarter_rows.append(
                {
                    "model_id":
                        model_id,

                    "quarter":
                        quarter,

                    **summarize_group(
                        x
                    ),
                }
            )

    quarter_summary = pd.DataFrame(
        quarter_rows
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Symbol breadth / concentration
    # -------------------------------------------------------------------------

    symbol_rows = []
    concentration_rows = []

    for model_id in MODEL_IDS:
        selected = validation.loc[
            model_mask(
                validation,
                model_id,
            )
        ]

        for symbol, x in selected.groupby(
            "symbol"
        ):
            symbol_rows.append(
                {
                    "model_id":
                        model_id,

                    "symbol":
                        symbol,

                    **summarize_group(
                        x
                    ),
                }
            )

        counts = (
            selected[
                "symbol"
            ]
            .value_counts()
            .sort_values(
                ascending=False
            )
        )

        total_n = len(
            selected
        )

        concentration_rows.append(
            {
                "model_id":
                    model_id,

                "total_n":
                    int(
                        total_n
                    ),

                "symbol_n":
                    int(
                        selected[
                            "symbol"
                        ]
                        .nunique()
                    ),

                "top1_share_pct":
                    (
                        100.0
                        * counts.head(
                            1
                        ).sum()
                        / total_n
                        if total_n
                        else np.nan
                    ),

                "top5_share_pct":
                    (
                        100.0
                        * counts.head(
                            5
                        ).sum()
                        / total_n
                        if total_n
                        else np.nan
                    ),

                "top10_share_pct":
                    (
                        100.0
                        * counts.head(
                            10
                        ).sum()
                        / total_n
                        if total_n
                        else np.nan
                    ),
            }
        )

    symbol_summary = pd.DataFrame(
        symbol_rows
    )

    concentration_summary = pd.DataFrame(
        concentration_rows
    )

    symbol_summary.to_csv(
        SYMBOL_OUTPUT,
        index=False,
    )

    concentration_summary.to_csv(
        CONCENTRATION_OUTPUT,
        index=False,
    )

    # Save event-level frozen model states
    df.to_parquet(
        EVENT_OUTPUT,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Terminal report
    # -------------------------------------------------------------------------

    print()
    print(
        "=" * 88
    )
    print(
        "OVERLAP AUDIT"
    )
    print(
        "=" * 88
    )

    print(
        overlap[
            [
                "flag",
                "total_n",
                "binary_n",
                "favorable_first_pct",
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
        "=" * 88
    )
    print(
        "MODEL LADDER - DISCOVERY / VALIDATION / ALL"
    )
    print(
        "=" * 88
    )

    print(
        model_summary[
            [
                "research_period",
                "model_id",
                "binary_n",
                "binary_retention_pct",
                "favorable_first_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "model_id",
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
        "=" * 88
    )
    print(
        "TRIAGE STATES"
    )
    print(
        "=" * 88
    )

    print(
        state_summary[
            [
                "research_period",
                "candidate_triage_state",
                "binary_n",
                "favorable_first_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "candidate_triage_state",
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
        "=" * 88
    )
    print(
        "VALIDATION DIRECTION"
    )
    print(
        "=" * 88
    )

    print(
        direction_summary[
            [
                "model_id",
                "direction",
                "binary_n",
                "favorable_first_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "model_id",
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
        "=" * 88
    )
    print(
        "VALIDATION OLDER / NEWER"
    )
    print(
        "=" * 88
    )

    print(
        temporal_summary[
            [
                "model_id",
                "validation_subperiod",
                "binary_n",
                "favorable_first_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "model_id",
                "validation_subperiod",
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
        "=" * 88
    )
    print(
        "VALIDATION CONCENTRATION"
    )
    print(
        "=" * 88
    )

    print(
        concentration_summary.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    report_lines = []

    report_lines.append(
        "A35.2 / R14 - ALTERNATIVE C2 FROZEN CANDIDATE MODEL LADDER V1"
    )

    report_lines.append(
        ""
    )

    report_lines.append(
        "METHODOLOGY NOTE:"
    )

    report_lines.append(
        "A34.4 already used discovery + validation evidence. "
        "This is model-development evaluation, not untouched OOS."
    )

    report_lines.append(
        ""
    )

    report_lines.append(
        "MODEL SUMMARY"
    )

    report_lines.append(
        model_summary.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    report_lines.append(
        ""
    )

    report_lines.append(
        "TRIAGE STATES"
    )

    report_lines.append(
        state_summary.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    report_lines.append(
        ""
    )

    report_lines.append(
        "OVERLAP"
    )

    report_lines.append(
        overlap.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    REPORT_OUTPUT.write_text(
        "\n".join(
            report_lines
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=" * 88
    )
    print(
        "OUTPUTS"
    )
    print(
        "=" * 88
    )

    print(
        f"Events:        {EVENT_OUTPUT}"
    )

    print(
        f"Model summary: {MODEL_SUMMARY_OUTPUT}"
    )

    print(
        f"State summary: {STATE_SUMMARY_OUTPUT}"
    )

    print(
        f"Direction:     {DIRECTION_OUTPUT}"
    )

    print(
        f"Temporal:      {TEMPORAL_OUTPUT}"
    )

    print(
        f"Quarter:       {QUARTER_OUTPUT}"
    )

    print(
        f"Symbols:       {SYMBOL_OUTPUT}"
    )

    print(
        f"Concentration: {CONCENTRATION_OUTPUT}"
    )

    print(
        f"Overlap:       {OVERLAP_OUTPUT}"
    )

    print(
        f"Report:        {REPORT_OUTPUT}"
    )

    print()
    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()
