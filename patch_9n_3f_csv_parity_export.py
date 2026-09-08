from pathlib import Path
import hashlib, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path.cwd()
SOURCE = ROOT / "PM_PD_Breakout_V4_8H7_Parity_Capture_FULL.pine"
OUTPUT = ROOT / "PM_PD_Breakout_V4_9N_3F_CSV_Parity_Export.pine"
EXPECTED_SHA = "79b9d80f0ec2c254bd69607ff626c2007ae7e617018d984f083ba2a25e7ba681"

if not SOURCE.exists():
    raise SystemExit(f"Missing source: {SOURCE}")

raw = SOURCE.read_bytes()
sha = hashlib.sha256(raw).hexdigest()
print("=== PMPD V5 9N-3F MACHINE-READABLE PINE CSV EXPORT PATCH ===")
print("SOURCE =", SOURCE)
print("SOURCE_SHA256 =", sha)
if sha != EXPECTED_SHA:
    raise SystemExit(f"Frozen source SHA mismatch: {sha} != {EXPECTED_SHA}")
print("FROZEN_SOURCE_SHA=PASS")

text = raw.decode("utf-8", errors="ignore")
marker = """//=============================================================================
// END 8H-7B-2K PARITY CLASSIFICATION CAPTURE + SYMBOL GUARD
//============================================================================="""

if marker not in text:
    raise SystemExit("Could not find parity-capture end marker.")
if "9N-3F MACHINE-READABLE CSV PARITY EXPORT" in text:
    raise SystemExit("Export block already present; refusing duplicate patch.")

