from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
import shutil

import pandas as pd

from tr_platform.historical.certified_dataset import load_certified_partition


MIGRATION_FILENAME = "2026-08-28_Migration_004_PMPD_112_Universe_Registration.sql"


@dataclass(frozen=True)
class GuardrailResult:
    name: str
    passed: bool
    expected_exception: str
    observed_exception: str
    message: str


def _copy_fixture_repo(source_root: Path, dest_root: Path, symbol: str = "AAPL", year: int = 2025) -> None:
    # Universe source
    src_migration = (
        source_root / "sql" / "migrations" / MIGRATION_FILENAME
    )
    dst_migration = (
        dest_root / "sql" / "migrations" / MIGRATION_FILENAME
    )
    dst_migration.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_migration, dst_migration)

    # Production manifest
    src_manifest = (
        source_root
        / "market_cache"
        / "MARKET_CACHE_V1"
        / "manifests"
        / "market_cache_manifest.parquet"
    )
    dst_manifest = (
        dest_root
        / "market_cache"
        / "MARKET_CACHE_V1"
        / "manifests"
        / "market_cache_manifest.parquet"
    )
    dst_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_manifest, dst_manifest)

    # Readiness certification
    src_cert = (
        source_root
        / "market_cache"
        / "MARKET_CACHE_V1"
        / "validation"
        / f"PMPD_112_V1_{year}_readiness_certification.csv"
    )
    dst_cert = (
        dest_root
        / "market_cache"
        / "MARKET_CACHE_V1"
        / "validation"
        / f"PMPD_112_V1_{year}_readiness_certification.csv"
    )
    dst_cert.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_cert, dst_cert)

    # One production partition
    src_partition = (
        source_root
        / "market_cache"
        / "MARKET_CACHE_V1"
        / "1m"
        / symbol
        / f"{year}.parquet"
    )
    dst_partition = (
        dest_root
        / "market_cache"
        / "MARKET_CACHE_V1"
        / "1m"
        / symbol
        / f"{year}.parquet"
    )
    dst_partition.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_partition, dst_partition)


def _expect_failure(
    *,
    name: str,
    expected_exception: type[BaseException],
    action: Callable[[], object],
) -> GuardrailResult:
    try:
        action()
    except Exception as exc:
        passed = isinstance(exc, expected_exception)
        return GuardrailResult(
            name=name,
            passed=passed,
            expected_exception=expected_exception.__name__,
            observed_exception=type(exc).__name__,
            message=str(exc),
        )

    return GuardrailResult(
        name=name,
        passed=False,
        expected_exception=expected_exception.__name__,
        observed_exception="NO_EXCEPTION",
        message="Operation unexpectedly succeeded.",
    )


def run_guardrail_gate(repo_root: Path) -> list[GuardrailResult]:
    repo_root = repo_root.resolve()
    results: list[GuardrailResult] = []

    # 1) Unknown symbol: authoritative-universe membership must fail closed.
    results.append(_expect_failure(
        name="unknown_symbol_rejected",
        expected_exception=ValueError,
        action=lambda: load_certified_partition(
            symbol="ZZZZ_NOT_REAL",
            year=2025,
            repo_root=repo_root,
        ),
    ))

    # 2) Non-certified year: certification is required before any partition load.
    results.append(_expect_failure(
        name="uncertified_year_rejected",
        expected_exception=RuntimeError,
        action=lambda: load_certified_partition(
            symbol="AAPL",
            year=2024,
            repo_root=repo_root,
        ),
    ))

    # The next three tests use isolated temporary copies. Production files are never mutated.
    with TemporaryDirectory(prefix="pmpd_guardrail_") as td:
        tmp = Path(td)
        _copy_fixture_repo(repo_root, tmp)

        aapl_path = (
            tmp / "market_cache" / "MARKET_CACHE_V1" / "1m" / "AAPL" / "2025.parquet"
        )
        cert_path = (
            tmp
            / "market_cache"
            / "MARKET_CACHE_V1"
            / "validation"
            / "PMPD_112_V1_2025_readiness_certification.csv"
        )

        # 3) Missing file must fail rather than silently continue.
        missing_backup = aapl_path.with_suffix(".backup.parquet")
        aapl_path.replace(missing_backup)
        results.append(_expect_failure(
            name="missing_partition_rejected",
            expected_exception=FileNotFoundError,
            action=lambda: load_certified_partition(
                symbol="AAPL",
                year=2025,
                repo_root=tmp,
            ),
        ))
        missing_backup.replace(aapl_path)

        # 4) Valid Parquet whose contents no longer match the manifest SHA must fail.
        df = pd.read_parquet(aapl_path)
        original_close = df.loc[0, "close"]
        df.loc[0, "close"] = float(original_close) + 0.0001
        df.to_parquet(aapl_path, index=False)

        results.append(_expect_failure(
            name="hash_mismatch_rejected",
            expected_exception=RuntimeError,
            action=lambda: load_certified_partition(
                symbol="AAPL",
                year=2025,
                repo_root=tmp,
                verify_hash=True,
            ),
        ))

    # 5) Explicitly non-ready certification must fail.
    with TemporaryDirectory(prefix="pmpd_cert_guardrail_") as td:
        tmp = Path(td)
        _copy_fixture_repo(repo_root, tmp)

        cert_path = (
            tmp
            / "market_cache"
            / "MARKET_CACHE_V1"
            / "validation"
            / "PMPD_112_V1_2025_readiness_certification.csv"
        )
        cert = pd.read_csv(cert_path)
        cert.loc[:, "research_ready"] = False
        cert.loc[:, "readiness_status"] = "NOT_READY"
        cert.to_csv(cert_path, index=False)

        results.append(_expect_failure(
            name="non_ready_certification_rejected",
            expected_exception=RuntimeError,
            action=lambda: load_certified_partition(
                symbol="AAPL",
                year=2025,
                repo_root=tmp,
            ),
        ))

    return results


def write_guardrail_report(results: list[GuardrailResult], repo_root: Path) -> Path:
    out_dir = (
        repo_root
        / "market_cache"
        / "MARKET_CACHE_V1"
        / "validation"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "PMPD_112_V1_2025_guardrail_gate.csv"
    pd.DataFrame([r.__dict__ for r in results]).to_csv(path, index=False)
    return path
