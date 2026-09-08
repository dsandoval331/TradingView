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


ENRICHMENT_VERSION = "PMPD_V5_9H_ENRICHMENT_V1"
PARENT_DATASET_VERSION = "PMPD_V5_9H_RESEARCH_DATASET_V1"
PROTOCOL_ID = "PMPD_V5_9H_FACTOR_PROTOCOL_V1"

LEVEL_NAMES = ("PM", "AH", "PD")


def _stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return sha256(b"[]").hexdigest()
    use=[c for c in cols if c in df.columns]
    x=df[use].copy().fillna("<NA>").astype(str)
    return sha256(_stable_json(x.to_dict("records")).encode("utf-8")).hexdigest()


def _identity_from_vector(vec: str) -> str:
    s=str(vec)
    names=[LEVEL_NAMES[i] for i,ch in enumerate(s[:3]) if ch=="1"]
    if not names:
        return "NONE"
    if len(names)==1:
        return names[0]
    return "MULTI_" + "_".join(names)


def _rth_atr14_1m(day: pd.DataFrame) -> pd.DataFrame:
    """RTH-local 1-minute Wilder ATR14.

    Frozen Batch-4 definition:
    - RTH bars only.
    - Resets each RTH day.
    - True range uses previous RTH 1m close within the same day.
    - First bar TR = high-low.
    - Wilder smoothing alpha=1/14, min_periods=14.
    This deliberately avoids injecting the overnight gap into the ATR denominator.
    """
    x=day.sort_values("timestamp_utc").copy()
    prev=x["close"].shift(1)
    tr=pd.concat([
        x["high"]-x["low"],
        (x["high"]-prev).abs(),
        (x["low"]-prev).abs(),
    ],axis=1).max(axis=1)
    x["rth_atr14_1m"]=tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    return x[["timestamp_utc","rth_atr14_1m"]]


def _rth_open_context(day: pd.DataFrame, direction: str, levels: dict[str,float]) -> dict:
    r=day.sort_values("timestamp_utc").iloc[0]
    px=float(r["open"])
    vals={k:float(v) for k,v in levels.items()}
    if direction=="BULL":
        ordered=sorted(vals.items(), key=lambda kv:(kv[1],kv[0]))
        pre={k:px>v for k,v in vals.items()}
    else:
        ordered=sorted(vals.items(), key=lambda kv:(-kv[1],kv[0]))
        pre={k:px<v for k,v in vals.items()}
    count=sum(pre.values())
    if any(np.isclose(px,v,rtol=0,atol=max(abs(v)*1e-12,1e-12)) for v in vals.values()):
        loc="ON_LEVEL_BOUNDARY"
    elif count<=0:
        loc="BEFORE_INNER"
    elif count==1:
        loc="BETWEEN_INNER_MIDDLE"
    elif count==2:
        loc="BETWEEN_MIDDLE_OUTER"
    else:
        loc="BEYOND_OUTER"
    return {
        "rth_open_price":px,
        "levels_precleared_at_rth_open":int(count),
        "rth_open_location_relative_stack":loc,
        "rth_open_precleared_vector":"".join("1" if pre[n] else "0" for n in LEVEL_NAMES),
        "rth_open_inner_level":ordered[0][0],
        "rth_open_middle_level":ordered[1][0],
        "rth_open_outer_level":ordered[2][0],
    }


def _first_contact_identity(day: pd.DataFrame, ts, direction: str, levels: dict[str,float]) -> str:
    row=day.loc[pd.to_datetime(day["timestamp_utc"],utc=True).eq(pd.Timestamp(ts))]
    if row.empty:
        return "MISSING_BAR"
    r=row.iloc[0]
    if direction=="BULL":
        bits={n:float(r["high"])>=float(levels[n]) for n in LEVEL_NAMES}
    else:
        bits={n:float(r["low"])<=float(levels[n]) for n in LEVEL_NAMES}
    return _identity_from_vector("".join("1" if bits[n] else "0" for n in LEVEL_NAMES))


