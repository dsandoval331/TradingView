from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import hashlib

import pandas as pd

from tr_platform.common.cache_config import CACHE_VERSION, SOURCE_NAME, MarketCacheConfig
from tr_platform.common.manifest import LocalManifest
from tr_platform.universe.pmpd_universe import load_validated_universe


@dataclass(frozen=True)
class PartitionAudit:
    symbol: str
    year: int
    status: str
    manifest_present: bool
    file_present: bool
    manifest_download_status: Optional[str]
    manifest_validation_status: Optional[str]
    manifest_row_count: Optional[int]
    parquet_row_count: Optional[int]
    unique_timestamps: Optional[int]
    duplicate_timestamps: Optional[int]
    invalid_ohlc_count: Optional[int]
    symbol_mismatch_count: Optional[int]
    cache_version_mismatch_count: Optional[int]
    source_mismatch_count: Optional[int]
    adjusted_true_count: Optional[int]
    first_timestamp_utc: Optional[str]
    last_timestamp_utc: Optional[str]
    file_size_bytes_manifest: Optional[int]
    file_size_bytes_actual: Optional[int]
    file_hash_match: Optional[bool]
    issues: str


@dataclass(frozen=True)
class DatasetAuditSummary:
    year: int
    expected_partitions: int
    audited_partitions: int
    pass_count: int
    warn_count: int
    fail_count: int
    research_ready_candidate: bool
    report_csv: str
    report_parquet: str


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_int(value) -> Optional[int]:
    if value is None or pd.isna(value):
        return None
    return int(value)


