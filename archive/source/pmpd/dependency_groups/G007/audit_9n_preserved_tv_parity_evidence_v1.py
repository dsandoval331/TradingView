from pathlib import Path
import json, csv, re

ROOT=Path.cwd()
print("=== PMPD V5 9N-3B PRESERVED TRADINGVIEW PARITY EVIDENCE AUDIT ===")

roots=[
    ROOT/"docs"/"pmpd"/"parity",
    ROOT/"docs"/"pmpd"/"specifications",
    ROOT/"strategies"/"pmpd"/"output",
    ROOT
]

patterns=[
    "*PMPD*V4*PARITY*",
    "*pmpd*v4*parity*",
    "*parity*result*",
    "*parity*evidence*",
    "*pine*parity*",
    "*8H7B2*",
]

seen=set(); files=[]
for base in roots:
    if not base.exists(): continue
    for pat in patterns:
        for p in base.rglob(pat):
            try:
                if p.is_file():
                    s=str(p.resolve())
                    if s not in seen:
                        seen.add(s); files.append(p)
            except Exception:
                pass

print("MATCHED_FILES =",len(files))
for p in sorted(files):
    print("FILE =",p)

# Summarize structured artifacts without dumping huge content.
structured=[]
for p in sorted(files):
    suf=p.suffix.lower()
    try:
        if suf==".csv":
            import pandas as pd
            df=pd.read_csv(p)
            rec={"path":str(p),"type":"csv","rows":int(len(df)),"columns":list(df.columns)}
            structured.append(rec)
            print("\nCSV =",p)
            print("ROWS =",len(df))
            print("COLUMNS =",list(df.columns))
            print("HEAD =")
            print(df.head(12).to_string(index=False))
        elif suf==".json":
            obj=json.loads(p.read_text(encoding="utf-8",errors="ignore"))
            rec={"path":str(p),"type":"json","python_type":type(obj).__name__}
            if isinstance(obj,list):
                rec["rows"]=len(obj)
                rec["keys"]=sorted({k for x in obj[:100] if isinstance(x,dict) for k in x.keys()})
                print("\nJSON =",p)
                print("LIST_ROWS =",len(obj))
                print("KEYS =",rec["keys"])
                print("HEAD =",json.dumps(obj[:5],indent=2)[:12000])
            elif isinstance(obj,dict):
                rec["keys"]=list(obj.keys())
                print("\nJSON =",p)
                print("KEYS =",list(obj.keys()))
                print("CONTENT_HEAD =",json.dumps(obj,indent=2)[:12000])
            structured.append(rec)
    except Exception as e:
        print("\nSTRUCTURED_READ_FAIL =",p,repr(e))

# Find evidence-bearing field names and parity verdict text in text files.
needles=[
    "expected_signal","actual_signal","signal_timestamp","signal_time",
    "reference_price","strength_score","grade","profile","priority","trade_type",
    "v4_primary_outcome","favorable_first","adverse_first","both","neither",
    "PASS","FAIL","TradingView","Pine","parity"
]
text_matches=[]
for p in sorted(files):
    if p.suffix.lower() not in {".md",".txt",".py",".pine",".sql",".csv",".json"}: continue
    try:
        txt=p.read_text(encoding="utf-8",errors="ignore")
    except Exception:
        continue
    lines=[]
    for i,line in enumerate(txt.splitlines(),1):
        ll=line.lower()
        if any(n.lower() in ll for n in needles):
            lines.append((i,line[:600]))
    if lines:
        text_matches.append({"path":str(p),"match_count":len(lines)})
        print("\nTEXT_EVIDENCE =",p)
        print("MATCH_COUNT =",len(lines))
        # Limit per file to avoid terminal flood.
        for i,line in lines[:80]:
            print(f"{i}: {line}")
        if len(lines)>80:
            print("...TRUNCATED_FOR_THIS_FILE...")

# Special inventory for all files under docs/pmpd/parity, because filenames may not match patterns.
parity_dir=ROOT/"docs"/"pmpd"/"parity"
all_parity=[]
if parity_dir.exists():
    for p in sorted(parity_dir.rglob("*")):
        if p.is_file():
            all_parity.append(str(p))
    print("\nALL_DOCS_PMPD_PARITY_FILES =",len(all_parity))
    for p in all_parity:
        print("PARITY_FILE =",p)

report={
    "matched_files":[str(p) for p in files],
    "structured":structured,
    "text_matches":text_matches,
    "all_docs_pmpd_parity_files":all_parity,
    "tradingview_parity_validated":False,
    "v4_logic_executed":False,
    "v4_modified":False,
    "v5_modified":False,
    "production_rule_authorized":False
}
rp=ROOT/"pmpd_v5_9n_preserved_tv_parity_evidence_audit_v1.json"
rp.write_text(json.dumps(report,indent=2),encoding="utf-8")

print("\nREPORT =",rp)
print("TRADINGVIEW_PARITY_VALIDATED=False")
print("V4_LOGIC_EXECUTED=False")
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_PRESERVED_TV_PARITY_EVIDENCE_AUDIT_GATE=PASS")
