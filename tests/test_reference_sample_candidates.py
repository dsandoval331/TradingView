from pathlib import Path
from collections import Counter

from tr_platform.parity.reference_sample_candidates import (
    build_candidate_manifest,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    a = build_candidate_manifest(repo_root=root)
    b = build_candidate_manifest(repo_root=root)

    assert a == b
    assert len(a) == 48

    counts = Counter(c.set_code for c in a)
    assert counts == {
        "SET_1": 12,
        "SET_2": 12,
        "SET_3": 12,
        "SET_4": 12,
    }

    # Candidate diversity: one symbol per set candidate slot.
    for set_code in counts:
        symbols = [c.symbol for c in a if c.set_code == set_code]
        assert len(symbols) == len(set(symbols))

    # Required sparse edge cases are present.
    assert any(c.symbol == "MNDY" for c in a)
    assert any(c.symbol == "BKNG" for c in a)
    assert any(c.symbol == "BLK" for c in a)

    print("=== 8H-7B-1 CANDIDATE SELECTION TEST PASS ===")
    print("Deterministic repeated build: PASS")
    print("Total candidates: 48")
    print("SET_1/2/3/4: 12 each")
    print("Python PMPD signal output used: NO")


if __name__ == "__main__":
    main()
