from pathlib import Path
import re, json

ROOT=Path.cwd()
OUT=ROOT/"pmpd_v5_9n_3k_massive_pipeline_inventory.txt"
EXTS={".py",".ps1",".md",".json",".toml",".yaml",".yml",".txt"}
SKIP={".git",".venv","venv","node_modules","__pycache__",".next"}
terms=re.compile(r"massive|polygon|MARKET_CACHE_V1|second1m_alt_entry_cache_v1|api[_ -]?key|aggs|aggregates|extended.?hours|premarket",re.I)

hits=[]
for p in ROOT.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in EXTS: continue
    if any(x in SKIP for x in p.parts): continue
    try:
        text=p.read_text(encoding="utf-8",errors="ignore")
    except Exception:
        continue
    lines=text.splitlines()
    matched=[]
    for i,line in enumerate(lines,1):
        if terms.search(line):
            # redact likely secrets/tokens while retaining pipeline clues
            safe=re.sub(r'(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*["\']?[^"\'\s,}]+',
                        r'\1=<REDACTED>',line)
            matched.append((i,safe[:500]))
    if matched:
        hits.append((p,matched[:30]))

with OUT.open("w",encoding="utf-8") as f:
    f.write("=== PMPD V5 9N-3K MASSIVE / MARKET-DATA PIPELINE INVENTORY ===\n")
    f.write(f"ROOT = {ROOT}\nFILES_WITH_HITS = {len(hits)}\n\n")
    for p,ms in hits:
        f.write(f"FILE: {p}\n")
        for n,line in ms: f.write(f"  L{n}: {line}\n")
        f.write("\n")
    f.write("NOTE: Secret-like assignments are redacted by this diagnostic.\n")
    f.write("V4_MODIFIED=False\nV5_MODIFIED=False\nPRODUCTION_RULE_AUTHORIZED=False\n")
print("FILES_WITH_HITS =",len(hits))
print("REPORT =",OUT)
print("9N_3K_PIPELINE_INVENTORY=PASS")
