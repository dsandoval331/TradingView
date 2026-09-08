from pathlib import Path
import os

ROOT = Path.cwd()
patterns = [
    "**/VRTX/2026.parquet",
    "**/*VRTX*2026*.parquet",
    "**/2026/**/*VRTX*.parquet",
    "**/*VRTX*.parquet",
]

seen = set()
matches = []

for pat in patterns:
    for f in ROOT.glob(pat):
        try:
            rp = f.resolve()
        except Exception:
            rp = f
        if rp in seen:
            continue
        seen.add(rp)
        try:
            size = f.stat().st_size
        except Exception:
            size = -1
        matches.append((str(f), size))

print("=== VRTX MASSIVE PARTITION LOCATOR ===")
print("ROOT =", ROOT)
if not matches:
    print("NO_MATCHES_FOUND")
else:
    for i, (path, size) in enumerate(matches, 1):
        print(f"[{i}] {path}")
        print(f"    size_bytes={size}")
