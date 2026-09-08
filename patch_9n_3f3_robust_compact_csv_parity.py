from pathlib import Path
import hashlib, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path.cwd()
SOURCE = ROOT / "PM_PD_Breakout_V4_8H7_Parity_Capture_FULL.pine"
OUTPUT = ROOT / "PM_PD_Breakout_V4_9N_3F3_COMPACT_CSV_Parity_Export.pine"
EXPECTED_SHA = "79b9d80f0ec2c254bd69607ff626c2007ae7e617018d984f083ba2a25e7ba681"

if not SOURCE.exists():
    raise SystemExit(f"Missing source: {SOURCE}")

raw = SOURCE.read_bytes()
sha = hashlib.sha256(raw).hexdigest()

print("=== PMPD V5 9N-3F3 ROBUST PARITY BOUNDARY DISCOVERY ===")
print("SOURCE =", SOURCE)
print("SOURCE_SHA256 =", sha)

if sha != EXPECTED_SHA:
    raise SystemExit(f"Frozen source SHA mismatch: {sha} != {EXPECTED_SHA}")

print("FROZEN_SOURCE_SHA=PASS")

text = raw.decode("utf-8", errors="ignore")
lines = text.splitlines()

# Robustly locate the END of the existing parity capture section by searching
# for the distinctive text independent of box-drawing/comment formatting.
end_idx = None
for i, line in enumerate(lines):
    normalized = line.upper().replace("–", "-").replace("—", "-")
    if "END 8H-7B-2K" in normalized and "PARITY CLASSIFICATION CAPTURE" in normalized:
        end_idx = i
        break

if end_idx is None:
    # Fallback: locate the next major section after the parity tables, which is
    # "ADD SIGNALS TO HISTORICAL TRACKER". Keep everything before that.
    for i, line in enumerate(lines):
        normalized = line.upper()
        if "ADD SIGNALS TO HISTORICAL TRACKER" in normalized:
            end_idx = i - 1
            print("BOUNDARY_MODE=FALLBACK_NEXT_SECTION")
            break
else:
    print("BOUNDARY_MODE=EXPLICIT_PARITY_END")

if end_idx is None or end_idx < 3000:
    # Diagnostic output to make a future failure actionable.
    hits = []
    for i, line in enumerate(lines):
        u = line.upper()
        if "PARITY" in u and ("CAPTURE" in u or "HISTORICAL TRACKER" in u):
            hits.append((i+1, line[:180]))
    print("DIAGNOSTIC_MATCHES:")
    for item in hits[:40]:
        print(item[0], item[1])
    raise SystemExit("Could not safely determine parity-capture boundary.")

# Include any immediately following separator/comment lines, but do not enter
# the next executable section.
while end_idx + 1 < len(lines):
    nxt = lines[end_idx + 1].strip()
    if nxt == "" or nxt.startswith("//"):
        # Stop before the historical-tracker header if encountered.
        if "ADD SIGNALS TO HISTORICAL TRACKER" in nxt.upper():
            break
        end_idx += 1
    else:
        break

prefix_lines = lines[:end_idx + 1]
prefix = "\n".join(prefix_lines)

old_title = 'indicator("PM + PD Breakout Monitor - V4 8H-7 Parity Capture",'
new_title = 'indicator("PM + PD V4 9N-3F3 COMPACT CSV PARITY",'
if old_title in prefix:
    prefix = prefix.replace(old_title, new_title, 1)
    print("DISPLAY_TITLE_RENAMED=True")
else:
    print("DISPLAY_TITLE_RENAMED=False")

