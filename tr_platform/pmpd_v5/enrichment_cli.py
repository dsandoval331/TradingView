from __future__ import annotations
from pathlib import Path
import argparse, json, zipfile
from .enrichment import run_full_universe_enrichment

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",default=".")
    ap.add_argument("--year",type=int,default=2025)
    ap.add_argument("--no-verify-hash",action="store_true")
    ap.add_argument("--output-dir",default="pmpd_v5_9h_enrichment_v1")
    args=ap.parse_args()
    repo=Path(args.repo_root).resolve()
    out=repo/args.output_dir
    out.mkdir(parents=True,exist_ok=True)
    enrich,summary,meta=run_full_universe_enrichment(
        repo_root=repo,year=args.year,verify_hash=not args.no_verify_hash
    )
    enrich.to_csv(out/"decision_enrichment.csv",index=False)
    summary.to_csv(out/"symbol_summary.csv",index=False)
    (out/"run_fingerprint.json").write_text(json.dumps(meta,indent=2,sort_keys=True),encoding="utf-8")
    zpath=repo/f"{args.output_dir}.zip"
    with zipfile.ZipFile(zpath,"w",zipfile.ZIP_DEFLATED) as z:
        for fp in out.rglob("*"):
            if fp.is_file(): z.write(fp,fp.relative_to(out))
    print("9H enrichment complete.")
    print(json.dumps(meta,indent=2,sort_keys=True))
    print(f"Package: {zpath}")

if __name__=="__main__":
    main()