def audit_partition(
    *,
    symbol: str,
    year: int,
    cfg: MarketCacheConfig,
    manifest: LocalManifest,
) -> PartitionAudit:
    issues: list[str] = []
    symbol = symbol.upper().strip()

    path = cfg.symbol_year_path(symbol, year)

    record = manifest.get(
        symbol=symbol,
        year=year,
        timeframe="1m",
        source=SOURCE_NAME,
        adjusted=False,
        cache_version=CACHE_VERSION,
    )

    if record is None:
        return PartitionAudit(
            symbol=symbol,
            year=year,
            status="FAIL",
            manifest_present=False,
            file_present=path.exists(),
            manifest_download_status=None,
            manifest_validation_status=None,
            manifest_row_count=None,
            parquet_row_count=None,
            unique_timestamps=None,
            duplicate_timestamps=None,
            invalid_ohlc_count=None,
            symbol_mismatch_count=None,
            cache_version_mismatch_count=None,
            source_mismatch_count=None,
            adjusted_true_count=None,
            first_timestamp_utc=None,
            last_timestamp_utc=None,
            file_size_bytes_manifest=None,
            file_size_bytes_actual=path.stat().st_size if path.exists() else None,
            file_hash_match=None,
            issues="manifest_missing",
        )

    if not path.exists():
        return PartitionAudit(
            symbol=symbol,
            year=year,
            status="FAIL",
            manifest_present=True,
            file_present=False,
            manifest_download_status=record.get("download_status"),
            manifest_validation_status=record.get("validation_status"),
            manifest_row_count=_safe_int(record.get("row_count")),
            parquet_row_count=None,
            unique_timestamps=None,
            duplicate_timestamps=None,
            invalid_ohlc_count=None,
            symbol_mismatch_count=None,
            cache_version_mismatch_count=None,
            source_mismatch_count=None,
            adjusted_true_count=None,
            first_timestamp_utc=None,
            last_timestamp_utc=None,
            file_size_bytes_manifest=_safe_int(record.get("file_size_bytes")),
            file_size_bytes_actual=None,
            file_hash_match=None,
            issues="file_missing",
        )

    if record.get("download_status") != "DOWNLOADED":
        issues.append(f"download_status={record.get('download_status')}")
    if record.get("validation_status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        issues.append(f"validation_status={record.get('validation_status')}")

    df = pd.read_parquet(path)

    required = {
        "symbol", "timestamp_utc", "timestamp_et", "trade_date",
        "open", "high", "low", "close", "volume",
        "session", "source", "adjusted", "cache_version",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        issues.append("missing_columns=" + ",".join(missing))

    parquet_rows = len(df)

    unique_timestamps = None
    duplicate_timestamps = None
    invalid_ohlc_count = None
    symbol_mismatch_count = None
    cache_version_mismatch_count = None
    source_mismatch_count = None
    adjusted_true_count = None
    first_ts = None
    last_ts = None

    if "timestamp_utc" in df.columns:
        unique_timestamps = int(df["timestamp_utc"].nunique())
        duplicate_timestamps = int(
            df.duplicated(["symbol", "timestamp_utc"]).sum()
        ) if "symbol" in df.columns else int(df["timestamp_utc"].duplicated().sum())
        first_ts = str(df["timestamp_utc"].min())
        last_ts = str(df["timestamp_utc"].max())
        if duplicate_timestamps:
            issues.append(f"duplicate_timestamps={duplicate_timestamps}")

    if {"open", "high", "low", "close"}.issubset(df.columns):
        invalid_ohlc_count = int((
            (df["high"] < df[["open", "close", "low"]].max(axis=1))
            | (df["low"] > df[["open", "close", "high"]].min(axis=1))
        ).sum())
        if invalid_ohlc_count:
            issues.append(f"invalid_ohlc={invalid_ohlc_count}")

    if "symbol" in df.columns:
        symbol_mismatch_count = int((df["symbol"] != symbol).sum())
        if symbol_mismatch_count:
            issues.append(f"symbol_mismatch={symbol_mismatch_count}")

    if "cache_version" in df.columns:
        cache_version_mismatch_count = int((df["cache_version"] != CACHE_VERSION).sum())
        if cache_version_mismatch_count:
            issues.append(f"cache_version_mismatch={cache_version_mismatch_count}")

    if "source" in df.columns:
        source_mismatch_count = int((df["source"] != SOURCE_NAME).sum())
        if source_mismatch_count:
            issues.append(f"source_mismatch={source_mismatch_count}")

    if "adjusted" in df.columns:
        adjusted_true_count = int(df["adjusted"].fillna(False).astype(bool).sum())
        if adjusted_true_count:
            issues.append(f"adjusted_true={adjusted_true_count}")

    manifest_rows = _safe_int(record.get("row_count"))
    if manifest_rows is not None and manifest_rows != parquet_rows:
        issues.append(f"row_count_mismatch={manifest_rows}!={parquet_rows}")

    manifest_size = _safe_int(record.get("file_size_bytes"))
    actual_size = path.stat().st_size
    if manifest_size is not None and manifest_size != actual_size:
        issues.append(f"file_size_mismatch={manifest_size}!={actual_size}")

    manifest_hash = record.get("file_hash")
    actual_hash = _sha256(path)
    hash_match = bool(manifest_hash) and str(manifest_hash) == actual_hash
    if not hash_match:
        issues.append("sha256_mismatch")

    # Timestamp year check in ET is authoritative for trade date partitioning.
    if "timestamp_et" in df.columns and len(df):
        years = pd.to_datetime(df["timestamp_et"]).dt.year.unique().tolist()
        if years != [year]:
            issues.append(f"timestamp_et_years={years}")

    status = "PASS" if not issues else "FAIL"

    return PartitionAudit(
        symbol=symbol,
        year=year,
        status=status,
        manifest_present=True,
        file_present=True,
        manifest_download_status=record.get("download_status"),
        manifest_validation_status=record.get("validation_status"),
        manifest_row_count=manifest_rows,
        parquet_row_count=parquet_rows,
        unique_timestamps=unique_timestamps,
        duplicate_timestamps=duplicate_timestamps,
        invalid_ohlc_count=invalid_ohlc_count,
        symbol_mismatch_count=symbol_mismatch_count,
        cache_version_mismatch_count=cache_version_mismatch_count,
        source_mismatch_count=source_mismatch_count,
        adjusted_true_count=adjusted_true_count,
        first_timestamp_utc=first_ts,
        last_timestamp_utc=last_ts,
        file_size_bytes_manifest=manifest_size,
        file_size_bytes_actual=actual_size,
        file_hash_match=hash_match,
        issues="; ".join(issues),
    )


def audit_universe_year(
    *,
    year: int,
    repo_root: Optional[Path] = None,
) -> DatasetAuditSummary:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]

    members = load_validated_universe(repo_root)
    symbols = [m.symbol for m in members]

    cfg = MarketCacheConfig.from_repo_root(repo_root)
    cfg.ensure_directories()
    manifest = LocalManifest(cfg.manifests_root / "market_cache_manifest.parquet")

    rows = [
        audit_partition(symbol=s, year=year, cfg=cfg, manifest=manifest)
        for s in symbols
    ]

    df = pd.DataFrame([asdict(r) for r in rows])

    report_dir = cfg.cache_root / "validation"
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_path = report_dir / f"PMPD_112_V1_{year}_integrity_audit.csv"
    parquet_path = report_dir / f"PMPD_112_V1_{year}_integrity_audit.parquet"

    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)

    pass_count = int((df["status"] == "PASS").sum())
    warn_count = int((df["status"] == "WARN").sum())
    fail_count = int((df["status"] == "FAIL").sum())

    return DatasetAuditSummary(
        year=year,
        expected_partitions=len(symbols),
        audited_partitions=len(df),
        pass_count=pass_count,
        warn_count=warn_count,
        fail_count=fail_count,
        research_ready_candidate=(len(df) == 112 and fail_count == 0),
        report_csv=str(csv_path),
        report_parquet=str(parquet_path),
    )
