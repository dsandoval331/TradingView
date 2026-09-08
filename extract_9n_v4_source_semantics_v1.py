from pathlib import Path
import json, hashlib

ROOT = Path.cwd()
TARGETS = [
    ROOT/"PM_PD_Breakout_V4_8H7_Parity_Capture_FULL.pine",
    ROOT/"PM_PD_Breakout_V4_8H7_Parity_Capture.pine",
    ROOT/"PM + PD Breakout Monitor - V4 8H-7 Parity Capture.pine",
    ROOT/"OlderProjectFolders"/"OlderTradingViewPineScriptWork"/"PM_Previous_Day_Breakout_Monitor_V4_Forward_Validation_FINAL.pine",
    ROOT/"PM + PD Breakout Monitor - V4 Forward Validation FINAL.pine",
    ROOT/"OlderProjectFolders"/"OlderTradingViewPineScriptWork"/"PM_Previous_Day_Breakout_Monitor_V3_4A6_V4_Grade_Profile_TQS_Capture.pine",
]
target = next((p for p in TARGETS if p.exists()), None)
if target is None:
    raise SystemExit("No target V4 Pine source found.")

text = target.read_text(encoding="utf-8", errors="ignore")
lines = text.splitlines()
sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

print("=== PMPD V5 9N-3D-B FROZEN V4 SOURCE SEMANTIC EXTRACTION ===")
print("TARGET =", target)
print("TARGET_SHA256 =", sha)
print("LINE_COUNT =", len(lines))

patterns = {
    "inputs_forward": ["minimumAlertPriority","showResearchPriorityAlerts","showLowObserveAlerts"],
    "profile": ["f_v4CombinationProfile(","f_profileName("],
    "priority": ["f_priorityCode(","f_priorityName(","f_tradeType(","f_productionTQS(","f_productionConfidence(","f_priorityAlertPass("],
    "atr_time": ["regularTicker","confATR =","confTime =","confTimeClose =","newConfirmationCandle"],
    "state": ["bullState","bearState","bullArmedBars","bearArmedBars","bullAlert :=","bearAlert :="],
    "components": ["bullPenATR","bearPenATR","bodyRatio","rangeATR","bullClosePosition","bearClosePosition"],
    "score": ["f_penetrationScore(","f_bodyScore(","f_closeScore(","f_rangeScore(","f_speedScore(","f_grade("],
    "parity": ["parityDirection","paritySignalTime","parityReference","parityATR","parityPen","parityBody","parityRangeATR","parityClosePos","parityBarsToConfirm","parityTotalScore","parityGrade","parityProfile","parityMFE","parityMAE","parityFirstOutcome"],
    "outcome": ["FIRST_NONE","FIRST_FAVORABLE","FIRST_ADVERSE","FIRST_BOTH","MFE","MAE"],
    "forward_alert": ["priorityAlertPass","minimumAlertPriority","alert(","alertcondition("],
}

def merged_windows(indices, pad=18):
    ws = []
    for i in sorted(set(indices)):
        a, b = max(0, i-pad), min(len(lines), i+pad+1)
        if ws and a <= ws[-1][1]:
            ws[-1] = (ws[-1][0], max(ws[-1][1], b))
        else:
            ws.append((a,b))
    return ws

report = {"target": str(target), "sha256": sha, "line_count": len(lines), "sections": {}}

for name, pats in patterns.items():
    idx = [i for i, line in enumerate(lines) if any(p.lower() in line.lower() for p in pats)]
    windows = merged_windows(idx)
    report["sections"][name] = []
    print(f"\n========== {name.upper()} ==========")
    if not windows:
        print("NO_MATCH")
    for a,b in windows:
        print(f"\n--- lines {a+1}-{b} ---")
        block = []
        for j in range(a,b):
            print(f"{j+1}: {lines[j]}")
            block.append({"line":j+1, "text":lines[j]})
        report["sections"][name].append({"start":a+1, "end":b, "lines":block})

embedded = ("parityDirection" in text and "parityFirstOutcome" in text and "Enable Parity Candidate Capture" in text)
report["parity_patch_embedded"] = embedded
print("\nPARITY_PATCH_EMBEDDED =", embedded)

plot_export = []
for i, line in enumerate(lines):
    low = line.lower()
    if ("plot(" in low or "plotchar(" in low) and ("parity" in low or "export" in low or "csv" in low):
        plot_export.append({"line":i+1,"text":line})
report["existing_parity_export_plots"] = plot_export
print("EXISTING_PARITY_EXPORT_PLOT_COUNT =", len(plot_export))
for r in plot_export:
    print(f"{r['line']}: {r['text']}")

rp = ROOT/"pmpd_v5_9n_3d_b_v4_source_semantics_v1.json"
rp.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nREPORT =", rp)
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_3D_B_SOURCE_SEMANTICS_GATE=PASS")
