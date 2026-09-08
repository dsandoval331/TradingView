#!/usr/bin/env python
from __future__ import annotations
import argparse, csv, hashlib, json, re, shutil
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

ROOT_DEFAULT = Path(r"C:\Users\DirtySouth\TradingResearch")
KEEP_DIRS = {".venv","config","data","docs","logs","market_cache","OlderProjectFolders","research","research_outputs","sql","strategies","tests","tr_platform","archive","scripts","pine"}
KEEP_FILES = {".gitignore","README.md","requirements.txt"}
CACHE_DIRS = {".pytest_cache","__pycache__"}
ZERO_SAFE = {"temp.ping","MassiveAPI_Test","pmpd_v4_commit_files.txt"}

PMPD = re.compile(r"(pmpd|pm[_ +]?pd|premarket_scanner|pms_)", re.I)
SECOND1M = re.compile(r"(second1m|second_candle|2ndcandle|2mcandle|altc2|ae2|s1m_|a(?:3[7-9]|4\d|5[0-6])(?:_|$)|fthc_)", re.I)
ORB = re.compile(r"(orb|build_6_|6_2\.pine|majorindexes_5minlookback|set[124]_cvs_test|set4_5minlookback)", re.I)
MARKET = re.compile(r"(massive|market_|archive_second1m_market|import_second1m_market)", re.I)

@dataclass
class Row:
    name:str; kind:str; size_bytes:int; sha256:str; project:str; action:str
    destination:str; reason:str; duplicate_of:str=""; applied:bool=False; note:str=""

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()

def project_for(name:str)->str:
    if PMPD.search(name): return "pmpd"
    if SECOND1M.search(name): return "second1m"
    if ORB.search(name): return "orb"
    if MARKET.search(name): return "market_data"
    return "other"

def pmpd_phase(name:str)->str:
    m=re.search(r"(?:PMPD[_ -]?V5[_ -]?)?(9[H-N])(?:[_ -]|$)",name,re.I)
    if m: return m.group(1).lower()
    if "alpha" in name.lower(): return "alpha"
    if "v4" in name.lower(): return "v4"
    return "misc"

def classify_file(root:Path,p:Path,project:str):
    n=p.name; e=p.suffix.lower(); ln=n.lower()
    if n in KEEP_FILES: return ("KEEP_ROOT","","Repository-level file")
    if n.startswith("BATS_") and e==".csv":
        d=root/"research_outputs"/"pmpd"/"9n"/"tradingview_parity"/"raw_exports"/n
        return ("MOVE_SAFE",str(d),"TradingView parity raw export")
    if e==".sql":
        sub=project if project!="other" else "infrastructure"
        return ("MOVE_SAFE",str(root/"sql"/sub/n),"SQL belongs under sql/<project>")
    if e==".zip":
        sub=project if project!="other" else "other"
        return ("MOVE_SAFE",str(root/"archive"/"packages"/sub/n),"Transport/archive package")
    if ln.startswith("readme_") and e==".md":
        d=(root/"research_outputs"/"pmpd"/"docs_history"/n) if (project=="pmpd" or "9n" in ln or "8h" in ln) else (root/"archive"/"docs_history"/n)
        return ("MOVE_SAFE",str(d),"Historical experiment README")
    if project=="pmpd" and e in {".csv",".json",".parquet",".txt",".md"}:
        return ("MOVE_SAFE",str(root/"research_outputs"/"pmpd"/pmpd_phase(n)/n),"PMPD generated research artifact")
    if project=="second1m" and e in {".csv",".json",".parquet",".txt",".md"}:
        return ("MOVE_SAFE",str(root/"research_outputs"/"second1m"/"legacy_research"/n),"Second1M generated research artifact")
    if project=="orb" and e in {".csv",".json",".parquet",".txt",".md"}:
        return ("MOVE_SAFE",str(root/"research_outputs"/"orb"/"legacy_research"/n),"ORB generated research artifact")
    if e in {".py",".ps1",".pine"}:
        d=(root/"pine"/project/n) if e==".pine" else (root/"scripts"/project/n)
        return ("REVIEW_CODE_MOVE",str(d),"Source move may break paths/imports; review first")
    if e in {".csv",".json",".parquet"}:
        return ("MOVE_SAFE",str(root/"research_outputs"/"misc"/n),"Generated result artifact")
    return ("REVIEW","","Unclassified root file")

