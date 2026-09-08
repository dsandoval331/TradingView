from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


# =============================================================================
# A35.4 / R14 — FINAL TEMPORAL + 2025Q3 FAILURE AUDIT V1
# =============================================================================
#
# PURPOSE
# -------
# 1) Test quarter-by-quarter ordering of:
#       PREFERRED > NEUTRAL > AVOID
#
# 2) Diagnose the known 2025Q3 PREFERRED failure using ONLY already-frozen
#    Alternative C2 context variables and family flags.
#
# NO new factor discovery.
# NO threshold optimization.
# NO post-hoc rule creation.
#
# IMPORTANT:
# A34.4 used validation evidence. This remains model-development research,
# not untouched prospective/OOS validation.
# =============================================================================


ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

INPUT_PATH = (
    RESEARCH_ROOT
    / "ae2_candidate_models_v1"
    / "ae2_candidate_model_events_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_candidate_model_temporal_audit_v1"
)

QUARTER_STATE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_quarter_state_ordering_v1.csv"
)

QUARTER_SPREAD_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_quarter_state_spreads_v1.csv"
)

Q3_DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_2025q3_preferred_direction_v1.csv"
)

Q3_CONTEXT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_2025q3_preferred_context_v1.csv"
)

Q3_SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_2025q3_preferred_symbol_v1.csv"
)

PREFERRED_QUARTER_CONTEXT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_preferred_quarter_context_v1.csv"
)

REPORT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_final_temporal_audit_report_v1.txt"
)

EXPECTED_EVENTS = 8307
EXPECTED_SYMBOLS = 112


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


def summarize_group(x: pd.DataFrame) -> dict:
    favorable_n = int(
        (x["outcome"] == "FAVORABLE_FIRST").sum()
    )

    adverse_n = int(
        (x["outcome"] == "ADVERSE_FIRST").sum()
    )

    binary_n = favorable_n + adverse_n

    ff = (
        100.0 * favorable_n / binary_n
        if binary_n
        else np.nan
    )

    return {
        "total_n": int(len(x)),
        "binary_n": binary_n,
        "favorable_n": favorable_n,
        "adverse_n": adverse_n,
        "favorable_first_pct": ff,
        "avg_mfe_pct": x["final_mfe_pct"].mean(),
        "avg_mae_pct": x["final_mae_pct"].mean(),
        "median_mfe_pct": x["final_mfe_pct"].median(),
        "median_mae_pct": x["final_mae_pct"].median(),
        "symbol_n": x["symbol"].nunique(),
        "trade_date_n": x["trade_date"].nunique(),
    }


def state_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for (quarter, state), x in df.groupby(
        ["quarter", "candidate_triage_state"],
        dropna=False,
    ):
        rows.append(
            {
                "quarter": quarter,
                "candidate_triage_state": state,
                **summarize_group(x),
            }
        )

    return pd.DataFrame(rows)


