import os
import time
from pathlib import Path

import pandas as pd
import psycopg


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

CACHE_ROOT = (
    PROJECT_ROOT
    / "market_cache"
    / "MARKET_CACHE_V1"
    / "1m"
)

SYMBOLS = ("SPY", "QQQ")
YEARS = (2025, 2026)

EXPECTED_SIGNAL_DATES = 261
EXPECTED_SYMBOL_DAYS = EXPECTED_SIGNAL_DATES * len(SYMBOLS)

TIMEFRAME = "1m"

# Canonical PostgreSQL provenance.
#
# MARKET_CACHE_V1 itself records:
#   source   = massive
#   adjusted = False
#
# We retain adjusted=False exactly.
#
# Existing market_intraday_history uses the canonical
# data-source label "massive_1m".
DATA_SOURCE = "massive_1m"

PROGRESS_EVERY = 100_000


# ============================================================
# ENVIRONMENT
# ============================================================

required_env = [
    "SUPABASE_DB_HOST",
    "SUPABASE_DB_USER",
    "SUPABASE_DB_PASSWORD",
]

missing_env = [
    name
    for name in required_env
    if not os.environ.get(name)
]

if missing_env:
    raise RuntimeError(
        "Missing environment variables: "
        + ", ".join(missing_env)
    )


# ============================================================
# CONNECT
# ============================================================

print()
print("=" * 80)
print("SECOND 1M — MARKET REFERENCE IMPORT")
print("=" * 80)
print()

conn = psycopg.connect(
    host=os.environ["SUPABASE_DB_HOST"],
    port=5432,
    dbname="postgres",
    user=os.environ["SUPABASE_DB_USER"],
    password=os.environ["SUPABASE_DB_PASSWORD"],
    sslmode="require",
)

print("Connected to Supabase PostgreSQL.")
print()

start_time = time.time()


