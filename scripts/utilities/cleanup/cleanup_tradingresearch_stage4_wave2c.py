#!/usr/bin/env python
from __future__ import annotations

r"""
TradingResearch Stage 4 — Wave 2C conservative dependency-group migration.

Commands:
    python .\cleanup_tradingresearch_stage4_wave2c.py plan
    python .\cleanup_tradingresearch_stage4_wave2c.py apply-safe
    python .\cleanup_tradingresearch_stage4_wave2c.py rollback-last

Safety rule:
  A dependency group is movable only when ALL members:
    * belong to one project;
    * resolve to one destination directory;
    * are not canonical/frozen/provenance backups;
    * are not cleanup tooling;
    * have no direct filename-reference dependency edges;
    * have only Python import relationships (or are isolated);
    * have no destination collisions.

This preserves same-directory Python imports while avoiding scripts that use
Path("other_script.py") / direct filename references, which can break after relocation.

No files are deleted or edited. Every move is SHA-256 verified.
"""

import argparse
import ast
import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict, deque
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

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def nrm(s: str) -> str:
    return s.lower().replace("-", "_").replace(" ", "_")

def is_cleanup(p: Path) -> bool:
    return nrm(p.name).startswith("cleanup_tradingresearch_")

def role(p: Path) -> str:
    n = nrm(p.name)
    if any(x in n for x in ("pre_patch_backup", "_backup", "backup_")):
        return "BACKUP_PROVENANCE"
    if any(x in n for x in ("final", "frozen", "candidate_model", "protocol")):
        return "CANONICAL_OR_FROZEN"
    if any(x in n for x in ("patch", "_fix", "fix1", "fix2", "fix3", "fix4", "fix5", "fix6", "fix7", "fix8", "fix9")):
        return "PATCH_OR_FIX"
    if p.suffix.lower() == ".pine":
        return "PINE_SOURCE"
    return "OTHER"

def classify(p: Path) -> tuple[str, str]:
    if p.name in OVERRIDES:
        return OVERRIDES[p.name]

    n = nrm(p.name)
    if is_cleanup(p):
        return "utilities", "cleanup"
    if n.startswith("osi_"):
        return "osi", "parity"
    if "orb" in n or n == "6_2.pine":
        return "orb", "legacy"

    if (
        re.search(r"(?:^|_)(a(?:3[7-9]|4\d|5[0-6]))(?:_|$)", n)
        or any(x in n for x in ("second1m", "second_candle", "alternative_c2", "altc2", "ae2_", "fthc_", "s1m_"))
    ):
        if "altc2" in n or "alternative_c2" in n:
            return "second1m", "altc2"
        if "ae2" in n:
            return "second1m", "ae2"
        if "fthc" in n:
            return "second1m", "fthc"
        if re.search(r"(?:^|_)(a(?:3[7-9]|4\d|5[0-6]))(?:_|$)", n):
            return "second1m", "a37_a56"
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
    if "pmpd_v5" in text or "join_and_audit_frozen_9h" in text or "summarize_9j" in text:
        return "pmpd", "legacy"
    if "second1m" in text or "altc2" in text or "ae2_" in text:
        return "second1m", "legacy"
    if "market_cache" in text and "batch_acquisition" in text:
        return "market_data", "utilities"

    return "unclassified", "review"

def destination_dir(root: Path, p: Path, project: str, phase: str) -> Path:
    base = "pine" if p.suffix.lower() == ".pine" else "scripts"
    return root / base / project / phase

def python_imports(p: Path):
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

def build_graph(sources):
    names = {p.name for p in sources}
    stems = {p.stem: p.name for p in sources if p.suffix.lower() == ".py"}
    graph = {p.name: set() for p in sources}
    edge_types = defaultdict(set)

    for p in sources:
        if p.suffix.lower() == ".py":
            for stem in python_imports(p):
                target = stems.get(stem)
                if target and target != p.name:
                    key = tuple(sorted((p.name, target)))
                    graph[p.name].add(target)
                    graph[target].add(p.name)
                    edge_types[key].add("PY_IMPORT")

    # Direct filename references are tracked separately and make a group unsafe.
    for p in sources:
        text = read_text(p)
        for target in names:
            if target != p.name and target in text:
                key = tuple(sorted((p.name, target)))
                graph[p.name].add(target)
                graph[target].add(p.name)
                edge_types[key].add("FILENAME_REFERENCE")

    return graph, edge_types

