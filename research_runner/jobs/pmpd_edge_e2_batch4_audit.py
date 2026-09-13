from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def run(root: Path) -> dict:
    base = root / "research_outputs" / "pmpd" / "edge" / "e2_batch4"
    files = {
        "summary": base / "summary.json",
        "robustness": base / "robustness.csv",
        "symbols": base / "symbol_concentration.csv",
        "loo": base / "leave_one_symbol_out.csv",
        "rvol": base / "rvol_ge_1_5_robustness.csv",
    }
    for p in files.values():
        if not p.exists():
            raise FileNotFoundError(p)
    summary = json.loads(files["summary"].read_text(encoding="utf-8"))
    robustness = pd.read_csv(files["robustness"])
    symbols = pd.read_csv(files["symbols"])
    loo = pd.read_csv(files["loo"])
    rvol = pd.read_csv(files["rvol"])
    audit = {
        "step": "PMPD-EDGE-E2-B4-AUDIT",
        "mechanical_audit_only": True,
        "summary": summary,
        "robustness_rows": robustness.to_dict(orient="records"),
        "top10_symbols": symbols.head(10).to_dict(orient="records"),
        "loo_min": loo.loc[loo["rate"].idxmin()].to_dict() if len(loo) else None,
        "loo_max": loo.loc[loo["rate"].idxmax()].to_dict() if len(loo) else None,
        "rvol_ge_1_5_rows": rvol.to_dict(orient="records"),
    }
    print("PMPD_EDGE_E2_B4_AUDIT=" + json.dumps(audit, sort_keys=True, default=str))
    out = base / "audit_summary.json"
    out.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    return {"status":"PASS","mechanical_audit_only":True,"output_paths":[str(out.relative_to(root))],"research_only":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False}
