from pathlib import Path
import hashlib, re, sys

ROOT = Path.cwd()
SOURCE = ROOT / "PM_PD_Breakout_V4_9N_3F3_COMPACT_CSV_Parity_Export.pine"
OUTPUT = ROOT / "PM_PD_Breakout_V4_9N_3F4_DATA_WINDOW_CSV_Parity_Export.pine"
EXPECTED_SHA = "44a47d3d02bb18bcb6a624cc3a608782f7dd207f44ce01ae936f20656f8788b4"

if not SOURCE.exists():
    raise SystemExit(f"Missing 9N-3F3 source: {SOURCE}")

raw = SOURCE.read_bytes()
sha = hashlib.sha256(raw).hexdigest()

print("=== PMPD V5 9N-3F4 DATA-WINDOW CSV EXPORT PATCH ===")
print("SOURCE =", SOURCE)
print("SOURCE_SHA256 =", sha)

if sha != EXPECTED_SHA:
    raise SystemExit(f"9N-3F3 source SHA mismatch: {sha} != {EXPECTED_SHA}")

print("9N_3F3_SOURCE_SHA=PASS")

text = raw.decode("utf-8", errors="strict")

count_none = text.count("display = display.none")
if count_none == 0:
    raise SystemExit("No 9N-3F3 display.none export plots found.")

# This copy exists only to change export visibility. No series expressions change.
text2 = text.replace(
    'indicator("PM + PD V4 9N-3F3 COMPACT CSV PARITY",',
    'indicator("PM + PD V4 9N-3F4 DATA WINDOW CSV PARITY",',
    1
)
text2 = text2.replace("display = display.none", "display = display.data_window")

OUTPUT.write_text(text2, encoding="utf-8")
out_sha = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()

print("EXPORT_PLOTS_CHANGED =", count_none)
print("CHANGE=display.none -> display.data_window")
print("OUTPUT =", OUTPUT)
print("OUTPUT_SHA256 =", out_sha)
print("OUTPUT_LINE_COUNT =", len(text2.splitlines()))
print("SERIES_EXPRESSIONS_CHANGED=False")
print("V4_SIGNAL_LOGIC_CHANGED=False")
print("ORIGINAL_V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("TRADINGVIEW_PARITY_VALIDATED=False")
print("9N_3F4_PATCH_GATE=PASS")
