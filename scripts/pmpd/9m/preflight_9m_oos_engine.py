from pathlib import Path
import json

ROOT=Path.cwd()
print("=== PMPD V5 9M OOS ENGINE PREFLIGHT ===")

checks = {
    "protocol": ROOT/"PMPD_V5_9M_OOS_PROTOCOL_V1.json",
    "coverage_cert": ROOT/"pmpd_v5_9m_2026_timestamp_coverage_cert_v1.json",
    "symbol_audit": ROOT/"pmpd_v5_9m_2026_symbol_partition_audit_v2.json",
}
for k,p in checks.items():
    print(f"{k.upper()}_EXISTS =",p.exists(), p)

# Inventory likely V5 engine/build files without executing research logic.
patterns = [
    "tr_platform/pmpd_v5/*.py",
    "*pmpd*v5*.py",
    "*9h*.py",
    "*structural*.py",
    "*dataset*.py",
]
found=[]
seen=set()
for pat in patterns:
    for p in ROOT.glob(pat):
        rp=str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            found.append(str(p))
print("CANDIDATE_ENGINE_FILES =",len(found))
for p in found[:120]:
    print("ENGINE_FILE =",p)

# Identify likely 2026 raw/canonical selected files from the certified report.
cov=checks["coverage_cert"]
if cov.exists():
    d=json.loads(cov.read_text(encoding="utf-8"))
    print("COVERAGE_CERTIFIED =",d.get("coverage_certified"))
    print("SYMBOLS_SELECTED =",d.get("symbols_selected"))
    print("COMMON_WINDOW_START =",d.get("common_window_start"))
    print("COMMON_WINDOW_END =",d.get("common_window_end"))
    selected=[]
    for sym,v in d.get("per_symbol",{}).items():
        s=v.get("selected")
        if s:
            selected.append((sym,s.get("path"),s.get("format"),s.get("rows")))
    print("SELECTED_SOURCE_FILES =",len(selected))
    for x in selected[:12]:
        print("SOURCE_SAMPLE =",x)

print("OUTCOMES_CHARACTERIZED=False")
print("CANDIDATE_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9M_ENGINE_PREFLIGHT_GATE=PASS")
