#!/usr/bin/env python
from __future__ import annotations

r"""
TradingResearch Stage 4 — Final conservative group cleanup.

Run:
    python .\cleanup_tradingresearch_stage4_final_groups.py apply

Rollback:
    python .\cleanup_tradingresearch_stage4_final_groups.py rollback-last

This script intentionally skips canonical/frozen/provenance-sensitive groups
and cleanup tooling. It moves non-sensitive dependency groups as intact units.

Rules:
  * Isolated/simple files -> normal scripts/pine destination.
  * Dependency groups with direct filename references -> archived intact under
    archive/source/<project>/dependency_groups/Gxxx so same-directory relationships
    are preserved for historical reruns from that folder.
  * Import-only groups that resolve to one project/phase -> normal scripts destination.
  * Sensitive groups remain in root for later/manual handling.
  * No source code is edited.
  * No source file is deleted.
  * Every move is SHA-256 verified.
  * Rollback manifest is written before the first move.
"""

import argparse
import ast
import hashlib
import json
import re
import shutil
from collections import defaultdict, deque, Counter
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

def txt(p: Path) -> str:
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
    return "NORMAL"

def classify(p: Path):
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
        or any(x in n for x in ("second1m","second_candle","alternative_c2","altc2","ae2_","fthc_","s1m_"))
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

    if any(x in n for x in ("massive","market_data","market_benchmark","vrtx_massive")):
        return "market_data", "utilities"

    t = txt(p).lower()
    if "pmpd_v5" in t or "join_and_audit_frozen_9h" in t or "summarize_9j" in t:
        return "pmpd", "legacy"
    if "second1m" in t or "altc2" in t or "ae2_" in t:
        return "second1m", "legacy"
    if "market_cache" in t and "batch_acquisition" in t:
        return "market_data", "utilities"
    return "unclassified", "review"

def py_imports(p: Path):
    out = set()
    try:
        tree = ast.parse(txt(p))
    except Exception:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out

def graph_and_edges(sources):
    names = {p.name for p in sources}
    stems = {p.stem:p.name for p in sources if p.suffix.lower()==".py"}
    graph = {p.name:set() for p in sources}
    edge_types = defaultdict(set)

    for p in sources:
        if p.suffix.lower()==".py":
            for stem in py_imports(p):
                target = stems.get(stem)
                if target and target != p.name:
                    k = tuple(sorted((p.name,target)))
                    graph[p.name].add(target); graph[target].add(p.name)
                    edge_types[k].add("PY_IMPORT")

    for p in sources:
        s = txt(p)
        for target in names:
            if target != p.name and target in s:
                k = tuple(sorted((p.name,target)))
                graph[p.name].add(target); graph[target].add(p.name)
                edge_types[k].add("FILENAME_REFERENCE")
    return graph, edge_types

def components(graph):
    seen=set(); comps=[]
    for node in sorted(graph):
        if node in seen: continue
        q=deque([node]); seen.add(node); comp=[]
        while q:
            cur=q.popleft(); comp.append(cur)
            for nb in graph[cur]:
                if nb not in seen:
                    seen.add(nb); q.append(nb)
        comps.append(sorted(comp))
    return comps

def plan_moves(root: Path):
    all_sources = sorted([p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS], key=lambda p:p.name.lower())
    sources = [p for p in all_sources if not is_cleanup(p)]
    graph, edge_types = graph_and_edges(sources)
    comps = components(graph)

    moves=[]; held=[]; groups=[]

    for gid, comp in enumerate(comps,1):
        members=[root/x for x in comp]
        classes=[classify(p) for p in members]
        projects=sorted({x[0] for x in classes})
        phases=sorted({x[1] for x in classes})
        sensitive=any(role(p)!="NORMAL" for p in members)
        unclassified=any(pr=="unclassified" for pr,_ in classes)

        direct_ref=False
        for i,a in enumerate(comp):
            for b in comp[i+1:]:
                if "FILENAME_REFERENCE" in edge_types.get(tuple(sorted((a,b))), set()):
                    direct_ref=True

        if sensitive or unclassified or len(projects)!=1:
            reason=[]
            if sensitive: reason.append("sensitive")
            if unclassified: reason.append("unclassified")
            if len(projects)!=1: reason.append("cross-project")
            held.extend(comp)
            groups.append((gid,comp,"HOLD",",".join(reason)))
            continue

        project=projects[0]

        # Direct-reference groups are historical dependency bundles: archive intact.
        if direct_ref and len(comp)>1:
            group_dir = root / "archive" / "source" / project / "dependency_groups" / f"G{gid:03d}"
            for p in members:
                moves.append((gid,p,group_dir/p.name,"ARCHIVE_GROUP"))
            groups.append((gid,comp,"MOVE_ARCHIVE_GROUP","direct filename references"))
            continue

        # Import-only or isolated groups: normal destination if one phase.
        if len(phases)==1:
            phase=phases[0]
            for p in members:
                base="pine" if p.suffix.lower()==".pine" else "scripts"
                dst=root/base/project/phase/p.name
                moves.append((gid,p,dst,"NORMAL_GROUP"))
            groups.append((gid,comp,"MOVE_NORMAL","single project/phase"))
        else:
            # Multiple phases but no direct refs: archive together rather than split.
            group_dir = root / "archive" / "source" / project / "dependency_groups" / f"G{gid:03d}"
            for p in members:
                moves.append((gid,p,group_dir/p.name,"ARCHIVE_GROUP"))
            groups.append((gid,comp,"MOVE_ARCHIVE_GROUP","multi-phase dependency group"))

    # destination collision screen
    final_moves=[]; collision_holds=[]
    for gid,src,dst,mode in moves:
        if dst.exists():
            collision_holds.append(src.name)
        else:
            final_moves.append((gid,src,dst,mode))

    if collision_holds:
        held.extend(collision_holds)
        final_moves=[m for m in final_moves if m[1].name not in collision_holds]

    return all_sources, groups, final_moves, sorted(set(held))