block = r"""
//=============================================================================
// 9N-3F MACHINE-READABLE CSV PARITY EXPORT
//=============================================================================
// Additive/read-only. Original frozen V4 logic remains unchanged.
// String encodings are export-only and are NOT model logic.
//
// Grade: Weak=0,C-=1,C=2,C+=3,B-=4,B=5,B+=6,A-=7,A=8,A+=9
// Trade Type: OBSERVE=0, SCALP=1, EXPANSION=2
// Confidence: INSUFFICIENT=0, LOW=1, MODERATE=2, MOD-HIGH=3, HIGH=4
//=============================================================================

f_9n3fGradeCode(string g) =>
    int result = 0
    if g == "C-"
        result := 1
    else if g == "C"
        result := 2
    else if g == "C+"
        result := 3
    else if g == "B-"
        result := 4
    else if g == "B"
        result := 5
    else if g == "B+"
        result := 6
    else if g == "A-"
        result := 7
    else if g == "A"
        result := 8
    else if g == "A+"
        result := 9
    result

f_9n3fTradeTypeCode(string value) =>
    value == "SCALP" ? 1 : value == "EXPANSION" ? 2 : 0

f_9n3fConfidenceCode(string value) =>
    value == "LOW" ? 1 :
     value == "MODERATE" ? 2 :
     value == "MOD-HIGH" ? 3 :
     value == "HIGH" ? 4 : 0

int n3fSignalCount = array.size(parityDirection)
int n3fDetailIndex = parityDetailSignal - 1
bool n3fHasSignal =
     parityCaptureAllowed and
     n3fDetailIndex >= 0 and
     n3fDetailIndex < n3fSignalCount

int n3fGradeBucket = n3fHasSignal ? f_gradeBucket(array.get(parityGrade, n3fDetailIndex)) : BUCKET_WEAK
int n3fProfile = n3fHasSignal ? array.get(parityProfile, n3fDetailIndex) : PROFILE_UNCLASSIFIED
int n3fPriority = n3fHasSignal ? f_priorityCode(n3fGradeBucket, n3fProfile) : PRIORITY_OBSERVE
string n3fTradeType = n3fHasSignal ? f_tradeType(n3fGradeBucket, n3fProfile) : "OBSERVE"
float n3fTQS = n3fHasSignal ? f_productionTQS(n3fGradeBucket, n3fProfile) : na
string n3fConfidence = n3fHasSignal ? f_productionConfidence(n3fGradeBucket, n3fProfile) : "INSUFFICIENT"

plot(parityCaptureAllowed ? (parityDateSeen ? 1.0 : 0.0) : na, "PMPD_PARITY_DATE_SEEN", display = display.none)
plot(parityCaptureAllowed ? float(n3fSignalCount) : na, "PMPD_PARITY_SIGNAL_COUNT", display = display.none)

plot(n3fHasSignal ? float(array.get(parityDirection, n3fDetailIndex)) : na, "PMPD_PARITY_DIRECTION", display = display.none)
plot(n3fHasSignal ? float(array.get(paritySignalTime, n3fDetailIndex)) : na, "PMPD_PARITY_SIGNAL_TIME_MS", display = display.none)
plot(n3fHasSignal ? array.get(parityReference, n3fDetailIndex) : na, "PMPD_PARITY_REFERENCE", display = display.none)

plot(parityCaptureAllowed ? parityDatePMH : na, "PMPD_PARITY_DATE_PMH", display = display.none)
plot(parityCaptureAllowed ? parityDatePML : na, "PMPD_PARITY_DATE_PML", display = display.none)
plot(parityCaptureAllowed ? parityDatePDH : na, "PMPD_PARITY_DATE_PDH", display = display.none)
plot(parityCaptureAllowed ? parityDatePDL : na, "PMPD_PARITY_DATE_PDL", display = display.none)

plot(n3fHasSignal ? array.get(parityPMH, n3fDetailIndex) : na, "PMPD_PARITY_PMH", display = display.none)
plot(n3fHasSignal ? array.get(parityPML, n3fDetailIndex) : na, "PMPD_PARITY_PML", display = display.none)
plot(n3fHasSignal ? array.get(parityPDH, n3fDetailIndex) : na, "PMPD_PARITY_PDH", display = display.none)
plot(n3fHasSignal ? array.get(parityPDL, n3fDetailIndex) : na, "PMPD_PARITY_PDL", display = display.none)
plot(n3fHasSignal ? array.get(parityFinalLevel, n3fDetailIndex) : na, "PMPD_PARITY_FINAL_LEVEL", display = display.none)

plot(n3fHasSignal ? array.get(parityATR, n3fDetailIndex) : na, "PMPD_PARITY_ATR", display = display.none)
plot(n3fHasSignal ? array.get(parityPen, n3fDetailIndex) : na, "PMPD_PARITY_PEN_PCT_ATR", display = display.none)
plot(n3fHasSignal ? array.get(parityBody, n3fDetailIndex) : na, "PMPD_PARITY_BODY_PCT", display = display.none)
plot(n3fHasSignal ? array.get(parityRangeATR, n3fDetailIndex) : na, "PMPD_PARITY_RANGE_PCT_ATR", display = display.none)
plot(n3fHasSignal ? array.get(parityClosePos, n3fDetailIndex) : na, "PMPD_PARITY_CLOSE_POS_PCT", display = display.none)
plot(n3fHasSignal ? float(array.get(parityBarsToConfirm, n3fDetailIndex)) : na, "PMPD_PARITY_BARS_TO_CONFIRM", display = display.none)

plot(n3fHasSignal ? array.get(parityTotalScore, n3fDetailIndex) : na, "PMPD_PARITY_TOTAL_SCORE", display = display.none)
plot(n3fHasSignal ? float(f_9n3fGradeCode(array.get(parityGrade, n3fDetailIndex))) : na, "PMPD_PARITY_GRADE_CODE", display = display.none)
plot(n3fHasSignal ? float(n3fProfile) : na, "PMPD_PARITY_PROFILE_CODE", display = display.none)
plot(n3fHasSignal ? float(n3fPriority) : na, "PMPD_PARITY_PRIORITY_CODE", display = display.none)
plot(n3fHasSignal ? float(f_9n3fTradeTypeCode(n3fTradeType)) : na, "PMPD_PARITY_TRADE_TYPE_CODE", display = display.none)
plot(n3fHasSignal ? n3fTQS : na, "PMPD_PARITY_TQS", display = display.none)
plot(n3fHasSignal ? float(f_9n3fConfidenceCode(n3fConfidence)) : na, "PMPD_PARITY_CONFIDENCE_CODE", display = display.none)

plot(n3fHasSignal ? (n3fPriority >= PRIORITY_CONDITIONAL ? 1.0 : 0.0) : na, "PMPD_PARITY_DEFAULT_CONDITIONAL_PLUS_ELIGIBLE", display = display.none)
plot(n3fHasSignal ? (f_priorityAlertPass(n3fPriority) ? 1.0 : 0.0) : na, "PMPD_PARITY_CURRENT_ALERT_PASS", display = display.none)

plot(n3fHasSignal ? array.get(parityPenScore, n3fDetailIndex) : na, "PMPD_PARITY_PEN_SCORE", display = display.none)
plot(n3fHasSignal ? array.get(parityBodyScore, n3fDetailIndex) : na, "PMPD_PARITY_BODY_SCORE", display = display.none)
plot(n3fHasSignal ? array.get(parityCloseScore, n3fDetailIndex) : na, "PMPD_PARITY_CLOSE_SCORE", display = display.none)
plot(n3fHasSignal ? array.get(parityRangeScore, n3fDetailIndex) : na, "PMPD_PARITY_RANGE_SCORE", display = display.none)
plot(n3fHasSignal ? array.get(paritySpeedScore, n3fDetailIndex) : na, "PMPD_PARITY_SPEED_SCORE", display = display.none)

plot(n3fHasSignal ? (array.get(parityDirectionalPass, n3fDetailIndex) ? 1.0 : 0.0) : na, "PMPD_PARITY_DIRECTIONAL_PASS", display = display.none)
plot(n3fHasSignal ? (array.get(parityPenPass, n3fDetailIndex) ? 1.0 : 0.0) : na, "PMPD_PARITY_PEN_PASS", display = display.none)
plot(n3fHasSignal ? (array.get(parityBodyPass, n3fDetailIndex) ? 1.0 : 0.0) : na, "PMPD_PARITY_BODY_PASS", display = display.none)
plot(n3fHasSignal ? (array.get(parityRangePass, n3fDetailIndex) ? 1.0 : 0.0) : na, "PMPD_PARITY_RANGE_PASS", display = display.none)
plot(n3fHasSignal ? (array.get(parityClosePass, n3fDetailIndex) ? 1.0 : 0.0) : na, "PMPD_PARITY_CLOSE_PASS", display = display.none)

plot(n3fHasSignal ? float(array.get(parityFirstOutcome, n3fDetailIndex)) : na, "PMPD_PARITY_FIRST_OUTCOME_CODE", display = display.none)
plot(n3fHasSignal ? array.get(parityMFE, n3fDetailIndex) : na, "PMPD_PARITY_MFE_PCT", display = display.none)
plot(n3fHasSignal ? array.get(parityMAE, n3fDetailIndex) : na, "PMPD_PARITY_MAE_PCT", display = display.none)

//=============================================================================
// END 9N-3F MACHINE-READABLE CSV PARITY EXPORT
//=============================================================================
"""

patched = text.replace(marker, marker + "\n" + block)
OUTPUT.write_text(patched, encoding="utf-8")
print("OUTPUT =", OUTPUT)
print("OUTPUT_SHA256 =", hashlib.sha256(OUTPUT.read_bytes()).hexdigest())
print("ORIGINAL_V4_MODIFIED=False")
print("PATCHED_COPY_ONLY=True")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_3F_PATCH_GATE=PASS")
