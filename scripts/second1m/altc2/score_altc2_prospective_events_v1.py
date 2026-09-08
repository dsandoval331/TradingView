from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np
import pandas as pd


ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

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

LEDGER_PATH = (
    EVENT_DIR
    / "altc2_prospective_event_ledger_v1.parquet"
)

LEDGER_CSV_PATH = (
    EVENT_DIR
    / "altc2_prospective_event_ledger_v1.csv"
)

AUDIT_PATH = (
    EVENT_DIR
    / "altc2_prospective_scoring_audit_v1.csv"
)

REQUIRED_COLUMNS = [
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

EVENT_KEY = [
    "symbol",
    "trade_date",
    "direction",
    "architecture",
    "decision_candle",
    "entry_timestamp",
]


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
                and exc.__class__.__name__
                == "ArrowKeyError"
            ):
                return None
            raise

    pyarrow.unregister_extension_type = safe_unregister


def read_table(path: Path) -> pd.DataFrame:
    safe_arrow_patch()

    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)

    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)

    raise RuntimeError(
        f"Unsupported input type: {path.suffix}. "
        "Use .parquet or .csv."
    )


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

    df["architecture"] = (
        df["architecture"]
        .astype(str)
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

    df["entry_timestamp"] = pd.to_datetime(
        df["entry_timestamp"],
        errors="coerce",
        utc=True,
    )

    for col in [
        "session_level_clear_state",
        "market_prior_5d_consensus",
        "market_3idx_prior_5d_state",
        "relative_multi_horizon_state",
        "exhaustion_state",
        "outcome",
    ]:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
        )

    return df


def event_key_string(row: pd.Series) -> str:
    parts = []

    for col in EVENT_KEY:
        value = row[col]

        if isinstance(value, pd.Timestamp):
            value = value.isoformat()

        parts.append(
            str(value)
        )

    return "|".join(parts)


def event_id_from_row(row: pd.Series) -> str:
    key = event_key_string(row)

    return hashlib.sha256(
        key.encode("utf-8")
    ).hexdigest()[:24]


