from pathlib import Path

p = Path("derive_and_certify_dp4_structural_clearance.py")
s = p.read_text(encoding="utf-8")

old = (
'base_cols = [c for c in v.columns if c != "event_vwap_loss_after_structural_clearance"]\n'
'left = v[["decision_id"] + base_cols].copy()\n'
'right = d[["decision_id"] + base_cols].copy()'
)

new = (
'base_cols = [c for c in v.columns if c not in {"decision_id", "event_vwap_loss_after_structural_clearance"}]\n'
'left = v[["decision_id"] + base_cols].copy()\n'
'right = d[["decision_id"] + base_cols].copy()'
)

if old not in s:
    raise SystemExit("Expected source-field comparison block not found; no changes made.")

p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("DP4_DUPLICATE_ID_PATCH_APPLIED=PASS")
