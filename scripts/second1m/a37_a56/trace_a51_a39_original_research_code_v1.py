from pathlib import Path

ROOT=Path(".")
NEEDLES=[
    "a39_transition_frozen_quintile_performance_v1",
    "vwap_distance_change_pp__frozen_quintile",
    "a39_frozen_transition_bucket_inventory_v1",
]
print("="*132)
print("A51.3F - TRACE ORIGINAL A39 RESEARCH IMPLEMENTATION")
print("="*132)

hits=[]
for p in ROOT.rglob("*.py"):
    # avoid virtual environments / caches
    s=str(p).lower()
    if any(x in s for x in ["\\.venv\\","/site-packages/","\\site-packages\\","__pycache__"]):
        continue
    try:
        txt=p.read_text(encoding="utf-8",errors="ignore")
    except Exception:
        continue
    found=[n for n in NEEDLES if n in txt]
    if found:
        hits.append((p,txt,found))

print(f"Matching Python files: {len(hits)}")
for p,txt,found in hits:
    print(f"\nFILE: {p}")
    print("MATCHED:", " | ".join(found))
    lines=txt.splitlines()
    idxs=[i for i,line in enumerate(lines) if any(n in line for n in NEEDLES)]
    shown=set()
    for i in idxs:
        lo=max(0,i-35); hi=min(len(lines),i+36)
        key=(lo,hi)
        if key in shown: continue
        shown.add(key)
        print(f"\n--- lines {lo+1}-{hi} ---")
        for j in range(lo,hi):
            print(f"{j+1:5d}: {lines[j]}")

print("\nRESULT: TRACE COMPLETE.")
print("No research values changed. No outcomes analyzed.")
