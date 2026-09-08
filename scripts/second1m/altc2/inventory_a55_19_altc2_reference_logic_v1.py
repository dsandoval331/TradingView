from pathlib import Path

ROOT = Path(".")
OUT = Path("a55_19_altc2_reference_logic_inventory.txt")

KEYS = [
    "c2_no_touch_ok",
    "c2_vwap_touch_or_cross",
    "c1_direction_aligned",
    "c1_vwap_close_ok",
    "c2_direction_aligned",
    "c2_vwap_close_ok",
    "c3_directional_confirmation",
    "decision_candle",
    "entry_timestamp",
    "entry_price",
    "c2_close",
    "architecture",
    "Alternative C2",
    "ALT_C2",
    "AE2",
]

EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    "data", ".pytest_cache", ".mypy_cache"
}

def iter_py_files(root):
    for p in root.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        yield p

def score_text(text):
    hits = {}
    score = 0
    low = text.lower()
    core = {
        "c2_no_touch_ok", "c2_vwap_touch_or_cross",
        "c1_direction_aligned", "c2_direction_aligned",
        "entry_price", "decision_candle"
    }
    for key in KEYS:
        n = low.count(key.lower())
        if n:
            hits[key] = n
            score += n * (5 if key in core else 2)
    return score, hits

def context_blocks(lines, patterns, radius=8):
    indexes = set()
    for i, line in enumerate(lines):
        ll = line.lower()
        if any(p.lower() in ll for p in patterns):
            for j in range(max(0, i-radius), min(len(lines), i+radius+1)):
                indexes.add(j)
    if not indexes:
        return []
    blocks = []
    vals = sorted(indexes)
    start = prev = vals[0]
    for idx in vals[1:]:
        if idx == prev + 1:
            prev = idx
        else:
            blocks.append((start, prev))
            start = prev = idx
    blocks.append((start, prev))
    return blocks

ranked = []
for p in iter_py_files(ROOT):
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    score, hits = score_text(text)
    if score:
        ranked.append((score, p, hits, text))

ranked.sort(key=lambda x: (-x[0], str(x[1]).lower()))

with OUT.open("w", encoding="utf-8") as f:
    f.write("="*120 + "\n")
    f.write("A55.19 - ALTERNATIVE C2 REFERENCE-LOGIC REPOSITORY INVENTORY\n")
    f.write("="*120 + "\n\n")
    f.write(f"Python files with relevant hits: {len(ranked)}\n\n")

    f.write("TOP CANDIDATE FILES\n")
    f.write("-"*120 + "\n")
    for score, p, hits, _ in ranked[:30]:
        f.write(f"SCORE {score:4d} | {p}\n")
        f.write("  " + ", ".join(f"{k}={v}" for k, v in hits.items()) + "\n")

    f.write("\n\nDETAILED CONTEXT FROM TOP 12 FILES\n")
    f.write("="*120 + "\n")
    focus = [
        "c2_no_touch_ok", "c2_vwap_touch_or_cross",
        "c1_direction_aligned", "c1_vwap_close_ok",
        "c2_direction_aligned", "c2_vwap_close_ok",
        "c3_directional_confirmation", "decision_candle",
        "entry_price", "entry_timestamp"
    ]

    for score, p, hits, text in ranked[:12]:
        lines = text.splitlines()
        f.write(f"\nFILE: {p}\nSCORE: {score}\n")
        f.write("-"*120 + "\n")
        blocks = context_blocks(lines, focus, radius=10)
        if not blocks:
            f.write("(No focused context blocks)\n")
            continue
        for bi, (a, b) in enumerate(blocks[:8], start=1):
            f.write(f"\n[BLOCK {bi}: lines {a+1}-{b+1}]\n")
            for i in range(a, b+1):
                f.write(f"{i+1:6d}: {lines[i]}\n")

print(f"Created {OUT}")
