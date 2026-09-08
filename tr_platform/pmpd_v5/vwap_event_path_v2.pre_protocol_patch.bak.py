from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json
import numpy as np
import pandas as pd

from tr_platform.historical.certified_dataset import load_certified_partition
from tr_platform.universe.pmpd_universe import load_validated_universe
from .alpha import run_symbol_alpha
from .certification import _normalize_vector_columns

VERSION="PMPD_V5_9J_VWAP_EVENT_PATH_V2"
PARENT="PMPD_V5_9H_RESEARCH_DATASET_V1"
PROTOCOL="PMPD_V5_9J_ENTRY_ARCH_PROTOCOL_V1"

def _rth_vwap(day):
    x=day.sort_values("timestamp_utc").copy()
    tp=(pd.to_numeric(x.high)+pd.to_numeric(x.low)+pd.to_numeric(x.close))/3.0
    vol=pd.to_numeric(x.volume,errors="coerce").fillna(0.0)
    den=vol.cumsum()
    x["rth_vwap"]=(tp*vol).cumsum()/den.replace(0,np.nan)
    x["side_sign"]=np.sign(pd.to_numeric(x.close)-x.rth_vwap).fillna(0).astype(int)
    x["vwap_touch"]=(pd.to_numeric(x.low)<=x.rth_vwap)&(pd.to_numeric(x.high)>=x.rth_vwap)
    return x

def _path_features(day,start_ts,end_ts,direction):
    start=pd.Timestamp(start_ts); end=pd.Timestamp(end_ts)
    # Event path is inclusive of DP1 contact bar and current completed decision bar.
    d=day[(day.timestamp_utc>=start)&(day.timestamp_utc<=end)].copy()
    if d.empty: return {}
    s=d.side_sign
    prev=s.shift(1)
    cross=(s.ne(0)&prev.ne(0)&s.ne(prev))
    cr=d.loc[cross.fillna(False)]
    cur=d.iloc[-1]; close=float(cur.close); v=float(cur.rth_vwap)
    if np.isclose(close,v,rtol=0,atol=max(abs(v)*1e-12,1e-12)): side="ON_VWAP"
    elif direction=="BULL": side="FAVORABLE_SIDE" if close>v else "ADVERSE_SIDE"
    else: side="FAVORABLE_SIDE" if close<v else "ADVERSE_SIDE"
    if cr.empty:
        last_dir="NONE"; age=np.nan
    else:
        lr=cr.iloc[-1]; last_dir="ABOVE" if int(lr.side_sign)>0 else "BELOW"
        age=(end-pd.Timestamp(lr.timestamp_utc)).total_seconds()/60
    start_sign=int(d.iloc[0].side_sign); end_sign=int(d.iloc[-1].side_sign)
    return {
      "rth_vwap_at_decision":v,
      "reference_price_minus_vwap_pct":(close/v-1)*100 if v else np.nan,
      "directional_vwap_side":side,
      "event_vwap_touch_from_dp1":bool(d.vwap_touch.any()),
      "event_vwap_cross_count_from_dp1":int(cross.fillna(False).sum()),
      "event_last_vwap_cross_direction":last_dir,
      "event_minutes_since_last_vwap_cross":age,
      "event_minutes_from_dp1":(end-start).total_seconds()/60,
      "event_dp1_side_sign":start_sign,
      "event_decision_side_sign":end_sign,
      "event_vwap_side_changed_from_dp1":bool(start_sign!=end_sign),
    }

def build_symbol(bars,*,symbol):
    dec=_normalize_vector_columns(run_symbol_alpha(bars,symbol=symbol)["decision_points"])
    if dec.empty: return pd.DataFrame()
    dec["trade_date"]=dec.event_id.map(lambda s:str(s).split("_")[1])
    dec=dec.sort_values(["event_id","decision_sequence"])
    dec["decision_occurrence"]=dec.groupby(["event_id","decision_type"]).cumcount()+1
    dec["primary_decision_unit"]=dec.decision_occurrence.eq(1)
    first=dec[dec.decision_type.eq("DP1_FIRST_CONTACT")].groupby("event_id").timestamp_utc.first()
    x=bars.copy()
    x["timestamp_utc"]=pd.to_datetime(x.timestamp_utc,utc=True)
    x["trade_date"]=pd.to_datetime(x.trade_date).dt.strftime("%Y-%m-%d")
    rows=[]
    for td,g in dec.groupby("trade_date",sort=False):
        day=x[(x.trade_date==td)&(x.session=="RTH")].copy()
        if day.empty: continue
        day=_rth_vwap(day)
        for r in g.itertuples(index=False):
            if r.event_id not in first.index: continue
            st=pd.Timestamp(first.loc[r.event_id]); en=pd.Timestamp(r.timestamp_utc)
            f=_path_features(day,st,en,r.direction)
            rows.append({"decision_id":r.decision_id,"event_id":r.event_id,
              "decision_type":r.decision_type,"timestamp_utc":r.timestamp_utc,
              "symbol":symbol,"trade_date":td,"direction":r.direction,
              "primary_decision_unit":bool(r.primary_decision_unit),
              "dp1_timestamp_utc":st,**f,
              "vwap_event_path_version":VERSION,"parent_dataset_version":PARENT,
              "protocol_id":PROTOCOL})
    return pd.DataFrame(rows)

def run(*,repo_root:Path,year=2025,verify_hash=True):
    repo_root=Path(repo_root).resolve(); members=load_validated_universe(repo_root)
    fs=[]; ss=[]
    for i,m in enumerate(members,1):
        print(f"[{i:03d}/{len(members):03d}] {m.symbol}",flush=True)
        p=load_certified_partition(symbol=m.symbol,year=year,repo_root=repo_root,verify_hash=verify_hash)
        e=build_symbol(p.dataframe.copy(),symbol=m.symbol)
        fs.append(e); ss.append({"symbol":m.symbol,"rows":len(e),"primary_rows":int(e.primary_decision_unit.sum())})
    a=pd.concat(fs,ignore_index=True)
    keycols=["decision_id","dp1_timestamp_utc","event_vwap_touch_from_dp1","event_vwap_cross_count_from_dp1",
             "event_last_vwap_cross_direction","event_minutes_since_last_vwap_cross",
             "event_vwap_side_changed_from_dp1"]
    h=sha256(a[keycols].fillna("<NA>").astype(str).to_csv(index=False).encode()).hexdigest()
    meta={"version":VERSION,"parent_dataset_version":PARENT,"protocol_id":PROTOCOL,"year":year,
          "rows":len(a),"primary_rows":int(a.primary_decision_unit.sum()),"symbol_count":len(members),
          "fingerprint":h}
    return a,pd.DataFrame(ss),meta
