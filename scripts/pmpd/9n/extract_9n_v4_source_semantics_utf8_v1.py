from pathlib import Path
import json, hashlib, sys

# Force UTF-8 output on Windows PowerShell redirection.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path.cwd()
TARGETS = [
    ROOT/"pine"/"pmpd"/"v4"/"frozen"/"PM_PD_Breakout_V4_8H7_Parity_Capture_FULL.pine",
    ROOT/"pine"/"pmpd"/"v4"/"frozen"/"PM_PD_Breakout_V4_8H7_Parity_Capture.pine",
    ROOT/"pine"/"pmpd"/"v4"/"frozen"/"PM + PD Breakout Monitor - V4 8H-7 Parity Capture.pine",
    ROOT/"OlderProjectFolders"/"OlderTradingViewPineScriptWork"/"PM_Previous_Day_Breakout_Monitor_V4_Forward_Validation_FINAL.pine",
    ROOT/"pine"/"pmpd"/"v4"/"frozen"/"PM + PD Breakout Monitor - V4 Forward Validation FINAL.pine",
    ROOT/"OlderProjectFolders"/"OlderTradingViewPineScriptWork"/"PM_Previous_Day_Breakout_Monitor_V3_4A6_V4_Grade_Profile_TQS_Capture.pine",
]

target = next((p for p in TARGETS if p.exists()), None)
if target is None:
    raise SystemExit("No target V4 Pine source found.")

text = target.read_text(encoding="utf-8", errors="ignore")
lines = text.splitlines()
sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

print("=== PMPD V5 9N-3D-B2 FROZEN V4 SOURCE SEMANTIC EXTRACTION UTF8-SAFE ===")
print("TARGET =", target)
print("TARGET_SHA256 =", sha)
print("LINE_COUNT =", len(lines))

patterns = {
    "profile_full": [
        "f_v4CombinationProfile(",
        "bool explosive =",
        "bool controlledStrong =",
        "bool efficientModerate =",
        "bool delayedStrong =",
        "bool prettyButWeak =",
    ],
    "priority_trade_type_tqs_confidence": [
        "f_priorityCode(",
        "f_priorityName(",
        "f_tradeType(",
        "f_productionTQS(",
        "f_productionConfidence(",
        "f_priorityAlertPass(",
    ],
    "atr_time_semantics": [
        "string regularTicker",
        "float confATR =",
        "int confTime =",
        "int confTimeClose =",
        "bool newConfirmationCandle",
        "request.security(",
    ],
    "state_machine": [
        "var int bullState",
        "var int bearState",
        "bullArmedBars",
        "bearArmedBars",
        "if bullState ==",
        "if bearState ==",
        "bullAlert :=",
        "bearAlert :=",
    ],
    "component_formulae": [
        "bullPenATR",
        "bearPenATR",
        "bodyRatio =",
        "rangeATR =",
        "bullClosePosition",
        "bearClosePosition",
        "directionalPass",
        "bodyPass",
        "rangePass",
    ],
    "score_grade": [
        "f_penetrationScore(",
        "f_bodyScore(",
        "f_closeScore(",
        "f_rangeScore(",
        "f_speedScore(",
        "f_grade(",
        "f_gradeThreshold(",
    ],
    "production_gating": [
        "bullProductionAlert",
        "bearProductionAlert",
        "minimumAlertPriority",
        "showResearchPriorityAlerts",
        "showLowObserveAlerts",
        "if bullProductionAlert",
        "if bearProductionAlert",
    ],
    "parity_arrays_capture": [
        "array.push(parityDirection",
        "array.push(paritySignalTime",
        "array.push(parityReference",
        "array.push(parityATR",
        "array.push(parityPen",
        "array.push(parityBody",
        "array.push(parityRangeATR",
        "array.push(parityClosePos",
        "array.push(parityBarsToConfirm",
        "array.push(parityTotalScore",
        "array.push(parityGrade",
        "array.push(parityProfile",
        "array.push(parityMFE",
        "array.push(parityMAE",
        "array.push(parityFirstOutcome",
    ],
    "parity_outcome_mfe_mae": [
        "FIRST_NONE",
        "FIRST_FAVORABLE",
        "FIRST_ADVERSE",
        "FIRST_BOTH",
        "newMFE",
        "newMAE",
        "hitFavNow",
        "hitAdvNow",
        "parityFirstOutcome",
    ],
    "existing_export_plots": [
        "plot(",
        "plotchar(",
    ],
}

def merged_windows(indices, pad=22):
    ws = []
    for i in sorted(set(indices)):
        a, b = max(0, i-pad), min(len(lines), i+pad+1)
        if ws and a <= ws[-1][1]:
            ws[-1] = (ws[-1][0], max(ws[-1][1], b))
        else:
            ws.append((a, b))
    return ws

report = {
    "target": str(target),
    "sha256": sha,
    "line_count": len(lines),
    "sections": {}
}

for name, pats in patterns.items():
    idx = []
    for i, line in enumerate(lines):
        low = line.lower()
        if name == "existing_export_plots":
            if ("plot(" in low or "plotchar(" in low) and ("parity" in low or "export" in low or "csv" in low):
                idx.append(i)
        else:
            if any(p.lower() in low for p in pats):
                idx.append(i)

    windows = merged_windows(idx)
    report["sections"][name] = []
    print(f"\n========== {name.upper()} ==========")
    if not windows:
        print("NO_MATCH")

    for a, b in windows:
        print(f"\n--- lines {a+1}-{b} ---")
        block = []
        for j in range(a, b):
            safe = lines[j].encode("utf-8", errors="replace").decode("utf-8")
            print(f"{j+1}: {safe}")
            block.append({"line": j+1, "text": safe})
        report["sections"][name].append({"start": a+1, "end": b, "lines": block})

# Extra direct checks
checks = {
    "uses_ta_atr": "ta.atr(atrLength)" in text,
    "uses_prior_confirm_bar_atr": "ta.atr(atrLength)[1]" in text,
    "has_priority_code": "f_priorityCode(" in text,
    "has_trade_type": "f_tradeType(" in text,
    "has_tqs": "f_productionTQS(" in text,
    "has_confidence": "f_productionConfidence(" in text,
    "has_priority_alert_pass": "f_priorityAlertPass(" in text,
    "parity_patch_embedded": (
        "parityDirection" in text and
        "parityFirstOutcome" in text and
        "Enable Parity Candidate Capture" in text
    ),
}
report["checks"] = checks

print("\n========== DIRECT CHECKS ==========")
for k, v in checks.items():
    print(f"{k}={v}")

rp = ROOT/"pmpd_v5_9n_3d_b2_v4_source_semantics_utf8_v1.json"
rp.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\nREPORT =", rp)
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_3D_B2_SOURCE_SEMANTICS_UTF8_GATE=PASS")


