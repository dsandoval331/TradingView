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
    / "ae2_ma_context_v1"
    / "ae2_ma_context_features_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_short_ma_warning_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_short_ma_warning_features_v1.parquet"
)

SUMMARY_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_short_ma_warning_summary_v1.csv"
)

QUARTER_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_short_ma_warning_quarter_v1.csv"
)

SYMBOL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_short_ma_warning_symbol_v1.csv"
)


EMA9 = 9
EMA20 = 20
SMA50 = 50


# =============================================================================
# HELPERS
# =============================================================================

def summarize_group(x: pd.DataFrame) -> dict:

    favorable_n = int(
        (x["outcome"] == "FAVORABLE_FIRST").sum()
    )

    adverse_n = int(
        (x["outcome"] == "ADVERSE_FIRST").sum()
    )

    both_n = int(
        (x["outcome"] == "BOTH_SAME_BAR").sum()
    )

    unresolved_n = int(
        (x["outcome"] == "UNRESOLVED").sum()
    )

    binary_n = favorable_n + adverse_n

    favorable_first_pct = (
        100.0 * favorable_n / binary_n
        if binary_n
        else np.nan
    )

    c3_confirmed_n = int(
        x["c3_confirmed"].sum()
    )

    c3_confirmation_pct = (
        100.0 * c3_confirmed_n / len(x)
        if len(x)
        else np.nan
    )

    return {
        "total_n": int(len(x)),
        "binary_n": binary_n,
        "favorable_n": favorable_n,
        "adverse_n": adverse_n,
        "both_n": both_n,
        "unresolved_n": unresolved_n,
        "favorable_first_pct": favorable_first_pct,
        "c3_confirmed_n": c3_confirmed_n,
        "c3_confirmation_pct": c3_confirmation_pct,
        "avg_mfe_pct": x["final_mfe_pct"].mean(),
        "avg_mae_pct": x["final_mae_pct"].mean(),
        "median_mfe_pct": x["final_mfe_pct"].median(),
        "median_mae_pct": x["final_mae_pct"].median(),
        "symbol_n": x["symbol"].nunique(),
        "trade_date_n": x["trade_date"].nunique(),
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

        if not isinstance(keys, tuple):
            keys = (keys,)

        row = dict(zip(group_cols, keys))
        row.update(summarize_group(x))
        rows.append(row)

    return pd.DataFrame(rows)


def directional_favorable(
    direction: str,
    price: float,
    reference: float,
) -> bool | None:

    if pd.isna(price) or pd.isna(reference):
        return None

    if direction == "BULL":
        return bool(price > reference)

    if direction == "BEAR":
        return bool(price < reference)

    return None


def warning_state(
    ema9_ok: bool | None,
    ema20_ok: bool | None,
) -> str:

    if ema9_ok is None or ema20_ok is None:
        return "UNKNOWN"

    if ema9_ok and ema20_ok:
        return "BOTH_FAVORABLE"

    if (not ema9_ok) and ema20_ok:
        return "EMA9_ONLY_OPPOSING"

    if ema9_ok and (not ema20_ok):
        return "EMA20_ONLY_OPPOSING"

    return "BOTH_OPPOSING"


# =============================================================================
# RTH-ONLY MA CONSTRUCTION
# =============================================================================

def load_symbol_rth_history(
    symbol: str,
) -> pd.DataFrame:

    paths = sorted(
        CACHE_ROOT.rglob(
            f"{symbol}_*.parquet"
        )
    )

    if not paths:
        raise RuntimeError(
            f"No Parquet partitions found for {symbol}"
        )

    frames = []

    for path in paths:

        table = pq.read_table(
            path,
            columns=[
                "symbol",
                "trade_date",
                "timestamp_utc",
                "close",
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

    df = df.loc[
        df["session"] == "RTH"
    ].copy()

    df = (
        df
        .sort_values(
            "timestamp_utc"
        )
        .drop_duplicates(
            subset=["timestamp_utc"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    close = df["close"].astype(float)

    df["rth_ema9"] = (
        close
        .ewm(
            span=EMA9,
            adjust=False,
            min_periods=EMA9,
        )
        .mean()
    )

    df["rth_ema20"] = (
        close
        .ewm(
            span=EMA20,
            adjust=False,
            min_periods=EMA20,
        )
        .mean()
    )

    df["rth_sma50"] = (
        close
        .rolling(
            window=SMA50,
            min_periods=SMA50,
        )
        .mean()
    )

    return df


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
            f"Input file not found: {INPUT_PATH}"
        )

    df = pd.read_parquet(
        INPUT_PATH
    )

    df["symbol"] = (
        df["symbol"]
        .astype(str)
        .str.upper()
    )

    df["trade_date"] = pd.to_datetime(
        df["trade_date"]
    )

    df["entry_timestamp"] = pd.to_datetime(
        df["entry_timestamp"],
        utc=True,
    )

    # =========================================================================
    # CONTINUOUS-MA WARNING STATE
    # =========================================================================

    df["continuous_short_ma_state"] = df.apply(
        lambda r:
            warning_state(
                r["price_vs_ema9_ok"],
                r["price_vs_ema20_ok"],
            ),
        axis=1,
    )

    # =========================================================================
    # BUILD RTH-ONLY EMA9 / EMA20
    # =========================================================================

    symbols = sorted(
        df["symbol"].unique()
    )

    enriched = []

    missing_rth_match_n = 0

    print("=" * 80)
    print("AE2 SHORT-MA OPPOSITION ROBUSTNESS V1")
    print("=" * 80)

    print(f"AE2 events: {len(df):,}")
    print(f"Symbols:    {len(symbols):,}")

    for i, symbol in enumerate(
        symbols,
        start=1,
    ):

        symbol_events = (
            df.loc[
                df["symbol"] == symbol
            ]
            .copy()
        )

        rth = load_symbol_rth_history(
            symbol
        )

        lookup = (
            rth[
                [
                    "timestamp_utc",
                    "close",
                    "rth_ema9",
                    "rth_ema20",
                    "rth_sma50",
                ]
            ]
            .set_index(
                "timestamp_utc"
            )
        )

        records = []

        for _, event in symbol_events.iterrows():

            ts = event[
                "entry_timestamp"
            ]

            if ts not in lookup.index:

                missing_rth_match_n += 1
                continue

            market_row = lookup.loc[
                ts
            ]

            if isinstance(
                market_row,
                pd.DataFrame,
            ):
                market_row = (
                    market_row.iloc[0]
                )

            r = event.to_dict()

            r["rth_ema9"] = market_row[
                "rth_ema9"
            ]

            r["rth_ema20"] = market_row[
                "rth_ema20"
            ]

            r["rth_sma50"] = market_row[
                "rth_sma50"
            ]

            direction = r[
                "direction"
            ]

            close = float(
                market_row["close"]
            )

            r["rth_price_vs_ema9_ok"] = (
                directional_favorable(
                    direction,
                    close,
                    market_row["rth_ema9"],
                )
            )

            r["rth_price_vs_ema20_ok"] = (
                directional_favorable(
                    direction,
                    close,
                    market_row["rth_ema20"],
                )
            )

            r["rth_short_ma_state"] = (
                warning_state(
                    r["rth_price_vs_ema9_ok"],
                    r["rth_price_vs_ema20_ok"],
                )
            )

            records.append(r)

        if records:
            enriched.append(
                pd.DataFrame(records)
            )

        if (
            i % 10 == 0
            or i == len(symbols)
        ):

            enriched_n = sum(
                len(x)
                for x in enriched
            )

            print(
                f"Processed "
                f"{i:>3}/{len(symbols)} "
                f"| enriched={enriched_n:,}"
            )

    if not enriched:
        raise RuntimeError(
            "No RTH-only MA events were enriched."
        )

    df = pd.concat(
        enriched,
        ignore_index=True,
    )

    print()
    print(
        f"Matched RTH events: "
        f"{len(df):,}"
    )

    print(
        f"Missing RTH matches: "
        f"{missing_rth_match_n:,}"
    )

    # =========================================================================
    # PERIODS
    # =========================================================================

    df["research_period"] = (
        df["temporal_half"]
        .map(
            {
                "OLDEST_HALF":
                    "DISCOVERY",

                "NEWEST_HALF":
                    "VALIDATION",
            }
        )
    )

    df["quarter"] = (
        df["trade_date"]
        .dt
        .to_period("Q")
        .astype(str)
    )

    # =========================================================================
    # LONG FORM: CONTINUOUS VS RTH_ONLY
    # =========================================================================

    continuous = df.copy()

    continuous["ma_definition"] = (
        "CONTINUOUS"
    )

    continuous["short_ma_state"] = (
        continuous[
            "continuous_short_ma_state"
        ]
    )

    rth = df.copy()

    rth["ma_definition"] = (
        "RTH_ONLY"
    )

    rth["short_ma_state"] = (
        rth[
            "rth_short_ma_state"
        ]
    )

    combined = pd.concat(
        [
            continuous,
            rth,
        ],
        ignore_index=True,
        sort=False,
    )

    # =========================================================================
    # OVERALL / PERIOD / DIRECTION SUMMARY
    # =========================================================================

    all_period = summarize(
        combined,
        [
            "ma_definition",
            "research_period",
            "short_ma_state",
        ],
    )

    all_period["direction"] = "ALL"

    by_direction = summarize(
        combined,
        [
            "ma_definition",
            "research_period",
            "direction",
            "short_ma_state",
        ],
    )

    summary = pd.concat(
        [
            all_period,
            by_direction,
        ],
        ignore_index=True,
        sort=False,
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    # =========================================================================
    # QUARTER SUMMARY
    # =========================================================================

    quarter_all = summarize(
        combined,
        [
            "ma_definition",
            "quarter",
            "short_ma_state",
        ],
    )

    quarter_all[
        "direction"
    ] = "ALL"

    quarter_direction = summarize(
        combined,
        [
            "ma_definition",
            "quarter",
            "direction",
            "short_ma_state",
        ],
    )

    quarter_summary = pd.concat(
        [
            quarter_all,
            quarter_direction,
        ],
        ignore_index=True,
        sort=False,
    )

    quarter_summary.to_csv(
        QUARTER_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SYMBOL BREADTH
    # =========================================================================

    symbol_summary = summarize(
        combined,
        [
            "ma_definition",
            "symbol",
            "short_ma_state",
        ],
    )

    symbol_summary.to_csv(
        SYMBOL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # SAVE EVENT DATASET
    # =========================================================================

    df.to_parquet(
        FEATURE_OUTPUT,
        index=False,
    )

    # =========================================================================
    # PRINT
    # =========================================================================

    print()
    print("=" * 80)
    print("SHORT-MA WARNING — DISCOVERY VS VALIDATION")
    print("=" * 80)

    display = summary.loc[
        summary["direction"] == "ALL"
    ]

    print(
        display[
            [
                "ma_definition",
                "research_period",
                "short_ma_state",
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
                "ma_definition",
                "research_period",
                "short_ma_state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("VALIDATION ONLY — DIRECTIONAL")
    print("=" * 80)

    validation_direction = (
        summary.loc[
            (
                summary["research_period"]
                == "VALIDATION"
            )
            &
            (
                summary["direction"]
                != "ALL"
            )
        ]
    )

    print(
        validation_direction[
            [
                "ma_definition",
                "direction",
                "short_ma_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
            ]
        ]
        .sort_values(
            [
                "ma_definition",
                "direction",
                "short_ma_state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("VALIDATION — BOTH_FAVORABLE VS ANY_OPPOSING")
    print("=" * 80)

    validation = combined.loc[
        combined["research_period"]
        == "VALIDATION"
    ].copy()

    validation[
        "binary_warning_state"
    ] = np.where(
        validation[
            "short_ma_state"
        ]
        == "BOTH_FAVORABLE",
        "BOTH_FAVORABLE",
        np.where(
            validation[
                "short_ma_state"
            ]
            == "UNKNOWN",
            "UNKNOWN",
            "ANY_OPPOSING",
        )
    )

    binary_summary = summarize(
        validation,
        [
            "ma_definition",
            "binary_warning_state",
        ],
    )

    print(
        binary_summary[
            [
                "ma_definition",
                "binary_warning_state",
                "total_n",
                "binary_n",
                "favorable_first_pct",
                "c3_confirmation_pct",
                "symbol_n",
            ]
        ]
        .sort_values(
            [
                "ma_definition",
                "binary_warning_state",
            ]
        )
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:.2f}",
        )
    )

    print()
    print("=" * 80)
    print("OUTPUTS")
    print("=" * 80)

    print(
        f"Features: "
        f"{FEATURE_OUTPUT}"
    )

    print(
        f"Summary:  "
        f"{SUMMARY_OUTPUT}"
    )

    print(
        f"Quarter:  "
        f"{QUARTER_OUTPUT}"
    )

    print(
        f"Symbols:  "
        f"{SYMBOL_OUTPUT}"
    )

    print()
    print("RESULT: COMPLETE")


if __name__ == "__main__":
    main()