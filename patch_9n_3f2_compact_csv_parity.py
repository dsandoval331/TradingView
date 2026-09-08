from pathlib import Path
import hashlib, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path.cwd()
SOURCE = ROOT / "PM_PD_Breakout_V4_8H7_Parity_Capture_FULL.pine"
OUTPUT = ROOT / "PM_PD_Breakout_V4_9N_3F2_COMPACT_CSV_Parity_Export.pine"
EXPECTED_SHA = "79b9d80f0ec2c254bd69607ff626c2007ae7e617018d984f083ba2a25e7ba681"

raw = SOURCE.read_bytes()
sha = hashlib.sha256(raw).hexdigest()
print("=== PMPD V5 9N-3F2 COMPACT MACHINE-READABLE PARITY COPY ===")
print("SOURCE =", SOURCE)
print("SOURCE_SHA256 =", sha)
if sha != EXPECTED_SHA:
    raise SystemExit(f"Frozen source SHA mismatch: {sha} != {EXPECTED_SHA}")
print("FROZEN_SOURCE_SHA=PASS")

text = raw.decode("utf-8", errors="ignore")
end_marker = "//=============================================================================\\n// END 8H-7B-2K PARITY CLASSIFICATION CAPTURE + SYMBOL GUARD\\n//============================================================================="
pos = text.find(end_marker)
if pos < 0:
    raise SystemExit("Could not locate parity-capture end marker.")

prefix = text[:pos + len(end_marker)]
old_title = 'indicator("PM + PD Breakout Monitor - V4 8H-7 Parity Capture",'
new_title = 'indicator("PM + PD V4 9N-3F2 COMPACT CSV PARITY",'
if old_title in prefix:
    prefix = prefix.replace(old_title, new_title, 1)

