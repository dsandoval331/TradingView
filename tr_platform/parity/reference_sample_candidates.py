from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
from typing import Optional
import json

import pandas as pd

from tr_platform.historical.certified_dataset import load_certified_partition
from tr_platform.universe.pmpd_universe import load_validated_universe


PROTOCOL_CODE = "PMPD_V4_PARITY_PROTOCOL_V1"
PROTOCOL_SHA256 = "924a410da843d6a6d8ddb267d3b88d6e824a815c983e0cb4847ccfb6532c0b46"
SAMPLE_VERSION = "PMPD_V4_PARITY_SAMPLE_CANDIDATES_V1"
YEAR = 2025

# Candidate pool is intentionally larger than the final 24-case sample.
# Pine evidence, not Python PMPD signal output, is used to classify candidates.
CANDIDATES_PER_SET = 12
FINAL_TARGET_PER_SET = 6

KNOWN_SPARSE = {"MNDY", "NOW", "KLAC", "BKNG", "BLK", "AXON", "URI", "REGN"}

# Freeze one sparse-source case into the candidate pool for edge-case coverage.
REQUIRED_SPARSE = {
    "SET_1": None,
    "SET_2": "MNDY",
    "SET_3": "BKNG",
    "SET_4": "BLK",
}


@dataclass(frozen=True)
class CandidateCase:
    candidate_id: str
    sample_version: str
    set_code: str
    position_in_set: int
    symbol: str
    trade_date: str
    source_sparse_symbol: bool
    selection_rank: int
    selection_hash: str
    selection_basis: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _hash_key(set_code: str, symbol: str, trade_date: str) -> str:
    payload = f"{PROTOCOL_SHA256}|{set_code}|{symbol}|{trade_date}"
    return sha256(payload.encode("utf-8")).hexdigest()


def _candidate_dates_for_symbol(
    *,
    symbol: str,
    year: int,
    repo_root: Path,
) -> list[str]:
    p = load_certified_partition(
        symbol=symbol,
        year=year,
        repo_root=repo_root,
        verify_hash=False,
    )
    dates = (
        pd.to_datetime(p.dataframe["trade_date"])
        .dt.strftime("%Y-%m-%d")
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    return dates


def build_candidate_manifest(
    *,
    repo_root: Optional[Path] = None,
    year: int = YEAR,
) -> list[CandidateCase]:
    if repo_root is None:
        repo_root = _repo_root()
    repo_root = repo_root.resolve()

    members = load_validated_universe(repo_root)
    by_set: dict[str, list] = {}
    for m in members:
        by_set.setdefault(m.set_code, []).append(m)

    selected: list[CandidateCase] = []

    for set_code in sorted(by_set):
        members_in_set = sorted(by_set[set_code], key=lambda x: x.position_in_set)
        pool = []

        for member in members_in_set:
            dates = _candidate_dates_for_symbol(
                symbol=member.symbol,
                year=year,
                repo_root=repo_root,
            )
            for trade_date in dates:
                h = _hash_key(set_code, member.symbol, trade_date)
                pool.append((h, member, trade_date))

        pool.sort(key=lambda x: x[0])

        # First pass: one candidate per symbol maximum, preventing a single
        # symbol from dominating the pool.
        chosen = []
        used_symbols = set()

        required_symbol = REQUIRED_SPARSE.get(set_code)
        if required_symbol:
            req_rows = [x for x in pool if x[1].symbol == required_symbol]
            if req_rows:
                chosen.append(req_rows[0])
                used_symbols.add(required_symbol)

        for row in pool:
            _, member, _ = row
            if member.symbol in used_symbols:
                continue
            chosen.append(row)
            used_symbols.add(member.symbol)
            if len(chosen) >= CANDIDATES_PER_SET:
                break

        if len(chosen) != CANDIDATES_PER_SET:
            raise RuntimeError(
                f"{set_code}: expected {CANDIDATES_PER_SET} candidates, got {len(chosen)}"
            )

        # Stable rank inside set.
        chosen.sort(key=lambda x: x[0])

        for rank, (h, member, trade_date) in enumerate(chosen, start=1):
            candidate_id = f"{set_code}_{rank:02d}_{member.symbol}_{trade_date}"
            selected.append(
                CandidateCase(
                    candidate_id=candidate_id,
                    sample_version=SAMPLE_VERSION,
                    set_code=set_code,
                    position_in_set=member.position_in_set,
                    symbol=member.symbol,
                    trade_date=trade_date,
                    source_sparse_symbol=member.symbol in KNOWN_SPARSE,
                    selection_rank=rank,
                    selection_hash=h,
                    selection_basis=(
                        "Protocol-hash deterministic symbol/date selection; "
                        "no PMPD Python signal output used."
                    ),
                )
            )

    return selected


def write_candidate_manifest(
    cases: list[CandidateCase],
    *,
    repo_root: Optional[Path] = None,
) -> tuple[Path, Path, str]:
    if repo_root is None:
        repo_root = _repo_root()
    repo_root = repo_root.resolve()

    out_dir = repo_root / "docs" / "pmpd" / "parity"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "PMPD_V4_PARITY_SAMPLE_CANDIDATES_V1.csv"
    json_path = out_dir / "PMPD_V4_PARITY_SAMPLE_CANDIDATES_V1.json"

    rows = [asdict(c) for c in cases]
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    json_path.write_text(
        json.dumps(rows, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    fingerprint_payload = json.dumps(
        rows, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    manifest_sha = sha256(fingerprint_payload).hexdigest()

    return csv_path, json_path, manifest_sha
