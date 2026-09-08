from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# A34.4 / R13 — ROBUST INTERACTION PROMOTION AUDIT V1
# =============================================================================
#
# PURPOSE
# -------
# Reduce the R13 interaction results into a small, governed set of:
#
#   TIER_A_POSITIVE      = robust positive candidate
#   TIER_B_CONTEXT       = replicated/supporting context, not promoted
#   TIER_C_AVOIDANCE     = robust negative / avoidance candidate
#   TIER_D_NONACTIONABLE = technically replicating but too weak/unstable
#
# IMPORTANT
# ---------
# This script DOES NOT discover new interactions and DOES NOT optimize thresholds
# to maximize win rate. It evaluates only the frozen R13 interaction states that
# already passed the discovery/validation sign-replication gate.
#
# The promotion thresholds below are governance thresholds, not statistically
# optimized trading thresholds.
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

INPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_interactions_v1"
)

PAIRED_PATH = (
    INPUT_ROOT
    / "ae2_interaction_discovery_validation_v1.csv"
)

REPLICATING_PATH = (
    INPUT_ROOT
    / "ae2_interaction_replicating_v1.csv"
)

DIRECTION_PATH = (
    INPUT_ROOT
    / "ae2_interaction_direction_v1.csv"
)

TEMPORAL_PATH = (
    INPUT_ROOT
    / "ae2_interaction_temporal_v1.csv"
)

QUARTER_PATH = (
    INPUT_ROOT
    / "ae2_interaction_quarter_v1.csv"
)

CONCENTRATION_PATH = (
    INPUT_ROOT
    / "ae2_interaction_concentration_v1.csv"
)

ETF_PATH = (
    INPUT_ROOT
    / "ae2_interaction_etf_sensitivity_v1.csv"
)

EVENTS_PATH = (
    INPUT_ROOT
    / "ae2_interaction_events_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_interaction_promotion_v1"
)

AUDIT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_promotion_audit_v1.csv"
)

TIER_A_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_tier_a_positive_v1.csv"
)

TIER_B_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_tier_b_context_v1.csv"
)

TIER_C_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_tier_c_avoidance_v1.csv"
)

TIER_D_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_tier_d_nonactionable_v1.csv"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_promotion_summary_v1.csv"
)

REPORT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_interaction_promotion_report_v1.txt"
)


# =============================================================================
# FROZEN GOVERNANCE THRESHOLDS
# =============================================================================
#
# Tier A / C deliberately require more than the original R13 replication gate.
#
# These thresholds are not optimized from the interaction results.
# They represent a conservative research-governance standard.
# =============================================================================

MIN_DISCOVERY_BINARY_N_STRONG = 150
MIN_VALIDATION_BINARY_N_STRONG = 150

MIN_ABS_DISCOVERY_LIFT_PP_STRONG = 3.0
MIN_ABS_VALIDATION_LIFT_PP_STRONG = 3.0

# An interaction should add something beyond each component alone.
MIN_VALIDATION_INCREMENTAL_VS_EACH_PARENT_PP = 1.0

# Directional robustness
MIN_DIRECTION_BINARY_N = 50

# Temporal robustness
MIN_TEMPORAL_BINARY_N = 75

# Breadth / concentration
MAX_TOP1_SHARE_PCT = 5.0
MAX_TOP10_SHARE_PCT = 30.0
MIN_SYMBOL_N = 75

# ETF robustness
MAX_ETF_FF_DELTA_PP = 2.0

# Weak/near-baseline replicated state threshold
MAX_ABS_VALIDATION_LIFT_PP_NONACTIONABLE = 1.5


# =============================================================================
# HELPERS
# =============================================================================

KEYS = [
    "hypothesis_id",
    "feature_a",
    "state_a",
    "feature_b",
    "state_b",
]


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Required input not found: {path}"
        )


def load_csv(path: Path) -> pd.DataFrame:
    require_file(path)
    return pd.read_csv(path)


def normalize_key_text(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in [
        "hypothesis_id",
        "feature_a",
        "state_a",
        "feature_b",
        "state_b",
        "effect_type",
        "direction",
        "validation_subperiod",
        "sensitivity",
        "quarter",
    ]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
            )

    return df


def same_candidate_mask(
    df: pd.DataFrame,
    row: pd.Series,
) -> pd.Series:
    mask = pd.Series(
        True,
        index=df.index,
    )

    for key in KEYS:
        mask &= (
            df[key].astype(str)
            == str(row[key])
        )

    return mask


