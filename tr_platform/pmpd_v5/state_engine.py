from __future__ import annotations

from dataclasses import dataclass, asdict
import pandas as pd

LEVEL_NAMES = ("PM", "AH", "PD")


def _vec(bits: dict[str, bool]) -> str:
    return "".join("1" if bits[n] else "0" for n in LEVEL_NAMES)


def _touch(direction: str, high: float, low: float, level: float) -> bool:
    return high >= level if direction == "BULL" else low <= level


def _traded_beyond(direction: str, high: float, low: float, level: float) -> bool:
    return high > level if direction == "BULL" else low < level


def _close_beyond(direction: str, close: float, level: float) -> bool:
    return close > level if direction == "BULL" else close < level


@dataclass(frozen=True)
class Transition:
    event_id: str
    sequence: int
    timestamp_utc: object
    prior_close_vector: str
    new_close_vector: str
    traded_vector: str
    attempt_number: int
    close: float


@dataclass(frozen=True)
class DecisionPoint:
    event_id: str
    decision_sequence: int
    decision_type: str
    timestamp_utc: object
    direction: str
    attempt_number: int
    close_vector: str
    traded_vector: str
    reference_price: float
    reference_price_source: str


def scan_directional_event(
    day_rth: pd.DataFrame,
    *,
    symbol: str,
    trade_date: str,
    direction: str,
    levels: dict[str, float],
    event_sequence: int = 1,
) -> tuple[dict | None, pd.DataFrame, pd.DataFrame]:
    """Scan one direction for one RTH day.

    Alpha rule: the first hard contact starts one parent event that remains open
    through RTH close. This deliberately avoids arbitrary disengagement thresholds.
    Attempts increment after prior structural progress is fully lost and a later bar
    again trades beyond at least one stack level.
    """
    direction = direction.upper().strip()
    x = day_rth.sort_values("timestamp_utc").reset_index(drop=True)
    if x.empty:
        return None, pd.DataFrame(), pd.DataFrame()

    started = False
    event_id = f"{symbol}_{trade_date}_{direction}_{event_sequence:02d}"
    prior_close_vec = "000"
    had_progress = False
    awaiting_reattempt = False
    attempt = 1
    transition_seq = 0
    decision_seq = 0
    transitions: list[dict] = []
    decisions: list[dict] = []
    first_contact_ts = None
    first_full_trade_ts = None
    first_full_close_ts = None
    max_cleared = 0

    emitted = set()

    def emit(kind: str, row, close_vec: str, traded_vec: str) -> None:
        nonlocal decision_seq
        key = kind
        if key in emitted and kind not in {"DP11_PARTIAL_RECLAIM", "DP12_FULL_RECLAIM"}:
            return
        decision_seq += 1
        decisions.append(asdict(DecisionPoint(
            event_id=event_id,
            decision_sequence=decision_seq,
            decision_type=kind,
            timestamp_utc=row.timestamp_utc,
            direction=direction,
            attempt_number=attempt,
            close_vector=close_vec,
            traded_vector=traded_vec,
            reference_price=float(row.close),
            reference_price_source="COMPLETED_1M_BAR_CLOSE",
        )))
        emitted.add(key)

    for row in x.itertuples(index=False):
        touch_bits = {n: _touch(direction, float(row.high), float(row.low), float(levels[n])) for n in LEVEL_NAMES}
        traded_bits = {n: _traded_beyond(direction, float(row.high), float(row.low), float(levels[n])) for n in LEVEL_NAMES}
        close_bits = {n: _close_beyond(direction, float(row.close), float(levels[n])) for n in LEVEL_NAMES}
        touch_vec, traded_vec, close_vec = _vec(touch_bits), _vec(traded_bits), _vec(close_bits)

        if not started:
            if "1" not in touch_vec:
                continue
            started = True
            first_contact_ts = row.timestamp_utc
            emit("DP1_FIRST_CONTACT", row, close_vec, traded_vec)

        if awaiting_reattempt and "1" in traded_vec:
            attempt += 1
            awaiting_reattempt = False

        traded_count = traded_vec.count("1")
        close_count = close_vec.count("1")
        max_cleared = max(max_cleared, traded_count, close_count)

        if traded_count >= 1:
            emit("DP2_FIRST_LEVEL_CLEAR", row, close_vec, traded_vec)
        if traded_count >= 2:
            emit("DP3_SECOND_LEVEL_CLEAR", row, close_vec, traded_vec)
        if traded_vec == "111":
            if first_full_trade_ts is None:
                first_full_trade_ts = row.timestamp_utc
            emit("DP4_FULL_STACK_FIRST_CLEAR", row, close_vec, traded_vec)
        if close_vec == "111":
            if first_full_close_ts is None:
                first_full_close_ts = row.timestamp_utc
            emit("DP5_FIRST_COMPLETED_BAR_RETENTION", row, close_vec, traded_vec)

        if close_vec != prior_close_vec:
            transition_seq += 1
            transitions.append(asdict(Transition(
                event_id=event_id,
                sequence=transition_seq,
                timestamp_utc=row.timestamp_utc,
                prior_close_vector=prior_close_vec,
                new_close_vector=close_vec,
                traded_vector=traded_vec,
                attempt_number=attempt,
                close=float(row.close),
            )))

            prior_n = prior_close_vec.count("1")
            new_n = close_vec.count("1")
            if prior_close_vec == "111" and 0 < new_n < 3:
                emit("DP9_PARTIAL_LOSS", row, close_vec, traded_vec)
            if prior_n > 0 and close_vec == "000":
                emit("DP10_FULL_LOSS", row, close_vec, traded_vec)
                if had_progress:
                    awaiting_reattempt = True
            if prior_n == 0 and 0 < new_n < 3 and had_progress:
                emit("DP11_PARTIAL_RECLAIM", row, close_vec, traded_vec)
            if prior_close_vec != "111" and close_vec == "111" and had_progress and first_full_close_ts != row.timestamp_utc:
                emit("DP12_FULL_RECLAIM", row, close_vec, traded_vec)

            if new_n > 0:
                had_progress = True
            prior_close_vec = close_vec

    if not started:
        return None, pd.DataFrame(), pd.DataFrame()

    event = {
        "event_id": event_id,
        "symbol": symbol,
        "trade_date": trade_date,
        "direction": direction,
        "event_sequence": event_sequence,
        "event_start_time": first_contact_ts,
        "event_end_time": x.iloc[-1]["timestamp_utc"],
        "termination_reason": "RTH_END_ALPHA",
        "first_full_stack_trade_time": first_full_trade_ts,
        "first_full_stack_close_time": first_full_close_ts,
        "max_levels_cleared": max_cleared,
        "attempt_count": attempt,
    }
    return event, pd.DataFrame(transitions), pd.DataFrame(decisions)