def components(graph):
    seen = set()
    out = []
    for node in sorted(graph):
        if node in seen:
            continue
        q = deque([node]); seen.add(node); comp = []
        while q:
            cur = q.popleft()
            comp.append(cur)
            for nb in graph[cur]:
                if nb not in seen:
                    seen.add(nb); q.append(nb)
        out.append(sorted(comp))
    return out

def create_plan(root: Path):
    all_sources = sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS],
        key=lambda p: p.name.lower()
    )
    sources = [p for p in all_sources if not is_cleanup(p)]
    graph, edge_types = build_graph(sources)
    comps = components(graph)

    group_rows = []
    move_rows = []

    for gid, comp in enumerate(comps, 1):
        members = [root / x for x in comp]
        classes = [classify(p) for p in members]
        projects = sorted({x[0] for x in classes})
        dest_dirs = [destination_dir(root, p, *classify(p)) for p in members]
        unique_dest_dirs = sorted({str(x.relative_to(root)) for x in dest_dirs})
        roles = [role(p) for p in members]

        direct_ref_edges = []
        import_edges = []
        for i, a in enumerate(comp):
            for b in comp[i+1:]:
                types = edge_types.get(tuple(sorted((a, b))), set())
                if "FILENAME_REFERENCE" in types:
                    direct_ref_edges.append(f"{a}<->{b}")
                if "PY_IMPORT" in types:
                    import_edges.append(f"{a}<->{b}")

        reasons = []
        safe = True

        if "unclassified" in projects:
            safe = False; reasons.append("unclassified member")
        if len(projects) != 1:
            safe = False; reasons.append("cross-project group")
        if len(unique_dest_dirs) != 1:
            safe = False; reasons.append("members map to different destination directories")
        if any(r in {"CANONICAL_OR_FROZEN", "BACKUP_PROVENANCE"} for r in roles):
            safe = False; reasons.append("canonical/frozen/provenance-sensitive member")
        if direct_ref_edges:
            safe = False; reasons.append(f"direct filename-reference edges={len(direct_ref_edges)}")

        collisions = []
        for p, ddir in zip(members, dest_dirs):
            dst = ddir / p.name
            if dst.exists():
                collisions.append(str(dst.relative_to(root)))
        if collisions:
            safe = False; reasons.append(f"destination collisions={len(collisions)}")

        status = "SAFE_GROUP_MOVE" if safe else "HOLD"

        group_rows.append({
            "group_id": gid,
            "member_count": len(comp),
            "project": " | ".join(projects),
            "destination_dirs": " | ".join(unique_dest_dirs),
            "status": status,
            "reason": "; ".join(reasons),
            "python_import_edges": len(import_edges),
            "direct_filename_reference_edges": len(direct_ref_edges),
            "members": " | ".join(comp),
        })

        if safe:
            for p, ddir in zip(members, dest_dirs):
                move_rows.append({
                    "group_id": gid,
                    "source": str(p.relative_to(root)),
                    "destination": str((ddir / p.name).relative_to(root)),
                    "sha256": sha256(p),
                })

    return group_rows, move_rows

