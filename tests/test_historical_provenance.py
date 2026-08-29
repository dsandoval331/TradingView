from pathlib import Path

from tr_platform.historical.provenance_gate import build_run_provenance


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    config = {
        "purpose": "8H-6A-6H-5-test",
        "primary_benchmark": "+0.50% favorable before -0.50% adverse",
        "signal_model": "Frozen V4 parity specification",
    }

    a = build_run_provenance(year=2025, run_config=config, repo_root=root)
    b = build_run_provenance(year=2025, run_config=config, repo_root=root)

    assert a.provenance_fingerprint_sha256 == b.provenance_fingerprint_sha256
    assert len(a.provenance_fingerprint_sha256) == 64
    assert a.strategy_code == "PMPD"
    assert a.model_version == "V4"
    assert a.universe_code == "PMPD_112_V1"
    assert a.cache_version == "MARKET_CACHE_V1"
    assert a.year == 2025
    assert len(a.input_partitions) == 6
    assert len(a.universe_source_sha256) == 64
    assert len(a.readiness_certification_sha256) == 64

    for p in a.input_partitions:
        assert len(p.file_sha256) == 64
        assert p.certification_status == "RESEARCH_READY"

    print("=== ARTIFACT & PROVENANCE TEST PASS ===")
    print(f"Strategy/model: {a.strategy_code}/{a.model_version}")
    print(f"Universe/year: {a.universe_code}/{a.year}")
    print(f"Input partitions: {len(a.input_partitions)}")
    print(f"Fingerprint: {a.provenance_fingerprint_sha256}")
    print("Repeated build fingerprint identical: PASS")


if __name__ == "__main__":
    main()
