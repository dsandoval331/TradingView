from pathlib import Path
import sys
try: sys.stdout.reconfigure(encoding="utf-8",errors="backslashreplace")
except Exception: pass

ROOT=Path(".")
NEEDLES=[
    "a39_transition_frozen_quintile_performance_v1.csv",
    "a39_transition_frozen_quintile_direction_v1.csv",
    "vwap_distance_change_pp__frozen_quintile",
]
print("="*132)
print("A51.3I - TRACE A39 SCREEN'S OWN FROZEN-QUINTILE CREATION")
print("="*132)

hits=[]
for p in ROOT.rglob("*.py"):
    s=str(p).lower()
    if any(x in s for x in ["\\.venv\\","/site-packages/","\\site-packages\\","__pycache__"]): continue
    try: lines=p.read_text(encoding="utf-8",errors="ignore").splitlines()
    except Exception: continue
    idx=[i for i,l in enumerate(lines) if any(n in l for n in NEEDLES)]
    if idx: hits.append((p,lines,idx))

print("Matching files:",len(hits))
for p,lines,idx in hits:
    print(f"\nFILE: {p}")
    # print broad contexts, especially function beginning and qcut/cut/rank operations
    relevant=set(idx)
    relevant.update(i for i,l in enumerate(lines) if any(t in l for t in [
        "qcut(", "pd.cut(", "__frozen_quintile", "research_period", "DISCOVERY",
        "PREFERRED", "session_level_clear_state", "market_prior_5d_consensus"
    ]))
    blocks=[]
    for i in sorted(relevant):
        lo=max(0,i-35); hi=min(len(lines),i+46)
        if blocks and lo<=blocks[-1][1]: blocks[-1]=(blocks[-1][0],max(blocks[-1][1],hi))
        else: blocks.append((lo,hi))
    for lo,hi in blocks:
        print(f"\n--- lines {lo+1}-{hi} ---")
        for j in range(lo,hi): print(f"{j+1:5d}: {lines[j]}")

print("\nRESULT: A39 SCREEN TRACE COMPLETE.")