try:

    # ========================================================
    # GET AUTHORITATIVE SECOND1M RESEARCH DATES
    # ========================================================

    with conn.cursor() as cur:

        cur.execute(
            """
            select distinct trade_date
            from public.v_second1m_factor_research
            where primary_binary_eligible
            order by trade_date
            """
        )

        signal_dates = {
            row[0]
            for row in cur.fetchall()
        }

    print("=" * 80)
    print("AUTHORITATIVE DATE MANIFEST")
    print("=" * 80)

    print(f"Eligible signal dates: {len(signal_dates):,}")
    print(f"Expected:              {EXPECTED_SIGNAL_DATES:,}")

    if len(signal_dates) != EXPECTED_SIGNAL_DATES:
        raise RuntimeError(
            "Unexpected eligible signal-date count: "
            f"{len(signal_dates):,}; "
            f"expected {EXPECTED_SIGNAL_DATES:,}"
        )

    print(f"First date:            {min(signal_dates)}")
    print(f"Last date:             {max(signal_dates)}")
    print()


    # ========================================================
    # LOAD MARKET_CACHE_V1 PARTITIONS
    # ========================================================

    print("=" * 80)
    print("READING MARKET_CACHE_V1")
    print("=" * 80)
    print()

    frames = []

    for symbol in SYMBOLS:

        for year in YEARS:

            path = (
                CACHE_ROOT
                / symbol
                / f"{year}.parquet"
            )

            if not path.exists():
                raise FileNotFoundError(
                    f"Missing cache partition:\n{path}"
                )

            print(f"Reading {path}")

            df = pd.read_parquet(path)

            required_columns = {
                "symbol",
                "timestamp_utc",
                "timestamp_et",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "vwap",
                "transactions",
                "timestamp_ms",
                "source",
                "adjusted",
            }

            missing_columns = (
                required_columns
                - set(df.columns)
            )

            if missing_columns:
                raise RuntimeError(
                    f"{path} missing columns: "
                    + ", ".join(sorted(missing_columns))
                )

            # -----------------------------------------------
            # Validate partition provenance
            # -----------------------------------------------

            if set(df["symbol"].dropna().unique()) != {symbol}:
                raise RuntimeError(
                    f"Unexpected symbol values in {path}"
                )

            if set(df["source"].dropna().unique()) != {"massive"}:
                raise RuntimeError(
                    f"Unexpected source values in {path}"
                )

            adjusted_values = set(
                df["adjusted"].dropna().unique().tolist()
            )

            if adjusted_values != {False}:
                raise RuntimeError(
                    f"Unexpected adjusted values in {path}: "
                    f"{adjusted_values}"
                )

            # -----------------------------------------------
            # Normalize trade_date for filtering
            # -----------------------------------------------

            df["trade_date"] = pd.to_datetime(
                df["trade_date"]
            ).dt.date

            df = df[
                df["trade_date"].isin(signal_dates)
            ].copy()

            if not df.empty:
                frames.append(df)

            print(
                f"  retained rows: {len(df):,}"
            )

    if not frames:
        raise RuntimeError(
            "No market-reference rows matched "
            "the authoritative signal dates."
        )

    market = pd.concat(
        frames,
        ignore_index=True,
    )

    market = market.sort_values(
        [
            "symbol",
            "trade_date",
            "timestamp_utc",
        ]
    ).reset_index(drop=True)

    print()
    print(f"Total retained rows: {len(market):,}")
    print()


    # ========================================================
    # LOCAL VALIDATION
    # ========================================================

    print("=" * 80)
    print("LOCAL MARKET-REFERENCE VALIDATION")
    print("=" * 80)

    symbol_days = (
        market[
            ["symbol", "trade_date"]
        ]
        .drop_duplicates()
    )

    print(f"Rows:          {len(market):,}")
    print(
        f"Symbols:       "
        f"{market['symbol'].nunique():,}"
    )
    print(
        f"Trading dates: "
        f"{market['trade_date'].nunique():,}"
    )
    print(
        f"Symbol-days:   "
        f"{len(symbol_days):,}"
    )
    print(
        f"First date:    "
        f"{market['trade_date'].min()}"
    )
    print(
        f"Last date:     "
        f"{market['trade_date'].max()}"
    )

    if market["symbol"].nunique() != 2:
        raise RuntimeError(
            "Expected exactly SPY and QQQ."
        )

    if market["trade_date"].nunique() != EXPECTED_SIGNAL_DATES:
        raise RuntimeError(
            "Market-reference date coverage "
            "does not match signal-date manifest."
        )

    if len(symbol_days) != EXPECTED_SYMBOL_DAYS:
        raise RuntimeError(
            f"Expected {EXPECTED_SYMBOL_DAYS} symbol-days, "
            f"found {len(symbol_days)}."
        )


    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    required_not_null = [
        "symbol",
        "trade_date",
        "timestamp_utc",
        "open",
        "high",
        "low",
        "close",
        "adjusted",
    ]

    missing_required = int(
        market[required_not_null]
        .isna()
        .any(axis=1)
        .sum()
    )

    print(
        f"Missing required fields: "
        f"{missing_required:,}"
    )

    if missing_required != 0:
        raise RuntimeError(
            "Missing required market-reference fields."
        )


    # --------------------------------------------------------
    # Duplicate canonical keys
    # --------------------------------------------------------

    duplicate_keys = int(
        market.duplicated(
            subset=[
                "symbol",
                "timestamp_utc",
            ],
            keep=False,
        ).sum()
    )

    print(
        f"Duplicate symbol/timestamps: "
        f"{duplicate_keys:,}"
    )

    if duplicate_keys != 0:
        raise RuntimeError(
            "Duplicate market-reference timestamps found."
        )


    # --------------------------------------------------------
    # OHLC validity
    # --------------------------------------------------------

    invalid_ohlc = market[
        (market["high"] < market["low"])
        | (market["high"] < market["open"])
        | (market["high"] < market["close"])
        | (market["low"] > market["open"])
        | (market["low"] > market["close"])
    ]

    print(
        f"Invalid OHLC rows: "
        f"{len(invalid_ohlc):,}"
    )

    if len(invalid_ohlc) != 0:
        raise RuntimeError(
            "Invalid OHLC rows found."
        )


    # --------------------------------------------------------
    # NY trade-date consistency
    # --------------------------------------------------------

    timestamp_et = pd.to_datetime(
        market["timestamp_utc"],
        utc=True,
    ).dt.tz_convert("America/New_York")

    timestamp_trade_dates = (
        timestamp_et.dt.date
    )

    wrong_trade_date = int(
        (
            timestamp_trade_dates
            != market["trade_date"]
        ).sum()
    )

    print(
        f"NY trade-date mismatches: "
        f"{wrong_trade_date:,}"
    )

    if wrong_trade_date != 0:
        raise RuntimeError(
            "NY timestamp/trade-date mismatch."
        )


    # --------------------------------------------------------
    # Opening-bar coverage
    # --------------------------------------------------------

    market["_time_et"] = (
        timestamp_et.dt.strftime("%H:%M")
    )

    open_coverage = (
        market[
            market["_time_et"].isin(
                ["09:30", "09:31"]
            )
        ]
        .groupby(
            ["symbol", "trade_date"]
        )["_time_et"]
        .agg(set)
    )

    missing_0930 = []
    missing_0931 = []

    for symbol in SYMBOLS:
        for trade_date in sorted(signal_dates):

            key = (
                symbol,
                trade_date,
            )

            times = (
                open_coverage.get(key, set())
            )

            if "09:30" not in times:
                missing_0930.append(key)

            if "09:31" not in times:
                missing_0931.append(key)

    print(
        f"Missing 09:30 symbol-days: "
        f"{len(missing_0930):,}"
    )

    print(
        f"Missing 09:31 symbol-days: "
        f"{len(missing_0931):,}"
    )

    if missing_0930:
        print()
        print("Missing 09:30:")
        for item in missing_0930:
            print(" ", item)

    if missing_0931:
        print()
        print("Missing 09:31:")
        for item in missing_0931:
            print(" ", item)

    if missing_0930 or missing_0931:
        raise RuntimeError(
            "Opening benchmark coverage is incomplete. "
            "Import aborted before database merge."
        )


    # ========================================================
    # PREPARE CANONICAL ROWS
    # ========================================================

    market["timeframe"] = TIMEFRAME
    market["data_source"] = DATA_SOURCE

    # Preserve actual cache provenance.
    market["adjusted"] = False

    market = market.drop(
        columns=["_time_et"]
    )


    # ========================================================
    # DATABASE IMPORT
    # ========================================================

    print()
    print("=" * 80)
    print("DATABASE IMPORT")
    print("=" * 80)
    print()

    with conn.cursor() as cur:

        cur.execute(
            """
            select count(*)
            from public.market_intraday_history
            where symbol in ('SPY', 'QQQ')
              and timeframe = '1m'
              and data_source = 'massive_1m'
              and adjusted = false
            """
        )

        rows_before = cur.fetchone()[0]

        print(
            f"Existing adjusted=false benchmark rows: "
            f"{rows_before:,}"
        )


        # ----------------------------------------------------
        # Temporary staging table
        # ----------------------------------------------------

        cur.execute(
            """
            create temporary table market_reference_stage (

                symbol text not null,
                trade_date date not null,

                timestamp_utc timestamptz not null,
                timestamp_ms bigint,

                timeframe text not null,

                open numeric not null,
                high numeric not null,
                low numeric not null,
                close numeric not null,

                volume numeric,
                vwap numeric,
                transactions bigint,

                data_source text not null,
                adjusted boolean not null

            ) on commit preserve rows;
            """
        )

        conn.commit()

        print("Temporary staging table created.")
        print()
        print("COPYing market-reference rows...")
        print()

        copy_sql = """
            copy market_reference_stage (
                symbol,
                trade_date,
                timestamp_utc,
                timestamp_ms,
                timeframe,
                open,
                high,
                low,
                close,
                volume,
                vwap,
                transactions,
                data_source,
                adjusted
            )
            from stdin
        """

        copied_rows = 0

        with cur.copy(copy_sql) as copy:

            for row in market.itertuples(index=False):

                copy.write_row(
                    (
                        row.symbol,
                        row.trade_date,
                        row.timestamp_utc.to_pydatetime(),
                        int(row.timestamp_ms),
                        TIMEFRAME,
                        float(row.open),
                        float(row.high),
                        float(row.low),
                        float(row.close),
                        (
                            None
                            if pd.isna(row.volume)
                            else float(row.volume)
                        ),
                        (
                            None
                            if pd.isna(row.vwap)
                            else float(row.vwap)
                        ),
                        (
                            None
                            if pd.isna(row.transactions)
                            else int(row.transactions)
                        ),
                        DATA_SOURCE,
                        False,
                    )
                )

                copied_rows += 1

                if (
                    copied_rows
                    % PROGRESS_EVERY
                    == 0
                ):
                    print(
                        f"Copied "
                        f"{copied_rows:,} rows..."
                    )

        conn.commit()

        print()
        print(
            f"COPY complete: "
            f"{copied_rows:,} rows"
        )


        # ----------------------------------------------------
        # Staging validation
        # ----------------------------------------------------

        cur.execute(
            """
            select
                count(*) as rows,
                count(distinct symbol) as symbols,
                count(
                    distinct (
                        symbol,
                        trade_date
                    )
                ) as symbol_days,
                min(trade_date),
                max(trade_date)
            from market_reference_stage
            """
        )

        (
            stage_rows,
            stage_symbols,
            stage_symbol_days,
            stage_first_date,
            stage_last_date,
        ) = cur.fetchone()

        print()
        print("STAGING:")
        print(f"Rows:        {stage_rows:,}")
        print(f"Symbols:     {stage_symbols:,}")
        print(
            f"Symbol-days: "
            f"{stage_symbol_days:,}"
        )
        print(f"First date:  {stage_first_date}")
        print(f"Last date:   {stage_last_date}")

        if stage_rows != len(market):
            raise RuntimeError(
                "Staging row count mismatch."
            )

        if stage_symbol_days != EXPECTED_SYMBOL_DAYS:
            raise RuntimeError(
                "Staging symbol-day mismatch."
            )


        # ----------------------------------------------------
        # Canonical merge
        # ----------------------------------------------------

        print()
        print(
            "Merging into "
            "public.market_intraday_history..."
        )

        cur.execute(
            """
            insert into public.market_intraday_history (

                symbol,
                trade_date,
                timestamp_utc,
                timestamp_ms,
                timeframe,

                open,
                high,
                low,
                close,

                volume,
                vwap,
                transactions,

                data_source,
                adjusted
            )

            select
                symbol,
                trade_date,
                timestamp_utc,
                timestamp_ms,
                timeframe,

                open,
                high,
                low,
                close,

                volume,
                vwap,
                transactions,

                data_source,
                adjusted

            from market_reference_stage

            on conflict (
                symbol,
                timestamp_utc,
                timeframe,
                data_source,
                adjusted
            )
            do nothing
            """
        )

        inserted_rows = cur.rowcount

        conn.commit()


        # ====================================================
        # FINAL CANONICAL VALIDATION
        # ====================================================

        cur.execute(
            """
            select count(*)
            from public.market_intraday_history
            where symbol in ('SPY', 'QQQ')
              and timeframe = '1m'
              and data_source = 'massive_1m'
              and adjusted = false
            """
        )

        rows_after = cur.fetchone()[0]

        print()
        print("=" * 80)
        print("FINAL IMPORT VALIDATION")
        print("=" * 80)

        print(
            f"Rows before:   "
            f"{rows_before:,}"
        )

        print(
            f"Rows after:    "
            f"{rows_after:,}"
        )

        print(
            f"Inserted:      "
            f"{inserted_rows:,}"
        )


        # ----------------------------------------------------
        # Research-date coverage
        # ----------------------------------------------------

        cur.execute(
            """
            with signal_dates as (
                select distinct trade_date
                from public.v_second1m_factor_research
                where primary_binary_eligible
            ),

            expected as (
                select
                    d.trade_date,
                    s.symbol
                from signal_dates d
                cross join (
                    values ('SPY'), ('QQQ')
                ) s(symbol)
            ),

            coverage as (
                select
                    symbol,
                    trade_date,

                    bool_or(
                        (
                            timestamp_utc
                            at time zone
                            'America/New_York'
                        )::time = time '09:30'
                    ) as has_0930,

                    bool_or(
                        (
                            timestamp_utc
                            at time zone
                            'America/New_York'
                        )::time = time '09:31'
                    ) as has_0931

                from public.market_intraday_history

                where symbol in ('SPY', 'QQQ')
                  and timeframe = '1m'
                  and data_source = 'massive_1m'
                  and adjusted = false

                group by
                    symbol,
                    trade_date
            )

            select
                count(*) as expected_symbol_days,

                count(*) filter (
                    where coalesce(
                        c.has_0930,
                        false
                    )
                ) as with_0930,

                count(*) filter (
                    where coalesce(
                        c.has_0931,
                        false
                    )
                ) as with_0931,

                count(*) filter (
                    where coalesce(
                        c.has_0930,
                        false
                    )
                    and coalesce(
                        c.has_0931,
                        false
                    )
                ) as complete_open_symbol_days

            from expected e

            left join coverage c
              on c.symbol = e.symbol
             and c.trade_date = e.trade_date
            """
        )

        (
            expected_symbol_days,
            with_0930,
            with_0931,
            complete_open_symbol_days,
        ) = cur.fetchone()

        print()
        print(
            f"Expected research symbol-days: "
            f"{expected_symbol_days:,}"
        )

        print(
            f"With 09:30:                   "
            f"{with_0930:,}"
        )

        print(
            f"With 09:31:                   "
            f"{with_0931:,}"
        )

        print(
            f"Complete opening coverage:    "
            f"{complete_open_symbol_days:,}"
        )

        if (
            expected_symbol_days
            != EXPECTED_SYMBOL_DAYS
        ):
            raise RuntimeError(
                "Unexpected expected symbol-day count."
            )

        if (
            complete_open_symbol_days
            != EXPECTED_SYMBOL_DAYS
        ):
            raise RuntimeError(
                "Canonical market-reference "
                "coverage is incomplete."
            )


    print()
    print("=" * 80)
    print("MARKET REFERENCE IMPORT SUCCESSFUL")
    print("=" * 80)

    print(
        f"Elapsed time: "
        f"{time.time() - start_time:.1f} seconds"
    )

    print(
        "SPY/QQQ market-reference data "
        "successfully loaded and validated."
    )

    print("=" * 80)


except Exception:

    conn.rollback()
    raise


finally:

    conn.close()