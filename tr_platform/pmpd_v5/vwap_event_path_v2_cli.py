from pathlib import Path
import argparse,json,zipfile
from .vwap_event_path_v2 import run
def main():
    p=argparse.ArgumentParser(); p.add_argument("--repo-root",default="."); p.add_argument("--year",type=int,default=2025)
    p.add_argument("--no-verify-hash",action="store_true"); p.add_argument("--output-dir",default="pmpd_v5_9j_vwap_event_path_v2")
    a=p.parse_args(); repo=Path(a.repo_root).resolve(); out=repo/a.output_dir; out.mkdir(parents=True,exist_ok=True)
    d,s,m=run(repo_root=repo,year=a.year,verify_hash=not a.no_verify_hash)
    d.to_csv(out/"decision_vwap_event_path_v2.csv",index=False); s.to_csv(out/"symbol_summary.csv",index=False)
    (out/"run_fingerprint.json").write_text(json.dumps(m,indent=2,sort_keys=True),encoding="utf-8")
    z=repo/f"{a.output_dir}.zip"
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as q:
        for f in out.rglob("*"):
            if f.is_file(): q.write(f,f.relative_to(out))
    print("9J VWAP Event Path V2 complete."); print(json.dumps(m,indent=2)); print(f"Package: {z}")
if __name__=="__main__": main()
