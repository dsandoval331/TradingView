from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research_runner.jobs import pmpd_edge_e3_batch2 as b2

PROTOCOL = "PMPD_EDGE_E3_TRADE_HEALTH_PROTOCOL_V1"
SHARDS = 16


def run(root: Path) -> dict:
    """Mechanical persistence-compatible rerun of unchanged E3-B2 research logic.

    E3-B2 completed its research computation successfully but the monolithic
    trade_health_events.parquet exceeded the governed artifact upload limit.
    This wrapper reruns the unchanged B2 logic, deterministically shards only
    the large parquet artifact, removes the monolith, and returns the shards
    plus the original coverage/summary artifacts for governed persistence.
    """
    result = b2.run(root)
    if result.get("status") != "PASS" or result.get("protocol") != PROTOCOL:
        raise RuntimeError("underlying E3-B2 did not PASS with the frozen protocol")

    out = root / "research_outputs" / "pmpd" / "edge" / "e3_batch2"
    mono = out / "trade_health_events.parquet"
    coverage = out / "event_coverage.csv"
    summary_p = out / "summary.json"
    if not mono.exists() or not coverage.exists() or not summary_p.exists():
        raise FileNotFoundError("expected E3-B2 outputs missing before sharding")

    ev = pd.read_parquet(mono)
    if ev.empty:
        raise RuntimeError("E3-B2 event dataset is empty")

    # Deterministic symbol-based sharding. Research rows and semantics are
    # unchanged; only artifact packaging differs from the original B2 run.
    symbols = sorted(ev["symbol"].astype(str).unique())
    shard_paths: list[Path] = []
    manifest_rows = []
    for shard_id in range(SHARDS):
        shard_symbols = symbols[shard_id::SHARDS]
        part = ev[ev["symbol"].astype(str).isin(shard_symbols)].copy()
        p = out / f"trade_health_events_part_{shard_id:02d}.parquet"
        part.to_parquet(p, index=False)
        shard_paths.append(p)
        manifest_rows.append({
            "shard_id": shard_id,
            "rows": int(len(part)),
            "symbols": shard_symbols,
            "file": p.name,
            "size_bytes": int(p.stat().st_size),
        })

    if sum(x["rows"] for x in manifest_rows) != len(ev):
        raise RuntimeError("shard row-count reconciliation failed")

    mono.unlink()
    manifest = {
        "step": "PMPD-EDGE-E3-B2-R2",
        "protocol": PROTOCOL,
        "mechanical_change_only": True,
        "research_logic_changed": False,
        "source_step": "PMPD-EDGE-E3-B2",
        "event_rows": int(len(ev)),
        "unique_trades": int(ev["event_key"].nunique()),
        "symbols": int(ev["symbol"].nunique()),
        "shard_count": SHARDS,
        "row_reconciliation_pass": True,
        "shards": manifest_rows,
        "guardrails": {
            "research_only": True,
            "2026_development_evidence": True,
            "v4_modified": False,
            "v5_modified": False,
            "production_rule_authorized": False,
            "trade_health_score_fit": False,
            "signal_quality_separate": True,
        },
    }
    manifest_p = out / "artifact_manifest.json"
    manifest_p.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print("PMPD_EDGE_E3_B2_R2_MANIFEST=" + json.dumps(manifest, sort_keys=True, default=str))

    outputs = shard_paths + [coverage, summary_p, manifest_p]
    return {
        "status": "PASS",
        "protocol": PROTOCOL,
        "mechanical_change_only": True,
        "research_logic_changed": False,
        "output_paths": [str(p.relative_to(root)) for p in outputs],
        "research_only": True,
        "v4_modified": False,
        "v5_modified": False,
        "production_rule_authorized": False,
    }
