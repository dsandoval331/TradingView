from __future__ import annotations

from tr_platform.historical.provenance_gate import (
    build_run_provenance,
    write_run_provenance,
)


def main() -> None:
    run_config = {
        "purpose": "8H-6A-6H-5 artifact_and_provenance_gate",
        "primary_benchmark": "+0.50% favorable before -0.50% adverse",
        "signal_model": "Frozen V4 parity specification",
        "data_policy": "Certified PMPD_112_V1 2025 production cache only",
    }

    p = build_run_provenance(year=2025, run_config=run_config)
    json_path, txt_path = write_run_provenance(p)

    print("=== ARTIFACT & PROVENANCE GATE PASS ===")
    print(f"Strategy/model:          {p.strategy_code}/{p.model_version}")
    print(f"Universe/year:           {p.universe_code}/{p.year}")
    print(f"Cache/timeframe/source:  {p.cache_version}/{p.timeframe}/{p.source}")
    print(f"Git commit:              {p.git_commit}")
    print(f"Input partitions:        {len(p.input_partitions)}")
    print(f"Universe SHA-256:        {p.universe_source_sha256}")
    print(f"Readiness cert SHA-256:  {p.readiness_certification_sha256}")
    print(f"Parity spec SHA-256:     {p.parity_spec_sha256}")
    print(f"Provenance fingerprint:  {p.provenance_fingerprint_sha256}")
    print(f"JSON artifact:           {json_path}")
    print(f"Text artifact:           {txt_path}")


if __name__ == "__main__":
    main()
