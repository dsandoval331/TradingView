from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow.parquet as pq


# ============================================================================
# CONFIG
# ============================================================================

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

CACHE_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_cache_v1"
)

OUTPUT_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

EVENTS_OUTPUT = (
    OUTPUT_ROOT
    / "second1m_alt_entry_events_v1.parquet"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "second1m_alt_entry_summary_v1.csv"
)

DIRECTION_SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "second1m_alt_entry_direction_summary_v1.csv"
)

POPULATION_OUTPUT = (
    OUTPUT_ROOT
    / "second1m_alt_entry_population_v1.csv"
)


FAVORABLE_TARGET_PCT = 0.50
ADVERSE_TARGET_PCT = 0.50

EXPECTED_SYMBOLS = 112
EXPECTED_PARTITIONS = 224

CACHE_VERSION = "SECOND1M_ALT_ENTRY_CACHE_V1"
RESEARCH_VERSION = "SECOND1M_ALT_ENTRY_RESEARCH_V1"


# ============================================================================
# EVENT RECORD
# ============================================================================

@dataclass
class EventRecord:
    symbol: str
    trade_date: str
    direction: str

    architecture: str
    decision_candle: int

    entry_timestamp: pd.Timestamp
    entry_price: float

    c1_open: float
    c1_high: float
    c1_low: float
    c1_close: float
    c1_volume: float
    c1_vwap: float

    c2_open: float
    c2_high: float
    c2_low: float
    c2_close: float
    c2_volume: float
    c2_vwap: float

    c3_open: Optional[float]
    c3_high: Optional[float]
    c3_low: Optional[float]
    c3_close: Optional[float]
    c3_volume: Optional[float]
    c3_vwap: Optional[float]

    c1_direction_aligned: bool
    c1_vwap_close_ok: bool

    c2_direction_aligned: bool
    c2_vwap_close_ok: bool
    c2_no_touch_ok: bool
    c2_vwap_touch_or_cross: bool

    c3_directional_confirmation: Optional[bool]

    favorable_target_price: float
    adverse_target_price: float

    outcome: str
    first_favorable_timestamp: Optional[pd.Timestamp]
    first_adverse_timestamp: Optional[pd.Timestamp]

    minutes_to_favorable_050: Optional[float]
    minutes_to_adverse_050: Optional[float]

    final_mfe_pct: float
    final_mae_pct: float

    research_version: str


# ============================================================================
# HELPERS
# ============================================================================

def directional_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """
    Reconstruct Pine RTH VWAP:
        cumulative(HLC3 * volume) / cumulative(volume)
    """

    tp = (
        high.astype(float)
        + low.astype(float)
        + close.astype(float)
    ) / 3.0

    pv = tp * volume.astype(float)

    cumulative_pv = pv.cumsum()
    cumulative_volume = volume.astype(float).cumsum()

    return cumulative_pv / cumulative_volume.replace(0, pd.NA)


def get_bar(
    day: pd.DataFrame,
    hhmm: str,
) -> Optional[pd.Series]:

    x = day.loc[
        day["_time_et"] == hhmm
    ]

    if x.empty:
        return None

    return x.iloc[0]


def safe_float(value) -> Optional[float]:

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return float(value)


