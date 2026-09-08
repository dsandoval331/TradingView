from pathlib import Path
import inspect, importlib, json, traceback

MODULES=[
    "tr_platform.pmpd_v5.full_universe_cli",
    "tr_platform.pmpd_v5.alpha",
    "tr_platform.pmpd_v5.research_dataset",
    "tr_platform.pmpd_v5.outcomes",
    "tr_platform.pmpd_v5.session_levels",
    "tr_platform.pmpd_v5.state_engine",
    "tr_platform.pmpd_v5.quality",
]

print("=== PMPD V5 9M ENGINE INTERFACE AUDIT ===")
report={"modules":{},"imports_ok":True,"outcomes_characterized":False,"candidate_modified":False,"production_rule_authorized":False}

for modname in MODULES:
    print(f"\n--- MODULE {modname} ---")
    try:
        m=importlib.import_module(modname)
        print("IMPORT=PASS")
        funcs=[]
        classes=[]
        for name,obj in sorted(vars(m).items()):
            if name.startswith("_"): 
                continue
            try:
                if inspect.isfunction(obj) and obj.__module__==modname:
                    sig=str(inspect.signature(obj))
                    funcs.append({"name":name,"signature":sig})
                    print("FUNCTION",name,sig)
                elif inspect.isclass(obj) and obj.__module__==modname:
                    try:
                        sig=str(inspect.signature(obj))
                    except Exception:
                        sig="(signature unavailable)"
                    classes.append({"name":name,"signature":sig})
                    print("CLASS",name,sig)
            except Exception:
                pass
        report["modules"][modname]={"functions":funcs,"classes":classes}
    except Exception as e:
        report["imports_ok"]=False
        report["modules"][modname]={"import_error":repr(e)}
        print("IMPORT=FAIL",repr(e))

# Print concise source for likely public entry points only.
LIKELY_NAMES=[
    "main","run","build_symbol","build_dataset","build_research_dataset",
    "compute_outcomes","calculate_outcomes","evaluate_outcomes",
    "build_session_levels","compute_session_levels",
    "build_state_engine","run_state_engine","apply_quality"
]
for modname in MODULES:
    try:
        m=importlib.import_module(modname)
    except Exception:
        continue
    for name in LIKELY_NAMES:
        obj=getattr(m,name,None)
        if callable(obj):
            print(f"\n=== SOURCE {modname}.{name} ===")
            try:
                src=inspect.getsource(obj)
                # Cap verbosity while preserving callable behavior.
                lines=src.splitlines()
                print("\n".join(lines[:180]))
                if len(lines)>180:
                    print(f"... SOURCE_TRUNCATED_AFTER_180_LINES total={len(lines)}")
            except Exception as e:
                print("SOURCE_UNAVAILABLE",repr(e))

# Also inspect argparse/parser construction text in the CLI source file.
try:
    import tr_platform.pmpd_v5.full_universe_cli as cli
    src=inspect.getsource(cli)
    print("\n=== FULL_UNIVERSE_CLI ARGUMENT LINES ===")
    for line in src.splitlines():
        if "add_argument" in line or "ArgumentParser" in line or "parse_args" in line:
            print(line)
except Exception as e:
    print("CLI_ARG_INSPECTION_FAIL",repr(e))

op=Path.cwd()/"pmpd_v5_9m_engine_interface_audit_v1.json"
op.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("\nREPORT =",op)
print("IMPORTS_OK =",report["imports_ok"])
print("OUTCOMES_CHARACTERIZED=False")
print("CANDIDATE_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9M_ENGINE_INTERFACE_AUDIT_GATE=PASS" if report["imports_ok"] else "9M_ENGINE_INTERFACE_AUDIT_GATE=REVIEW")
