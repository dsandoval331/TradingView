import csv
import os
import sys
import time
from pathlib import Path

import psycopg


# ============================================================
# CONFIGURATION
# ============================================================

SOURCE_FILE = Path(
    r"C:\Users\DirtySouth\Downloads\PMPD_Historical_1M\PMPD_historical_1m_all.csv"
)

EXPECTED_ROWS = 1_075_790
EXPECTED_SYMBOL_DAYS = 2_457
EXPECTED_SYMBOLS = 112

TIMEFRAME = "1m"

PROGRESS_EVERY = 100_000


# ============================================================
# REQUIRED ENVIRONMENT VARIABLES
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
# SOURCE FILE CHECK
# ============================================================

if not SOURCE_FILE.exists():
    raise FileNotFoundError(
        f"Source file not found:\n{SOURCE_FILE}"
    )


required_csv_columns = {
    "symbol",
    "trade_date",
    "timestamp_ms",
    "timestamp_utc",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap",
    "transactions",
    "data_source",
    "adjusted",
}


# ============================================================
# HELPERS
# ============================================================

def nullable(value):
    """
    Convert blank CSV values to None for PostgreSQL NULL.
    """
    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


def parse_bool(value):
    value = str(value).strip().lower()

    if value in ("true", "1", "yes", "y"):
        return True

    if value in ("false", "0", "no", "n"):
        return False

    raise ValueError(
        f"Unexpected boolean value: {value}"
    )


# ============================================================
# CONNECT
# ============================================================

print()
print("=" * 80)
print("SECOND 1M CANDLE — HISTORICAL 1M IMPORT")
print("=" * 80)

print(f"Source file:       {SOURCE_FILE}")
print(f"Expected rows:     {EXPECTED_ROWS:,}")
print(f"Expected symbols:  {EXPECTED_SYMBOLS}")
print(f"Expected days:     {EXPECTED_SYMBOL_DAYS:,}")
print()

print("Connecting to Supabase PostgreSQL...")

conn = psycopg.connect(
    host=os.environ["SUPABASE_DB_HOST"],
    port=5432,
    dbname="postgres",
    user=os.environ["SUPABASE_DB_USER"],
    password=os.environ["SUPABASE_DB_PASSWORD"],
    sslmode="require",
)

print("Connected successfully.")
print()


# ============================================================
# BEGIN IMPORT
# ============================================================

start_time = time.time()

