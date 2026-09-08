from pathlib import Path
import hashlib, json, sys
import pandas as pd

ROOT = Path.cwd()
SYMBOL = "VRTX"
TARGET_DATE = pd.Timestamp("2026-07-01").date()

ENGINE = ROOT / "v4_parity_engine_v2.py"
DATA = ROOT / "market_cache" / "MARKET_CACHE_V1" / "1m" / SYMBOL / "2026.parquet"
REPORT = ROOT / "pmpd_v5_9n_3g_vrtx_2026-07-01_parity_report.json"
SIGNALS_CSV = ROOT / "pmpd_v5_9n_3g_vrtx_2026_signals.csv"

EXPECTED_ENGINE_SHA256 = "cab75475f0bf4f4a9d8cf86561d9959957d660aeae7926769e26c53599be4b22"
PINE_OBSERVED_SIGNAL_COUNT = 0
PINE_OBSERVED_DATE_LOADED = True

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

print("=== PMPD V5 9N-3G FIRST PINE ↔ PYTHON PARITY CASE ===")
print("CASE =", SYMBOL, TARGET_DATE)
print("PINE_OBSERVED = DATE_LOADED / NO_SIGNAL")

if not ENGINE.exists():
    raise SystemExit(f"Missing engine: {ENGINE}")
engine_sha = sha256(ENGINE)
print("ENGINE =", ENGINE)
print("ENGINE_SHA256 =", engine_sha)
if engine_sha != EXPECTED_ENGINE_SHA256:
    raise SystemExit("ENGINE_SHA_MISMATCH")
print("ENGINE_SHA=PASS")

if not DATA.exists():
    raise SystemExit(f"Missing canonical Massive partition: {DATA}")
print("DATA =", DATA)
print("DATA_SHA256 =", sha256(DATA))

from v4_parity_engine_v2 import evaluate_v4_signals, build_daily_levels

raw = pd.read_parquet(DATA)
print("RAW_ROWS =", len(raw))
print("RAW_COLUMNS =", list(raw.columns))

# Enforce canonical symbol and target-date coverage.
if "symbol" in raw.columns:
    syms = sorted(set(raw["symbol"].dropna().astype(str)))
    if syms != [SYMBOL]:
        raise SystemExit(f"SYMBOL_CONTENT_MISMATCH: {syms[:10]}")

if "timestamp_et" in raw.columns:
    et = pd.to_datetime(raw["timestamp_et"])
else:
    et = pd.to_datetime(raw["timestamp_utc"], utc=True).dt.tz_convert("America/New_York")
dates = set(et.dt.date)
if TARGET_DATE not in dates:
    raise SystemExit("TARGET_DATE_NOT_IN_MASSIVE_PARTITION")
print("MASSIVE_TARGET_DATE_PRESENT=PASS")

signals = evaluate_v4_signals(raw, symbol=SYMBOL)
signals.to_csv(SIGNALS_CSV, index=False)

if signals.empty:
    target = signals.copy()
else:
    target = signals[signals["trade_date"].astype(str) == str(TARGET_DATE)].copy()

python_count = int(len(target))

levels = build_daily_levels(raw)
level_record = None
if TARGET_DATE in levels.index:
    lv = levels.loc[TARGET_DATE]
    level_record = {
        "pmh": None if pd.isna(lv["pmh"]) else float(lv["pmh"]),
        "pml": None if pd.isna(lv["pml"]) else float(lv["pml"]),
        "pdh": None if pd.isna(lv["pdh"]) else float(lv["pdh"]),
        "pdl": None if pd.isna(lv["pdl"]) else float(lv["pdl"]),
        "bull_final": None if pd.isna(lv["bull_final"]) else float(lv["bull_final"]),
        "bear_final": None if pd.isna(lv["bear_final"]) else float(lv["bear_final"]),
    }

signal_rows = []
for _, r in target.iterrows():
    signal_rows.append({
        "direction": str(r.get("direction")),
        "signal_timestamp_et": str(r.get("signal_timestamp_et")),
        "reference_price": float(r.get("reference_price")),
        "grade": str(r.get("grade")),
        "profile": str(r.get("profile")),
        "priority": str(r.get("priority")),
        "production_alert": bool(r.get("production_alert")),
    })

count_match = python_count == PINE_OBSERVED_SIGNAL_COUNT
case_gate = "PASS" if count_match else "FAIL"

report = {
    "protocol_step": "9N-3G-FIRST-PINE-PYTHON-PARITY",
    "symbol": SYMBOL,
    "target_date": str(TARGET_DATE),
    "pine_observed": {
        "date_loaded": PINE_OBSERVED_DATE_LOADED,
        "signal_count": PINE_OBSERVED_SIGNAL_COUNT,
        "status": "NO_SIGNAL",
    },
    "python_reconstruction": {
        "signal_count": python_count,
        "signals": signal_rows,
        "daily_levels": level_record,
    },
    "parity_checks": {
        "signal_count_match": count_match,
    },
    "gate": case_gate,
    "engine_sha256": engine_sha,
    "data_path": str(DATA),
    "data_sha256": sha256(DATA),
    "v4_modified": False,
    "v5_modified": False,
    "production_rule_authorized": False,
    "tradingview_full_24_case_parity_validated": False,
}

REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("PYTHON_TARGET_SIGNAL_COUNT =", python_count)
if signal_rows:
    print("PYTHON_TARGET_SIGNALS:")
    for s in signal_rows:
        print(" ", s)
print("PYTHON_DAILY_LEVELS =", level_record)
print("PINE_SIGNAL_COUNT =", PINE_OBSERVED_SIGNAL_COUNT)
print("SIGNAL_COUNT_MATCH =", count_match)
print("REPORT =", REPORT)
print("ALL_2026_SIGNALS_CSV =", SIGNALS_CSV)
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("TRADINGVIEW_FULL_24_CASE_PARITY_VALIDATED=False")
print("9N_3G_FIRST_CASE_GATE=" + case_gate)

if not count_match:
    sys.exit(2)