def write_plan(root, group_rows, move_rows):
    out = root / "cleanup_reports"; out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    gpath = out / f"stage4_wave2c_groups_{stamp}.csv"
    mpath = out / f"stage4_wave2c_moves_{stamp}.csv"
    jpath = out / f"stage4_wave2c_groups_{stamp}.json"

    with gpath.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=group_rows[0].keys()); w.writeheader(); w.writerows(group_rows)
    with mpath.open("w", newline="", encoding="utf-8-sig") as f:
        fields = ["group_id","source","destination","sha256"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(move_rows)
    jpath.write_text(json.dumps(group_rows, indent=2), encoding="utf-8")
    return gpath, mpath, jpath

def print_plan(group_rows, move_rows, paths):
    status = Counter(g["status"] for g in group_rows)
    safe_groups = [g for g in group_rows if g["status"] == "SAFE_GROUP_MOVE"]
    print("=== STAGE 4 WAVE 2C PLAN ===")
    print(f"Dependency groups evaluated: {len(group_rows)}")
    print(f"SAFE_GROUP_MOVE: {len(safe_groups)}")
    print(f"HOLD           : {status.get('HOLD', 0)}")
    print(f"Files planned to move: {len(move_rows)}")
    print("")
    print("Safe groups:")
    for g in safe_groups:
        print(f"  G{g['group_id']:03d} size={g['member_count']:2d} project={g['project']} -> {g['destination_dirs']}")
    print("")
    print("NO FILES MOVED BY PLAN COMMAND.")
    print(f"Groups CSV: {paths[0]}")
    print(f"Moves CSV : {paths[1]}")
    print(f"JSON      : {paths[2]}")

def apply_safe(root: Path):
    group_rows, move_rows = create_plan(root)
    if not move_rows:
        print("No safe Wave 2C moves.")
        return

    out = root / "cleanup_reports"; out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rb = out / f"stage4_wave2c_rollback_{stamp}.json"
    manifest = {"created_at": datetime.now().isoformat(), "moves": [
        {"from": r["source"], "to": r["destination"], "sha256": r["sha256"], "completed": False}
        for r in move_rows
    ]}
    rb.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    moved = 0
    try:
        for i, r in enumerate(move_rows):
            src = root / r["source"]; dst = root / r["destination"]
            if not src.exists(): raise RuntimeError(f"Source missing: {src}")
            if sha256(src) != r["sha256"]: raise RuntimeError(f"Hash changed: {src}")
            if dst.exists(): raise RuntimeError(f"Destination exists: {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            if not dst.exists() or sha256(dst) != r["sha256"]:
                raise RuntimeError(f"Post-move verification failed: {dst}")
            manifest["moves"][i]["completed"] = True
            rb.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            moved += 1
    except Exception:
        print(f"ERROR after {moved} successful moves.")
        print(f"Rollback manifest: {rb}")
        print("Run rollback-last to restore completed moves.")
        raise

    remaining = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS]
    print("=== STAGE 4 WAVE 2C APPLY ===")
    print(f"Moved and SHA-verified: {moved}")
    print(f"Root source files remaining: {len(remaining)}")
    print(f"Rollback manifest: {rb}")
    print("No files were deleted or edited.")

def rollback_last(root: Path):
    out = root / "cleanup_reports"
    manifests = sorted(out.glob("stage4_wave2c_rollback_*.json"))
    if not manifests: raise SystemExit("No Wave 2C rollback manifest found.")
    rb = manifests[-1]
    data = json.loads(rb.read_text(encoding="utf-8"))
    restored = 0
    for item in reversed(data["moves"]):
        if not item.get("completed"): continue
        src = root / item["to"]; dst = root / item["from"]
        if dst.exists(): raise RuntimeError(f"Original already exists: {dst}")
        if not src.exists(): raise RuntimeError(f"Moved file missing: {src}")
        if sha256(src) != item["sha256"]: raise RuntimeError(f"Hash mismatch: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        if sha256(dst) != item["sha256"]: raise RuntimeError(f"Rollback verification failed: {dst}")
        restored += 1
    print("=== STAGE 4 WAVE 2C ROLLBACK ===")
    print(f"Restored and SHA-verified: {restored}")
    print(f"Manifest used: {rb}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["plan","apply-safe","rollback-last"])
    args = ap.parse_args()
    root = Path(__file__).resolve().parent

    if args.command == "plan":
        groups, moves = create_plan(root)
        paths = write_plan(root, groups, moves)
        print_plan(groups, moves, paths)
    elif args.command == "apply-safe":
        apply_safe(root)
    else:
        rollback_last(root)

if __name__ == "__main__":
    main()
