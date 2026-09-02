from __future__ import annotations

from collections import Counter

from tr_platform.parity.reference_sample_candidates import (
    build_candidate_manifest,
    write_candidate_manifest,
)


def main() -> None:
    cases = build_candidate_manifest()
    csv_path, json_path, manifest_sha = write_candidate_manifest(cases)

    print("=== PMPD 8H-7B-1 REFERENCE SAMPLE CANDIDATES ===")
    print(f"Candidates: {len(cases)}")
    counts = Counter(c.set_code for c in cases)
    for set_code in sorted(counts):
        print(f"{set_code}: {counts[set_code]}")
    print(f"Sparse-source candidates: {sum(c.source_sparse_symbol for c in cases)}")
    print()
    for c in cases:
        sparse = " SPARSE" if c.source_sparse_symbol else ""
        print(
            f"{c.candidate_id} | {c.set_code} #{c.position_in_set} | "
            f"{c.symbol} | {c.trade_date}{sparse}"
        )
    print()
    print(f"CSV:  {csv_path}")
    print(f"JSON: {json_path}")
    print(f"Manifest SHA-256: {manifest_sha}")
    print()
    print("IMPORTANT: These are candidate symbol/date cases only.")
    print("No Python PMPD signal result was used to select them.")
    print("Pine evidence will classify candidates before the final 24-case sample is frozen.")


if __name__ == "__main__":
    main()
