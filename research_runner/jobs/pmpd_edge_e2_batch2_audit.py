from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def run(root: Path) -> dict:
    base = root / "research_outputs" / "pmpd" / "edge" / "e2_batch2"
    summary_p = base / "summary.json"
    coverage_p = base / "coverage.csv"
    delay_p = base / "decision_delay.csv"
    schema_p = base / "schema_audit.json"
    paths_p = base / "acceptance_state_paths.parquet"
    for p in [summary_p, coverage_p, delay_p, schema_p, paths_p]:
        if not p.exists():
            raise FileNotFoundError(p)

    summary = json.loads(summary_p.read_text(encoding="utf-8"))
    coverage = pd.read_csv(coverage_p)
    delay = pd.read_csv(delay_p)
    schema = json.loads(schema_p.read_text(encoding="utf-8"))
    paths = pd.read_parquet(paths_p)

    states = ["penetration", "close_acceptance", "hold_acceptance", "retest_acceptance", "failed_acceptance", "reclaim_after_failure"]
    analyzable = paths[paths.get("analyzable", False).fillna(False).astype(bool)].copy() if "analyzable" in paths.columns else paths.iloc[0:0].copy()

    direction = {}
    for d in ["BULL", "BEAR"]:
        g = analyzable[analyzable["direction"].astype(str).str.upper().eq(d)] if len(analyzable) else analyzable
        direction[d] = {
            "events": int(len(g)),
            **{s: int(g[f"{s}_seen"].fillna(False).astype(bool).sum()) if f"{s}_seen" in g.columns else 0 for s in states},
        }

    rvol = {}
    if "opening_rvol_ge_1_5" in analyzable.columns:
        for flag in [False, True]:
            g = analyzable[analyzable["opening_rvol_ge_1_5"].fillna(False).astype(bool).eq(flag)]
            rvol[str(flag).lower()] = {
                "events": int(len(g)),
                **{s: int(g[f"{s}_seen"].fillna(False).astype(bool).sum()) if f"{s}_seen" in g.columns else 0 for s in states},
            }

    audit = {
        "step": "PMPD-EDGE-E2-B2-AUDIT",
        "research_batch": "E2-B2",
        "mechanical_audit_only": True,
        "outcome_comparison_performed": False,
        "summary": summary,
        "coverage": coverage.to_dict(orient="records"),
        "decision_delay": delay.to_dict(orient="records"),
        "schema": {
            "resolved_level_mapping": schema.get("resolved_level_mapping"),
            "boundary_source_counts": schema.get("boundary_source_counts"),
            "missing_cache_symbols": schema.get("missing_cache_symbols"),
            "symbol_errors": schema.get("symbol_errors"),
        },
        "parquet": {
            "rows": int(len(paths)),
            "columns": list(paths.columns),
            "analyzable_rows": int(len(analyzable)),
            "unique_symbols": int(paths["symbol"].nunique()) if "symbol" in paths.columns else None,
            "duplicate_event_keys": int(paths["event_key"].duplicated().sum()) if "event_key" in paths.columns else None,
            "direction_state_counts": direction,
            "opening_rvol_context_state_counts": rvol,
        },
    }

    print("PMPD_EDGE_E2_B2_AUDIT=" + json.dumps(audit, sort_keys=True, default=str))
    out = base / "audit_summary.json"
    out.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    return {
        "status": "PASS",
        "mechanical_audit_only": True,
        "outcome_comparison_performed": False,
        "output_paths": [str(out.relative_to(root))],
        "v4_modified": False,
        "v5_modified": False,
        "production_rule_authorized": False,
    }
