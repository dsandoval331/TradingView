from __future__ import annotations

import argparse
import json
import shutil
from hashlib import sha256
from pathlib import Path

import pandas as pd

from .factor_batch1 import BATCH_ID, PROTOCOL_ID, run_batch1


def main() -> None:
    p=argparse.ArgumentParser(description="Run PMPD V5 9H factor batch 1")
    p.add_argument("--input",default="pmpd_v5_9h_research_dataset_v1/decision_research.csv")
    p.add_argument("--output",default="pmpd_v5_9h_factor_batch1")
    args=p.parse_args()

    inp=Path(args.input).resolve(); out=Path(args.output).resolve()
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(inp,low_memory=False)
    results=run_batch1(df)
    for name,frame in results.items(): frame.to_csv(out/f"{name}.csv",index=False)
    payload={
        "batch_id":BATCH_ID,"protocol_id":PROTOCOL_ID,
        "input_rows":int(len(df)),
        "factor_summary_rows":int(len(results['factor_summary'])),
        "contrast_rows":int(len(results['continuous_contrasts'])),
    }
    payload["run_fingerprint"]=sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    (out/"run_fingerprint.json").write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8")
    archive=shutil.make_archive(str(out),"zip",root_dir=out)
    print(json.dumps(payload,indent=2,sort_keys=True)); print(f"Package: {archive}")

if __name__=="__main__": main()