def evaluate_outcome(
    future_bars: pd.DataFrame,
    direction: str,
    entry_timestamp: pd.Timestamp,
    entry_price: float,
) -> dict:

    if direction == "BULL":
        favorable_target = (
            entry_price
            * (1.0 + FAVORABLE_TARGET_PCT / 100.0)
        )

        adverse_target = (
            entry_price
            * (1.0 - ADVERSE_TARGET_PCT / 100.0)
        )

    elif direction == "BEAR":
        favorable_target = (
            entry_price
            * (1.0 - FAVORABLE_TARGET_PCT / 100.0)
        )

        adverse_target = (
            entry_price
            * (1.0 + ADVERSE_TARGET_PCT / 100.0)
        )

    else:
        raise ValueError(
            f"Unexpected direction: {direction}"
        )

    first_favorable_timestamp = None
    first_adverse_timestamp = None
    outcome = "UNRESOLVED"

    highest = entry_price
    lowest = entry_price

    for row in future_bars.itertuples():

        high = float(row.high)
        low = float(row.low)
        ts = row.timestamp_utc

        highest = max(
            highest,
            high,
        )

        lowest = min(
            lowest,
            low,
        )

        if direction == "BULL":

            favorable_hit = (
                high >= favorable_target
            )

            adverse_hit = (
                low <= adverse_target
            )

        else:

            favorable_hit = (
                low <= favorable_target
            )

            adverse_hit = (
                high >= adverse_target
            )

        if (
            favorable_hit
            and first_favorable_timestamp is None
        ):
            first_favorable_timestamp = ts

        if (
            adverse_hit
            and first_adverse_timestamp is None
        ):
            first_adverse_timestamp = ts

        if favorable_hit and adverse_hit:
            outcome = "BOTH_SAME_BAR"
            break

        if favorable_hit:
            outcome = "FAVORABLE_FIRST"
            break

        if adverse_hit:
            outcome = "ADVERSE_FIRST"
            break

    # Full-session MFE / MAE.
    # We intentionally compute this from all post-entry bars,
    # not only bars before first resolution.

    if not future_bars.empty:

        highest = max(
            entry_price,
            float(future_bars["high"].max()),
        )

        lowest = min(
            entry_price,
            float(future_bars["low"].min()),
        )

    if direction == "BULL":

        final_mfe_pct = (
            (highest - entry_price)
            / entry_price
            * 100.0
        )

        final_mae_pct = (
            (entry_price - lowest)
            / entry_price
            * 100.0
        )

    else:

        final_mfe_pct = (
            (entry_price - lowest)
            / entry_price
            * 100.0
        )

        final_mae_pct = (
            (highest - entry_price)
            / entry_price
            * 100.0
        )

    minutes_to_favorable = None

    if first_favorable_timestamp is not None:
        minutes_to_favorable = (
            first_favorable_timestamp
            - entry_timestamp
        ).total_seconds() / 60.0

    minutes_to_adverse = None

    if first_adverse_timestamp is not None:
        minutes_to_adverse = (
            first_adverse_timestamp
            - entry_timestamp
        ).total_seconds() / 60.0

    return {
        "favorable_target_price":
            favorable_target,

        "adverse_target_price":
            adverse_target,

        "outcome":
            outcome,

        "first_favorable_timestamp":
            first_favorable_timestamp,

        "first_adverse_timestamp":
            first_adverse_timestamp,

        "minutes_to_favorable_050":
            minutes_to_favorable,

        "minutes_to_adverse_050":
            minutes_to_adverse,

        "final_mfe_pct":
            max(final_mfe_pct, 0.0),

        "final_mae_pct":
            max(final_mae_pct, 0.0),
    }


