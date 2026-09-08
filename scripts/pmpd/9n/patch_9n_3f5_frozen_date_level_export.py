from pathlib import Path
import hashlib, re

ROOT = Path.cwd()
SOURCE = ROOT / "pine" / "pmpd" / "v4" / "parity_exports" / "PM_PD_Breakout_V4_9N_3F4_DATA_WINDOW_CSV_Parity_Export.pine"
OUTPUT = ROOT / "pine" / "pmpd" / "v4" / "parity_exports" / "PM_PD_Breakout_V4_9N_3F5_FROZEN_DATE_LEVEL_CSV_Parity_Export.pine"

EXPECTED_SHA = "e8bf58312402e990c66f0b0312099881a3e0e1ec1beeb42028c0f6f7e82138ae"

def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

print("=== PMPD V5 9N-3F5 FROZEN TARGET-DATE LEVEL EXPORT PATCH ===")

if not SOURCE.exists():
    raise SystemExit(f"Missing 9N-3F4 source: {SOURCE}")

src_sha = sha256(SOURCE)
print("SOURCE =", SOURCE)
print("SOURCE_SHA256 =", src_sha)
if src_sha != EXPECTED_SHA:
    raise SystemExit(f"9N-3F4 SHA mismatch: {src_sha}")
print("9N_3F4_SOURCE_SHA=PASS")

text = SOURCE.read_text(encoding="utf-8")

text = text.replace(
    'indicator("PM + PD V4 9N-3F4 DATA WINDOW CSV PARITY",',
    'indicator("PM + PD V4 9N-3F5 FROZEN DATE LEVEL CSV PARITY",',
    1
)

marker_match = re.search(r'(?m)^[^\n]*PMPD_PARITY_[^\n]*$', text)
if not marker_match:
    raise SystemExit("Could not locate PMPD_PARITY export block.")

freeze_block = """
//-----------------------------------------------------------------------------
// 9N-3F5 instrumentation only: freeze exact target-date levels on first
// completed confirmation candle for the selected target date.
//-----------------------------------------------------------------------------
var bool  n3f5DateLevelFrozen = false
var float n3f5FrozenPMH = na
var float n3f5FrozenPML = na
var float n3f5FrozenPDH = na
var float n3f5FrozenPDL = na

if parityCaptureAllowed and
   not n3f5DateLevelFrozen and
   newConfirmationCandle and
   f_paritySameNyDate(confTimeClose, parityTargetDate)

    n3f5DateLevelFrozen := true
    n3f5FrozenPMH := pmh
    n3f5FrozenPML := pml
    n3f5FrozenPDH := pdh
    n3f5FrozenPDL := pdl

"""

text = text[:marker_match.start()] + freeze_block + text[marker_match.start():]

mapping = {
    "PMPD_PARITY_DATE_PMH": "n3f5FrozenPMH",
    "PMPD_PARITY_DATE_PML": "n3f5FrozenPML",
    "PMPD_PARITY_DATE_PDH": "n3f5FrozenPDH",
    "PMPD_PARITY_DATE_PDL": "n3f5FrozenPDL",
}

changed = {}
for title, expr in mapping.items():
    pat1 = re.compile(rf'plot\(\s*[^,\n]+,\s*"{re.escape(title)}"')
    pat2 = re.compile(rf'plot\(\s*[^,\n]+,\s*title\s*=\s*"{re.escape(title)}"')
    if pat1.search(text):
        text, n = pat1.subn(f'plot({expr}, "{title}"', text, count=1)
    elif pat2.search(text):
        text, n = pat2.subn(f'plot({expr}, title = "{title}"', text, count=1)
    else:
        n = 0
    changed[title] = n

text += '\nplot(n3f5DateLevelFrozen ? 1.0 : 0.0, "PMPD_PARITY_DATE_LEVEL_FROZEN", display = display.data_window)\n'

if not all(v == 1 for v in changed.values()):
    print("REPLACEMENT_COUNTS =", changed)
    raise SystemExit("Could not replace all four frozen date-level export plots.")

OUTPUT.write_text(text, encoding="utf-8")
out_sha = sha256(OUTPUT)

print("REPLACEMENT_COUNTS =", changed)
print("FREEZE_RULE = first matching completed confirmation candle only")
print("OUTPUT =", OUTPUT)
print("OUTPUT_SHA256 =", out_sha)
print("OUTPUT_LINE_COUNT =", len(text.splitlines()))
print("V4_SIGNAL_LOGIC_CHANGED=False")
print("V4_SCORE_LOGIC_CHANGED=False")
print("V4_OUTCOME_LOGIC_CHANGED=False")
print("ORIGINAL_V4_MODIFIED=False")
print("V5_MODIFIED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("TRADINGVIEW_PARITY_VALIDATED=False")
print("9N_3F5_PATCH_GATE=PASS")



