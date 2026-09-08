from pathlib import Path
import json, hashlib, pandas as pd

ROOT=Path.cwd()
SPEC=ROOT/"docs"/"pmpd"/"specifications"/"2026-08-28_PMPD_V4_PARITY_SPEC_V1.md"
EXPECTED_SPEC_SHA="e40351c02088aa2b7528fd98f5be6c651a010f4b3cc8d62905b5dda8aa0474fb"

print("=== PMPD V5 9N-3A V4 RECONSTRUCTION STATIC CERTIFICATION ===")
assert SPEC.exists(), f"Missing spec {SPEC}"
sha=hashlib.sha256(SPEC.read_bytes()).hexdigest()
print("SPEC_SHA256 =",sha)
print("EXPECTED_SPEC_SHA256 =",EXPECTED_SPEC_SHA)
assert sha==EXPECTED_SPEC_SHA, "Frozen V4 spec hash mismatch"

from v4_parity_engine_v1 import _grade,_profile,_strength_score

# Frozen grade boundary tests.
grade_cases=[
    (97,"A+"),(93,"A"),(90,"A-"),(87,"B+"),(83,"B"),(80,"B-"),
    (77,"C+"),(73,"C"),(70,"C-"),(69.999,"Weak")
]
for score,expected in grade_cases:
    got,_=_grade(score)
    assert got==expected,(score,got,expected)
print("GRADE_BOUNDARIES=PASS")

# Frozen profile precedence / rules.
assert _profile(100,100,50,70,0)=="Explosive"
assert _profile(60,100,60,80,1)=="Controlled Strong"
assert _profile(40,75,65,80,1)=="Efficient Moderate"
assert _profile(60,100,65,80,2)=="Delayed Strong"
assert _profile(20,50,70,80,1)=="Pretty but Weak"
print("PROFILE_RULES=PASS")

# Score component max/reference check.
score=_strength_score(100,100,100,150,0)
print("FULL_REFERENCE_SCORE =",score)
assert abs(score-100.0)<1e-9
print("STRENGTH_SCORE_REFERENCE=PASS")

report={
 "spec_sha256":sha,
 "grade_boundaries":"PASS",
 "profile_rules":"PASS",
 "strength_score_reference":"PASS",
 "tradingview_parity_validated":False,
 "v4_modified":False,
 "v5_modified":False,
 "production_rule_authorized":False
}
rp=ROOT/"pmpd_v5_9n_v4_reconstruction_static_cert_v1.json"
rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("REPORT =",rp)
print("TRADINGVIEW_PARITY_VALIDATED=False")
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_V4_RECONSTRUCTION_STATIC_GATE=PASS")
