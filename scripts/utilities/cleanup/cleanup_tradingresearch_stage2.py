#!/usr/bin/env python
"""
Stage 2 cleanup for C:\Users\DirtySouth\TradingResearch

SAFE DEFAULT:
  python cleanup_tradingresearch_stage2.py scan

Then:
  python cleanup_tradingresearch_stage2.py apply-review-items

This script:
- classifies remaining root source files into better project/phase destinations
- scans text/source files for filename references before proposing source moves
- writes source dependency + move manifests
- does NOT move source code automatically
- safely moves the known non-code REVIEW items
- safely removes the two stranded exact duplicates if their canonical copies exist
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")
TEXT_EXTS = {".py",".ps1",".pine",".md",".txt",".sql",".json",".toml",".yaml",".yml",".ini",".cfg"}

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()

def classify_source(name):
    n=name.lower(); ext=Path(name).suffix.lower()
    # PMPD first: 9J-9N and V4/parity family
    if re.search(r"(^|_)(9[j-n])(_|$)", n) or "v4_parity" in n or "pmpd" in n or "dp4_" in n or "vwap_event_path_v2" in n:
        proj="pmpd"
        m=re.search(r"(^|_)(9[j-n])(_|$)", n)
        phase=m.group(2) if m else ("v4" if "v4" in n or "parity" in n else "legacy")
    elif re.search(r"(second1m|second_candle|2ndcandle|altc2|ae2|s1m_|fthc_|^a(?:3[7-9]|4\d|5[0-6])_)", n):
        proj="second1m"
        if "altc2" in n: phase="altc2"
        elif "ae2" in n: phase="ae2"
        elif re.match(r"a(?:3[7-9]|4\d|5[0-6])_", n): phase="a37_a56"
        elif "fthc" in n: phase="fthc"
        else: phase="legacy"
    elif "orb" in n or n.startswith("build_6_") or n=="6_2.pine":
        proj="orb"; phase="legacy"
    elif "massive" in n or "market_data" in n or "market_benchmark" in n or "vrtx_massive" in n:
        proj="market_data"; phase="utilities"
    elif n.startswith(("test.","cleanup_","install_")):
        proj="utilities"; phase="misc"
    else:
        proj="utilities"; phase="legacy"

    if ext==".pine":
        dest=ROOT/"pine"/proj/phase/name
    else:
        dest=ROOT/"scripts"/proj/phase/name
    return proj,phase,dest

def source_files():
    return [p for p in ROOT.iterdir() if p.is_file() and p.suffix.lower() in {".py",".ps1",".pine"}]

def searchable_files():
    skip={".git",".venv","market_cache","data"}
    out=[]
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in TEXT_EXTS: continue
        try:
            rel=p.relative_to(ROOT)
            if rel.parts and rel.parts[0] in skip: continue
        except Exception: pass
        out.append(p)
    return out

def dependency_scan(srcs):
    corpus=[]
    for p in searchable_files():
        try:
            txt=p.read_text(encoding="utf-8",errors="ignore")
            corpus.append((p,txt))
        except Exception: pass
    rows=[]
    for src in srcs:
        refs=[]
        for p,txt in corpus:
            if p==src: continue
            if src.name in txt:
                refs.append(str(p.relative_to(ROOT)))
        proj,phase,dest=classify_source(src.name)
        rows.append({
            "name":src.name,"project":proj,"phase":phase,
            "proposed_destination":str(dest.relative_to(ROOT)),
            "reference_count":len(refs),
            "references":" | ".join(refs[:50]),
            "move_status":"REVIEW_REFERENCED" if refs else "CANDIDATE_UNREFERENCED"
        })
    return rows

def write_reports(rows):
    out=ROOT/"cleanup_reports"; out.mkdir(exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    cp=out/f"stage2_source_move_manifest_{stamp}.csv"
    jp=out/f"stage2_source_move_manifest_{stamp}.json"
    with cp.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    jp.write_text(json.dumps(rows,indent=2),encoding="utf-8")
    return cp,jp

def move_no_overwrite(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists():
        if src.is_file() and dst.is_file() and sha(src)==sha(dst):
            return "IDENTICAL_DEST_EXISTS"
        return "DEST_EXISTS"
    shutil.move(str(src),str(dst)); return "MOVED"

def apply_review_items():
    moves = {
        "MajorIndexes_5MinLookback": ROOT/"research_outputs"/"orb"/"legacy_research"/"MajorIndexes_5MinLookback",
        "Set1_CVS_Test": ROOT/"research_outputs"/"orb"/"legacy_research"/"Set1_CVS_Test",
        "Set2_CVS_Test": ROOT/"research_outputs"/"orb"/"legacy_research"/"Set2_CVS_Test",
        "Set4_5MinLookback": ROOT/"research_outputs"/"orb"/"legacy_research"/"Set4_5MinLookback",
        "Set4_CVS_Test": ROOT/"research_outputs"/"orb"/"legacy_research"/"Set4_CVS_Test",
        "Screenshot 2026-09-05 131332.png": ROOT/"archive"/"screenshots"/"Screenshot 2026-09-05 131332.png",
        "v4_parity_validation_inspection.txt": ROOT/"research_outputs"/"pmpd"/"9n"/"v4_parity_validation_inspection.txt",
    }
    print("=== REVIEW ITEM CLEANUP ===")
    for name,dst in moves.items():
        src=ROOT/name
        if src.exists(): print(name, "->", move_no_overwrite(src,dst))
        else: print(name, "-> NOT_PRESENT")

    # Stranded duplicate SQL: canonical was already moved.
    dup_sql=ROOT/"031_pmpd_v5_thread_handoff_9j_vwap_event_path_v2 (1).sql"
    canon_sql=ROOT/"sql"/"pmpd"/"031_pmpd_v5_thread_handoff_9j_vwap_event_path_v2.sql"
    if dup_sql.exists() and canon_sql.exists() and sha(dup_sql)==sha(canon_sql):
        dup_sql.unlink(); print(dup_sql.name, "-> DELETED_EXACT_DUPLICATE")

    dup_zip=ROOT/"PMPD_V5_9I_FINAL_CLOSEOUT (1).zip"
    canon_zip=ROOT/"archive"/"packages"/"pmpd"/"PMPD_V5_9I_FINAL_CLOSEOUT.zip"
    if dup_zip.exists() and canon_zip.exists() and sha(dup_zip)==sha(canon_zip):
        dup_zip.unlink(); print(dup_zip.name, "-> DELETED_EXACT_DUPLICATE")

    print(".git -> KEPT")
    print("cleanup_reports -> KEPT until cleanup is finished")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("command",choices=["scan","apply-review-items"])
    a=ap.parse_args()
    if a.command=="apply-review-items":
        apply_review_items()
    srcs=source_files()
    rows=dependency_scan(srcs)
    cp,jp=write_reports(rows)
    counts=defaultdict(int)
    projects=defaultdict(int)
    for r in rows:
        counts[r["move_status"]]+=1; projects[r["project"]]+=1
    print("\n=== SOURCE DEPENDENCY SCAN ===")
    print("Root source files:",len(rows))
    for k in sorted(projects): print(f"{k:14s}: {projects[k]}")
    for k in sorted(counts): print(f"{k:24s}: {counts[k]}")
    print("Manifest CSV :",cp)
    print("Manifest JSON:",jp)
    print("\nNO SOURCE CODE WAS MOVED.")

if __name__=="__main__":
    main()
