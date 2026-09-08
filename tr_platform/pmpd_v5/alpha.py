from __future__ import annotations

import pandas as pd

from .geometry import geometry_as_dict
from .outcomes import evaluate_rth_outcome
from .session_levels import build_session_levels, add_session_quality_metadata
from .state_engine import scan_directional_event


def run_symbol_alpha(bars: pd.DataFrame, *, symbol: str) -> dict[str, pd.DataFrame]:
    """Run PMPD V5 Alpha structural engine for one certified-like symbol frame."""
    x = bars.copy()
    x["trade_date"] = pd.to_datetime(x["trade_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    x["timestamp_utc"] = pd.to_datetime(x["timestamp_utc"], errors="coerce", utc=True)
    levels = build_session_levels(x)

    events, transitions, decisions, geometries = [], [], [], []

    for lvl in levels.itertuples(index=False):
        if not bool(lvl.has_complete_six_levels):
            continue
        trade_date = pd.Timestamp(lvl.trade_date)
        day = x.loc[x["trade_date"].eq(trade_date) & x["session"].eq("RTH")].copy()
        if day.empty:
            continue

        lvl_row = pd.Series(lvl._asdict())
        for direction in ("BULL", "BEAR"):
            geom = geometry_as_dict(lvl_row, direction)
            geom.update({"symbol": symbol, "trade_date": trade_date})
            geometries.append(geom)
            directional_levels = {
                "PM": geom["pm_level"],
                "AH": geom["ah_level"],
                "PD": geom["pd_level"],
            }
            event, tr, dp = scan_directional_event(
                day,
                symbol=symbol,
                trade_date=trade_date.strftime("%Y-%m-%d"),
                direction=direction,
                levels=directional_levels,
            )
            if event is None:
                continue
            event.update({
                "pm_level": geom["pm_level"],
                "ah_level": geom["ah_level"],
                "pd_level": geom["pd_level"],
                "identity_order_inner_to_outer": geom["identity_order_inner_to_outer"],
                "stack_width_pct": geom["stack_width_pct"],
            })
            events.append(event)
            if not tr.empty:
                transitions.append(tr)
            if not dp.empty:
                decisions.append(dp)

    events_df = pd.DataFrame(events)
    transitions_df = pd.concat(transitions, ignore_index=True) if transitions else pd.DataFrame()
    decisions_df = pd.concat(decisions, ignore_index=True) if decisions else pd.DataFrame()
    geometry_df = pd.DataFrame(geometries)

    outcomes = []
    if not decisions_df.empty:
        for d in decisions_df.itertuples(index=False):
            td = pd.Timestamp(str(d.event_id).split("_")[1])
            future = x.loc[
                x["trade_date"].eq(td)
                & x["session"].eq("RTH")
                & x["timestamp_utc"].gt(pd.Timestamp(d.timestamp_utc))
            ].sort_values("timestamp_utc")
            result = evaluate_rth_outcome(
                future,
                direction=d.direction,
                entry_price=float(d.reference_price),
            )
            outcomes.append({"decision_id": f"{d.event_id}_DP{int(d.decision_sequence):02d}", "event_id": d.event_id,
                             "decision_sequence": int(d.decision_sequence), **result})
        decisions_df["decision_id"] = [f"{r.event_id}_DP{int(r.decision_sequence):02d}" for r in decisions_df.itertuples()]

    return {
        "session_levels": levels,
        "geometry": geometry_df,
        "events": events_df,
        "transitions": transitions_df,
        "decision_points": decisions_df,
        "outcomes": pd.DataFrame(outcomes),
    }
