#!/usr/bin/env python
from __future__ import annotations

"""
TradingResearch Stage 3 source-code migration audit.

Purpose
-------
Audit root-level .py/.ps1/.pine files before any relocation.

This script DOES NOT MOVE, DELETE, OR EDIT SOURCE CODE.

It:
  1. inventories root source files;
  2. classifies project / phase / source role;
  3. detects Python import relationships using AST;
  4. detects executable/script references and important path literals;
  5. flags canonical/provenance-sensitive files;
  6. proposes destinations;
  7. writes CSV + JSON reports under cleanup_reports.

Run:
    python cleanup_tradingresearch_stage3_audit.py

Optional:
    python cleanup_tradingresearch_stage3_audit.py --root "C:\path\to\TradingResearch"
"""

import argparse
import ast
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

SOURCE_EXTS = {".py", ".ps1", ".pine"}
TEXT_EXTS = {
    ".py", ".ps1", ".pine", ".md", ".txt", ".sql", ".json",
    ".toml", ".yaml", ".yml", ".ini", ".cfg", ".csv"
}

# Directories that should not be searched for executable dependencies.
SEARCH_SKIP_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache",
    "market_cache", "archive", "cleanup_reports"
}

# Important paths whose relocation can break active research code.
PROTECTED_PATH_TOKENS = [
    "pmpd_v5_9m_oos_candidate_dp4_v1.parquet",
    "pmpd_v5_9m_oos_candidate_dp4_v1_manifest.json",
    "pmpd_v5_9n_3s_h2h_summary.json",
    "pmpd_v5_9n_3s_symbol_h2h.csv",
    "pmpd_v5_9n_3s_monthly_h2h.csv",
    "pmpd_v5_9n_3s_v4_events_2026.parquet",
    "data/second1m_alt_entry_cache_v1",
    r"data\second1m_alt_entry_cache_v1",
]

PMPD_EXACT_OR_PREFIX = (
    "audit_9m_", "audit_9n_", "build_9k_", "build_9m_",
    "certify_9m_", "certify_9n_", "derive_and_certify_dp4_",
    "diagnose_9n_", "extract_9n_", "freeze_9j_", "freeze_9m_",
    "inspect_dp_structural_", "inspect_v4_parity_",
    "join_and_audit_frozen_9h_", "parse_9n_", "patch_9k_",
    "patch_9n_", "patch_certify_v2_", "patch_discovery_stage1_",
    "patch_dp4_", "patch_outcome_", "patch_validation_",
    "preflight_9k_", "preflight_9m_", "preflight_9n_",
    "probe_9n_", "recover_9n_", "run_9j_", "run_9k_", "run_9m_",
    "run_9n_", "summarize_9j_", "v4_parity_engine", "vwap_event_path_v2",
)

SECOND1M_PREFIXES = (
    "a37_", "a38_", "a39_", "a40_", "a41_", "a42_", "a43_", "a44_",
    "a45_", "a46_", "a47_", "a48_", "a49_", "a50_", "a51_", "a52_",
    "a53_", "a54_", "a55_", "a56_", "ae2_", "altc2_", "second1m_",
    "research_second1m_", "validate_second1m_", "acquire_second1m_",
    "archive_second1m_", "import_second1m_", "import_second_candle_",
    "initialize_altc2_", "report_altc2_", "run_altc2_", "score_altc2_",
    "update_altc2_", "fthc_", "s1m_",
)

MARKET_DATA_PATTERNS = (
    "massive", "market_data", "market_benchmark", "vrtx_massive",
)

ORB_PATTERNS = (
    "orb", "build_6_", "6_2.pine",
)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def norm(s: str) -> str:
    return s.lower().replace(" ", "_").replace("-", "_")