def inventory(root:Path):
    rows=[]; hashes=defaultdict(list)
    files=[p for p in root.iterdir() if p.is_file()]
    for p in files:
        try: hashes[sha256_file(p)].append(p)
        except Exception: pass
    for p in sorted(root.iterdir(), key=lambda x:x.name.lower()):
        if p.is_dir():
            if p.name in KEEP_DIRS:
                rows.append(Row(p.name,"dir",0,"","core","KEEP_ROOT","","Core directory"))
            elif p.name in CACHE_DIRS:
                rows.append(Row(p.name,"dir",0,"","cache","DELETE_SAFE","","Re-creatable cache directory"))
            elif p.name.startswith("pmpd_v5_"):
                d=root/"research_outputs"/"pmpd"/"legacy_generated_dirs"/p.name
                rows.append(Row(p.name,"dir",0,"","pmpd","MOVE_SAFE",str(d),"Generated PMPD research directory"))
            else:
                rows.append(Row(p.name,"dir",0,"",project_for(p.name),"REVIEW","","Unclassified directory"))
            continue
        h=sha256_file(p); project=project_for(p.name)
        action,dest,reason=classify_file(root,p,project)
        dup=""
        siblings=[x for x in hashes[h] if x!=p]
        if siblings and " (1)" in p.stem:
            action="DELETE_SAFE"; dup=siblings[0].name; dest=""; reason="Exact duplicate '(1)' copy"
        elif siblings: dup=siblings[0].name
        if p.stat().st_size==0 and p.name in ZERO_SAFE:
            action="DELETE_SAFE"; dest=""; reason="Known zero-byte temporary/diagnostic file"
        rows.append(Row(p.name,"file",p.stat().st_size,h,project,action,dest,reason,dup))
    return rows

def write_manifest(root,rows):
    out=root/"cleanup_reports"; out.mkdir(exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    cp=out/f"root_cleanup_manifest_{stamp}.csv"; jp=out/f"root_cleanup_manifest_{stamp}.json"
    with cp.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(asdict(rows[0]).keys())); w.writeheader()
        for r in rows: w.writerow(asdict(r))
    jp.write_text(json.dumps([asdict(r) for r in rows],indent=2),encoding="utf-8")
    return cp,jp

def print_summary(rows):
    c=defaultdict(int); s=defaultdict(int)
    for r in rows: c[r.action]+=1; s[r.action]+=r.size_bytes
    print("\n=== SUMMARY ===")
    for a in sorted(c): print(f"{a:18s} {c[a]:4d} items {s[a]/1048576:10.2f} MB")
    hg=defaultdict(list)
    for r in rows:
        if r.sha256: hg[r.sha256].append(r.name)
    d=[v for v in hg.values() if len(v)>1]
    print(f"Exact duplicate hash groups: {len(d)}")
    for g in d[:20]: print(" DUP:", " | ".join(g))

def safe_move(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists():
        if src.is_file() and dst.is_file() and sha256_file(src)==sha256_file(dst):
            return False,"identical destination already exists"
        return False,"destination exists; not overwritten"
    shutil.move(str(src),str(dst)); return True,""

def apply_safe(root,rows):
    for r in rows:
        if r.action!="MOVE_SAFE": continue
        src=root/r.name; dst=Path(r.destination)
        if not src.exists(): continue
        ok,note=safe_move(src,dst)
        print(("MOVE " if ok else "SKIP ")+f"{r.name}" + (f" -> {dst.relative_to(root)}" if ok else f": {note}"))

def delete_safe(root,rows):
    for r in rows:
        if r.action!="DELETE_SAFE": continue
        p=root/r.name
        if not p.exists(): continue
        if p.is_dir() and p.name in CACHE_DIRS:
            shutil.rmtree(p); print("DELETE DIR ",r.name); continue
        if p.is_file() and r.duplicate_of:
            o=root/r.duplicate_of
            if o.exists() and sha256_file(p)==sha256_file(o):
                p.unlink(); print("DELETE DUP ",r.name); continue
        if p.is_file() and p.stat().st_size==0 and p.name in ZERO_SAFE:
            p.unlink(); print("DELETE ZERO",r.name)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("command",choices=["scan","apply-safe","delete-safe"])
    ap.add_argument("--root",type=Path,default=ROOT_DEFAULT)
    a=ap.parse_args(); root=a.root.resolve()
    if not root.exists(): raise SystemExit(f"Missing root: {root}")
    print("ROOT:",root)
    rows=inventory(root); print_summary(rows)
    c,j=write_manifest(root,rows)
    print("\nManifest CSV :",c); print("Manifest JSON:",j)
    if a.command=="scan":
        print("\nSCAN ONLY — nothing moved or deleted."); return
    if a.command=="apply-safe": apply_safe(root,rows)
    if a.command=="delete-safe": delete_safe(root,rows)
    post=inventory(root); print_summary(post)
    c2,j2=write_manifest(root,post)
    print("\nPost-action CSV :",c2); print("Post-action JSON:",j2)

if __name__=="__main__":
    main()
