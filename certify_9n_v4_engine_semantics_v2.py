from pathlib import Path
import hashlib, math, json
import numpy as np

from v4_parity_engine_v2 import (
    EXPECTED_FROZEN_PINE_SHA256,
    MAX_PEN_POINTS, MAX_BODY_POINTS, MAX_CLOSE_POINTS, MAX_RANGE_POINTS, MAX_SPEED_POINTS,
    penetration_score, body_score, close_score, range_score, speed_score, grade,
    v4_profile, PROFILE_EXPLOSIVE, PROFILE_CONTROLLED, PROFILE_EFFICIENT,
    PROFILE_DELAYED, PROFILE_PRETTY_WEAK, PROFILE_UNCLASSIFIED,
    priority_code, PRIORITY_PRIME, PRIORITY_CONDITIONAL, PRIORITY_RESEARCH,
    PRIORITY_LOW, PRIORITY_OBSERVE, BUCKET_A, BUCKET_B, BUCKET_C, BUCKET_WEAK,
    trade_type, production_tqs, production_confidence, pine_rma
)

ROOT=Path.cwd()
print("=== PMPD V5 9N-3E V4 ENGINE SEMANTIC CERTIFICATION ===")

# 1. Frozen score model reference.
full = (
    penetration_score(100.0) +
    body_score(100.0) +
    close_score(100.0) +
    range_score(150.0) +
    speed_score(0)
)
assert abs(full - 100.0) < 1e-12
assert (MAX_PEN_POINTS,MAX_BODY_POINTS,MAX_CLOSE_POINTS,MAX_RANGE_POINTS,MAX_SPEED_POINTS)==(40.0,15.0,15.0,25.0,5.0)
print("SCORE_MODEL=PASS")
print("FULL_REFERENCE_SCORE =", full)

# 2. Grade boundaries.
checks = [(97,"A+"),(93,"A"),(90,"A-"),(87,"B+"),(83,"B"),(80,"B-"),
          (77,"C+"),(73,"C"),(70,"C-"),(69.999,"Weak")]
for x, exp in checks:
    assert grade(x)==exp, (x,grade(x),exp)
print("GRADE_BOUNDARIES=PASS")

# 3. V4 profile precedence and representative boundaries.
assert v4_profile(100,100,50,70,0)==PROFILE_EXPLOSIVE
assert v4_profile(60,100,60,80,0)==PROFILE_CONTROLLED
assert v4_profile(40,75,65,80,0)==PROFILE_EFFICIENT
assert v4_profile(60,100,65,80,2)==PROFILE_DELAYED
assert v4_profile(39,74,70,80,1)==PROFILE_PRETTY_WEAK
assert v4_profile(10,20,20,20,4)==PROFILE_UNCLASSIFIED
print("V4_PROFILE_RULES=PASS")

# 4. Frozen priority matrix/fallbacks.
assert priority_code(BUCKET_A, PROFILE_EXPLOSIVE)==PRIORITY_PRIME
assert priority_code(BUCKET_B, PROFILE_CONTROLLED)==PRIORITY_CONDITIONAL
assert priority_code(BUCKET_C, PROFILE_EFFICIENT)==PRIORITY_CONDITIONAL
assert priority_code(BUCKET_A, PROFILE_DELAYED)==PRIORITY_RESEARCH
assert priority_code(BUCKET_WEAK, PROFILE_PRETTY_WEAK)==PRIORITY_LOW
assert priority_code(BUCKET_A, PROFILE_UNCLASSIFIED)==PRIORITY_OBSERVE
assert priority_code(BUCKET_A, PROFILE_CONTROLLED)==PRIORITY_OBSERVE
print("PRIORITY_MATRIX=PASS")

# 5. Trade type / TQS / confidence.
assert trade_type(BUCKET_A, PROFILE_EXPLOSIVE)=="EXPANSION"
assert trade_type(BUCKET_B, PROFILE_CONTROLLED)=="SCALP"
assert trade_type(BUCKET_A, PROFILE_DELAYED)=="EXPANSION"
assert abs(production_tqs(BUCKET_A, PROFILE_EXPLOSIVE)-42.7)<1e-12
assert production_confidence(BUCKET_C, PROFILE_CONTROLLED)=="MOD-HIGH"
assert math.isnan(production_tqs(BUCKET_A, PROFILE_UNCLASSIFIED))
assert production_confidence(BUCKET_A, PROFILE_UNCLASSIFIED)=="INSUFFICIENT"
print("PRODUCTION_LOOKUP_MATRIX=PASS")

# 6. Pine RMA semantics: SMA seed then Wilder recursion.
x=np.array([1.,2.,3.,4.,5.,6.])
r=pine_rma(x,3)
# seed at index 2 = 2; index 3 = 2 + (4-2)/3
assert np.isnan(r[0]) and np.isnan(r[1])
assert abs(r[2]-2.0)<1e-12
assert abs(r[3]-(8/3))<1e-12
assert abs(r[4]-(31/9))<1e-12
print("PINE_RMA_REFERENCE=PASS")

# 7. Verify recovered Pine source SHA when present.
pine_candidates=[
    ROOT/"PM_PD_Breakout_V4_8H7_Parity_Capture_FULL.pine",
    ROOT/"PM_PD_Breakout_V4_8H7_Parity_Capture.pine",
]
pine=next((p for p in pine_candidates if p.exists()),None)
pine_sha=None
if pine:
    pine_sha=hashlib.sha256(pine.read_bytes()).hexdigest()
    assert pine_sha==EXPECTED_FROZEN_PINE_SHA256,(pine_sha,EXPECTED_FROZEN_PINE_SHA256)
    print("FROZEN_PINE_SHA=PASS")
else:
    print("FROZEN_PINE_SHA=NOT_CHECKED_SOURCE_NOT_LOCAL")

report={
    "expected_frozen_pine_sha256":EXPECTED_FROZEN_PINE_SHA256,
    "observed_pine_sha256":pine_sha,
    "score_model":"PASS",
    "grade_boundaries":"PASS",
    "v4_profile_rules":"PASS",
    "priority_matrix":"PASS",
    "production_lookup_matrix":"PASS",
    "pine_rma_reference":"PASS",
    "tradingview_parity_validated":False,
    "v4_modified":False,
    "v5_modified":False,
    "production_rule_authorized":False,
}
rp=ROOT/"pmpd_v5_9n_3e_v4_engine_semantic_cert_v2.json"
rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("REPORT =",rp)
print("TRADINGVIEW_PARITY_VALIDATED=False")
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_3E_V4_ENGINE_SEMANTIC_GATE=PASS")
