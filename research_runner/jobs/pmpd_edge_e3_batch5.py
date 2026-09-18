from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

PROTOCOL = "PMPD_EDGE_E3_TRADE_HEALTH_PROTOCOL_V1"

def run(root: Path) -> dict:
    src = root / "research_outputs/pmpd/edge/e3_batch4"
    required = [
        "event_type_overall.csv","event_type_by_month.csv","event_type_by_direction.csv",
        "event_type_by_symbol.csv","symbol_concentration.csv","trade_event_concentration.csv",
        "robustness_envelope.csv","summary.json"
    ]
    missing=[x for x in required if not (src/x).exists()]
    if missing: raise FileNotFoundError(f"missing E3-B4 artifacts: {missing}")
    b4=json.loads((src/"summary.json").read_text())
    if b4.get("protocol") != PROTOCOL: raise RuntimeError("E3 protocol mismatch")
    integ=b4.get("integrity",{})
    if not integ.get("row_reconciliation_pass") or not integ.get("direction_encoding_pass"):
        raise RuntimeError("E3-B4 integrity gate did not pass")

    overall=pd.read_csv(src/"event_type_overall.csv")
    robust=pd.read_csv(src/"robustness_envelope.csv")
    sym=pd.read_csv(src/"symbol_concentration.csv")
    trade=pd.read_csv(src/"trade_event_concentration.csv")

    out=root/"research_outputs/pmpd/edge/e3_batch5"; out.mkdir(parents=True,exist_ok=True)

    evidence=overall.merge(robust,on=["event_family","event_type"],how="left",suffixes=("_assoc","_robust"))
    evidence.to_csv(out/"e3_evidence_synthesis.csv",index=False)

    replication_design={
      "step":"PMPD-EDGE-E3-B5",
      "protocol":PROTOCOL,
      "purpose":"Freeze replication design after E3-B3 association and E3-B4 robustness/concentration audit; do not fit thresholds or promote production rules.",
      "frozen_event_taxonomy":True,
      "frozen_outcome_definition":{"favorable_first_pct":0.005,"adverse_first_pct":0.005,
        "anchor":"event decision_timestamp_et / price_at_decision","same_minute":"reported separately and excluded from directional first-passage rate"},
      "replication_unit":"event decision timestamp nested within trade, symbol, and trade date",
      "required_replication_checks":[
        "exact event-type and event-family definitions from E3-B1/B2",
        "strict causal availability at decision_timestamp_et",
        "BULL/BEAR direction encoding validation",
        "row/cardinality reconciliation",
        "overall favorable-first association",
        "temporal stability",
        "directional stability",
        "symbol concentration",
        "events-per-trade concentration",
        "same-minute and unresolved outcomes reported separately"
      ],
      "primary_replication_rule":"Evaluate all frozen E3 event types without selecting, dropping, or retuning event definitions based on 2026 development outcomes.",
      "development_evidence_policy":"2026 remains development evidence and cannot authorize production promotion.",
      "promotion_gate":"No Trade Health score, alert, Pine/production rule, or V4/V5 modification until untouched replication is completed and reviewed.",
      "guardrails":{"research_only":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False,
        "trade_health_score_fit":False,"threshold_search_performed":False,"event_taxonomy_retuned":False,"signal_quality_separate":True}
    }
    (out/"replication_design.json").write_text(json.dumps(replication_design,indent=2))

    summary={
      "step":"PMPD-EDGE-E3-B5","protocol":PROTOCOL,
      "b4_integrity":integ,
      "event_types_synthesized":int(overall.event_type.nunique()),
      "event_families_synthesized":int(overall.event_family.nunique()),
      "symbols_in_concentration_audit":int(len(sym)),
      "trades_in_concentration_audit":int(len(trade)),
      "replication_design_frozen":True,
      "guardrails":replication_design["guardrails"],
      "next_step":"Untouched E3 replication dataset selection/materialization requires a consequential data-period decision if no pre-designated untouched period is already governed."
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str))
    outputs=[out/"e3_evidence_synthesis.csv",out/"replication_design.json",out/"summary.json"]
    print("PMPD_EDGE_E3_B5_SUMMARY="+json.dumps(summary,sort_keys=True,default=str))
    return {"status":"PASS","protocol":PROTOCOL,"output_paths":[str(p.relative_to(root)) for p in outputs],
      "research_only":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False}
