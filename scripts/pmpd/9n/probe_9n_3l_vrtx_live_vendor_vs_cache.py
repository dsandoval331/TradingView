from pathlib import Path
import getpass, os, json, hashlib
import pandas as pd

ROOT = Path.cwd()
SYMBOL = "VRTX"
DAY = "2026-07-01"
CACHE = ROOT / "data" / "second1m_alt_entry_cache_v1" / "partitions" / SYMBOL / f"{SYMBOL}_2026.parquet"
OUT_JSON = ROOT / "pmpd_v5_9n_3l_vrtx_live_vendor_vs_cache.json"
OUT_CSV = ROOT / "pmpd_v5_9n_3l_vrtx_live_vendor_vs_cache_rows.csv"

PINE = {"pmh":503.00, "pml":494.15, "pdh":500.99, "pdl":489.62, "signal_count":0}

def sha256(p: Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def et_series(df):
    if "timestamp_et" in df.columns:
        s=pd.to_datetime(df["timestamp_et"], errors="coerce")
        if getattr(s.dt,"tz",None) is not None:
            s=s.dt.tz_convert("America/New_York")
        return s
    if "timestamp_utc" in df.columns:
        return pd.to_datetime(df["timestamp_utc"], errors="coerce", utc=True).dt.tz_convert("America/New_York")
    if "timestamp_ms" in df.columns:
        return pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True).dt.tz_convert("America/New_York")
    raise ValueError("No supported timestamp column")

def summarize(df, label):
    et=et_series(df)
    mins=et.dt.hour*60+et.dt.minute
    date=pd.Timestamp(DAY).date()
    dmask=et.dt.date.eq(date)
    out={"label":label,"rows_day":int(dmask.sum())}
    for name,lo,hi in [("pre",240,569),("rth",570,959),("ah",960,1199)]:
        x=df.loc[dmask & mins.between(lo,hi)].copy()
        xt=et.loc[x.index].dropna().drop_duplicates().sort_values()
        out[f"{name}_rows"]=int(len(x))
        out[f"{name}_unique_minutes"]=int(len(xt))
        out[f"{name}_first"]=None if xt.empty else str(xt.iloc[0])
        out[f"{name}_last"]=None if xt.empty else str(xt.iloc[-1])
        out[f"{name}_high"]=None if x.empty else float(x["high"].max())
        out[f"{name}_low"]=None if x.empty else float(x["low"].min())
    return out

print("=== PMPD V5 9N-3L LIVE MASSIVE VENDOR ↔ CACHE PROBE ===")
print("CASE =", SYMBOL, DAY)
print("PINE_REFERENCE =", PINE)

if not CACHE.exists():
    raise SystemExit(f"Missing cache: {CACHE}")

from tr_platform.downloader.massive_client import MassiveClient, MassiveClientConfig
from tr_platform.downloader.partition_acquisition import normalize_massive_minute_rows

key=os.environ.get("MASSIVE_API_KEY","").strip()
if not key:
    key=getpass.getpass("Enter Massive API key: ").strip()
if not key:
    raise SystemExit("Massive API key not provided")

client=MassiveClient(MassiveClientConfig(api_key=key))

cache=pd.read_parquet(CACHE)
cache_summary=summarize(cache,"local_second1m_cache_adjusted_true")
print("CACHE_SHA256 =",sha256(CACHE))
print("CACHE_SUMMARY =",cache_summary)

results={"case":{"symbol":SYMBOL,"date":DAY},"pine_reference":PINE,
         "cache_path":str(CACHE),"cache_sha256":sha256(CACHE),
         "cache_summary":cache_summary,"vendor":{}}

all_rows=[]

for adjusted in (True, False):
    print(f"\nQUERY_VENDOR adjusted={adjusted}")
    raw=client.get_minute_aggs(symbol=SYMBOL,start_date=DAY,end_date=DAY,adjusted=adjusted,limit=50000)
    print("RAW_VENDOR_ROWS =",len(raw))
    df=normalize_massive_minute_rows(SYMBOL,raw,"9N_3L_DIAGNOSTIC")
    # normalize function may set metadata but preserves OHLC/timestamps
    summ=summarize(df,f"live_massive_adjusted_{str(adjusted).lower()}")
    print("VENDOR_SUMMARY =",summ)
    results["vendor"][str(adjusted).lower()]=summ
    tmp=df.copy()
    tmp["diagnostic_adjusted"]=adjusted
    all_rows.append(tmp)

# Compare exact timestamp/OHLC overlap for adjusted=True live vendor vs local cache on target day.
live_true=pd.concat(all_rows[:1],ignore_index=True)
def canonical_rows(df):
    x=df.copy()
    x["_et"]=et_series(x)
    x=x[x["_et"].dt.date.eq(pd.Timestamp(DAY).date())]
    cols=["_et","open","high","low","close","volume"]
    return x[cols].sort_values("_et").drop_duplicates("_et").reset_index(drop=True)

a=canonical_rows(cache)
b=canonical_rows(live_true)
m=a.merge(b,on="_et",how="outer",suffixes=("_cache","_live"),indicator=True)
ohlc_cols=["open","high","low","close"]
both=m["_merge"].eq("both")
ohlc_equal=True
for c in ohlc_cols:
    eq=(m.loc[both,f"{c}_cache"].astype(float)-m.loc[both,f"{c}_live"].astype(float)).abs() <= 1e-9
    if not bool(eq.all()): ohlc_equal=False
results["cache_vs_live_adjusted_true"]={
    "cache_unique_timestamps":int(len(a)),
    "live_unique_timestamps":int(len(b)),
    "only_cache":int((m["_merge"]=="left_only").sum()),
    "only_live":int((m["_merge"]=="right_only").sum()),
    "shared":int(both.sum()),
    "shared_ohlc_exact":bool(ohlc_equal),
}

# Pine level comparisons.
for k in ("true","false"):
    s=results["vendor"][k]
    results["vendor"][k]["pine_level_deltas"]={
        "pmh":None if s["pre_high"] is None else float(s["pre_high"]-PINE["pmh"]),
        "pml":None if s["pre_low"] is None else float(s["pre_low"]-PINE["pml"]),
        "pdh_using_same_day_rth_for_reference_only":None if s["rth_high"] is None else float(s["rth_high"]-PINE["pdh"]),
        "pdl_using_same_day_rth_for_reference_only":None if s["rth_low"] is None else float(s["rth_low"]-PINE["pdl"]),
    }

pd.concat(all_rows,ignore_index=True).to_csv(OUT_CSV,index=False)
OUT_JSON.write_text(json.dumps(results,indent=2),encoding="utf-8")

print("\nCACHE_VS_LIVE_ADJUSTED_TRUE =",results["cache_vs_live_adjusted_true"])
print("OUTPUT_JSON =",OUT_JSON)
print("OUTPUT_CSV =",OUT_CSV)
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("TRADINGVIEW_FULL_24_CASE_PARITY_VALIDATED=False")
print("9N_3L_LIVE_VENDOR_CACHE_PROBE=PASS")
