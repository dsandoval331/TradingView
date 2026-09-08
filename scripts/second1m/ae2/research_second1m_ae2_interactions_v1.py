from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow as pa


# =============================================================================
# PYARROW / PANDAS COMPATIBILITY GUARD
# =============================================================================
#
# Some pandas + pyarrow version combinations attempt to unregister the legacy
# Arrow extension type ``arrow.py_extension_type`` even when that type is not
# registered.  In that environment pandas.read_parquet()/to_parquet() can fail
# with:
#
#   pyarrow.lib.ArrowKeyError:
#       No type extension with name arrow.py_extension_type found
#
# The missing legacy registration is harmless for these research parquet files.
# We therefore make unregister_extension_type idempotent for this process only.
# All other Arrow errors continue to propagate normally.
# =============================================================================

_ORIGINAL_ARROW_UNREGISTER_EXTENSION_TYPE = pa.unregister_extension_type


def _safe_arrow_unregister_extension_type(type_name: str):
    try:
        return _ORIGINAL_ARROW_UNREGISTER_EXTENSION_TYPE(type_name)
    except pa.ArrowKeyError:
        if type_name == "arrow.py_extension_type":
            return None
        raise


pa.unregister_extension_type = _safe_arrow_unregister_extension_type


# =============================================================================
# A34.3 / R13 - ALTERNATIVE C2 FROZEN TWO-FACTOR INTERACTION RUNNER V1
# =============================================================================
#
# Purpose
# -------
# Execute ONLY the preregistered two-factor interaction families defined at
# A34.2. This runner is intentionally not an unrestricted interaction miner.
#
# Research protections
# --------------------
# 1. Discovery chooses; validation confirms.
# 2. C2-available information only. No C3+ / post-entry Trade Health inputs.
# 3. Existing categorical states are reused; no new threshold optimization.
# 4. Minimum binary sample gate is applied separately in discovery/validation.
# 5. BULL/BEAR, temporal, symbol-breadth, quarter, and ETF-exclusion checks.
# 6. Negative/non-replicating findings are preserved.
# 7. No three-factor or higher-order combinations.
#
# Primary outcome
# ---------------
# FAVORABLE_FIRST vs ADVERSE_FIRST using the existing frozen ±0.50% outcome.
#
# =============================================================================


# =============================================================================
# CONFIG
# =============================================================================

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

# The calendar feature parquet is the current broadest pre-entry feature table.
MASTER_PATH = (
    RESEARCH_ROOT
    / "ae2_calendar_v1"
    / "ae2_calendar_features_v1.parquet"
)

# Optional H4 source. This file was created during A24 robustness research.
# If it is missing, H4 is explicitly marked SKIPPED rather than fabricated.
EXHAUSTION_PATH = (
    RESEARCH_ROOT
    / "ae2_robustness_v1"
    / "ae2_structural_states_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_interactions_v1"
)

EVENTS_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_events_v1.parquet"
)

PAIR_INVENTORY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_pair_inventory_v1.csv"
)

ALL_STATES_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_all_states_v1.csv"
)

PAIRED_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_discovery_validation_v1.csv"
)

REPLICATING_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_replicating_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_direction_v1.csv"
)

TEMPORAL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_temporal_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_quarter_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_symbol_v1.csv"
)

CONCENTRATION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_concentration_v1.csv"
)

ETF_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_etf_sensitivity_v1.csv"
)

TOP_DISCOVERY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_top_discovery_v1.csv"
)

MIN_DISCOVERY_BINARY_N = 75
MIN_VALIDATION_BINARY_N = 75

EXPECTED_EVENTS = 8307
EXPECTED_SYMBOLS = 112

EXCLUDE_SYMBOLS = {
    "SPY",
    "QQQ",
    "TQQQ",
}

# Stable event identity shared by the feature branches.
EVENT_KEY_CANDIDATES = [
    "symbol",
    "trade_date",
    "direction",
    "architecture",
    "decision_candle",
    "entry_timestamp",
]


# =============================================================================
# FROZEN PREREGISTERED INTERACTION MATRIX
# =============================================================================
#
# Each tuple:
#   (hypothesis_id, hypothesis_label, feature_a, feature_b)
#
# H4 is conditional on the existing "exhaustion_state" column being available
# from ae2_structural_states_v1.parquet.
#
# IMPORTANT:
# The script enumerates states only INSIDE these preregistered feature pairs.
# It does not search arbitrary feature combinations.
# =============================================================================

