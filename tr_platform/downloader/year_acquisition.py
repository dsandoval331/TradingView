from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from getpass import getpass
from pathlib import Path
from typing import Optional

import pandas as pd

from tr_platform.common.cache_config import (
    CACHE_VERSION,
    SOURCE_NAME,
    MarketCacheConfig,
    NEW_YORK_TZ,
    classify_session,
)
from tr_platform.common.manifest import (
    CachePartitionRecord,
    LocalManifest,
    sha256_file,
    utc_now_iso,
)
from tr_platform.downloader.massive_client import MassiveClient, MassiveClientConfig


@dataclass(frozen=True)
class YearAcquisitionResult:
    action: str
    symbol: str
    year: int
    requested_start: str
    requested_end: str
    row_count: int
    output_path: Path
    manifest_path: Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _year_bounds(year: int, today: Optional[date] = None) -> tuple[str, str]:
    """
    Production year bounds:
      - Past year: Jan 1 through Dec 31
      - Current year: Jan 1 through today
      - Future year: invalid
    """
    if today is None:
        today = date.today()

    if year > today.year:
        raise ValueError(f"Cannot acquire future year {year}.")

    start = date(year, 1, 1)
    end = today if year == today.year else date(year, 12, 31)

    return start.isoformat(), end.isoformat()