def build_event(
    *,
    symbol: str,
    trade_date,
    direction: str,
    architecture: str,
    decision_candle: int,
    c1: pd.Series,
    c2: pd.Series,
    c3: Optional[pd.Series],
    day: pd.DataFrame,
    c1_direction_aligned: bool,
    c1_vwap_close_ok: bool,
    c2_direction_aligned: bool,
    c2_vwap_close_ok: bool,
    c2_no_touch_ok: bool,
    c2_vwap_touch_or_cross: bool,
    c3_directional_confirmation: Optional[bool],
) -> EventRecord:

    if decision_candle == 2:
        entry_bar = c2

    elif decision_candle == 3:
        if c3 is None:
            raise RuntimeError(
                "C3 event requested without C3 bar."
            )

        entry_bar = c3

    else:
        raise ValueError(
            f"Unexpected decision candle: {decision_candle}"
        )

    entry_timestamp = (
        entry_bar["timestamp_utc"]
    )

    entry_price = float(
        entry_bar["close"]
    )

    future_bars = day.loc[
        day["timestamp_utc"]
        > entry_timestamp
    ].copy()

    outcome = evaluate_outcome(
        future_bars=
            future_bars,

        direction=
            direction,

        entry_timestamp=
            entry_timestamp,

        entry_price=
            entry_price,
    )

    return EventRecord(
        symbol=symbol,
        trade_date=str(trade_date),
        direction=direction,

        architecture=
            architecture,

        decision_candle=
            decision_candle,

        entry_timestamp=
            entry_timestamp,

        entry_price=
            entry_price,

        c1_open=float(c1["open"]),
        c1_high=float(c1["high"]),
        c1_low=float(c1["low"]),
        c1_close=float(c1["close"]),
        c1_volume=float(c1["volume"]),
        c1_vwap=float(c1["_pine_vwap"]),

        c2_open=float(c2["open"]),
        c2_high=float(c2["high"]),
        c2_low=float(c2["low"]),
        c2_close=float(c2["close"]),
        c2_volume=float(c2["volume"]),
        c2_vwap=float(c2["_pine_vwap"]),

        c3_open=(
            safe_float(c3["open"])
            if c3 is not None
            else None
        ),

        c3_high=(
            safe_float(c3["high"])
            if c3 is not None
            else None
        ),

        c3_low=(
            safe_float(c3["low"])
            if c3 is not None
            else None
        ),

        c3_close=(
            safe_float(c3["close"])
            if c3 is not None
            else None
        ),

        c3_volume=(
            safe_float(c3["volume"])
            if c3 is not None
            else None
        ),

        c3_vwap=(
            safe_float(c3["_pine_vwap"])
            if c3 is not None
            else None
        ),

        c1_direction_aligned=
            c1_direction_aligned,

        c1_vwap_close_ok=
            c1_vwap_close_ok,

        c2_direction_aligned=
            c2_direction_aligned,

        c2_vwap_close_ok=
            c2_vwap_close_ok,

        c2_no_touch_ok=
            c2_no_touch_ok,

        c2_vwap_touch_or_cross=
            c2_vwap_touch_or_cross,

        c3_directional_confirmation=
            c3_directional_confirmation,

        favorable_target_price=
            outcome[
                "favorable_target_price"
            ],

        adverse_target_price=
            outcome[
                "adverse_target_price"
            ],

        outcome=
            outcome["outcome"],

        first_favorable_timestamp=
            outcome[
                "first_favorable_timestamp"
            ],

        first_adverse_timestamp=
            outcome[
                "first_adverse_timestamp"
            ],

        minutes_to_favorable_050=
            outcome[
                "minutes_to_favorable_050"
            ],

        minutes_to_adverse_050=
            outcome[
                "minutes_to_adverse_050"
            ],

        final_mfe_pct=
            outcome[
                "final_mfe_pct"
            ],

        final_mae_pct=
            outcome[
                "final_mae_pct"
            ],

        research_version=
            RESEARCH_VERSION,
    )


# ============================================================================
# CLASSIFY ONE COMPLETE OPENING
# ============================================================================

