from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import pandas as pd

from tr_platform.common.cache_config import MarketCacheConfig


KNOWN_SOURCE_SPARSE_SYMBOLS_2025 = [
    "MNDY", "NOW", "KLAC", "BKNG", "BLK", "AXON", "URI", "REGN"
]


@dataclass(frozen=True)
class ReadinessCertification:
    year: int
    structural_integrity_pass: bool
    structural_pass_count: int
    structural_fail_count: int
    coverage_fail_count: int
    coverage_warn_count: int
    vendor_cache_parity_pass: bool
    vendor_cache_parity_cases: int
    vendor_cache_parity_failures: int
    full_universe_partitions: int
    full_universe_expected: int
    known_source_sparse_symbols: int
    research_ready: bool
    readiness_status: str
    rationale: str
    output_csv: str


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required validation report not found: {path}")
    return pd.read_csv(path)


def certify_2025_readiness(
    *,
    year: int,
    repo_root: Optional[Path] = None,
) -> ReadinessCertification:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]

    cfg = MarketCacheConfig.from_repo_root(repo_root)
    validation_dir = cfg.cache_root / "validation"

    structural_path = validation_dir / f"PMPD_112_V1_{year}_integrity_audit.csv"
    coverage_path = validation_dir / f"PMPD_112_V1_{year}_coverage_audit.csv"
    parity_path = validation_dir / f"PMPD_112_V1_{year}_vendor_cache_parity.csv"

    structural = _load_csv(structural_path)
    coverage = _load_csv(coverage_path)
    parity = _load_csv(parity_path)

    structural_pass_count = int((structural["status"] == "PASS").sum())
    structural_fail_count = int((structural["status"] == "FAIL").sum())

    coverage_fail_count = int((coverage["status"] == "FAIL").sum())
    coverage_warn_count = int((coverage["status"] == "WARN").sum())

    vendor_cache_parity_cases = len(parity)
    vendor_cache_parity_failures = int((parity["status"] == "FAIL").sum())

    full_universe_partitions = len(structural)
    full_universe_expected = 112

    structural_integrity_pass = (
        full_universe_partitions == full_universe_expected
        and structural_fail_count == 0
        and structural_pass_count == full_universe_expected
    )

    vendor_cache_parity_pass = (
        vendor_cache_parity_cases >= 4
        and vendor_cache_parity_failures == 0
    )

    known_sparse = set(KNOWN_SOURCE_SPARSE_SYMBOLS_2025)
    warned_symbols = set(
        coverage.loc[coverage["status"] == "WARN", "symbol"].astype(str)
    )

    only_known_source_sparsity = warned_symbols.issubset(known_sparse)

    research_ready = (
        structural_integrity_pass
        and coverage_fail_count == 0
        and vendor_cache_parity_pass
        and only_known_source_sparsity
        and full_universe_partitions == full_universe_expected
    )

    if research_ready:
        readiness_status = "RESEARCH_READY"
        rationale = (
            "PMPD_112_V1 2025 passes structural integrity for all 112 partitions, "
            "has no coverage FAIL partitions, and fresh vendor-to-cache parity "
            "matches exactly for all sampled forensic/control cases. The remaining "
            "coverage WARN symbols are treated as known source-level sparse aggregate "
            "characteristics rather than cache-loss defects."
        )
    else:
        readiness_status = "NOT_READY"
        rationale = (
            "One or more readiness gates failed: inspect structural integrity, "
            "coverage FAIL/WARN population, vendor-cache parity, and universe counts."
        )

    output_path = validation_dir / f"PMPD_112_V1_{year}_readiness_certification.csv"
    row = pd.DataFrame([asdict(ReadinessCertification(
        year=year,
        structural_integrity_pass=structural_integrity_pass,
        structural_pass_count=structural_pass_count,
        structural_fail_count=structural_fail_count,
        coverage_fail_count=coverage_fail_count,
        coverage_warn_count=coverage_warn_count,
        vendor_cache_parity_pass=vendor_cache_parity_pass,
        vendor_cache_parity_cases=vendor_cache_parity_cases,
        vendor_cache_parity_failures=vendor_cache_parity_failures,
        full_universe_partitions=full_universe_partitions,
        full_universe_expected=full_universe_expected,
        known_source_sparse_symbols=len(warned_symbols & known_sparse),
        research_ready=research_ready,
        readiness_status=readiness_status,
        rationale=rationale,
        output_csv=str(output_path),
    ))])
    row.to_csv(output_path, index=False)

    return ReadinessCertification(
        year=year,
        structural_integrity_pass=structural_integrity_pass,
        structural_pass_count=structural_pass_count,
        structural_fail_count=structural_fail_count,
        coverage_fail_count=coverage_fail_count,
        coverage_warn_count=coverage_warn_count,
        vendor_cache_parity_pass=vendor_cache_parity_pass,
        vendor_cache_parity_cases=vendor_cache_parity_cases,
        vendor_cache_parity_failures=vendor_cache_parity_failures,
        full_universe_partitions=full_universe_partitions,
        full_universe_expected=full_universe_expected,
        known_source_sparse_symbols=len(warned_symbols & known_sparse),
        research_ready=research_ready,
        readiness_status=readiness_status,
        rationale=rationale,
        output_csv=str(output_path),
    )