FROZEN_INTERACTION_PAIRS = [
    # H1 — Structural clearance × market relationship
    (
        "H1A",
        "STRUCTURE_CLEARANCE_X_MARKET_5D_CONSENSUS",
        "session_level_clear_state",
        "market_prior_5d_consensus",
    ),
    (
        "H1B",
        "STRUCTURE_CLEARANCE_X_3IDX_5D_REGIME",
        "session_level_clear_state",
        "market_3idx_prior_5d_state",
    ),

    # H2 — Session-level accomplishment × relative strength
    (
        "H2A",
        "STRUCTURE_CLEARANCE_X_RELATIVE_MULTI_HORIZON",
        "session_level_clear_state",
        "relative_multi_horizon_state",
    ),
    (
        "H2B",
        "STRUCTURE_CLEARANCE_X_RELATIVE_STRENGTH_5D",
        "session_level_clear_state",
        "directional_stock_vs_market_avg_5d_pct__state",
    ),

    # H3 — Premarket participation × structural difficulty
    (
        "H3A",
        "PREMARKET_RVOL_X_C2_BREAK_COUNT",
        "premarket_rvol_20d_discovery_state",
        "c2_break_count_state",
    ),
    (
        "H3B",
        "PREMARKET_RVOL_X_LEVEL_CLUSTER",
        "premarket_rvol_20d_discovery_state",
        "relevant_level_cluster_state",
    ),

    # H4 — C2 exhaustion × structural accomplishment
    (
        "H4A",
        "C2_EXHAUSTION_X_STRUCTURE_CLEARANCE",
        "exhaustion_state",
        "session_level_clear_state",
    ),

    # H5 — Relative strength × market regime
    (
        "H5A",
        "RELATIVE_MULTI_HORIZON_X_3IDX_5D_REGIME",
        "relative_multi_horizon_state",
        "market_3idx_prior_5d_state",
    ),
    (
        "H5B",
        "RELATIVE_STRENGTH_5D_X_3IDX_5D_REGIME",
        "directional_stock_vs_market_avg_5d_pct__state",
        "market_3idx_prior_5d_state",
    ),
]


# =============================================================================
# HELPERS
# =============================================================================

