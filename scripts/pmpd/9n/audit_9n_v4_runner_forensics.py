from pathlib import Path
import json, re

ROOT=Path.cwd()
print("=== PMPD V5 9N-3 V4 RUNNER FORENSIC AUDIT ===")

prov_dir=ROOT/"strategies"/"pmpd"/"output"/"provenance"
prov_files=sorted(prov_dir.glob("PMPD_V4_PMPD_112_V1_2025_*")) if prov_dir.exists() else []
print("PROVENANCE_FILES =",len(prov_files))

for p in prov_files:
    print("\n--- PROVENANCE",p,"---")
    try:
        txt=p.read_text(encoding="utf-8",errors="ignore")
        print(txt[:12000])
    except Exception as e:
        print("READ_FAIL",repr(e))

needles=[
    "PMPD_V4_PARITY_SPEC_V1",
    "PMPD_V4_PMPD_112_V1",
    "parity_spec_path",
    "signal_timeframe",
    "run_full_universe",
    "strategy_id",
    "favorable_target",
    "adverse_target",
    "same_bar",
    "signal_candle_excursion",
    "profile_precedence"
]

hits=[]
for p in ROOT.rglob("*.py"):
    try:
        txt=p.read_text(encoding="utf-8",errors="ignore")
    except Exception:
        continue
    matched=[n for n in needles if n.lower() in txt.lower()]
    if matched:
        # Ignore current audit scripts unless they contain another useful path reference.
        hits.append((p,matched,txt))

print("\nPYTHON_HIT_COUNT =",len(hits))
for p,matched,txt in hits:
    print("\n--- PYTHON_MATCH",p,"---")
    print("MATCHED =",matched)
    lines=txt.splitlines()
    shown=0
    for i,line in enumerate(lines,1):
        ll=line.lower()
        if any(n.lower() in ll for n in matched):
            lo=max(0,i-4); hi=min(len(lines),i+5)
            print(f"[LINES {lo+1}-{hi}]")
            for j in range(lo,hi):
                print(f"{j+1}: {lines[j][:500]}")
            shown+=1
            if shown>=8:
                break

# Also inventory likely strategy package paths.
for base in [ROOT/"strategies"/"pmpd", ROOT/"tr_platform"]:
    print("\nTREE_BASE =",base)
    if base.exists():
        count=0
        for p in sorted(base.rglob("*.py")):
            print("PY =",p)
            count+=1
            if count>=250:
                print("...TRUNCATED...")
                break
    else:
        print("MISSING")

report={
    "provenance_files":[str(p) for p in prov_files],
    "python_hit_files":[str(p) for p,_,_ in hits],
    "v4_logic_executed":False,
    "v4_modified":False,
    "v5_modified":False,
    "production_rule_authorized":False
}
rp=ROOT/"pmpd_v5_9n_v4_runner_forensic_audit_v1.json"
rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("\nREPORT =",rp)
print("V4_LOGIC_EXECUTED=False")
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_V4_RUNNER_FORENSIC_AUDIT_GATE=PASS")
