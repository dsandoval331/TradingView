from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


# =============================================================================
# CONFIG
# =============================================================================

ROOT = Path(
    r"C:\Users\DirtySouth\TradingResearch"
)

CACHE_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_cache_v1"
    / "partitions"
)

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

INPUT_PATH = (
    RESEARCH_ROOT
    / "ae2_volume_robustness_v1"
    / "ae2_volume_robustness_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_session_levels_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_level_features_v1.parquet"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_level_summary_v1.csv"
)

DIRECTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_level_direction_v1.csv"
)

PROXIMITY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_level_proximity_v1.csv"
)

THRESHOLD_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_level_discovery_thresholds_v1.csv"
)

CONFLUENCE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_level_confluence_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_level_quarter_v1.csv"
)

INTERACTION_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_level_interactions_v1.csv"
)

COVERAGE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_session_level_coverage_v1.csv"
)

EXPECTED_SYMBOLS = 112


# =============================================================================
# DATETIME HELPERS
# =============================================================================

def normalize_date_ns(
    series: pd.Series,
) -> pd.Series:
    """
    Convert a date/datetime-like Series to timezone-naive midnight
    datetime64[ns].

    This is used explicitly for every merge key so pandas merge/merge_asof
    cannot fail because one parquet path produced datetime64[s] while another
    produced datetime64[us] or datetime64[ns].
    """

    result = (
        pd.to_datetime(
            series,
            errors="coerce",
        )
        .dt
        .normalize()
    )

    return result.astype(
        "datetime64[ns]"
    )


# =============================================================================
# GENERAL SUMMARY HELPERS
# =============================================================================

def summarize_group(
    x: pd.DataFrame,
) -> dict:

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
        else np.nan
    )

    c3_confirmed_n = int(
        x["c3_confirmed"].sum()
    )

    c3_confirmation_pct = (
        100.0
        * c3_confirmed_n
        / len(x)
        if len(x)
        else np.nan
    )

    return {
        "total_n":
            int(len(x)),

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

        "c3_confirmation_pct":
            c3_confirmation_pct,

        "avg_mfe_pct":
            x["final_mfe_pct"].mean(),

        "avg_mae_pct":
            x["final_mae_pct"].mean(),

        "median_mfe_pct":
            x["final_mfe_pct"].median(),

        "median_mae_pct":
            x["final_mae_pct"].median(),

        "symbol_n":
            x["symbol"].nunique(),

        "trade_date_n":
            x["trade_date"].nunique(),
    }


def summarize(
    df: pd.DataFrame,
    group_cols: list[str],
) -> pd.DataFrame:

    rows = []

    for keys, x in df.groupby(
        group_cols,
        dropna=False,
    ):

        if not isinstance(
            keys,
            tuple,
        ):
            keys = (keys,)

        row = dict(
            zip(
                group_cols,
                keys,
            )
        )

        row.update(
            summarize_group(x)
        )

        rows.append(row)

    return pd.DataFrame(
        rows
    )


# =============================================================================
# CACHE HELPERS
# =============================================================================

def get_symbol_paths(
    symbol: str,
) -> list[Path]:

    symbol_dir = (
        CACHE_ROOT
        / symbol
    )

    if not symbol_dir.exists():

        raise RuntimeError(
            f"Cache directory not found "
            f"for {symbol}: {symbol_dir}"
        )

    paths = sorted(
        symbol_dir.glob(
            f"{symbol}_*.parquet"
        )
    )

    if not paths:

        raise RuntimeError(
            f"No cache partitions found "
            f"for {symbol}"
        )

    return paths


# =============================================================================
# LOAD / RECONSTRUCT SESSION LEVELS
# =============================================================================

