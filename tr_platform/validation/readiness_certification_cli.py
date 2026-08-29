from __future__ import annotations

import argparse
from tr_platform.validation.readiness_certification import certify_2025_readiness


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Certify PMPD_112_V1 dataset research readiness."
    )
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    r = certify_2025_readiness(year=args.year)

    print("=== PMPD_112_V1 RESEARCH READINESS CERTIFICATION ===")
    print(f"Year:                         {r.year}")
    print(f"Structural integrity:         {r.structural_integrity_pass}")
    print(f"Structural PASS/FAIL:         {r.structural_pass_count}/{r.structural_fail_count}")
    print(f"Coverage WARN/FAIL:           {r.coverage_warn_count}/{r.coverage_fail_count}")
    print(f"Vendor-cache parity:          {r.vendor_cache_parity_pass}")
    print(f"Parity cases/failures:        {r.vendor_cache_parity_cases}/{r.vendor_cache_parity_failures}")
    print(f"Universe partitions:          {r.full_universe_partitions}/{r.full_universe_expected}")
    print(f"Known sparse-source symbols:  {r.known_source_sparse_symbols}")
    print(f"Readiness status:             {r.readiness_status}")
    print(f"Research ready:               {r.research_ready}")
    print(f"Certification CSV:            {r.output_csv}")
    print()
    print("Rationale:")
    print(r.rationale)

    if not r.research_ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