def classify_day(
    day: pd.DataFrame,
) -> tuple[list[EventRecord], dict]:

    symbol = str(
        day["symbol"].iloc[0]
    )

    trade_date = (
        day["trade_date"].iloc[0]
    )

    c1 = get_bar(
        day,
        "09:30",
    )

    c2 = get_bar(
        day,
        "09:31",
    )

    c3 = get_bar(
        day,
        "09:32",
    )

    population = {
        "symbol": symbol,
        "trade_date": str(trade_date),
        "has_c1": c1 is not None,
        "has_c2": c2 is not None,
        "has_c3": c3 is not None,
        "complete_c1_c2":
            c1 is not None
            and c2 is not None,
        "complete_c1_c2_c3":
            c1 is not None
            and c2 is not None
            and c3 is not None,
        "direction": None,
        "c1_valid": False,
        "ae0_clean": False,
        "ae2_reclaim": False,
        "ae3_color_relaxed": False,
        "ae4_reclaim_c3": False,
        "ae5_color_c3": False,
        "nc_vwap_close_fail": False,
    }

    events: list[
        EventRecord
    ] = []

    if c1 is None or c2 is None:
        return events, population

    c1_open = float(c1["open"])
    c1_close = float(c1["close"])
    c1_vwap = float(c1["_pine_vwap"])

    c2_open = float(c2["open"])
    c2_high = float(c2["high"])
    c2_low = float(c2["low"])
    c2_close = float(c2["close"])
    c2_vwap = float(c2["_pine_vwap"])

    # C1 establishes prospective direction.
    if (
        c1_close > c1_open
        and c1_close > c1_vwap
    ):
        direction = "BULL"

    elif (
        c1_close < c1_open
        and c1_close < c1_vwap
    ):
        direction = "BEAR"

    else:
        return events, population

    population["direction"] = (
        direction
    )

    population["c1_valid"] = True

    c1_direction_aligned = True
    c1_vwap_close_ok = True

    if direction == "BULL":

        c2_direction_aligned = (
            c2_close > c2_open
        )

        c2_vwap_close_ok = (
            c2_close > c2_vwap
        )

        c2_no_touch_ok = (
            c2_low > c2_vwap
        )

        c2_vwap_touch_or_cross = (
            c2_low <= c2_vwap
        )

        if c3 is not None:

            c3_directional_confirmation = (
                float(c3["close"])
                > c2_close
            )

        else:

            c3_directional_confirmation = None

    else:

        c2_direction_aligned = (
            c2_close < c2_open
        )

        c2_vwap_close_ok = (
            c2_close < c2_vwap
        )

        c2_no_touch_ok = (
            c2_high < c2_vwap
        )

        c2_vwap_touch_or_cross = (
            c2_high >= c2_vwap
        )

        if c3 is not None:

            c3_directional_confirmation = (
                float(c3["close"])
                < c2_close
            )

        else:

            c3_directional_confirmation = None

    # ----------------------------------------------------------------------
    # AE0 — Exact frozen Pine research-event structure.
    # ----------------------------------------------------------------------

    ae0 = (
        c2_direction_aligned
        and c2_vwap_close_ok
        and c2_no_touch_ok
    )

    # ----------------------------------------------------------------------
    # AE2 — VWAP touch/cross + reclaim.
    # Keeps C2 directional alignment.
    # ----------------------------------------------------------------------

    ae2 = (
        c2_direction_aligned
        and c2_vwap_close_ok
        and c2_vwap_touch_or_cross
    )

    # ----------------------------------------------------------------------
    # AE3 — C2 color relaxed.
    # Preserve clean/no-touch VWAP structure.
    # ----------------------------------------------------------------------

    ae3 = (
        (not c2_direction_aligned)
        and c2_vwap_close_ok
        and c2_no_touch_ok
    )

    # ----------------------------------------------------------------------
    # Negative control — C2 closes wrong side of VWAP.
    # ----------------------------------------------------------------------

    nc_vwap_close_fail = (
        not c2_vwap_close_ok
    )

    # ----------------------------------------------------------------------
    # C3 confirmations.
    # ----------------------------------------------------------------------

    ae4 = (
        ae2
        and c3 is not None
        and c3_directional_confirmation is True
    )

    ae5 = (
        ae3
        and c3 is not None
        and c3_directional_confirmation is True
    )

    population[
        "ae0_clean"
    ] = ae0

    population[
        "ae2_reclaim"
    ] = ae2

    population[
        "ae3_color_relaxed"
    ] = ae3

    population[
        "ae4_reclaim_c3"
    ] = ae4

    population[
        "ae5_color_c3"
    ] = ae5

    population[
        "nc_vwap_close_fail"
    ] = nc_vwap_close_fail

    if ae0:

        events.append(
            build_event(
                symbol=symbol,
                trade_date=trade_date,
                direction=direction,
                architecture=
                    "AE0_CLEAN",
                decision_candle=2,
                c1=c1,
                c2=c2,
                c3=c3,
                day=day,
                c1_direction_aligned=
                    c1_direction_aligned,
                c1_vwap_close_ok=
                    c1_vwap_close_ok,
                c2_direction_aligned=
                    c2_direction_aligned,
                c2_vwap_close_ok=
                    c2_vwap_close_ok,
                c2_no_touch_ok=
                    c2_no_touch_ok,
                c2_vwap_touch_or_cross=
                    c2_vwap_touch_or_cross,
                c3_directional_confirmation=
                    c3_directional_confirmation,
            )
        )

    if ae2:

        events.append(
            build_event(
                symbol=symbol,
                trade_date=trade_date,
                direction=direction,
                architecture=
                    "AE2_RECLAIM",
                decision_candle=2,
                c1=c1,
                c2=c2,
                c3=c3,
                day=day,
                c1_direction_aligned=
                    c1_direction_aligned,
                c1_vwap_close_ok=
                    c1_vwap_close_ok,
                c2_direction_aligned=
                    c2_direction_aligned,
                c2_vwap_close_ok=
                    c2_vwap_close_ok,
                c2_no_touch_ok=
                    c2_no_touch_ok,
                c2_vwap_touch_or_cross=
                    c2_vwap_touch_or_cross,
                c3_directional_confirmation=
                    c3_directional_confirmation,
            )
        )

    if ae3:

        events.append(
            build_event(
                symbol=symbol,
                trade_date=trade_date,
                direction=direction,
                architecture=
                    "AE3_COLOR_RELAXED",
                decision_candle=2,
                c1=c1,
                c2=c2,
                c3=c3,
                day=day,
                c1_direction_aligned=
                    c1_direction_aligned,
                c1_vwap_close_ok=
                    c1_vwap_close_ok,
                c2_direction_aligned=
                    c2_direction_aligned,
                c2_vwap_close_ok=
                    c2_vwap_close_ok,
                c2_no_touch_ok=
                    c2_no_touch_ok,
                c2_vwap_touch_or_cross=
                    c2_vwap_touch_or_cross,
                c3_directional_confirmation=
                    c3_directional_confirmation,
            )
        )

    if ae4:

        events.append(
            build_event(
                symbol=symbol,
                trade_date=trade_date,
                direction=direction,
                architecture=
                    "AE4_RECLAIM_C3",
                decision_candle=3,
                c1=c1,
                c2=c2,
                c3=c3,
                day=day,
                c1_direction_aligned=
                    c1_direction_aligned,
                c1_vwap_close_ok=
                    c1_vwap_close_ok,
                c2_direction_aligned=
                    c2_direction_aligned,
                c2_vwap_close_ok=
                    c2_vwap_close_ok,
                c2_no_touch_ok=
                    c2_no_touch_ok,
                c2_vwap_touch_or_cross=
                    c2_vwap_touch_or_cross,
                c3_directional_confirmation=
                    c3_directional_confirmation,
            )
        )

    if ae5:

        events.append(
            build_event(
                symbol=symbol,
                trade_date=trade_date,
                direction=direction,
                architecture=
                    "AE5_COLOR_C3",
                decision_candle=3,
                c1=c1,
                c2=c2,
                c3=c3,
                day=day,
                c1_direction_aligned=
                    c1_direction_aligned,
                c1_vwap_close_ok=
                    c1_vwap_close_ok,
                c2_direction_aligned=
                    c2_direction_aligned,
                c2_vwap_close_ok=
                    c2_vwap_close_ok,
                c2_no_touch_ok=
                    c2_no_touch_ok,
                c2_vwap_touch_or_cross=
                    c2_vwap_touch_or_cross,
                c3_directional_confirmation=
                    c3_directional_confirmation,
            )
        )

    if nc_vwap_close_fail:

        events.append(
            build_event(
                symbol=symbol,
                trade_date=trade_date,
                direction=direction,
                architecture=
                    "NC_VWAP_CLOSE_FAIL",
                decision_candle=2,
                c1=c1,
                c2=c2,
                c3=c3,
                day=day,
                c1_direction_aligned=
                    c1_direction_aligned,
                c1_vwap_close_ok=
                    c1_vwap_close_ok,
                c2_direction_aligned=
                    c2_direction_aligned,
                c2_vwap_close_ok=
                    c2_vwap_close_ok,
                c2_no_touch_ok=
                    c2_no_touch_ok,
                c2_vwap_touch_or_cross=
                    c2_vwap_touch_or_cross,
                c3_directional_confirmation=
                    c3_directional_confirmation,
            )
        )

    return events, population


