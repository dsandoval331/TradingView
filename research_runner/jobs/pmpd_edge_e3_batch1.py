from __future__ import annotations

import json
from pathlib import Path

PROTOCOL = "PMPD_EDGE_E3_TRADE_HEALTH_PROTOCOL_V1"


def run(root: Path) -> dict:
    protocol = {
        "step": "PMPD-EDGE-E3-B1",
        "protocol": PROTOCOL,
        "purpose": "Outcome-blind freeze of causal post-entry Trade Health event taxonomy and measurement semantics before outcome association testing.",
        "entry_anchor": {
            "primary": "DP4_FULL_STACK_FIRST_CLEAR",
            "reason": "Preserve the frozen V5 structural anchor; E2 did not promote a replacement acceptance entry rule.",
            "signal_quality_separate": True,
            "trade_health_starts_after_entry_anchor": True,
        },
        "event_families": {
            "level_behavior": ["STACK_HOLD", "STACK_FAILURE", "STACK_RECLAIM", "FAILED_CONTINUATION"],
            "vwap": ["VWAP_TEST", "VWAP_PENETRATION", "VWAP_REJECTION", "VWAP_ACCEPTANCE", "VWAP_RECLAIM"],
            "structure": ["FAVORABLE_HIGHER_LOW", "FAVORABLE_LOWER_HIGH", "ADVERSE_HIGHER_LOW", "ADVERSE_LOWER_HIGH", "RECOVERY_STRUCTURE"],
            "momentum": ["MOMENTUM_SUPPORT", "MOMENTUM_DETERIORATION", "MOMENTUM_PRICE_DIVERGENCE"],
        },
        "causal_semantics": {
            "completed_5m_close_required": ["STACK_HOLD", "STACK_FAILURE", "STACK_RECLAIM", "FAILED_CONTINUATION", "VWAP_REJECTION", "VWAP_ACCEPTANCE", "VWAP_RECLAIM", "FAVORABLE_HIGHER_LOW", "FAVORABLE_LOWER_HIGH", "ADVERSE_HIGHER_LOW", "ADVERSE_LOWER_HIGH", "RECOVERY_STRUCTURE", "MOMENTUM_SUPPORT", "MOMENTUM_DETERIORATION", "MOMENTUM_PRICE_DIVERGENCE"],
            "intrabar_touch_allowed_but_not_decision": ["VWAP_TEST", "VWAP_PENETRATION"],
            "decision_time": "first timestamp at which all defining information is observable",
            "no_future_path_leakage": True,
        },
        "measurements_per_event": [
            "event_key", "symbol", "trade_date", "direction", "event_type", "event_family",
            "decision_timestamp_et", "minutes_from_dp4", "price_at_decision",
            "directional_return_from_dp4_pct", "mfe_so_far_pct", "mae_so_far_pct",
            "stack_distance_pct", "stack_distance_atr14", "vwap_distance_pct",
            "opening_rvol_ge_1_5_context"
        ],
        "trade_health_role": {
            "supportive_events": ["STACK_HOLD", "STACK_RECLAIM", "VWAP_REJECTION", "VWAP_RECLAIM", "FAVORABLE_HIGHER_LOW", "FAVORABLE_LOWER_HIGH", "RECOVERY_STRUCTURE", "MOMENTUM_SUPPORT"],
            "warning_events": ["STACK_FAILURE", "FAILED_CONTINUATION", "VWAP_ACCEPTANCE", "ADVERSE_HIGHER_LOW", "ADVERSE_LOWER_HIGH", "MOMENTUM_DETERIORATION", "MOMENTUM_PRICE_DIVERGENCE"],
            "labels_are_research_hypotheses_not_proven_actions": True
        },
        "e2_carry_forward": {
            "reclaim_after_failure_plus_opening_rvol_ge_1_5": "context_only",
            "may_be_measured_not_promoted": True,
            "threshold_retuning_allowed": False
        },
        "guardrails": {
            "research_only": True,
            "2026_development_evidence": True,
            "v4_modified": False,
            "v5_modified": False,
            "production_rule_authorized": False,
            "outcomes_inspected_in_b1": False,
            "trade_health_score_fit_in_b1": False,
            "threshold_search_in_b1": False,
            "signal_quality_and_trade_health_kept_separate": True
        },
        "next_batch": "E3-B2 construct timestamped Trade Health event-path dataset and certify causal availability/coverage before outcome association testing."
    }
    out = root / "research_outputs" / "pmpd" / "edge" / "e3_batch1"
    out.mkdir(parents=True, exist_ok=True)
    p = out / "trade_health_protocol.json"
    p.write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    return {"status":"PASS","protocol":PROTOCOL,"output_paths":[str(p.relative_to(root))],"research_only":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False}
