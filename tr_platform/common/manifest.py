from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
import hashlib
import json

import pandas as pd


MANIFEST_VERSION = "MARKET_CACHE_MANIFEST_V1"

DOWNLOAD_STATUSES = {
    "NOT_REQUESTED",
    "PARTIAL",
    "DOWNLOADED",
    "FAILED",
}

VALIDATION_STATUSES = {
    "NOT_VALIDATED",
    "PASS",
    "PASS_WITH_WARNINGS",
    "FAIL",
}


@dataclass
class CachePartitionRecord:
    symbol: str
    year: int
    timeframe: str = "1m"
    source: str = "massive"
    adjusted: bool = False
    cache_version: str = "MARKET_CACHE_V1"

    requested_start: Optional[str] = None
    requested_end: Optional[str] = None

    actual_first_bar: Optional[str] = None
    actual_last_bar: Optional[str] = None

    row_count: int = 0
    trading_days: int = 0
    rth_days: int = 0
    premarket_days: int = 0
    afterhours_days: int = 0

    duplicate_count: int = 0
    conflicting_duplicate_count: int = 0
    invalid_ohlc_count: int = 0
    missing_rth_minutes: int = 0

    download_status: str = "NOT_REQUESTED"
    validation_status: str = "NOT_VALIDATED"

    download_attempts: int = 0
    last_download_at: Optional[str] = None
    last_validated_at: Optional[str] = None

    local_relative_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    file_hash: Optional[str] = None
    hash_algorithm: str = "SHA256"

    notes: Optional[str] = None
    manifest_version: str = MANIFEST_VERSION

    def normalize(self) -> "CachePartitionRecord":
        self.symbol = self.symbol.upper().strip()

        if self.download_status not in DOWNLOAD_STATUSES:
            raise ValueError(f"Invalid download_status: {self.download_status}")

        if self.validation_status not in VALIDATION_STATUSES:
            raise ValueError(f"Invalid validation_status: {self.validation_status}")

        if self.year < 1900 or self.year > 2200:
            raise ValueError(f"Invalid year: {self.year}")

        return self


class LocalManifest:
    """
    Local source of truth for MARKET_CACHE_V1 acquisition state.

    One row per:
        symbol x year x timeframe x source x adjusted x cache_version
    """

    KEY_COLUMNS = [
        "symbol",
        "year",
        "timeframe",
        "source",
        "adjusted",
        "cache_version",
    ]

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path.resolve()
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> pd.DataFrame:
        if not self.manifest_path.exists():
            return pd.DataFrame()

        df = pd.read_parquet(self.manifest_path)
        if not df.empty:
            df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
        return df

    def save(self, df: pd.DataFrame) -> None:
        tmp_path = self.manifest_path.with_suffix(".tmp.parquet")
        df = df.sort_values(self.KEY_COLUMNS).reset_index(drop=True)
        df.to_parquet(tmp_path, index=False)
        tmp_path.replace(self.manifest_path)

    def upsert(self, record: CachePartitionRecord) -> None:
        record = record.normalize()
        new_row = pd.DataFrame([asdict(record)])

        df = self.load()

        if df.empty:
            self.save(new_row)
            return

        mask = pd.Series(True, index=df.index)
        for col in self.KEY_COLUMNS:
            mask &= df[col].astype(str) == str(new_row.iloc[0][col])

        if mask.any():
            df = df.loc[~mask].copy()

        df = pd.concat([df, new_row], ignore_index=True)
        self.save(df)

    def get(
        self,
        symbol: str,
        year: int,
        timeframe: str = "1m",
        source: str = "massive",
        adjusted: bool = False,
        cache_version: str = "MARKET_CACHE_V1",
    ) -> Optional[dict]:
        df = self.load()
        if df.empty:
            return None

        mask = (
            (df["symbol"] == symbol.upper().strip())
            & (df["year"] == year)
            & (df["timeframe"] == timeframe)
            & (df["source"] == source)
            & (df["adjusted"] == adjusted)
            & (df["cache_version"] == cache_version)
        )

        if not mask.any():
            return None

        return df.loc[mask].iloc[0].to_dict()

    def is_complete(
        self,
        symbol: str,
        year: int,
        expected_path: Path,
        timeframe: str = "1m",
        source: str = "massive",
        adjusted: bool = False,
        cache_version: str = "MARKET_CACHE_V1",
    ) -> bool:
        row = self.get(
            symbol=symbol,
            year=year,
            timeframe=timeframe,
            source=source,
            adjusted=adjusted,
            cache_version=cache_version,
        )

        if row is None:
            return False

        return (
            row.get("download_status") == "DOWNLOADED"
            and row.get("validation_status") in {"PASS", "PASS_WITH_WARNINGS"}
            and expected_path.exists()
        )

    def next_incomplete(
        self,
        symbols: Iterable[str],
        years: Iterable[int],
        path_builder,
    ) -> Optional[tuple[str, int]]:
        for symbol in symbols:
            for year in years:
                expected_path = path_builder(symbol, year)
                if not self.is_complete(symbol, year, expected_path):
                    return symbol.upper().strip(), year

        return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