def classify_project(name: str) -> tuple[str, str]:
    n = norm(name)

    # PM+PD
    if (
        "pmpd" in n
        or "pm_pd_breakout" in n
        or "pm_+_pd_breakout" in n
        or n.startswith(PMPD_EXACT_OR_PREFIX)
        or re.search(r"(?:^|_)9[ghijklmn](?:_|$)", n)
    ):
        m = re.search(r"(?:^|_)(9[ghijklmn])(?:_|$)", n)
        if m:
            return "pmpd", m.group(1)
        if "v4" in n or "parity" in n:
            return "pmpd", "v4"
        return "pmpd", "legacy"

    # Second1M
    if n.startswith(SECOND1M_PREFIXES) or any(x in n for x in ("alternative_c2", "second_candle")):
        if "altc2" in n or "alternative_c2" in n:
            return "second1m", "altc2"
        if "ae2" in n:
            return "second1m", "ae2"
        m = re.match(r"a(3[7-9]|4\d|5[0-6])_", n)
        if m:
            return "second1m", "a37_a56"
        if "fthc" in n:
            return "second1m", "fthc"
        if any(x in n for x in ("acquire_", "import_", "archive_")):
            return "second1m", "ingestion"
        return "second1m", "legacy"

    # ORB
    if any(x in n for x in ORB_PATTERNS):
        return "orb", "legacy"

    # Market data
    if any(x in n for x in MARKET_DATA_PATTERNS):
        return "market_data", "utilities"

    # Cleanup and repo helpers
    if n.startswith("cleanup_tradingresearch_"):
        return "utilities", "cleanup"

    return "unclassified", "review"

def classify_role(name: str) -> str:
    n = norm(name)

    if any(x in n for x in ("pre_patch_backup", "_backup", "backup_", "pre_symbol_guard")):
        return "BACKUP_PROVENANCE"
    if any(x in n for x in ("final", "frozen", "candidate_model", "protocol")):
        return "CANONICAL_OR_FROZEN"
    if any(x in n for x in ("patch", "_fix", "fix1", "fix2", "fix3", "fix4", "fix5", "fix6", "fix7", "fix8", "fix9")):
        return "PATCH_OR_FIX"
    if any(x in n for x in ("audit", "diagnose", "inspect", "inventory", "trace", "preflight", "certify", "probe", "summarize")):
        return "AUDIT_DIAGNOSTIC"
    if any(x in n for x in ("research_", "discovery", "robustness", "evaluate_", "score_", "freeze_", "build_", "run_")):
        return "RESEARCH_EXECUTABLE"
    if Path(name).suffix.lower() == ".pine":
        return "PINE_SOURCE"
    return "UTILITY_OR_UNKNOWN"

def proposed_destination(root: Path, path: Path, project: str, phase: str, role: str) -> str:
    ext = path.suffix.lower()
    name = path.name

    # Provenance backups stay distinct and go to archive/source only after explicit approval.
    if role == "BACKUP_PROVENANCE":
        return str((root / "archive" / "source" / project / phase / name).relative_to(root))

    if ext == ".pine":
        return str((root / "pine" / project / phase / name).relative_to(root))

    return str((root / "scripts" / project / phase / name).relative_to(root))

def parse_python_imports(path: Path) -> set[str]:
    out: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return out

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module.split(".")[0])
    return out

def get_root_sources(root: Path) -> list[Path]:
    return sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS],
        key=lambda p: p.name.lower()
    )

def searchable_text_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] in SEARCH_SKIP_DIRS:
            continue
        yield p

