"""
PMPD V4 parity reference engine v2
9N-3E — reconstructed from the recovered frozen V4 Pine parity source.

This is a RESEARCH/PARITY implementation only.
It does not modify V4 or V5 and does not authorize production rules.

Recovered Pine source SHA256:
79b9d80f0ec2c254bd69607ff626c2007ae7e617018d984f083ba2a25e7ba681
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Iterable
import math
import pandas as pd
import numpy as np

TZ = "America/New_York"

# Frozen V4 defaults.
ATR_LENGTH = 14
MIN_PEN_ATR = 10.0
MIN_BODY_RATIO = 50.0
MIN_RANGE_ATR = 25.0
MIN_CLOSE_POSITION = 80.0

USE_PENETRATION = True
USE_DIRECTIONAL_CANDLE = True
USE_BODY_RATIO = True
USE_RANGE_ATR = False
USE_CLOSE_POSITION = False
REQUIRE_MIN_GRADE = False
ENABLE_STRENGTH_SCORE = True
MINIMUM_GRADE = "B"

MAX_PEN_POINTS = 40.0
MAX_BODY_POINTS = 15.0
MAX_CLOSE_POINTS = 15.0
MAX_RANGE_POINTS = 25.0
MAX_SPEED_POINTS = 5.0
PEN_FULL_SCORE_ATR_PCT = 100.0
RANGE_FULL_SCORE_ATR_PCT = 150.0

PRIORITY_OBSERVE = 0
PRIORITY_LOW = 1
PRIORITY_RESEARCH = 2
PRIORITY_CONDITIONAL = 3
PRIORITY_PRIME = 4

BUCKET_A = 0
BUCKET_B = 1
BUCKET_C = 2
BUCKET_WEAK = 3

PROFILE_CONTROLLED = 0
PROFILE_EXPLOSIVE = 1
PROFILE_EFFICIENT = 2
PROFILE_PRETTY_WEAK = 3
PROFILE_DELAYED = 4
PROFILE_UNCLASSIFIED = 5

PROFILE_NAMES = {
    PROFILE_CONTROLLED: "Controlled Strong",
    PROFILE_EXPLOSIVE: "Explosive",
    PROFILE_EFFICIENT: "Efficient Moderate",
    PROFILE_PRETTY_WEAK: "Pretty but Weak",
    PROFILE_DELAYED: "Delayed Strong",
    PROFILE_UNCLASSIFIED: "Unclassified",
}

PRIORITY_NAMES = {
    PRIORITY_OBSERVE: "OBSERVE",
    PRIORITY_LOW: "LOW",
    PRIORITY_RESEARCH: "RESEARCH",
    PRIORITY_CONDITIONAL: "CONDITIONAL",
    PRIORITY_PRIME: "PRIME",
}

EXPECTED_FROZEN_PINE_SHA256 = "79b9d80f0ec2c254bd69607ff626c2007ae7e617018d984f083ba2a25e7ba681"


@dataclass(frozen=True)
class V4Config:
    atr_length: int = ATR_LENGTH
    use_penetration: bool = USE_PENETRATION
    min_pen_atr: float = MIN_PEN_ATR
    use_directional_candle: bool = USE_DIRECTIONAL_CANDLE
    use_body_ratio: bool = USE_BODY_RATIO
    min_body_ratio: float = MIN_BODY_RATIO
    use_range_atr: bool = USE_RANGE_ATR
    min_range_atr: float = MIN_RANGE_ATR
    use_close_position: bool = USE_CLOSE_POSITION
    min_close_position: float = MIN_CLOSE_POSITION
    require_min_grade: bool = REQUIRE_MIN_GRADE
    enable_strength_score: bool = ENABLE_STRENGTH_SCORE
    minimum_grade: str = MINIMUM_GRADE
    minimum_alert_priority: str = "Conditional+"
    show_research_priority_alerts: bool = False
    show_low_observe_alerts: bool = False


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def grade(score: float) -> str:
    if score >= 97.0: return "A+"
    if score >= 93.0: return "A"
    if score >= 90.0: return "A-"
    if score >= 87.0: return "B+"
    if score >= 83.0: return "B"
    if score >= 80.0: return "B-"
    if score >= 77.0: return "C+"
    if score >= 73.0: return "C"
    if score >= 70.0: return "C-"
    return "Weak"


def grade_threshold(g: str) -> float:
    return {"A+":97.0,"A":93.0,"A-":90.0,"B+":87.0,"B":83.0,"B-":80.0,
            "C+":77.0,"C":73.0,"C-":70.0}.get(g, 70.0)


def grade_bucket(g: str) -> int:
    if g in ("A+","A","A-"): return BUCKET_A
    if g in ("B+","B","B-"): return BUCKET_B
    if g in ("C+","C","C-"): return BUCKET_C
    return BUCKET_WEAK


def penetration_score(penetration_atr: float) -> float:
    return clamp(penetration_atr / PEN_FULL_SCORE_ATR_PCT, 0.0, 1.0) * MAX_PEN_POINTS


def body_score(ratio: float) -> float:
    return clamp(ratio / 100.0, 0.0, 1.0) * MAX_BODY_POINTS


def close_score(close_position: float) -> float:
    return clamp((close_position - 50.0) / 50.0, 0.0, 1.0) * MAX_CLOSE_POINTS


def range_score(candle_range_atr: float) -> float:
    return clamp(candle_range_atr / RANGE_FULL_SCORE_ATR_PCT, 0.0, 1.0) * MAX_RANGE_POINTS


def speed_score(bars_to_confirm: int) -> float:
    if bars_to_confirm <= 0: return 5.0
    if bars_to_confirm == 1: return 4.5
    if bars_to_confirm == 2: return 3.0
    if bars_to_confirm == 3: return 1.5
    return 0.0


def v4_profile(penetration: float, range_value: float, body_value: float,
               close_value: float, speed_bars: int) -> int:
    explosive = (
        ((penetration >= 100.0 and range_value >= 100.0) or
         (range_value >= 200.0 and penetration >= 40.0))
        and body_value >= 50.0
        and close_value >= 70.0
        and 0 <= speed_bars <= 1
    )
    controlled = (
        penetration >= 60.0 and range_value >= 100.0 and
        body_value >= 60.0 and close_value >= 80.0 and
        0 <= speed_bars <= 1
    )
    efficient = (
        penetration >= 40.0 and range_value >= 75.0 and
        body_value >= 65.0 and close_value >= 80.0 and
        0 <= speed_bars <= 1
    )
    delayed = (
        penetration >= 60.0 and range_value >= 100.0 and
        body_value >= 65.0 and close_value >= 80.0 and
        2 <= speed_bars <= 3
    )
    pretty_weak = (
        body_value >= 70.0 and close_value >= 80.0 and
        0 <= speed_bars <= 1 and
        (penetration < 40.0 or range_value < 75.0)
    )
    if explosive: return PROFILE_EXPLOSIVE
    if controlled: return PROFILE_CONTROLLED
    if efficient: return PROFILE_EFFICIENT
    if delayed: return PROFILE_DELAYED
    if pretty_weak: return PROFILE_PRETTY_WEAK
    return PROFILE_UNCLASSIFIED


def priority_code(bucket: int, profile: int) -> int:
    result = PRIORITY_RESEARCH
    if profile == PROFILE_EXPLOSIVE and bucket in (BUCKET_A, BUCKET_B, BUCKET_C):
        return PRIORITY_PRIME
    if profile == PROFILE_CONTROLLED and bucket == BUCKET_C:
        return PRIORITY_PRIME
    if profile == PROFILE_CONTROLLED and bucket == BUCKET_B:
        return PRIORITY_CONDITIONAL
    if profile == PROFILE_EFFICIENT and bucket in (BUCKET_C, BUCKET_WEAK):
        return PRIORITY_CONDITIONAL
    if profile == PROFILE_DELAYED and bucket == BUCKET_A:
        return PRIORITY_RESEARCH
    if profile == PROFILE_PRETTY_WEAK:
        return PRIORITY_LOW
    if profile == PROFILE_UNCLASSIFIED:
        return PRIORITY_OBSERVE
    if profile == PROFILE_CONTROLLED and bucket == BUCKET_A:
        return PRIORITY_OBSERVE
    return result


def trade_type(bucket: int, profile: int) -> str:
    if profile == PROFILE_EXPLOSIVE:
        return "EXPANSION"
    if profile in (PROFILE_CONTROLLED, PROFILE_EFFICIENT):
        return "SCALP"
    if profile == PROFILE_DELAYED and bucket == BUCKET_A:
        return "EXPANSION"
    return "OBSERVE"


_TQS = {
    (BUCKET_A, PROFILE_EXPLOSIVE): 42.7,
    (BUCKET_B, PROFILE_EXPLOSIVE): 42.1,
    (BUCKET_C, PROFILE_EXPLOSIVE): 50.2,
    (BUCKET_C, PROFILE_CONTROLLED): 42.2,
    (BUCKET_B, PROFILE_CONTROLLED): 33.4,
    (BUCKET_C, PROFILE_EFFICIENT): 36.1,
    (BUCKET_WEAK, PROFILE_EFFICIENT): 36.7,
    (BUCKET_A, PROFILE_DELAYED): 59.9,
    (BUCKET_A, PROFILE_CONTROLLED): 31.0,
    (BUCKET_WEAK, PROFILE_PRETTY_WEAK): 30.4,
}

_CONFIDENCE = {
    (BUCKET_A, PROFILE_EXPLOSIVE): "HIGH",
    (BUCKET_B, PROFILE_EXPLOSIVE): "HIGH",
    (BUCKET_C, PROFILE_EXPLOSIVE): "MODERATE",
    (BUCKET_C, PROFILE_CONTROLLED): "MOD-HIGH",
    (BUCKET_B, PROFILE_CONTROLLED): "HIGH",
    (BUCKET_C, PROFILE_EFFICIENT): "HIGH",
    (BUCKET_WEAK, PROFILE_EFFICIENT): "HIGH",
    (BUCKET_A, PROFILE_DELAYED): "LOW",
    (BUCKET_A, PROFILE_CONTROLLED): "MODERATE",
    (BUCKET_WEAK, PROFILE_PRETTY_WEAK): "HIGH",
}


def production_tqs(bucket: int, profile: int) -> float:
    return _TQS.get((bucket, profile), math.nan)


def production_confidence(bucket: int, profile: int) -> str:
    return _CONFIDENCE.get((bucket, profile), "INSUFFICIENT")


def priority_alert_pass(priority: int, cfg: V4Config) -> bool:
    if cfg.minimum_alert_priority == "Prime Only":
        return priority == PRIORITY_PRIME
    if cfg.minimum_alert_priority == "Conditional+":
        return priority >= PRIORITY_CONDITIONAL
    return (
        priority >= PRIORITY_CONDITIONAL or
        (priority == PRIORITY_RESEARCH and cfg.show_research_priority_alerts) or
        (priority in (PRIORITY_LOW, PRIORITY_OBSERVE) and cfg.show_low_observe_alerts)
    )


def pine_rma(values: Iterable[float], length: int) -> np.ndarray:
    """TradingView/Pine-style RMA: SMA seed, then alpha=1/length recursion."""
    a = np.asarray(list(values), dtype=float)
    out = np.full(a.shape, np.nan, dtype=float)
    if length <= 0:
        raise ValueError("length must be > 0")
    valid_run = []
    seed_i = None
    for i, v in enumerate(a):
        if np.isnan(v):
            continue
        valid_run.append(v)
        if len(valid_run) == length:
            seed_i = i
            out[i] = float(np.mean(valid_run))
            break
    if seed_i is None:
        return out
    alpha = 1.0 / float(length)
    prev = out[seed_i]
    for i in range(seed_i + 1, len(a)):
        v = a[i]
        if np.isnan(v):
            out[i] = prev
        else:
            prev = alpha * v + (1.0 - alpha) * prev
            out[i] = prev
    return out


def add_pine_atr(rth5: pd.DataFrame, length: int = ATR_LENGTH) -> pd.DataFrame:
    """
    Compute ta.atr(length) on the concatenated regular-session 5m stream.
    Previous close carries across sessions, matching regularTicker behavior.
    """
    df = rth5.copy().sort_values("bar_start_et").reset_index(drop=True)
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1, skipna=True)
    df["tr"] = tr.astype(float)
    df["atr"] = pine_rma(df["tr"].to_numpy(), length)
    return df


def _ensure_et_index(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    if isinstance(df.index, pd.DatetimeIndex):
        ts = df.index
    else:
        candidates = [c for c in ("timestamp","time","datetime","ts") if c in df.columns]
        if not candidates:
            raise ValueError("Need a DatetimeIndex or timestamp/time/datetime/ts column.")
        ts = pd.to_datetime(df[candidates[0]], utc=True, errors="raise")
    if ts.tz is None:
        # Canonical Massive cache is expected UTC if tz-naive.
        ts = ts.tz_localize("UTC")
    ts = ts.tz_convert(TZ)
    df = df.copy()
    df["timestamp_et"] = ts
    return df


def build_rth_5m(raw_1m: pd.DataFrame) -> pd.DataFrame:
    """Construct 09:30-09:34, 09:35-09:39 ... RTH bars from canonical 1m."""
    df = _ensure_et_index(raw_1m)
    for c in ("open","high","low","close"):
        if c not in df.columns:
            raise ValueError(f"Missing required column: {c}")
    t = df["timestamp_et"]
    mins = t.dt.hour * 60 + t.dt.minute
    rth = df[(mins >= 570) & (mins <= 959)].copy()  # 09:30 through 15:59
    rth["trade_date"] = rth["timestamp_et"].dt.date
    rth["minute_from_open"] = (rth["timestamp_et"].dt.hour * 60 + rth["timestamp_et"].dt.minute) - 570
    rth["bucket"] = (rth["minute_from_open"] // 5).astype(int)
    g = rth.groupby(["trade_date","bucket"], sort=True)
    out = g.agg(
        open=("open","first"),
        high=("high","max"),
        low=("low","min"),
        close=("close","last"),
        raw_count=("close","size"),
    ).reset_index()
    base = pd.to_datetime(out["trade_date"].astype(str)).dt.tz_localize(TZ)
    out["bar_start_et"] = base + pd.Timedelta(hours=9, minutes=30) + pd.to_timedelta(out["bucket"]*5, unit="m")
    out["bar_close_et"] = out["bar_start_et"] + pd.Timedelta(minutes=5)
    return out.sort_values("bar_start_et").reset_index(drop=True)


def build_daily_levels(raw_1m: pd.DataFrame) -> pd.DataFrame:
    """PMH/PML current PRE + PDH/PDL previous valid RTH session."""
    df = _ensure_et_index(raw_1m)
    t = df["timestamp_et"]
    mins = t.dt.hour * 60 + t.dt.minute
    df["trade_date"] = t.dt.date

    pre = df[(mins >= 240) & (mins <= 569)]
    pre_levels = pre.groupby("trade_date").agg(pmh=("high","max"), pml=("low","min"))

    rth = df[(mins >= 570) & (mins <= 959)]
    rth_levels = rth.groupby("trade_date").agg(rth_high=("high","max"), rth_low=("low","min")).sort_index()
    rth_levels["pdh"] = rth_levels["rth_high"].shift(1)
    rth_levels["pdl"] = rth_levels["rth_low"].shift(1)

    levels = pre_levels.join(rth_levels[["pdh","pdl"]], how="outer").sort_index()
    levels["bull_final"] = levels[["pmh","pdh"]].max(axis=1)
    levels["bear_final"] = levels[["pml","pdl"]].min(axis=1)
    levels.index.name = "trade_date"
    return levels


def _signal_metrics(row: pd.Series, bull_final: float, bear_final: float):
    conf_range = float(row.high - row.low)
    conf_body = abs(float(row.close - row.open))
    body_ratio = 0.0
    range_atr = 0.0
    bull_close_position = 0.0
    bear_close_position = 0.0
    atr = float(row.atr)
    if conf_range > 0:
        body_ratio = conf_body / conf_range * 100.0
        bull_close_position = (float(row.close) - float(row.low)) / conf_range * 100.0
        bear_close_position = (float(row.high) - float(row.close)) / conf_range * 100.0
    if atr > 0:
        range_atr = conf_range / atr * 100.0
        bull_pen_atr = (float(row.close) - bull_final) / atr * 100.0
        bear_pen_atr = (bear_final - float(row.close)) / atr * 100.0
    else:
        bull_pen_atr = math.nan
        bear_pen_atr = math.nan
    return {
        "conf_range": conf_range,
        "conf_body": conf_body,
        "body_ratio": body_ratio,
        "range_atr": range_atr,
        "bull_close_position": bull_close_position,
        "bear_close_position": bear_close_position,
        "bull_pen_atr": bull_pen_atr,
        "bear_pen_atr": bear_pen_atr,
    }


def evaluate_v4_signals(raw_1m: pd.DataFrame, symbol: Optional[str] = None,
                        cfg: V4Config = V4Config()) -> pd.DataFrame:
    """
    Reproduce frozen V4 raw-valid signal state machine on canonical 1m data.

    Canonical signal timestamp = completed 5m bar close time (confTimeClose).
    Signal reference = completed 5m close.
    """
    rth5 = add_pine_atr(build_rth_5m(raw_1m), cfg.atr_length)
    levels = build_daily_levels(raw_1m)

    signals = []
    current_date = None
    bull_state = bear_state = 0
    bull_armed_bars = bear_armed_bars = 0
    bull_armed_time = bear_armed_time = None
    bull_initial_pen = bear_initial_pen = math.nan

    for row in rth5.itertuples(index=False):
        d = row.trade_date
        if d != current_date:
            current_date = d
            bull_state = bear_state = 0
            bull_armed_bars = bear_armed_bars = 0
            bull_armed_time = bear_armed_time = None
            bull_initial_pen = bear_initial_pen = math.nan

        if d not in levels.index:
            continue
        lv = levels.loc[d]
        if any(pd.isna(lv.get(k)) for k in ("pmh","pml","pdh","pdl","bull_final","bear_final")):
            continue
        if pd.isna(row.atr):
            continue

        m = _signal_metrics(pd.Series(row._asdict()), float(lv.bull_final), float(lv.bear_final))

        bull_directional = (not cfg.use_directional_candle) or (row.close > row.open)
        bear_directional = (not cfg.use_directional_candle) or (row.close < row.open)
        body_pass = (not cfg.use_body_ratio) or (m["body_ratio"] >= cfg.min_body_ratio)
        range_pass = (not cfg.use_range_atr) or (m["range_atr"] >= cfg.min_range_atr)
        bull_close_pass = (not cfg.use_close_position) or (m["bull_close_position"] >= cfg.min_close_position)
        bear_close_pass = (not cfg.use_close_position) or (m["bear_close_position"] >= cfg.min_close_position)
        bull_pen_pass = (not cfg.use_penetration) or (m["bull_pen_atr"] >= cfg.min_pen_atr)
        bear_pen_pass = (not cfg.use_penetration) or (m["bear_pen_atr"] >= cfg.min_pen_atr)

        def emit(direction: str, bars_to_confirm: int, initial_pen: float):
            if direction == "BULL":
                pen = m["bull_pen_atr"]; close_pos = m["bull_close_position"]
                directional_pass = bull_directional; pen_pass = bull_pen_pass; close_pass = bull_close_pass
                final = float(lv.bull_final)
            else:
                pen = m["bear_pen_atr"]; close_pos = m["bear_close_position"]
                directional_pass = bear_directional; pen_pass = bear_pen_pass; close_pass = bear_close_pass
                final = float(lv.bear_final)

            ps = penetration_score(pen)
            bs = body_score(m["body_ratio"])
            cs = close_score(close_pos)
            rs = range_score(m["range_atr"])
            ss = speed_score(bars_to_confirm)
            total = ps + bs + cs + rs + ss
            g = grade(total)
            bucket = grade_bucket(g)
            prof = v4_profile(pen, m["range_atr"], m["body_ratio"], close_pos, bars_to_confirm)
            pri = priority_code(bucket, prof)

            signals.append({
                "symbol": symbol,
                "trade_date": d,
                "direction": direction,
                "signal_timestamp_et": row.bar_close_et,
                "signal_bar_start_et": row.bar_start_et,
                "reference_price": float(row.close),
                "pmh": float(lv.pmh), "pml": float(lv.pml),
                "pdh": float(lv.pdh), "pdl": float(lv.pdl),
                "final_level": final,
                "atr": float(row.atr),
                "penetration_pct_atr": pen,
                "initial_penetration_pct_atr": initial_pen,
                "body_pct": m["body_ratio"],
                "range_pct_atr": m["range_atr"],
                "close_position_pct": close_pos,
                "bars_to_confirm": int(bars_to_confirm),
                "pen_score": ps, "body_score": bs, "close_score": cs,
                "range_score": rs, "speed_score": ss, "total_score": total,
                "grade": g, "grade_bucket": bucket,
                "profile_code": prof, "profile": PROFILE_NAMES[prof],
                "priority_code": pri, "priority": PRIORITY_NAMES[pri],
                "trade_type": trade_type(bucket, prof),
                "tqs": production_tqs(bucket, prof),
                "confidence": production_confidence(bucket, prof),
                "production_alert": priority_alert_pass(pri, cfg),
                "directional_pass": bool(directional_pass),
                "penetration_pass": bool(pen_pass),
                "body_pass": bool(body_pass),
                "range_pass": bool(range_pass),
                "close_pass": bool(close_pass),
            })

        # Pine sequential state semantics — BULL.
        if bull_state == 2:
            if row.close <= lv.bull_final:
                bull_state = 0; bull_armed_time = None; bull_armed_bars = 0; bull_initial_pen = math.nan

        if bull_state == 1:
            if row.close < lv.bull_final:
                bull_state = 0; bull_armed_time = None; bull_armed_bars = 0; bull_initial_pen = math.nan
            else:
                bull_armed_bars += 1
                core = bull_pen_pass and bull_directional and body_pass and range_pass and bull_close_pass
                if core:
                    total = (
                        penetration_score(m["bull_pen_atr"]) + body_score(m["body_ratio"]) +
                        close_score(m["bull_close_position"]) + range_score(m["range_atr"]) +
                        speed_score(bull_armed_bars)
                    )
                    grade_pass = (not (cfg.require_min_grade and cfg.enable_strength_score)) or total >= grade_threshold(cfg.minimum_grade)
                    if grade_pass:
                        emit("BULL", bull_armed_bars, bull_initial_pen)
                        bull_state = 2

        if bull_state == 0:
            if row.close > lv.bull_final:
                bull_state = 1
                bull_armed_time = row.bar_start_et
                bull_armed_bars = 0
                bull_initial_pen = m["bull_pen_atr"]
                core = bull_pen_pass and bull_directional and body_pass and range_pass and bull_close_pass
                if core:
                    total = (
                        penetration_score(m["bull_pen_atr"]) + body_score(m["body_ratio"]) +
                        close_score(m["bull_close_position"]) + range_score(m["range_atr"]) +
                        speed_score(0)
                    )
                    grade_pass = (not (cfg.require_min_grade and cfg.enable_strength_score)) or total >= grade_threshold(cfg.minimum_grade)
                    if grade_pass:
                        emit("BULL", 0, bull_initial_pen)
                        bull_state = 2

        # Pine sequential state semantics — BEAR.
        if bear_state == 2:
            if row.close >= lv.bear_final:
                bear_state = 0; bear_armed_time = None; bear_armed_bars = 0; bear_initial_pen = math.nan

        if bear_state == 1:
            if row.close > lv.bear_final:
                bear_state = 0; bear_armed_time = None; bear_armed_bars = 0; bear_initial_pen = math.nan
            else:
                bear_armed_bars += 1
                core = bear_pen_pass and bear_directional and body_pass and range_pass and bear_close_pass
                if core:
                    total = (
                        penetration_score(m["bear_pen_atr"]) + body_score(m["body_ratio"]) +
                        close_score(m["bear_close_position"]) + range_score(m["range_atr"]) +
                        speed_score(bear_armed_bars)
                    )
                    grade_pass = (not (cfg.require_min_grade and cfg.enable_strength_score)) or total >= grade_threshold(cfg.minimum_grade)
                    if grade_pass:
                        emit("BEAR", bear_armed_bars, bear_initial_pen)
                        bear_state = 2

        if bear_state == 0:
            if row.close < lv.bear_final:
                bear_state = 1
                bear_armed_time = row.bar_start_et
                bear_armed_bars = 0
                bear_initial_pen = m["bear_pen_atr"]
                core = bear_pen_pass and bear_directional and body_pass and range_pass and bear_close_pass
                if core:
                    total = (
                        penetration_score(m["bear_pen_atr"]) + body_score(m["body_ratio"]) +
                        close_score(m["bear_close_position"]) + range_score(m["range_atr"]) +
                        speed_score(0)
                    )
                    grade_pass = (not (cfg.require_min_grade and cfg.enable_strength_score)) or total >= grade_threshold(cfg.minimum_grade)
                    if grade_pass:
                        emit("BEAR", 0, bear_initial_pen)
                        bear_state = 2

    out = pd.DataFrame(signals)
    return out


def attach_v4_outcomes(signals: pd.DataFrame, raw_1m: pd.DataFrame,
                       favorable_pct: float = 0.50, adverse_pct: float = 0.50) -> pd.DataFrame:
    """
    Frozen V4 5m outcome semantics:
    - signal candle excluded
    - subsequent completed RTH 5m bars only
    - same session only
    - first outcome freezes at FAVORABLE_FIRST / ADVERSE_FIRST / BOTH
    - MFE/MAE continue through the rest of the session
    """
    if signals.empty:
        return signals.copy()
    bars = build_rth_5m(raw_1m)
    result = signals.copy()
    result["first_outcome"] = "NEITHER"
    result["mfe_pct"] = 0.0
    result["mae_pct"] = 0.0

    for idx, s in result.iterrows():
        same = bars[
            (bars["trade_date"] == s["trade_date"]) &
            (bars["bar_close_et"] > s["signal_timestamp_et"])
        ]
        ref = float(s["reference_price"])
        outcome = "NEITHER"
        mfe = 0.0
        mae = 0.0
        for b in same.itertuples(index=False):
            if s["direction"] == "BULL":
                mfe_c = (b.high - ref) / ref * 100.0
                mae_c = (b.low - ref) / ref * 100.0
                fav = b.high >= ref * (1.0 + favorable_pct/100.0)
                adv = b.low <= ref * (1.0 - adverse_pct/100.0)
            else:
                mfe_c = (ref - b.low) / ref * 100.0
                mae_c = (ref - b.high) / ref * 100.0
                fav = b.low <= ref * (1.0 - favorable_pct/100.0)
                adv = b.high >= ref * (1.0 + adverse_pct/100.0)

            mfe = max(mfe, float(mfe_c))
            mae = min(mae, float(mae_c))

            if outcome == "NEITHER":
                if fav and adv:
                    outcome = "BOTH"
                elif fav:
                    outcome = "FAVORABLE_FIRST"
                elif adv:
                    outcome = "ADVERSE_FIRST"

        result.at[idx, "first_outcome"] = outcome
        result.at[idx, "mfe_pct"] = mfe
        result.at[idx, "mae_pct"] = mae

    return result


def evaluate_v4(raw_1m: pd.DataFrame, symbol: Optional[str] = None,
                cfg: V4Config = V4Config()) -> pd.DataFrame:
    return attach_v4_outcomes(evaluate_v4_signals(raw_1m, symbol=symbol, cfg=cfg), raw_1m)


def load_parquet_and_evaluate(path: str | Path, symbol: Optional[str] = None) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_parquet(path)
    return evaluate_v4(df, symbol=symbol or path.stem)
