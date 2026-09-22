from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

OUT_REL = Path("research_outputs/pmod/p2/batch2")
EIGHT = {"AXON","BKNG","BLK","KLAC","MNDY","NOW","REGN","URI"}
CONTEXT = ["SPY","QQQ","DIA","XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY"]
SNAPS = ["09:00","09:15","09:20","09:25","09:27","09:28","09:29"]

def _read(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    cols = {str(c).lower(): c for c in df.columns}
    # MARKET_CACHE_V1 canonical files use timestamp_utc; retain legacy aliases only
    # for compatibility with previously governed cache materializations.
    tscol = next((cols[k] for k in ("timestamp_utc","timestamp","datetime","time","ts") if k in cols), None)
    if tscol is None:
        raise RuntimeError(f"no canonical/compatible timestamp column: {path}")
    df = df.rename(columns={tscol:"timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if df["timestamp"].isna().any():
        raise RuntimeError(f"unparseable timestamp value(s): {path}")
    return df

def _audit(path: Path, symbol: str, year: int) -> dict:
    if not path.exists(): return {"symbol":symbol,"year":year,"status":"MISSING","path":str(path)}
    df=_read(path); cols={str(c).lower():c for c in df.columns}
    local=df["timestamp"].dt.tz_convert("America/New_York")
    dates=local.dt.date; hhmm=local.dt.strftime("%H:%M")
    dup=int(df["timestamp"].duplicated(keep=False).sum())
    conflict=0
    if dup:
        valuecols=[cols[k] for k in ("open","high","low","close","volume") if k in cols]
        dup_frame=df[df["timestamp"].duplicated(False)]
        if valuecols:
            conflict=int(dup_frame.groupby("timestamp")[valuecols].nunique().max(axis=1).gt(1).sum())
    invalid=0
    if all(k in cols for k in ("open","high","low","close")):
        o,h,l,c=(pd.to_numeric(df[cols[k]],errors="coerce") for k in ("open","high","low","close"))
        invalid=int(((l>h)|(o<l)|(o>h)|(c<l)|(c>h)|o.isna()|h.isna()|l.isna()|c.isna()).sum())
    rth=(hhmm>="09:30")&(hhmm<"16:00")
    pm=(hhmm>="04:00")&(hhmm<"09:30")
    trade_days=int(pd.Series(dates).nunique()); rth_days=int(pd.Series(dates[rth]).nunique()); pm_days=int(pd.Series(dates[pm]).nunique())
    snap={}
    for s in SNAPS:
        ds=set(dates[hhmm==s]); snap[s]=len(ds)
    # Snapshot availability is observation-based; absence is not synthesized.
    return {"symbol":symbol,"year":year,"status":"PASS" if invalid==0 and conflict==0 else "REVIEW",
            "path":str(path),"rows":len(df),"first_bar":str(df.timestamp.min()),"last_bar":str(df.timestamp.max()),
            "trading_days":trade_days,"rth_days":rth_days,"premarket_days":pm_days,
            "duplicate_rows":dup,"conflicting_duplicate_timestamps":conflict,"invalid_ohlc":invalid,
            **{f"snapshot_{s.replace(':','')}":snap[s] for s in SNAPS}}

def run(work_root: Path) -> dict:
    root=Path(work_root).resolve(); cache=root/"market_cache"/"MARKET_CACHE_V1"/"1m"; out=root/OUT_REL; out.mkdir(parents=True,exist_ok=True)
    symbols=sorted([p.name for p in cache.iterdir() if p.is_dir()]) if cache.exists() else []
    rows=[]
    for sym in sorted(set(symbols)|set(CONTEXT)|EIGHT):
        for year in (2024,2025): rows.append(_audit(cache/sym/f"{year}.parquet",sym,year))
    cert=pd.DataFrame(rows); cert.to_csv(out/"pmod_p2_b2_partition_certification.csv",index=False)
    eight=cert[cert.symbol.isin(EIGHT)].copy(); eight.to_csv(out/"pmod_p2_b2_eight_symbol_audit.csv",index=False)
    context=cert[cert.symbol.isin(CONTEXT)].copy(); context.to_csv(out/"pmod_p2_b2_context_audit.csv",index=False)
    summary={"cache_symbols_discovered":len(symbols),"partitions_audited":len(cert),
             "eight_present_partitions":int((eight.status!="MISSING").sum()),"eight_required_partitions":16,
             "context_present_partitions":int((context.status!="MISSING").sum()),"context_required_partitions":len(CONTEXT)*2,
             "snapshots":SNAPS,"timezone":"America/New_York",
             "missing_observations_synthesized":False,
             "note":"Exact snapshot absence is retained as observed absence; no synthetic zero-volume bars."}
    (out/"pmod_p2_b2_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return {"artifact":str(out/"pmod_p2_b2_partition_certification.csv"),
            "output_paths":[str(out/"pmod_p2_b2_partition_certification.csv"),str(out/"pmod_p2_b2_eight_symbol_audit.csv"),str(out/"pmod_p2_b2_context_audit.csv"),str(out/"pmod_p2_b2_summary.json")],
            "research_phase":"PMOD-P2","batch":"P2-B2","research_logic_modified":False}
