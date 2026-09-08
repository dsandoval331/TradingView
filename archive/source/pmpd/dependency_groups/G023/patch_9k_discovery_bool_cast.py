from pathlib import Path

p=Path("run_9k_classifier_discovery_v1.py")
s=p.read_text(encoding="utf-8")

old='        s=pd.to_numeric(frame[c],errors="coerce")'
new='        s=pd.to_numeric(frame[c],errors="coerce").astype(float)'

if old not in s:
    raise SystemExit("Expected prep_fit numeric conversion line not found; no changes made.")

s=s.replace(old,new,1)
p.write_text(s,encoding="utf-8")
print("9K_DISCOVERY_BOOL_CAST_PATCH=PASS")
