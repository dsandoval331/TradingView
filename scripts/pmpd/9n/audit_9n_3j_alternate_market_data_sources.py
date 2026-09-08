from pathlib import Path
import os, json, hashlib
import pandas as pd

ROOT = Path.cwd()
OUT_CSV = ROOT / "pmpd_v5_9n_3j_alternate_market_data_source_audit.csv"
OUT_JSON = ROOT / "pmpd_v5_9n_3j_alternate_market_data_source_summary.json"

CASES = [
("VRTX","2026-07-01"),("INTC","2026-03-31"),("QCOM","2026-07-02"),("MSFT","2026-03-31"),
("TXN","2026-05-08"),("COIN","2026-05-18"),("ADBE","2026-04-13"),("MU","2026-07-07"),
("CAT","2026-04-17"),("SLB","2026-07-28"),("UNH","2026-05-29"),("COP","2026-04-08"),
("MRVL","2026-05-14"),("NOW","2026-03-25"),("PANW","2026-04-09"),("PEP","2026-05-06"),
("C","2026-04-01"),("LOW","2026-03-20"),("APP","2026-08-18"),("BLK","2026-07-27"),
("SHOP","2026-04-24"),("CSCO","2026-06-02"),("DASH","2026-05-13"),("ABNB","2026-07-31"),
]
CASE_MAP = {s:d for s,d in CASES}
SYMS = set(CASE_MAP)

SKIP_DIRS = {".git",".venv","venv","node_modules","__pycache__",".next"}
BASELINE_TOKEN = "second1m_alt_entry_cache_v1"

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def guess_symbols(path: Path):
    text = " ".join(path.parts[-4:]).upper()
    hits=[]
    for s in SYMS:
        # conservative token-ish matching
        if (f"_{s}_" in text or f"\\{s}\\" in str(path).upper() or
            path.stem.upper().startswith(s+"_") or path.stem.upper().endswith("_"+s) or
            path.stem.upper()==s or path.parent.name.upper()==s):
            hits.append(s)
    return hits

def get_et(df):
    if "timestamp_et" in df.columns:
        et=pd.to_datetime(df["timestamp_et"], errors="coerce")
        if getattr(et.dt,"tz",None) is not None:
            et=et.dt.tz_convert("America/New_York")
        return et
    for c in ("timestamp_utc","timestamp","time","datetime","ts"):
        if c in df.columns:
            t=pd.to_datetime(df[c], errors="coerce", utc=True)
            return t.dt.tz_convert("America/New_York")
    if isinstance(df.index, pd.DatetimeIndex):
        idx=df.index
        if idx.tz is None:
            idx=idx.tz_localize("UTC")
        return pd.Series(idx.tz_convert("America/New_York"), index=df.index)
    return None

def stats(df, symbol, date_s):
    # symbol filter only if column exists and contains multiple symbols
    if "symbol" in df.columns:
        vals=df["symbol"].astype(str).str.upper()
        if symbol in set(vals.unique()):
            df=df.loc[vals.eq(symbol)].copy()
    et=get_et(df)
    if et is None:
        return None
    target=pd.Timestamp(date_s).date()
    mins=et.dt.hour*60+et.dt.minute
    mask_date=et.dt.date.eq(target)
    pre=df.loc[mask_date & mins.between(240,569)]
    rth=df.loc[mask_date & mins.between(570,959)]
    pre_t=et.loc[pre.index].dropna().drop_duplicates().sort_values()
    rth_t=et.loc[rth.index].dropna().drop_duplicates().sort_values()
    return {
        "pre_unique_minutes":int(len(pre_t)),
        "pre_first":None if pre_t.empty else str(pre_t.iloc[0]),
        "pre_last":None if pre_t.empty else str(pre_t.iloc[-1]),
        "pre_high":None if pre.empty or "high" not in pre else float(pre["high"].max()),
        "pre_low":None if pre.empty or "low" not in pre else float(pre["low"].min()),
        "rth_unique_minutes":int(len(rth_t)),
        "rth_high":None if rth.empty or "high" not in rth else float(rth["high"].max()),
        "rth_low":None if rth.empty or "low" not in rth else float(rth["low"].min()),
    }

print("=== PMPD V5 9N-3J ALTERNATE LOCAL MARKET-DATA SOURCE AUDIT ===")
print("ROOT =", ROOT)
print("Searching local parquet candidates for the frozen 24 parity symbols...")

candidates=[]
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    dp=Path(dirpath)
    for fn in filenames:
        if not fn.lower().endswith(".parquet"):
            continue
        p=dp/fn
        hits=guess_symbols(p)
        for s in hits:
            candidates.append((s,p))

