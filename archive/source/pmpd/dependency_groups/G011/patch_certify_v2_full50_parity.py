from pathlib import Path

p = Path("certify_v2_full50.py")
s = p.read_text(encoding="utf-8")

old = (
'j = v2[["decision_id","rth_vwap_at_decision"]].merge(v1[["decision_id",v1_vwap_col]], on="decision_id", how="inner", suffixes=("_v2","_v1"))\n'
'a = pd.to_numeric(j["rth_vwap_at_decision"], errors="coerce")\n'
'b = pd.to_numeric(j[v1_vwap_col], errors="coerce")'
)

new = (
'left = v2[["decision_id","rth_vwap_at_decision"]].rename(columns={"rth_vwap_at_decision":"rth_vwap_at_decision_v2"})\n'
'right = v1[["decision_id",v1_vwap_col]].rename(columns={v1_vwap_col:"rth_vwap_at_decision_v1"})\n'
'j = left.merge(right, on="decision_id", how="inner")\n'
'a = pd.to_numeric(j["rth_vwap_at_decision_v2"], errors="coerce")\n'
'b = pd.to_numeric(j["rth_vwap_at_decision_v1"], errors="coerce")'
)

if old not in s:
    raise SystemExit("Expected parity block not found; no changes made.")

p.write_text(s.replace(old, new), encoding="utf-8")
print("PATCH_APPLIED=PASS")