def sign_matches(
    value: float,
    baseline: float,
    effect_type: str,
) -> bool:
    if pd.isna(value) or pd.isna(baseline):
        return False

    if effect_type == "POSITIVE_REPLICATING":
        return value > baseline

    if effect_type == "NEGATIVE_REPLICATING":
        return value < baseline

    return False


def safe_abs_delta(
    a: float,
    b: float,
) -> float:
    if pd.isna(a) or pd.isna(b):
        return np.nan

    return abs(
        float(a)
        - float(b)
    )


def get_event_baselines() -> dict:
    """
    Read the narrow interaction parquet and calculate exact baselines needed
    for directional and validation-half robustness.

    Includes a narrow pyarrow compatibility guard for the same pandas/pyarrow
    environment issue encountered during A34.3.
    """

    require_file(
        EVENTS_PATH
    )

    import pyarrow

    original_unregister = getattr(
        pyarrow,
        "unregister_extension_type",
        None,
    )

    if original_unregister is not None:

        def safe_unregister(name: str):
            try:
                return original_unregister(
                    name
                )
            except Exception as exc:
                if (
                    name
                    == "arrow.py_extension_type"
                    and exc.__class__.__name__
                    == "ArrowKeyError"
                ):
                    return None
                raise

        pyarrow.unregister_extension_type = (
            safe_unregister
        )

    events = pd.read_parquet(
        EVENTS_PATH,
        columns=[
            "outcome",
            "direction",
            "research_period",
            "validation_subperiod",
            "symbol",
        ],
    )

    events[
        "is_binary"
    ] = events[
        "outcome"
    ].isin(
        [
            "FAVORABLE_FIRST",
            "ADVERSE_FIRST",
        ]
    )

    events[
        "is_favorable"
    ] = (
        events[
            "outcome"
        ]
        == "FAVORABLE_FIRST"
    )

    def ff_pct(x: pd.DataFrame) -> float:
        y = x.loc[
            x[
                "is_binary"
            ]
        ]

        if y.empty:
            return np.nan

        return (
            100.0
            * y[
                "is_favorable"
            ].mean()
        )

    baseline = {}

    baseline[
        "VALIDATION_ALL"
    ] = ff_pct(
        events.loc[
            events[
                "research_period"
            ]
            == "VALIDATION"
        ]
    )

    for direction in sorted(
        events[
            "direction"
        ]
        .dropna()
        .unique()
    ):
        baseline[
            f"DIRECTION::{direction}"
        ] = ff_pct(
            events.loc[
                (
                    events[
                        "research_period"
                    ]
                    == "VALIDATION"
                )
                &
                (
                    events[
                        "direction"
                    ]
                    == direction
                )
            ]
        )

    for subperiod in [
        "VALIDATION_OLDER",
        "VALIDATION_NEWER",
    ]:
        baseline[
            f"TEMPORAL::{subperiod}"
        ] = ff_pct(
            events.loc[
                events[
                    "validation_subperiod"
                ]
                == subperiod
            ]
        )

    baseline[
        "ETF_EXCLUDED"
    ] = ff_pct(
        events.loc[
            (
                events[
                    "research_period"
                ]
                == "VALIDATION"
            )
            &
            (
                ~events[
                    "symbol"
                ]
                .isin(
                    [
                        "SPY",
                        "QQQ",
                        "TQQQ",
                    ]
                )
            )
        ]
    )

    return baseline


def directional_audit(
    direction_df: pd.DataFrame,
    row: pd.Series,
    baselines: dict,
) -> tuple[bool, str]:
    x = direction_df.loc[
        same_candidate_mask(
            direction_df,
            row,
        )
    ]

    if x.empty:
        return (
            False,
            "missing_direction_rows",
        )

    failures = []

    expected_directions = [
        "BEAR",
        "BULL",
    ]

    for direction in expected_directions:
        y = x.loc[
            x[
                "direction"
            ]
            == direction
        ]

        if y.empty:
            failures.append(
                f"{direction}_missing"
            )
            continue

        record = y.iloc[0]

        if int(
            record[
                "binary_n"
            ]
        ) < MIN_DIRECTION_BINARY_N:
            failures.append(
                f"{direction}_n<{MIN_DIRECTION_BINARY_N}"
            )
            continue

        baseline = baselines.get(
            f"DIRECTION::{direction}",
            np.nan,
        )

        if not sign_matches(
            float(
                record[
                    "favorable_first_pct"
                ]
            ),
            baseline,
            str(
                row[
                    "effect_type"
                ]
            ),
        ):
            failures.append(
                f"{direction}_sign_fail"
            )

    return (
        len(
            failures
        )
        == 0,
        ";".join(
            failures
        ),
    )


