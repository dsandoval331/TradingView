from pathlib import Path

ROOT=Path(".")
NEEDLES=[
    "vwap_distance_change_pp__bucket",
    "pd.qcut",
    "qcut(",
]
print("="*132)
print("A51.3G - TRACE UPSTREAM A39 BUCKET CREATION")
print("="*132)

for p in ROOT.rglob("*.py"):
    s=str(p).lower()
    if any(x in s for x in ["\\.venv\\","/site-packages/","\\site-packages\\","__pycache__"]):
        continue
    try: txt=p.read_text(encoding="utf-8",errors="ignore")
    except Exception: continue
    lines=txt.splitlines()
    idxs=[i for i,l in enumerate(lines) if "vwap_distance_change_pp__bucket" in l]
    # also include likely C2 predictor builders with qcut logic
    if not idxs and ("c2_predict" in p.name.lower() or "alt_entry" in p.name.lower()):
        idxs=[i for i,l in enumerate(lines) if "qcut(" in l and ("bucket" in l or "__bucket" in l)]
    if not idxs: continue
    print(f"\nFILE: {p}")
    shown=set()
    for i in idxs:
        lo=max(0,i-45); hi=min(len(lines),i+46)
        if (lo,hi) in shown: continue
        shown.add((lo,hi))
        print(f"\n--- lines {lo+1}-{hi} ---")
        for j in range(lo,hi):
            print(f"{j+1:5d}: {lines[j]}")
print("\nRESULT: UPSTREAM BUCKET-CREATION TRACE COMPLETE.")
