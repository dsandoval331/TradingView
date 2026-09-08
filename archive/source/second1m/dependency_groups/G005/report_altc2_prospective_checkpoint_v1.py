from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

DEFAULT_LEDGER = (
    Path("data")
    / "second1m_alt_entry_prospective_v1"
    / "events"
    / "altc2_prospective_event_ledger_v1.parquet"
)

STATE_MINIMUMS = {
    "PREFERRED": 200,
    "NEUTRAL": 500,
    "AVOID": 300,
}

DIRECTION_MINIMUMS = {
    ("PREFERRED", "BULL"): 60,
    ("PREFERRED", "BEAR"): 60,
    ("AVOID", "BULL"): 80,
    ("AVOID", "BEAR"): 80,
}

PREFERRED_CHECKPOINTS = [50, 100, 200]

BINARY_OUTCOMES = {"FAVORABLE_FIRST", "ADVERSE_FIRST"}


def pct(n: int, d: int) -> float | None:
    return (100.0 * n / d) if d else None


def fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}%"


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in [
        "candidate_triage_state",
        "direction",
        "outcome",
        "symbol",
    ]:
        if col in out.columns:
            out[col] = (
                out[col]
                .astype(str)
                .str.upper()
                .str.strip()
            )

    return out


def state_row(df: pd.DataFrame, state: str) -> dict:
    part = df[df["candidate_triage_state"] == state].copy()
    binary = part[part["outcome"].isin(BINARY_OUTCOMES)]
    favorable = int((binary["outcome"] == "FAVORABLE_FIRST").sum())
    adverse = int((binary["outcome"] == "ADVERSE_FIRST").sum())

    return {
        "state": state,
        "total_n": len(part),
        "binary_n": len(binary),
        "favorable_n": favorable,
        "adverse_n": adverse,
        "ff_pct": pct(favorable, len(binary)),
    }


