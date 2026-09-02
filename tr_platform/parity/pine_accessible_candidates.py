from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
from typing import Optional
import json
import pandas as pd
from tr_platform.universe.pmpd_universe import load_validated_universe

PROTOCOL_SHA256="924a410da843d6a6d8ddb267d3b88d6e824a815c983e0cb4847ccfb6532c0b46"
DECISION_CODE="PMPD_8H7B2B_TV_HISTORY_ACCESS_V1"
SAMPLE_VERSION="PMPD_V4_PINE_PARITY_CANDIDATES_V2"
ACCESS_START="2026-02-23"
ACCESS_END="2026-08-28"
CANDIDATES_PER_SET=12
KNOWN_SPARSE={"MNDY","NOW","KLAC","BKNG","BLK","AXON","URI","REGN"}
REQUIRED_SPARSE={"SET_1":None,"SET_2":"MNDY","SET_3":"BKNG","SET_4":"BLK"}
MARKET_CLOSED_DATES={"2026-04-03","2026-05-25","2026-06-19","2026-07-03"}

@dataclass(frozen=True)
class PineParityCandidate:
    candidate_id:str
    sample_version:str
    set_code:str
    position_in_set:int
    symbol:str
    trade_date:str
    source_sparse_symbol:bool
    selection_rank:int
    selection_hash:str
    access_window_start:str
    access_window_end:str
    selection_basis:str

def eligible_trading_dates():
    out=[]
    for d in pd.date_range(ACCESS_START,ACCESS_END,freq="D"):
        iso=d.strftime("%Y-%m-%d")
        if d.weekday()<5 and iso not in MARKET_CLOSED_DATES:
            out.append(iso)
    return out

def _hash_key(set_code,symbol,trade_date):
    payload=f"{PROTOCOL_SHA256}|{DECISION_CODE}|{ACCESS_START}|{ACCESS_END}|{set_code}|{symbol}|{trade_date}"
    return sha256(payload.encode()).hexdigest()

def build_candidate_manifest(repo_root:Optional[Path]=None):
    if repo_root is None:
        repo_root=Path(__file__).resolve().parents[2]
    members=load_validated_universe(repo_root.resolve())
    dates=eligible_trading_dates()
    by_set={}
    for m in members: by_set.setdefault(m.set_code,[]).append(m)
    result=[]
    for set_code in sorted(by_set):
        pool=[]
        for m in sorted(by_set[set_code], key=lambda x:x.position_in_set):
            for dt in dates: pool.append((_hash_key(set_code,m.symbol,dt),m,dt))
        pool.sort(key=lambda x:x[0])
        chosen=[]; used=set()
        req=REQUIRED_SPARSE.get(set_code)
        if req:
            row=next(x for x in pool if x[1].symbol==req)
            chosen.append(row); used.add(req)
        for row in pool:
            if row[1].symbol in used: continue
            chosen.append(row); used.add(row[1].symbol)
            if len(chosen)>=CANDIDATES_PER_SET: break
        chosen.sort(key=lambda x:x[0])
        if len(chosen)!=CANDIDATES_PER_SET: raise RuntimeError(set_code)
        for rank,(h,m,dt) in enumerate(chosen,1):
            result.append(PineParityCandidate(
                f"{set_code}_{rank:02d}_{m.symbol}_{dt}",SAMPLE_VERSION,set_code,
                m.position_in_set,m.symbol,dt,m.symbol in KNOWN_SPARSE,rank,h,
                ACCESS_START,ACCESS_END,
                "Deterministic protocol+access-window hash selection; no Python PMPD signal output used."
            ))
    return result

def write_candidate_manifest(cases,repo_root:Optional[Path]=None):
    if repo_root is None: repo_root=Path(__file__).resolve().parents[2]
    out=repo_root.resolve()/"docs"/"pmpd"/"parity"; out.mkdir(parents=True,exist_ok=True)
    rows=[asdict(c) for c in cases]
    csv=out/f"{SAMPLE_VERSION}.csv"; js=out/f"{SAMPLE_VERSION}.json"
    pd.DataFrame(rows).to_csv(csv,index=False)
    js.write_text(json.dumps(rows,indent=2,sort_keys=True),encoding="utf-8")
    digest=sha256(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return csv,js,digest