def temporal_audit(
    temporal_df: pd.DataFrame,
    row: pd.Series,
    baselines: dict,
) -> tuple[bool, str]:
    x = temporal_df.loc[
        same_candidate_mask(
            temporal_df,
            row,
        )
    ]

    if x.empty:
        return (
            False,
            "missing_temporal_rows",
        )

    failures = []

    for subperiod in [
        "VALIDATION_OLDER",
        "VALIDATION_NEWER",
    ]:
        y = x.loc[
            x[
                "validation_subperiod"
            ]
            == subperiod
        ]

        if y.empty:
            failures.append(
                f"{subperiod}_missing"
            )
            continue

        record = y.iloc[0]

        if int(
            record[
                "binary_n"
            ]
        ) < MIN_TEMPORAL_BINARY_N:
            failures.append(
                f"{subperiod}_n<{MIN_TEMPORAL_BINARY_N}"
            )
            continue

        baseline = baselines.get(
            f"TEMPORAL::{subperiod}",
            np.nan,
        )

        if not sign_matches(
            float(
                record[
                    "favorable_first_pct"
                ]
            ),
            baseline,
            str(
                row[
                    "effect_type"
                ]
            ),
        ):
            failures.append(
                f"{subperiod}_sign_fail"
            )

    return (
        len(
            failures
        )
        == 0,
        ";".join(
            failures
        ),
    )


def concentration_audit(
    concentration_df: pd.DataFrame,
    row: pd.Series,
) -> tuple[bool, str]:
    x = concentration_df.loc[
        same_candidate_mask(
            concentration_df,
            row,
        )
    ]

    if x.empty:
        return (
            False,
            "missing_concentration_row",
        )

    record = x.iloc[0]

    failures = []

    if int(
        record[
            "symbol_n"
        ]
    ) < MIN_SYMBOL_N:
        failures.append(
            f"symbol_n<{MIN_SYMBOL_N}"
        )

    if float(
        record[
            "top1_share_pct"
        ]
    ) > MAX_TOP1_SHARE_PCT:
        failures.append(
            f"top1>{MAX_TOP1_SHARE_PCT}"
        )

    if float(
        record[
            "top10_share_pct"
        ]
    ) > MAX_TOP10_SHARE_PCT:
        failures.append(
            f"top10>{MAX_TOP10_SHARE_PCT}"
        )

    return (
        len(
            failures
        )
        == 0,
        ";".join(
            failures
        ),
    )


def etf_audit(
    etf_df: pd.DataFrame,
    row: pd.Series,
) -> tuple[
    bool,
    str,
    float,
    float,
    float,
]:
    x = etf_df.loc[
        same_candidate_mask(
            etf_df,
            row,
        )
    ]

    base = x.loc[
        x[
            "sensitivity"
        ]
        == "BASE"
    ]

    excl = x.loc[
        x[
            "sensitivity"
        ]
        == "EXCLUDE_SPY_QQQ_TQQQ"
    ]

    if (
        base.empty
        or excl.empty
    ):
        return (
            False,
            "missing_etf_rows",
            np.nan,
            np.nan,
            np.nan,
        )

    base_ff = float(
        base.iloc[0][
            "favorable_first_pct"
        ]
    )

    excl_ff = float(
        excl.iloc[0][
            "favorable_first_pct"
        ]
    )

    delta = safe_abs_delta(
        base_ff,
        excl_ff,
    )

    return (
        bool(
            delta
            <= MAX_ETF_FF_DELTA_PP
        ),
        (
            ""
            if delta
            <= MAX_ETF_FF_DELTA_PP
            else (
                f"ETF_delta>{MAX_ETF_FF_DELTA_PP}"
            )
        ),
        base_ff,
        excl_ff,
        delta,
    )


