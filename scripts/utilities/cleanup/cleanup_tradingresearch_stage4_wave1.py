#!/usr/bin/env python
from __future__ import annotations

r"""
TradingResearch Stage 4 — controlled source migration, Wave 1.

Commands:
    python .\cleanup_tradingresearch_stage4_wave1.py plan
    python .\cleanup_tradingresearch_stage4_wave1.py apply-safe
    python .\cleanup_tradingresearch_stage4_wave1.py rollback-last

Wave 1 moves only files that are confidently classified, not canonical/frozen
or provenance backups, not cleanup tooling, and have no detected root-source
dependency edges. No files are deleted or edited. Every move is SHA-256 verified.
"""

import argparse, ast, csv, hashlib, json, re, shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

SOURCE_EXTS = {".py", ".ps1", ".pine"}

OVERRIDES = {
    "patch_certify_v2_full50_parity.py": ("pmpd", "9j"),
    "patch_outcome_independence_comment_filter.py": ("pmpd", "9h"),
    "patch_outcome_join_ambiguous_same_bar.py": ("pmpd", "9h"),
    "patch_outcome_join_prefer_canonical_label.py": ("pmpd", "9h"),
    "patch_validation_robustness_block_repair_v3.py": ("pmpd", "9j"),
    "patch_validation_robustness_corr_scope_v2.py": ("pmpd", "9j"),
    "patch_validation_robustness_no_scipy.py": ("pmpd", "9j"),
    "run_controlled_batch.py": ("market_data", "utilities"),
    "Test.py": ("utilities", "misc"),
}

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def nrm(s: str) -> str:
    return s.lower().replace("-", "_").replace(" ", "_")

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def classify(p: Path):
    if p.name in OVERRIDES:
        return OVERRIDES[p.name]

    n = nrm(p.name)

    if n.startswith("cleanup_tradingresearch_"):
        return "utilities", "cleanup"
    if n.startswith("osi_"):
        return "osi", "parity"
    if "orb" in n or n == "6_2.pine":
        return "orb", "legacy"

    if (
        re.search(r"(?:^|_)(a(?:3[7-9]|4\d|5[0-6]))(?:_|$)", n)
        or any(x in n for x in (
            "second1m", "second_candle", "alternative_c2",
            "altc2", "ae2_", "fthc_", "s1m_"
        ))
    ):
        if "altc2" in n or "alternative_c2" in n:
            return "second1m", "altc2"
        if "ae2" in n:
            return "second1m", "ae2"
        if "fthc" in n:
            return "second1m", "fthc"
        if re.search(r"(?:^|_)(a(?:3[7-9]|4\d|5[0-6]))(?:_|$)", n):
            return "second1m", "a37_a56"
        if any(x in n for x in ("import_", "acquire_", "archive_")):
            return "second1m", "ingestion"
        return "second1m", "legacy"

    if (
        "pmpd" in n or "pm_pd_breakout" in n or "pm_+_pd_breakout" in n
        or "v4_parity" in n or "vwap_event_path" in n or "dp4" in n
        or re.search(r"(?:^|_)(9[g-n])(?:_|$)", n)
    ):
        m = re.search(r"(?:^|_)(9[g-n])(?:_|$)", n)
        if m:
            return "pmpd", m.group(1)
        if "v4" in n or "parity" in n or "forward_validation" in n:
            return "pmpd", "v4"
        return "pmpd", "legacy"

    if any(x in n for x in ("massive", "market_data", "market_benchmark", "vrtx_massive")):
        return "market_data", "utilities"

    text = read_text(p).lower()
    scores = {"pmpd": 0, "second1m": 0, "orb": 0, "market_data": 0}
    terms = {
        "pmpd": (("pmpd",4),("pmpd_v5",5),("pm+pd",4),("v4_parity",4),("vwap_event_path",3),("dp4_",3)),
        "second1m": (("second1m",5),("altc2",5),("alternative_c2",5),("ae2_",4),("a41_",3),("a51_",3),("a56_",3)),
        "orb": (("opening range breakout",5),("15m orb",5)),
        "market_data": (("market_cache",3),("massive",3)),
    }
    for project, pairs in terms.items():
        for token, weight in pairs:
            if token in text:
                scores[project] += weight
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if ranked[0][1] >= 5 and ranked[0][1] >= ranked[1][1] + 2:
        return ranked[0][0], "legacy"

    return "unclassified", "review"

