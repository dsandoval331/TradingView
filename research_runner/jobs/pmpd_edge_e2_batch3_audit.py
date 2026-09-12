from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def run(root: Path) -> dict:
    base = root / "research_outputs" / "pmpd" / "edge" / "e2_batch3"
    summary_p = base / "summary.json"
    comp_p = base / "state_comparison.csv"
    rvol_p = base / "opening_rvol_context.csv"
    outcomes_p = base / "state_anchored_outcomes.parquet"
    for p in [summary_p, comp_p, rvol_p, outcomes_p]:
        if not p.exists():
            raise FileNotFoundError(p)

    summary = json.loads(summary_p.read_text(encoding="utf-8"))
    comp = pd.read_csv(comp_p)
    rvol = pd.read_csv(rvol_p)
    outcomes = pd.read_parquet(outcomes_p)

    audit = {
        "step": "PMPD-EDGE-E2-B3-AUDIT",
        "mechanical_audit_only": True,
        "source_step": summary.get("step"),
        "protocol": summary.get("protocol"),
        "favorable_target_pct": summary.get("favorable_target_pct"),
        "adverse_target_pct": summary.get("adverse_target_pct"),
        "bootstrap_reps": summary.get("bootstrap_reps"),
        "bootstrap_seed": summary.get("bootstrap_seed"),
        "comparison_rows": comp.to_dict(orient="records"),
        "opening_rvol_rows": rvol.to_dict(orient="records"),
        "outcomes_rows": int(len(outcomes)),
        "unique_symbols": int(outcomes["symbol"].nunique()) if "symbol" in outcomes.columns else None,
        "duplicate_event_keys": int(outcomes["event_key"].duplicated().sum()) if "event_key" in outcomes.columns else None,
        "guardrails": summary.get("guardrails", {}),
    }
    print("PMPD_EDGE_E2_B3_AUDIT=" + json.dumps(audit, sort_keys=True, default=str))
    out = base / "audit_summary.json"
    out.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    return {
        "status": "PASS",
        "mechanical_audit_only": True,
        "output_paths": [str(out.relative_to(root))],
        "research_only": True,
        "v4_modified": False,
        "v5_modified": False,
        "production_rule_authorized": False,
    }
