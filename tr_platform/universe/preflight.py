from __future__ import annotations

import argparse
from pathlib import Path

from tr_platform.universe.pmpd_universe import (
    get_set_members,
    load_validated_universe,
    validate_members,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate PMPD_112_V1 and print a set/year acquisition preflight."
    )
    parser.add_argument("--set", type=int, required=True, dest="set_number")
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    root = repo_root()
    universe = load_validated_universe(root)
    validation = validate_members(universe)
    selected = get_set_members(root, args.set_number)

    print("=== PMPD_112_V1 UNIVERSE VALIDATION ===")
    print(f"Total members:  {validation.total_members}")
    print(f"Unique symbols: {validation.unique_symbols}")
    for set_code in sorted(validation.set_counts):
        print(f"{set_code}:         {validation.set_counts[set_code]}")
    print("Authoritative correction: SET_1 #12=CVX / SET_4 #27=CVS")
    print()
    print(f"=== SET_{args.set_number} / {args.year} PREFLIGHT ===")
    print(f"Partitions: {len(selected)}")
    print()

    for member in selected:
        print(
            f"{member.position_in_set:>2}. "
            f"{member.symbol:<6} -> {member.symbol} {args.year}"
        )


if __name__ == "__main__":
    main()
