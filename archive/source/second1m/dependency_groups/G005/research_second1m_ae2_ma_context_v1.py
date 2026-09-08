from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


# =============================================================================
# CONFIG
# =============================================================================

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

CACHE_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_cache_v1"
)

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

INPUT_PATH = (
    RESEARCH_ROOT
    / "ae2_c2_predictors_v1"
    / "ae2_c2_predictor_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_ma_context_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_ma_context_features_v1.parquet"
)

STATE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_ma_state_summary_v1.csv"
)

CROSS_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_ma_cross_summary_v1.csv"
)

TEMPORAL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_ma_temporal_summary_v1.csv"
)

STACK_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_ma_stack_summary_v1.csv"
)


EMA_FAST = 9
EMA_SLOW = 20
SMA_LONG = 50

EXPECTED_SYMBOLS = 112


# =============================================================================
# BASIC HELPERS
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

        "c3_confirmed_n":
            c3_confirmed_n,

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


def directional_relation(
    direction: str,
    left: float,
    right: float,
) -> bool | None:

    if pd.isna(left) or pd.isna(right):
        return None

    if direction == "BULL":
        return bool(left > right)

    if direction == "BEAR":
        return bool(left < right)

    return None


def directional_distance_pct(
    direction: str,
    left: float,
    right: float,
) -> float:

    if pd.isna(left) or pd.isna(right):
        return np.nan

    if right == 0:
        return np.nan

    raw = (
        100.0
        * (
            left / right
            - 1.0
        )
    )

    if direction == "BULL":
        return raw

    if direction == "BEAR":
        return -raw

    return np.nan


def directional_slope(
    direction: str,
    current: float,
    previous: float,
) -> float:

    if pd.isna(current) or pd.isna(previous):
        return np.nan

    if previous == 0:
        return np.nan

    raw = (
        100.0
        * (
            current / previous
            - 1.0
        )
    )

    if direction == "BULL":
        return raw

    if direction == "BEAR":
        return -raw

    return np.nan


def cross_state(
    direction: str,
    prev_left: float,
    prev_right: float,
    cur_left: float,
    cur_right: float,
) -> str:

    values = [
        prev_left,
        prev_right,
        cur_left,
        cur_right,
    ]

    if any(
        pd.isna(v)
        for v in values
    ):
        return "UNKNOWN"

    if direction == "BULL":

        favorable_cross = (
            prev_left <= prev_right
            and cur_left > cur_right
        )

        adverse_cross = (
            prev_left >= prev_right
            and cur_left < cur_right
        )

    elif direction == "BEAR":

        favorable_cross = (
            prev_left >= prev_right
            and cur_left < cur_right
        )

        adverse_cross = (
            prev_left <= prev_right
            and cur_left > cur_right
        )

    else:
        return "UNKNOWN"

    if favorable_cross:
        return "FAVORABLE_CROSS"

    if adverse_cross:
        return "ADVERSE_CROSS"

    favorable_now = (
        directional_relation(
            direction,
            cur_left,
            cur_right,
        )
    )

    if favorable_now is True:
        return "FAVORABLE_HOLD"

    if favorable_now is False:
        return "OPPOSING_HOLD"

    return "UNKNOWN"


# =============================================================================
# LOAD ONE SYMBOL'S MARKET HISTORY
# =============================================================================

