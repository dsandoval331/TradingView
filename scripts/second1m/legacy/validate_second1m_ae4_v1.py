from __future__ import annotations

from pathlib import Path

import pandas as pd


# ============================================================================
# CONFIG
# ============================================================================

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

EVENTS_PATH = (
    RESEARCH_ROOT
    / "second1m_alt_entry_events_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae4_validation_v1"
)

TEMPORAL_OUTPUT = (
    OUTPUT_ROOT
    / "ae4_temporal_validation_v1.csv"
)

PARENT_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_c3_confirmation_parent_v1.csv"
)

ENTRY_OUTPUT = (
    OUTPUT_ROOT
    / "ae4_entry_timing_comparison_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae4_symbol_validation_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae4_quarter_validation_v1.csv"
)


# ============================================================================
# SUMMARY HELPER
# ============================================================================

def summarize(
    df: pd.DataFrame,
    group_cols: list[str],
) -> pd.DataFrame:

    rows = []

    if not group_cols:
        groups = [((), df)]
    else:
        groups = df.groupby(
            group_cols,
            dropna=False,
        )

    for keys, x in groups:

        if not isinstance(keys, tuple):
            keys = (keys,)

        base = (
            dict(zip(group_cols, keys))
            if group_cols
            else {}
        )

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

        ff_pct = (
            100.0 * favorable_n / binary_n
            if binary_n
            else None
        )

        rows.append(
            {
                **base,
                "total_n": int(len(x)),
                "binary_n": binary_n,
                "favorable_n": favorable_n,
                "adverse_n": adverse_n,
                "both_n": both_n,
                "unresolved_n": unresolved_n,
                "favorable_first_pct": ff_pct,
                "avg_mfe_pct": x["final_mfe_pct"].mean(),
                "avg_mae_pct": x["final_mae_pct"].mean(),
                "median_mfe_pct": x["final_mfe_pct"].median(),
                "median_mae_pct": x["final_mae_pct"].median(),
                "symbol_n": x["symbol"].nunique(),
                "trade_date_n": x["trade_date"].nunique(),
            }
        )

    return pd.DataFrame(rows)


# ============================================================================
# LOAD
# ============================================================================

