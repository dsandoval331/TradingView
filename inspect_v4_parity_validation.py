from pathlib import Path
import re

src = Path.cwd() / "PM_PD_Breakout_V4_8H7_Parity_Capture_FULL.pine"
text = src.read_text(encoding="utf-8", errors="ignore")
lines = text.splitlines()

terms = [
    "parityCandidateId", "parityCaptureAllowed", "parityDateSeen",
    "INVALID CANDIDATE ID", "DATE_NOT_LOADED", "f_paritySameNyDate",
    "SET_1_01_EX", "parityTargetDate"
]

print("=== V4 PARITY VALIDATION INSPECTION ===")
for term in terms:
    print(f"\n===== {term} =====")
    found = False
    for i, line in enumerate(lines):
        if term.lower() in line.lower():
            found = True
            lo=max(0,i-8); hi=min(len(lines),i+12)
            print(f"\n--- lines {lo+1}-{hi} ---")
            for j in range(lo,hi):
                print(f"{j+1:5}: {lines[j]}")
    if not found:
        print("NOT FOUND")
