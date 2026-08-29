from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import hashlib

import pandas as pd

from tr_platform.common.cache_config import (
    CACHE_VERSION,
    SOURCE_NAME,
    CANONICAL_TIMEFRAME,
    MarketCacheConfig,
)
from tr_platform.common.manifest import LocalManifest
from tr_platform.universe.pmpd_universe import (
    UNIVERSE_CODE,
    load_validated_universe,
)


REQUIRED_COLUMNS = [
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

VALID_SESSIONS = {"PRE", "RTH", "AH", "OVERNIGHT"}


@dataclass(frozen=True)
class CertifiedPartition:
    symbol: str
    year: int
    universe_code: str
    cache_version: str
    timeframe: str
    source: str
    row_count: int
    first_timestamp_utc: str
    last_timestamp_utc: str
    file_path: str
    file_sha256: str
    manifest_validation_status: str
    certification_status: str
    dataframe: pd.DataFrame


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _certification_path(cfg: MarketCacheConfig, year: int) -> Path:
    return (
        cfg.cache_root
        / "validation"
        / f"PMPD_112_V1_{year}_readiness_certification.csv"
    )


def _assert_dataset_certified(cfg: MarketCacheConfig, year: int) -> str:
    path = _certification_path(cfg, year)

    if not path.exists():
        raise RuntimeError(
            f"Dataset certification missing for {UNIVERSE_CODE} {year}: {path}"
        )

    cert = pd.read_csv(path)

    if len(cert) != 1:
        raise RuntimeError(
            f"Expected exactly one readiness-certification row, found {len(cert)}."
        )

    row = cert.iloc[0]

    ready_raw = row.get("research_ready")
    if isinstance(ready_raw, str):
        ready = ready_raw.strip().lower() == "true"
    else:
        ready = bool(ready_raw)

    status = str(row.get("readiness_status", "")).strip()

    if not ready or status != "RESEARCH_READY":
        raise RuntimeError(
            f"Dataset is not certified research-ready: "
            f"research_ready={ready_raw}, readiness_status={status}"
        )

    return status


def _assert_symbol_in_universe(repo_root: Path, symbol: str) -> None:
    members = load_validated_universe(repo_root)
    symbols = {m.symbol for m in members}
    if symbol not in symbols:
        raise ValueError(
            f"{symbol} is not a member of authoritative universe {UNIVERSE_CODE}."
        )


def _assert_schema_and_values(df: pd.DataFrame, symbol: str, year: int) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise RuntimeError(f"Certified partition missing columns: {missing}")

    if df.empty:
        raise RuntimeError("Certified partition is empty.")

    if int(df["timestamp_utc"].nunique()) != len(df):
        raise RuntimeError("Certified partition contains duplicate UTC timestamps.")

    if int((df["symbol"] != symbol).sum()) != 0:
        raise RuntimeError("Certified partition contains symbol mismatches.")

    if int((df["cache_version"] != CACHE_VERSION).sum()) != 0:
        raise RuntimeError("Certified partition contains cache-version mismatches.")

    if int((df["source"] != SOURCE_NAME).sum()) != 0:
        raise RuntimeError("Certified partition contains source mismatches.")

    if int(df["adjusted"].fillna(False).astype(bool).sum()) != 0:
        raise RuntimeError("Certified partition unexpectedly contains adjusted=True rows.")

    sessions = set(df["session"].dropna().astype(str).unique())
    unknown_sessions = sessions - VALID_SESSIONS
    if unknown_sessions:
        raise RuntimeError(f"Unknown session labels: {sorted(unknown_sessions)}")

    utc = pd.to_datetime(df["timestamp_utc"])
    et = pd.to_datetime(df["timestamp_et"])

    if getattr(utc.dt, "tz", None) is None:
        raise RuntimeError("timestamp_utc is not timezone-aware.")

    if getattr(et.dt, "tz", None) is None:
        raise RuntimeError("timestamp_et is not timezone-aware.")

    years = sorted(set(et.dt.year.tolist()))
    if years != [year]:
        raise RuntimeError(
            f"Certified partition contains unexpected ET years: {years}"
        )

    numeric_cols = [
        "open", "high", "low", "close", "volume",
        "vwap", "transactions", "timestamp_ms",
    ]
    bad_numeric = [
        c for c in numeric_cols
        if not pd.api.types.is_numeric_dtype(df[c])
    ]
    if bad_numeric:
        raise RuntimeError(
            f"Expected numeric columns are not numeric: {bad_numeric}"
        )


def load_certified_partition(
    *,
    symbol: str,
    year: int,
    repo_root: Optional[Path] = None,
    verify_hash: bool = True,
) -> CertifiedPartition:
    """
    Load one production partition only if:
      1) the full PMPD_112_V1/year dataset is formally RESEARCH_READY;
      2) the symbol belongs to the authoritative frozen universe;
      3) the production manifest says the partition is complete/validated;
      4) the Parquet file exists and matches manifest row/hash metadata;
      5) canonical schema, dtypes, symbol/year/source/cache/session checks pass.
    """
    symbol = symbol.upper().strip()

    if repo_root is None:
        repo_root = _repo_root()
    repo_root = repo_root.resolve()

    cfg = MarketCacheConfig.from_repo_root(repo_root)
    certification_status = _assert_dataset_certified(cfg, year)
    _assert_symbol_in_universe(repo_root, symbol)

    path = cfg.symbol_year_path(symbol, year)
    if not path.exists():
        raise FileNotFoundError(f"Certified partition file missing: {path}")

    manifest = LocalManifest(
        cfg.manifests_root / "market_cache_manifest.parquet"
    )
    rec = manifest.get(
        symbol=symbol,
        year=year,
        timeframe=CANONICAL_TIMEFRAME,
        source=SOURCE_NAME,
        adjusted=False,
        cache_version=CACHE_VERSION,
    )

    if rec is None:
        raise RuntimeError(f"Manifest record missing for {symbol} {year}.")

    if rec.get("download_status") != "DOWNLOADED":
        raise RuntimeError(
            f"Manifest download_status is {rec.get('download_status')}, not DOWNLOADED."
        )

    if rec.get("validation_status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        raise RuntimeError(
            f"Manifest validation_status is {rec.get('validation_status')}."
        )

    df = pd.read_parquet(path)
    _assert_schema_and_values(df, symbol, year)

    manifest_rows = int(rec.get("row_count") or 0)
    if manifest_rows != len(df):
        raise RuntimeError(
            f"Manifest/Parquet row mismatch: {manifest_rows} != {len(df)}"
        )

    manifest_hash = str(rec.get("file_hash") or "")
    if not manifest_hash:
        raise RuntimeError("Manifest SHA-256 is missing.")

    actual_hash = manifest_hash
    if verify_hash:
        actual_hash = _sha256_file(path)
        if actual_hash != manifest_hash:
            raise RuntimeError(
                f"SHA-256 mismatch for {symbol} {year}: "
                f"manifest={manifest_hash}, actual={actual_hash}"
            )

    utc = pd.to_datetime(df["timestamp_utc"])

    return CertifiedPartition(
        symbol=symbol,
        year=year,
        universe_code=UNIVERSE_CODE,
        cache_version=CACHE_VERSION,
        timeframe=CANONICAL_TIMEFRAME,
        source=SOURCE_NAME,
        row_count=len(df),
        first_timestamp_utc=str(utc.min()),
        last_timestamp_utc=str(utc.max()),
        file_path=str(path),
        file_sha256=actual_hash,
        manifest_validation_status=str(rec.get("validation_status")),
        certification_status=certification_status,
        dataframe=df,
    )
