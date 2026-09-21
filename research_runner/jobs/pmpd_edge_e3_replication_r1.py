from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from tr_platform.pmpd_v5.certification import run_full_universe_structural_baseline

PROTOCOL = "PMPD_EDGE_E3_TRADE_HEALTH_PROTOCOL_V1"
DATASET = "PMPD-EDGE-E3-REPLICATION-2025-HOLDOUT-V1"
CANDIDATE = "PMPD_V5_CANDIDATE_DP4_UNSCORED_V1"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(root: Path) -> dict:
    """Outcome-blind reconstruction/preflight for the frozen 2025 E3 replication cohort.

    This batch deliberately stops before Trade Health event/outcome association.  It
    reconstructs the V5 structural engine from the frozen 112-symbol MARKET_CACHE_V1
    cohort and extracts DP4_FULL_STACK_FIRST_CLEAR decision points so the subsequent
    replication batch can apply the frozen E3 protocol without inspecting outcomes
    during engine/candidate certification.
    """
    dataset_marker = root / "research_outputs" / "pmpd" / "edge" / "e3_2025_replication" / "dataset_freeze.json"
    out = root / "research_outputs" / "pmpd" / "edge" / "e3_2025_replication" / "r1"
    out.mkdir(parents=True, exist_ok=True)

    summary_df, outputs, payload = run_full_universe_structural_baseline(
        repo_root=root, year=2025, verify_hash=True
    )
    if int(payload.get("symbol_count", 0)) != 112:
        raise RuntimeError(f"expected exact 112-symbol universe, got {payload.get('symbol_count')}")

    decisions = outputs["decision_points"].copy()
    if decisions.empty:
        raise RuntimeError("structural engine produced zero decision points")
    required = {"symbol", "event_id", "trade_date", "decision_type", "direction", "timestamp_utc"}
    missing = sorted(required.difference(decisions.columns))
    if missing:
        raise RuntimeError(f"decision-point schema missing required columns: {missing}")

    dp4 = decisions.loc[decisions["decision_type"].eq("DP4_FULL_STACK_FIRST_CLEAR")].copy()
    if dp4.empty:
        raise RuntimeError("zero DP4_FULL_STACK_FIRST_CLEAR decision points")

    # Structural-only checks.  Do not join or summarize any outcome fields here.
    dp4["timestamp_utc"] = pd.to_datetime(dp4["timestamp_utc"], utc=True)
    duplicate_keys = int(dp4.duplicated(["symbol", "event_id", "timestamp_utc"]).sum())
    invalid_direction = int((~dp4["direction"].isin(["BULL", "BEAR"])).sum())
    if duplicate_keys or invalid_direction:
        raise RuntimeError(
            f"DP4 integrity failed: duplicate_keys={duplicate_keys} invalid_direction={invalid_direction}"
        )

    symbol_counts = (
        dp4.groupby("symbol", as_index=False)
        .agg(dp4_rows=("event_id", "size"), trade_dates=("trade_date", "nunique"))
        .sort_values("symbol")
    )

    # Persist compact structural artifacts only; no Trade Health outcomes.
    dp4.to_parquet(out / "dp4_structural_population.parquet", index=False)
    symbol_counts.to_csv(out / "dp4_symbol_coverage.csv", index=False)
    summary_df.to_csv(out / "structural_symbol_summary.csv", index=False)

    manifest = {
        "step": "PMPD-EDGE-E3-R1",
        "protocol": PROTOCOL,
        "dataset_version": DATASET,
        "candidate_reference": CANDIDATE,
        "year": 2025,
        "purpose": "Outcome-blind 2025 replication-engine reconstruction and DP4 structural population preflight.",
        "symbol_count": int(payload["symbol_count"]),
        "structural_event_count": int(payload["total_events"]),
        "structural_transition_count": int(payload["total_transitions"]),
        "structural_decision_point_count": int(payload["total_decision_points"]),
        "dp4_rows": int(len(dp4)),
        "dp4_symbols": int(dp4["symbol"].nunique()),
        "dp4_trade_dates": int(pd.Series(dp4["trade_date"]).nunique()),
        "direction_counts": {str(k): int(v) for k, v in dp4["direction"].value_counts().to_dict().items()},
        "duplicate_dp4_keys": duplicate_keys,
        "invalid_direction_rows": invalid_direction,
        "structural_run_fingerprint": payload["run_fingerprint"],
        "outcomes_inspected": False,
        "trade_health_events_computed": False,
        "trade_health_score_fit": False,
        "threshold_search_performed": False,
        "event_taxonomy_retuned": False,
        "v4_modified": False,
        "v5_modified": False,
        "production_rule_authorized": False,
        "next_gate": "Reconcile frozen V5 primary-decision-unit / primary-inference eligibility semantics before outcome-bearing E3 replication."
    }
    (out / "summary.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    artifact_paths = [
        out / "dp4_structural_population.parquet",
        out / "dp4_symbol_coverage.csv",
        out / "structural_symbol_summary.csv",
        out / "summary.json",
    ]
    artifact_manifest = {
        "dataset_version": DATASET,
        "artifacts": [
            {
                "path": str(p.relative_to(root)).replace("\\", "/"),
                "size_bytes": p.stat().st_size,
                "sha256": _sha256(p),
            }
            for p in artifact_paths
        ],
    }
    (out / "artifact_manifest.json").write_text(
        json.dumps(artifact_manifest, indent=2), encoding="utf-8"
    )
    artifact_paths.append(out / "artifact_manifest.json")

    print("PMPD_EDGE_E3_R1_SUMMARY=" + json.dumps(manifest, sort_keys=True, default=str))
    return {
        "status": "PASS",
        "protocol": PROTOCOL,
        "dataset_version": DATASET,
        "output_paths": [str(p.relative_to(root)).replace("\\", "/") for p in artifact_paths],
        "outcomes_inspected": False,
        "research_only": True,
        "v4_modified": False,
        "v5_modified": False,
        "production_rule_authorized": False,
    }
