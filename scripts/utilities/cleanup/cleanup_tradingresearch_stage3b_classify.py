#!/usr/bin/env python
from __future__ import annotations

r"""
TradingResearch Stage 3B source classification refinement.

Audit only. DOES NOT MOVE, DELETE, OR EDIT SOURCE CODE.

Run from repository root:
    python .\cleanup_tradingresearch_stage3b_classify.py
"""

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

SOURCE_EXTS = {".py", ".ps1", ".pine"}

def nrm(s: str) -> str:
    return s.lower().replace("-", "_").replace(" ", "_")

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return ""

def phase_from_name(name: str, project: str) -> str:
    n = nrm(name)

    if project == "pmpd":
        m = re.search(r"(?:^|_)(9[g-n])(?:_|$)", n)
        if m:
            return m.group(1)
        if "v4" in n or "parity" in n or "forward_validation" in n:
            return "v4"
        return "legacy"

    if project == "second1m":
        m = re.search(r"(?:^|_)(a(?:3[7-9]|4\d|5[0-6]))(?:_|$)", n)
        if m:
            return "a37_a56"
        if "altc2" in n or "alternative_c2" in n:
            return "altc2"
        if "ae2" in n:
            return "ae2"
        if "fthc" in n:
            return "fthc"
        if any(x in n for x in ("import_", "acquire_", "archive_")):
            return "ingestion"
        return "legacy"

    if project == "orb":
        return "legacy"
    if project == "market_data":
        return "utilities"
    if project == "osi":
        return "parity"
    if project == "utilities":
        return "cleanup" if "cleanup_tradingresearch" in n else "misc"
    return "review"

def classify(path: Path) -> tuple[str, str, list[str]]:
    name = path.name
    n = nrm(name)
    text = read_text(path)
    reasons = []

    # Cleanup tooling
    if n.startswith("cleanup_tradingresearch_"):
        return "utilities", "HIGH", ["cleanup filename"]

    # OSI is a distinct Pine family; preserve separately rather than guessing.
    if n.startswith("osi_"):
        return "osi", "HIGH", ["OSI filename family"]

    # ORB
    if "orb" in n or n == "6_2.pine":
        return "orb", "HIGH", ["ORB filename"]

    # Second1M explicit filename families.
    if (
        re.search(r"(?:^|_)(a(?:3[7-9]|4\d|5[0-6]))(?:_|$)", n)
        or any(x in n for x in (
            "second1m", "second_candle", "alternative_c2", "altc2",
            "ae2_", "fthc_", "s1m_"
        ))
    ):
        return "second1m", "HIGH", ["Second1M A37-A56/AE2/AltC2 filename family"]

    # PM+PD explicit filename families.
    if (
        "pmpd" in n
        or "pm_pd_breakout" in n
        or "pm_+_pd_breakout" in n
        or "v4_parity" in n
        or "vwap_event_path" in n
        or "dp4" in n
        or re.search(r"(?:^|_)(9[g-n])(?:_|$)", n)
    ):
        return "pmpd", "HIGH", ["PM+PD filename family"]

    # Market data utilities
    if any(x in n for x in ("massive", "market_data", "market_benchmark", "vrtx_massive")):
        return "market_data", "HIGH", ["market-data filename"]

    # Content-based classification for generic filenames.
    scores = {
        "pmpd": 0,
        "second1m": 0,
        "orb": 0,
        "market_data": 0,
    }

    content_terms = {
        "pmpd": (
            ("pmpd", 4), ("pm+pd", 4), ("pm + pd", 4),
            ("vwap_event_path", 3), ("dp4_", 3),
            ("pmpd_v5", 5), ("v4_parity", 4),
        ),
        "second1m": (
            ("second1m", 5), ("second 1m", 4), ("second 1-minute", 4),
            ("altc2", 5), ("alternative_c2", 5), ("ae2_", 4),
            ("a37_", 3), ("a38_", 3), ("a39_", 3), ("a41_", 3),
            ("a42_", 3), ("a51_", 3), ("a52_", 3), ("a53_", 3),
            ("a56_", 3),
        ),
        "orb": (("15m orb", 5), ("opening range breakout", 4),),
        "market_data": (("massive", 3), ("market_cache", 2),),
    }

    for project, terms in content_terms.items():
        for term, weight in terms:
            if term in text:
                scores[project] += weight

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_project, top_score = ranked[0]
    second_score = ranked[1][1]

    if top_score >= 5 and top_score >= second_score + 2:
        reasons.append(f"content score {scores}")
        return top_project, "MEDIUM", reasons

    # Generic test/helper file.
    if n == "test.py":
        return "utilities", "LOW", ["generic test file; manual review recommended"]

    return "unclassified", "LOW", [f"no decisive signal; content score {scores}"]