def load_symbol_history(
    symbol: str,
) -> pd.DataFrame:

    paths = sorted(
        CACHE_ROOT.rglob(
            f"{symbol}_*.parquet"
        )
    )

    if not paths:
        raise RuntimeError(
            f"No cache partitions found for {symbol}"
        )

    frames = []

    for path in paths:

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

        frames.append(
            table.to_pandas()
        )

    df = pd.concat(
        frames,
        ignore_index=True,
    )

    df["symbol"] = (
        df["symbol"]
        .astype(str)
        .str.upper()
    )

    df["timestamp_utc"] = pd.to_datetime(
        df["timestamp_utc"],
        utc=True,
    )

    df["trade_date"] = pd.to_datetime(
        df["trade_date"]
    ).dt.date

    df = (
        df
        .sort_values(
            "timestamp_utc"
        )
        .drop_duplicates(
            subset=[
                "timestamp_utc"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    # -------------------------------------------------------------------------
    # CONTINUOUS 1-MINUTE MOVING AVERAGES
    #
    # These intentionally use all chronological cached bars.
    # They do NOT reset at the RTH open.
    # -------------------------------------------------------------------------

    df["ema9"] = (
        df["close"]
        .astype(float)
        .ewm(
            span=EMA_FAST,
            adjust=False,
            min_periods=EMA_FAST,
        )
        .mean()
    )

    df["ema20"] = (
        df["close"]
        .astype(float)
        .ewm(
            span=EMA_SLOW,
            adjust=False,
            min_periods=EMA_SLOW,
        )
        .mean()
    )

    df["sma50"] = (
        df["close"]
        .astype(float)
        .rolling(
            window=SMA_LONG,
            min_periods=SMA_LONG,
        )
        .mean()
    )

    df["prev_close"] = (
        df["close"]
        .shift(1)
    )

    df["prev_ema9"] = (
        df["ema9"]
        .shift(1)
    )

    df["prev_ema20"] = (
        df["ema20"]
        .shift(1)
    )

    df["prev_sma50"] = (
        df["sma50"]
        .shift(1)
    )

    return df


# =============================================================================
# ENRICH ONE AE2 EVENT
# =============================================================================

def enrich_event(
    row: pd.Series,
    market_row: pd.Series,
) -> dict:

    direction = row[
        "direction"
    ]

    close = float(
        market_row[
            "close"
        ]
    )

    ema9 = market_row[
        "ema9"
    ]

    ema20 = market_row[
        "ema20"
    ]

    sma50 = market_row[
        "sma50"
    ]

    prev_close = market_row[
        "prev_close"
    ]

    prev_ema9 = market_row[
        "prev_ema9"
    ]

    prev_ema20 = market_row[
        "prev_ema20"
    ]

    prev_sma50 = market_row[
        "prev_sma50"
    ]

    price_vs_ema9_ok = (
        directional_relation(
            direction,
            close,
            ema9,
        )
    )

    price_vs_ema20_ok = (
        directional_relation(
            direction,
            close,
            ema20,
        )
    )

    price_vs_sma50_ok = (
        directional_relation(
            direction,
            close,
            sma50,
        )
    )

    ema9_vs_ema20_ok = (
        directional_relation(
            direction,
            ema9,
            ema20,
        )
    )

    ema9_vs_sma50_ok = (
        directional_relation(
            direction,
            ema9,
            sma50,
        )
    )

    ema20_vs_sma50_ok = (
        directional_relation(
            direction,
            ema20,
            sma50,
        )
    )

    bools = [
        price_vs_ema9_ok,
        price_vs_ema20_ok,
        price_vs_sma50_ok,
        ema9_vs_ema20_ok,
        ema9_vs_sma50_ok,
        ema20_vs_sma50_ok,
    ]

    known_bools = [
        b
        for b in bools
        if b is not None
    ]

    favorable_count = (
        sum(
            bool(b)
            for b in known_bools
        )
        if known_bools
        else np.nan
    )

    if len(
        known_bools
    ) < 6:

        stack_state = (
            "UNKNOWN"
        )

    elif favorable_count == 6:

        stack_state = (
            "FULL_FAVORABLE"
        )

    elif favorable_count == 0:

        stack_state = (
            "FULL_OPPOSING"
        )

    elif favorable_count >= 4:

        stack_state = (
            "MOSTLY_FAVORABLE"
        )

    elif favorable_count <= 2:

        stack_state = (
            "MOSTLY_OPPOSING"
        )

    else:

        stack_state = (
            "MIXED"
        )

    price_ema9_cross = (
        cross_state(
            direction,
            prev_close,
            prev_ema9,
            close,
            ema9,
        )
    )

    price_ema20_cross = (
        cross_state(
            direction,
            prev_close,
            prev_ema20,
            close,
            ema20,
        )
    )

    price_sma50_cross = (
        cross_state(
            direction,
            prev_close,
            prev_sma50,
            close,
            sma50,
        )
    )

    ema9_ema20_cross = (
        cross_state(
            direction,
            prev_ema9,
            prev_ema20,
            ema9,
            ema20,
        )
    )

    return {
        "ema9":
            ema9,

        "ema20":
            ema20,

        "sma50":
            sma50,

        "price_vs_ema9_ok":
            price_vs_ema9_ok,

        "price_vs_ema20_ok":
            price_vs_ema20_ok,

        "price_vs_sma50_ok":
            price_vs_sma50_ok,

        "ema9_vs_ema20_ok":
            ema9_vs_ema20_ok,

        "ema9_vs_sma50_ok":
            ema9_vs_sma50_ok,

        "ema20_vs_sma50_ok":
            ema20_vs_sma50_ok,

        "price_ema9_distance_pct":
            directional_distance_pct(
                direction,
                close,
                ema9,
            ),

        "price_ema20_distance_pct":
            directional_distance_pct(
                direction,
                close,
                ema20,
            ),

        "price_sma50_distance_pct":
            directional_distance_pct(
                direction,
                close,
                sma50,
            ),

        "ema9_ema20_distance_pct":
            directional_distance_pct(
                direction,
                ema9,
                ema20,
            ),

        "ema9_sma50_distance_pct":
            directional_distance_pct(
                direction,
                ema9,
                sma50,
            ),

        "ema20_sma50_distance_pct":
            directional_distance_pct(
                direction,
                ema20,
                sma50,
            ),

        "ema9_slope_1bar_pct":
            directional_slope(
                direction,
                ema9,
                prev_ema9,
            ),

        "ema20_slope_1bar_pct":
            directional_slope(
                direction,
                ema20,
                prev_ema20,
            ),

        "sma50_slope_1bar_pct":
            directional_slope(
                direction,
                sma50,
                prev_sma50,
            ),

        "ma_favorable_count":
            favorable_count,

        "ma_stack_state":
            stack_state,

        "price_ema9_cross_state":
            price_ema9_cross,

        "price_ema20_cross_state":
            price_ema20_cross,

        "price_sma50_cross_state":
            price_sma50_cross,

        "ema9_ema20_cross_state":
            ema9_ema20_cross,
    }


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

    ae2 = pd.read_parquet(
        INPUT_PATH
    )

    ae2[
        "symbol"
    ] = (
        ae2[
            "symbol"
        ]
        .astype(str)
        .str.upper()
    )

    ae2[
        "trade_date"
    ] = pd.to_datetime(
        ae2[
            "trade_date"
        ]
    )

    ae2[
        "entry_timestamp"
    ] = pd.to_datetime(
        ae2[
            "entry_timestamp"
        ],
        utc=True,
    )

    symbols = sorted(
        ae2[
            "symbol"
        ].unique()
    )

    if len(
        symbols
    ) != EXPECTED_SYMBOLS:

        raise RuntimeError(
            f"Expected "
            f"{EXPECTED_SYMBOLS} "
            f"AE2 symbols, found "
            f"{len(symbols)}"
        )

    print(
        "=" * 80
    )

    print(
        "AE2 EMA/SMA/VWAP CONTEXT V1"
    )

    print(
        "=" * 80
    )

    print(
        f"AE2 events: "
        f"{len(ae2):,}"
    )

    print(
        f"Symbols:    "
        f"{len(symbols):,}"
    )

    enriched_frames = []

    missing_timestamp_n = 0

    # =========================================================================
    # PROCESS SYMBOL BY SYMBOL
    # =========================================================================

    for i, symbol in enumerate(
        symbols,
        start=1,
    ):

        symbol_events = (
            ae2.loc[
                ae2[
                    "symbol"
                ]
                == symbol
            ]
            .copy()
        )

        history = (
            load_symbol_history(
                symbol
            )
        )

        # Keep only the exact C2 entry timestamps
        # relevant to AE2 events.

        lookup_cols = [
            "timestamp_utc",
            "close",
            "ema9",
            "ema20",
            "sma50",
            "prev_close",
            "prev_ema9",
            "prev_ema20",
            "prev_sma50",
        ]

        lookup = (
            history[
                lookup_cols
            ]
            .set_index(
                "timestamp_utc"
            )
        )

        records = []

        for _, event in (
            symbol_events.iterrows()
        ):

            ts = event[
                "entry_timestamp"
            ]

            if ts not in lookup.index:

                missing_timestamp_n += 1

                continue

            market_row = (
                lookup.loc[
                    ts
                ]
            )

            # Defensive duplicate handling.
            if isinstance(
                market_row,
                pd.DataFrame,
            ):

                market_row = (
                    market_row.iloc[0]
                )

            context = enrich_event(
                event,
                market_row,
            )

            record = (
                event.to_dict()
            )

            record.update(
                context
            )

            records.append(
                record
            )

        if records:

            enriched_frames.append(
                pd.DataFrame(
                    records
                )
            )

        if (
            i % 10 == 0
            or i == len(symbols)
        ):

            enriched_so_far = sum(
                len(x)
                for x in enriched_frames
            )

            print(
                f"Processed "
                f"{i:>3}/"
                f"{len(symbols)} "
                f"| enriched="
                f"{enriched_so_far:,}"
            )

    if not enriched_frames:

        raise RuntimeError(
            "No AE2 events were enriched."
        )

    df = pd.concat(
        enriched_frames,
        ignore_index=True,
    )

    print()

    print(
        f"Matched C2 events: "
        f"{len(df):,}"
    )

    print(
        f"Missing timestamps:"
        f" {missing_timestamp_n:,}"
    )

    # =========================================================================
    # TEMPORAL PERIOD
    # =========================================================================

    if (
        "temporal_half"
        not in df.columns
    ):

        unique_dates = sorted(
            df[
                "trade_date"
            ]
            .dropna()
            .unique()
        )

        midpoint = pd.Timestamp(
            unique_dates[
                len(unique_dates)
                // 2
            ]
        )

        df[
            "temporal_half"
        ] = df[
            "trade_date"
        ].apply(
            lambda x:
                "OLDEST_HALF"
                if x < midpoint
                else "NEWEST_HALF"
        )

    df[
        "research_period"
    ] = df[
        "temporal_half"
    ].map(
        {
            "OLDEST_HALF":
                "DISCOVERY",

            "NEWEST_HALF":
                "VALIDATION",
        }
    )

    # =========================================================================
    # STATIC MA STATE SUMMARY
    # =========================================================================

    state_features = [
        "price_vs_ema9_ok",
        "price_vs_ema20_ok",
        "price_vs_sma50_ok",
        "ema9_vs_ema20_ok",
        "ema9_vs_sma50_ok",
        "ema20_vs_sma50_ok",
    ]

    state_frames = []

    for feature in state_features:

        x = df.copy()

        x[
            "state"
        ] = x[
            feature
        ].map(
            {
                True:
                    "FAVORABLE",

                False:
                    "OPPOSING",
            }
        ).fillna(
            "UNKNOWN"
        )

        all_dir = summarize(
            x,
            [
                "research_period",
                "state",
            ],
        )

        all_dir[
            "direction"
        ] = "ALL"

        all_dir[
            "feature"
        ] = feature

        by_dir = summarize(
            x,
            [
                "research_period",
                "direction",
                "state",
            ],
        )

        by_dir[
            "feature"
        ] = feature

        state_frames.extend(
            [
                all_dir,
                by_dir,
            ]
        )

    state_summary = pd.concat(
        state_frames,
        ignore_index=True,
        sort=False,
    )

    state_summary.to_csv(
        STATE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # STACK SUMMARY
    # =========================================================================

    stack_all = summarize(
        df,
        [
            "research_period",
            "ma_stack_state",
        ],
    )

    stack_all[
        "direction"
    ] = "ALL"

    stack_direction = summarize(
        df,
        [
            "research_period",
            "direction",
            "ma_stack_state",
        ],
    )

    stack_summary = pd.concat(
        [
            stack_all,
            stack_direction,
        ],
        ignore_index=True,
        sort=False,
    )

    stack_summary.to_csv(
        STACK_OUTPUT,
        index=False,
    )

    # =========================================================================
    # CROSS SUMMARY
    # =========================================================================

    cross_features = [
        "price_ema9_cross_state",
        "price_ema20_cross_state",
        "price_sma50_cross_state",
        "ema9_ema20_cross_state",
    ]

    cross_frames = []

    for feature in cross_features:

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
            "feature"
        ] = feature

        all_dir = (
            all_dir.rename(
                columns={
                    feature:
                        "cross_state"
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
            "feature"
        ] = feature

        by_dir = (
            by_dir.rename(
                columns={
                    feature:
                        "cross_state"
                }
            )
        )

        cross_frames.extend(
            [
                all_dir,
                by_dir,
            ]
        )

    cross_summary = pd.concat(
        cross_frames,
        ignore_index=True,
        sort=False,
    )

    cross_summary.to_csv(
        CROSS_OUTPUT,
        index=False,
    )

    # =========================================================================
    # TEMPORAL CONTINUOUS METRICS
    # =========================================================================

    continuous_features = [
        "price_ema9_distance_pct",
        "price_ema20_distance_pct",
        "price_sma50_distance_pct",
        "ema9_ema20_distance_pct",
        "ema9_sma50_distance_pct",
        "ema20_sma50_distance_pct",
        "ema9_slope_1bar_pct",
        "ema20_slope_1bar_pct",
        "sma50_slope_1bar_pct",
    ]

    temporal_rows = []

    for feature in continuous_features:

        for period, x in df.groupby(
            "research_period",
            dropna=False,
        ):

            confirmed = x.loc[
                x[
                    "c3_confirmed"
                ]
            ]

            not_confirmed = x.loc[
                ~x[
                    "c3_confirmed"
                ]
            ]

            winners = x.loc[
                x[
                    "outcome"
                ]
                == "FAVORABLE_FIRST"
            ]

            losers = x.loc[
                x[
                    "outcome"
                ]
                == "ADVERSE_FIRST"
            ]

            temporal_rows.append(
                {
                    "feature":
                        feature,

                    "research_period":
                        period,

                    "n":
                        len(x),

                    "confirmed_mean":
                        confirmed[
                            feature
                        ].mean(),

                    "not_confirmed_mean":
                        not_confirmed[
                            feature
                        ].mean(),

                    "confirmation_difference":
                        confirmed[
                            feature
                        ].mean()
                        -
                        not_confirmed[
                            feature
                        ].mean(),

                    "winner_mean":
                        winners[
                            feature
                        ].mean(),

                    "loser_mean":
                        losers[
                            feature
                        ].mean(),

                    "outcome_difference":
                        winners[
                            feature
                        ].mean()
                        -
                        losers[
                            feature
                        ].mean(),
                }
            )

    temporal_summary = (
        pd.DataFrame(
            temporal_rows
        )
    )

    temporal_summary.to_csv(
        TEMPORAL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # WRITE FEATURE DATASET
    # =========================================================================

    df.to_parquet(
        FEATURE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # PRINT REPORT
    # =========================================================================

    print()

    print(
        "=" * 80
    )

    print(
        "STATIC MA STATES — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    for feature in state_features:

        print()

        print(
            feature
        )

        print(
            "-" * 80
        )

        x = state_summary.loc[
            (
                state_summary[
                    "feature"
                ]
                == feature
            )
            &
            (
                state_summary[
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
                ]
            ].to_string(
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
        "MA STACK — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    stack_display = (
        stack_summary.loc[
            stack_summary[
                "direction"
            ]
            == "ALL"
        ]
    )

    print(
        stack_display[
            [
                "research_period",
                "ma_stack_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ].to_string(
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
        "C2 CROSS EVENTS — "
        "DISCOVERY VS VALIDATION"
    )

    print(
        "=" * 80
    )

    for feature in cross_features:

        print()

        print(
            feature
        )

        print(
            "-" * 80
        )

        x = cross_summary.loc[
            (
                cross_summary[
                    "feature"
                ]
                == feature
            )
            &
            (
                cross_summary[
                    "direction"
                ]
                == "ALL"
            )
        ]

        print(
            x[
                [
                    "research_period",
                    "cross_state",
                    "total_n",
                    "binary_n",
                    "favorable_first_pct",
                    "c3_confirmation_pct",
                ]
            ].to_string(
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
        "CONTINUOUS MA METRICS — "
        "CONFIRMED VS NOT / WINNER VS LOSER"
    )

    print(
        "=" * 80
    )

    print(
        temporal_summary.to_string(
            index=False,
            float_format=
                lambda z:
                    f"{z:.4f}",
        )
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
        f"Features: "
        f"{FEATURE_OUTPUT}"
    )

    print(
        f"States:   "
        f"{STATE_OUTPUT}"
    )

    print(
        f"Stack:    "
        f"{STACK_OUTPUT}"
    )

    print(
        f"Crosses:  "
        f"{CROSS_OUTPUT}"
    )

    print(
        f"Temporal: "
        f"{TEMPORAL_OUTPUT}"
    )

    print()

    print(
        "RESULT: COMPLETE"
    )


if __name__ == "__main__":
    main()