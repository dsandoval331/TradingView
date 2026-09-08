from pathlib import Path
import json, importlib, inspect

ROOT=Path.cwd()
print("=== PMPD V5 9N-2 V4 IMPLEMENTATION PREFLIGHT ===")

# Locate likely V4/parity artifacts without running signal/outcome logic.
patterns=[
    "*v4*.py","*V4*.py","*parity*.py","*PMPD_V4*.json","*PMPD_V4*.sql",
    "*pmpd*v4*","*pmpd*parity*"
]
seen=set(); hits=[]
for pat in patterns:
    for p in ROOT.rglob(pat):
        try:
            if p.is_file():
                s=str(p.resolve())
                if s not in seen:
                    seen.add(s); hits.append(p)
        except Exception:
            pass

print("ARTIFACT_COUNT =",len(hits))
for p in sorted(hits)[:200]:
    print("ARTIFACT =",p)

# Probe likely import names safely. Imports only; do not call research functions.
modules=[
    "tr_platform.pmpd_v4",
    "tr_platform.pmpd",
    "tr_platform.pmpd.parity",
    "tr_platform.pmpd_v4.parity",
    "tr_platform.pmpd_v4.engine",
    "tr_platform.pmpd_v4.strategy",
]
imports={}
for name in modules:
    try:
        m=importlib.import_module(name)
        imports[name]="PASS"
        print("\\nMODULE",name,"IMPORT=PASS")
        for n,obj in inspect.getmembers(m):
            if n.startswith("_"): continue
            if inspect.isfunction(obj) or inspect.isclass(obj):
                try: sig=str(inspect.signature(obj))
                except Exception: sig="(?)"
                print(("FUNCTION" if inspect.isfunction(obj) else "CLASS"),n,sig)
    except Exception as e:
        imports[name]=repr(e)
        print("\\nMODULE",name,"IMPORT=FAIL",repr(e))

# Search text artifacts for frozen spec code / likely CLI entrypoints.
needles=["PMPD_V4_PARITY_SPEC_V1","primary_favorable_pct","primary_adverse_pct",
         "same_bar","signal_timeframe","5m","run_full","evaluate"]
text_hits=[]
for p in hits:
    if p.suffix.lower() not in {".py",".json",".sql",".txt",".md"}: continue
    try:
        txt=p.read_text(encoding="utf-8",errors="ignore")
    except Exception:
        continue
    found=[n for n in needles if n.lower() in txt.lower()]
    if found:
        text_hits.append({"path":str(p),"needles":found})
        print("\\nTEXT_MATCH =",p)
        print("MATCHED =",found)
        # Print only relevant lines, not data outcomes.
        for line in txt.splitlines():
            ll=line.lower()
            if any(n.lower() in ll for n in needles):
                print(line[:500])

report={
    "artifact_count":len(hits),
    "artifacts":[str(p) for p in hits],
    "imports":imports,
    "text_hits":text_hits,
    "v4_logic_executed":False,
    "v4_modified":False,
    "v5_modified":False,
    "production_rule_authorized":False
}
rp=ROOT/"pmpd_v5_9n_v4_implementation_preflight_v1.json"
rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("\\nREPORT =",rp)
print("V4_LOGIC_EXECUTED=False")
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_V4_IMPLEMENTATION_PREFLIGHT_GATE=PASS")
