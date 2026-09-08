#!/usr/bin/env python
from __future__ import annotations

r"""
TradingResearch Stage 4 — Wave 2B dependency-group audit.

Run:
    python .\cleanup_tradingresearch_stage4_wave2b_audit.py

Audit only. No files are moved, deleted, or edited.

Key correction from Wave 2:
  * cleanup_tradingresearch_*.py files are EXCLUDED from the dependency graph.
    They intentionally mention many source filenames and were falsely merging
    unrelated PM+PD / ORB / utility files into one giant dependency group.
"""

import ast
import csv
import json
import re
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
    if any(x in n for x in (
        "audit", "diagnose", "inspect", "inventory", "trace",
        "preflight", "certify", "probe", "summarize", "report_"
    )):
        return "AUDIT_DIAGNOSTIC"
    if p.suffix.lower() == ".pine":
        return "PINE_SOURCE"
    return "RESEARCH_OR_UTILITY"

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

    # Small content fallback for generic held files.
    text = read_text(p).lower()
    if "pmpd_v5" in text or "join_and_audit_frozen_9h" in text or "summarize_9j" in text:
        return "pmpd", "legacy"
    if "second1m" in text or "altc2" in text or "ae2_" in text:
        return "second1m", "legacy"
    if "market_cache" in text and "batch_acquisition" in text:
        return "market_data", "utilities"

    return "unclassified", "review"

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
    # Cleanup tools are intentionally excluded from graph construction.
    graph_sources = [p for p in sources if not is_cleanup(p)]
    names = {p.name for p in graph_sources}
    stems = {p.stem: p.name for p in graph_sources if p.suffix.lower() == ".py"}
    graph = {p.name: set() for p in graph_sources}

    for p in graph_sources:
        if p.suffix.lower() == ".py":
            for stem in python_imports(p):
                target = stems.get(stem)
                if target and target != p.name:
                    graph[p.name].add(target)
                    graph[target].add(p.name)

    for p in graph_sources:
        text = read_text(p)
        for target in names:
            if target != p.name and target in text:
                graph[p.name].add(target)
                graph[target].add(p.name)

    return graph

def connected_components(graph):
    seen = set()
    comps = []
    for node in sorted(graph):
        if node in seen:
            continue
        q = deque([node])
        seen.add(node)
        comp = []
        while q:
            cur = q.popleft()
            comp.append(cur)
            for nb in graph[cur]:
                if nb not in seen:
                    seen.add(nb)
                    q.append(nb)
        comps.append(sorted(comp))
    return comps

def main():
    root = Path(__file__).resolve().parent
    all_sources = sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS],
        key=lambda p: p.name.lower()
    )
    cleanup_sources = [p for p in all_sources if is_cleanup(p)]
    sources = [p for p in all_sources if not is_cleanup(p)]

    graph = build_graph(all_sources)
    comps = connected_components(graph)

    rows = []
    group_rows = []

    for gid, comp in enumerate(comps, start=1):
        members = [root / name for name in comp]
        roles = [role(p) for p in members]
        classes = [classify(p) for p in members]
        projects = sorted(set(pr for pr, _ in classes))
        phases = sorted(set(ph for _, ph in classes))

        has_sensitive = any(r in {"CANONICAL_OR_FROZEN", "BACKUP_PROVENANCE"} for r in roles)
        has_unclassified = any(pr == "unclassified" for pr, _ in classes)

        if has_sensitive:
            status = "HOLD_SENSITIVE_GROUP"
        elif has_unclassified:
            status = "HOLD_UNCLASSIFIED_GROUP"
        elif len(projects) == 1:
            status = "GROUP_MOVE_CANDIDATE"
        else:
            status = "HOLD_CROSS_PROJECT_GROUP"

        group_rows.append({
            "group_id": gid,
            "member_count": len(comp),
            "projects": " | ".join(projects),
            "phases": " | ".join(phases),
            "status": status,
            "members": " | ".join(comp),
        })

        for p in members:
            project, phase = classify(p)
            rows.append({
                "group_id": gid,
                "name": p.name,
                "project": project,
                "phase": phase,
                "role": role(p),
                "degree": len(graph[p.name]),
                "neighbors": " | ".join(sorted(graph[p.name])),
                "group_status": status,
            })

    outdir = root / "cleanup_reports"
    outdir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    groups_csv = outdir / f"stage4_wave2b_dependency_groups_{stamp}.csv"
    files_csv = outdir / f"stage4_wave2b_dependency_files_{stamp}.csv"
    json_path = outdir / f"stage4_wave2b_dependency_groups_{stamp}.json"

    with groups_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=group_rows[0].keys())
        w.writeheader()
        w.writerows(group_rows)

    with files_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    json_path.write_text(json.dumps(group_rows, indent=2), encoding="utf-8")

    status_counts = Counter(g["status"] for g in group_rows)
    nonisolated = [g for g in group_rows if g["member_count"] > 1]

    print("=== STAGE 4 WAVE 2B DEPENDENCY-GROUP AUDIT ===")
    print(f"Root source files total : {len(all_sources)}")
    print(f"Cleanup tools excluded  : {len(cleanup_sources)}")
    print(f"Research/source analyzed: {len(sources)}")
    print(f"Dependency groups total : {len(group_rows)}")
    print(f"Non-isolated groups     : {len(nonisolated)}")
    print("")
    print("Group status:")
    for k, v in sorted(status_counts.items()):
        print(f"  {k:28s} {v}")

    print("")
    print("Non-isolated groups:")
    for g in nonisolated:
        print(
            f"  G{g['group_id']:03d}  size={g['member_count']:2d}  "
            f"{g['status']:24s}  {g['projects']}"
        )

    print("")
    print("Cleanup tools intentionally kept in root:")
    for p in cleanup_sources:
        print(f"  - {p.name}")

    print("")
    print("NO FILES MOVED, DELETED, OR EDITED.")
    print(f"Groups CSV: {groups_csv}")
    print(f"Files CSV : {files_csv}")
    print(f"JSON      : {json_path}")

if __name__ == "__main__":
    main()