# ============================================================================
# SUMMARIES
# ============================================================================

def summarize(
    events_df: pd.DataFrame,
    group_cols: list[str],
) -> pd.DataFrame:

    rows = []

    grouped = events_df.groupby(
        group_cols,
        dropna=False,
    )

    for keys, x in grouped:

        if not isinstance(
            keys,
            tuple,
        ):
            keys = (keys,)

        base = dict(
            zip(
                group_cols,
                keys,
            )
        )

        favorable_n = int(
            (
                x["outcome"]
                == "FAVORABLE_FIRST"
            ).sum()
        )

        adverse_n = int(
            (
                x["outcome"]
                == "ADVERSE_FIRST"
            ).sum()
        )

        both_n = int(
            (
                x["outcome"]
                == "BOTH_SAME_BAR"
            ).sum()
        )

        unresolved_n = int(
            (
                x["outcome"]
                == "UNRESOLVED"
            ).sum()
        )

        binary_n = (
            favorable_n
            + adverse_n
        )

        favorable_first_pct = (
            100.0
            * favorable_n
            / binary_n
            if binary_n
            else None
        )

        row = {
            **base,

            "total_n":
                len(x),

            "binary_n":
                binary_n,

            "favorable_n":
                favorable_n,

            "adverse_n":
                adverse_n,

            "both_n":
                both_n,

            "unresolved_n":
                unresolved_n,

            "favorable_first_pct":
                favorable_first_pct,

            "avg_mfe_pct":
                x[
                    "final_mfe_pct"
                ].mean(),

            "avg_mae_pct":
                x[
                    "final_mae_pct"
                ].mean(),

            "median_mfe_pct":
                x[
                    "final_mfe_pct"
                ].median(),

            "median_mae_pct":
                x[
                    "final_mae_pct"
                ].median(),

            "avg_minutes_to_favorable":
                x[
                    "minutes_to_favorable_050"
                ].mean(),

            "avg_minutes_to_adverse":
                x[
                    "minutes_to_adverse_050"
                ].mean(),

            "symbol_n":
                x["symbol"].nunique(),

            "trade_date_n":
                x["trade_date"].nunique(),
        }

        rows.append(row)

    result = pd.DataFrame(rows)

    sort_cols = [
        col
        for col
        in group_cols
        if col in result.columns
    ]

    if sort_cols:
        result = result.sort_values(
            sort_cols
        )

    return result.reset_index(
        drop=True
    )


