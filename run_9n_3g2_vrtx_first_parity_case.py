from pathlib import Path
import hashlib, json, sys
import pandas as pd

ROOT = Path.cwd()
SYMBOL = "VRTX"
TARGET_DATE = pd.Timestamp("2026-07-01").date()

ENGINE = ROOT / "v4_parity_engine_v2.py"
DATA = ROOT / "data" / "second1m_alt_entry_cache_v1" / "partitions" / SYMBOL / f"{SYMBOL}_2026.parquet"
REPORT = ROOT / "pmpd_v5_9n_3g2_vrtx_2026-07-01_parity_report.json"
SIGNALS_CSV = ROOT / "pmpd_v5_9n_3g2_vrtx_2026_signals.csv"

EXPECTED_ENGINE_SHA256 = "cab75475f0bf4f4a9d8cf86561d9959957d660aeae7926769e26c53599be4b22"

PINE = {
    "date_loaded": True,
    "signal_count": 0,
    "pmh": 503.53,
    "pml": 498.10,
    "pdh": 502.71,
    "pdl": 494.80,
}

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def close_enough(a, b, tol=1e-9):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol

print("=== PMPD V5 9N-3G2 FIRST PINE ↔ PYTHON PARITY CASE ===")
print("CASE =", SYMBOL, TARGET_DATE)
print("PINE_OBSERVED = DATE_LOADED / NO_SIGNAL")
print("PINE_LEVELS =", {k: PINE[k] for k in ("pmh","pml","pdh","pdl")})

if not ENGINE.exists():
    raise SystemExit(f"Missing engine: {ENGINE}")
engine_sha = sha256(ENGINE)
print("ENGINE =", ENGINE)
print("ENGINE_SHA256 =", engine_sha)
if engine_sha != EXPECTED_ENGINE_SHA256:
    raise SystemExit("ENGINE_SHA_MISMATCH")
print("ENGINE_SHA=PASS")

if not DATA.exists():
    raise SystemExit(f"Missing located VRTX partition: {DATA}")
print("DATA =", DATA)
print("DATA_SHA256 =", sha256(DATA))

from v4_parity_engine_v2 import evaluate_v4_signals, build_daily_levels

raw = pd.read_parquet(DATA)
print("RAW_ROWS =", len(raw))
print("RAW_COLUMNS =", list(raw.columns))

# Flexible target-date coverage check.
if "timestamp_et" in raw.columns:
    et = pd.to_datetime(raw["timestamp_et"])
elif "timestamp_utc" in raw.columns:
    et = pd.to_datetime(raw["timestamp_utc"], utc=True).dt.tz_convert("America/New_York")
elif "timestamp" in raw.columns:
    ts = pd.to_datetime(raw["timestamp"])
    if getattr(ts.dt, "tz", None) is None:
        raise SystemExit("TIMESTAMP_COLUMN_IS_TZ_NAIVE_AND_AMBIGUOUS")
    et = ts.dt.tz_convert("America/New_York")
else:
    raise SystemExit("NO_SUPPORTED_TIMESTAMP_COLUMN")

dates = set(et.dt.date)
if TARGET_DATE not in dates:
    raise SystemExit("TARGET_DATE_NOT_IN_PARTITION")
print("TARGET_DATE_PRESENT=PASS")

signals = evaluate_v4_signals(raw, symbol=SYMBOL)
signals.to_csv(SIGNALS_CSV, index=False)

if signals.empty:
    target = signals.copy()
else:
    date_col = None
    for candidate in ("trade_date", "signal_date", "date"):
        if candidate in signals.columns:
            date_col = candidate
            break
    if date_col is None:
        raise SystemExit(f"NO_SIGNAL_DATE_COLUMN: {list(signals.columns)}")
    target = signals[signals[date_col].astype(str) == str(TARGET_DATE)].copy()

python_count = int(len(target))

levels = build_daily_levels(raw)
if TARGET_DATE not in levels.index:
    # tolerate string/date-like index
    hit = [idx for idx in levels.index if str(idx)[:10] == str(TARGET_DATE)]
    if not hit:
        raise SystemExit("TARGET_DATE_NOT_IN_DAILY_LEVELS")
    lv = levels.loc[hit[0]]
else:
    lv = levels.loc[TARGET_DATE]

python_levels = {}
for key in ("pmh","pml","pdh","pdl"):
    val = lv[key]
    python_levels[key] = None if pd.isna(val) else float(val)

count_match = python_count == PINE["signal_count"]
level_matches = {k: close_enough(python_levels[k], PINE[k]) for k in python_levels}
levels_match = all(level_matches.values())

# First no-signal case gate requires both the signal count and common levels to agree.
case_gate = "PASS" if count_match and levels_match else "FAIL"

signal_rows = []
for _, r in target.iterrows():
    signal_rows.append({k: (None if pd.isna(r[k]) else str(r[k])) for k in target.columns})

report = {
    "protocol_step": "9N-3G2-FIRST-PINE-PYTHON-PARITY",
    "symbol": SYMBOL,
    "target_date": str(TARGET_DATE),
    "pine_observed": PINE,
    "python_reconstruction": {
        "signal_count": python_count,
        "daily_levels": python_levels,
        "signals": signal_rows,
    },
    "parity_checks": {
        "signal_count_match": count_match,
        "level_matches": level_matches,
        "all_four_levels_match": levels_match,
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
print("PINE_SIGNAL_COUNT =", PINE["signal_count"])
print("SIGNAL_COUNT_MATCH =", count_match)
print("PYTHON_LEVELS =", python_levels)
print("LEVEL_MATCHES =", level_matches)
print("ALL_FOUR_LEVELS_MATCH =", levels_match)
if signal_rows:
    print("PYTHON_TARGET_SIGNALS =", signal_rows)
print("REPORT =", REPORT)
print("ALL_2026_SIGNALS_CSV =", SIGNALS_CSV)
print("V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("TRADINGVIEW_FULL_24_CASE_PARITY_VALIDATED=False")
print("9N_3G2_FIRST_CASE_GATE=" + case_gate)

if case_gate != "PASS":
    sys.exit(2)
