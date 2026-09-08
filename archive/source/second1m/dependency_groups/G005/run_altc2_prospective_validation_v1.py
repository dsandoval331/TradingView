from __future__ import annotations

from pathlib import Path
import argparse
import importlib.util
import json
import os
import sys
import time
from getpass import getpass

import numpy as np
import pandas as pd


# =============================================================================
# A36.3B — CONSOLIDATED PARITY-PRESERVING PROSPECTIVE RUNNER V1
# =============================================================================
#
# This runner:
#   1. Incrementally extends the frozen 1m cache through --end-date
#   2. Re-runs the ORIGINAL frozen feature lineage in an isolated work tree
#   3. Re-applies the ORIGINAL frozen exhaustion thresholds from historical V1
#   4. Extracts only prospective AE2 events >= protocol prospective_start_date
#   5. Scores PREFERRED / NEUTRAL / AVOID exactly as Candidate Model V1
#   6. Appends idempotently to the prospective ledger
#   7. Writes a compact validation status report
#
# IMPORTANT:
#   - Historical research outputs are NEVER overwritten.
#   - Frozen research scripts are imported from the repository root.
#   - Their output paths are remapped into a prospective work directory.
#   - No C3+ / Trade Health inputs affect entry classification.
# =============================================================================


ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

HIST_RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

CACHE_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_cache_v1"
)

WORK_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_prospective_work_v1"
)

VALIDATION_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_prospective_v1"
)

PROTOCOL_PATH = (
    VALIDATION_ROOT
    / "protocol"
    / "ALT_C2_PROSPECTIVE_VALIDATION_V1.json"
)

EVENT_DIR = VALIDATION_ROOT / "events"
REPORT_DIR = VALIDATION_ROOT / "reports"

LEDGER_PATH = (
    EVENT_DIR
    / "altc2_prospective_event_ledger_v1.parquet"
)

LEDGER_CSV_PATH = (
    EVENT_DIR
    / "altc2_prospective_event_ledger_v1.csv"
)

RUN_REPORT_PATH = (
    REPORT_DIR
    / "altc2_prospective_status_v1.csv"
)

FROZEN_EXHAUSTION_THRESHOLDS = (
    HIST_RESEARCH_ROOT
    / "ae2_robustness_v1"
    / "ae2_discovery_thresholds_v1.csv"
)

# Exact frozen source scripts, in dependency order.
PIPELINE_SCRIPTS = [
    "research_second1m_alt_entry_v1.py",
    "research_second1m_ae2_c2_predictors_v1.py",
    "research_second1m_ae2_ma_context_v1.py",
    "research_second1m_ae2_short_ma_warning_v1.py",
    "research_second1m_ae2_daily_trend_v1.py",
    "research_second1m_ae2_trend_exhaustion_robustness_v1.py",
    "research_second1m_ae2_weekly_trend_v1.py",
    "research_second1m_ae2_market_regime_v1.py",
    "research_second1m_ae2_three_index_regime_v1.py",
    "research_second1m_ae2_relative_strength_v1.py",
    "research_second1m_ae2_relative_strength_robustness_v1.py",
    "research_second1m_ae2_opening_volume_v1.py",
    "research_second1m_ae2_volume_robustness_v1.py",
    "research_second1m_ae2_session_levels_v1.py",
]

ACQUISITION_SCRIPT = (
    ROOT
    / "acquire_second1m_alt_entry_universe.py"
)

# Final feature source after the exact chain above.
SESSION_FEATURE_PATH = (
    WORK_ROOT
    / "ae2_session_levels_v1"
    / "ae2_session_level_features_v1.parquet"
)

C2_FEATURE_PATH = (
    WORK_ROOT
    / "ae2_c2_predictors_v1"
    / "ae2_c2_predictor_features_v1.parquet"
)

FAVORABLE_TARGET_PCT = 0.50
ADVERSE_TARGET_PCT = 0.50

EVENT_KEY = [
    "symbol",
    "trade_date",
    "direction",
    "architecture",
    "decision_candle",
    "entry_timestamp",
]

EXHAUSTION_FEATURES = {
    "c2_favorable_vwap_distance_pct": "C2_VWAP_DISTANCE",
    "c2_favorable_body_return_pct": "C2_BODY_RETURN",
    "c1_to_c2_close_progress_pct": "C1_TO_C2_PROGRESS",
    "c2_favorable_clv_pct": "C2_FAVORABLE_CLV",
}


