from __future__ import annotations

import math
import pandas as pd


def evaluate_rth_outcome(
    future_bars: pd.DataFrame,
    *,
    direction: str,
    entry_price: float,
    favorable_pct: float = 0.50,
    adverse_pct: float = 0.50,
) -> dict:
    """Evaluate outcome beginning strictly AFTER a completed decision bar."""
    direction = direction.upper().strip()
    if direction not in {"BULL", "BEAR"}:
        raise ValueError("direction must be BULL or BEAR")
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")

    if direction == "BULL":
        fav_target = entry_price * (1 + favorable_pct / 100.0)
        adv_target = entry_price * (1 - adverse_pct / 100.0)
    else:
        fav_target = entry_price * (1 - favorable_pct / 100.0)
        adv_target = entry_price * (1 + adverse_pct / 100.0)

    first_fav = None
    first_adv = None
    outcome = "UNRESOLVED"

    for r in future_bars.itertuples(index=False):
        high, low, ts = float(r.high), float(r.low), r.timestamp_utc
        fav_hit = high >= fav_target if direction == "BULL" else low <= fav_target
        adv_hit = low <= adv_target if direction == "BULL" else high >= adv_target
        if fav_hit and adv_hit:
            first_fav = ts
            first_adv = ts
            outcome = "AMBIGUOUS_SAME_BAR"
            break
        if fav_hit:
            first_fav = ts
            outcome = "FAVORABLE_FIRST"
            break
        if adv_hit:
            first_adv = ts
            outcome = "ADVERSE_FIRST"
            break

    if future_bars.empty:
        mfe = mae = 0.0
    else:
        hi = max(entry_price, float(future_bars["high"].max()))
        lo = min(entry_price, float(future_bars["low"].min()))
        if direction == "BULL":
            mfe = (hi - entry_price) / entry_price * 100.0
            mae = (entry_price - lo) / entry_price * 100.0
        else:
            mfe = (entry_price - lo) / entry_price * 100.0
            mae = (hi - entry_price) / entry_price * 100.0

    return {
        "favorable_target_price": fav_target,
        "adverse_target_price": adv_target,
        "outcome": outcome,
        "first_favorable_timestamp": first_fav,
        "first_adverse_timestamp": first_adv,
        "mfe_pct": mfe,
        "mae_pct": mae,
    }
