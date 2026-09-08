#!/usr/bin/env python3
"""PMPD V5 9J VWAP Event-Path V2 enrichment core.

This module intentionally does not guess repository-specific filenames. It exposes
pure functions that can be wired to the certified 9H/9J parent decision package
and canonical 1-minute bars. Required logical columns are documented below.
"""
from __future__ import annotations
import pandas as pd
import numpy as np

PARTITIONS = [
    ("DISCOVERY", pd.Timestamp("2025-01-02"), pd.Timestamp("2025-04-30")),
    ("VALIDATION_A", pd.Timestamp("2025-05-01"), pd.Timestamp("2025-08-29")),
    ("VALIDATION_B", pd.Timestamp("2025-09-02"), pd.Timestamp("2025-12-31")),
]

def assign_partition(d):
    d = pd.Timestamp(d).normalize()
    for name, lo, hi in PARTITIONS:
        if lo <= d <= hi:
            return name
    return None

def _sign(direction: str) -> int:
    x = str(direction).upper()
    if x.startswith("BULL") or x in {"LONG", "UP", "1", "+1"}: return 1
    if x.startswith("BEAR") or x in {"SHORT", "DOWN", "-1"}: return -1
    raise ValueError(f"Unknown direction: {direction}")

def enrich_event(decisions_event: pd.DataFrame, bars_event: pd.DataFrame) -> pd.DataFrame:
    """Create leakage-safe V2 rows for one parent event.

    decisions_event required logical columns:
      decision_id,event_id,symbol,trade_date,direction,decision_type,decision_timestamp
    bars_event required logical columns:
      timestamp,open,high,low,close,vwap

    DP1 timestamp is the first decision_timestamp whose decision_type == 'DP1'.
    Every output row uses only bars dp1_timestamp <= timestamp <= decision_timestamp.
    """
    d = decisions_event.copy()
    b = bars_event.copy()
    d["decision_timestamp"] = pd.to_datetime(d["decision_timestamp"], utc=True)
    b["timestamp"] = pd.to_datetime(b["timestamp"], utc=True)
    d = d.sort_values("decision_timestamp")
    b = b.sort_values("timestamp")
    dp1s = d.loc[d["decision_type"].astype(str).str.upper().eq("DP1"), "decision_timestamp"]
    if dp1s.empty:
        raise ValueError(f"event {d['event_id'].iloc[0]} has no DP1")
    dp1 = dp1s.iloc[0]
    sgn = _sign(d["direction"].iloc[0])
    b = b.loc[b["timestamp"].ge(dp1)].copy()
    if b.empty: raise ValueError("no bars at/after DP1")

    b["signed_close_dist"] = sgn * (b["close"] - b["vwap"]) / b["vwap"]
    b["signed_open_dist"] = sgn * (b["open"] - b["vwap"]) / b["vwap"]
    b["side"] = np.sign(b["signed_close_dist"]).astype(int)
    b["touch"] = (b["low"] <= b["vwap"]) & (b["high"] >= b["vwap"])
    prev_side = b["side"].shift(1)
    close_flip = (prev_side.ne(0) & b["side"].ne(0) & prev_side.ne(b["side"]))
    body_cross = b["touch"] & (np.sign(b["signed_open_dist"]).ne(np.sign(b["signed_close_dist"])))
    b["cross"] = close_flip | body_cross
    rows=[]
    for r in d.itertuples(index=False):
        end = r.decision_timestamp
        w = b.loc[b["timestamp"].le(end)].copy()  # hard leakage boundary
        if w.empty: raise ValueError(f"no source bars through decision {r.decision_id}")
        fav = w["side"].gt(0); adv = w["side"].lt(0)
        touch = w["touch"]; cross = w["cross"]
        # Observable sequence events only; no future look-ahead.
        seen_adv = adv.cummax()
        reclaim = fav & seen_adv.shift(1, fill_value=False)
        seen_fav = fav.cummax()
        loss = adv & seen_fav.shift(1, fill_value=False)
        interaction = touch | cross
        rejection = fav & interaction.shift(1, fill_value=False)
        def first_ts(mask):
            x=w.loc[mask,"timestamp"]; return x.iloc[0] if len(x) else pd.NaT
        def last_ts(mask):
            x=w.loc[mask,"timestamp"]; return x.iloc[-1] if len(x) else pd.NaT
        def age_minutes(ts):
            return np.nan if pd.isna(ts) else (end-ts).total_seconds()/60.0
        # trailing streak
        sides=w["side"].tolist(); cur=sides[-1]; streak=0
        for x in reversed(sides):
            if x==cur and cur!=0: streak+=1
            else: break
        last_touch=last_ts(touch); last_cross=last_ts(cross); last_reclaim=last_ts(reclaim); last_loss=last_ts(loss)
        rows.append({
            "decision_id":r.decision_id,"event_id":r.event_id,"symbol":r.symbol,
            "trade_date":r.trade_date,"direction":r.direction,"decision_type":r.decision_type,
            "decision_timestamp":end,"dp1_timestamp":dp1,
            "partition":assign_partition(r.trade_date),
            "source_max_timestamp":w["timestamp"].max(),
            "bars_since_dp1":len(w)-1,
            "minutes_since_dp1":(end-dp1).total_seconds()/60.0,
            "signed_close_vwap_distance":w["signed_close_dist"].iloc[-1],
            "min_signed_close_vwap_distance":w["signed_close_dist"].min(),
            "max_signed_close_vwap_distance":w["signed_close_dist"].max(),
            "vwap_side":int(w["side"].iloc[-1]),
            "touch_after_dp1":bool(touch.any()),"touch_count":int(touch.sum()),
            "first_touch_timestamp":first_ts(touch),
            "cross_after_dp1":bool(cross.any()),"cross_count":int(cross.sum()),
            "first_cross_timestamp":first_ts(cross),
            "first_favorable_close_timestamp":first_ts(fav),
            "first_adverse_close_timestamp":first_ts(adv),
            "favorable_close_count":int(fav.sum()),"adverse_close_count":int(adv.sum()),
            "favorable_close_fraction":float(fav.mean()),"adverse_close_fraction":float(adv.mean()),
            "favorable_streak_at_decision":streak if cur>0 else 0,
            "adverse_streak_at_decision":streak if cur<0 else 0,
            "directional_rejection_observed":bool(rejection.any()),
            "reclaim_observed":bool(reclaim.any()),"loss_observed":bool(loss.any()),
            "last_touch_age_minutes":age_minutes(last_touch),
            "last_cross_age_minutes":age_minutes(last_cross),
            "last_reclaim_age_minutes":age_minutes(last_reclaim),
            "last_loss_age_minutes":age_minutes(last_loss),
        })
    return pd.DataFrame(rows)

def audit(parent: pd.DataFrame, v2: pd.DataFrame) -> dict:
    """Hard pre-outcome integrity gates."""
    pids=set(parent.decision_id.astype(str)); vids=set(v2.decision_id.astype(str))
    checks={
      "row_count_match":len(parent)==len(v2),
      "parent_unique_decision_ids":parent.decision_id.nunique()==len(parent),
      "v2_unique_decision_ids":v2.decision_id.nunique()==len(v2),
      "decision_id_set_match":pids==vids,
      "dp1_not_after_decision":bool((pd.to_datetime(v2.dp1_timestamp,utc=True)<=pd.to_datetime(v2.decision_timestamp,utc=True)).all()),
      "source_not_after_decision":bool((pd.to_datetime(v2.source_max_timestamp,utc=True)<=pd.to_datetime(v2.decision_timestamp,utc=True)).all()),
      "no_negative_minutes_since_dp1":bool((v2.minutes_since_dp1>=0).all()),
      "valid_partition":bool(v2.partition.notna().all()),
    }
    checks["PASS"]=all(checks.values())
    return checks
