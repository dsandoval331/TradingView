from __future__ import annotations

import pandas as pd

from tr_platform.pmpd_v5.alpha import run_symbol_alpha
from tr_platform.pmpd_v5.geometry import build_stack_geometry
from tr_platform.pmpd_v5.outcomes import evaluate_rth_outcome
from tr_platform.pmpd_v5.session_levels import build_session_levels


def _bar(ts_et: str, session: str, o: float, h: float, l: float, c: float, v: int = 1000) -> dict:
    et = pd.Timestamp(ts_et, tz="America/New_York")
    return {
        "symbol": "TEST",
        "timestamp_et": et,
        "timestamp_utc": et.tz_convert("UTC"),
        "trade_date": et.tz_localize(None).normalize(),
        "open": o, "high": h, "low": l, "close": c, "volume": v,
        "session": session,
    }


def fixture() -> pd.DataFrame:
    rows = [
        # Prior day RTH + AH.
        _bar("2025-01-02 09:30", "RTH", 99, 100, 98, 99.5),
        _bar("2025-01-02 15:59", "RTH", 99.5, 101, 99, 100),
        _bar("2025-01-02 16:00", "AH", 100, 101.5, 99.8, 101),
        _bar("2025-01-02 19:59", "AH", 101, 102, 100.5, 101.5),
        # Current premarket: PMH=103, PML=100.
        _bar("2025-01-03 04:00", "PRE", 101.5, 102, 100, 101),
        _bar("2025-01-03 09:29", "PRE", 101, 103, 100.5, 102.5),
        # RTH bullish path through PDH=101, AHH=102, PMH=103.
        _bar("2025-01-03 09:30", "RTH", 102.4, 102.8, 102.2, 102.6),
        _bar("2025-01-03 09:31", "RTH", 102.6, 103.2, 102.5, 103.1),
        _bar("2025-01-03 09:32", "RTH", 103.1, 103.8, 103.0, 103.6),
        _bar("2025-01-03 09:33", "RTH", 103.6, 104.3, 103.4, 104.1),
        _bar("2025-01-03 15:59", "RTH", 104.1, 104.2, 103.9, 104.0),
    ]
    return pd.DataFrame(rows)


def main() -> None:
    df = fixture()
    levels = build_session_levels(df)
    cur = levels.loc[levels["trade_date"].eq(pd.Timestamp("2025-01-03"))].iloc[0]
    assert cur.pmh == 103
    assert cur.pml == 100
    assert cur.ahh == 102
    assert cur.ahl == 99.8
    assert cur.pdh == 101
    assert cur.pdl == 98
    assert bool(cur.has_complete_six_levels)

    g = build_stack_geometry(cur, "BULL")
    assert g.identity_order_inner_to_outer == "PD>AH>PM"
    assert g.outer_level_name == "PM"

    out = run_symbol_alpha(df, symbol="TEST")
    assert not out["events"].empty
    bull = out["events"].loc[out["events"]["direction"].eq("BULL")].iloc[0]
    assert bull.max_levels_cleared == 3
    assert bull.identity_order_inner_to_outer == "PD>AH>PM"

    bull_dp = out["decision_points"].loc[out["decision_points"]["event_id"].eq(bull.event_id)]
    kinds = set(bull_dp["decision_type"])
    assert "DP1_FIRST_CONTACT" in kinds
    assert "DP4_FULL_STACK_FIRST_CLEAR" in kinds
    assert "DP5_FIRST_COMPLETED_BAR_RETENTION" in kinds

    # Explicit same-bar uncertainty behavior.
    future = pd.DataFrame([{
        "timestamp_utc": pd.Timestamp("2025-01-03 15:00", tz="UTC"),
        "high": 100.6, "low": 99.4,
    }])
    amb = evaluate_rth_outcome(future, direction="BULL", entry_price=100.0)
    assert amb["outcome"] == "AMBIGUOUS_SAME_BAR"

    print("=== PMPD V5 ALPHA SYNTHETIC TEST PASS ===")
    print(f"Events: {len(out['events'])}")
    print(f"Transitions: {len(out['transitions'])}")
    print(f"Decision points: {len(out['decision_points'])}")
    print(f"Outcomes: {len(out['outcomes'])}")


if __name__ == "__main__":
    main()
