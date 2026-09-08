from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

from tr_platform.pmpd_v5.certification import _fingerprint_rows, compare_package_fingerprints


def main() -> None:
    df = pd.DataFrame([
        {"event_id": "A_1", "direction": "BULL", "max_levels_cleared": 3},
        {"event_id": "A_2", "direction": "BEAR", "max_levels_cleared": 2},
    ])
    a = _fingerprint_rows(df, ["event_id", "direction", "max_levels_cleared"])
    b = _fingerprint_rows(df.copy(), ["event_id", "direction", "max_levels_cleared"])
    assert a == b

    tmp = Path("/tmp/pmpd_v5_cert_test")
    tmp.mkdir(parents=True, exist_ok=True)
    payload = {
        "selection_fingerprint": "abc",
        "run_fingerprint": "def",
        "symbol_aggregate_fingerprints": [{"symbol": "AAPL", "aggregate_fp": "xyz"}],
    }
    p1, p2 = tmp / "a.json", tmp / "b.json"
    p1.write_text(json.dumps(payload), encoding="utf-8")
    p2.write_text(json.dumps(payload), encoding="utf-8")
    assert compare_package_fingerprints(p1, p2) == []

    payload["run_fingerprint"] = "changed"
    p2.write_text(json.dumps(payload), encoding="utf-8")
    assert "run_fingerprint_mismatch" in compare_package_fingerprints(p1, p2)
    print("=== PMPD V5 CERTIFICATION HARNESS SYNTHETIC TEST PASS ===")


if __name__ == "__main__":
    main()