def role(p: Path) -> str:
    n = nrm(p.name)
    if any(x in n for x in ("pre_patch_backup", "_backup", "backup_")):
        return "BACKUP_PROVENANCE"
    if any(x in n for x in ("final", "frozen", "candidate_model", "protocol")):
        return "CANONICAL_OR_FROZEN"
    if any(x in n for x in ("patch", "_fix", "fix1", "fix2", "fix3", "fix4", "fix5", "fix6", "fix7", "fix8", "fix9")):
        return "PATCH_OR_FIX"
    if any(x in n for x in ("audit","diagnose","inspect","inventory","trace","preflight","certify","probe","summarize","report_")):
        return "AUDIT_DIAGNOSTIC"
    if p.suffix.lower() == ".pine":
        return "PINE_SOURCE"
    return "RESEARCH_OR_UTILITY"

def python_import_stems(p: Path):
    out = set()
    try:
        tree = ast.parse(read_text(p))
    except Exception:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out

def dependency_graph(sources):
    names = {p.name for p in sources}
    stem_to_name = {p.stem: p.name for p in sources if p.suffix.lower() == ".py"}
    graph = {p.name: set() for p in sources}

    for p in sources:
        if p.suffix.lower() == ".py":
            for stem in python_import_stems(p):
                target = stem_to_name.get(stem)
                if target and target != p.name:
                    graph[p.name].add(target)
                    graph[target].add(p.name)

    for p in sources:
        text = read_text(p)
        for target in names:
            if target != p.name and target in text:
                graph[p.name].add(target)
                graph[target].add(p.name)
    return graph

def destination(root: Path, p: Path, project: str, phase: str):
    base = "pine" if p.suffix.lower() == ".pine" else "scripts"
    return root / base / project / phase / p.name

def create_plan(root: Path):
    sources = sorted([p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS], key=lambda x: x.name.lower())
    graph = dependency_graph(sources)
    rows = []

    for p in sources:
        project, phase = classify(p)
        r = role(p)
        deps = sorted(graph.get(p.name, set()))
        dst = destination(root, p, project, phase)
        reasons = []
        safe = True

        if project == "unclassified":
            safe = False
            reasons.append("unclassified")
        if project == "utilities" and phase == "cleanup":
            safe = False
            reasons.append("keep cleanup tooling in root until cleanup complete")
        if r in {"CANONICAL_OR_FROZEN", "BACKUP_PROVENANCE"}:
            safe = False
            reasons.append("provenance/canonical review")
        if deps:
            safe = False
            reasons.append(f"root-source dependencies={len(deps)}")
        if dst.exists():
            safe = False
            reasons.append("destination already exists")

        rows.append({
            "source": str(p.relative_to(root)),
            "destination": str(dst.relative_to(root)),
            "project": project,
            "phase": phase,
            "role": r,
            "sha256": sha256(p),
            "dependency_count": len(deps),
            "dependencies": " | ".join(deps),
            "status": "SAFE_WAVE1" if safe else "HOLD",
            "reason": "; ".join(reasons),
        })
    return rows

def write_plan(root: Path, rows):
    outdir = root / "cleanup_reports"
    outdir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = outdir / f"stage4_wave1_plan_{stamp}.csv"
    json_path = outdir / f"stage4_wave1_plan_{stamp}.json"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return csv_path, json_path

