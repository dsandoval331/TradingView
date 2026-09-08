from pathlib import Path

p = Path("derive_and_certify_dp4_structural_clearance.py")
s = p.read_text(encoding="utf-8")

old = 'd["event_last_vwap_loss_timestamp_utc"] = pd.NaT'
new = 'd["event_last_vwap_loss_timestamp_utc"] = pd.Series(pd.NaT, index=d.index, dtype="datetime64[ns, UTC]")'

if old not in s:
    raise SystemExit("Expected timestamp initialization line not found; no changes made.")

p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("DP4_TZ_PATCH_APPLIED=PASS")