def direction_row(df: pd.DataFrame, state: str, direction: str) -> dict:
    part = df[
        (df["candidate_triage_state"] == state)
        & (df["direction"] == direction)
    ].copy()

    binary = part[part["outcome"].isin(BINARY_OUTCOMES)]
    favorable = int((binary["outcome"] == "FAVORABLE_FIRST").sum())

    return {
        "state": state,
        "direction": direction,
        "total_n": len(part),
        "binary_n": len(binary),
        "ff_pct": pct(favorable, len(binary)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report frozen Alternative C2 prospective validation progress."
    )
    parser.add_argument(
        "--ledger",
        default=str(DEFAULT_LEDGER),
        help="Path to prospective ledger parquet.",
    )
    args = parser.parse_args()

    ledger_path = Path(args.ledger)

    if not ledger_path.exists():
        raise FileNotFoundError(f"Ledger not found: {ledger_path}")

    df = normalize(pd.read_parquet(ledger_path))

    required = {
        "candidate_triage_state",
        "direction",
        "outcome",
        "symbol",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"Ledger missing required columns: {missing}")

    print("=" * 88)
    print("A36.4B - ALT C2 PROSPECTIVE CHECKPOINT REPORT V1")
    print("=" * 88)
    print(f"Ledger: {ledger_path.resolve()}")
    print(f"Total ledger events: {len(df):,}")
    print()

    rows = [state_row(df, s) for s in ["PREFERRED", "NEUTRAL", "AVOID"]]

    print("STATE PERFORMANCE")
    print("-" * 88)
    print(f"{'STATE':<12}{'TOTAL':>8}{'BINARY':>9}{'FAV':>8}{'ADV':>8}{'FF%':>10}")
    for r in rows:
        print(
            f"{r['state']:<12}"
            f"{r['total_n']:>8,}"
            f"{r['binary_n']:>9,}"
            f"{r['favorable_n']:>8,}"
            f"{r['adverse_n']:>8,}"
            f"{fmt_pct(r['ff_pct']):>10}"
        )

    print()
    print("PREFERRED CHECKPOINTS")
    print("-" * 88)

    pref = next(r for r in rows if r["state"] == "PREFERRED")
    pref_n = pref["binary_n"]

    for cp in PREFERRED_CHECKPOINTS:
        reached = pref_n >= cp
        remaining = max(cp - pref_n, 0)
        status = "REACHED" if reached else f"{remaining} remaining"
        print(
            f"Preferred binary N >= {cp:<3}: "
            f"{pref_n:>4}/{cp:<4}  {status}"
        )

    print()
    print("FORMAL GRADUATION SAMPLE MINIMUMS")
    print("-" * 88)

    for state in ["PREFERRED", "NEUTRAL", "AVOID"]:
        row = next(r for r in rows if r["state"] == state)
        target = STATE_MINIMUMS[state]
        remaining = max(target - row["binary_n"], 0)
        status = "MET" if remaining == 0 else f"{remaining} remaining"
        print(
            f"{state:<10} binary N: "
            f"{row['binary_n']:>4}/{target:<4}  {status}"
        )

    print()
    print("DIRECTIONAL MINIMUMS")
    print("-" * 88)

    for (state, direction), target in DIRECTION_MINIMUMS.items():
        r = direction_row(df, state, direction)
        remaining = max(target - r["binary_n"], 0)
        status = "MET" if remaining == 0 else f"{remaining} remaining"
        print(
            f"{state:<10} {direction:<4}: "
            f"{r['binary_n']:>4}/{target:<3}  "
            f"FF={fmt_pct(r['ff_pct']):>7}  {status}"
        )

    print()
    print("FROZEN SUCCESS CRITERIA - DESCRIPTIVE ONLY UNTIL MINIMUMS ARE MET")
    print("-" * 88)

    by_state = {r["state"]: r for r in rows}
    p = by_state["PREFERRED"]["ff_pct"]
    n = by_state["NEUTRAL"]["ff_pct"]
    a = by_state["AVOID"]["ff_pct"]

    hierarchy = (
        p is not None and n is not None and a is not None
        and p > n > a
    )
    spread = (p - a) if p is not None and a is not None else None

    print(f"Preferred > Neutral > Avoid: {'YES' if hierarchy else 'NO'}")
    print(
        "Preferred - Avoid spread >= 7pp: "
        + (
            "N/A"
            if spread is None
            else f"{spread:.2f}pp "
                 f"({'YES' if spread >= 7 else 'NO'})"
        )
    )
    print(
        "Preferred >= 53%: "
        + (
            "N/A"
            if p is None
            else f"{p:.2f}% ({'YES' if p >= 53 else 'NO'})"
        )
    )
    print(
        "Avoid <= 47%: "
        + (
            "N/A"
            if a is None
            else f"{a:.2f}% ({'YES' if a <= 47 else 'NO'})"
        )
    )

    pref_df = df[df["candidate_triage_state"] == "PREFERRED"].copy()
    if len(pref_df):
        symbol_counts = pref_df["symbol"].value_counts()
        top1_share = 100.0 * symbol_counts.iloc[0] / len(pref_df)
        top10_share = 100.0 * symbol_counts.head(10).sum() / len(pref_df)

        print(
            f"Largest Preferred symbol share <= 5%: "
            f"{top1_share:.2f}% "
            f"({'YES' if top1_share <= 5 else 'NO'})"
        )
        print(
            f"Top 10 Preferred symbol share <= 35%: "
            f"{top10_share:.2f}% "
            f"({'YES' if top10_share <= 35 else 'NO'})"
        )
    else:
        print("Largest Preferred symbol share <= 5%: N/A")
        print("Top 10 Preferred symbol share <= 35%: N/A")

    print()
    print("NOTE:")
    print(
        "These criteria are frozen, but early YES/NO values are not a "
        "graduation decision until the predefined minimum sample sizes are met."
    )
    print()
    print("RESULT: REPORT COMPLETE")


if __name__ == "__main__":
    main()