def load_symbol_session_levels(
    symbol: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    paths = get_symbol_paths(
        symbol
    )

    frames = []

    for path in paths:

        table = pq.read_table(
            path,
            columns=[
                "symbol",
                "timestamp_et",
                "trade_date",
                "high",
                "low",
                "close",
                "session",
            ],
        )

        frames.append(
            table.to_pandas()
        )

    bars = pd.concat(
        frames,
        ignore_index=True,
    )

    bars[
        "symbol"
    ] = (
        bars[
            "symbol"
        ]
        .astype(str)
        .str.upper()
    )

    # -------------------------------------------------------------------------
    # CRITICAL DATETIME NORMALIZATION
    # -------------------------------------------------------------------------

    bars[
        "trade_date"
    ] = normalize_date_ns(
        bars[
            "trade_date"
        ]
    )

    # timestamp_et values are timezone-aware in the parquet cache.
    # utc=True safely normalizes offsets across EST/EDT before converting back
    # to America/New_York.
    bars[
        "timestamp_et"
    ] = (
        pd.to_datetime(
            bars[
                "timestamp_et"
            ],
            utc=True,
            errors="coerce",
        )
        .dt
        .tz_convert(
            "America/New_York"
        )
    )

    bars = (
        bars
        .dropna(
            subset=[
                "timestamp_et",
                "trade_date",
            ]
        )
        .sort_values(
            "timestamp_et"
        )
        .drop_duplicates(
            subset=[
                "timestamp_et"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    # =========================================================================
    # CURRENT-DAY PREMARKET
    #
    # PRE = 04:00 through 09:29 ET from the acquisition pipeline.
    # =========================================================================

    pre = bars.loc[
        bars[
            "session"
        ]
        == "PRE"
    ].copy()

    pre_daily = (
        pre.groupby(
            "trade_date",
            as_index=False,
        )
        .agg(
            pmh=(
                "high",
                "max",
            ),
            pml=(
                "low",
                "min",
            ),
            pre_last_close=(
                "close",
                "last",
            ),
            pre_bar_n=(
                "close",
                "size",
            ),
        )
    )

    pre_daily[
        "symbol"
    ] = symbol

    # Explicit ns normalization after groupby.
    pre_daily[
        "trade_date"
    ] = normalize_date_ns(
        pre_daily[
            "trade_date"
        ]
    )

    # =========================================================================
    # PREVIOUS COMPLETED RTH SESSION
    #
    # PDH / PDL are calculated from the completed previous RTH day.
    # =========================================================================

    rth = bars.loc[
        bars[
            "session"
        ]
        == "RTH"
    ].copy()

    rth_daily = (
        rth.groupby(
            "trade_date",
            as_index=False,
        )
        .agg(
            pdh=(
                "high",
                "max",
            ),
            pdl=(
                "low",
                "min",
            ),
            prior_rth_close=(
                "close",
                "last",
            ),
            prior_rth_bar_n=(
                "close",
                "size",
            ),
        )
    )

    rth_daily[
        "trade_date"
    ] = normalize_date_ns(
        rth_daily[
            "trade_date"
        ]
    )

    # =========================================================================
    # PREVIOUS COMPLETED AFTER-HOURS SESSION
    #
    # AH = 16:00 through 19:59 ET.
    #
    # The AH session belongs to the same calendar/trading date as the completed
    # RTH session. We later attach the entire completed date to the next AE2
    # trade using a strict prior-date merge.
    # =========================================================================

    ah = bars.loc[
        bars[
            "session"
        ]
        == "AH"
    ].copy()

    ah_daily = (
        ah.groupby(
            "trade_date",
            as_index=False,
        )
        .agg(
            ahh=(
                "high",
                "max",
            ),
            ahl=(
                "low",
                "min",
            ),
            prior_ah_close=(
                "close",
                "last",
            ),
            prior_ah_bar_n=(
                "close",
                "size",
            ),
        )
    )

    ah_daily[
        "trade_date"
    ] = normalize_date_ns(
        ah_daily[
            "trade_date"
        ]
    )

    # =========================================================================
    # COMBINE COMPLETED RTH + AH
    # =========================================================================

    prior_daily = (
        rth_daily.merge(
            ah_daily,
            on="trade_date",
            how="left",
            validate="one_to_one",
        )
    )

    prior_daily = prior_daily.rename(
        columns={
            "trade_date":
                "prior_session_date",
        }
    )

    # -------------------------------------------------------------------------
    # CRITICAL FIX:
    # Explicitly enforce datetime64[ns] AFTER rename/merge.
    # -------------------------------------------------------------------------

    prior_daily[
        "prior_session_date"
    ] = normalize_date_ns(
        prior_daily[
            "prior_session_date"
        ]
    )

    prior_daily[
        "symbol"
    ] = symbol

    pre_daily = (
        pre_daily
        .sort_values(
            [
                "symbol",
                "trade_date",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    prior_daily = (
        prior_daily
        .sort_values(
            [
                "symbol",
                "prior_session_date",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return (
        pre_daily,
        prior_daily,
    )


# =============================================================================
# DIRECTIONAL LEVEL HELPERS
# =============================================================================

def select_directional_level(
    direction: str,
    high_level: float,
    low_level: float,
) -> float:

    if direction == "BULL":
        return high_level

    if direction == "BEAR":
        return low_level

    return np.nan


def directional_barrier_distance_pct(
    direction: str,
    price: float,
    level: float,
) -> float:
    """
    Positive:
        the relevant directional barrier remains ahead.

    Negative:
        C2 close has already cleared the directional barrier.

    BULL:
        PMH / AHH / PDH

    BEAR:
        PML / AHL / PDL
    """

    if (
        pd.isna(price)
        or pd.isna(level)
        or price == 0
    ):
        return np.nan

    if direction == "BULL":

        return (
            (
                level
                - price
            )
            / price
            * 100.0
        )

    if direction == "BEAR":

        return (
            (
                price
                - level
            )
            / price
            * 100.0
        )

    return np.nan


def is_beyond(
    direction: str,
    price: float,
    level: float,
) -> bool:

    if (
        pd.isna(price)
        or pd.isna(level)
    ):
        return False

    if direction == "BULL":

        return bool(
            price > level
        )

    if direction == "BEAR":

        return bool(
            price < level
        )

    return False


def bar_traded_beyond(
    direction: str,
    bar_high: float,
    bar_low: float,
    level: float,
) -> bool:

    if (
        pd.isna(bar_high)
        or pd.isna(bar_low)
        or pd.isna(level)
    ):
        return False

    if direction == "BULL":

        return bool(
            bar_high > level
        )

    if direction == "BEAR":

        return bool(
            bar_low < level
        )

    return False


def bar_crossed_level(
    direction: str,
    bar_high: float,
    bar_low: float,
    level: float,
) -> bool:

    if (
        pd.isna(bar_high)
        or pd.isna(bar_low)
        or pd.isna(level)
    ):
        return False

    if direction == "BULL":

        return bool(
            bar_low <= level
            and bar_high > level
        )

    if direction == "BEAR":

        return bool(
            bar_high >= level
            and bar_low < level
        )

    return False


def classify_level_structure(
    direction: str,
    level: float,
    c1_open: float,
    c1_high: float,
    c1_low: float,
    c1_close: float,
    c2_high: float,
    c2_low: float,
    c2_close: float,
) -> str:

    if pd.isna(
        level
    ):
        return "UNKNOWN"

    if is_beyond(
        direction,
        c1_open,
        level,
    ):
        return "ALREADY_BEYOND_AT_C1_OPEN"

    c1_cross = bar_crossed_level(
        direction,
        c1_high,
        c1_low,
        level,
    )

    c2_cross = bar_crossed_level(
        direction,
        c2_high,
        c2_low,
        level,
    )

    c1_close_beyond = is_beyond(
        direction,
        c1_close,
        level,
    )

    c2_close_beyond = is_beyond(
        direction,
        c2_close,
        level,
    )

    c1_traded_beyond = bar_traded_beyond(
        direction,
        c1_high,
        c1_low,
        level,
    )

    c2_traded_beyond = bar_traded_beyond(
        direction,
        c2_high,
        c2_low,
        level,
    )

    if (
        c1_cross
        and c1_close_beyond
        and c2_close_beyond
    ):
        return "C1_BREAK_HELD_THROUGH_C2"

    if (
        not c1_close_beyond
        and c2_cross
        and c2_close_beyond
    ):
        return "C2_BREAK"

    if (
        c1_close_beyond
        and c2_close_beyond
    ):
        return "C1_CLOSED_BEYOND"

    if (
        (
            c1_traded_beyond
            or c2_traded_beyond
        )
        and not c2_close_beyond
    ):
        return "FAILED_BREAK"

    if c2_close_beyond:
        return "C2_CLOSED_BEYOND"

    return "NOT_CLEARED"


# =============================================================================
# PROXIMITY HELPERS
# =============================================================================

def classify_proximity(
    distance_pct: float,
    near_cutoff: float,
    far_cutoff: float,
) -> str:

    if pd.isna(
        distance_pct
    ):
        return "UNKNOWN"

    # Negative means the level has already been cleared.
    if distance_pct < 0:
        return "CLEARED"

    if distance_pct <= near_cutoff:
        return "NEAR_AHEAD"

    if distance_pct >= far_cutoff:
        return "FAR_AHEAD"

    return "MID_AHEAD"


# =============================================================================
# COMBINED / CONFLUENCE HELPERS
# =============================================================================

def count_available(
    values: list[float],
) -> int:

    return int(
        sum(
            not pd.isna(v)
            for v in values
        )
    )


def count_cleared(
    distances: list[float],
) -> int:

    return int(
        sum(
            (
                not pd.isna(v)
                and v < 0
            )
            for v in distances
        )
    )


def overall_clear_state(
    available_n: int,
    cleared_n: int,
) -> str:

    if available_n < 3:
        return "INCOMPLETE"

    if cleared_n == 3:
        return "ALL_3_CLEARED"

    if cleared_n == 2:
        return "TWO_OF_3_CLEARED"

    if cleared_n == 1:
        return "ONE_OF_3_CLEARED"

    return "NONE_CLEARED"


def level_cluster_span_pct(
    levels: list[float],
    reference_price: float,
) -> float:

    clean = [
        float(v)
        for v in levels
        if not pd.isna(v)
    ]

    if (
        len(clean) < 2
        or pd.isna(reference_price)
        or reference_price == 0
    ):
        return np.nan

    return (
        (
            max(clean)
            - min(clean)
        )
        / reference_price
        * 100.0
    )


def nearest_ahead_distance(
    distances: list[float],
) -> float:

    ahead = [
        float(v)
        for v in distances
        if (
            not pd.isna(v)
            and v >= 0
        )
    ]

    if not ahead:
        return np.nan

    return min(
        ahead
    )


def nearest_ahead_level_name(
    row: pd.Series,
) -> str:

    candidates = []

    for family in [
        "pm",
        "ah",
        "pd",
    ]:

        value = row[
            f"{family}_directional_distance_pct"
        ]

        if (
            not pd.isna(value)
            and value >= 0
        ):
            candidates.append(
                (
                    value,
                    family.upper(),
                )
            )

    if not candidates:
        return "NONE_AHEAD"

    candidates.sort(
        key=lambda x:
            x[0]
    )

    return candidates[
        0
    ][
        1
    ]


# =============================================================================
# MAIN
# =============================================================================

def main():

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not INPUT_PATH.exists():

        raise FileNotFoundError(
            f"Input not found: "
            f"{INPUT_PATH}"
        )

    events = pd.read_parquet(
        INPUT_PATH
    )

    events[
        "symbol"
    ] = (
        events[
            "symbol"
        ]
        .astype(str)
        .str.upper()
    )

    # -------------------------------------------------------------------------
    # CRITICAL DATETIME NORMALIZATION
    # -------------------------------------------------------------------------

    events[
        "trade_date"
    ] = normalize_date_ns(
        events[
            "trade_date"
        ]
    )

    required_event_cols = [
        "symbol",
        "trade_date",
        "direction",
        "research_period",
        "outcome",
        "c3_confirmed",
        "final_mfe_pct",
        "final_mae_pct",

        "c1_open",
        "c1_high",
        "c1_low",
        "c1_close",

        "c2_open",
        "c2_high",
        "c2_low",
        "c2_close",
    ]

    missing = [
        col
        for col in required_event_cols
        if col not in events.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing required event columns: "
            + ", ".join(
                missing
            )
        )

    symbols = sorted(
        events[
            "symbol"
        ].unique()
    )

    if len(
        symbols
    ) != EXPECTED_SYMBOLS:

        raise RuntimeError(
            f"Expected "
            f"{EXPECTED_SYMBOLS} symbols, "
            f"found {len(symbols)}"
        )

    print(
        "=" * 80
    )

    print(
        "AE2 SESSION LEVEL STRUCTURE "
        "PM / AH / PREVIOUS DAY V1"
    )

    print(
        "=" * 80
    )

    print(
        f"AE2 events: "
        f"{len(events):,}"
    )

    print(
        f"Symbols:    "
        f"{len(symbols):,}"
    )

    # =========================================================================
    # SESSION ENRICHMENT
    # =========================================================================

    enriched_frames = []

    for i, symbol in enumerate(
        symbols,
        start=1,
    ):

        symbol_events = (
            events.loc[
                events[
                    "symbol"
                ]
                == symbol
            ]
            .copy()
        )

        # Reassert exact merge dtype at symbol level.
        symbol_events[
            "trade_date"
        ] = normalize_date_ns(
            symbol_events[
                "trade_date"
            ]
        )

        symbol_events = (
            symbol_events
            .sort_values(
                "trade_date"
            )
            .reset_index(
                drop=True
            )
        )

        (
            pre_daily,
            prior_daily,
        ) = load_symbol_session_levels(
            symbol
        )

        # ---------------------------------------------------------------------
        # CURRENT-DAY PREMARKET
        # ---------------------------------------------------------------------

        pre_daily[
            "trade_date"
        ] = normalize_date_ns(
            pre_daily[
                "trade_date"
            ]
        )

        symbol_events = (
            symbol_events.merge(
                pre_daily,
                on=[
                    "symbol",
                    "trade_date",
                ],
                how="left",
                validate="many_to_one",
            )
        )

        # ---------------------------------------------------------------------
        # PREVIOUS COMPLETED SESSION
        #
        # Strictly earlier session:
        #
        # event day T
        # attaches most recent completed RTH/AH session before T.
        # ---------------------------------------------------------------------

        symbol_events[
            "trade_date"
        ] = normalize_date_ns(
            symbol_events[
                "trade_date"
            ]
        )

        prior_daily[
            "prior_session_date"
        ] = normalize_date_ns(
            prior_daily[
                "prior_session_date"
            ]
        )

        # Defensive dtype audit.
        if (
            symbol_events[
                "trade_date"
            ].dtype
            !=
            prior_daily[
                "prior_session_date"
            ].dtype
        ):

            raise RuntimeError(
                f"{symbol} merge dtype mismatch "
                f"after normalization: "
                f"trade_date="
                f"{symbol_events['trade_date'].dtype}, "
                f"prior_session_date="
                f"{prior_daily['prior_session_date'].dtype}"
            )

        symbol_events = (
            symbol_events
            .sort_values(
                [
                    "symbol",
                    "trade_date",
                ]
            )
            .reset_index(
                drop=True
            )
        )

        prior_daily = (
            prior_daily
            .sort_values(
                [
                    "symbol",
                    "prior_session_date",
                ]
            )
            .reset_index(
                drop=True
            )
        )

        symbol_events = pd.merge_asof(
            symbol_events,
            prior_daily,
            by="symbol",
            left_on="trade_date",
            right_on="prior_session_date",
            direction="backward",
            allow_exact_matches=False,
        )

        enriched_frames.append(
            symbol_events
        )

        if (
            i % 10 == 0
            or i == len(symbols)
        ):

            enriched_n = sum(
                len(x)
                for x in enriched_frames
            )

            print(
                f"Processed "
                f"{i:>3}/{len(symbols)} "
                f"| enriched="
                f"{enriched_n:,}"
            )

    df = pd.concat(
        enriched_frames,
        ignore_index=True,
    )

    if len(
        df
    ) != len(
        events
    ):

        raise RuntimeError(
            "Event count changed during "
            "session-level enrichment."
        )

    # =========================================================================
    # RAW LEVEL INTEGRITY
    # =========================================================================

    raw_level_cols = [
        "pmh",
        "pml",
        "ahh",
        "ahl",
        "pdh",
        "pdl",
    ]

    missing_levels = [
        col
        for col in raw_level_cols
        if col not in df.columns
    ]

    if missing_levels:

        raise RuntimeError(
            "Missing reconstructed session "
            "level columns: "
            + ", ".join(
                missing_levels
            )
        )

    # =========================================================================
    # DIRECTIONALLY RELEVANT LEVEL PRICES
    #
    # BULL:
    #   PMH / AHH / PDH
    #
    # BEAR:
    #   PML / AHL / PDL
    # =========================================================================

    df[
        "pm_directional_level"
    ] = df.apply(
        lambda r:
            select_directional_level(
                r[
                    "direction"
                ],
                r[
                    "pmh"
                ],
                r[
                    "pml"
                ],
            ),
        axis=1,
    )

    df[
        "ah_directional_level"
    ] = df.apply(
        lambda r:
            select_directional_level(
                r[
                    "direction"
                ],
                r[
                    "ahh"
                ],
                r[
                    "ahl"
                ],
            ),
        axis=1,
    )

    df[
        "pd_directional_level"
    ] = df.apply(
        lambda r:
            select_directional_level(
                r[
                    "direction"
                ],
                r[
                    "pdh"
                ],
                r[
                    "pdl"
                ],
            ),
        axis=1,
    )

    # =========================================================================
    # DIRECTIONAL DISTANCE FROM C2 CLOSE
    # =========================================================================

    for family in [
        "pm",
        "ah",
        "pd",
    ]:

        df[
            f"{family}_directional_distance_pct"
        ] = df.apply(
            lambda r,
            fam=family:
                directional_barrier_distance_pct(
                    r[
                        "direction"
                    ],
                    r[
                        "c2_close"
                    ],
                    r[
                        f"{fam}_directional_level"
                    ],
                ),
            axis=1,
        )

    # =========================================================================
    # INDIVIDUAL LEVEL STRUCTURE
    # =========================================================================

    for family in [
        "pm",
        "ah",
        "pd",
    ]:

        level_col = (
            f"{family}_directional_level"
        )

        state_col = (
            f"{family}_level_structure_state"
        )

        df[
            state_col
        ] = df.apply(
            lambda r,
            lvl=level_col:
                classify_level_structure(
                    r[
                        "direction"
                    ],
                    r[
                        lvl
                    ],
                    r[
                        "c1_open"
                    ],
                    r[
                        "c1_high"
                    ],
                    r[
                        "c1_low"
                    ],
                    r[
                        "c1_close"
                    ],
                    r[
                        "c2_high"
                    ],
                    r[
                        "c2_low"
                    ],
                    r[
                        "c2_close"
                    ],
                ),
            axis=1,
        )

        df[
            f"{family}_c1_cross"
        ] = df.apply(
            lambda r,
            lvl=level_col:
                bar_crossed_level(
                    r[
                        "direction"
                    ],
                    r[
                        "c1_high"
                    ],
                    r[
                        "c1_low"
                    ],
                    r[
                        lvl
                    ],
                ),
            axis=1,
        )

        df[
            f"{family}_c2_cross"
        ] = df.apply(
            lambda r,
            lvl=level_col:
                bar_crossed_level(
                    r[
                        "direction"
                    ],
                    r[
                        "c2_high"
                    ],
                    r[
                        "c2_low"
                    ],
                    r[
                        lvl
                    ],
                ),
            axis=1,
        )

        df[
            f"{family}_c2_closed_beyond"
        ] = df.apply(
            lambda r,
            lvl=level_col:
                is_beyond(
                    r[
                        "direction"
                    ],
                    r[
                        "c2_close"
                    ],
                    r[
                        lvl
                    ],
                ),
            axis=1,
        )

    # =========================================================================
    # DISCOVERY-FROZEN PROXIMITY THRESHOLDS
    #
    # Only levels still ahead of C2 participate in the q20/q80 derivation.
    #
    # These thresholds describe the distribution of proximity.
    # They are NOT optimized using outcome.
    # =========================================================================

    discovery = df.loc[
        df[
            "research_period"
        ]
        == "DISCOVERY"
    ].copy()

    threshold_rows = []

    for family in [
        "pm",
        "ah",
        "pd",
    ]:

        feature = (
            f"{family}_directional_distance_pct"
        )

        values = (
            discovery.loc[
                discovery[
                    feature
                ]
                >= 0,
                feature,
            ]
            .dropna()
            .astype(float)
        )

        if values.empty:

            raise RuntimeError(
                f"No discovery ahead-level "
                f"values for {feature}"
            )

        q20 = (
            values
            .quantile(
                0.20
            )
        )

        q80 = (
            values
            .quantile(
                0.80
            )
        )

        threshold_rows.append(
            {
                "level_family":
                    family.upper(),

                "feature":
                    feature,

                "discovery_ahead_q20":
                    q20,

                "discovery_ahead_q80":
                    q80,

                "discovery_ahead_n":
                    int(
                        len(
                            values
                        )
                    ),
            }
        )

        df[
            f"{family}_proximity_state"
        ] = df[
            feature
        ].apply(
            lambda x,
            low=q20,
            high=q80:
                classify_proximity(
                    x,
                    low,
                    high,
                )
        )

    thresholds = pd.DataFrame(
        threshold_rows
    )

    # =========================================================================
    # COMBINED LEVEL STRUCTURE
    # =========================================================================

    df[
        "relevant_levels_available_n"
    ] = df.apply(
        lambda r:
            count_available(
                [
                    r[
                        "pm_directional_level"
                    ],
                    r[
                        "ah_directional_level"
                    ],
                    r[
                        "pd_directional_level"
                    ],
                ]
            ),
        axis=1,
    )

    df[
        "relevant_levels_cleared_n"
    ] = df.apply(
        lambda r:
            count_cleared(
                [
                    r[
                        "pm_directional_distance_pct"
                    ],
                    r[
                        "ah_directional_distance_pct"
                    ],
                    r[
                        "pd_directional_distance_pct"
                    ],
                ]
            ),
        axis=1,
    )

    df[
        "session_level_clear_state"
    ] = df.apply(
        lambda r:
            overall_clear_state(
                int(
                    r[
                        "relevant_levels_available_n"
                    ]
                ),
                int(
                    r[
                        "relevant_levels_cleared_n"
                    ]
                ),
            ),
        axis=1,
    )

    # =========================================================================
    # LEVEL CLUSTER / CONFLUENCE
    # =========================================================================

    df[
        "relevant_level_cluster_span_pct"
    ] = df.apply(
        lambda r:
            level_cluster_span_pct(
                [
                    r[
                        "pm_directional_level"
                    ],
                    r[
                        "ah_directional_level"
                    ],
                    r[
                        "pd_directional_level"
                    ],
                ],
                r[
                    "c2_close"
                ],
            ),
        axis=1,
    )

    df[
        "nearest_ahead_level_distance_pct"
    ] = df.apply(
        lambda r:
            nearest_ahead_distance(
                [
                    r[
                        "pm_directional_distance_pct"
                    ],
                    r[
                        "ah_directional_distance_pct"
                    ],
                    r[
                        "pd_directional_distance_pct"
                    ],
                ]
            ),
        axis=1,
    )

    df[
        "nearest_ahead_level"
    ] = df.apply(
        nearest_ahead_level_name,
        axis=1,
    )

    # =========================================================================
    # DISCOVERY-FROZEN CLUSTER STATE
    # =========================================================================

    discovery_cluster = (
        df.loc[
            df[
                "research_period"
            ]
            == "DISCOVERY",
            "relevant_level_cluster_span_pct",
        ]
        .dropna()
        .astype(float)
    )

    if discovery_cluster.empty:

        raise RuntimeError(
            "No discovery cluster values."
        )

    cluster_q20 = (
        discovery_cluster
        .quantile(
            0.20
        )
    )

    cluster_q80 = (
        discovery_cluster
        .quantile(
            0.80
        )
    )

    thresholds = pd.concat(
        [
            thresholds,
            pd.DataFrame(
                [
                    {
                        "level_family":
                            "COMBINED",

                        "feature":
                            "relevant_level_cluster_span_pct",

                        "discovery_ahead_q20":
                            cluster_q20,

                        "discovery_ahead_q80":
                            cluster_q80,

                        "discovery_ahead_n":
                            int(
                                len(
                                    discovery_cluster
                                )
                            ),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    thresholds.to_csv(
        THRESHOLD_OUTPUT,
        index=False,
    )

    def cluster_state(
        value: float,
    ) -> str:

        if pd.isna(
            value
        ):
            return "UNKNOWN"

        if value <= cluster_q20:
            return "TIGHT_CLUSTER"

        if value >= cluster_q80:
            return "WIDE_CLUSTER"

        return "MODERATE_CLUSTER"

    df[
        "relevant_level_cluster_state"
    ] = df[
        "relevant_level_cluster_span_pct"
    ].apply(
        cluster_state
    )

    # =========================================================================
    # NUMBER OF LEVELS BROKEN ON C2
    # =========================================================================

    df[
        "c2_break_level_n"
    ] = (
        df[
            [
                "pm_level_structure_state",
                "ah_level_structure_state",
                "pd_level_structure_state",
            ]
        ]
        .eq(
            "C2_BREAK"
        )
        .sum(
            axis=1
        )
        .astype(int)
    )

    def c2_break_count_state(
        value: int,
    ) -> str:

        if value <= 0:
            return "NO_C2_LEVEL_BREAK"

        if value == 1:
            return "ONE_C2_LEVEL_BREAK"

        return "MULTIPLE_C2_LEVEL_BREAKS"

    df[
        "c2_break_count_state"
    ] = df[
        "c2_break_level_n"
    ].apply(
        c2_break_count_state
    )

    # =========================================================================
    # QUARTER
    # =========================================================================

    df[
        "quarter"
    ] = (
        df[
            "trade_date"
        ]
        .dt
        .to_period(
            "Q"
        )
        .astype(str)
    )

    # =========================================================================
    # COVERAGE
    # =========================================================================

    coverage_features = [
        "pmh",
        "pml",
        "ahh",
        "ahl",
        "pdh",
        "pdl",

        "pm_directional_level",
        "ah_directional_level",
        "pd_directional_level",

        "pm_directional_distance_pct",
        "ah_directional_distance_pct",
        "pd_directional_distance_pct",

        "relevant_level_cluster_span_pct",
        "nearest_ahead_level_distance_pct",
    ]

    coverage_rows = []

    for feature in (
        coverage_features
    ):

        available_n = int(
            df[
                feature
            ]
            .notna()
            .sum()
        )

        coverage_rows.append(
            {
                "feature":
                    feature,

                "available_n":
                    available_n,

                "coverage_pct":
                    (
                        100.0
                        * available_n
                        / len(df)
                    ),
            }
        )

    coverage = pd.DataFrame(
        coverage_rows
    )

    coverage.to_csv(
        COVERAGE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # INDIVIDUAL LEVEL STRUCTURE SUMMARY
    # =========================================================================

    summary_frames = []

    for family in [
        "pm",
        "ah",
        "pd",
    ]:

        feature = (
            f"{family}_level_structure_state"
        )

        all_dir = summarize(
            df,
            [
                "research_period",
                feature,
            ],
        )

        all_dir[
            "direction"
        ] = "ALL"

        all_dir[
            "level_family"
        ] = family.upper()

        all_dir = (
            all_dir.rename(
                columns={
                    feature:
                        "state"
                }
            )
        )

        by_dir = summarize(
            df,
            [
                "research_period",
                "direction",
                feature,
            ],
        )

        by_dir[
            "level_family"
        ] = family.upper()

        by_dir = (
            by_dir.rename(
                columns={
                    feature:
                        "state"
                }
            )
        )

        summary_frames.extend(
            [
                all_dir,
                by_dir,
            ]
        )

    session_summary = pd.concat(
        summary_frames,
        ignore_index=True,
        sort=False,
    )

    session_summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    direction_summary = (
        session_summary.loc[
            session_summary[
                "direction"
            ]
            != "ALL"
        ]
        .copy()
    )

    direction_summary.to_csv(
        DIRECTION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # PROXIMITY SUMMARY
    # =========================================================================

    proximity_frames = []

    for family in [
        "pm",
        "ah",
        "pd",
    ]:

        feature = (
            f"{family}_proximity_state"
        )

        x = summarize(
            df,
            [
                "research_period",
                feature,
            ],
        )

        x[
            "level_family"
        ] = family.upper()

        x = x.rename(
            columns={
                feature:
                    "state"
            }
        )

        proximity_frames.append(
            x
        )

    proximity_summary = pd.concat(
        proximity_frames,
        ignore_index=True,
        sort=False,
    )

    proximity_summary.to_csv(
        PROXIMITY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # CONFLUENCE SUMMARY
    # =========================================================================

    confluence_frames = []

    for feature in [
        "session_level_clear_state",
        "relevant_level_cluster_state",
        "nearest_ahead_level",
        "c2_break_count_state",
    ]:

        x = summarize(
            df,
            [
                "research_period",
                feature,
            ],
        )

        x[
            "feature"
        ] = feature

        x = x.rename(
            columns={
                feature:
                    "state"
            }
        )

        confluence_frames.append(
            x
        )

    confluence = pd.concat(
        confluence_frames,
        ignore_index=True,
        sort=False,
    )

    confluence.to_csv(
        CONFLUENCE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # QUARTER STABILITY
    # =========================================================================

    quarter_summary = summarize(
        df,
        [
            "quarter",
            "session_level_clear_state",
        ],
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # INTERACTIONS WITH PRIOR VALIDATED CONTEXT
    # =========================================================================

    possible_interactions = [
        (
            "session_level_clear_state",
            "market_prior_5d_consensus",
        ),

        (
            "session_level_clear_state",
            "positive_candidate_state",
        ),

        (
            "session_level_clear_state",
            "negative_candidate_state",
        ),

        (
            "session_level_clear_state",
            "low_c2_rvol_market_opposition_state",
        ),

        (
            "c2_break_count_state",
            "market_prior_5d_consensus",
        ),

        (
            "relevant_level_cluster_state",
            "positive_candidate_state",
        ),
    ]

    interaction_frames = []

    for (
        level_feature,
        context_feature,
    ) in possible_interactions:

        if (
            level_feature
            not in df.columns
            or context_feature
            not in df.columns
        ):
            continue

        x = summarize(
            df,
            [
                "research_period",
                level_feature,
                context_feature,
            ],
        )

        x[
            "level_feature"
        ] = level_feature

        x[
            "context_feature"
        ] = context_feature

        x = x.rename(
            columns={
                level_feature:
                    "level_state",

                context_feature:
                    "context_state",
            }
        )

        interaction_frames.append(
            x
        )

    if interaction_frames:

        interactions = pd.concat(
            interaction_frames,
            ignore_index=True,
            sort=False,
        )

    else:

        interactions = pd.DataFrame()

    interactions.to_csv(
        INTERACTION_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SAVE EVENT FEATURES
    # =========================================================================

    df.to_parquet(
        FEATURE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # REPORT
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "SESSION LEVEL COVERAGE"
    )

    print(
        "=" * 80
    )

    print(
        coverage.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    print()

    print(
        "=" * 80
    )

    print(
        "DISCOVERY-FROZEN "
        "PROXIMITY / CLUSTER THRESHOLDS"
    )

    print(
        "=" * 80
    )

    print(
        thresholds.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.4f}",
        )
    )

    # =========================================================================
    # INDIVIDUAL LEVEL STRUCTURE
    # =========================================================================

    for family in [
        "PM",
        "AH",
        "PD",
    ]:

        print()

        print(
            "=" * 80
        )

        print(
            f"{family} DIRECTIONAL LEVEL STRUCTURE — "
            f"DISCOVERY VS VALIDATION"
        )

        print(
            "=" * 80
        )

        x = session_summary.loc[
            (
                session_summary[
                    "level_family"
                ]
                == family
            )
            &
            (
                session_summary[
                    "direction"
                ]
                == "ALL"
            )
        ]

        print(
            x[
                [
                    "research_period",
                    "state",
                    "total_n",
                    "binary_n",
                    "favorable_first_pct",
                    "c3_confirmation_pct",
                    "avg_mfe_pct",
                    "avg_mae_pct",
                ]
            ]
            .sort_values(
                [
                    "research_period",
                    "state",
                ]
            )
            .to_string(
                index=False,
                float_format=
                    lambda z:
                        f"{z:.2f}",
            )
        )

    # =========================================================================
    # PROXIMITY
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "LEVEL PROXIMITY — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    print(
        proximity_summary[
            [
                "level_family",
                "research_period",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "level_family",
                "research_period",
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    # =========================================================================
    # COMBINED CLEAR STATE
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "PM/AH/PD COMBINED CLEAR STATE"
    )

    print(
        "=" * 80
    )

    x = confluence.loc[
        confluence[
            "feature"
        ]
        == "session_level_clear_state"
    ]

    print(
        x[
            [
                "research_period",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "avg_mfe_pct",
                "avg_mae_pct",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    # =========================================================================
    # NUMBER OF LEVELS BROKEN ON C2
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "NUMBER OF PM/AH/PD LEVELS "
        "BROKEN ON C2"
    )

    print(
        "=" * 80
    )

    x = confluence.loc[
        confluence[
            "feature"
        ]
        == "c2_break_count_state"
    ]

    print(
        x[
            [
                "research_period",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    # =========================================================================
    # LEVEL CLUSTERING
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "RELEVANT LEVEL CLUSTERING"
    )

    print(
        "=" * 80
    )

    x = confluence.loc[
        confluence[
            "feature"
        ]
        == "relevant_level_cluster_state"
    ]

    print(
        x[
            [
                "research_period",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "research_period",
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    # =========================================================================
    # VALIDATION DIRECTIONAL
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "INDIVIDUAL SESSION LEVELS — "
        "VALIDATION DIRECTIONAL"
    )

    print(
        "=" * 80
    )

    x = direction_summary.loc[
        direction_summary[
            "research_period"
        ]
        == "VALIDATION"
    ]

    print(
        x[
            [
                "level_family",
                "direction",
                "state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "level_family",
                "direction",
                "state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    # =========================================================================
    # QUARTER STABILITY
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "COMBINED CLEAR STATE — "
        "QUARTER STABILITY"
    )

    print(
        "=" * 80
    )

    print(
        quarter_summary[
            [
                "quarter",
                "session_level_clear_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "quarter",
                "session_level_clear_state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.2f}",
        )
    )

    # =========================================================================
    # INTERACTIONS
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "SESSION LEVEL × CONTEXT — "
        "VALIDATION"
    )

    print(
        "=" * 80
    )

    if not interactions.empty:

        x = interactions.loc[
            interactions[
                "research_period"
            ]
            == "VALIDATION"
        ]

        print(
            x[
                [
                    "level_feature",
                    "context_feature",
                    "level_state",
                    "context_state",
                    "total_n",
                    "binary_n",
                    "favorable_first_pct",
                    "c3_confirmation_pct",
                ]
            ]
            .sort_values(
                [
                    "level_feature",
                    "context_feature",
                    "level_state",
                    "context_state",
                ]
            )
            .to_string(
                index=False,
                float_format=
                    lambda z:
                        f"{z:.2f}",
            )
        )

    else:

        print(
            "No interaction rows produced."
        )

    print()

    print(
        "=" * 80
    )

    print(
        "OUTPUTS"
    )

    print(
        "=" * 80
    )

    print(
        f"Features:     "
        f"{FEATURE_OUTPUT}"
    )

    print(
        f"Summary:      "
        f"{SUMMARY_OUTPUT}"
    )

    print(
        f"Direction:    "
        f"{DIRECTION_OUTPUT}"
    )

    print(
        f"Proximity:    "
        f"{PROXIMITY_OUTPUT}"
    )

    print(
        f"Thresholds:   "
        f"{THRESHOLD_OUTPUT}"
    )

    print(
        f"Confluence:   "
        f"{CONFLUENCE_OUTPUT}"
    )

    print(
        f"Quarter:      "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Interactions: "
        f"{INTERACTION_OUTPUT}"
    )

    print(
        f"Coverage:     "
        f"{COVERAGE_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()