def classify_candidate(
    row: pd.Series,
) -> str:
    effect_type = str(
        row[
            "effect_type"
        ]
    )

    discovery_n = int(
        row[
            "binary_n_discovery"
        ]
    )

    validation_n = int(
        row[
            "binary_n_validation"
        ]
    )

    discovery_lift = float(
        row[
            "lift_vs_baseline_pp_discovery"
        ]
    )

    validation_lift = float(
        row[
            "lift_vs_baseline_pp_validation"
        ]
    )

    incr_a_val = float(
        row[
            "incremental_vs_feature_a_pp_validation"
        ]
    )

    incr_b_val = float(
        row[
            "incremental_vs_feature_b_pp_validation"
        ]
    )

    strong_sample = (
        discovery_n
        >= MIN_DISCOVERY_BINARY_N_STRONG
        and validation_n
        >= MIN_VALIDATION_BINARY_N_STRONG
    )

    strong_positive_lift = (
        discovery_lift
        >= MIN_ABS_DISCOVERY_LIFT_PP_STRONG
        and validation_lift
        >= MIN_ABS_VALIDATION_LIFT_PP_STRONG
    )

    strong_negative_lift = (
        discovery_lift
        <= -MIN_ABS_DISCOVERY_LIFT_PP_STRONG
        and validation_lift
        <= -MIN_ABS_VALIDATION_LIFT_PP_STRONG
    )

    positive_incremental = (
        incr_a_val
        >= MIN_VALIDATION_INCREMENTAL_VS_EACH_PARENT_PP
        and incr_b_val
        >= MIN_VALIDATION_INCREMENTAL_VS_EACH_PARENT_PP
    )

    negative_incremental = (
        incr_a_val
        <= -MIN_VALIDATION_INCREMENTAL_VS_EACH_PARENT_PP
        and incr_b_val
        <= -MIN_VALIDATION_INCREMENTAL_VS_EACH_PARENT_PP
    )

    robustness_pass = bool(
        row[
            "direction_pass"
        ]
        and row[
            "temporal_pass"
        ]
        and row[
            "concentration_pass"
        ]
        and row[
            "etf_pass"
        ]
    )

    if (
        effect_type
        == "POSITIVE_REPLICATING"
        and strong_sample
        and strong_positive_lift
        and positive_incremental
        and robustness_pass
    ):
        return "TIER_A_POSITIVE"

    if (
        effect_type
        == "NEGATIVE_REPLICATING"
        and strong_sample
        and strong_negative_lift
        and negative_incremental
        and robustness_pass
    ):
        return "TIER_C_AVOIDANCE"

    if (
        abs(
            validation_lift
        )
        <= MAX_ABS_VALIDATION_LIFT_PP_NONACTIONABLE
    ):
        return "TIER_D_NONACTIONABLE"

    return "TIER_B_CONTEXT"