def main() -> None:

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not EVENTS_PATH.exists():
        raise FileNotFoundError(
            f"Event file not found: {EVENTS_PATH}"
        )

    events = pd.read_parquet(EVENTS_PATH)

    events["trade_date"] = pd.to_datetime(
        events["trade_date"]
    )

    events["entry_timestamp"] = pd.to_datetime(
        events["entry_timestamp"],
        utc=True,
    )

    print("=" * 80)
    print("AE4 RECLAIM + C3 VALIDATION V1")
    print("=" * 80)

    print(f"Event rows: {len(events):,}")

    ae2 = events.loc[
        events["architecture"] == "AE2_RECLAIM"
    ].copy()

    ae4 = events.loc[
        events["architecture"] == "AE4_RECLAIM_C3"
    ].copy()

    if ae2.empty:
        raise RuntimeError("AE2 population is empty.")

    if ae4.empty:
        raise RuntimeError("AE4 population is empty.")

    print(f"AE2 rows:    {len(ae2):,}")
    print(f"AE4 rows:    {len(ae4):,}")

    # ========================================================================
    # UNIQUE EVENT KEY
    # ========================================================================

    key_cols = [
        "symbol",
        "trade_date",
        "direction",
    ]

    ae2_duplicate_n = int(
        ae2.duplicated(key_cols).sum()
    )

    ae4_duplicate_n = int(
        ae4.duplicated(key_cols).sum()
    )

    if ae2_duplicate_n:
        raise RuntimeError(
            f"AE2 duplicate event keys: {ae2_duplicate_n}"
        )

    if ae4_duplicate_n:
        raise RuntimeError(
            f"AE4 duplicate event keys: {ae4_duplicate_n}"
        )

    # ========================================================================
    # CONFIRMATION MEMBERSHIP
    # ========================================================================

    ae4_keys = (
        ae4[key_cols]
        .assign(c3_confirmed=True)
    )

    parent = ae2.merge(
        ae4_keys,
        on=key_cols,
        how="left",
    )

    parent["c3_confirmed"] = (
        parent["c3_confirmed"]
        .fillna(False)
        .astype(bool)
    )

    parent["confirmation_group"] = parent[
        "c3_confirmed"
    ].map(
        {
            True: "C3_CONFIRMED",
            False: "NO_C3_CONFIRMATION",
        }
    )

    # ========================================================================
    # A23.1 — COMMON C2-ENTRY PARENT COMPARISON
    # ========================================================================

    parent_summary = summarize(
        parent,
        [
            "confirmation_group",
        ],
    )

    parent_direction = summarize(
        parent,
        [
            "confirmation_group",
            "direction",
        ],
    )

    parent_combined = pd.concat(
        [
            parent_summary.assign(
                direction="ALL"
            ),
            parent_direction,
        ],
        ignore_index=True,
        sort=False,
    )

    parent_combined.to_csv(
        PARENT_OUTPUT,
        index=False,
    )

    # ========================================================================
    # A23.2 — ACTUAL ENTRY COMPARISON
    #
    # Same confirmed population:
    #   AE2 = C2 close entry
    #   AE4 = C3 close entry
    #
    # This isolates the effect of waiting for C3 on the exact same setups.
    # ========================================================================

    confirmed_ae2 = parent.loc[
        parent["c3_confirmed"]
    ].copy()

    confirmed_ae2["entry_version"] = (
        "CONFIRMED_AE2_ENTER_C2"
    )

    ae4_entry = ae4.copy()

    ae4_entry["entry_version"] = (
        "AE4_ENTER_C3"
    )

    entry_compare = pd.concat(
        [
            confirmed_ae2,
            ae4_entry,
        ],
        ignore_index=True,
        sort=False,
    )

    entry_summary = summarize(
        entry_compare,
        [
            "entry_version",
        ],
    )

    entry_direction = summarize(
        entry_compare,
        [
            "entry_version",
            "direction",
        ],
    )

    entry_combined = pd.concat(
        [
            entry_summary.assign(
                direction="ALL"
            ),
            entry_direction,
        ],
        ignore_index=True,
        sort=False,
    )

    entry_combined.to_csv(
        ENTRY_OUTPUT,
        index=False,
    )

    # ========================================================================
    # A23.3 — TEMPORAL VALIDATION
    # ========================================================================

    unique_dates = sorted(
        ae4["trade_date"].dropna().unique()
    )

    if len(unique_dates) < 2:
        raise RuntimeError(
            "Insufficient AE4 dates for temporal validation."
        )

    midpoint_index = len(unique_dates) // 2

    midpoint_date = pd.Timestamp(
        unique_dates[midpoint_index]
    )

    ae4["temporal_half"] = (
        ae4["trade_date"]
        .apply(
            lambda x:
                "OLDEST_HALF"
                if x < midpoint_date
                else "NEWEST_HALF"
        )
    )

    temporal_summary = summarize(
        ae4,
        [
            "temporal_half",
        ],
    )

    temporal_direction = summarize(
        ae4,
        [
            "temporal_half",
            "direction",
        ],
    )

    temporal_combined = pd.concat(
        [
            temporal_summary.assign(
                direction="ALL"
            ),
            temporal_direction,
        ],
        ignore_index=True,
        sort=False,
    )

    temporal_combined[
        "midpoint_date"
    ] = midpoint_date.date()

    temporal_combined.to_csv(
        TEMPORAL_OUTPUT,
        index=False,
    )

    # ========================================================================
    # A23.4 — QUARTER STABILITY
    # ========================================================================

    ae4["quarter"] = (
        ae4["trade_date"]
        .dt
        .to_period("Q")
        .astype(str)
    )

    quarter_summary = summarize(
        ae4,
        ["quarter"],
    )

    quarter_direction = summarize(
        ae4,
        [
            "quarter",
            "direction",
        ],
    )

    quarter_combined = pd.concat(
        [
            quarter_summary.assign(
                direction="ALL"
            ),
            quarter_direction,
        ],
        ignore_index=True,
        sort=False,
    )

    quarter_combined.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # ========================================================================
    # A23.5 — SYMBOL BREADTH
    # ========================================================================

    symbol_summary = summarize(
        ae4,
        ["symbol"],
    )

    symbol_summary = symbol_summary.sort_values(
        [
            "binary_n",
            "symbol",
        ],
        ascending=[
            False,
            True,
        ],
    ).reset_index(drop=True)

    total_ae4 = len(ae4)

    symbol_summary[
        "share_of_ae4_pct"
    ] = (
        100.0
        * symbol_summary["total_n"]
        / total_ae4
    )

    symbol_summary.to_csv(
        SYMBOL_OUTPUT,
        index=False,
    )

    top_1_share = (
        symbol_summary[
            "share_of_ae4_pct"
        ].iloc[0]
        if not symbol_summary.empty
        else 0.0
    )

    top_5_share = (
        symbol_summary[
            "share_of_ae4_pct"
        ].head(5).sum()
    )

    top_10_share = (
        symbol_summary[
            "share_of_ae4_pct"
        ].head(10).sum()
    )

    # ========================================================================
    # PRINT RESULTS
    # ========================================================================

    print()
    print("=" * 80)
    print("A23.1 — AE2 PARENT: DOES C3 CONFIRMATION DISCRIMINATE?")
    print("=" * 80)

    parent_display = [
        "confirmation_group",
        "direction",
        "total_n",
        "binary_n",
        "favorable_first_pct",
        "avg_mfe_pct",
        "avg_mae_pct",
        "symbol_n",
    ]

    print(
        parent_combined[
            parent_display
        ].to_string(
            index=False,
            float_format=lambda x:
                f"{x:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("A23.2 — SAME CONFIRMED SETUPS: C2 ENTRY VS C3 ENTRY")
    print("=" * 80)

    entry_display = [
        "entry_version",
        "direction",
        "total_n",
        "binary_n",
        "favorable_first_pct",
        "avg_mfe_pct",
        "avg_mae_pct",
        "median_mfe_pct",
        "median_mae_pct",
    ]

    print(
        entry_combined[
            entry_display
        ].to_string(
            index=False,
            float_format=lambda x:
                f"{x:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("A23.3 — AE4 TEMPORAL HALF VALIDATION")
    print("=" * 80)

    temporal_display = [
        "temporal_half",
        "direction",
        "total_n",
        "binary_n",
        "favorable_first_pct",
        "avg_mfe_pct",
        "avg_mae_pct",
    ]

    print(
        temporal_combined[
            temporal_display
        ].to_string(
            index=False,
            float_format=lambda x:
                f"{x:.2f}",
        )
    )

    print(
        f"\nTemporal midpoint: "
        f"{midpoint_date.date()}"
    )

    print()
    print("=" * 80)
    print("A23.4 — AE4 QUARTER STABILITY")
    print("=" * 80)

    quarter_display = [
        "quarter",
        "direction",
        "total_n",
        "binary_n",
        "favorable_first_pct",
    ]

    print(
        quarter_combined[
            quarter_display
        ].to_string(
            index=False,
            float_format=lambda x:
                f"{x:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("A23.5 — AE4 SYMBOL BREADTH")
    print("=" * 80)

    print(
        f"AE4 symbols:     "
        f"{ae4['symbol'].nunique()}"
    )

    print(
        f"Top-1 share:     "
        f"{top_1_share:.2f}%"
    )

    print(
        f"Top-5 share:     "
        f"{top_5_share:.2f}%"
    )

    print(
        f"Top-10 share:    "
        f"{top_10_share:.2f}%"
    )

    print()
    print("TOP 15 BY SAMPLE SIZE")
    print("-" * 80)

    symbol_display = [
        "symbol",
        "total_n",
        "binary_n",
        "favorable_first_pct",
        "share_of_ae4_pct",
    ]

    print(
        symbol_summary[
            symbol_display
        ]
        .head(15)
        .to_string(
            index=False,
            float_format=lambda x:
                f"{x:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("OUTPUTS")
    print("=" * 80)

    print(
        f"Parent comparison: "
        f"{PARENT_OUTPUT}"
    )

    print(
        f"Entry comparison:  "
        f"{ENTRY_OUTPUT}"
    )

    print(
        f"Temporal:          "
        f"{TEMPORAL_OUTPUT}"
    )

    print(
        f"Quarter:           "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Symbols:           "
        f"{SYMBOL_OUTPUT}"
    )

    print()
    print("RESULT: COMPLETE")


if __name__ == "__main__":
    main()