def executable_reference_scan(root: Path, sources: list[Path]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """
    Returns:
      script_refs[target_filename] -> files containing likely executable calls
      protected_refs[token] -> files referencing protected data paths

    This intentionally avoids treating arbitrary historical prose mentions as dependencies.
    """
    target_names = {p.name for p in sources}
    refs: dict[str, list[str]] = defaultdict(list)
    protected: dict[str, list[str]] = defaultdict(list)

    invocation_markers = (
        "python ", "python.exe", "python -m", "subprocess", "runpy",
        "powershell", "pwsh", "& ", "start-process", "invoke-expression",
        "import ", "from "
    )

    for p in searchable_text_files(root):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel = str(p.relative_to(root))

        # Important artifact/path references.
        low = text.lower()
        for token in PROTECTED_PATH_TOKENS:
            if token.lower() in low:
                protected[token].append(rel)

        # Direct script references only when line looks executable/config-like.
        for line in text.splitlines():
            line_low = line.lower()
            if not any(m in line_low for m in invocation_markers):
                continue
            for target in target_names:
                if target in line:
                    refs[target].append(rel)

    # Python AST import relationships among root modules.
    module_to_file = {p.stem: p.name for p in sources if p.suffix.lower() == ".py"}
    for src in sources:
        if src.suffix.lower() != ".py":
            continue
        for module in parse_python_imports(src):
            target = module_to_file.get(module)
            if target and target != src.name:
                refs[target].append(str(src.relative_to(root)))

    # Deduplicate
    refs = {k: sorted(set(v)) for k, v in refs.items()}
    protected = {k: sorted(set(v)) for k, v in protected.items()}
    return refs, protected

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"C:\Users\DirtySouth\TradingResearch")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Root does not exist: {root}")

    sources = get_root_sources(root)
    refs, protected_refs = executable_reference_scan(root, sources)

    rows: list[dict[str, object]] = []
    for p in sources:
        project, phase = classify_project(p.name)
        role = classify_role(p.name)
        ref_list = refs.get(p.name, [])

        # Review severity.
        if project == "unclassified":
            disposition = "MANUAL_CLASSIFICATION_REQUIRED"
        elif ref_list:
            disposition = "DEPENDENCY_REVIEW_REQUIRED"
        elif role in {"CANONICAL_OR_FROZEN", "BACKUP_PROVENANCE"}:
            disposition = "PROVENANCE_REVIEW_REQUIRED"
        else:
            disposition = "MOVE_CANDIDATE_AFTER_REVIEW"

        rows.append({
            "name": p.name,
            "extension": p.suffix.lower(),
            "bytes": p.stat().st_size,
            "sha256": sha256(p),
            "project": project,
            "phase": phase,
            "role": role,
            "proposed_destination": proposed_destination(root, p, project, phase, role),
            "executable_reference_count": len(ref_list),
            "executable_references": " | ".join(ref_list),
            "disposition": disposition,
        })

    outdir = root / "cleanup_reports"
    outdir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = outdir / f"stage3_source_migration_audit_{stamp}.csv"
    json_path = outdir / f"stage3_source_migration_audit_{stamp}.json"
    protected_path = outdir / f"stage3_protected_path_references_{stamp}.json"
    summary_path = outdir / f"stage3_source_migration_summary_{stamp}.txt"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    protected_path.write_text(json.dumps(protected_refs, indent=2), encoding="utf-8")

    project_counts = Counter(str(r["project"]) for r in rows)
    disposition_counts = Counter(str(r["disposition"]) for r in rows)
    role_counts = Counter(str(r["role"]) for r in rows)

    lines = []
    lines.append("=== STAGE 3 SOURCE MIGRATION AUDIT ===")
    lines.append(f"Root source files: {len(rows)}")
    lines.append("")
    lines.append("Projects:")
    for k, v in sorted(project_counts.items()):
        lines.append(f"  {k:18s} {v}")
    lines.append("")
    lines.append("Dispositions:")
    for k, v in sorted(disposition_counts.items()):
        lines.append(f"  {k:32s} {v}")
    lines.append("")
    lines.append("Roles:")
    for k, v in sorted(role_counts.items()):
        lines.append(f"  {k:24s} {v}")
    lines.append("")
    lines.append("Protected path references:")
    for token in PROTECTED_PATH_TOKENS:
        vals = protected_refs.get(token, [])
        lines.append(f"  {token}: {len(vals)}")
        for rel in vals[:10]:
            lines.append(f"      - {rel}")
    lines.append("")
    lines.append("NO SOURCE CODE WAS MOVED, DELETED, OR EDITED.")
    lines.append(f"CSV: {csv_path}")
    lines.append(f"JSON: {json_path}")
    lines.append(f"Protected refs: {protected_path}")

    summary = "\n".join(lines)
    summary_path.write_text(summary, encoding="utf-8")
    print(summary)

if __name__ == "__main__":
    main()