export = r'''
//=============================================================================
// 9N-3F3 COMPACT MACHINE-READABLE CSV PARITY EXPORT
//=============================================================================
// READ-ONLY RESEARCH COPY.
// Frozen source retained through existing parity capture.
// Downstream analytics/display omitted only to stay below compiler limits.
//=============================================================================

f_9n3f3GradeCode(string g) =>
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

f_9n3f3TradeTypeCode(string value) =>
    value == "SCALP" ? 1 : value == "EXPANSION" ? 2 : 0

f_9n3f3ConfidenceCode(string value) =>
    value == "LOW" ? 1 :
     value == "MODERATE" ? 2 :
     value == "MOD-HIGH" ? 3 :
     value == "HIGH" ? 4 : 0

int n3f3SignalCount = array.size(parityDirection)
int n3f3DetailIndex = parityDetailSignal - 1
bool n3f3HasSignal = parityCaptureAllowed and n3f3DetailIndex >= 0 and n3f3DetailIndex < n3f3SignalCount

int n3f3GradeBucket = n3f3HasSignal ? f_gradeBucket(array.get(parityGrade, n3f3DetailIndex)) : BUCKET_WEAK
int n3f3Profile = n3f3HasSignal ? array.get(parityProfile, n3f3DetailIndex) : PROFILE_UNCLASSIFIED
int n3f3Priority = n3f3HasSignal ? f_priorityCode(n3f3GradeBucket, n3f3Profile) : PRIORITY_OBSERVE
string n3f3TradeType = n3f3HasSignal ? f_tradeType(n3f3GradeBucket, n3f3Profile) : "OBSERVE"
float n3f3TQS = n3f3HasSignal ? f_productionTQS(n3f3GradeBucket, n3f3Profile) : na
string n3f3Confidence = n3f3HasSignal ? f_productionConfidence(n3f3GradeBucket, n3f3Profile) : "INSUFFICIENT"

plot(parityCaptureAllowed ? (parityDateSeen ? 1.0 : 0.0) : na, "PMPD_PARITY_DATE_SEEN", display = display.none)
plot(parityCaptureAllowed ? float(n3f3SignalCount) : na, "PMPD_PARITY_SIGNAL_COUNT", display = display.none)
plot(n3f3HasSignal ? float(array.get(parityDirection, n3f3DetailIndex)) : na, "PMPD_PARITY_DIRECTION", display = display.none)
plot(n3f3HasSignal ? float(array.get(paritySignalTime, n3f3DetailIndex)) : na, "PMPD_PARITY_SIGNAL_TIME_MS", display = display.none)
plot(n3f3HasSignal ? array.get(parityReference, n3f3DetailIndex) : na, "PMPD_PARITY_REFERENCE", display = display.none)

plot(parityCaptureAllowed ? parityDatePMH : na, "PMPD_PARITY_DATE_PMH", display = display.none)
plot(parityCaptureAllowed ? parityDatePML : na, "PMPD_PARITY_DATE_PML", display = display.none)
plot(parityCaptureAllowed ? parityDatePDH : na, "PMPD_PARITY_DATE_PDH", display = display.none)
plot(parityCaptureAllowed ? parityDatePDL : na, "PMPD_PARITY_DATE_PDL", display = display.none)

plot(n3f3HasSignal ? array.get(parityFinalLevel, n3f3DetailIndex) : na, "PMPD_PARITY_FINAL_LEVEL", display = display.none)
plot(n3f3HasSignal ? array.get(parityATR, n3f3DetailIndex) : na, "PMPD_PARITY_ATR", display = display.none)
plot(n3f3HasSignal ? array.get(parityPen, n3f3DetailIndex) : na, "PMPD_PARITY_PEN_PCT_ATR", display = display.none)
plot(n3f3HasSignal ? array.get(parityBody, n3f3DetailIndex) : na, "PMPD_PARITY_BODY_PCT", display = display.none)
plot(n3f3HasSignal ? array.get(parityRangeATR, n3f3DetailIndex) : na, "PMPD_PARITY_RANGE_PCT_ATR", display = display.none)
plot(n3f3HasSignal ? array.get(parityClosePos, n3f3DetailIndex) : na, "PMPD_PARITY_CLOSE_POS_PCT", display = display.none)
plot(n3f3HasSignal ? float(array.get(parityBarsToConfirm, n3f3DetailIndex)) : na, "PMPD_PARITY_BARS_TO_CONFIRM", display = display.none)

plot(n3f3HasSignal ? array.get(parityTotalScore, n3f3DetailIndex) : na, "PMPD_PARITY_TOTAL_SCORE", display = display.none)
plot(n3f3HasSignal ? float(f_9n3f3GradeCode(array.get(parityGrade, n3f3DetailIndex))) : na, "PMPD_PARITY_GRADE_CODE", display = display.none)
plot(n3f3HasSignal ? float(n3f3Profile) : na, "PMPD_PARITY_PROFILE_CODE", display = display.none)
plot(n3f3HasSignal ? float(n3f3Priority) : na, "PMPD_PARITY_PRIORITY_CODE", display = display.none)
plot(n3f3HasSignal ? float(f_9n3f3TradeTypeCode(n3f3TradeType)) : na, "PMPD_PARITY_TRADE_TYPE_CODE", display = display.none)
plot(n3f3HasSignal ? n3f3TQS : na, "PMPD_PARITY_TQS", display = display.none)
plot(n3f3HasSignal ? float(f_9n3f3ConfidenceCode(n3f3Confidence)) : na, "PMPD_PARITY_CONFIDENCE_CODE", display = display.none)

plot(n3f3HasSignal ? (n3f3Priority >= PRIORITY_CONDITIONAL ? 1.0 : 0.0) : na, "PMPD_PARITY_DEFAULT_CONDITIONAL_PLUS_ELIGIBLE", display = display.none)

plot(n3f3HasSignal ? array.get(parityPenScore, n3f3DetailIndex) : na, "PMPD_PARITY_PEN_SCORE", display = display.none)
plot(n3f3HasSignal ? array.get(parityBodyScore, n3f3DetailIndex) : na, "PMPD_PARITY_BODY_SCORE", display = display.none)
plot(n3f3HasSignal ? array.get(parityCloseScore, n3f3DetailIndex) : na, "PMPD_PARITY_CLOSE_SCORE", display = display.none)
plot(n3f3HasSignal ? array.get(parityRangeScore, n3f3DetailIndex) : na, "PMPD_PARITY_RANGE_SCORE", display = display.none)
plot(n3f3HasSignal ? array.get(paritySpeedScore, n3f3DetailIndex) : na, "PMPD_PARITY_SPEED_SCORE", display = display.none)

plot(n3f3HasSignal ? float(array.get(parityFirstOutcome, n3f3DetailIndex)) : na, "PMPD_PARITY_FIRST_OUTCOME_CODE", display = display.none)
plot(n3f3HasSignal ? array.get(parityMFE, n3f3DetailIndex) : na, "PMPD_PARITY_MFE_PCT", display = display.none)
plot(n3f3HasSignal ? array.get(parityMAE, n3f3DetailIndex) : na, "PMPD_PARITY_MAE_PCT", display = display.none)
'''

OUTPUT.write_text(prefix + "\n" + export + "\n", encoding="utf-8")

print("BOUNDARY_LINE =", end_idx + 1)
print("OUTPUT =", OUTPUT)
print("OUTPUT_SHA256 =", hashlib.sha256(OUTPUT.read_bytes()).hexdigest())
print("OUTPUT_LINE_COUNT =", len(OUTPUT.read_text(encoding="utf-8").splitlines()))
print("DOWNSTREAM_ANALYTICS_DISPLAY_REMOVED=True")
print("ORIGINAL_V4_MODIFIED=False")
print("PATCHED_COPY_ONLY=True")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("TRADINGVIEW_PARITY_VALIDATED=False")
print("9N_3F3_PATCH_GATE=PASS")
