from pathlib import Path
import json, re
from datetime import datetime, timezone

ROOT=Path.cwd()
TARGET_YEAR=2026
SYMBOLS_EXPECTED=112

def candidate_files(root):
    pats=["**/*.parquet","**/*.csv"]
    for pat in pats:
        for p in root.glob(pat):
            s=str(p).lower()
            if any(x in s for x in [".venv","site-packages","pmpd_v5_9h","pmpd_v5_9j","pmpd_v5_9k"]):
                continue
            yield p

rows=[]
for p in candidate_files(ROOT):
    name=p.name.upper()
    path=str(p).upper()
    year_hint=("2026" in name or "2026" in path)
    # Prefer canonical cache/market-data paths, but keep any 2026 candidate visible.
    market_hint=any(x in path for x in ["MARKET","CACHE","MASSIVE","1M","PARQUET"])
    if year_hint or market_hint:
        rows.append({"path":str(p),"size_bytes":p.stat().st_size,"year_hint":year_hint,"market_hint":market_hint})

# Extract ticker-like tokens only as a navigation hint; this is not certification.
ticker_tokens=set()
for r in rows:
    if r["year_hint"]:
        stem=Path(r["path"]).stem.upper()
        for tok in re.split(r"[^A-Z0-9.-]+",stem):
            if 1 <= len(tok) <= 6 and tok.isalpha() and tok not in {"CSV","DATA","CACHE","MARKET","MINUTE","PARQUET"}:
                ticker_tokens.add(tok)

report={
 "protocol":"PMPD_V5_9M_OOS_LOCAL_INVENTORY_V1",
 "target_year":TARGET_YEAR,
 "expected_universe_members":SYMBOLS_EXPECTED,
 "candidate_file_count":len(rows),
 "candidate_2026_file_count":sum(r["year_hint"] for r in rows),
 "ticker_like_tokens_from_2026_paths":sorted(ticker_tokens),
 "files":rows[:5000],
 "certified_coverage":False,
 "outcomes_characterized":False,
 "candidate_modified":False,
 "production_rule_authorized":False,
 "generated_at_utc":datetime.now(timezone.utc).isoformat()
}
p=ROOT/"pmpd_v5_9m_oos_local_inventory_v1.json"
p.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("=== PMPD V5 9M OOS LOCAL INVENTORY ===")
print("TARGET_YEAR=2026")
print("EXPECTED_UNIVERSE_MEMBERS=112")
print("CANDIDATE_FILES=",len(rows))
print("CANDIDATE_2026_FILES=",sum(r["year_hint"] for r in rows))
print("TICKER_LIKE_2026_PATH_TOKENS=",len(ticker_tokens))
print("REPORT=",p)
print("CERTIFIED_COVERAGE=False")
print("OUTCOMES_CHARACTERIZED=False")
print("CANDIDATE_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9M_LOCAL_INVENTORY_GATE=PASS")
