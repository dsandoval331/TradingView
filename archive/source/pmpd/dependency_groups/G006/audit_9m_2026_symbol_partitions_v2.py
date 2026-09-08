from pathlib import Path
import json, re
from collections import defaultdict

ROOT=Path.cwd()
INVENTORY=ROOT/"pmpd_v5_9m_oos_local_inventory_v1.json"
SYMBOLS=['AAPL', 'ABBV', 'ABNB', 'ADBE', 'AMAT', 'AMD', 'AMGN', 'AMZN', 'ANET', 'APP', 'ARM', 'ASML', 'AVGO', 'AXON', 'AXP', 'BA', 'BAC', 'BKNG', 'BLK', 'BMY', 'C', 'CAT', 'CEG', 'CMCSA', 'CME', 'CMG', 'COIN', 'COP', 'COST', 'CRM', 'CRWD', 'CSCO', 'CVS', 'CVX', 'DASH', 'DDOG', 'DE', 'DELL', 'DIS', 'EOG', 'ETN', 'FDX', 'GE', 'GILD', 'GOOG', 'GS', 'HAL', 'HD', 'HON', 'HOOD', 'IBM', 'INTC', 'ISRG', 'IWM', 'JNJ', 'JPM', 'KLAC', 'LLY', 'LMT', 'LOW', 'LRCX', 'LULU', 'MA', 'MCD', 'META', 'MNDY', 'MRK', 'MRNA', 'MRVL', 'MS', 'MSFT', 'MU', 'NEE', 'NFLX', 'NKE', 'NOW', 'NVDA', 'ORCL', 'OXY', 'PANW', 'PEP', 'PFE', 'PLTR', 'PYPL', 'QCOM', 'QQQ', 'RBLX', 'REGN', 'RTX', 'SBUX', 'SCHW', 'SHOP', 'SLB', 'SNOW', 'SPY', 'T', 'TEAM', 'TGT', 'TMO', 'TMUS', 'TQQQ', 'TSLA', 'TXN', 'UBER', 'UNH', 'UPS', 'URI', 'V', 'VRTX', 'VZ', 'WMT', 'XOM']

assert INVENTORY.exists(), f"Missing {INVENTORY}. Run audit_9m_2026_local_inventory.py first."
inv=json.loads(INVENTORY.read_text(encoding="utf-8"))

def relative_tokens(p):
    p=Path(p)
    try:
        rel=p.resolve().relative_to(ROOT.resolve())
        text=str(rel).upper()
    except Exception:
        # Strip Windows drive prefix so C: cannot be mistaken for ticker C.
        text=re.sub(r"^[A-Z]:[\\/]", "", str(p).upper())
    return [t for t in re.split(r"[^A-Z0-9]+", text) if t]

def symbol_hits(p):
    toks=set(relative_tokens(p))
    return [s for s in SYMBOLS if s in toks]

files=[Path(r["path"]) for r in inv.get("files",[]) if r.get("year_hint") and Path(r["path"]).exists()]
mapped=defaultdict(list)
unmapped=[]
ambiguous=[]

for p in files:
    hits=symbol_hits(p)
    if len(hits)==1:
        mapped[hits[0]].append(p)
    elif len(hits)==0:
        unmapped.append(str(p))
    else:
        ambiguous.append((str(p),hits))

present=sorted(mapped)
missing=sorted(set(SYMBOLS)-set(present))
multi=sorted([s for s,ps in mapped.items() if len(ps)>1])

print("=== PMPD V5 9M 2026 SYMBOL/PARTITION AUDIT V2 ===")
print("EXPECTED_SYMBOLS =",len(SYMBOLS))
print("2026_FILES_FROM_INVENTORY =",len(files))
print("MAPPED_SYMBOLS =",len(present))
print("MISSING_SYMBOLS =",missing)
print("UNMAPPED_FILES =",len(unmapped))
print("AMBIGUOUS_FILES =",len(ambiguous))
print("SYMBOLS_WITH_MULTIPLE_2026_FILES =",len(multi))

fmt=defaultdict(int)
parquet_rows=defaultdict(int)
parquet_fail=[]
timestamp_candidates=defaultdict(set)

try:
    import pyarrow.parquet as pq
    HAVE_PYARROW=True
except Exception:
    HAVE_PYARROW=False

for sym,ps in mapped.items():
    for p in ps:
        fmt[p.suffix.lower()]+=1
        if p.suffix.lower()==".parquet" and HAVE_PYARROW:
            try:
                pf=pq.ParquetFile(p)
                parquet_rows[sym]+=pf.metadata.num_rows
                for c in pf.schema.names:
                    lc=c.lower()
                    if any(k in lc for k in ["timestamp","datetime","time","date"]):
                        timestamp_candidates[sym].add(c)
            except Exception as e:
                parquet_fail.append((str(p),repr(e)))

print("FORMAT_COUNTS =",dict(fmt))
print("PYARROW_AVAILABLE =",HAVE_PYARROW)
print("PARQUET_FAILURES =",len(parquet_fail))
if parquet_rows:
    vals=list(parquet_rows.values())
    print("PARQUET_ROW_TOTAL =",sum(vals))
    print("PARQUET_ROWS_MIN_PER_MAPPED_SYMBOL =",min(vals))
    print("PARQUET_ROWS_MAX_PER_MAPPED_SYMBOL =",max(vals))

report={
 "protocol":"PMPD_V5_9M_2026_SYMBOL_PARTITION_AUDIT_V2",
 "fix":"Use project-relative path tokenization; strip Windows drive prefix to prevent C: from matching ticker C.",
 "expected_symbols":len(SYMBOLS),
 "mapped_symbols":len(present),
 "missing_symbols":missing,
 "mapped_symbol_list":present,
 "2026_files":len(files),
 "format_counts":dict(fmt),
 "unmapped_count":len(unmapped),
 "ambiguous_count":len(ambiguous),
 "unmapped_files":unmapped[:500],
 "ambiguous_files":ambiguous[:500],
 "symbols_with_multiple_files":multi,
 "pyarrow_available":HAVE_PYARROW,
 "parquet_failures":parquet_fail[:100],
 "per_symbol_files":{s:[str(p) for p in mapped[s]] for s in present},
 "per_symbol_parquet_rows":dict(parquet_rows),
 "per_symbol_timestamp_candidates":{s:sorted(v) for s,v in timestamp_candidates.items()},
 "coverage_certified":False,
 "outcomes_characterized":False,
 "candidate_modified":False,
 "production_rule_authorized":False
}
op=ROOT/"pmpd_v5_9m_2026_symbol_partition_audit_v2.json"
op.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("REPORT =",op)
print("COVERAGE_CERTIFIED=False")
print("OUTCOMES_CHARACTERIZED=False")
print("CANDIDATE_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9M_SYMBOL_PARTITION_AUDIT_V2_GATE=PASS")
