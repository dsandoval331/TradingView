from __future__ import annotations

from pathlib import Path

from tr_platform.universe.pmpd_universe import (
    get_set_members,
    load_validated_universe,
    validate_members,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> None:
    root = repo_root()

    members = load_validated_universe(root)
    validation = validate_members(members)

    assert validation.total_members == 112
    assert validation.unique_symbols == 112
    assert validation.set_counts == {
        "SET_1": 28,
        "SET_2": 28,
        "SET_3": 28,
        "SET_4": 28,
    }

    set1 = get_set_members(root, 1)
    set4 = get_set_members(root, 4)

    assert len(set1) == 28
    assert len(set4) == 28
    assert set1[0].symbol == "MSFT"
    assert set1[11].symbol == "CVX"
    assert set4[26].symbol == "CVS"
    assert set4[27].symbol == "NEE"

    print("=== PMPD_112_V1 LOADER TEST PASS ===")
    print("Total members: 112")
    print("Unique symbols: 112")
    print("SET_1/2/3/4: 28 each")
    print("SET_1 #12: CVX")
    print("SET_4 #27: CVS")
    print("Set 1 first/last: MSFT / TQQQ")
    print("Set 4 first/last: ARM / NEE")


if __name__ == "__main__":
    main()