try:

    with conn.cursor() as cur:

        # ----------------------------------------------------
        # VERIFY DESTINATION BEFORE IMPORT
        # ----------------------------------------------------

        cur.execute(
            """
            select count(*)
            from public.market_intraday_history
            """
        )

        rows_before = cur.fetchone()[0]

        print(
            f"Destination rows before import: "
            f"{rows_before:,}"
        )


        # ----------------------------------------------------
        # CREATE TEMPORARY STAGING TABLE
        # ----------------------------------------------------

        print()
        print("Creating temporary staging table...")

        cur.execute(
            """
            create temporary table intraday_1m_stage (

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


        # ----------------------------------------------------
        # COPY CSV INTO STAGING
        # ----------------------------------------------------

        print()
        print("Loading CSV into staging with PostgreSQL COPY...")
        print()

        copied_rows = 0

        with SOURCE_FILE.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as f:

            reader = csv.DictReader(f)

            csv_columns = set(
                reader.fieldnames or []
            )

            missing_columns = (
                required_csv_columns
                - csv_columns
            )

            if missing_columns:
                raise RuntimeError(
                    "CSV missing required columns: "
                    + ", ".join(
                        sorted(missing_columns)
                    )
                )


            copy_sql = """
                copy intraday_1m_stage (
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


            with cur.copy(copy_sql) as copy:

                for row in reader:

                    symbol = row["symbol"].strip().upper()

                    trade_date = row[
                        "trade_date"
                    ].strip()

                    timestamp_utc = row[
                        "timestamp_utc"
                    ].strip()

                    timestamp_ms = nullable(
                        row["timestamp_ms"]
                    )

                    open_price = row[
                        "open"
                    ].strip()

                    high_price = row[
                        "high"
                    ].strip()

                    low_price = row[
                        "low"
                    ].strip()

                    close_price = row[
                        "close"
                    ].strip()

                    volume = nullable(
                        row["volume"]
                    )

                    vwap = nullable(
                        row["vwap"]
                    )

                    transactions = nullable(
                        row["transactions"]
                    )

                    data_source = row[
                        "data_source"
                    ].strip()

                    adjusted = parse_bool(
                        row["adjusted"]
                    )


                    copy.write_row(
                        (
                            symbol,
                            trade_date,
                            timestamp_utc,
                            timestamp_ms,
                            TIMEFRAME,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume,
                            vwap,
                            transactions,
                            data_source,
                            adjusted,
                        )
                    )


                    copied_rows += 1


                    if (
                        copied_rows
                        % PROGRESS_EVERY
                        == 0
                    ):

                        elapsed = (
                            time.time()
                            - start_time
                        )

                        print(
                            f"Copied "
                            f"{copied_rows:,} rows "
                            f"({elapsed:,.1f}s elapsed)"
                        )


        conn.commit()

        print()
        print(
            f"COPY complete: "
            f"{copied_rows:,} rows"
        )


        # ----------------------------------------------------
        # STAGING VALIDATION
        # ----------------------------------------------------

        print()
        print("=" * 80)
        print("STAGING VALIDATION")
        print("=" * 80)


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
                min(trade_date) as first_date,
                max(trade_date) as last_date
            from intraday_1m_stage
            """
        )

        (
            stage_rows,
            stage_symbols,
            stage_symbol_days,
            first_date,
            last_date,
        ) = cur.fetchone()


        print(
            f"Rows:          {stage_rows:,}"
        )

        print(
            f"Symbols:       {stage_symbols:,}"
        )

        print(
            f"Symbol-days:   {stage_symbol_days:,}"
        )

        print(
            f"First date:    {first_date}"
        )

        print(
            f"Last date:     {last_date}"
        )


        # ----------------------------------------------------
        # REQUIRED STAGING ASSERTIONS
        # ----------------------------------------------------

        if stage_rows != EXPECTED_ROWS:
            raise RuntimeError(
                f"Staging row mismatch. "
                f"Expected {EXPECTED_ROWS:,}, "
                f"found {stage_rows:,}."
            )

        if stage_symbols != EXPECTED_SYMBOLS:
            raise RuntimeError(
                f"Symbol mismatch. "
                f"Expected {EXPECTED_SYMBOLS}, "
                f"found {stage_symbols}."
            )

        if (
            stage_symbol_days
            != EXPECTED_SYMBOL_DAYS
        ):
            raise RuntimeError(
                f"Symbol-day mismatch. "
                f"Expected "
                f"{EXPECTED_SYMBOL_DAYS:,}, "
                f"found "
                f"{stage_symbol_days:,}."
            )


        # ----------------------------------------------------
        # CHECK REQUIRED FIELDS
        # ----------------------------------------------------

        cur.execute(
            """
            select count(*)
            from intraday_1m_stage
            where symbol is null
               or trade_date is null
               or timestamp_utc is null
               or open is null
               or high is null
               or low is null
               or close is null
            """
        )

        missing_required = cur.fetchone()[0]

        print(
            f"Missing required fields: "
            f"{missing_required:,}"
        )

        if missing_required != 0:
            raise RuntimeError(
                "Required-field validation failed."
            )


        # ----------------------------------------------------
        # CHECK DUPLICATE UNIQUE BAR KEYS
        # ----------------------------------------------------

        cur.execute(
            """
            select count(*)
            from (
                select
                    symbol,
                    timestamp_utc,
                    timeframe,
                    data_source,
                    adjusted,
                    count(*) as n
                from intraday_1m_stage
                group by
                    symbol,
                    timestamp_utc,
                    timeframe,
                    data_source,
                    adjusted
                having count(*) > 1
            ) d
            """
        )

        duplicate_keys = cur.fetchone()[0]

        print(
            f"Duplicate bar keys: "
            f"{duplicate_keys:,}"
        )


        # ----------------------------------------------------
        # OHLC VALIDATION
        # ----------------------------------------------------

        cur.execute(
            """
            select count(*)
            from intraday_1m_stage
            where high < low
               or high < open
               or high < close
               or low > open
               or low > close
            """
        )

        invalid_ohlc = cur.fetchone()[0]

        print(
            f"Invalid OHLC rows: "
            f"{invalid_ohlc:,}"
        )

        if invalid_ohlc != 0:
            raise RuntimeError(
                "OHLC validation failed."
            )


        # ----------------------------------------------------
        # SESSION DATE VALIDATION
        #
        # trade_date should match NY trading date.
        # ----------------------------------------------------

        cur.execute(
            """
            select count(*)
            from intraday_1m_stage
            where (
                timestamp_utc
                at time zone
                'America/New_York'
            )::date <> trade_date
            """
        )

        wrong_trade_date = cur.fetchone()[0]

        print(
            f"NY trade-date mismatches: "
            f"{wrong_trade_date:,}"
        )

        if wrong_trade_date != 0:
            raise RuntimeError(
                "Trade-date/timezone validation failed."
            )


        # ----------------------------------------------------
        # 09:30 / 09:31 COVERAGE
        # ----------------------------------------------------

        cur.execute(
            """
            with days as (
                select distinct
                    symbol,
                    trade_date
                from intraday_1m_stage
            ),
            bars as (
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

                from intraday_1m_stage

                group by
                    symbol,
                    trade_date
            )

            select
                count(*) filter (
                    where not has_0930
                ) as missing_0930,

                count(*) filter (
                    where not has_0931
                ) as missing_0931

            from bars
            """
        )

        (
            missing_0930,
            missing_0931,
        ) = cur.fetchone()


        print(
            f"Missing 09:30 days: "
            f"{missing_0930:,}"
        )

        print(
            f"Missing 09:31 days: "
            f"{missing_0931:,}"
        )


        # ----------------------------------------------------
        # MERGE INTO CANONICAL TABLE
        # ----------------------------------------------------

        print()
        print("=" * 80)
        print("MERGING INTO CANONICAL TABLE")
        print("=" * 80)


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

            from intraday_1m_stage

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

        conn.commit()


        # ----------------------------------------------------
        # FINAL CANONICAL VALIDATION
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
                min(trade_date) as first_date,
                max(trade_date) as last_date
            from public.market_intraday_history
            where data_source = 'massive_1m'
              and timeframe = '1m'
              and adjusted = true
            """
        )

        (
            final_rows,
            final_symbols,
            final_symbol_days,
            final_first_date,
            final_last_date,
        ) = cur.fetchone()


        inserted_this_run = (
            final_rows
            - rows_before
        )


        print()
        print("=" * 80)
        print("FINAL IMPORT VALIDATION")
        print("=" * 80)

        print(
            f"Rows before import:   "
            f"{rows_before:,}"
        )

        print(
            f"Rows after import:    "
            f"{final_rows:,}"
        )

        print(
            f"Inserted this run:    "
            f"{inserted_this_run:,}"
        )

        print(
            f"Symbols:              "
            f"{final_symbols:,}"
        )

        print(
            f"Symbol-days:          "
            f"{final_symbol_days:,}"
        )

        print(
            f"First date:           "
            f"{final_first_date}"
        )

        print(
            f"Last date:            "
            f"{final_last_date}"
        )

        print(
            f"Missing 09:30 days:   "
            f"{missing_0930:,}"
        )

        print(
            f"Missing 09:31 days:   "
            f"{missing_0931:,}"
        )


        # ----------------------------------------------------
        # FINAL EXPECTED COUNTS
        # ----------------------------------------------------

        if final_rows != EXPECTED_ROWS:
            raise RuntimeError(
                f"FINAL ROW COUNT FAILED: "
                f"expected {EXPECTED_ROWS:,}, "
                f"found {final_rows:,}"
            )

        if (
            final_symbol_days
            != EXPECTED_SYMBOL_DAYS
        ):
            raise RuntimeError(
                "FINAL SYMBOL-DAY COUNT FAILED."
            )

        if final_symbols != EXPECTED_SYMBOLS:
            raise RuntimeError(
                "FINAL SYMBOL COUNT FAILED."
            )

        if missing_0930 != 0:
            raise RuntimeError(
                "Unexpected missing 09:30 bars."
            )

        if missing_0931 != 26:
            print()
            print(
                "WARNING: expected 26 missing "
                "09:31 symbol-days, but found "
                f"{missing_0931}."
            )


        elapsed = (
            time.time()
            - start_time
        )

        print()
        print("=" * 80)
        print("IMPORT SUCCESSFUL")
        print("=" * 80)

        print(
            f"Elapsed time: "
            f"{elapsed:,.1f} seconds"
        )

        print(
            "Historical 1-minute data "
            "successfully loaded and validated."
        )

        print("=" * 80)


except Exception as exc:

    conn.rollback()

    print()
    print("=" * 80)
    print("IMPORT FAILED")
    print("=" * 80)

    print(str(exc))

    print()
    print(
        "The transaction was rolled back "
        "where applicable."
    )

    sys.exit(1)


finally:

    conn.close()