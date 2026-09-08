from pathlib import Path
import pandas as pd
import json

ROOT = Path("data/second1m_alt_entry_research_v1")
OUT_CSV = Path("a56_1e_ae2_parity_test_set.csv")
OUT_TXT = Path("a56_1e_ae2_parity_test_set.txt")

def read_any(path):
    s = path.suffix.lower()
    if s == ".csv":
        return pd.read_csv(path)
    if s == ".parquet":
        return pd.read_parquet(path)
    if s in {".jsonl", ".ndjson"}:
        return pd.read_json(path, lines=True)
    return None

def find_candidate_files():
    candidates = []
    terms = ("ae2", "event", "population", "alternative", "alt_entry")
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".csv", ".parquet", ".jsonl", ".ndjson"}:
            name = p.name.lower()
            if any(t in name for t in terms):
                candidates.append(p)
    return candidates

required_core = {
    "symbol", "trade_date", "direction",
    "c1_open", "c1_close", "c1_vwap",
    "c2_open", "c2_high", "c2_low", "c2_close", "c2_vwap"
}

best = None
for p in find_candidate_files():
    try:
        df = read_any(p)
    except Exception:
        continue
    if df is None or df.empty:
        continue
    cols = set(df.columns)
    score = len(required_core & cols)
    if "architecture" in cols:
        score += 5
    if "ae2_reclaim" in cols:
        score += 5
    if best is None or score > best[0]:
        best = (score, p, df)

if best is None:
    raise SystemExit("No candidate AE2 dataset found under data/second1m_alt_entry_research_v1")

score, source, df = best
print(f"Using source: {source}")
print(f"Rows: {len(df):,}")

# Normalize trade date.
df = df.copy()
df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date.astype(str)

# Positive AE2 rows.
if "architecture" in df.columns:
    pos = df[df["architecture"].astype(str).str.upper().eq("AE2_RECLAIM")].copy()
elif "ae2_reclaim" in df.columns:
    pos = df[df["ae2_reclaim"].fillna(False).astype(bool)].copy()
else:
    # If the chosen file itself is an AE2-only event ledger.
    pos = df.copy()

# Prefer deterministic spread across direction and time.
pos = pos.sort_values(["trade_date", "symbol"]).copy()

def choose_spread(frame, n):
    if frame.empty:
        return frame
    if len(frame) <= n:
        return frame
    idx = [round(i) for i in pd.Series(range(n)).map(lambda k: k * (len(frame)-1) / (n-1))]
    return frame.iloc[idx]

bull = choose_spread(pos[pos["direction"].astype(str).str.upper().eq("BULL")], 5)
bear = choose_spread(pos[pos["direction"].astype(str).str.upper().eq("BEAR")], 5)
test = pd.concat([bull, bear], ignore_index=True)

# Recompute expected frozen flags for transparency.
test["expected_c2_direction_aligned"] = (
    ((test["direction"].str.upper() == "BULL") & (test["c2_close"] > test["c2_open"])) |
    ((test["direction"].str.upper() == "BEAR") & (test["c2_close"] < test["c2_open"]))
)
test["expected_c2_vwap_close_ok"] = (
    ((test["direction"].str.upper() == "BULL") & (test["c2_close"] > test["c2_vwap"])) |
    ((test["direction"].str.upper() == "BEAR") & (test["c2_close"] < test["c2_vwap"]))
)
test["expected_c2_touch_or_cross"] = (
    ((test["direction"].str.upper() == "BULL") & (test["c2_low"] <= test["c2_vwap"])) |
    ((test["direction"].str.upper() == "BEAR") & (test["c2_high"] >= test["c2_vwap"]))
)
test["expected_ae2"] = (
    test["expected_c2_direction_aligned"] &
    test["expected_c2_vwap_close_ok"] &
    test["expected_c2_touch_or_cross"]
)

if "entry_price" not in test.columns:
    test["entry_price"] = test["c2_close"]

wanted = [
    "symbol", "trade_date", "direction",
    "c1_open", "c1_high", "c1_low", "c1_close", "c1_vwap",
    "c2_open", "c2_high", "c2_low", "c2_close", "c2_vwap",
    "expected_c2_direction_aligned",
    "expected_c2_vwap_close_ok",
    "expected_c2_touch_or_cross",
    "expected_ae2", "entry_price"
]
wanted = [c for c in wanted if c in test.columns]
test = test[wanted].sort_values(["trade_date", "symbol"]).reset_index(drop=True)
test.to_csv(OUT_CSV, index=False)

with OUT_TXT.open("w", encoding="utf-8") as f:
    f.write("A56.1E — FROZEN AE2 PINE ↔ PYTHON PARITY TEST SET\n")
    f.write("=" * 100 + "\n")
    f.write(f"Source: {source}\n")
    f.write(f"Positive AE2 population found: {len(pos):,}\n")
    f.write(f"Selected tests: {len(test)}\n\n")
    f.write(test.to_string(index=False))
    f.write("\n\nPASS RULE\n")
    f.write("For every selected row, Pine must match direction, C1/C2 VWAP values to displayed precision, ")
    f.write("all three C2 flags, final AE2 state, and C2-close entry. Investigate every mismatch; do not tune.\n")

print(f"Wrote {OUT_CSV}")
print(f"Wrote {OUT_TXT}")
print("\nSelected test set:")
print(test.to_string(index=False))