def _normalize(symbol: str, rows: list[dict], cache_version: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).copy()

    df = df.rename(columns={
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "vw": "vwap",
        "n": "transactions",
        "t": "timestamp_ms",
    })

    required = ["timestamp_ms", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Massive response missing required columns: {missing}")

    if "vwap" not in df.columns:
        df["vwap"] = pd.NA
    if "transactions" not in df.columns:
        df["transactions"] = pd.NA

    df["symbol"] = symbol.upper().strip()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
    df["timestamp_et"] = df["timestamp_utc"].dt.tz_convert(NEW_YORK_TZ)
    df["trade_date"] = df["timestamp_et"].dt.date
    df["session"] = [classify_session(ts.hour, ts.minute) for ts in df["timestamp_et"]]
    df["source"] = SOURCE_NAME
    df["adjusted"] = False
    df["cache_version"] = cache_version

    columns = [
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
        "session",
        "source",
        "adjusted",
        "cache_version",
    ]

    return df[columns].sort_values("timestamp_utc").reset_index(drop=True)


def _validate(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "validation_status": "FAIL",
            "duplicate_count": 0,
            "invalid_ohlc_count": 0,
            "row_count": 0,
            "trading_days": 0,
            "rth_days": 0,
            "premarket_days": 0,
            "afterhours_days": 0,
        }

    duplicate_count = int(df.duplicated(["symbol", "timestamp_utc"]).sum())

    invalid_ohlc_count = int((
        (df["high"] < df[["open", "close", "low"]].max(axis=1))
        | (df["low"] > df[["open", "close", "high"]].min(axis=1))
    ).sum())

    trading_days = int(df["trade_date"].nunique())
    rth_days = int(df.loc[df["session"] == "RTH", "trade_date"].nunique())
    premarket_days = int(df.loc[df["session"] == "PRE", "trade_date"].nunique())
    afterhours_days = int(df.loc[df["session"] == "AH", "trade_date"].nunique())

    status = "PASS"
    if duplicate_count > 0 or invalid_ohlc_count > 0:
        status = "FAIL"

    return {
        "validation_status": status,
        "duplicate_count": duplicate_count,
        "invalid_ohlc_count": invalid_ohlc_count,
        "row_count": int(len(df)),
        "trading_days": trading_days,
        "rth_days": rth_days,
        "premarket_days": premarket_days,
        "afterhours_days": afterhours_days,
    }


def _atomic_write(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tmp.parquet")

    df.to_parquet(tmp_path, index=False)

    check = pd.read_parquet(tmp_path)
    if len(check) != len(df):
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Read-back row mismatch: wrote {len(df)}, read {len(check)}"
        )

    if check["timestamp_utc"].nunique() != df["timestamp_utc"].nunique():
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError("Read-back timestamp uniqueness mismatch.")

    tmp_path.replace(output_path)


def acquire_symbol_year(
    *,
    symbol: str,
    year: int,
    api_key: Optional[str] = None,
    force: bool = False,
    repo_root: Optional[Path] = None,
) -> YearAcquisitionResult:
    """
    Production symbol/year acquisition for MARKET_CACHE_V1.

    This is the first implementation that may mark an actual production
    symbol/year partition as complete.
    """
    symbol = symbol.upper().strip()

    if repo_root is None:
        repo_root = _repo_root()

    cfg = MarketCacheConfig.from_repo_root(repo_root)
    cfg.ensure_directories()

    requested_start, requested_end = _year_bounds(year)
    output_path = cfg.symbol_year_path(symbol, year)
    manifest_path = cfg.manifests_root / "market_cache_manifest.parquet"

    manifest = LocalManifest(manifest_path)

    existing = manifest.get(
        symbol=symbol,
        year=year,
        timeframe="1m",
        source=SOURCE_NAME,
        adjusted=False,
        cache_version=CACHE_VERSION,
    )

    exact_complete = (
        existing is not None
        and existing.get("download_status") == "DOWNLOADED"
        and existing.get("validation_status") in {"PASS", "PASS_WITH_WARNINGS"}
        and str(existing.get("requested_start")) == requested_start
        and str(existing.get("requested_end")) == requested_end
        and output_path.exists()
    )

    if exact_complete and not force:
        return YearAcquisitionResult(
            action="SKIPPED_COMPLETE",
            symbol=symbol,
            year=year,
            requested_start=requested_start,
            requested_end=requested_end,
            row_count=int(existing.get("row_count") or 0),
            output_path=output_path,
            manifest_path=manifest_path,
        )

    attempts = int(existing.get("download_attempts") or 0) + 1 if existing else 1

    manifest.upsert(CachePartitionRecord(
        symbol=symbol,
        year=year,
        adjusted=False,
        cache_version=CACHE_VERSION,
        requested_start=requested_start,
        requested_end=requested_end,
        download_status="PARTIAL",
        validation_status="NOT_VALIDATED",
        download_attempts=attempts,
        local_relative_path=str(output_path.relative_to(repo_root)),
        notes="Production symbol/year acquisition started.",
    ))

    if api_key is None:
        api_key = getpass("Enter your Massive API key: ").strip()

    client = MassiveClient(
        MassiveClientConfig(
            api_key=api_key,
            requests_per_minute=4.0,
        )
    )

    try:
        rows = client.get_minute_aggs(
            symbol=symbol,
            start_date=requested_start,
            end_date=requested_end,
            adjusted=False,
            limit=50_000,
        )

        df = _normalize(symbol, rows, CACHE_VERSION)
        validation = _validate(df)

        if validation["validation_status"] == "FAIL":
            raise RuntimeError(
                "Canonical validation failed: "
                f"duplicates={validation['duplicate_count']}, "
                f"invalid_ohlc={validation['invalid_ohlc_count']}, "
                f"rows={validation['row_count']}"
            )

        _atomic_write(df, output_path)

        file_hash = sha256_file(output_path)
        now = utc_now_iso()

        manifest.upsert(CachePartitionRecord(
            symbol=symbol,
            year=year,
            adjusted=False,
            cache_version=CACHE_VERSION,
            requested_start=requested_start,
            requested_end=requested_end,
            actual_first_bar=df["timestamp_utc"].min().isoformat(),
            actual_last_bar=df["timestamp_utc"].max().isoformat(),
            row_count=len(df),
            trading_days=validation["trading_days"],
            rth_days=validation["rth_days"],
            premarket_days=validation["premarket_days"],
            afterhours_days=validation["afterhours_days"],
            duplicate_count=validation["duplicate_count"],
            invalid_ohlc_count=validation["invalid_ohlc_count"],
            download_status="DOWNLOADED",
            validation_status=validation["validation_status"],
            download_attempts=attempts,
            last_download_at=now,
            last_validated_at=now,
            local_relative_path=str(output_path.relative_to(repo_root)),
            file_size_bytes=output_path.stat().st_size,
            file_hash=file_hash,
            notes="Production symbol/year acquisition completed.",
        ))

        return YearAcquisitionResult(
            action="DOWNLOADED",
            symbol=symbol,
            year=year,
            requested_start=requested_start,
            requested_end=requested_end,
            row_count=len(df),
            output_path=output_path,
            manifest_path=manifest_path,
        )

    except Exception as exc:
        manifest.upsert(CachePartitionRecord(
            symbol=symbol,
            year=year,
            adjusted=False,
            cache_version=CACHE_VERSION,
            requested_start=requested_start,
            requested_end=requested_end,
            download_status="FAILED",
            validation_status="FAIL",
            download_attempts=attempts,
            last_download_at=utc_now_iso(),
            local_relative_path=str(output_path.relative_to(repo_root)),
            notes=f"{type(exc).__name__}: {exc}",
        ))
        raise
