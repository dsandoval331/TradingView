from pathlib import Path
import pandas as pd
import hashlib

ROOT = Path.cwd()
SYMBOL = "VRTX"
DATA = ROOT / "data" / "second1m_alt_entry_cache_v1" / "partitions" / SYMBOL / f"{SYMBOL}_2026.parquet"
TARGET = pd.Timestamp("2026-07-01").date()
PINE = {"pmh":503.53,"pml":498.10,"pdh":502.71,"pdl":494.80}

print("=== PMPD V5 9N-3H LEVEL-SOURCE DIAGNOSTIC ===")
print("DATA =", DATA)
if not DATA.exists():
    raise SystemExit("MISSING_DATA")
print("DATA_SHA256 =", hashlib.sha256(DATA.read_bytes()).hexdigest())

df = pd.read_parquet(DATA)
print("ROWS =", len(df))
print("COLUMNS =", list(df.columns))

for c in ("source","adjusted","session","timeframe","cache_version"):
    if c in df.columns:
        print(f"{c.upper()}_VALUES =", df[c].dropna().astype(str).value_counts().head(20).to_dict())

# Build ET timestamps from explicit timestamp_et when possible.
et = pd.to_datetime(df["timestamp_et"])
if getattr(et.dt, "tz", None) is None:
    # cache column represents ET wall-clock
    df = df.copy()
    df["_et"] = et
else:
    df = df.copy()
    df["_et"] = et.dt.tz_convert("America/New_York")

df["_date"] = df["_et"].dt.date
df["_minute"] = df["_et"].dt.hour*60 + df["_et"].dt.minute

def extrema(day, lo_min, hi_min):
    x = df[(df["_date"] == day) & (df["_minute"] >= lo_min) & (df["_minute"] <= hi_min)]
    if x.empty:
        return None
    hi_i = x["high"].idxmax()
    lo_i = x["low"].idxmin()
    return {
        "rows": len(x),
        "high": float(x.loc[hi_i,"high"]),
        "high_time": str(x.loc[hi_i,"_et"]),
        "low": float(x.loc[lo_i,"low"]),
        "low_time": str(x.loc[lo_i,"_et"]),
        "first_time": str(x["_et"].min()),
        "last_time": str(x["_et"].max()),
    }

days = [pd.Timestamp("2026-06-26").date(), pd.Timestamp("2026-06-29").date(),
        pd.Timestamp("2026-06-30").date(), pd.Timestamp("2026-07-01").date()]
for d in days:
    print("\nDATE", d)
    print(" PRE_0400_0929 =", extrema(d,240,569))
    print(" RTH_0930_1559 =", extrema(d,570,959))
    print(" AH_1600_1959  =", extrema(d,960,1199))

# Find dates/session extrema closest to each Pine level around target.
print("\n=== CLOSEST RAW EXTREMA TO PINE LEVELS (±5 trading/calendar days) ===")
window = df[(df["_date"] >= pd.Timestamp("2026-06-24").date()) & (df["_date"] <= pd.Timestamp("2026-07-03").date())].copy()
records=[]
for d, g in window.groupby("_date"):
    for name,lo,hi in [("PRE",240,569),("RTH",570,959),("AH",960,1199)]:
        x=g[(g["_minute"]>=lo)&(g["_minute"]<=hi)]
        if x.empty: continue
        records.append({"date":d,"session":name,"high":float(x.high.max()),"low":float(x.low.min())})
rec=pd.DataFrame(records)
for k,v in PINE.items():
    col = "high" if k in ("pmh","pdh") else "low"
    z=rec.copy()
    z["abs_diff"]=(z[col]-v).abs()
    print(k, "PINE=", v)
    print(z.sort_values("abs_diff").head(8).to_string(index=False))

# Show target-date PRE and previous-day RTH raw top/bottom rows.
for d, name, lo, hi in [
    (pd.Timestamp("2026-07-01").date(),"TARGET_PRE",240,569),
    (pd.Timestamp("2026-06-30").date(),"PREV_RTH",570,959),
]:
    x=df[(df["_date"]==d)&(df["_minute"]>=lo)&(df["_minute"]<=hi)].copy()
    print(f"\n=== {name} TOP HIGHS ===")
    print(x.nlargest(10,"high")[["_et","open","high","low","close","volume","source","adjusted","session"]].to_string(index=False))
    print(f"\n=== {name} BOTTOM LOWS ===")
    print(x.nsmallest(10,"low")[["_et","open","high","low","close","volume","source","adjusted","session"]].to_string(index=False))

print("\n9N_3H_DIAGNOSTIC_COMPLETE=PASS")