def role(name: str) -> str:
    n = nrm(name)
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
    if any(x in n for x in (
        "research_", "discovery", "robustness", "evaluate_",
        "score_", "freeze_", "build_", "run_"
    )):
        return "RESEARCH_EXECUTABLE"
    if Path(name).suffix.lower() == ".pine":
        return "PINE_SOURCE"
    return "UTILITY_OR_UNKNOWN"

def proposed_destination(root: Path, p: Path, project: str, phase: str, r: str) -> str:
    if r == "BACKUP_PROVENANCE":
        dest = root / "archive" / "source" / project / phase / p.name
    elif p.suffix.lower() == ".pine":
        dest = root / "pine" / project / phase / p.name
    else:
        dest = root / "scripts" / project / phase / p.name
    return str(dest.relative_to(root))

def main():
    root = Path(__file__).resolve().parent
    sources = sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS],
        key=lambda p: p.name.lower()
    )

    rows = []
    for p in sources:
        project, confidence, reasons = classify(p)
        phase = phase_from_name(p.name, project)
        r = role(p.name)

        if project == "unclassified":
            disposition = "MANUAL_CLASSIFICATION_REQUIRED"
        elif confidence == "LOW":
            disposition = "MANUAL_REVIEW_RECOMMENDED"
        elif r in {"BACKUP_PROVENANCE", "CANONICAL_OR_FROZEN"}:
            disposition = "PROVENANCE_REVIEW_REQUIRED"
        else:
            disposition = "CLASSIFIED_MOVE_CANDIDATE"

        rows.append({
            "name": p.name,
            "extension": p.suffix.lower(),
            "project": project,
            "phase": phase,
            "role": r,
            "confidence": confidence,
            "reason": " | ".join(reasons),
            "proposed_destination": proposed_destination(root, p, project, phase, r),
            "disposition": disposition,
        })

    outdir = root / "cleanup_reports"
    outdir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = outdir / f"stage3b_refined_source_classification_{stamp}.csv"
    json_path = outdir / f"stage3b_refined_source_classification_{stamp}.json"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    pc = Counter(r["project"] for r in rows)
    cc = Counter(r["confidence"] for r in rows)
    dc = Counter(r["disposition"] for r in rows)

    print("=== STAGE 3B REFINED SOURCE CLASSIFICATION ===")
    print(f"Root source files: {len(rows)}")
    print("")
    print("Projects:")
    for k, v in sorted(pc.items()):
        print(f"  {k:18s} {v}")
    print("")
    print("Confidence:")
    for k, v in sorted(cc.items()):
        print(f"  {k:8s} {v}")
    print("")
    print("Dispositions:")
    for k, v in sorted(dc.items()):
        print(f"  {k:32s} {v}")

    unresolved = [r for r in rows if r["project"] == "unclassified" or r["confidence"] == "LOW"]
    print("")
    print(f"Still requiring manual classification/review: {len(unresolved)}")
    for r in unresolved:
        print(f"  - {r['name']} -> {r['project']} / {r['confidence']}")

    print("")
    print("NO SOURCE CODE WAS MOVED, DELETED, OR EDITED.")
    print(f"CSV : {csv_path}")
    print(f"JSON: {json_path}")

if __name__ == "__main__":
    main()