# de-duplicate
seen=set(); unique=[]
for s,p in candidates:
    key=(s,str(p.resolve()).lower())
    if key not in seen:
        seen.add(key); unique.append((s,p))
candidates=unique
print("CANDIDATE_SYMBOL_FILES =", len(candidates))

rows=[]
errors=[]
for i,(symbol,p) in enumerate(candidates,1):
    date_s=CASE_MAP[symbol]
    try:
        df=pd.read_parquet(p)
        st=stats(df,symbol,date_s)
        if st is None:
            errors.append({"symbol":symbol,"path":str(p),"error":"no supported timestamp"})
            continue
        source_vals=";".join(sorted(df["source"].dropna().astype(str).unique())) if "source" in df.columns else ""
        adjusted_vals=";".join(sorted(df["adjusted"].dropna().astype(str).unique())) if "adjusted" in df.columns else ""
        row={
            "symbol":symbol,"date":date_s,"path":str(p),
            "is_baseline_cache":BASELINE_TOKEN in str(p).lower(),
            "size_bytes":p.stat().st_size,
            "source_values":source_vals,"adjusted_values":adjusted_vals,
            **st
        }
        rows.append(row)
        print(f'[{i}/{len(candidates)}] {symbol:5s} PRE={st["pre_unique_minutes"]:3d} RTH={st["rth_unique_minutes"]:3d}  {p}')
    except Exception as e:
        errors.append({"symbol":symbol,"path":str(p),"error":repr(e)})
        print("ERROR",symbol,p,repr(e))

audit=pd.DataFrame(rows)
if audit.empty:
    OUT_CSV.write_text("",encoding="utf-8")
    summary={"step":"9N-3J","candidate_files":len(candidates),"usable_files":0,"errors":errors}
    OUT_JSON.write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print("NO_USABLE_ALTERNATE_FILES")
    print("SUMMARY =",OUT_JSON)
    raise SystemExit(0)

audit["rank_pre"]=audit.groupby("symbol")["pre_unique_minutes"].rank(method="dense",ascending=False)
audit["best_for_symbol"]=audit["rank_pre"].eq(1)
audit.to_csv(OUT_CSV,index=False)

best=audit.sort_values(["symbol","pre_unique_minutes","rth_unique_minutes"],ascending=[True,False,False]).groupby("symbol").head(1)
baseline=audit[audit["is_baseline_cache"]].sort_values("symbol").groupby("symbol").head(1)

improvements=[]
for _,b in best.iterrows():
    s=b.symbol
    base=baseline[baseline.symbol.eq(s)]
    base_pre=None if base.empty else int(base.iloc[0].pre_unique_minutes)
    if base_pre is None or int(b.pre_unique_minutes)>base_pre:
        improvements.append({
            "symbol":s,"date":b.date,"baseline_pre_minutes":base_pre,
            "best_pre_minutes":int(b.pre_unique_minutes),
            "best_rth_minutes":int(b.rth_unique_minutes),
            "best_path":b.path,
            "source_values":b.source_values,
            "adjusted_values":b.adjusted_values,
        })

summary={
    "step":"9N-3J",
    "purpose":"discover and compare alternate local parquet sources for the frozen 24 parity cases",
    "candidate_files":int(len(candidates)),
    "usable_files":int(len(audit)),
    "symbols_with_usable_data":int(audit.symbol.nunique()),
    "symbols_with_better_pre_source_than_baseline":len(improvements),
    "improvements":improvements,
    "best_by_symbol":best[["symbol","date","pre_unique_minutes","rth_unique_minutes","path","source_values","adjusted_values"]].to_dict("records"),
    "errors":errors[:100],
    "governance":{
        "v4_modified":False,"v5_modified":False,"production_rule_authorized":False,
        "full_tradingview_parity_validated":False,
        "data_discovery_only":True
    }
}
OUT_JSON.write_text(json.dumps(summary,indent=2),encoding="utf-8")

print("\nSYMBOLS_WITH_BETTER_PRE_SOURCE_THAN_BASELINE =",len(improvements))
for x in improvements:
    print("IMPROVEMENT",x["symbol"],"baseline",x["baseline_pre_minutes"],"->",x["best_pre_minutes"],x["best_path"])
print("CSV =",OUT_CSV)
print("SUMMARY =",OUT_JSON)
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("TRADINGVIEW_FULL_24_CASE_PARITY_VALIDATED=False")
print("9N_3J_ALTERNATE_SOURCE_AUDIT=PASS")