export = r'''
//=============================================================================
// 9N-3F2 COMPACT MACHINE-READABLE CSV PARITY EXPORT
//=============================================================================
// READ-ONLY RESEARCH COPY. Frozen source retained through parity capture.
// Downstream analytics/display omitted only to stay below compiler limits.
//=============================================================================

f_9n3f2GradeCode(string g) =>
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

f_9n3f2TradeTypeCode(string value) =>
    value == "SCALP" ? 1 : value == "EXPANSION" ? 2 : 0

f_9n3f2ConfidenceCode(string value) =>
    value == "LOW" ? 1 :
     value == "MODERATE" ? 2 :
     value == "MOD-HIGH" ? 3 :
     value == "HIGH" ? 4 : 0

int n3f2SignalCount = array.size(parityDirection)
int n3f2DetailIndex = parityDetailSignal - 1
bool n3f2HasSignal = parityCaptureAllowed and n3f2DetailIndex >= 0 and n3f2DetailIndex < n3f2SignalCount

int n3f2GradeBucket = n3f2HasSignal ? f_gradeBucket(array.get(parityGrade, n3f2DetailIndex)) : BUCKET_WEAK
int n3f2Profile = n3f2HasSignal ? array.get(parityProfile, n3f2DetailIndex) : PROFILE_UNCLASSIFIED
int n3f2Priority = n3f2HasSignal ? f_priorityCode(n3f2GradeBucket, n3f2Profile) : PRIORITY_OBSERVE
string n3f2TradeType = n3f2HasSignal ? f_tradeType(n3f2GradeBucket, n3f2Profile) : "OBSERVE"
float n3f2TQS = n3f2HasSignal ? f_productionTQS(n3f2GradeBucket, n3f2Profile) : na
string n3f2Confidence = n3f2HasSignal ? f_productionConfidence(n3f2GradeBucket, n3f2Profile) : "INSUFFICIENT"

plot(parityCaptureAllowed ? (parityDateSeen ? 1.0 : 0.0) : na, "PMPD_PARITY_DATE_SEEN", display = display.none)
plot(parityCaptureAllowed ? float(n3f2SignalCount) : na, "PMPD_PARITY_SIGNAL_COUNT", display = display.none)
plot(n3f2HasSignal ? float(array.get(parityDirection, n3f2DetailIndex)) : na, "PMPD_PARITY_DIRECTION", display = display.none)
plot(n3f2HasSignal ? float(array.get(paritySignalTime, n3f2DetailIndex)) : na, "PMPD_PARITY_SIGNAL_TIME_MS", display = display.none)
plot(n3f2HasSignal ? array.get(parityReference, n3f2DetailIndex) : na, "PMPD_PARITY_REFERENCE", display = display.none)
plot(parityCaptureAllowed ? parityDatePMH : na, "PMPD_PARITY_DATE_PMH", display = display.none)
plot(parityCaptureAllowed ? parityDatePML : na, "PMPD_PARITY_DATE_PML", display = display.none)
plot(parityCaptureAllowed ? parityDatePDH : na, "PMPD_PARITY_DATE_PDH", display = display.none)
plot(parityCaptureAllowed ? parityDatePDL : na, "PMPD_PARITY_DATE_PDL", display = display.none)
plot(n3f2HasSignal ? array.get(parityFinalLevel, n3f2DetailIndex) : na, "PMPD_PARITY_FINAL_LEVEL", display = display.none)
plot(n3f2HasSignal ? array.get(parityATR, n3f2DetailIndex) : na, "PMPD_PARITY_ATR", display = display.none)
plot(n3f2HasSignal ? array.get(parityPen, n3f2DetailIndex) : na, "PMPD_PARITY_PEN_PCT_ATR", display = display.none)
plot(n3f2HasSignal ? array.get(parityBody, n3f2DetailIndex) : na, "PMPD_PARITY_BODY_PCT", display = display.none)
plot(n3f2HasSignal ? array.get(parityRangeATR, n3f2DetailIndex) : na, "PMPD_PARITY_RANGE_PCT_ATR", display = display.none)
plot(n3f2HasSignal ? array.get(parityClosePos, n3f2DetailIndex) : na, "PMPD_PARITY_CLOSE_POS_PCT", display = display.none)
plot(n3f2HasSignal ? float(array.get(parityBarsToConfirm, n3f2DetailIndex)) : na, "PMPD_PARITY_BARS_TO_CONFIRM", display = display.none)
plot(n3f2HasSignal ? array.get(parityTotalScore, n3f2DetailIndex) : na, "PMPD_PARITY_TOTAL_SCORE", display = display.none)
plot(n3f2HasSignal ? float(f_9n3f2GradeCode(array.get(parityGrade, n3f2DetailIndex))) : na, "PMPD_PARITY_GRADE_CODE", display = display.none)
plot(n3f2HasSignal ? float(n3f2Profile) : na, "PMPD_PARITY_PROFILE_CODE", display = display.none)
plot(n3f2HasSignal ? float(n3f2Priority) : na, "PMPD_PARITY_PRIORITY_CODE", display = display.none)
plot(n3f2HasSignal ? float(f_9n3f2TradeTypeCode(n3f2TradeType)) : na, "PMPD_PARITY_TRADE_TYPE_CODE", display = display.none)
plot(n3f2HasSignal ? n3f2TQS : na, "PMPD_PARITY_TQS", display = display.none)
plot(n3f2HasSignal ? float(f_9n3f2ConfidenceCode(n3f2Confidence)) : na, "PMPD_PARITY_CONFIDENCE_CODE", display = display.none)
plot(n3f2HasSignal ? (n3f2Priority >= PRIORITY_CONDITIONAL ? 1.0 : 0.0) : na, "PMPD_PARITY_DEFAULT_CONDITIONAL_PLUS_ELIGIBLE", display = display.none)
plot(n3f2HasSignal ? array.get(parityPenScore, n3f2DetailIndex) : na, "PMPD_PARITY_PEN_SCORE", display = display.none)
plot(n3f2HasSignal ? array.get(parityBodyScore, n3f2DetailIndex) : na, "PMPD_PARITY_BODY_SCORE", display = display.none)
plot(n3f2HasSignal ? array.get(parityCloseScore, n3f2DetailIndex) : na, "PMPD_PARITY_CLOSE_SCORE", display = display.none)
plot(n3f2HasSignal ? array.get(parityRangeScore, n3f2DetailIndex) : na, "PMPD_PARITY_RANGE_SCORE", display = display.none)
plot(n3f2HasSignal ? array.get(paritySpeedScore, n3f2DetailIndex) : na, "PMPD_PARITY_SPEED_SCORE", display = display.none)
plot(n3f2HasSignal ? float(array.get(parityFirstOutcome, n3f2DetailIndex)) : na, "PMPD_PARITY_FIRST_OUTCOME_CODE", display = display.none)
plot(n3f2HasSignal ? array.get(parityMFE, n3f2DetailIndex) : na, "PMPD_PARITY_MFE_PCT", display = display.none)
plot(n3f2HasSignal ? array.get(parityMAE, n3f2DetailIndex) : na, "PMPD_PARITY_MAE_PCT", display = display.none)
'''

OUTPUT.write_text(prefix + "\\n" + export + "\\n", encoding="utf-8")

print("OUTPUT =", OUTPUT)
print("OUTPUT_SHA256 =", hashlib.sha256(OUTPUT.read_bytes()).hexdigest())
print("OUTPUT_LINE_COUNT =", len(OUTPUT.read_text(encoding="utf-8").splitlines()))
print("TRUNCATION_POINT=END_EXISTING_PARITY_CAPTURE")
print("DOWNSTREAM_ANALYTICS_DISPLAY_REMOVED=True")
print("ORIGINAL_V4_MODIFIED=False")
print("PATCHED_COPY_ONLY=True")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("TRADINGVIEW_PARITY_VALIDATED=False")
print("9N_3F2_COMPACT_PATCH_GATE=PASS")
