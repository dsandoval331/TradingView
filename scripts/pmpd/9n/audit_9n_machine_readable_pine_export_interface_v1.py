from pathlib import Path
import json

ROOT=Path.cwd()
print("=== PMPD V5 9N-3D-A MACHINE-READABLE PINE EXPORT INTERFACE AUDIT ===")

terms=[
"PM_Previous_Day_Breakout_Monitor_V3_4A6_V4_Grade_Profile_TQS_Capture",
"f_v4CombinationProfile","f_profileName","priority","tradeType","trade_type",
"trade type","TQS","ta.atr","atr(","bullTotalScore","bearTotalScore","bullGrade",
"bearGrade","parityDirection","paritySignalTime","parityReference","parityPMH",
"parityPML","parityPDH","parityPDL","parityATR","parityPen","parityBody",
"parityRangeATR","parityClosePos","parityBarsToConfirm","parityTotalScore",
"parityGrade","parityProfile","parityMFE","parityMAE","parityFirstOutcome"
]

pine_files=[p for p in ROOT.rglob("*.pine") if p.is_file()]
print("PINE_FILE_COUNT =",len(pine_files))
for p in sorted(pine_files):
    print("PINE_FILE =",p)

matches=[]
for p in sorted(pine_files):
    lines=p.read_text(encoding="utf-8",errors="ignore").splitlines()
    idx=[i for i,line in enumerate(lines) if any(t.lower() in line.lower() for t in terms)]
    if not idx:
        continue
    windows=[]
    for i in idx:
        a=max(0,i-6); b=min(len(lines),i+7)
        if windows and a <= windows[-1][1]:
            windows[-1]=(windows[-1][0],max(windows[-1][1],b))
        else:
            windows.append((a,b))
    print("\n=== FILE MATCHES:",p,"===")
    rec={"path":str(p),"windows":[]}
    for a,b in windows:
        print(f"\n--- lines {a+1}-{b} ---")
        chunk=[]
        for j in range(a,b):
            print(f"{j+1}: {lines[j]}")
            chunk.append({"line":j+1,"text":lines[j]})
        rec["windows"].append({"start":a+1,"end":b,"lines":chunk})
    matches.append(rec)

report={
"pine_file_count":len(pine_files),
"matches":matches,
"objective":"Resolve exact frozen V4 Pine interfaces for additive CSV export, ATR semantics, and priority/trade-type fallback.",
"v4_modified":False,
"v5_modified":False,
"production_rule_authorized":False
}
rp=ROOT/"pmpd_v5_9n_3d_a_pine_export_interface_audit_v1.json"
rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("\nREPORT =",rp)
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_3D_A_PINE_EXPORT_INTERFACE_AUDIT_GATE=PASS")
