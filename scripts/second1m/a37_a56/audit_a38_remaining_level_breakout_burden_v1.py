from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

SRC = Path(
    "data/second1m_alt_entry_research_v1/"
    "ae2_preferred_level_timing_v1/"
    "a38_preferred_level_timing_events_v1.parquet"
)
OUTDIR = SRC.parent

BINARY = {"FAVORABLE_FIRST", "ADVERSE_FIRST"}

def summarize(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    x = df[df["outcome"].isin(BINARY)].copy()
    x["ff"] = x["outcome"].eq("FAVORABLE_FIRST").astype(int)
    out = (
        x.groupby(group_cols, dropna=False)
         .agg(binary_n=("ff", "size"), favorable_n=("ff", "sum"))
         .reset_index()
    )
    out["adverse_n"] = out["binary_n"] - out["favorable_n"]
    out["ff_pct"] = 100.0 * out["favorable_n"] / out["binary_n"]
    return out

def remaining_level(row) -> str:
    if row["c1_levels_cleared_n"] != 2:
        return "NOT_ONE_REMAINING"
    cleared = {
        "PM": bool(row["c1_pm_beyond"]),
        "AH": bool(row["c1_ah_beyond"]),
        "PD": bool(row["c1_pd_beyond"]),
    }
    remaining = [k for k, v in cleared.items() if not v]
    return remaining[0] if len(remaining) == 1 else "UNKNOWN"

def main():
    df = pd.read_parquet(SRC)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["quarter"] = df["trade_date"].dt.to_period("Q").astype(str)
    df["remaining_level_for_c2"] = df.apply(remaining_level, axis=1)

    # Focus: exactly two cleared by C1 => one structural level remains for C2.
    one = df[df["c1_levels_cleared_n"].eq(2)].copy()

    pooled = summarize(one, ["research_period", "remaining_level_for_c2"])
    by_dir = summarize(one, ["research_period", "direction", "remaining_level_for_c2"])
    by_q = summarize(one, ["quarter", "remaining_level_for_c2"])

    pooled.to_csv(OUTDIR / "a38_remaining_level_performance_v1.csv", index=False)
    by_dir.to_csv(OUTDIR / "a38_remaining_level_direction_v1.csv", index=False)
    by_q.to_csv(OUTDIR / "a38_remaining_level_quarter_v1.csv", index=False)

    # Also show burden count as a direct inverse of C1-cleared count.
    burden = summarize(df, ["research_period", "levels_newly_cleared_by_c2_n"])
    burden_dir = summarize(df, ["research_period", "direction", "levels_newly_cleared_by_c2_n"])
    burden.to_csv(OUTDIR / "a38_c2_breakout_burden_summary_v1.csv", index=False)
    burden_dir.to_csv(OUTDIR / "a38_c2_breakout_burden_direction_v1.csv", index=False)

    print("=" * 110)
    print("A38.2 - WHICH LEVEL REMAINS FOR C2? / BREAKOUT-BURDEN STRUCTURE")
    print("=" * 110)

    print("\nONE LEVEL REMAINING FOR C2 — DISCOVERY / VALIDATION")
    print("-" * 110)
    print(pooled.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print("\nONE LEVEL REMAINING FOR C2 — BY DIRECTION")
    print("-" * 110)
    print(by_dir.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print("\nONE LEVEL REMAINING FOR C2 — BY QUARTER (cells N >= 8)")
    print("-" * 110)
    qshow = by_q[by_q["binary_n"].ge(8)]
    print(qshow.to_string(index=False, float_format=lambda x: f"{x:.2f}") if len(qshow) else "NONE")

    print("\nC2 NEW-CLEAR BURDEN — DISCOVERY / VALIDATION")
    print("-" * 110)
    print(burden.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print("\nC2 NEW-CLEAR BURDEN — BY DIRECTION")
    print("-" * 110)
    print(burden_dir.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print()
    print("RESULT: REMAINING-LEVEL / BURDEN AUDIT COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