def main() -> None:
    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in [
        PAIRED_PATH,
        REPLICATING_PATH,
        DIRECTION_PATH,
        TEMPORAL_PATH,
        QUARTER_PATH,
        CONCENTRATION_PATH,
        ETF_PATH,
        EVENTS_PATH,
    ]:
        require_file(
            path
        )

    replicating = normalize_key_text(
        load_csv(
            REPLICATING_PATH
        )
    )

    direction = normalize_key_text(
        load_csv(
            DIRECTION_PATH
        )
    )

    temporal = normalize_key_text(
        load_csv(
            TEMPORAL_PATH
        )
    )

    concentration = normalize_key_text(
        load_csv(
            CONCENTRATION_PATH
        )
    )

    etf = normalize_key_text(
        load_csv(
            ETF_PATH
        )
    )

    baselines = get_event_baselines()

    print(
        "=" * 88
    )

    print(
        "A34.4 / R13 - ROBUST INTERACTION PROMOTION AUDIT V1"
    )

    print(
        "=" * 88
    )

    print(
        f"Replicating interaction states: "
        f"{len(replicating):,}"
    )

    print(
        f"Validation baseline: "
        f"{baselines['VALIDATION_ALL']:.2f}%"
    )

    print(
        f"Validation BEAR baseline: "
        f"{baselines['DIRECTION::BEAR']:.2f}%"
    )

    print(
        f"Validation BULL baseline: "
        f"{baselines['DIRECTION::BULL']:.2f}%"
    )

    print(
        f"Validation older baseline: "
        f"{baselines['TEMPORAL::VALIDATION_OLDER']:.2f}%"
    )

    print(
        f"Validation newer baseline: "
        f"{baselines['TEMPORAL::VALIDATION_NEWER']:.2f}%"
    )

    audit_rows = []

    for _, candidate in (
        replicating.iterrows()
    ):
        direction_pass, direction_reason = (
            directional_audit(
                direction,
                candidate,
                baselines,
            )
        )

        temporal_pass, temporal_reason = (
            temporal_audit(
                temporal,
                candidate,
                baselines,
            )
        )

        (
            concentration_pass,
            concentration_reason,
        ) = concentration_audit(
            concentration,
            candidate,
        )

        (
            etf_pass,
            etf_reason,
            etf_base_ff,
            etf_excluded_ff,
            etf_delta_pp,
        ) = etf_audit(
            etf,
            candidate,
        )

        row = candidate.to_dict()

        row.update(
            {
                "direction_pass":
                    direction_pass,

                "direction_reason":
                    direction_reason,

                "temporal_pass":
                    temporal_pass,

                "temporal_reason":
                    temporal_reason,

                "concentration_pass":
                    concentration_pass,

                "concentration_reason":
                    concentration_reason,

                "etf_pass":
                    etf_pass,

                "etf_reason":
                    etf_reason,

                "etf_base_ff_pct":
                    etf_base_ff,

                "etf_excluded_ff_pct":
                    etf_excluded_ff,

                "etf_delta_pp":
                    etf_delta_pp,
            }
        )

        audit_rows.append(
            row
        )

    audit = pd.DataFrame(
        audit_rows
    )

    audit[
        "promotion_tier"
    ] = audit.apply(
        classify_candidate,
        axis=1,
    )

    audit[
        "robustness_pass_count"
    ] = (
        audit[
            [
                "direction_pass",
                "temporal_pass",
                "concentration_pass",
                "etf_pass",
            ]
        ]
        .astype(int)
        .sum(
            axis=1
        )
    )

    # Sort with strongest research candidates first within each tier.
    tier_order = {
        "TIER_A_POSITIVE": 1,
        "TIER_C_AVOIDANCE": 2,
        "TIER_B_CONTEXT": 3,
        "TIER_D_NONACTIONABLE": 4,
    }

    audit[
        "_tier_order"
    ] = audit[
        "promotion_tier"
    ].map(
        tier_order
    )

    audit[
        "_abs_validation_lift"
    ] = audit[
        "lift_vs_baseline_pp_validation"
    ].abs()

    audit = (
        audit
        .sort_values(
            [
                "_tier_order",
                "_abs_validation_lift",
                "binary_n_validation",
            ],
            ascending=[
                True,
                False,
                False,
            ],
        )
        .drop(
            columns=[
                "_tier_order",
                "_abs_validation_lift",
            ]
        )
    )

    audit.to_csv(
        AUDIT_OUTPUT,
        index=False,
    )

    tier_a = audit.loc[
        audit[
            "promotion_tier"
        ]
        == "TIER_A_POSITIVE"
    ].copy()

    tier_b = audit.loc[
        audit[
            "promotion_tier"
        ]
        == "TIER_B_CONTEXT"
    ].copy()

    tier_c = audit.loc[
        audit[
            "promotion_tier"
        ]
        == "TIER_C_AVOIDANCE"
    ].copy()

    tier_d = audit.loc[
        audit[
            "promotion_tier"
        ]
        == "TIER_D_NONACTIONABLE"
    ].copy()

    tier_a.to_csv(
        TIER_A_OUTPUT,
        index=False,
    )

    tier_b.to_csv(
        TIER_B_OUTPUT,
        index=False,
    )

    tier_c.to_csv(
        TIER_C_OUTPUT,
        index=False,
    )

    tier_d.to_csv(
        TIER_D_OUTPUT,
        index=False,
    )

    summary = (
        audit[
            "promotion_tier"
        ]
        .value_counts()
        .rename_axis(
            "promotion_tier"
        )
        .reset_index(
            name="state_n"
        )
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    display_cols = [
        "promotion_tier",
        "hypothesis_id",
        "state_a",
        "state_b",
        "binary_n_discovery",
        "favorable_first_pct_discovery",
        "lift_vs_baseline_pp_discovery",
        "binary_n_validation",
        "favorable_first_pct_validation",
        "lift_vs_baseline_pp_validation",
        "incremental_vs_feature_a_pp_validation",
        "incremental_vs_feature_b_pp_validation",
        "direction_pass",
        "temporal_pass",
        "concentration_pass",
        "etf_pass",
    ]

    report_lines = []

    report_lines.append(
        "=" * 88
    )

    report_lines.append(
        "A34.4 / R13 - ROBUST INTERACTION PROMOTION AUDIT V1"
    )

    report_lines.append(
        "=" * 88
    )

    report_lines.append(
        ""
    )

    report_lines.append(
        "BASELINES"
    )

    report_lines.append(
        "-" * 88
    )

    report_lines.append(
        f"Validation overall: "
        f"{baselines['VALIDATION_ALL']:.2f}%"
    )

    report_lines.append(
        f"Validation BEAR:    "
        f"{baselines['DIRECTION::BEAR']:.2f}%"
    )

    report_lines.append(
        f"Validation BULL:    "
        f"{baselines['DIRECTION::BULL']:.2f}%"
    )

    report_lines.append(
        f"Validation older:   "
        f"{baselines['TEMPORAL::VALIDATION_OLDER']:.2f}%"
    )

    report_lines.append(
        f"Validation newer:   "
        f"{baselines['TEMPORAL::VALIDATION_NEWER']:.2f}%"
    )

    report_lines.append(
        ""
    )

    report_lines.append(
        "PROMOTION SUMMARY"
    )

    report_lines.append(
        "-" * 88
    )

    report_lines.append(
        summary.to_string(
            index=False
        )
    )

    for tier_name, frame in [
        (
            "TIER A - ROBUST POSITIVE CANDIDATES",
            tier_a,
        ),
        (
            "TIER C - ROBUST AVOIDANCE CANDIDATES",
            tier_c,
        ),
        (
            "TIER B - SUPPORTING / CONTEXT ONLY",
            tier_b,
        ),
        (
            "TIER D - NONACTIONABLE",
            tier_d,
        ),
    ]:
        report_lines.append(
            ""
        )

        report_lines.append(
            "=" * 88
        )

        report_lines.append(
            tier_name
        )

        report_lines.append(
            "=" * 88
        )

        if frame.empty:
            report_lines.append(
                "NONE"
            )
        else:
            report_lines.append(
                frame[
                    display_cols
                ]
                .to_string(
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
        "=" * 88
    )

    report_lines.append(
        "GOVERNANCE THRESHOLDS"
    )

    report_lines.append(
        "=" * 88
    )

    report_lines.extend(
        [
            f"Strong sample: discovery >= {MIN_DISCOVERY_BINARY_N_STRONG}, "
            f"validation >= {MIN_VALIDATION_BINARY_N_STRONG}",

            f"Strong lift: abs discovery >= "
            f"{MIN_ABS_DISCOVERY_LIFT_PP_STRONG:.1f} pp, "
            f"abs validation >= "
            f"{MIN_ABS_VALIDATION_LIFT_PP_STRONG:.1f} pp",

            f"Incremental interaction: validation adds >= "
            f"{MIN_VALIDATION_INCREMENTAL_VS_EACH_PARENT_PP:.1f} pp "
            f"beyond EACH parent in same direction",

            f"Directional minimum N: {MIN_DIRECTION_BINARY_N}",

            f"Temporal minimum N: {MIN_TEMPORAL_BINARY_N}",

            f"Symbol breadth: symbol_n >= {MIN_SYMBOL_N}",

            f"Concentration: top1 <= {MAX_TOP1_SHARE_PCT:.1f}%, "
            f"top10 <= {MAX_TOP10_SHARE_PCT:.1f}%",

            f"ETF robustness: absolute FF change <= "
            f"{MAX_ETF_FF_DELTA_PP:.1f} pp",

            f"Tier D near-baseline rule: abs validation lift <= "
            f"{MAX_ABS_VALIDATION_LIFT_PP_NONACTIONABLE:.1f} pp",
        ]
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
        "PROMOTION SUMMARY"
    )
    print(
        "=" * 88
    )

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print(
        "=" * 88
    )
    print(
        "TIER A - ROBUST POSITIVE CANDIDATES"
    )
    print(
        "=" * 88
    )

    if tier_a.empty:
        print(
            "NONE"
        )
    else:
        print(
            tier_a[
                display_cols
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
        "TIER C - ROBUST AVOIDANCE CANDIDATES"
    )
    print(
        "=" * 88
    )

    if tier_c.empty:
        print(
            "NONE"
        )
    else:
        print(
            tier_c[
                display_cols
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
        f"Audit:    {AUDIT_OUTPUT}"
    )

    print(
        f"Tier A:   {TIER_A_OUTPUT}"
    )

    print(
        f"Tier B:   {TIER_B_OUTPUT}"
    )

    print(
        f"Tier C:   {TIER_C_OUTPUT}"
    )

    print(
        f"Tier D:   {TIER_D_OUTPUT}"
    )

    print(
        f"Summary:  {SUMMARY_OUTPUT}"
    )

    print(
        f"Report:   {REPORT_OUTPUT}"
    )

    print()
    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()