def _transition_features(transitions: pd.DataFrame, decision_ts) -> dict:
    if transitions.empty:
        return {
            "transition_count_to_dp":0,
            "directional_recross_count_to_dp":0,
            "structural_path_signature_to_dp":"000",
            "warning_persistence_minutes_at_dp":np.nan,
            "warning_transition_count_at_dp":0,
        }
    t=transitions.copy()
    t["timestamp_utc"]=pd.to_datetime(t["timestamp_utc"],utc=True)
    t=t.loc[t["timestamp_utc"].le(pd.Timestamp(decision_ts))].sort_values(["timestamp_utc","sequence"])
    if t.empty:
        return {
            "transition_count_to_dp":0,
            "directional_recross_count_to_dp":0,
            "structural_path_signature_to_dp":"000",
            "warning_persistence_minutes_at_dp":np.nan,
            "warning_transition_count_at_dp":0,
        }

    flips=[0,0,0]
    for r in t.itertuples(index=False):
        a=str(r.prior_close_vector); b=str(r.new_close_vector)
        for i in range(3):
            if a[i]!=b[i]:
                flips[i]+=1
    recross=sum(max(v-1,0) for v in flips)
    path="000>" + ">".join(t["new_close_vector"].astype(str).tolist())

    # Failure-warning persistence begins with the most recent full-retention loss.
    starts=t.loc[
        t["prior_close_vector"].astype(str).eq("111")
        & ~t["new_close_vector"].astype(str).eq("111")
    ]
    if starts.empty:
        wmin=np.nan
        wcount=0
    else:
        start=starts.iloc[-1]
        start_ts=pd.Timestamp(start["timestamp_utc"])
        wmin=(pd.Timestamp(decision_ts)-start_ts).total_seconds()/60.0
        wcount=int(t.loc[t["timestamp_utc"].ge(start_ts)].shape[0])

    return {
        "transition_count_to_dp":int(len(t)),
        "directional_recross_count_to_dp":int(recross),
        "structural_path_signature_to_dp":path,
        "warning_persistence_minutes_at_dp":wmin,
        "warning_transition_count_at_dp":wcount,
    }


def build_symbol_enrichment(bars: pd.DataFrame, *, symbol: str) -> pd.DataFrame:
    outputs=run_symbol_alpha(bars, symbol=symbol)
    decisions=_normalize_vector_columns(outputs["decision_points"])
    if decisions.empty:
        return pd.DataFrame()

    events=outputs["events"].copy()
    geometry=outputs["geometry"].copy()
    transitions=outputs["transitions"].copy()
    levels=outputs["session_levels"].copy()
    levels["symbol"]=symbol

    x=bars.copy()
    x["trade_date"]=pd.to_datetime(x["trade_date"],errors="coerce").dt.tz_localize(None).dt.normalize()
    x["timestamp_utc"]=pd.to_datetime(x["timestamp_utc"],errors="coerce",utc=True)
    x=x.sort_values("timestamp_utc")

    decisions["symbol"]=symbol
    decisions["trade_date"]=decisions["event_id"].map(lambda s:str(s).split("_")[1])
    decisions["trade_date"]=pd.to_datetime(decisions["trade_date"]).dt.strftime("%Y-%m-%d")
    decisions=decisions.sort_values(["event_id","decision_type","decision_sequence"])
    decisions["decision_occurrence"]=decisions.groupby(["event_id","decision_type"]).cumcount()+1
    decisions["primary_decision_unit"]=decisions["decision_occurrence"].eq(1)

    evcols=["event_id","pm_level","ah_level","pd_level","stack_width_pct","identity_order_inner_to_outer"]
    decisions=decisions.merge(events[[c for c in evcols if c in events.columns]],on="event_id",how="left",validate="many_to_one")

    # Geometry stack width absolute.
    if not geometry.empty:
        g=geometry[["symbol","trade_date","direction","stack_width_abs"]].copy()
        g["trade_date"]=pd.to_datetime(g["trade_date"]).dt.strftime("%Y-%m-%d")
        decisions=decisions.merge(g,on=["symbol","trade_date","direction"],how="left",validate="many_to_one")

    rows=[]
    for r in decisions.itertuples(index=False):
        td=pd.Timestamp(r.trade_date)
        day=x.loc[x["trade_date"].eq(td)&x["session"].eq("RTH")].copy()
        levels3={"PM":float(r.pm_level),"AH":float(r.ah_level),"PD":float(r.pd_level)}
        ctx=_rth_open_context(day,r.direction,levels3)

        dps=decisions.loc[decisions["event_id"].eq(r.event_id)]
        dp1=dps.loc[dps["decision_type"].eq("DP1_FIRST_CONTACT")].sort_values("decision_sequence")
        dp2=dps.loc[dps["decision_type"].eq("DP2_FIRST_LEVEL_CLEAR")].sort_values("decision_sequence")
        first_contact_identity=_first_contact_identity(
            day, dp1.iloc[0]["timestamp_utc"], r.direction, levels3
        ) if not dp1.empty else "NONE"
        first_clear_identity=_identity_from_vector(
            str(dp2.iloc[0]["traded_vector"])
        ) if not dp2.empty else "NONE"

        tr=transitions.loc[transitions["event_id"].eq(r.event_id)].copy() if not transitions.empty else pd.DataFrame()
        tf=_transition_features(tr,r.timestamp_utc)

        atr=_rth_atr14_1m(day)
        av=atr.loc[pd.to_datetime(atr["timestamp_utc"],utc=True).eq(pd.Timestamp(r.timestamp_utc)),"rth_atr14_1m"]
        atrv=float(av.iloc[0]) if len(av) and pd.notna(av.iloc[0]) else np.nan
        atr_norm=float(r.stack_width_abs)/atrv if pd.notna(atrv) and atrv>0 else np.nan

        # Elapsed structural timing uses only decision points already observed by this DP.
        prior=dps.loc[pd.to_datetime(dps["timestamp_utc"],utc=True).le(pd.Timestamp(r.timestamp_utc))].copy()
        def first_ts(kind):
            a=prior.loc[prior["decision_type"].eq(kind)]
            return pd.Timestamp(a.sort_values("decision_sequence").iloc[0]["timestamp_utc"]) if not a.empty else pd.NaT
        t1=first_ts("DP1_FIRST_CONTACT")
        t2=first_ts("DP2_FIRST_LEVEL_CLEAR")
        t3=first_ts("DP3_SECOND_LEVEL_CLEAR")
        t4=first_ts("DP4_FULL_STACK_FIRST_CLEAR")

        def mins(a,b):
            return (b-a).total_seconds()/60 if pd.notna(a) and pd.notna(b) and b>=a else np.nan

        rows.append({
            "decision_id":r.decision_id,
            "event_id":r.event_id,
            "decision_sequence":int(r.decision_sequence),
            "decision_type":r.decision_type,
            "timestamp_utc":r.timestamp_utc,
            "symbol":symbol,
            "trade_date":r.trade_date,
            "direction":r.direction,
            "primary_decision_unit":bool(r.primary_decision_unit),
            "attempt_number_at_dp":int(r.attempt_number),
            "first_contact_level_identity":first_contact_identity,
            "first_cleared_level_identity":first_clear_identity,
            **ctx,
            "rth_atr14_1m":atrv,
            "stack_width_atr14_1m":atr_norm,
            "contact_to_first_clear_minutes":mins(t1,t2),
            "first_to_second_clear_minutes":mins(t2,t3),
            "second_to_full_stack_clear_minutes":mins(t3,t4),
            "contact_to_full_stack_clear_minutes":mins(t1,t4),
            **tf,
            "enrichment_version":ENRICHMENT_VERSION,
            "parent_dataset_version":PARENT_DATASET_VERSION,
            "protocol_id":PROTOCOL_ID,
        })
    return pd.DataFrame(rows)


