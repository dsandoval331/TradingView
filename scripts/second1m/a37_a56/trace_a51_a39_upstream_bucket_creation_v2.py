from pathlib import Path
import sys

# Avoid Windows cp1252 failures when source contains arrows or other Unicode.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass

ROOT=Path(".")
print("="*132)
print("A51.3G V2 - TRACE ACTUAL UPSTREAM CREATION OF vwap_distance_change_pp__bucket")
print("="*132)

hits=[]
for p in ROOT.rglob("*.py"):
    s=str(p).lower()
    if any(x in s for x in ["\\.venv\\","/site-packages/","\\site-packages\\","__pycache__"]):
        continue
    try:
        lines=p.read_text(encoding="utf-8",errors="ignore").splitlines()
    except Exception:
        continue

    for i,line in enumerate(lines):
        if "vwap_distance_change_pp__bucket" not in line:
            continue

        # Creation-like occurrences only, not simple reads such as b="...__bucket".
        nearby="\n".join(lines[max(0,i-25):min(len(lines),i+26)])
        creation_tokens=["qcut(", "cut(", "__bucket] =", "__bucket\"] =", "bucket_cols", "bucket_features",
                         "pd.qcut", "pd.cut", "assign(", "transform("]
        if any(tok in nearby for tok in creation_tokens):
            hits.append((p,i,lines))

print(f"Creation-like hits: {len(hits)}")
seen=set()
for p,i,lines in hits:
    key=(str(p),i)
    if key in seen: continue
    seen.add(key)
    lo=max(0,i-55); hi=min(len(lines),i+56)
    print(f"\nFILE: {p}")
    print(f"--- lines {lo+1}-{hi} ---")
    for j in range(lo,hi):
        print(f"{j+1:5d}: {lines[j]}")

print("\nSECONDARY SEARCH: generic bucket-generation helpers in C2 predictor builders")
for p in ROOT.rglob("*.py"):
    if "c2_predict" not in p.name.lower(): continue
    try: lines=p.read_text(encoding="utf-8",errors="ignore").splitlines()
    except Exception: continue
    idx=[i for i,l in enumerate(lines) if "qcut(" in l or ("__bucket" in l and ("for " in l or "=" in l))]
    if idx:
        print(f"\nFILE: {p}")
        for i in idx:
            lo=max(0,i-25); hi=min(len(lines),i+26)
            print(f"--- lines {lo+1}-{hi} ---")
            for j in range(lo,hi): print(f"{j+1:5d}: {lines[j]}")

print("\nRESULT: TRACE COMPLETE.")