def print_summary(rows, csv_path=None, json_path=None):
    statuses = Counter(r["status"] for r in rows)
    projects = Counter(r["project"] for r in rows if r["status"] == "SAFE_WAVE1")
    roles_held = Counter(r["role"] for r in rows if r["status"] == "HOLD")

    print("=== STAGE 4 WAVE 1 PLAN ===")
    print(f"Root source files evaluated: {len(rows)}")
    print(f"SAFE_WAVE1: {statuses.get('SAFE_WAVE1', 0)}")
    print(f"HOLD      : {statuses.get('HOLD', 0)}")
    print("")
    print("Safe moves by project:")
    for k, v in sorted(projects.items()):
        print(f"  {k:18s} {v}")
    print("")
    print("Held files by role:")
    for k, v in sorted(roles_held.items()):
        print(f"  {k:24s} {v}")
    dep_holds = [r for r in rows if r["status"] == "HOLD" and r["dependency_count"]]
    print("")
    print(f"Dependency-sensitive holds: {len(dep_holds)}")
    if csv_path: print(f"Plan CSV : {csv_path}")
    if json_path: print(f"Plan JSON: {json_path}")
    print("")
    print("NO FILES MOVED BY PLAN COMMAND.")

def apply_safe(root: Path):
    rows = create_plan(root)
    safe = [r for r in rows if r["status"] == "SAFE_WAVE1"]
    if not safe:
        print("No SAFE_WAVE1 files to move.")
        return

    outdir = root / "cleanup_reports"
    outdir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rollback_path = outdir / f"stage4_wave1_rollback_{stamp}.json"

    rollback = {"created_at": datetime.now().isoformat(), "moves": [
        {"from": r["source"], "to": r["destination"], "sha256": r["sha256"], "completed": False}
        for r in safe
    ]}
    rollback_path.write_text(json.dumps(rollback, indent=2), encoding="utf-8")

    moved = 0
    try:
        for idx, r in enumerate(safe):
            src = root / r["source"]
            dst = root / r["destination"]
            if not src.exists():
                raise RuntimeError(f"Source missing: {src}")
            if sha256(src) != r["sha256"]:
                raise RuntimeError(f"Source hash changed: {src}")
            if dst.exists():
                raise RuntimeError(f"Destination exists: {dst}")

            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))

            if not dst.exists() or sha256(dst) != r["sha256"]:
                raise RuntimeError(f"Post-move hash verification failed: {dst}")

            rollback["moves"][idx]["completed"] = True
            rollback_path.write_text(json.dumps(rollback, indent=2), encoding="utf-8")
            moved += 1
    except Exception:
        print(f"ERROR after {moved} successful moves.")
        print(f"Rollback manifest: {rollback_path}")
        print("Run rollback-last to restore completed Stage 4 moves.")
        raise

    remaining = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS]
    print("=== STAGE 4 WAVE 1 APPLY ===")
    print(f"Moved and SHA-verified: {moved}")
    print(f"Root source files remaining: {len(remaining)}")
    print(f"Rollback manifest: {rollback_path}")
    print("No files were deleted or edited.")

def rollback_last(root: Path):
    outdir = root / "cleanup_reports"
    manifests = sorted(outdir.glob("stage4_wave1_rollback_*.json"))
    if not manifests:
        raise SystemExit("No Stage 4 rollback manifest found.")
    path = manifests[-1]
    data = json.loads(path.read_text(encoding="utf-8"))
    restored = 0

    for item in reversed(data["moves"]):
        if not item.get("completed"):
            continue
        original = root / item["from"]
        moved = root / item["to"]
        if original.exists():
            raise RuntimeError(f"Original path already exists: {original}")
        if not moved.exists():
            raise RuntimeError(f"Moved file missing: {moved}")
        if sha256(moved) != item["sha256"]:
            raise RuntimeError(f"Hash mismatch: {moved}")

        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(moved), str(original))
        if sha256(original) != item["sha256"]:
            raise RuntimeError(f"Rollback hash verification failed: {original}")
        restored += 1

    print("=== STAGE 4 WAVE 1 ROLLBACK ===")
    print(f"Restored and SHA-verified: {restored}")
    print(f"Manifest used: {path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["plan", "apply-safe", "rollback-last"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parent

    if args.command == "plan":
        rows = create_plan(root)
        csv_path, json_path = write_plan(root, rows)
        print_summary(rows, csv_path, json_path)
    elif args.command == "apply-safe":
        apply_safe(root)
    else:
        rollback_last(root)

if __name__ == "__main__":
    main()
