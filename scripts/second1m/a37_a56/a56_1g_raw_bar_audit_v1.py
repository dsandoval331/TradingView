from pathlib import Path
import pandas as pd
import json
import sys

CACHE_ROOT = Path("data/second1m_alt_entry_cache_v1")
MANIFEST = Path("a56_1e_ae2_parity_test_set.csv")
OUT_TXT = Path("a56_1g_raw_bar_audit.txt")
OUT_CSV = Path("a56_1g_raw_bar_audit.csv")

TARGETS = {
    ("TSLA", "2026-08-27"),
    ("WMT", "2026-08-27"),
}

def load_table(path: Path):
    ext = path.suffix.lower()
    if ext == ".parquet":
        return pd.read_parquet(path)
    if ext == ".csv":
        return pd.read_csv(path)
    if ext in (".jsonl", ".ndjson"):
        return pd.read_json(path, lines=True)
    return None

def normalize_columns(df: pd.DataFrame):
    ren = {}
    for c in df.columns:
        lc = c.lower().strip()
        aliases = {
            "ticker": "symbol",
            "sym": "symbol",
            "datetime": "timestamp",
            "timestamp_utc": "timestamp",
            "ts": "timestamp",
            "date": "trade_date",
        }
        if lc in aliases:
            ren[c] = aliases[lc]
        elif lc in {"symbol","trade_date","timestamp","open","high","low","close","volume"}:
            ren[c] = lc
    return df.rename(columns=ren)

def candidate_files():
    files = []
    for p in CACHE_ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".parquet",".csv",".jsonl",".ndjson"}:
            files.append(p)
    return files

if not MANIFEST.exists():
    raise SystemExit(f"Missing {MANIFEST}. Put this script in the TradingResearch root with the parity manifest.")

manifest = pd.read_csv(MANIFEST)
manifest["trade_date"] = manifest["trade_date"].astype(str)

rows_out = []
log = []

log.append("A56.1G — RAW 1-MINUTE BAR AUDIT")
log.append("="*100)
log.append(f"Cache root: {CACHE_ROOT}")
log.append(f"Manifest: {MANIFEST}")
log.append("Targets: TSLA 2026-08-27, WMT 2026-08-27")
log.append("")

found_any = False

for path in candidate_files():
    try:
        df = load_table(path)
    except Exception:
        continue
    if df is None or df.empty:
        continue

    df = normalize_columns(df)
    cols = set(df.columns)
    if not {"open","high","low","close"} <= cols:
        continue

    # Infer symbol from column or filename.
    if "symbol" not in df.columns:
        stem = path.stem.upper()
        inferred = None
        for sym, _ in TARGETS:
            if sym in stem:
                inferred = sym
                break
        if inferred:
            df["symbol"] = inferred
        else:
            continue

    # Need a timestamp to isolate 09:30/09:31 ET.
    if "timestamp" not in df.columns:
        continue

    ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    if ts.notna().sum() == 0:
        # Retry as timezone-naive, assuming already local.
        ts2 = pd.to_datetime(df["timestamp"], errors="coerce")
        if ts2.notna().sum() == 0:
            continue
        df["_ts_local"] = ts2
        df["_date_local"] = ts2.dt.date.astype(str)
        df["_time_local"] = ts2.dt.strftime("%H:%M")
        timezone_note = "timestamp parsed naive; treated as local in file"
    else:
        local = ts.dt.tz_convert("America/New_York")
        df["_ts_local"] = local
        df["_date_local"] = local.dt.date.astype(str)
        df["_time_local"] = local.dt.strftime("%H:%M")
        timezone_note = "timestamp parsed UTC and converted to America/New_York"

    for sym, dt in TARGETS:
        sub = df[
            df["symbol"].astype(str).str.upper().eq(sym)
            & df["_date_local"].eq(dt)
            & df["_time_local"].isin(["09:30","09:31"])
        ].copy()

        if sub.empty:
            continue

        found_any = True
        log.append(f"SOURCE FILE: {path}")
        log.append(f"{sym} {dt} — {timezone_note}")

        ref = manifest[
            manifest["symbol"].astype(str).str.upper().eq(sym)
            & manifest["trade_date"].eq(dt)
        ]
        if ref.empty:
            log.append("Manifest row not found.")
            continue
        ref = ref.iloc[0]

        for _, r in sub.sort_values("_ts_local").iterrows():
            hhmm = r["_time_local"]
            prefix = "c1" if hhmm == "09:30" else "c2"

            out = {
                "symbol": sym,
                "trade_date": dt,
                "bar": prefix.upper(),
                "ny_time": hhmm,
                "source_file": str(path),
                "raw_open": r["open"],
                "raw_high": r["high"],
                "raw_low": r["low"],
                "raw_close": r["close"],
                "manifest_open": ref.get(f"{prefix}_open"),
                "manifest_high": ref.get(f"{prefix}_high"),
                "manifest_low": ref.get(f"{prefix}_low"),
                "manifest_close": ref.get(f"{prefix}_close"),
            }

            for fld in ("open","high","low","close"):
                a = pd.to_numeric(pd.Series([out[f"raw_{fld}"]]), errors="coerce").iloc[0]
                b = pd.to_numeric(pd.Series([out[f"manifest_{fld}"]]), errors="coerce").iloc[0]
                out[f"delta_{fld}"] = None if pd.isna(a) or pd.isna(b) else float(a-b)

            rows_out.append(out)

            log.append(
                f"  {prefix.upper()} {hhmm} NY | "
                f"RAW O/H/L/C={r['open']}/{r['high']}/{r['low']}/{r['close']} | "
                f"MANIFEST={ref.get(f'{prefix}_open')}/{ref.get(f'{prefix}_high')}/"
                f"{ref.get(f'{prefix}_low')}/{ref.get(f'{prefix}_close')}"
            )
        log.append("")

if not found_any:
    log.append("NO MATCHING 09:30/09:31 NY BARS FOUND.")
    log.append("")
    log.append("Next diagnostic:")
    log.append("Run the following and share the output:")
    log.append(r'Get-ChildItem ".\data\second1m_alt_entry_cache_v1" -Recurse -File | Select-Object -First 80 FullName,Length')
    log.append("")
    log.append("This means the audit script could not infer the cache schema/file layout; it does NOT imply the data is missing.")

if rows_out:
    out_df = pd.DataFrame(rows_out)
    out_df.to_csv(OUT_CSV, index=False)
    log.append("SUMMARY")
    log.append("-"*100)
    log.append(out_df.to_string(index=False))
else:
    pd.DataFrame().to_csv(OUT_CSV, index=False)

OUT_TXT.write_text("\n".join(log), encoding="utf-8")

print("\n".join(log))
print(f"\nWrote: {OUT_TXT}")
print(f"Wrote: {OUT_CSV}")