def score_model(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Positive Family P1
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

    # Supporting nested H1B; no second vote.
    df[
        "support_h1b_all3_opposing"
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

    # Negative Family N1
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

    # Negative Family N2
    df[
        "negative_n2_child_exhaustion"
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
        "negative_n2_child_relative"
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
            "negative_n2_child_exhaustion"
        ]
        |
        df[
            "negative_n2_child_relative"
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

    def classify(row: pd.Series) -> str:
        if bool(
            row[
                "negative_family_any"
            ]
        ):
            return "AVOID"

        if bool(
            row[
                "positive_family_p1"
            ]
        ):
            return "PREFERRED"

        return "NEUTRAL"

    df[
        "candidate_triage_state"
    ] = df.apply(
        classify,
        axis=1,
    )

    return df


def validate_against_protocol(
    df: pd.DataFrame,
    protocol: dict,
) -> None:
    missing = [
        col
        for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing:
        raise RuntimeError(
            "Prospective input is missing required frozen columns: "
            + ", ".join(missing)
        )

    if df[
        "trade_date"
    ].isna().any():
        raise RuntimeError(
            "One or more trade_date values could not be parsed."
        )

    if df[
        "entry_timestamp"
    ].isna().any():
        raise RuntimeError(
            "One or more entry_timestamp values could not be parsed."
        )

    start_date = pd.Timestamp(
        protocol[
            "prospective_start_date"
        ]
    )

    too_old = df.loc[
        df[
            "trade_date"
        ]
        < start_date
    ]

    if not too_old.empty:
        raise RuntimeError(
            f"Found {len(too_old):,} rows before frozen prospective "
            f"start date {start_date.date()}."
        )

    duplicate_n = int(
        df.duplicated(
            subset=EVENT_KEY,
            keep=False,
        ).sum()
    )

    if duplicate_n:
        raise RuntimeError(
            f"Input contains {duplicate_n:,} duplicate event-key rows."
        )


def append_idempotent(
    scored: pd.DataFrame,
) -> tuple[pd.DataFrame, int, int]:
    EVENT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if LEDGER_PATH.exists():
        existing = read_table(
            LEDGER_PATH
        )

        existing = normalize(
            existing
        )

        if "event_id" not in existing.columns:
            raise RuntimeError(
                "Existing prospective ledger is missing event_id."
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

    incoming = scored.copy()

    is_new = ~incoming[
        "event_id"
    ].astype(str).isin(
        existing_ids
    )

    new_rows = incoming.loc[
        is_new
    ].copy()

    skipped_n = int(
        (~is_new).sum()
    )

    if existing.empty:
        combined = new_rows.copy()
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
        combined = combined.sort_values(
            [
                "trade_date",
                "symbol",
                "entry_timestamp",
            ]
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
            len(new_rows)
        ),
        skipped_n,
    )


def write_audit(
    scored: pd.DataFrame,
    source_path: Path,
    new_n: int,
    skipped_n: int,
) -> None:
    rows = []

    for state, x in scored.groupby(
        "candidate_triage_state"
    ):
        rows.append(
            {
                "source_file":
                    str(
                        source_path
                    ),

                "candidate_triage_state":
                    state,

                "row_n":
                    int(
                        len(x)
                    ),

                "model_conflict_n":
                    int(
                        x[
                            "model_conflict"
                        ]
                        .sum()
                    ),

                "new_ledger_rows_total":
                    new_n,

                "duplicate_rows_skipped_total":
                    skipped_n,
            }
        )

    audit = pd.DataFrame(
        rows
    )

    if AUDIT_PATH.exists():
        previous = pd.read_csv(
            AUDIT_PATH
        )

        audit = pd.concat(
            [
                previous,
                audit,
            ],
            ignore_index=True,
            sort=False,
        )

    audit.to_csv(
        AUDIT_PATH,
        index=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Score already-enriched prospective AE2 events using "
            "ALT_C2_CANDIDATE_MODEL_V1 and append them to the frozen ledger."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Prospective enriched AE2 .parquet or .csv file.",
    )

    args = parser.parse_args()

    input_path = Path(
        args.input
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input not found: {input_path}"
        )

    if not PROTOCOL_PATH.exists():
        raise FileNotFoundError(
            f"Frozen protocol not found: {PROTOCOL_PATH}"
        )

    protocol = json.loads(
        PROTOCOL_PATH.read_text(
            encoding="utf-8"
        )
    )

    df = read_table(
        input_path
    )

    missing_before_normalize = [
        col
        for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing_before_normalize:
        raise RuntimeError(
            "Prospective input missing columns: "
            + ", ".join(
                missing_before_normalize
            )
        )

    df = normalize(
        df
    )

    validate_against_protocol(
        df,
        protocol,
    )

    df[
        "event_id"
    ] = df.apply(
        event_id_from_row,
        axis=1,
    )

    df[
        "candidate_model_id"
    ] = protocol[
        "candidate_model_id"
    ]

    df[
        "protocol_id"
    ] = protocol[
        "protocol_id"
    ]

    df = score_model(
        df
    )

    combined, new_n, skipped_n = (
        append_idempotent(
            df
        )
    )

    write_audit(
        df,
        input_path,
        new_n,
        skipped_n,
    )

    print(
        "=" * 88
    )

    print(
        "A36.2 - ALT C2 PROSPECTIVE FROZEN SCORER V1"
    )

    print(
        "=" * 88
    )

    print(
        f"Input rows:        {len(df):,}"
    )

    print(
        f"New ledger rows:   {new_n:,}"
    )

    print(
        f"Duplicate skipped: {skipped_n:,}"
    )

    print(
        f"Ledger rows:       {len(combined):,}"
    )

    print()

    print(
        "INPUT STATE COUNTS"
    )

    print(
        df[
            "candidate_triage_state"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print()

    conflict_n = int(
        df[
            "model_conflict"
        ]
        .sum()
    )

    print(
        f"Model conflicts:   {conflict_n:,}"
    )

    if conflict_n:
        print(
            "Conflict rule applied: AVOID + MODEL_CONFLICT flag."
        )

    print()

    print(
        f"Ledger parquet: {LEDGER_PATH}"
    )

    print(
        f"Ledger CSV:     {LEDGER_CSV_PATH}"
    )

    print(
        f"Audit CSV:      {AUDIT_PATH}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()