# ============================================================================
# MAIN
# ============================================================================

def main():

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    parquet_files = sorted(
        CACHE_ROOT.rglob(
            "*.parquet"
        )
    )

    print("=" * 80)
    print(
        "SECOND 1M ALTERNATIVE ENTRY "
        "RESEARCH V1"
    )
    print("=" * 80)

    print(
        f"Cache partitions: "
        f"{len(parquet_files):,}"
    )

    if (
        len(parquet_files)
        != EXPECTED_PARTITIONS
    ):
        raise RuntimeError(
            f"Expected "
            f"{EXPECTED_PARTITIONS} "
            f"partitions, found "
            f"{len(parquet_files)}."
        )

    all_events = []
    all_population = []

    processed_days = 0

    for i, path in enumerate(
        parquet_files,
        start=1,
    ):

        table = pq.read_table(
            path,
            columns=[
                "symbol",
                "trade_date",
                "timestamp_utc",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "session",
            ],
        )

        df = table.to_pandas()

        if df.empty:
            continue

        df["symbol"] = (
            df["symbol"]
            .astype(str)
            .str.upper()
        )

        df["trade_date"] = (
            pd.to_datetime(
                df["trade_date"]
            )
            .dt
            .date
        )

        df["timestamp_utc"] = (
            pd.to_datetime(
                df["timestamp_utc"],
                utc=True,
            )
        )

        # Alternative Entry V1 uses RTH only.
        df = df.loc[
            df["session"] == "RTH"
        ].copy()

        if df.empty:
            continue

        df = df.sort_values(
            [
                "symbol",
                "trade_date",
                "timestamp_utc",
            ]
        )

        et = (
            df["timestamp_utc"]
            .dt
            .tz_convert(
                "America/New_York"
            )
        )

        df["_time_et"] = (
            et.dt.strftime(
                "%H:%M"
            )
        )

        for (
            symbol,
            trade_date,
        ), day in df.groupby(
            [
                "symbol",
                "trade_date",
            ],
            sort=False,
        ):

            day = (
                day
                .sort_values(
                    "timestamp_utc"
                )
                .copy()
            )

            day["_pine_vwap"] = (
                directional_vwap(
                    day["high"],
                    day["low"],
                    day["close"],
                    day["volume"],
                )
            )

            events, population = (
                classify_day(day)
            )

            all_population.append(
                population
            )

            for event in events:
                all_events.append(
                    asdict(event)
                )

            processed_days += 1

        if (
            i % 20 == 0
            or i
            == len(parquet_files)
        ):

            print(
                f"Processed "
                f"{i:>3}/"
                f"{len(parquet_files)} "
                f"| symbol-days="
                f"{processed_days:,} "
                f"| events="
                f"{len(all_events):,}"
            )

    population_df = pd.DataFrame(
        all_population
    )

    events_df = pd.DataFrame(
        all_events
    )

    if population_df.empty:
        raise RuntimeError(
            "Population output is empty."
        )

    if events_df.empty:
        raise RuntimeError(
            "No Alternative C2 events "
            "were generated."
        )

    # ======================================================================
    # WRITE EVENT DATASET
    # ======================================================================

    events_df.to_parquet(
        EVENTS_OUTPUT,
        index=False,
    )

    population_df.to_csv(
        POPULATION_OUTPUT,
        index=False,
    )

    summary = summarize(
        events_df,
        ["architecture"],
    )

    direction_summary = summarize(
        events_df,
        [
            "architecture",
            "direction",
        ],
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    direction_summary.to_csv(
        DIRECTION_SUMMARY_OUTPUT,
        index=False,
    )

    # ======================================================================
    # REPORT POPULATION
    # ======================================================================

    print()
    print("=" * 80)
    print("POPULATION")
    print("=" * 80)

    print(
        f"Symbol-days:           "
        f"{len(population_df):,}"
    )

    print(
        f"Complete C1+C2:        "
        f"{int(population_df['complete_c1_c2'].sum()):,}"
    )

    print(
        f"Complete C1+C2+C3:     "
        f"{int(population_df['complete_c1_c2_c3'].sum()):,}"
    )

    print(
        f"C1-valid directional:  "
        f"{int(population_df['c1_valid'].sum()):,}"
    )

    print()

    architecture_cols = [
        (
            "AE0_CLEAN",
            "ae0_clean",
        ),
        (
            "AE2_RECLAIM",
            "ae2_reclaim",
        ),
        (
            "AE3_COLOR_RELAXED",
            "ae3_color_relaxed",
        ),
        (
            "AE4_RECLAIM_C3",
            "ae4_reclaim_c3",
        ),
        (
            "AE5_COLOR_C3",
            "ae5_color_c3",
        ),
        (
            "NC_VWAP_CLOSE_FAIL",
            "nc_vwap_close_fail",
        ),
    ]

    for label, col in architecture_cols:

        n = int(
            population_df[col].sum()
        )

        print(
            f"{label:<22} "
            f"{n:>7,}"
        )

    # ======================================================================
    # REPORT ARCHITECTURE RESULTS
    # ======================================================================

    print()
    print("=" * 80)
    print(
        "ARCHITECTURE OUTCOMES"
    )
    print("=" * 80)

    display_cols = [
        "architecture",
        "total_n",
        "binary_n",
        "favorable_n",
        "adverse_n",
        "both_n",
        "unresolved_n",
        "favorable_first_pct",
        "avg_mfe_pct",
        "avg_mae_pct",
        "median_mfe_pct",
        "median_mae_pct",
        "symbol_n",
    ]

    print(
        summary[
            display_cols
        ].to_string(
            index=False,
            float_format=lambda x:
                f"{x:.2f}",
        )
    )

    print()
    print("=" * 80)
    print(
        "DIRECTIONAL OUTCOMES"
    )
    print("=" * 80)

    direction_display = [
        "architecture",
        "direction",
        "total_n",
        "binary_n",
        "favorable_first_pct",
        "avg_mfe_pct",
        "avg_mae_pct",
        "symbol_n",
    ]

    print(
        direction_summary[
            direction_display
        ].to_string(
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
        f"Events:      "
        f"{EVENTS_OUTPUT}"
    )

    print(
        f"Population:  "
        f"{POPULATION_OUTPUT}"
    )

    print(
        f"Summary:     "
        f"{SUMMARY_OUTPUT}"
    )

    print(
        f"By direction:"
        f" {DIRECTION_SUMMARY_OUTPUT}"
    )

    print()
    print("RESULT: COMPLETE")


if __name__ == "__main__":
    main()