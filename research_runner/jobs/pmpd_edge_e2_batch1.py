from __future__ import annotations

import json
from pathlib import Path

PROTOCOL = "PMPD_EDGE_E2_ACCEPTANCE_PROTOCOL_V1"

# E2-B1 is intentionally outcome-blind. It freezes measurement semantics before
# any acceptance state is compared with favorable/adverse outcomes.
TAXONOMY = [
    {
        "state": "PENETRATION_ONLY",
        "definition": "Price trades beyond the directional full-stack boundary after DP4, but no qualifying completed 5m close beyond the boundary has yet occurred.",
        "decision_time": "first qualifying trade beyond boundary",
    },
    {
        "state": "CLOSE_ACCEPTANCE",
        "definition": "First completed 5m bar after DP4 closes beyond the directional full-stack boundary.",
        "decision_time": "qualifying 5m bar close",
    },
    {
        "state": "HOLD_ACCEPTANCE",
        "definition": "After CLOSE_ACCEPTANCE, the next completed 5m bar also closes beyond the same directional boundary without an intervening completed-bar close back inside the stack.",
        "decision_time": "second qualifying completed 5m close",
    },
    {
        "state": "RETEST_ACCEPTANCE",
        "definition": "After CLOSE_ACCEPTANCE, price revisits/touches the broken boundary and subsequently produces a completed 5m close back on the breakout side before a completed 5m close through the boundary to the inside.",
        "decision_time": "post-retest qualifying completed 5m close",
    },
    {
        "state": "FAILED_ACCEPTANCE",
        "definition": "After CLOSE_ACCEPTANCE, a completed 5m bar closes back through the broken boundary to the inside of the stack before HOLD_ACCEPTANCE or RETEST_ACCEPTANCE is established.",
        "decision_time": "first qualifying failed completed 5m close",
    },
    {
        "state": "RECLAIM_AFTER_FAILURE",
        "definition": "After FAILED_ACCEPTANCE, a later completed 5m bar closes again beyond the directional boundary during the same RTH session.",
        "decision_time": "qualifying reclaim 5m close",
    },
]

MEASUREMENTS = {
    "boundary": "DP4_FULL_STACK_FIRST_CLEAR directional full-stack boundary; Bull=max(PMH,AHH,PDH), Bear=min(PML,AHL,PDL).",
    "clock": "America/New_York; RTH only; no overnight carry.",
    "confirmation_bar": "Completed 5-minute bars. Intrabar highs/lows may establish touch/penetration, but acceptance/failure states require completed closes.",
    "distance": "Directional close distance beyond boundary recorded as raw percent and, where available without lookahead, normalized by prior-completed 5m ATR14.",
    "time_beyond": "Elapsed minutes from DP4 to each state plus count of completed 5m closes beyond boundary.",
    "retest_touch": "Intrabar touch/cross of the boundary after CLOSE_ACCEPTANCE; classification is not known until the subsequent completed-bar decision.",
    "vwap": "Record contemporaneous VWAP-side/distance only at each state decision time; do not use future VWAP behavior to classify entry acceptance.",
    "context": "Carry frozen opening RVOL >=1.5 as research context only; do not retune it and do not require it for acceptance-state membership.",
}

GUARDRAILS = [
    "Research-only; no Pine production rule authorized.",
    "Frozen V4 and frozen V5 are not modified.",
    "2026 evidence already exposed to PMPD-EDGE is development evidence, not untouched OOS.",
    "E2 entry/acceptance variables must be observable by the stated decision_time.",
    "Post-entry Trade Health variables remain reserved for E3 and must not define E2 entry acceptance.",
    "No acceptance threshold or taxonomy state may be added/removed after outcome comparison without declaring a new protocol version.",
    "No Strength Score, inherited V4 weights, or outcome-fitted score is introduced in E2-B1.",
]


def run(root: Path) -> dict:
    out = root / "research_outputs" / "pmpd" / "edge" / "e2_batch1"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "step": "PMPD-EDGE-E2-B1",
        "protocol": PROTOCOL,
        "purpose": "Outcome-blind freeze of penetration-versus-acceptance taxonomy and measurement semantics before E2 outcome testing.",
        "entry_anchor": "DP4_FULL_STACK_FIRST_CLEAR",
        "taxonomy": TAXONOMY,
        "measurements": MEASUREMENTS,
        "guardrails": GUARDRAILS,
        "next_batch": "E2-B2 constructs the state-path dataset under this frozen protocol, audits causal availability/coverage, and only then performs pre-specified outcome comparisons.",
    }
    p = out / "acceptance_protocol.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "status": "PASS",
        "protocol": PROTOCOL,
        "states_frozen": len(TAXONOMY),
        "output_paths": [str(p.relative_to(root))],
        "research_only": True,
        "v4_modified": False,
        "v5_modified": False,
        "production_rule_authorized": False,
    }
