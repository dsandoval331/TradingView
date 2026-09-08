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

VWAP_ENRICHMENT_VERSION="PMPD_V5_9J_VWAP_ENTRY_CONTEXT_V1"
PARENT_DATASET_VERSION="PMPD_V5_9H_RESEARCH_DATASET_V1"
PROTOCOL_ID="PMPD_V5_9J_ENTRY_ARCH_PROTOCOL_V1"

def _stable_json(v):
    return json.dumps(v,sort_keys=True,separators=(",",":"),default=str)

def _fingerprint(df,cols):
    if df.empty: return sha256(b"[]").hexdigest()
    use=[c for c in cols if c in df.columns]
    x=df[use].copy().fillna("<NA>").astype(str)
    return sha256(_stable_json(x.to_dict("records")).encode()).hexdigest()

def _rth_vwap_day(day):
    """Completed-bar RTH VWAP using typical price * volume, reset each RTH day."""
    x=day.sort_values("timestamp_utc").copy()
    tp=(pd.to_numeric(x["high"])+pd.to_numeric(x["low"])+pd.to_numeric(x["close"]))/3.0
    vol=pd.to_numeric(x["volume"],errors="coerce").fillna(0.0)
    den=vol.cumsum()
    x["rth_vwap"]=(tp*vol).cumsum()/den.replace(0,np.nan)
    x["close_minus_vwap_pct"]=(pd.to_numeric(x["close"])/x["rth_vwap"]-1.0)*100.0
    x["above_vwap"]=pd.to_numeric(x["close"])>x["rth_vwap"]
    x["below_vwap"]=pd.to_numeric(x["close"])<x["rth_vwap"]
    return x

def _features_to_decision(day,decision_ts,direction):
    d=day.loc[pd.to_datetime(day["timestamp_utc"],utc=True).le(pd.Timestamp(decision_ts))].copy()
    if d.empty:
        return {}
    cur=d.iloc[-1]
    v=float(cur["rth_vwap"]) if pd.notna(cur["rth_vwap"]) else np.nan
    close=float(cur["close"])
    if pd.isna(v):
        side="UNKNOWN"
    elif np.isclose(close,v,rtol=0,atol=max(abs(v)*1e-12,1e-12)):
        side="ON_VWAP"
    elif direction=="BULL":
        side="FAVORABLE_SIDE" if close>v else "ADVERSE_SIDE"
    else:
        side="FAVORABLE_SIDE" if close<v else "ADVERSE_SIDE"

    # A bar "touches" its contemporaneous VWAP when VWAP lies inside bar range.
    touch=(pd.to_numeric(d["low"])<=d["rth_vwap"]) & (pd.to_numeric(d["high"])>=d["rth_vwap"])
    s=np.sign(pd.to_numeric(d["close"])-d["rth_vwap"]).fillna(0).astype(int)
    prev=s.shift(1)
    cross=(s.ne(0)&prev.ne(0)&s.ne(prev))
    cross_rows=d.loc[cross.fillna(False)]
    if cross_rows.empty:
        cross_count=0; last_dir="NONE"; mins=np.nan
    else:
        cross_count=int(len(cross_rows))
        lr=cross_rows.iloc[-1]
        idx=cross_rows.index[-1]
        sv=int(s.loc[idx])
        last_dir="ABOVE" if sv>0 else "BELOW"
        mins=(pd.Timestamp(decision_ts)-pd.Timestamp(lr["timestamp_utc"])).total_seconds()/60.0

    return {
      "rth_vwap_at_decision":v,
      "reference_price_minus_vwap_pct":(close/v-1.0)*100.0 if pd.notna(v) and v else np.nan,
      "directional_vwap_side":side,
      "vwap_touch_to_decision":bool(touch.any()),
      "vwap_cross_count_to_decision":cross_count,
      "last_vwap_cross_direction":last_dir,
      "minutes_since_last_vwap_cross":mins,
    }

def build_symbol_vwap_enrichment(bars,*,symbol):
    outputs=run_symbol_alpha(bars,symbol=symbol)
    decisions=_normalize_vector_columns(outputs["decision_points"])
    if decisions.empty: return pd.DataFrame()
    x=bars.copy()
    x["trade_date"]=pd.to_datetime(x["trade_date"],errors="coerce").dt.tz_localize(None).dt.normalize()
    x["timestamp_utc"]=pd.to_datetime(x["timestamp_utc"],errors="coerce",utc=True)
    decisions["symbol"]=symbol
    decisions["trade_date"]=decisions["event_id"].map(lambda s:str(s).split("_")[1])
    decisions["trade_date"]=pd.to_datetime(decisions["trade_date"]).dt.strftime("%Y-%m-%d")
    decisions=decisions.sort_values(["event_id","decision_type","decision_sequence"])
    decisions["decision_occurrence"]=decisions.groupby(["event_id","decision_type"]).cumcount()+1
    decisions["primary_decision_unit"]=decisions["decision_occurrence"].eq(1)
    rows=[]
    for td,grp in decisions.groupby("trade_date",sort=False):
        day=x.loc[x["trade_date"].eq(pd.Timestamp(td)) & x["session"].eq("RTH")].copy()
        if day.empty: continue
        day=_rth_vwap_day(day)
        for r in grp.itertuples(index=False):
            f=_features_to_decision(day,r.timestamp_utc,r.direction)
            rows.append({
              "decision_id":r.decision_id,"event_id":r.event_id,
              "decision_type":r.decision_type,"timestamp_utc":r.timestamp_utc,
              "symbol":symbol,"trade_date":td,"direction":r.direction,
              "primary_decision_unit":bool(r.primary_decision_unit),**f,
              "vwap_enrichment_version":VWAP_ENRICHMENT_VERSION,
              "parent_dataset_version":PARENT_DATASET_VERSION,"protocol_id":PROTOCOL_ID
            })
    return pd.DataFrame(rows)

def run_full_universe_vwap_enrichment(*,repo_root:Path,year:int=2025,verify_hash:bool=True):
    repo_root=Path(repo_root).resolve()
    members=load_validated_universe(repo_root)
    frames=[]; summary=[]
    for i,m in enumerate(members,start=1):
        print(f"[{i:03d}/{len(members):03d}] {m.symbol}",flush=True)
        p=load_certified_partition(symbol=m.symbol,year=year,repo_root=repo_root,verify_hash=verify_hash)
        e=build_symbol_vwap_enrichment(p.dataframe.copy(),symbol=m.symbol)
        if not e.empty: frames.append(e)
        summary.append({"symbol":m.symbol,"rows":len(e),"primary_rows":int(e["primary_decision_unit"].sum()) if not e.empty else 0})
    all_df=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    meta={"vwap_enrichment_version":VWAP_ENRICHMENT_VERSION,"parent_dataset_version":PARENT_DATASET_VERSION,
          "protocol_id":PROTOCOL_ID,"year":year,"symbol_count":len(members),"rows":int(len(all_df)),
          "primary_rows":int(all_df["primary_decision_unit"].sum()) if not all_df.empty else 0}
    meta["fingerprint"]=_fingerprint(all_df,["decision_id","event_id","decision_type","timestamp_utc",
      "rth_vwap_at_decision","reference_price_minus_vwap_pct","directional_vwap_side",
      "vwap_touch_to_decision","vwap_cross_count_to_decision","last_vwap_cross_direction","minutes_since_last_vwap_cross"])
    return all_df,pd.DataFrame(summary),meta
