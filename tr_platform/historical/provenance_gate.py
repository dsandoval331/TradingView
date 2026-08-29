from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Optional
import importlib.metadata
import json
import platform
import subprocess

from tr_platform.common.cache_config import CACHE_VERSION, SOURCE_NAME, CANONICAL_TIMEFRAME
from tr_platform.historical.certified_dataset import load_certified_partition
from tr_platform.universe.pmpd_universe import UNIVERSE_CODE


DEFAULT_SAMPLE = [
    ("AAPL", 2025),
    ("SPY", 2025),
    ("JNJ", 2025),
    ("PANW", 2025),
    ("BKNG", 2025),
    ("ARM", 2025),
]

STRATEGY_CODE = "PMPD"
MODEL_VERSION = "V4"
PARITY_SPEC_FILE = "2026-08-28_PMPD_V4_PARITY_SPEC_V1.md"
UNIVERSE_MIGRATION_FILE = "2026-08-28_Migration_004_PMPD_112_Universe_Registration.sql"


@dataclass(frozen=True)
class InputPartitionProvenance:
    symbol: str
    year: int
    rows: int
    file_path: str
    file_sha256: str
    first_timestamp_utc: str
    last_timestamp_utc: str
    manifest_validation_status: str
    certification_status: str


@dataclass(frozen=True)
class RunProvenance:
    strategy_code: str
    model_version: str
    universe_code: str
    cache_version: str
    timeframe: str
    source: str
    year: int
    git_commit: Optional[str]
    python_version: str
    pandas_version: Optional[str]
    pyarrow_version: Optional[str]
    parity_spec_path: Optional[str]
    parity_spec_sha256: Optional[str]
    universe_source_path: str
    universe_source_sha256: str
    readiness_certification_path: str
    readiness_certification_sha256: str
    run_config: dict
    input_partitions: list[InputPartitionProvenance]
    provenance_fingerprint_sha256: str
    generated_at_utc: str


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _package_version(name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _git_commit(repo_root: Path) -> Optional[str]:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _find_parity_spec(repo_root: Path) -> Optional[Path]:
    candidates = [
        repo_root / "docs" / "pmpd" / "specifications" / PARITY_SPEC_FILE,
        repo_root / "docs" / PARITY_SPEC_FILE,
        repo_root / "config" / PARITY_SPEC_FILE,
        repo_root / PARITY_SPEC_FILE,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def build_run_provenance(
    *,
    year: int,
    run_config: dict,
    sample: list[tuple[str, int]] = DEFAULT_SAMPLE,
    repo_root: Optional[Path] = None,
) -> RunProvenance:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]
    repo_root = repo_root.resolve()

    universe_path = repo_root / "sql" / "migrations" / UNIVERSE_MIGRATION_FILE
    if not universe_path.exists():
        raise FileNotFoundError(f"Universe source missing: {universe_path}")

    cert_path = (
        repo_root
        / "market_cache"
        / CACHE_VERSION
        / "validation"
        / f"PMPD_112_V1_{year}_readiness_certification.csv"
    )
    if not cert_path.exists():
        raise FileNotFoundError(f"Readiness certification missing: {cert_path}")

    parity_path = _find_parity_spec(repo_root)

    partitions: list[InputPartitionProvenance] = []
    for symbol, partition_year in sample:
        if partition_year != year:
            raise ValueError(
                f"Mixed-year provenance sample is not allowed: "
                f"{symbol} has {partition_year}, run year is {year}."
            )

        p = load_certified_partition(
            symbol=symbol,
            year=partition_year,
            repo_root=repo_root,
            verify_hash=True,
        )

        partitions.append(
            InputPartitionProvenance(
                symbol=symbol,
                year=partition_year,
                rows=p.row_count,
                file_path=p.file_path,
                file_sha256=p.file_sha256,
                first_timestamp_utc=p.first_timestamp_utc,
                last_timestamp_utc=p.last_timestamp_utc,
                manifest_validation_status=p.manifest_validation_status,
                certification_status=p.certification_status,
            )
        )

    stable_payload = {
        "strategy_code": STRATEGY_CODE,
        "model_version": MODEL_VERSION,
        "universe_code": UNIVERSE_CODE,
        "cache_version": CACHE_VERSION,
        "timeframe": CANONICAL_TIMEFRAME,
        "source": SOURCE_NAME,
        "year": year,
        "git_commit": _git_commit(repo_root),
        "python_version": platform.python_version(),
        "pandas_version": _package_version("pandas"),
        "pyarrow_version": _package_version("pyarrow"),
        "parity_spec_path": str(parity_path) if parity_path else None,
        "parity_spec_sha256": _sha256_file(parity_path) if parity_path else None,
        "universe_source_path": str(universe_path),
        "universe_source_sha256": _sha256_file(universe_path),
        "readiness_certification_path": str(cert_path),
        "readiness_certification_sha256": _sha256_file(cert_path),
        "run_config": run_config,
        "input_partitions": [asdict(x) for x in partitions],
    }

    fingerprint = sha256(
        json.dumps(
            stable_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    return RunProvenance(
        strategy_code=STRATEGY_CODE,
        model_version=MODEL_VERSION,
        universe_code=UNIVERSE_CODE,
        cache_version=CACHE_VERSION,
        timeframe=CANONICAL_TIMEFRAME,
        source=SOURCE_NAME,
        year=year,
        git_commit=stable_payload["git_commit"],
        python_version=stable_payload["python_version"],
        pandas_version=stable_payload["pandas_version"],
        pyarrow_version=stable_payload["pyarrow_version"],
        parity_spec_path=stable_payload["parity_spec_path"],
        parity_spec_sha256=stable_payload["parity_spec_sha256"],
        universe_source_path=stable_payload["universe_source_path"],
        universe_source_sha256=stable_payload["universe_source_sha256"],
        readiness_certification_path=stable_payload["readiness_certification_path"],
        readiness_certification_sha256=stable_payload["readiness_certification_sha256"],
        run_config=run_config,
        input_partitions=partitions,
        provenance_fingerprint_sha256=fingerprint,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def write_run_provenance(
    provenance: RunProvenance,
    *,
    repo_root: Optional[Path] = None,
) -> tuple[Path, Path]:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]
    repo_root = repo_root.resolve()

    out_dir = repo_root / "strategies" / "pmpd" / "output" / "provenance"
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = (
        f"{provenance.strategy_code}_{provenance.model_version}_"
        f"{provenance.universe_code}_{provenance.year}_"
        f"{provenance.provenance_fingerprint_sha256[:12]}"
    )

    json_path = out_dir / f"{stem}.json"
    txt_path = out_dir / f"{stem}.txt"

    payload = asdict(provenance)
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "=== PMPD HISTORICAL RUN PROVENANCE ===",
        f"Strategy: {provenance.strategy_code}",
        f"Model version: {provenance.model_version}",
        f"Universe: {provenance.universe_code}",
        f"Year: {provenance.year}",
        f"Cache version: {provenance.cache_version}",
        f"Timeframe: {provenance.timeframe}",
        f"Source: {provenance.source}",
        f"Git commit: {provenance.git_commit}",
        f"Python: {provenance.python_version}",
        f"Pandas: {provenance.pandas_version}",
        f"PyArrow: {provenance.pyarrow_version}",
        f"Parity spec: {provenance.parity_spec_path}",
        f"Parity spec SHA256: {provenance.parity_spec_sha256}",
        f"Universe source SHA256: {provenance.universe_source_sha256}",
        f"Readiness cert SHA256: {provenance.readiness_certification_sha256}",
        f"Provenance fingerprint: {provenance.provenance_fingerprint_sha256}",
        "",
        "Run config:",
        json.dumps(provenance.run_config, indent=2, sort_keys=True),
        "",
        "Input partitions:",
    ]

    for p in provenance.input_partitions:
        lines.append(
            f"- {p.symbol} {p.year}: rows={p.rows}, "
            f"sha256={p.file_sha256}, cert={p.certification_status}, "
            f"manifest={p.manifest_validation_status}"
        )

    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, txt_path
