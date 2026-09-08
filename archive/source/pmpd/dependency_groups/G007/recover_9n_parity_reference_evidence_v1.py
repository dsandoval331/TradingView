from pathlib import Path
import json, re

ROOT=Path.cwd()
print("=== PMPD V5 9N-3C PARITY REFERENCE EVIDENCE RECOVERY ===")

# Search broadly for completed Pine/TV observations/results, not candidate definitions.
name_terms=("parity","8h7","8h-7","pine","tradingview","capture","reference","observed","classification")
content_terms=(
    "pine_signal_exists","pine_signal_timestamp","pine_primary_outcome",
    "parity_status","PARITY_MATCH","DATE_NOT_LOADED","NO_SIGNAL",
    "FAVORABLE_FIRST","ADVERSE_FIRST","STRENGTH_SCORE_MISMATCH",
    "GRADE_MISMATCH","REFERENCE_PRICE_MISMATCH"
)
skip_names={
    "audit_9n_preserved_tv_parity_evidence_v1.py",
    "pmpd_v5_9n_preserved_tv_parity_evidence_output.txt",
    "pmpd_v5_9n_preserved_tv_parity_evidence_audit_v1.json",
}
allowed={".csv",".json",".txt",".md",".log",".tsv",".pine",".sql"}

candidates=[]
for p in ROOT.rglob("*"):
    try:
        if not p.is_file() or p.name in skip_names: continue
        if p.suffix.lower() not in allowed: continue
        n=str(p).lower()
        if any(t in n for t in name_terms):
            candidates.append(p)
    except Exception:
        pass

# Add content-discovered files, bounded to reasonably sized text files.
seen={str(p.resolve()) for p in candidates}
for p in ROOT.rglob("*"):
    try:
        if not p.is_file() or p.name in skip_names or p.suffix.lower() not in allowed: continue
        if p.stat().st_size > 8_000_000: continue
        s=str(p.resolve())
        if s in seen: continue
        txt=p.read_text(encoding="utf-8",errors="ignore")
        if any(t.lower() in txt.lower() for t in content_terms):
            candidates.append(p); seen.add(s)
    except Exception:
        pass

print("FILES_SCANNED_AS_EVIDENCE_CANDIDATES =",len(candidates))

evidence=[]
for p in sorted(candidates):
    try:
        txt=p.read_text(encoding="utf-8",errors="ignore")
    except Exception:
        continue
    hits=[t for t in content_terms if t.lower() in txt.lower()]
    # Exclude obvious protocol/spec/code-only files from "observed evidence" classification.
    lowname=str(p).lower()
    definition_only=(
        p.suffix.lower() in {".pine",".sql"} or
        "specification" in lowname or "protocol" in lowname or
        "readme" in lowname or "candidate" in lowname
    )
    observed_markers=[]
    for marker in ("pine_signal_exists","pine_signal_timestamp","pine_primary_outcome","parity_status"):
        if marker.lower() in txt.lower():
            observed_markers.append(marker)
    # CSV/TSV header inspection
    header=txt.splitlines()[0] if txt.splitlines() else ""
    header_observed=any(m in header.lower() for m in
        ("pine_signal","pine_primary_outcome","parity_status","actual_signal","expected_signal"))
    likely_observed=(bool(observed_markers) or header_observed) and not definition_only
    rec={"path":str(p),"hits":hits,"observed_markers":observed_markers,
         "header":header[:1000],"likely_observed_evidence":likely_observed}
    if likely_observed:
        evidence.append(rec)
        print("\nLIKELY_OBSERVED_EVIDENCE =",p)
        print("HEADER =",header[:1000])
        print("MARKERS =",observed_markers)
        # show only first 25 lines
        for i,line in enumerate(txt.splitlines()[:25],1):
            print(f"{i}: {line[:1200]}")

print("\nLIKELY_OBSERVED_EVIDENCE_FILES =",len(evidence))
report={
    "likely_observed_evidence":evidence,
    "tradingview_parity_validated":False,
    "v4_logic_executed":False,
    "v4_modified":False,
    "v5_modified":False,
    "production_rule_authorized":False
}
rp=ROOT/"pmpd_v5_9n_parity_reference_evidence_recovery_v1.json"
rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("REPORT =",rp)
print("TRADINGVIEW_PARITY_VALIDATED=False")
print("V4_LOGIC_EXECUTED=False")
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9N_PARITY_REFERENCE_EVIDENCE_RECOVERY_GATE=PASS")