def apply(root: Path):
    all_sources, groups, moves, held = plan_moves(root)

    print("=== STAGE 4 FINAL GROUP CLEANUP — PREVIEW ===")
    print(f"Root source files before: {len(all_sources)}")
    print(f"Files to move           : {len(moves)}")
    print(f"Files held              : {len(held)}")
    c=Counter(m[3] for m in moves)
    for k,v in sorted(c.items()):
        print(f"  {k:18s} {v}")
    print("")

    if not moves:
        print("Nothing eligible to move.")
        return

    out=root/"cleanup_reports"; out.mkdir(exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    rb=out/f"stage4_final_groups_rollback_{stamp}.json"

    manifest={
        "created_at":datetime.now().isoformat(),
        "moves":[
            {"from":str(src.relative_to(root)),"to":str(dst.relative_to(root)),
             "sha256":sha256(src),"group_id":gid,"mode":mode,"completed":False}
            for gid,src,dst,mode in moves
        ]
    }
    rb.write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    moved=0
    try:
        for i,item in enumerate(manifest["moves"]):
            src=root/item["from"]; dst=root/item["to"]
            if not src.exists(): raise RuntimeError(f"Source missing: {src}")
            if sha256(src)!=item["sha256"]: raise RuntimeError(f"Hash changed: {src}")
            if dst.exists(): raise RuntimeError(f"Destination exists: {dst}")
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(str(src),str(dst))
            if not dst.exists() or sha256(dst)!=item["sha256"]:
                raise RuntimeError(f"Verification failed: {dst}")
            item["completed"]=True
            rb.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
            moved+=1
    except Exception:
        print(f"ERROR after {moved} successful moves.")
        print(f"Rollback manifest: {rb}")
        print("Run rollback-last.")
        raise

    remaining=[p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS]
    print("=== APPLY COMPLETE ===")
    print(f"Moved and SHA-verified : {moved}")
    print(f"Root source files after: {len(remaining)}")
    print(f"Rollback manifest      : {rb}")
    print("No source files were deleted or edited.")

def rollback(root: Path):
    out=root/"cleanup_reports"
    manifests=sorted(out.glob("stage4_final_groups_rollback_*.json"))
    if not manifests: raise SystemExit("No final-group rollback manifest found.")
    rb=manifests[-1]
    data=json.loads(rb.read_text(encoding="utf-8"))
    restored=0
    for item in reversed(data["moves"]):
        if not item.get("completed"): continue
        src=root/item["to"]; dst=root/item["from"]
        if dst.exists(): raise RuntimeError(f"Original already exists: {dst}")
        if not src.exists(): raise RuntimeError(f"Moved file missing: {src}")
        if sha256(src)!=item["sha256"]: raise RuntimeError(f"Hash mismatch: {src}")
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(src),str(dst))
        if sha256(dst)!=item["sha256"]: raise RuntimeError(f"Rollback verify failed: {dst}")
        restored+=1
    print("=== ROLLBACK COMPLETE ===")
    print(f"Restored and SHA-verified: {restored}")
    print(f"Manifest: {rb}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("command",choices=["apply","rollback-last"])
    args=ap.parse_args()
    root=Path(__file__).resolve().parent
    if args.command=="apply":
        apply(root)
    else:
        rollback(root)

if __name__=="__main__":
    main()
