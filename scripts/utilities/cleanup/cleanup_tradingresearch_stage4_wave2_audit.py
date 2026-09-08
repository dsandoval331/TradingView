#!/usr/bin/env python
from __future__ import annotations

r"""
TradingResearch Stage 4 — Wave 2 dependency-group audit.

Run:
    python .\cleanup_tradingresearch_stage4_wave2_audit.py

Audit only. No files are moved, deleted, or edited.

Purpose:
  * inspect the 115 source files held after Wave 1;
  * build connected dependency groups among root source files;
  * show which groups can potentially move together;
  * isolate canonical/frozen/provenance-sensitive groups;
  * write CSV/JSON reports for review.
"""

import ast
import csv
import json
import re
from collections import Counter, defaultdict, deque
from datetime import datetime
from pathlib import Path

SOURCE_EXTS = {".py", ".ps1", ".pine"}

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def nrm(s: str) -> str:
    return s.lower().replace("-", "_").replace(" ", "_")

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
    n = nrm(p.name)

    # cleanup tooling
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
    names = {p.name for p in sources}
    stems = {p.stem: p.name for p in sources if p.suffix.lower() == ".py"}
    graph = {p.name: set() for p in sources}
    edge_reasons = defaultdict(list)

    for p in sources:
        if p.suffix.lower() == ".py":
            for stem in python_imports(p):
                target = stems.get(stem)
                if target and target != p.name:
                    graph[p.name].add(target)
                    graph[target].add(p.name)
                    edge_reasons[tuple(sorted((p.name, target)))].append("python_import")

    for p in sources:
        text = read_text(p)
        for target in names:
            if target != p.name and target in text:
                graph[p.name].add(target)
                graph[target].add(p.name)
                edge_reasons[tuple(sorted((p.name, target)))].append("filename_reference")

    return graph, edge_reasons

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
    sources = sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS],
        key=lambda p: p.name.lower()
    )

    graph, edge_reasons = build_graph(sources)
    comps = connected_components(graph)

    # Exclude isolated cleanup tooling from migration candidates.
    rows = []
    group_rows = []

    for gid, comp in enumerate(comps, start=1):
        members = [root / name for name in comp]
        roles = [role(p) for p in members]
        classes = [classify(p) for p in members]

        projects = sorted(set(p for p, _ in classes))
        phases = sorted(set(ph for _, ph in classes))

        has_sensitive = any(r in {"CANONICAL_OR_FROZEN", "BACKUP_PROVENANCE"} for r in roles)
        has_cleanup = any(classify(p) == ("utilities", "cleanup") for p in members)
        has_unclassified = any(classify(p)[0] == "unclassified" for p in members)

        if has_cleanup:
            status = "KEEP_ROOT_CLEANUP"
        elif has_sensitive:
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

    groups_csv = outdir / f"stage4_wave2_dependency_groups_{stamp}.csv"
    files_csv = outdir / f"stage4_wave2_dependency_files_{stamp}.csv"
    json_path = outdir / f"stage4_wave2_dependency_groups_{stamp}.json"

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

    print("=== STAGE 4 WAVE 2 DEPENDENCY-GROUP AUDIT ===")
    print(f"Root source files: {len(sources)}")
    print(f"Dependency groups total: {len(group_rows)}")
    print(f"Non-isolated groups: {len(nonisolated)}")
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
    print("NO FILES MOVED, DELETED, OR EDITED.")
    print(f"Groups CSV: {groups_csv}")
    print(f"Files CSV : {files_csv}")
    print(f"JSON      : {json_path}")

if __name__ == "__main__":
    main()
