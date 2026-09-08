from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

SRC = Path(
    "data/second1m_alt_entry_research_v1/"
    "ae2_session_levels_robustness_v1/"
    "ae2_session_levels_robustness_features_v1.parquet"
)
OUTDIR = Path(
    "data/second1m_alt_entry_research_v1/"
    "ae2_preferred_level_timing_v1"
)

BINARY = {"FAVORABLE_FIRST", "ADVERSE_FIRST"}

def beyond(close: pd.Series, level: pd.Series, direction: pd.Series) -> pd.Series:
    close = pd.to_numeric(close, errors="coerce")
    level = pd.to_numeric(level, errors="coerce")
    bull = direction.astype(str).str.upper().eq("BULL")
    return np.where(bull, close > level, close < level)

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

def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(SRC)

    # Historical Preferred family only:
    # ALL_3_CLEARED + CONSENSUS_OPPOSING.
    p = df[
        df["session_level_clear_state"].eq("ALL_3_CLEARED")
        & df["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")
        & df["outcome"].isin(BINARY)
    ].copy()

    p["direction"] = p["direction"].astype(str).str.upper()
    p["trade_date"] = pd.to_datetime(p["trade_date"])
    p["quarter"] = p["trade_date"].dt.to_period("Q").astype(str)

    # Determine which relevant levels were already closed beyond by C1.
    p["c1_pm_beyond"] = beyond(p["c1_close"], p["pm_directional_level"], p["direction"])
    p["c1_ah_beyond"] = beyond(p["c1_close"], p["ah_directional_level"], p["direction"])
    p["c1_pd_beyond"] = beyond(p["c1_close"], p["pd_directional_level"], p["direction"])

    p["c2_pm_beyond_calc"] = beyond(p["c2_close"], p["pm_directional_level"], p["direction"])
    p["c2_ah_beyond_calc"] = beyond(p["c2_close"], p["ah_directional_level"], p["direction"])
    p["c2_pd_beyond_calc"] = beyond(p["c2_close"], p["pd_directional_level"], p["direction"])

    p["c1_levels_cleared_n"] = (
        p[["c1_pm_beyond", "c1_ah_beyond", "c1_pd_beyond"]].astype(int).sum(axis=1)
    )
    p["c2_levels_cleared_calc_n"] = (
        p[["c2_pm_beyond_calc", "c2_ah_beyond_calc", "c2_pd_beyond_calc"]]
        .astype(int).sum(axis=1)
    )
    p["levels_newly_cleared_by_c2_n"] = (
        p["c2_levels_cleared_calc_n"] - p["c1_levels_cleared_n"]
    )

    def pattern(row):
        parts = []
        if row["c1_pm_beyond"]: parts.append("PM")
        if row["c1_ah_beyond"]: parts.append("AH")
        if row["c1_pd_beyond"]: parts.append("PD")
        return "+".join(parts) if parts else "NONE"

    p["c1_cleared_pattern"] = p.apply(pattern, axis=1)

    # Audit: Preferred ALL_3_CLEARED should mean C2 is beyond all 3 by close.
    parity_bad = int((p["c2_levels_cleared_calc_n"] != 3).sum())

    keep = [
        "symbol","trade_date","direction","outcome","research_period","quarter",
        "c1_close","c2_close",
        "pm_directional_level","ah_directional_level","pd_directional_level",
        "c1_pm_beyond","c1_ah_beyond","c1_pd_beyond",
        "c2_pm_beyond_calc","c2_ah_beyond_calc","c2_pd_beyond_calc",
        "c1_levels_cleared_n","c2_levels_cleared_calc_n",
        "levels_newly_cleared_by_c2_n","c1_cleared_pattern",
        "c2_break_level_n","c2_break_count_state",
    ]
    keep = [c for c in keep if c in p.columns]
    p[keep].to_parquet(OUTDIR / "a38_preferred_level_timing_events_v1.parquet", index=False)
    p[keep].to_csv(OUTDIR / "a38_preferred_level_timing_events_v1.csv", index=False)

    count_perf = summarize(
        p, ["research_period", "direction", "c1_levels_cleared_n"]
    )
    count_perf.to_csv(OUTDIR / "a38_c1_cleared_count_performance_v1.csv", index=False)

    burden_perf = summarize(
        p, ["research_period", "direction", "levels_newly_cleared_by_c2_n"]
    )
    burden_perf.to_csv(OUTDIR / "a38_c2_new_clear_burden_performance_v1.csv", index=False)

    pattern_perf = summarize(
        p, ["research_period", "direction", "c1_cleared_pattern"]
    )
    pattern_perf.to_csv(OUTDIR / "a38_c1_cleared_pattern_performance_v1.csv", index=False)

    quarter_perf = summarize(
        p, ["quarter", "c1_levels_cleared_n"]
    )
    quarter_perf.to_csv(OUTDIR / "a38_c1_cleared_count_quarter_v1.csv", index=False)

    print("=" * 106)
    print("A38.1 - PREFERRED LEVEL-TIMING / C2 BREAKOUT-BURDEN AUDIT")
    print("=" * 106)
    print(f"Preferred binary events: {len(p):,}")
    print(f"C2 all-3-close parity violations: {parity_bad:,}")
    print()

    print("C1 LEVELS ALREADY CLEARED — DISCOVERY / VALIDATION")
    print("-" * 106)
    pooled = summarize(p, ["research_period", "c1_levels_cleared_n"])
    print(pooled.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print()
    print("C1 LEVELS ALREADY CLEARED — BY DIRECTION")
    print("-" * 106)
    print(count_perf.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print()
    print("C1 CLEARED PATTERN — pooled directions, cells N >= 15")
    print("-" * 106)
    pat = summarize(p, ["research_period", "c1_cleared_pattern"])
    pat = pat[pat["binary_n"] >= 15]
    print(pat.to_string(index=False, float_format=lambda x: f"{x:.2f}") if len(pat) else "NONE")

    print()
    print("RESULT: LEVEL-TIMING AUDIT COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