# =============================================================================
# COMPATIBILITY / IMPORT HELPERS
# =============================================================================

def safe_arrow_patch() -> None:
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
            return original_unregister(name)
        except Exception as exc:
            if (
                name == "arrow.py_extension_type"
                and exc.__class__.__name__ == "ArrowKeyError"
            ):
                return None
            raise

    pyarrow.unregister_extension_type = safe_unregister


def import_module_from_path(
    path: Path,
    module_name: str,
):
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Could not import {path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


def remap_path_value(
    value,
):
    if not isinstance(
        value,
        Path,
    ):
        return value

    try:
        relative = value.relative_to(
            HIST_RESEARCH_ROOT
        )

        return (
            WORK_ROOT
            / relative
        )

    except ValueError:
        return value


def remap_module_research_paths(
    module,
) -> None:
    """
    Remap only Paths living under historical research root.
    Cache paths remain untouched and continue using the shared frozen cache.
    """

    for name, value in list(
        vars(module).items()
    ):
        if isinstance(
            value,
            Path,
        ):
            setattr(
                module,
                name,
                remap_path_value(
                    value
                ),
            )

    # First-stage event generator uses OUTPUT_ROOT directly under historical root.
    if hasattr(
        module,
        "OUTPUT_ROOT",
    ):
        value = getattr(
            module,
            "OUTPUT_ROOT",
        )

        if isinstance(
            value,
            Path,
        ):
            try:
                value.relative_to(
                    HIST_RESEARCH_ROOT
                )

                setattr(
                    module,
                    "OUTPUT_ROOT",
                    WORK_ROOT,
                )

            except ValueError:
                pass

    # Recompute simple output globals that may have been based on OUTPUT_ROOT
    # before it was remapped.
    for name, value in list(
        vars(module).items()
    ):
        if isinstance(
            value,
            Path,
        ):
            setattr(
                module,
                name,
                remap_path_value(
                    value
                ),
            )


# =============================================================================
# INCREMENTAL ACQUISITION
# =============================================================================

def build_year_start(
    year: int,
) -> str:
    if year == 2025:
        return "2025-05-23"

    return f"{year}-01-01"


def acquire_incremental(
    end_date: pd.Timestamp,
) -> None:
    """
    Extend only the current/end-year partition for each symbol.
    Uses the original acquisition module's Massive client, normalization,
    validation helpers, and atomic parquet writer.
    """

    if not ACQUISITION_SCRIPT.exists():
        raise FileNotFoundError(
            f"Missing acquisition source: {ACQUISITION_SCRIPT}"
        )

    module = import_module_from_path(
        ACQUISITION_SCRIPT,
        "altc2_acquire_frozen",
    )

    root = ROOT

    symbols = module.load_research_symbols(
        root
    )

    api_key = (
        os.environ
        .get(
            "MASSIVE_API_KEY"
        )
    )

    if not api_key:
        api_key = getpass(
            "Enter Massive API key: "
        ).strip()

    if not api_key:
        raise RuntimeError(
            "Massive API key was not provided."
        )

    client = module.MassiveClient(
        module.MassiveClientConfig(
            api_key=api_key,
            requests_per_minute=
                module.REQUESTS_PER_MINUTE,
        )
    )

    end_year = int(
        end_date.year
    )

    print()
    print(
        "=" * 88
    )

    print(
        "INCREMENTAL CACHE ACQUISITION"
    )

    print(
        "=" * 88
    )

    print(
        f"Target end date: {end_date.date()}"
    )

    updated_n = 0
    skipped_n = 0

    for i, symbol in enumerate(
        symbols,
        start=1,
    ):
        path = module.partition_path(
            root,
            symbol,
            end_year,
        )

        requested_year_start = pd.Timestamp(
            build_year_start(
                end_year
            )
        )

        if path.exists():
            existing = pd.read_parquet(
                path
            )

            existing[
                "trade_date"
            ] = pd.to_datetime(
                existing[
                    "trade_date"
                ],
                errors="coerce",
            )

            max_date = existing[
                "trade_date"
            ].max()

            if (
                not pd.isna(
                    max_date
                )
                and pd.Timestamp(
                    max_date
                ).normalize()
                >= end_date.normalize()
            ):
                skipped_n += 1

                print(
                    f"[{i:>3}/{len(symbols)}] "
                    f"{symbol:<6} SKIP "
                    f"(already through {pd.Timestamp(max_date).date()})"
                )

                continue

            if pd.isna(
                max_date
            ):
                incremental_start = (
                    requested_year_start
                )
            else:
                incremental_start = (
                    pd.Timestamp(
                        max_date
                    ).normalize()
                    + pd.Timedelta(
                        days=1
                    )
                )
        else:
            existing = pd.DataFrame()

            incremental_start = (
                requested_year_start
            )

        if incremental_start > end_date:
            skipped_n += 1
            continue

        print(
            f"[{i:>3}/{len(symbols)}] "
            f"{symbol:<6} "
            f"{incremental_start.date()} -> {end_date.date()}"
        )

        rows = (
            client
            .get_minute_aggs(
                symbol=symbol,
                start_date=
                    incremental_start.strftime(
                        "%Y-%m-%d"
                    ),
                end_date=
                    end_date.strftime(
                        "%Y-%m-%d"
                    ),
                adjusted=True,
                limit=module.MASSIVE_LIMIT,
            )
        )

        new_df = module.normalize_rows(
            symbol,
            rows,
        )

        if new_df.empty:
            print(
                "    NO NEW ROWS"
            )
            continue

        if existing.empty:
            combined = (
                new_df
                .copy()
            )
        else:
            combined = pd.concat(
                [
                    existing,
                    new_df,
                ],
                ignore_index=True,
                sort=False,
            )

            combined = (
                combined
                .drop_duplicates(
                    subset=[
                        "timestamp_utc"
                    ],
                    keep="last",
                )
            )

        combined = (
            combined
            .sort_values(
                "timestamp_utc"
            )
            .reset_index(
                drop=True
            )
        )

        module.atomic_write(
            combined,
            path,
        )

        updated_n += 1

    print()

    print(
        f"Updated partitions: {updated_n:,}"
    )

    print(
        f"Skipped partitions: {skipped_n:,}"
    )


# =============================================================================
# RUN ORIGINAL FROZEN RESEARCH LINEAGE IN ISOLATED WORK TREE
# =============================================================================

def run_frozen_stage(
    script_name: str,
    stage_index: int,
    stage_count: int,
) -> None:
    path = ROOT / script_name

    if not path.exists():
        raise FileNotFoundError(
            f"Missing frozen source script: {path}"
        )

    module = import_module_from_path(
        path,
        (
            "altc2_stage_"
            + str(
                stage_index
            )
        ),
    )

    remap_module_research_paths(
        module
    )

    # First-stage partition-count contract:
    # set expected count to the exact complete cache file count.
    if hasattr(
        module,
        "EXPECTED_PARTITIONS",
    ):
        parquet_n = len(
            list(
                CACHE_ROOT.rglob(
                    "*.parquet"
                )
            )
        )

        module.EXPECTED_PARTITIONS = (
            parquet_n
        )

    print()
    print(
        "=" * 88
    )

    print(
        f"STAGE {stage_index}/{stage_count}: "
        f"{script_name}"
    )

    print(
        "=" * 88
    )

    module.main()


def run_feature_lineage() -> None:
    WORK_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    stage_count = len(
        PIPELINE_SCRIPTS
    )

    for i, script_name in enumerate(
        PIPELINE_SCRIPTS,
        start=1,
    ):
        run_frozen_stage(
            script_name,
            i,
            stage_count,
        )


# =============================================================================
# FROZEN EXHAUSTION REAPPLICATION
# =============================================================================

def load_frozen_thresholds() -> dict:
    if not FROZEN_EXHAUSTION_THRESHOLDS.exists():
        raise FileNotFoundError(
            "Frozen exhaustion thresholds not found: "
            f"{FROZEN_EXHAUSTION_THRESHOLDS}"
        )

    thresholds = pd.read_csv(
        FROZEN_EXHAUSTION_THRESHOLDS
    )

    required = {
        "feature",
        "discovery_q20",
        "discovery_q80",
    }

    missing = (
        required
        - set(
            thresholds.columns
        )
    )

    if missing:
        raise RuntimeError(
            "Frozen threshold file missing columns: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    lookup = {}

    for _, row in thresholds.iterrows():
        lookup[
            str(
                row[
                    "feature"
                ]
            )
        ] = {
            "q20":
                float(
                    row[
                        "discovery_q20"
                    ]
                ),

            "q80":
                float(
                    row[
                        "discovery_q80"
                    ]
                ),
        }

    for feature in EXHAUSTION_FEATURES:
        if feature not in lookup:
            raise RuntimeError(
                "Frozen threshold missing feature: "
                f"{feature}"
            )

    return lookup


def compute_frozen_exhaustion(
    c2: pd.DataFrame,
) -> pd.DataFrame:
    thresholds = load_frozen_thresholds()

    x = c2[
        EVENT_KEY
        + list(
            EXHAUSTION_FEATURES.keys()
        )
    ].copy()

    extreme_cols = []

    for feature in EXHAUSTION_FEATURES:
        q80 = thresholds[
            feature
        ][
            "q80"
        ]

        col = (
            f"_extreme_{feature}"
        )

        x[
            col
        ] = (
            x[
                feature
            ]
            >= q80
        )

        extreme_cols.append(
            col
        )

    x[
        "exhaustion_extreme_count"
    ] = (
        x[
            extreme_cols
        ]
        .astype(int)
        .sum(
            axis=1
        )
    )

    x[
        "exhaustion_state"
    ] = np.where(
        x[
            "exhaustion_extreme_count"
        ]
        == 0,
        "NONE",
        np.where(
            x[
                "exhaustion_extreme_count"
            ]
            == 1,
            "ONE",
            "MULTIPLE",
        ),
    )

    return x[
        EVENT_KEY
        + [
            "exhaustion_extreme_count",
            "exhaustion_state",
        ]
    ]


# =============================================================================
# PROSPECTIVE ENRICHMENT / CLASSIFICATION
# =============================================================================

def normalize_keys(
    df: pd.DataFrame,
) -> pd.DataFrame:
    df = df.copy()

    df[
        "symbol"
    ] = (
        df[
            "symbol"
        ]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df[
        "direction"
    ] = (
        df[
            "direction"
        ]
        .astype(str)
        .str.upper()
        .str.strip()
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

    df[
        "entry_timestamp"
    ] = pd.to_datetime(
        df[
            "entry_timestamp"
        ],
        errors="coerce",
        utc=True,
    )

    return df


def build_enriched_prospective(
    protocol: dict,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    if not SESSION_FEATURE_PATH.exists():
        raise FileNotFoundError(
            f"Missing session feature output: {SESSION_FEATURE_PATH}"
        )

    if not C2_FEATURE_PATH.exists():
        raise FileNotFoundError(
            f"Missing C2 feature output: {C2_FEATURE_PATH}"
        )

    session = pd.read_parquet(
        SESSION_FEATURE_PATH
    )

    c2 = pd.read_parquet(
        C2_FEATURE_PATH
    )

    session = normalize_keys(
        session
    )

    c2 = normalize_keys(
        c2
    )

    frozen_exhaustion = (
        compute_frozen_exhaustion(
            c2
        )
    )

    frozen_exhaustion = normalize_keys(
        frozen_exhaustion
    )

    # Avoid duplicate stale exhaustion columns from the chain.
    session = session.drop(
        columns=[
            "exhaustion_state",
            "exhaustion_extreme_count",
        ],
        errors="ignore",
    )

    enriched = session.merge(
        frozen_exhaustion,
        on=EVENT_KEY,
        how="left",
        validate="one_to_one",
    )

    required = [
        "symbol",
        "trade_date",
        "direction",
        "architecture",
        "decision_candle",
        "entry_timestamp",
        "entry_price",
        "outcome",
        "final_mfe_pct",
        "final_mae_pct",
        "session_level_clear_state",
        "market_prior_5d_consensus",
        "market_3idx_prior_5d_state",
        "relative_multi_horizon_state",
        "exhaustion_state",
    ]

    missing = [
        col
        for col in required
        if col not in enriched.columns
    ]

    if missing:
        raise RuntimeError(
            "Prospective enrichment missing required fields: "
            + ", ".join(
                missing
            )
        )

    prospective_start = pd.Timestamp(
        protocol[
            "prospective_start_date"
        ]
    )

    prospective = enriched.loc[
        (
            enriched[
                "trade_date"
            ]
            >= prospective_start
        )
        &
        (
            enriched[
                "trade_date"
            ]
            <= end_date
        )
    ].copy()

    return prospective


def score_candidate_model(
    df: pd.DataFrame,
) -> pd.DataFrame:
    df = df.copy()

    for col in [
        "session_level_clear_state",
        "market_prior_5d_consensus",
        "market_3idx_prior_5d_state",
        "relative_multi_horizon_state",
        "exhaustion_state",
    ]:
        df[
            col
        ] = (
            df[
                col
            ]
            .astype(str)
            .str.strip()
        )

    df[
        "positive_family_p1"
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
        "support_h1b"
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

    df[
        "negative_family_n1"
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

    df[
        "negative_n2_exhaustion_child"
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
        "negative_n2_relative_child"
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

    df[
        "negative_family_n2"
    ] = (
        df[
            "negative_n2_exhaustion_child"
        ]
        |
        df[
            "negative_n2_relative_child"
        ]
    )

    df[
        "negative_family_any"
    ] = (
        df[
            "negative_family_n1"
        ]
        |
        df[
            "negative_family_n2"
        ]
    )

    df[
        "model_conflict"
    ] = (
        df[
            "positive_family_p1"
        ]
        &
        df[
            "negative_family_any"
        ]
    )

    df[
        "candidate_triage_state"
    ] = np.where(
        df[
            "negative_family_any"
        ],
        "AVOID",
        np.where(
            df[
                "positive_family_p1"
            ],
            "PREFERRED",
            "NEUTRAL",
        ),
    )

    return df


# =============================================================================
# LEDGER
# =============================================================================

def event_id(
    row: pd.Series,
) -> str:
    import hashlib

    values = []

    for col in EVENT_KEY:
        value = row[
            col
        ]

        if isinstance(
            value,
            pd.Timestamp,
        ):
            value = value.isoformat()

        values.append(
            str(
                value
            )
        )

    text = "|".join(
        values
    )

    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()[:24]


def append_ledger(
    scored: pd.DataFrame,
    protocol: dict,
) -> tuple[pd.DataFrame, int, int]:
    EVENT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    scored = scored.copy()

    scored[
        "event_id"
    ] = scored.apply(
        event_id,
        axis=1,
    )

    scored[
        "protocol_id"
    ] = protocol[
        "protocol_id"
    ]

    scored[
        "candidate_model_id"
    ] = protocol[
        "candidate_model_id"
    ]

    if LEDGER_PATH.exists():
        existing = pd.read_parquet(
            LEDGER_PATH
        )

        existing_ids = set(
            existing[
                "event_id"
            ]
            .astype(str)
        )
    else:
        existing = pd.DataFrame()

        existing_ids = set()

    is_new = ~scored[
        "event_id"
    ].astype(str).isin(
        existing_ids
    )

    new_rows = scored.loc[
        is_new
    ].copy()

    duplicate_n = int(
        (~is_new).sum()
    )

    if existing.empty:
        combined = new_rows
    else:
        combined = pd.concat(
            [
                existing,
                new_rows,
            ],
            ignore_index=True,
            sort=False,
        )

    if not combined.empty:
        combined = (
            combined
            .sort_values(
                [
                    "trade_date",
                    "symbol",
                    "entry_timestamp",
                ]
            )
            .reset_index(
                drop=True
            )
        )

    combined.to_parquet(
        LEDGER_PATH,
        index=False,
    )

    combined.to_csv(
        LEDGER_CSV_PATH,
        index=False,
    )

    return (
        combined,
        int(
            len(
                new_rows
            )
        ),
        duplicate_n,
    )


# =============================================================================
# STATUS REPORT
# =============================================================================

def ff_stats(
    x: pd.DataFrame,
) -> dict:
    favorable = int(
        (
            x[
                "outcome"
            ]
            == "FAVORABLE_FIRST"
        ).sum()
    )

    adverse = int(
        (
            x[
                "outcome"
            ]
            == "ADVERSE_FIRST"
        ).sum()
    )

    both = int(
        (
            x[
                "outcome"
            ]
            == "BOTH_SAME_BAR"
        ).sum()
    )

    unresolved = int(
        (
            x[
                "outcome"
            ]
            == "UNRESOLVED"
        ).sum()
    )

    binary = favorable + adverse

    return {
        "total_n":
            int(
                len(
                    x
                )
            ),

        "binary_n":
            binary,

        "favorable_n":
            favorable,

        "adverse_n":
            adverse,

        "both_same_bar_n":
            both,

        "unresolved_n":
            unresolved,

        "favorable_first_pct":
            (
                100.0
                * favorable
                / binary
                if binary
                else np.nan
            ),
    }


def write_status_report(
    ledger: pd.DataFrame,
) -> pd.DataFrame:
    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows = []

    for state in [
        "PREFERRED",
        "NEUTRAL",
        "AVOID",
    ]:
        x = ledger.loc[
            ledger[
                "candidate_triage_state"
            ]
            == state
        ]

        rows.append(
            {
                "candidate_triage_state":
                    state,

                **ff_stats(
                    x
                ),
            }
        )

    report = pd.DataFrame(
        rows
    )

    report.to_csv(
        RUN_REPORT_PATH,
        index=False,
    )

    return report


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Alternative C2 frozen prospective validation "
            "through a specified completed market date."
        )
    )

    parser.add_argument(
        "--end-date",
        required=True,
        help="Completed prospective market date, YYYY-MM-DD.",
    )

    parser.add_argument(
        "--skip-acquire",
        action="store_true",
        help=(
            "Do not call Massive. Use the cache exactly as it exists."
        ),
    )

    parser.add_argument(
        "--skip-feature-rebuild",
        action="store_true",
        help=(
            "Use existing prospective work feature outputs."
        ),
    )

    args = parser.parse_args()

    safe_arrow_patch()

    if not PROTOCOL_PATH.exists():
        raise FileNotFoundError(
            f"Frozen protocol missing: {PROTOCOL_PATH}"
        )

    protocol = json.loads(
        PROTOCOL_PATH.read_text(
            encoding="utf-8"
        )
    )

    end_date = pd.Timestamp(
        args.end_date
    ).normalize()

    prospective_start = pd.Timestamp(
        protocol[
            "prospective_start_date"
        ]
    )

    if end_date < prospective_start:
        raise RuntimeError(
            f"--end-date {end_date.date()} is before "
            f"prospective start {prospective_start.date()}."
        )

    print(
        "=" * 88
    )

    print(
        "A36.3B - ALT C2 CONSOLIDATED PROSPECTIVE RUNNER V1"
    )

    print(
        "=" * 88
    )

    print(
        f"Prospective start: {prospective_start.date()}"
    )

    print(
        f"Run end date:      {end_date.date()}"
    )

    print(
        f"Protocol:          {protocol['protocol_id']}"
    )

    print(
        f"Model:             {protocol['candidate_model_id']}"
    )

    if not args.skip_acquire:
        acquire_incremental(
            end_date
        )
    else:
        print()
        print(
            "Acquisition skipped by request."
        )

    if not args.skip_feature_rebuild:
        run_feature_lineage()
    else:
        print()
        print(
            "Feature rebuild skipped by request."
        )

    prospective = (
        build_enriched_prospective(
            protocol,
            end_date,
        )
    )

    scored = score_candidate_model(
        prospective
    )

    ledger, new_n, duplicate_n = (
        append_ledger(
            scored,
            protocol,
        )
    )

    report = write_status_report(
        ledger
    )

    print()
    print(
        "=" * 88
    )

    print(
        "PROSPECTIVE RUN SUMMARY"
    )

    print(
        "=" * 88
    )

    print(
        f"Prospective events in current rebuild: "
        f"{len(scored):,}"
    )

    print(
        f"New ledger events:                    "
        f"{new_n:,}"
    )

    print(
        f"Existing duplicates skipped:          "
        f"{duplicate_n:,}"
    )

    print(
        f"Total ledger events:                  "
        f"{len(ledger):,}"
    )

    print()

    print(
        report.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    print()

    conflict_n = int(
        ledger[
            "model_conflict"
        ]
        .sum()
    ) if (
        not ledger.empty
        and "model_conflict"
        in ledger.columns
    ) else 0

    print(
        f"Model conflicts in ledger: {conflict_n:,}"
    )

    print()

    print(
        f"Ledger: {LEDGER_PATH}"
    )

    print(
        f"Status: {RUN_REPORT_PATH}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()