def build_quarter_spreads(
    quarter_state: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for quarter, q in quarter_state.groupby("quarter"):
        lookup = {
            str(r["candidate_triage_state"]): r
            for _, r in q.iterrows()
        }

        preferred = lookup.get("PREFERRED")
        neutral = lookup.get("NEUTRAL")
        avoid = lookup.get("AVOID")

        if (
            preferred is None
            or neutral is None
            or avoid is None
        ):
            rows.append(
                {
                    "quarter": quarter,
                    "preferred_ff_pct": np.nan,
                    "neutral_ff_pct": np.nan,
                    "avoid_ff_pct": np.nan,
                    "preferred_minus_neutral_pp": np.nan,
                    "neutral_minus_avoid_pp": np.nan,
                    "preferred_minus_avoid_pp": np.nan,
                    "strict_order_pass": False,
                    "missing_state": True,
                }
            )
            continue

        p = float(preferred["favorable_first_pct"])
        n = float(neutral["favorable_first_pct"])
        a = float(avoid["favorable_first_pct"])

        rows.append(
            {
                "quarter": quarter,
                "preferred_binary_n": int(preferred["binary_n"]),
                "neutral_binary_n": int(neutral["binary_n"]),
                "avoid_binary_n": int(avoid["binary_n"]),
                "preferred_ff_pct": p,
                "neutral_ff_pct": n,
                "avoid_ff_pct": a,
                "preferred_minus_neutral_pp": p - n,
                "neutral_minus_avoid_pp": n - a,
                "preferred_minus_avoid_pp": p - a,
                "strict_order_pass": bool(p > n > a),
                "missing_state": False,
            }
        )

    return pd.DataFrame(rows)


def categorical_context_table(
    preferred: pd.DataFrame,
    column: str,
) -> pd.DataFrame:
    rows = []

    for quarter, q in preferred.groupby("quarter"):
        binary_q = q.loc[
            q["outcome"].isin(
                ["FAVORABLE_FIRST", "ADVERSE_FIRST"]
            )
        ]

        quarter_binary_n = len(binary_q)

        for state, x in binary_q.groupby(
            column,
            dropna=False,
        ):
            stats = summarize_group(x)

            rows.append(
                {
                    "feature": column,
                    "quarter": quarter,
                    "state": state,
                    "share_of_quarter_binary_pct": (
                        100.0 * len(x) / quarter_binary_n
                        if quarter_binary_n
                        else np.nan
                    ),
                    **stats,
                }
            )

    return pd.DataFrame(rows)


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

    df = pd.read_parquet(INPUT_PATH)

    if len(df) != EXPECTED_EVENTS:
        raise RuntimeError(
            f"Expected {EXPECTED_EVENTS:,} events, found {len(df):,}."
        )

    if df["symbol"].nunique() != EXPECTED_SYMBOLS:
        raise RuntimeError(
            f"Expected {EXPECTED_SYMBOLS} symbols, "
            f"found {df['symbol'].nunique()}."
        )

    df["trade_date"] = pd.to_datetime(
        df["trade_date"],
        errors="coerce",
    )

    print("=" * 96)
    print(
        "A35.4 / R14 - FINAL TEMPORAL + 2025Q3 FAILURE AUDIT V1"
    )
    print("=" * 96)
    print(f"Events:  {len(df):,}")
    print(f"Symbols: {df['symbol'].nunique():,}")
    print()

    # =========================================================================
    # 1. QUARTERLY TRIAGE ORDERING
    # =========================================================================

    quarter_state = state_summary(df)

    quarter_state.to_csv(
        QUARTER_STATE_OUTPUT,
        index=False,
    )

    quarter_spreads = build_quarter_spreads(
        quarter_state
    )

    quarter_spreads.to_csv(
        QUARTER_SPREAD_OUTPUT,
        index=False,
    )

    strict_pass_n = int(
        quarter_spreads["strict_order_pass"].sum()
    )

    strict_total_n = int(
        (~quarter_spreads["missing_state"]).sum()
    )

    # =========================================================================
    # 2. 2025Q3 PREFERRED FAILURE DIAGNOSTIC
    # =========================================================================

    preferred = df.loc[
        df["candidate_triage_state"] == "PREFERRED"
    ].copy()

    q3 = preferred.loc[
        preferred["quarter"] == "2025Q3"
    ].copy()

    other_preferred = preferred.loc[
        preferred["quarter"] != "2025Q3"
    ].copy()

    # Direction
    q3_direction_rows = []

    for label, sample in [
        ("2025Q3", q3),
        ("OTHER_PREFERRED_QUARTERS", other_preferred),
    ]:
        for direction, x in sample.groupby("direction"):
            q3_direction_rows.append(
                {
                    "sample": label,
                    "direction": direction,
                    **summarize_group(x),
                }
            )

    q3_direction = pd.DataFrame(
        q3_direction_rows
    )

    q3_direction.to_csv(
        Q3_DIRECTION_OUTPUT,
        index=False,
    )

    # Frozen context variables only.
    context_features = [
        "market_prior_5d_consensus",
        "market_3idx_prior_5d_state",
        "relative_multi_horizon_state",
        "session_level_clear_state",
        "exhaustion_state",
    ]

    context_frames = []

    for feature in context_features:
        if feature not in preferred.columns:
            continue

        context_frames.append(
            categorical_context_table(
                preferred,
                feature,
            )
        )

    preferred_quarter_context = pd.concat(
        context_frames,
        ignore_index=True,
    )

    preferred_quarter_context.to_csv(
        PREFERRED_QUARTER_CONTEXT_OUTPUT,
        index=False,
    )

    # Direct Q3 vs all-other comparison for each frozen state.
    q3_context_rows = []

    for feature in context_features:
        if feature not in preferred.columns:
            continue

        for state in sorted(
            preferred[feature]
            .astype(str)
            .unique()
        ):
            for label, sample in [
                ("2025Q3", q3),
                (
                    "OTHER_PREFERRED_QUARTERS",
                    other_preferred,
                ),
            ]:
                binary_sample = sample.loc[
                    sample["outcome"].isin(
                        [
                            "FAVORABLE_FIRST",
                            "ADVERSE_FIRST",
                        ]
                    )
                ]

                x = binary_sample.loc[
                    binary_sample[feature].astype(str)
                    == state
                ]

                if x.empty:
                    continue

                stats = summarize_group(x)

                q3_context_rows.append(
                    {
                        "feature": feature,
                        "state": state,
                        "sample": label,
                        "share_of_sample_binary_pct": (
                            100.0
                            * len(x)
                            / len(binary_sample)
                            if len(binary_sample)
                            else np.nan
                        ),
                        **stats,
                    }
                )

    q3_context = pd.DataFrame(
        q3_context_rows
    )

    q3_context.to_csv(
        Q3_CONTEXT_OUTPUT,
        index=False,
    )

    # Symbol concentration / breadth for Q3 vs other preferred quarters.
    q3_symbol_rows = []

    for label, sample in [
        ("2025Q3", q3),
        (
            "OTHER_PREFERRED_QUARTERS",
            other_preferred,
        ),
    ]:
        binary_sample = sample.loc[
            sample["outcome"].isin(
                [
                    "FAVORABLE_FIRST",
                    "ADVERSE_FIRST",
                ]
            )
        ]

        counts = (
            binary_sample["symbol"]
            .value_counts()
            .sort_values(
                ascending=False
            )
        )

        total = len(binary_sample)

        for symbol, n in counts.items():
            x = binary_sample.loc[
                binary_sample["symbol"] == symbol
            ]

            stats = summarize_group(x)

            q3_symbol_rows.append(
                {
                    "sample": label,
                    "symbol": symbol,
                    "sample_share_pct": (
                        100.0 * n / total
                        if total
                        else np.nan
                    ),
                    **stats,
                }
            )

    q3_symbol = pd.DataFrame(
        q3_symbol_rows
    )

    q3_symbol.to_csv(
        Q3_SYMBOL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # TERMINAL REPORT
    # =========================================================================

    print("=" * 96)
    print("QUARTERLY TRIAGE STATES")
    print("=" * 96)

    print(
        quarter_state[
            [
                "quarter",
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
                "quarter",
                "candidate_triage_state",
            ]
        )
        .to_string(
            index=False,
            float_format=lambda z: f"{z:.2f}",
        )
    )

    print()
    print("=" * 96)
    print("QUARTERLY STATE ORDERING / SPREADS")
    print("=" * 96)

    print(
        quarter_spreads.to_string(
            index=False,
            float_format=lambda z: f"{z:.2f}",
        )
    )

    print()
    print(
        f"Strict PREFERRED > NEUTRAL > AVOID ordering: "
        f"{strict_pass_n}/{strict_total_n} quarters"
    )

    print()
    print("=" * 96)
    print("2025Q3 PREFERRED - DIRECTION DIAGNOSTIC")
    print("=" * 96)

    print(
        q3_direction[
            [
                "sample",
                "direction",
                "binary_n",
                "favorable_first_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
                "symbol_n",
            ]
        ]
        .to_string(
            index=False,
            float_format=lambda z: f"{z:.2f}",
        )
    )

    print()
    print("=" * 96)
    print("2025Q3 PREFERRED - FROZEN CONTEXT COMPARISON")
    print("=" * 96)

    if q3_context.empty:
        print("No context rows.")
    else:
        print(
            q3_context[
                [
                    "feature",
                    "state",
                    "sample",
                    "share_of_sample_binary_pct",
                    "binary_n",
                    "favorable_first_pct",
                    "avg_mfe_pct",
                    "avg_mae_pct",
                    "symbol_n",
                ]
            ]
            .sort_values(
                [
                    "feature",
                    "state",
                    "sample",
                ]
            )
            .to_string(
                index=False,
                float_format=lambda z: f"{z:.2f}",
            )
        )

    print()
    print("=" * 96)
    print("2025Q3 PREFERRED - SYMBOL CONCENTRATION")
    print("=" * 96)

    for label in [
        "2025Q3",
        "OTHER_PREFERRED_QUARTERS",
    ]:
        x = q3_symbol.loc[
            q3_symbol["sample"] == label
        ].copy()

        print()
        print(label)

        if x.empty:
            print("NONE")
            continue

        print(
            x[
                [
                    "symbol",
                    "binary_n",
                    "sample_share_pct",
                    "favorable_first_pct",
                ]
            ]
            .head(15)
            .to_string(
                index=False,
                float_format=lambda z: f"{z:.2f}",
            )
        )

    # =========================================================================
    # TEXT REPORT
    # =========================================================================

    report = []

    report.append(
        "A35.4 / R14 - FINAL TEMPORAL + 2025Q3 FAILURE AUDIT V1"
    )
    report.append("")
    report.append(
        "This is model-development research, not untouched OOS validation."
    )
    report.append("")
    report.append("QUARTERLY TRIAGE STATES")
    report.append(
        quarter_state.to_string(
            index=False,
            float_format=lambda z: f"{z:.2f}",
        )
    )
    report.append("")
    report.append("QUARTERLY STATE SPREADS")
    report.append(
        quarter_spreads.to_string(
            index=False,
            float_format=lambda z: f"{z:.2f}",
        )
    )
    report.append("")
    report.append(
        f"Strict ordering pass: {strict_pass_n}/{strict_total_n}"
    )
    report.append("")
    report.append("2025Q3 DIRECTION")
    report.append(
        q3_direction.to_string(
            index=False,
            float_format=lambda z: f"{z:.2f}",
        )
    )
    report.append("")
    report.append("2025Q3 FROZEN CONTEXT")
    report.append(
        q3_context.to_string(
            index=False,
            float_format=lambda z: f"{z:.2f}",
        )
    )

    REPORT_OUTPUT.write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    print()
    print("=" * 96)
    print("OUTPUTS")
    print("=" * 96)
    print(f"Quarter states:   {QUARTER_STATE_OUTPUT}")
    print(f"Quarter spreads:  {QUARTER_SPREAD_OUTPUT}")
    print(f"Q3 direction:     {Q3_DIRECTION_OUTPUT}")
    print(f"Q3 context:       {Q3_CONTEXT_OUTPUT}")
    print(f"Q3 symbols:       {Q3_SYMBOL_OUTPUT}")
    print(
        f"Quarter context:  "
        f"{PREFERRED_QUARTER_CONTEXT_OUTPUT}"
    )
    print(f"Report:           {REPORT_OUTPUT}")
    print()
    print("RESULT: COMPLETE")


if __name__ == "__main__":
    main()
