from pathlib import Path
import argparse,json,zipfile
from .vwap_enrichment import run_full_universe_vwap_enrichment
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",default=".")
    ap.add_argument("--year",type=int,default=2025)
    ap.add_argument("--no-verify-hash",action="store_true")
    ap.add_argument("--output-dir",default="pmpd_v5_9j_vwap_enrichment_v1")
    a=ap.parse_args()
    repo=Path(a.repo_root).resolve(); out=repo/a.output_dir; out.mkdir(parents=True,exist_ok=True)
    df,s,m=run_full_universe_vwap_enrichment(repo_root=repo,year=a.year,verify_hash=not a.no_verify_hash)
    df.to_csv(out/"decision_vwap_enrichment.csv",index=False)
    s.to_csv(out/"symbol_summary.csv",index=False)
    (out/"run_fingerprint.json").write_text(json.dumps(m,indent=2,sort_keys=True),encoding="utf-8")
    z=repo/f"{a.output_dir}.zip"
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as q:
        for fp in out.rglob("*"):
            if fp.is_file(): q.write(fp,fp.relative_to(out))
    print("9J VWAP enrichment complete.")
    print(json.dumps(m,indent=2,sort_keys=True))
    print(f"Package: {z}")
if __name__=="__main__": main()
