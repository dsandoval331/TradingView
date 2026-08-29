from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable


UNIVERSE_CODE = "PMPD_112_V1"
EXPECTED_TOTAL = 112
EXPECTED_SET_COUNT = 4
EXPECTED_PER_SET = 28

MIGRATION_FILENAME = "2026-08-28_Migration_004_PMPD_112_Universe_Registration.sql"

_MEMBER_RE = re.compile(
    r"\('(?P<set_code>SET_[1-4])'\s*,\s*(?P<position>\d+)\s*,\s*'(?P<symbol>[A-Z0-9.\-]+)'\)"
)


@dataclass(frozen=True)
class UniverseMember:
    set_code: str
    position_in_set: int
    symbol: str


@dataclass(frozen=True)
class UniverseValidation:
    total_members: int
    unique_symbols: int
    set_counts: dict[str, int]
    valid: bool


def default_migration_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "sql"
        / "migrations"
        / MIGRATION_FILENAME
    )


def load_members_from_migration(migration_path: Path) -> list[UniverseMember]:
    if not migration_path.exists():
        raise FileNotFoundError(
            f"Authoritative universe migration not found: {migration_path}"
        )

    text = migration_path.read_text(encoding="utf-8", errors="replace")

    members = [
        UniverseMember(
            set_code=m.group("set_code"),
            position_in_set=int(m.group("position")),
            symbol=m.group("symbol"),
        )
        for m in _MEMBER_RE.finditer(text)
    ]

    if not members:
        raise ValueError(
            f"No {UNIVERSE_CODE} membership rows found in {migration_path}"
        )

    return members


def validate_members(members: Iterable[UniverseMember]) -> UniverseValidation:
    members = list(members)

    set_counts = {
        f"SET_{i}": sum(m.set_code == f"SET_{i}" for m in members)
        for i in range(1, EXPECTED_SET_COUNT + 1)
    }

    unique_symbols = len({m.symbol for m in members})

    # Validate set positions are exactly 1..28.
    for set_code in set_counts:
        positions = sorted(
            m.position_in_set for m in members if m.set_code == set_code
        )
        expected = list(range(1, EXPECTED_PER_SET + 1))
        if positions != expected:
            raise ValueError(
                f"{set_code} positions invalid. "
                f"Expected 1..{EXPECTED_PER_SET}, found {positions}"
            )

    # Authoritative correction guard.
    set1_pos12 = next(
        (m.symbol for m in members if m.set_code == "SET_1" and m.position_in_set == 12),
        None,
    )
    set4_pos27 = next(
        (m.symbol for m in members if m.set_code == "SET_4" and m.position_in_set == 27),
        None,
    )

    if set1_pos12 != "CVX":
        raise ValueError(f"Expected SET_1 position 12 = CVX, found {set1_pos12}")

    if set4_pos27 != "CVS":
        raise ValueError(f"Expected SET_4 position 27 = CVS, found {set4_pos27}")

    valid = (
        len(members) == EXPECTED_TOTAL
        and unique_symbols == EXPECTED_TOTAL
        and all(count == EXPECTED_PER_SET for count in set_counts.values())
    )

    if not valid:
        raise ValueError(
            "Universe validation failed: "
            f"total={len(members)}, unique={unique_symbols}, sets={set_counts}"
        )

    return UniverseValidation(
        total_members=len(members),
        unique_symbols=unique_symbols,
        set_counts=set_counts,
        valid=True,
    )


def load_validated_universe(repo_root: Path) -> list[UniverseMember]:
    path = default_migration_path(repo_root)
    members = load_members_from_migration(path)
    validate_members(members)
    return sorted(members, key=lambda m: (m.set_code, m.position_in_set))


def get_set_members(
    repo_root: Path,
    set_number: int,
) -> list[UniverseMember]:
    if set_number not in {1, 2, 3, 4}:
        raise ValueError("set_number must be 1, 2, 3, or 4.")

    members = load_validated_universe(repo_root)
    set_code = f"SET_{set_number}"
    selected = [m for m in members if m.set_code == set_code]

    if len(selected) != EXPECTED_PER_SET:
        raise ValueError(
            f"{set_code} expected {EXPECTED_PER_SET} members, found {len(selected)}"
        )

    return selected
