from pathlib import Path
import json, re
from collections import defaultdict
import pandas as pd

ROOT=Path.cwd()
REPORT=ROOT/"pmpd_v5_9m_2026_symbol_partition_audit_v2.json"
assert REPORT.exists(), f"Missing {REPORT}"
r=json.loads(REPORT.read_text(encoding="utf-8"))

OHLC_ALIASES={
    "open":{"open","o"},
    "high":{"high","h"},
    "low":{"low","l"},
    "close":{"close","c"},
    "volume":{"volume","v","vol"},
}
TIME_HINTS=("timestamp","datetime","time","date","t")

def norm(x): return str(x).strip().lower()

def detect_time_col(cols):
    cs=[str(c) for c in cols]
    low={norm(c):c for c in cs}
    for exact in ["timestamp","datetime","time","date","t"]:
        if exact in low: return low[exact]
    for c in cs:
        lc=norm(c)
        if "timestamp" in lc or "datetime" in lc:
            return c
    return None

def has_ohlcv(cols):
    lows={norm(c) for c in cols}
    return all(any(a in lows for a in aliases) for k,aliases in OHLC_ALIASES.items() if k!="volume")

def parse_ts_series(s):
    # Numeric epoch support plus normal datetime strings.
    x=pd.Series(s)
    if pd.api.types.is_numeric_dtype(x):
        vals=pd.to_numeric(x,errors="coerce")
        mx=vals.dropna().abs().median() if vals.notna().any() else 0
        unit="ms" if mx>1e11 else "s"
        return pd.to_datetime(vals,unit=unit,utc=True,errors="coerce")
    return pd.to_datetime(x,utc=True,errors="coerce")

try:
    import pyarrow.parquet as pq
    HAVE_PQ=True
except Exception:
    HAVE_PQ=False

per_symbol={}
problems=[]
for sym,paths in r["per_symbol_files"].items():
    candidates=[]
    for ps in paths:
        p=Path(ps)
        if not p.exists(): continue
        ext=p.suffix.lower()
        try:
            if ext==".parquet" and HAVE_PQ:
                pf=pq.ParquetFile(p)
                cols=list(pf.schema.names)
                tc=detect_time_col(cols)
                if not tc or not has_ohlcv(cols): 
                    continue
                tbl=pq.read_table(p,columns=[tc])
                ts=parse_ts_series(tbl[tc].to_pandas())
                ts=ts[(ts.dt.year==2026)]
                if ts.empty: continue
                candidates.append({
                    "path":str(p),"format":"parquet","rows":int(pf.metadata.num_rows),
                    "time_col":tc,"first_2026":ts.min().isoformat(),"last_2026":ts.max().isoformat(),
                    "ohlcv_schema":True
                })
            elif ext==".csv":
                # Cheap header first; only read timestamp column for plausible OHLC files.
                hdr=pd.read_csv(p,nrows=0)
                cols=list(hdr.columns)
                tc=detect_time_col(cols)
                if not tc or not has_ohlcv(cols):
                    continue
                tsraw=pd.read_csv(p,usecols=[tc])[tc]
                ts=parse_ts_series(tsraw)
                ts=ts[(ts.dt.year==2026)]
                if ts.empty: continue
                candidates.append({
                    "path":str(p),"format":"csv","rows":int(len(tsraw)),
                    "time_col":tc,"first_2026":ts.min().isoformat(),"last_2026":ts.max().isoformat(),
                    "ohlcv_schema":True
                })
        except Exception as e:
            problems.append({"symbol":sym,"path":str(p),"error":repr(e)})
    if candidates:
        # Prefer parquet, then largest row count / widest time span proxy.
        candidates.sort(key=lambda x:(x["format"]=="parquet",x["rows"]),reverse=True)
        per_symbol[sym]={"selected":candidates[0],"all_candidates":candidates}
    else:
        per_symbol[sym]={"selected":None,"all_candidates":[]}

selected={s:v["selected"] for s,v in per_symbol.items() if v["selected"]}
missing=sorted(set(r["mapped_symbol_list"])-set(selected))
print("=== PMPD V5 9M 2026 TIMESTAMP/COVERAGE CERTIFICATION ===")
print("SYMBOLS_EXPECTED =",len(r["mapped_symbol_list"]))
print("SYMBOLS_WITH_OHLC_2026_CANDIDATE =",len(selected))
print("SYMBOLS_WITHOUT_OHLC_2026_CANDIDATE =",missing)
print("READ_PROBLEMS =",len(problems))

if selected:
    firsts={s:pd.Timestamp(v["first_2026"]) for s,v in selected.items()}
    lasts={s:pd.Timestamp(v["last_2026"]) for s,v in selected.items()}
    common_start=max(firsts.values())
    common_end=min(lasts.values())
    print("EARLIEST_ANY_FIRST_2026 =",min(firsts.values()).isoformat())
    print("LATEST_SYMBOL_FIRST_2026 =",common_start.isoformat())
    print("EARLIEST_SYMBOL_LAST_2026 =",common_end.isoformat())
    print("LATEST_ANY_LAST_2026 =",max(lasts.values()).isoformat())
    print("COMMON_WINDOW_START =",common_start.isoformat())
    print("COMMON_WINDOW_END =",common_end.isoformat())
    print("COMMON_WINDOW_NONEMPTY =",bool(common_end>=common_start))

    # Date-level breadth summaries.
    start_dates=pd.Series([x.date() for x in firsts.values()])
    end_dates=pd.Series([x.date() for x in lasts.values()])
    print("FIRST_DATE_COUNTS_TOP =",start_dates.value_counts().sort_index().to_dict())
    print("LAST_DATE_COUNTS_TOP =",end_dates.value_counts().sort_index().to_dict())

report={
    "protocol":"PMPD_V5_9M_2026_TIMESTAMP_COVERAGE_CERT_V1",
    "symbols_expected":len(r["mapped_symbol_list"]),
    "symbols_selected":len(selected),
    "symbols_missing":missing,
    "read_problems":problems,
    "per_symbol":per_symbol,
    "coverage_certified": bool(len(selected)==len(r["mapped_symbol_list"])) if selected else False,
    "outcomes_characterized":False,
    "candidate_modified":False,
    "production_rule_authorized":False
}
if selected:
    report["common_window_start"]=common_start.isoformat()
    report["common_window_end"]=common_end.isoformat()
op=ROOT/"pmpd_v5_9m_2026_timestamp_coverage_cert_v1.json"
op.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("REPORT =",op)
print("COVERAGE_CERTIFIED =",report["coverage_certified"])
print("OUTCOMES_CHARACTERIZED=False")
print("CANDIDATE_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9M_TIMESTAMP_COVERAGE_GATE=PASS" if report["coverage_certified"] else "9M_TIMESTAMP_COVERAGE_GATE=REVIEW")