def run_full_universe_enrichment(*, repo_root: Path, year: int=2025, verify_hash: bool=True):
    repo_root=Path(repo_root).resolve()
    members=load_validated_universe(repo_root)
    frames=[]
    summary=[]
    for i,m in enumerate(members,start=1):
        print(f"[{i:03d}/{len(members):03d}] {m.symbol}",flush=True)
        p=load_certified_partition(symbol=m.symbol,year=year,repo_root=repo_root,verify_hash=verify_hash)
        e=build_symbol_enrichment(p.dataframe.copy(),symbol=m.symbol)
        if not e.empty:
            frames.append(e)
        summary.append({"symbol":m.symbol,"enrichment_rows":len(e),"primary_rows":int(e["primary_decision_unit"].sum()) if not e.empty else 0})
    all_df=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    meta={
        "enrichment_version":ENRICHMENT_VERSION,
        "parent_dataset_version":PARENT_DATASET_VERSION,
        "protocol_id":PROTOCOL_ID,
        "year":year,
        "symbol_count":len(members),
        "rows":int(len(all_df)),
        "primary_rows":int(all_df["primary_decision_unit"].sum()) if not all_df.empty else 0,
    }
    meta["fingerprint"]=_fingerprint(all_df,[
        "decision_id","event_id","decision_type","timestamp_utc",
        "first_contact_level_identity","first_cleared_level_identity",
        "levels_precleared_at_rth_open","rth_open_location_relative_stack",
        "stack_width_atr14_1m","directional_recross_count_to_dp",
        "structural_path_signature_to_dp","warning_persistence_minutes_at_dp"
    ])
    return all_df,pd.DataFrame(summary),meta