def normalize_event_fields(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "symbol" in df.columns:
        df["symbol"] = (
            df["symbol"]
            .astype(str)
            .str.upper()
            .str.strip()
        )

    if "direction" in df.columns:
        df["direction"] = (
            df["direction"]
            .astype(str)
            .str.upper()
            .str.strip()
        )

    if "trade_date" in df.columns:
        df["trade_date"] = (
            pd.to_datetime(
                df["trade_date"],
                errors="coerce",
            )
            .dt
            .normalize()
        )

    if "entry_timestamp" in df.columns:
        df["entry_timestamp"] = pd.to_datetime(
            df["entry_timestamp"],
            errors="coerce",
            utc=True,
        )

    return df


def available_event_keys(df: pd.DataFrame) -> list[str]:
    return [
        col
        for col in EVENT_KEY_CANDIDATES
        if col in df.columns
    ]


def require_columns(
    df: pd.DataFrame,
    columns: Iterable[str],
    label: str,
) -> None:
    missing = [
        col
        for col in columns
        if col not in df.columns
    ]

    if missing:
        raise RuntimeError(
            f"{label} missing required columns: "
            + ", ".join(missing)
        )


def validate_unique_event_keys(
    df: pd.DataFrame,
    keys: list[str],
    label: str,
) -> None:
    if not keys:
        raise RuntimeError(
            f"{label}: no event keys are available."
        )

    duplicate_n = int(
        df.duplicated(
            subset=keys,
            keep=False,
        ).sum()
    )

    if duplicate_n:
        dupes = (
            df.loc[
                df.duplicated(
                    subset=keys,
                    keep=False,
                ),
                keys,
            ]
            .head(20)
        )

        raise RuntimeError(
            f"{label}: found {duplicate_n:,} rows "
            f"in duplicate event keys.\n"
            f"Example duplicates:\n{dupes.to_string(index=False)}"
        )


def favorable_first_stats(
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


def safe_delta(
    value: float,
    baseline: float,
) -> float:
    if (
        pd.isna(value)
        or pd.isna(baseline)
    ):
        return np.nan

    return float(
        value
        - baseline
    )


def state_text(value) -> str:
    if pd.isna(value):
        return "<MISSING>"

    return str(value)


def summarize_feature_state(
    df: pd.DataFrame,
    feature: str,
    state,
    period: str,
) -> dict:
    x = df.loc[
        (
            df["research_period"]
            == period
        )
        &
        (
            df[feature]
            .map(state_text)
            == state_text(state)
        )
    ]

    if x.empty:
        return {
            "binary_n": 0,
            "favorable_first_pct": np.nan,
        }

    stats = favorable_first_stats(x)

    return {
        "binary_n":
            stats["binary_n"],

        "favorable_first_pct":
            stats["favorable_first_pct"],
    }


def build_validation_subperiod(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    df = df.copy()

    validation_dates = sorted(
        df.loc[
            df["research_period"]
            == "VALIDATION",
            "trade_date",
        ]
        .dropna()
        .unique()
    )

    if not validation_dates:
        raise RuntimeError(
            "Validation population is empty."
        )

    midpoint = pd.Timestamp(
        validation_dates[
            len(validation_dates)
            // 2
        ]
    )

    df["validation_subperiod"] = "NOT_VALIDATION"

    older_mask = (
        (
            df["research_period"]
            == "VALIDATION"
        )
        &
        (
            df["trade_date"]
            < midpoint
        )
    )

    newer_mask = (
        (
            df["research_period"]
            == "VALIDATION"
        )
        &
        (
            df["trade_date"]
            >= midpoint
        )
    )

    df.loc[
        older_mask,
        "validation_subperiod",
    ] = "VALIDATION_OLDER"

    df.loc[
        newer_mask,
        "validation_subperiod",
    ] = "VALIDATION_NEWER"

    return df, midpoint


# =============================================================================
# LOAD MASTER + OPTIONAL H4
# =============================================================================

def load_master() -> tuple[pd.DataFrame, list[dict]]:
    if not MASTER_PATH.exists():
        raise FileNotFoundError(
            f"Master feature file not found: {MASTER_PATH}"
        )

    print(
        f"Master: {MASTER_PATH}"
    )

    # Determine only the columns required for the frozen interaction matrix
    # plus outcome/robustness metadata.
    required_master_cols = {
        "symbol",
        "trade_date",
        "direction",
        "architecture",
        "decision_candle",
        "entry_timestamp",
        "outcome",
        "final_mfe_pct",
        "final_mae_pct",
        "research_period",
    }

    for _, _, feature_a, feature_b in FROZEN_INTERACTION_PAIRS:
        if feature_a != "exhaustion_state":
            required_master_cols.add(feature_a)

        if feature_b != "exhaustion_state":
            required_master_cols.add(feature_b)

    # Read schema first so absent optional H4 does not break the master load.
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(
        MASTER_PATH
    )

    master_schema = set(
        pf.schema_arrow.names
    )

    actual_master_cols = sorted(
        col
        for col in required_master_cols
        if col in master_schema
    )

    missing_nonoptional = sorted(
        col
        for col in required_master_cols
        if (
            col not in master_schema
            and col != "exhaustion_state"
        )
    )

    if missing_nonoptional:
        raise RuntimeError(
            "Master parquet is missing preregistered columns: "
            + ", ".join(
                missing_nonoptional
            )
        )

    df = pd.read_parquet(
        MASTER_PATH,
        columns=actual_master_cols,
    )

    df = normalize_event_fields(
        df
    )

    keys = available_event_keys(
        df
    )

    validate_unique_event_keys(
        df,
        keys,
        "MASTER",
    )

    if len(df) != EXPECTED_EVENTS:
        raise RuntimeError(
            f"MASTER expected {EXPECTED_EVENTS:,} rows, "
            f"found {len(df):,}."
        )

    if df["symbol"].nunique() != EXPECTED_SYMBOLS:
        raise RuntimeError(
            f"MASTER expected {EXPECTED_SYMBOLS} symbols, "
            f"found {df['symbol'].nunique()}."
        )

    pair_inventory_notes = []

    # -------------------------------------------------------------------------
    # Optional H4 exhaustion-state join.
    # -------------------------------------------------------------------------

    if EXHAUSTION_PATH.exists():
        ex_pf = pq.ParquetFile(
            EXHAUSTION_PATH
        )

        ex_schema = set(
            ex_pf.schema_arrow.names
        )

        if "exhaustion_state" in ex_schema:
            ex_keys = [
                key
                for key in keys
                if key in ex_schema
            ]

            if len(ex_keys) < 3:
                pair_inventory_notes.append(
                    {
                        "hypothesis_id": "H4A",
                        "status": "SKIPPED",
                        "note":
                            "Exhaustion file exists but insufficient "
                            "shared event keys for safe join.",
                    }
                )
            else:
                ex = pd.read_parquet(
                    EXHAUSTION_PATH,
                    columns=ex_keys + [
                        "exhaustion_state"
                    ],
                )

                ex = normalize_event_fields(
                    ex
                )

                validate_unique_event_keys(
                    ex,
                    ex_keys,
                    "EXHAUSTION",
                )

                before_n = len(df)

                df = df.merge(
                    ex,
                    on=ex_keys,
                    how="left",
                    validate="one_to_one",
                )

                if len(df) != before_n:
                    raise RuntimeError(
                        "H4 exhaustion join changed master row count."
                    )

                missing_exhaustion_n = int(
                    df["exhaustion_state"]
                    .isna()
                    .sum()
                )

                pair_inventory_notes.append(
                    {
                        "hypothesis_id": "H4A",
                        "status": "AVAILABLE",
                        "note":
                            f"Joined exhaustion_state from "
                            f"{EXHAUSTION_PATH.name}; "
                            f"missing={missing_exhaustion_n:,}.",
                    }
                )
        else:
            pair_inventory_notes.append(
                {
                    "hypothesis_id": "H4A",
                    "status": "SKIPPED",
                    "note":
                        "Exhaustion parquet exists but does not contain "
                        "exhaustion_state.",
                }
            )
    else:
        pair_inventory_notes.append(
            {
                "hypothesis_id": "H4A",
                "status": "SKIPPED",
                "note":
                    f"Optional exhaustion file not found: "
                    f"{EXHAUSTION_PATH}",
            }
        )

    return df, pair_inventory_notes


# =============================================================================
# PAIR INVENTORY
# =============================================================================

def build_pair_inventory(
    df: pd.DataFrame,
    notes: list[dict],
) -> pd.DataFrame:
    note_lookup = {
        row["hypothesis_id"]: row
        for row in notes
    }

    rows = []

    for (
        hypothesis_id,
        hypothesis_label,
        feature_a,
        feature_b,
    ) in FROZEN_INTERACTION_PAIRS:

        a_exists = (
            feature_a
            in df.columns
        )

        b_exists = (
            feature_b
            in df.columns
        )

        status = (
            "AVAILABLE"
            if (
                a_exists
                and b_exists
            )
            else "SKIPPED"
        )

        note = ""

        if hypothesis_id in note_lookup:
            note = note_lookup[
                hypothesis_id
            ]["note"]

        if not a_exists:
            note = (
                note
                + (
                    "; "
                    if note
                    else ""
                )
                + f"Missing feature_a={feature_a}"
            )

        if not b_exists:
            note = (
                note
                + (
                    "; "
                    if note
                    else ""
                )
                + f"Missing feature_b={feature_b}"
            )

        rows.append(
            {
                "hypothesis_id":
                    hypothesis_id,

                "hypothesis_label":
                    hypothesis_label,

                "feature_a":
                    feature_a,

                "feature_b":
                    feature_b,

                "feature_a_available":
                    a_exists,

                "feature_b_available":
                    b_exists,

                "status":
                    status,

                "note":
                    note,
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# ALL INTERACTION STATES
# =============================================================================

def build_all_interaction_states(
    df: pd.DataFrame,
    pair_inventory: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    baseline_lookup = {}

    for period in [
        "DISCOVERY",
        "VALIDATION",
    ]:
        base = df.loc[
            df["research_period"]
            == period
        ]

        baseline_lookup[
            period
        ] = favorable_first_stats(
            base
        )

    available_pairs = pair_inventory.loc[
        pair_inventory["status"]
        == "AVAILABLE"
    ]

    for _, pair in available_pairs.iterrows():
        hypothesis_id = pair[
            "hypothesis_id"
        ]

        hypothesis_label = pair[
            "hypothesis_label"
        ]

        feature_a = pair[
            "feature_a"
        ]

        feature_b = pair[
            "feature_b"
        ]

        # Convert states to normalized strings so NaN is retained explicitly.
        pair_df = df.copy()

        pair_df[
            "_state_a"
        ] = pair_df[
            feature_a
        ].map(
            state_text
        )

        pair_df[
            "_state_b"
        ] = pair_df[
            feature_b
        ].map(
            state_text
        )

        for (
            period,
            state_a,
            state_b,
        ), x in pair_df.groupby(
            [
                "research_period",
                "_state_a",
                "_state_b",
            ],
            dropna=False,
        ):
            stats = favorable_first_stats(
                x
            )

            baseline_ff = baseline_lookup[
                period
            ][
                "favorable_first_pct"
            ]

            parent_a = summarize_feature_state(
                pair_df,
                feature_a,
                state_a,
                period,
            )

            parent_b = summarize_feature_state(
                pair_df,
                feature_b,
                state_b,
                period,
            )

            rows.append(
                {
                    "hypothesis_id":
                        hypothesis_id,

                    "hypothesis_label":
                        hypothesis_label,

                    "feature_a":
                        feature_a,

                    "state_a":
                        state_a,

                    "feature_b":
                        feature_b,

                    "state_b":
                        state_b,

                    "research_period":
                        period,

                    "baseline_favorable_first_pct":
                        baseline_ff,

                    "feature_a_binary_n":
                        parent_a[
                            "binary_n"
                        ],

                    "feature_a_favorable_first_pct":
                        parent_a[
                            "favorable_first_pct"
                        ],

                    "feature_b_binary_n":
                        parent_b[
                            "binary_n"
                        ],

                    "feature_b_favorable_first_pct":
                        parent_b[
                            "favorable_first_pct"
                        ],

                    "lift_vs_baseline_pp":
                        safe_delta(
                            stats[
                                "favorable_first_pct"
                            ],
                            baseline_ff,
                        ),

                    "incremental_vs_feature_a_pp":
                        safe_delta(
                            stats[
                                "favorable_first_pct"
                            ],
                            parent_a[
                                "favorable_first_pct"
                            ],
                        ),

                    "incremental_vs_feature_b_pp":
                        safe_delta(
                            stats[
                                "favorable_first_pct"
                            ],
                            parent_b[
                                "favorable_first_pct"
                            ],
                        ),

                    **stats,
                }
            )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# DISCOVERY -> VALIDATION PAIRING
# =============================================================================

def pair_discovery_validation(
    all_states: pd.DataFrame,
) -> pd.DataFrame:
    keys = [
        "hypothesis_id",
        "hypothesis_label",
        "feature_a",
        "state_a",
        "feature_b",
        "state_b",
    ]

    discovery = all_states.loc[
        all_states[
            "research_period"
        ]
        == "DISCOVERY"
    ].copy()

    validation = all_states.loc[
        all_states[
            "research_period"
        ]
        == "VALIDATION"
    ].copy()

    paired = discovery.merge(
        validation,
        on=keys,
        how="inner",
        suffixes=(
            "_discovery",
            "_validation",
        ),
    )

    paired[
        "passes_sample_gate"
    ] = (
        (
            paired[
                "binary_n_discovery"
            ]
            >= MIN_DISCOVERY_BINARY_N
        )
        &
        (
            paired[
                "binary_n_validation"
            ]
            >= MIN_VALIDATION_BINARY_N
        )
    )

    paired[
        "discovery_effect_sign"
    ] = np.sign(
        paired[
            "lift_vs_baseline_pp_discovery"
        ]
    )

    paired[
        "validation_effect_sign"
    ] = np.sign(
        paired[
            "lift_vs_baseline_pp_validation"
        ]
    )

    paired[
        "same_effect_direction"
    ] = (
        paired[
            "discovery_effect_sign"
        ]
        ==
        paired[
            "validation_effect_sign"
        ]
    )

    paired[
        "effect_type"
    ] = np.where(
        (
            paired[
                "lift_vs_baseline_pp_discovery"
            ]
            > 0
        )
        &
        (
            paired[
                "lift_vs_baseline_pp_validation"
            ]
            > 0
        ),
        "POSITIVE_REPLICATING",
        np.where(
            (
                paired[
                    "lift_vs_baseline_pp_discovery"
                ]
                < 0
            )
            &
            (
                paired[
                    "lift_vs_baseline_pp_validation"
                ]
                < 0
            ),
            "NEGATIVE_REPLICATING",
            "NON_REPLICATING",
        ),
    )

    paired[
        "validation_minus_discovery_lift_pp"
    ] = (
        paired[
            "lift_vs_baseline_pp_validation"
        ]
        -
        paired[
            "lift_vs_baseline_pp_discovery"
        ]
    )

    # Discovery-only ranking. Validation is NOT used to choose the rank.
    paired[
        "discovery_abs_lift_pp"
    ] = (
        paired[
            "lift_vs_baseline_pp_discovery"
        ]
        .abs()
    )

    paired[
        "discovery_rank_within_hypothesis"
    ] = (
        paired.groupby(
            "hypothesis_id"
        )[
            "discovery_abs_lift_pp"
        ]
        .rank(
            method="dense",
            ascending=False,
        )
    )

    return paired


# =============================================================================
# ROBUSTNESS FOR REPLICATING STATES
# =============================================================================

def candidate_mask(
    df: pd.DataFrame,
    row: pd.Series,
) -> pd.Series:
    feature_a = row[
        "feature_a"
    ]

    feature_b = row[
        "feature_b"
    ]

    state_a = row[
        "state_a"
    ]

    state_b = row[
        "state_b"
    ]

    return (
        (
            df[
                feature_a
            ]
            .map(
                state_text
            )
            == state_text(
                state_a
            )
        )
        &
        (
            df[
                feature_b
            ]
            .map(
                state_text
            )
            == state_text(
                state_b
            )
        )
    )


def build_direction_summary(
    df: pd.DataFrame,
    replicating: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for _, candidate in replicating.iterrows():
        mask = candidate_mask(
            df,
            candidate,
        )

        x0 = df.loc[
            mask
            &
            (
                df[
                    "research_period"
                ]
                == "VALIDATION"
            )
        ]

        for direction, x in x0.groupby(
            "direction"
        ):
            rows.append(
                {
                    "hypothesis_id":
                        candidate[
                            "hypothesis_id"
                        ],

                    "feature_a":
                        candidate[
                            "feature_a"
                        ],

                    "state_a":
                        candidate[
                            "state_a"
                        ],

                    "feature_b":
                        candidate[
                            "feature_b"
                        ],

                    "state_b":
                        candidate[
                            "state_b"
                        ],

                    "effect_type":
                        candidate[
                            "effect_type"
                        ],

                    "direction":
                        direction,

                    **favorable_first_stats(
                        x
                    ),
                }
            )

    return pd.DataFrame(
        rows
    )


def build_temporal_summary(
    df: pd.DataFrame,
    replicating: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for _, candidate in replicating.iterrows():
        mask = candidate_mask(
            df,
            candidate,
        )

        x0 = df.loc[
            mask
            &
            (
                df[
                    "research_period"
                ]
                == "VALIDATION"
            )
        ]

        for subperiod, x in x0.groupby(
            "validation_subperiod"
        ):
            if subperiod == "NOT_VALIDATION":
                continue

            rows.append(
                {
                    "hypothesis_id":
                        candidate[
                            "hypothesis_id"
                        ],

                    "feature_a":
                        candidate[
                            "feature_a"
                        ],

                    "state_a":
                        candidate[
                            "state_a"
                        ],

                    "feature_b":
                        candidate[
                            "feature_b"
                        ],

                    "state_b":
                        candidate[
                            "state_b"
                        ],

                    "effect_type":
                        candidate[
                            "effect_type"
                        ],

                    "validation_subperiod":
                        subperiod,

                    **favorable_first_stats(
                        x
                    ),
                }
            )

    return pd.DataFrame(
        rows
    )


def build_quarter_summary(
    df: pd.DataFrame,
    replicating: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for _, candidate in replicating.iterrows():
        mask = candidate_mask(
            df,
            candidate,
        )

        x0 = df.loc[
            mask
        ]

        for quarter, x in x0.groupby(
            "quarter"
        ):
            rows.append(
                {
                    "hypothesis_id":
                        candidate[
                            "hypothesis_id"
                        ],

                    "feature_a":
                        candidate[
                            "feature_a"
                        ],

                    "state_a":
                        candidate[
                            "state_a"
                        ],

                    "feature_b":
                        candidate[
                            "feature_b"
                        ],

                    "state_b":
                        candidate[
                            "state_b"
                        ],

                    "effect_type":
                        candidate[
                            "effect_type"
                        ],

                    "quarter":
                        quarter,

                    **favorable_first_stats(
                        x
                    ),
                }
            )

    return pd.DataFrame(
        rows
    )


def build_symbol_and_concentration(
    df: pd.DataFrame,
    replicating: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    symbol_rows = []
    concentration_rows = []

    for _, candidate in replicating.iterrows():
        mask = candidate_mask(
            df,
            candidate,
        )

        x0 = df.loc[
            mask
            &
            (
                df[
                    "research_period"
                ]
                == "VALIDATION"
            )
        ]

        if x0.empty:
            continue

        for symbol, x in x0.groupby(
            "symbol"
        ):
            symbol_rows.append(
                {
                    "hypothesis_id":
                        candidate[
                            "hypothesis_id"
                        ],

                    "feature_a":
                        candidate[
                            "feature_a"
                        ],

                    "state_a":
                        candidate[
                            "state_a"
                        ],

                    "feature_b":
                        candidate[
                            "feature_b"
                        ],

                    "state_b":
                        candidate[
                            "state_b"
                        ],

                    "effect_type":
                        candidate[
                            "effect_type"
                        ],

                    "symbol":
                        symbol,

                    **favorable_first_stats(
                        x
                    ),
                }
            )

        counts = (
            x0[
                "symbol"
            ]
            .value_counts()
            .sort_values(
                ascending=False
            )
        )

        total_n = len(
            x0
        )

        top1_n = int(
            counts.head(
                1
            ).sum()
        )

        top5_n = int(
            counts.head(
                5
            ).sum()
        )

        top10_n = int(
            counts.head(
                10
            ).sum()
        )

        concentration_rows.append(
            {
                "hypothesis_id":
                    candidate[
                        "hypothesis_id"
                    ],

                "feature_a":
                    candidate[
                        "feature_a"
                    ],

                "state_a":
                    candidate[
                        "state_a"
                    ],

                "feature_b":
                    candidate[
                        "feature_b"
                    ],

                "state_b":
                    candidate[
                        "state_b"
                    ],

                "effect_type":
                    candidate[
                        "effect_type"
                    ],

                "total_n":
                    int(
                        total_n
                    ),

                "symbol_n":
                    int(
                        x0[
                            "symbol"
                        ]
                        .nunique()
                    ),

                "top1_share_pct":
                    (
                        100.0
                        * top1_n
                        / total_n
                    ),

                "top5_share_pct":
                    (
                        100.0
                        * top5_n
                        / total_n
                    ),

                "top10_share_pct":
                    (
                        100.0
                        * top10_n
                        / total_n
                    ),
            }
        )

    return (
        pd.DataFrame(
            symbol_rows
        ),
        pd.DataFrame(
            concentration_rows
        ),
    )


def build_etf_sensitivity(
    df: pd.DataFrame,
    replicating: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for _, candidate in replicating.iterrows():
        mask = candidate_mask(
            df,
            candidate,
        )

        base = df.loc[
            mask
            &
            (
                df[
                    "research_period"
                ]
                == "VALIDATION"
            )
        ]

        for label, x in [
            (
                "BASE",
                base,
            ),
            (
                "EXCLUDE_SPY_QQQ_TQQQ",
                base.loc[
                    ~base[
                        "symbol"
                    ].isin(
                        EXCLUDE_SYMBOLS
                    )
                ],
            ),
        ]:
            if x.empty:
                continue

            rows.append(
                {
                    "hypothesis_id":
                        candidate[
                            "hypothesis_id"
                        ],

                    "feature_a":
                        candidate[
                            "feature_a"
                        ],

                    "state_a":
                        candidate[
                            "state_a"
                        ],

                    "feature_b":
                        candidate[
                            "feature_b"
                        ],

                    "state_b":
                        candidate[
                            "state_b"
                        ],

                    "effect_type":
                        candidate[
                            "effect_type"
                        ],

                    "sensitivity":
                        label,

                    **favorable_first_stats(
                        x
                    ),
                }
            )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "=" * 88
    )

    print(
        "A34.3 / R13 - ALTERNATIVE C2 FROZEN TWO-FACTOR INTERACTION RUNNER V1"
    )

    print(
        "=" * 88
    )

    df, notes = load_master()

    require_columns(
        df,
        [
            "symbol",
            "trade_date",
            "direction",
            "outcome",
            "final_mfe_pct",
            "final_mae_pct",
            "research_period",
        ],
        "MASTER",
    )

    df[
        "research_period"
    ] = (
        df[
            "research_period"
        ]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    # Build quarter and validation-half metadata locally so it is consistent.
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

    df, validation_midpoint = build_validation_subperiod(
        df
    )

    # -------------------------------------------------------------------------
    # Population audit
    # -------------------------------------------------------------------------

    print()
    print(
        "=" * 88
    )
    print(
        "POPULATION AUDIT"
    )
    print(
        "=" * 88
    )

    print(
        f"Rows:                {len(df):,}"
    )

    print(
        f"Symbols:             {df['symbol'].nunique():,}"
    )

    print(
        f"Discovery rows:      "
        f"{(df['research_period'] == 'DISCOVERY').sum():,}"
    )

    print(
        f"Validation rows:     "
        f"{(df['research_period'] == 'VALIDATION').sum():,}"
    )

    print(
        f"Validation midpoint: {validation_midpoint.date()}"
    )

    for period in [
        "DISCOVERY",
        "VALIDATION",
    ]:
        x = df.loc[
            df[
                "research_period"
            ]
            == period
        ]

        stats = favorable_first_stats(
            x
        )

        print(
            f"{period:<10} "
            f"binary={stats['binary_n']:,} "
            f"FF={stats['favorable_first_pct']:.2f}%"
        )

    # -------------------------------------------------------------------------
    # Pair inventory
    # -------------------------------------------------------------------------

    pair_inventory = build_pair_inventory(
        df,
        notes,
    )

    pair_inventory.to_csv(
        PAIR_INVENTORY_OUTPUT,
        index=False,
    )

    print()
    print(
        "=" * 88
    )
    print(
        "FROZEN INTERACTION PAIR INVENTORY"
    )
    print(
        "=" * 88
    )

    print(
        pair_inventory[
            [
                "hypothesis_id",
                "hypothesis_label",
                "feature_a",
                "feature_b",
                "status",
                "note",
            ]
        ]
        .to_string(
            index=False
        )
    )

    # -------------------------------------------------------------------------
    # All state combinations inside frozen pairs
    # -------------------------------------------------------------------------

    all_states = build_all_interaction_states(
        df,
        pair_inventory,
    )

    all_states.to_csv(
        ALL_STATES_OUTPUT,
        index=False,
    )

    paired = pair_discovery_validation(
        all_states
    )

    paired.to_csv(
        PAIRED_OUTPUT,
        index=False,
    )

    # Discovery-selected view. This is for audit/ranking only.
    top_discovery = (
        paired.loc[
            paired[
                "passes_sample_gate"
            ]
        ]
        .sort_values(
            [
                "hypothesis_id",
                "discovery_rank_within_hypothesis",
                "binary_n_discovery",
            ],
            ascending=[
                True,
                True,
                False,
            ],
        )
        .copy()
    )

    top_discovery.to_csv(
        TOP_DISCOVERY_OUTPUT,
        index=False,
    )

    # Replication gate:
    #   sample gate in BOTH periods
    #   same sign vs AE2 period baseline
    replicating = paired.loc[
        (
            paired[
                "passes_sample_gate"
            ]
        )
        &
        (
            paired[
                "same_effect_direction"
            ]
        )
        &
        (
            paired[
                "effect_type"
            ]
            != "NON_REPLICATING"
        )
    ].copy()

    # IMPORTANT: order by discovery magnitude, not validation magnitude.
    replicating = replicating.sort_values(
        [
            "hypothesis_id",
            "discovery_abs_lift_pp",
            "binary_n_discovery",
        ],
        ascending=[
            True,
            False,
            False,
        ],
    )

    replicating.to_csv(
        REPLICATING_OUTPUT,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Robustness
    # -------------------------------------------------------------------------

    if replicating.empty:
        direction_summary = pd.DataFrame()
        temporal_summary = pd.DataFrame()
        quarter_summary = pd.DataFrame()
        symbol_summary = pd.DataFrame()
        concentration_summary = pd.DataFrame()
        etf_summary = pd.DataFrame()

    else:
        direction_summary = build_direction_summary(
            df,
            replicating,
        )

        temporal_summary = build_temporal_summary(
            df,
            replicating,
        )

        quarter_summary = build_quarter_summary(
            df,
            replicating,
        )

        (
            symbol_summary,
            concentration_summary,
        ) = build_symbol_and_concentration(
            df,
            replicating,
        )

        etf_summary = build_etf_sensitivity(
            df,
            replicating,
        )

    direction_summary.to_csv(
        DIRECTION_OUTPUT,
        index=False,
    )

    temporal_summary.to_csv(
        TEMPORAL_OUTPUT,
        index=False,
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    symbol_summary.to_csv(
        SYMBOL_OUTPUT,
        index=False,
    )

    concentration_summary.to_csv(
        CONCENTRATION_OUTPUT,
        index=False,
    )

    etf_summary.to_csv(
        ETF_OUTPUT,
        index=False,
    )

    # Save the narrow combined dataset used for this research stage.
    df.to_parquet(
        EVENTS_OUTPUT,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Report
    # -------------------------------------------------------------------------

    print()
    print(
        "=" * 88
    )
    print(
        "DISCOVERY-RANKED SAMPLE-GATED STATES"
    )
    print(
        "=" * 88
    )

    if top_discovery.empty:
        print(
            "No interaction states passed the sample gate."
        )
    else:
        display = top_discovery[
            [
                "hypothesis_id",
                "state_a",
                "state_b",
                "binary_n_discovery",
                "favorable_first_pct_discovery",
                "lift_vs_baseline_pp_discovery",
                "binary_n_validation",
                "favorable_first_pct_validation",
                "lift_vs_baseline_pp_validation",
                "same_effect_direction",
                "effect_type",
                "discovery_rank_within_hypothesis",
            ]
        ].copy()

        print(
            display.to_string(
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
        "REPLICATING INTERACTION STATES"
    )
    print(
        "=" * 88
    )

    if replicating.empty:
        print(
            "No states passed both sample and replication gates."
        )
    else:
        print(
            replicating[
                [
                    "hypothesis_id",
                    "state_a",
                    "state_b",
                    "binary_n_discovery",
                    "favorable_first_pct_discovery",
                    "lift_vs_baseline_pp_discovery",
                    "incremental_vs_feature_a_pp_discovery",
                    "incremental_vs_feature_b_pp_discovery",
                    "binary_n_validation",
                    "favorable_first_pct_validation",
                    "lift_vs_baseline_pp_validation",
                    "incremental_vs_feature_a_pp_validation",
                    "incremental_vs_feature_b_pp_validation",
                    "effect_type",
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
        "REPLICATING STATES — VALIDATION DIRECTION"
    )
    print(
        "=" * 88
    )

    if direction_summary.empty:
        print(
            "No replicating directional rows."
        )
    else:
        print(
            direction_summary[
                [
                    "hypothesis_id",
                    "state_a",
                    "state_b",
                    "effect_type",
                    "direction",
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
        "REPLICATING STATES — OLDER VS NEWER VALIDATION"
    )
    print(
        "=" * 88
    )

    if temporal_summary.empty:
        print(
            "No replicating temporal rows."
        )
    else:
        print(
            temporal_summary[
                [
                    "hypothesis_id",
                    "state_a",
                    "state_b",
                    "effect_type",
                    "validation_subperiod",
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
        "REPLICATING STATES — SYMBOL CONCENTRATION"
    )
    print(
        "=" * 88
    )

    if concentration_summary.empty:
        print(
            "No concentration rows."
        )
    else:
        print(
            concentration_summary[
                [
                    "hypothesis_id",
                    "state_a",
                    "state_b",
                    "effect_type",
                    "total_n",
                    "symbol_n",
                    "top1_share_pct",
                    "top5_share_pct",
                    "top10_share_pct",
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
        "REPLICATING STATES — ETF SENSITIVITY"
    )
    print(
        "=" * 88
    )

    if etf_summary.empty:
        print(
            "No ETF sensitivity rows."
        )
    else:
        print(
            etf_summary[
                [
                    "hypothesis_id",
                    "state_a",
                    "state_b",
                    "effect_type",
                    "sensitivity",
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
        "OUTPUTS"
    )
    print(
        "=" * 88
    )

    print(
        f"Events:          {EVENTS_OUTPUT}"
    )
    print(
        f"Pair inventory:  {PAIR_INVENTORY_OUTPUT}"
    )
    print(
        f"All states:      {ALL_STATES_OUTPUT}"
    )
    print(
        f"Paired:          {PAIRED_OUTPUT}"
    )
    print(
        f"Replicating:     {REPLICATING_OUTPUT}"
    )
    print(
        f"Direction:       {DIRECTION_OUTPUT}"
    )
    print(
        f"Temporal:        {TEMPORAL_OUTPUT}"
    )
    print(
        f"Quarter:         {QUARTER_OUTPUT}"
    )
    print(
        f"Symbols:         {SYMBOL_OUTPUT}"
    )
    print(
        f"Concentration:   {CONCENTRATION_OUTPUT}"
    )
    print(
        f"ETF sensitivity: {ETF_OUTPUT}"
    )
    print(
        f"Top discovery:   {TOP_DISCOVERY_OUTPUT}"
    )

    print()
    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()
