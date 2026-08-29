from pathlib import Path
from tr_platform.validation.readiness_certification import certify_2025_readiness


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    r = certify_2025_readiness(year=2025, repo_root=root)
    print("=== READINESS CERTIFICATION TEST COMPLETE ===")
    print(f"Status: {r.readiness_status}")
    print(f"Research ready: {r.research_ready}")
    print(f"Structural PASS/FAIL: {r.structural_pass_count}/{r.structural_fail_count}")
    print(f"Coverage WARN/FAIL: {r.coverage_warn_count}/{r.coverage_fail_count}")
    print(f"Vendor parity: {r.vendor_cache_parity_pass}")
    print(f"Universe: {r.full_universe_partitions}/{r.full_universe_expected}")


if __name__ == "__main__":
    main()
