from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
from research_runner.jobs import pmpd_edge_e2_batch2 as e2

PROTOCOL="PMPD_EDGE_E3_TRADE_HEALTH_PROTOCOL_V1"


def _dir(direction:str,x:float,ref:float)->float:
    return (1 if direction=="BULL" else -1)*(x/ref-1) if ref and np.isfinite(ref) else np.nan


def _emit(rows, base, typ, fam, t, price, dp4, boundary, vwap, rvol, daybars):
    prior=daybars[daybars.decision_time_et<=t]
    if prior.empty:return
    closes=prior.close.astype(float)
    sign=1 if base["direction"]=="BULL" else -1
    entry=float(base["entry_price"])
    dr=sign*(price/entry-1) if entry else np.nan
    dirs=sign*(closes/entry-1)
    rows.append({**base,"event_type":typ,"event_family":fam,"decision_timestamp_et":t,"minutes_from_dp4":float((t-dp4).total_seconds()/60),"price_at_decision":float(price),"directional_return_from_dp4_pct":float(dr),"mfe_so_far_pct":float(dirs.max()) if len(dirs) else np.nan,"mae_so_far_pct":float(dirs.min()) if len(dirs) else np.nan,"stack_distance_pct":float(_dir(base['direction'],price,boundary)),"stack_distance_atr14":float(sign*(price-boundary)/prior.iloc[-1].prior_atr14) if pd.notna(prior.iloc[-1].prior_atr14) and prior.iloc[-1].prior_atr14>0 else np.nan,"vwap_distance_pct":float(_dir(base['direction'],price,vwap)),"opening_rvol_ge_1_5_context":bool(rvol)})


def run(root:Path)->dict:
    proto_p=root/"research_outputs/pmpd/edge/e3_batch1/trade_health_protocol.json"
    paths_p=root/"research_outputs/pmpd/edge/e2_batch2_r2/acceptance_state_paths.parquet"
    cache=root/"data/second1m_alt_entry_cache_v1/partitions"
    for p in [proto_p,paths_p,cache]:
        if not p.exists():raise FileNotFoundError(p)
    proto=json.loads(proto_p.read_text())
    if proto.get("protocol")!=PROTOCOL:raise RuntimeError("E3 protocol mismatch")
    paths=pd.read_parquet(paths_p)
    rows=[]; errors=[]; missing=[]
    for n,sym in enumerate(sorted(paths.symbol.astype(str).unique()),1):
        print(f"[{n}/112] E3_TRADE_HEALTH_PATH {sym}")
        d=e2._load_cache(cache,sym)
        if d is None: missing.append(sym);continue
        try: minutes,bars,_=e2._prepare_symbol(d)
        except Exception as exc: errors.append({"symbol":sym,"error":repr(exc)});continue
        for _,r in paths[(paths.symbol.astype(str)==sym)&paths.analyzable.fillna(False)].iterrows():
            direction=str(r.direction).upper(); sign=1 if direction=="BULL" else -1
            dp4=pd.Timestamp(r.dp4_timestamp_et); boundary=float(r.acceptance_boundary); day=r.trade_date
            b=bars[(bars.trade_date==day)&(bars.decision_time_et>dp4)].copy().reset_index(drop=True)
            m=minutes[minutes.trade_date==day].copy()
            if b.empty:continue
            entry=float(boundary); base={"event_key":r.event_key,"symbol":sym,"trade_date":day,"direction":direction,"dp4_timestamp_et":dp4,"entry_price":entry}
            rvol=bool(r.get("opening_rvol_ge_1_5",False))
            # Level behavior: reuse the already-certified E2 causal state timestamps.
            level_map={"hold_acceptance":"STACK_HOLD","failed_acceptance":"STACK_FAILURE","reclaim_after_failure":"STACK_RECLAIM"}
            for src,typ in level_map.items():
                if bool(r.get(f"{src}_seen",False)) and pd.notna(r.get(f"{src}_time")):
                    t=pd.Timestamp(r[f"{src}_time"]); price=float(r[f"{src}_price"]); vw=e2._sample_vwap(m,t)
                    _emit(rows,base,typ,"level_behavior",t,price,dp4,boundary,vw,rvol,b)
            # Completed 5m bars with contemporaneous VWAP sampled only through decision time.
            rel=[]
            for i,br in b.iterrows():
                t=br.decision_time_et; vw=e2._sample_vwap(m,t)
                if not np.isfinite(vw):continue
                c=float(br.close); hi=float(br.high); lo=float(br.low); fav=sign*(c-vw)>0
                touch=(lo<=vw<=hi)
                rel.append((i,br,t,vw,fav,touch))
                if touch:
                    _emit(rows,base,"VWAP_TEST","vwap",t,c,dp4,boundary,vw,rvol,b)
                    if (direction=="BULL" and lo<vw) or (direction=="BEAR" and hi>vw):
                        _emit(rows,base,"VWAP_PENETRATION","vwap",t,c,dp4,boundary,vw,rvol,b)
                    if fav:_emit(rows,base,"VWAP_REJECTION","vwap",t,c,dp4,boundary,vw,rvol,b)
                if not fav:_emit(rows,base,"VWAP_ACCEPTANCE","vwap",t,c,dp4,boundary,vw,rvol,b)
                if len(rel)>1 and fav and not rel[-2][4]:_emit(rows,base,"VWAP_RECLAIM","vwap",t,c,dp4,boundary,vw,rvol,b)
            # 3-bar confirmed pivots: confirmation bar is decision time, avoiding future leakage.
            piv=[]
            for i in range(2,len(b)):
                a,curr,z=b.iloc[i-2],b.iloc[i-1],b.iloc[i]
                t=z.decision_time_et; vw=e2._sample_vwap(m,t)
                if curr.low<a.low and curr.low<z.low:piv.append(("L",float(curr.low),t,float(z.close),vw))
                if curr.high>a.high and curr.high>z.high:piv.append(("H",float(curr.high),t,float(z.close),vw))
            for kind in ["L","H"]:
                q=[x for x in piv if x[0]==kind]
                for prev,cur in zip(q,q[1:]):
                    higher=cur[1]>prev[1]
                    if kind=="L": typ=("FAVORABLE_HIGHER_LOW" if direction=="BULL" and higher else "ADVERSE_LOWER_HIGH" if direction=="BEAR" and higher else "ADVERSE_HIGHER_LOW" if direction=="BULL" else "FAVORABLE_LOWER_HIGH")
                    else: typ=("FAVORABLE_HIGHER_LOW" if direction=="BULL" and higher else "ADVERSE_LOWER_HIGH" if direction=="BEAR" and higher else "ADVERSE_HIGHER_LOW" if direction=="BULL" else "FAVORABLE_LOWER_HIGH")
                    _emit(rows,base,typ,"structure",cur[2],cur[3],dp4,boundary,cur[4],rvol,b)
            # Threshold-free two-close directional momentum and price/momentum divergence.
            dret=sign*b.close.astype(float).pct_change()
            for i in range(2,len(b)):
                t=b.iloc[i].decision_time_et; price=float(b.iloc[i].close); vw=e2._sample_vwap(m,t)
                if dret.iloc[i]>0 and dret.iloc[i-1]>0:_emit(rows,base,"MOMENTUM_SUPPORT","momentum",t,price,dp4,boundary,vw,rvol,b)
                if dret.iloc[i]<0 and dret.iloc[i-1]<0:_emit(rows,base,"MOMENTUM_DETERIORATION","momentum",t,price,dp4,boundary,vw,rvol,b)
                p0,p1,p2=sign*float(b.iloc[i-2].close),sign*float(b.iloc[i-1].close),sign*price
                if p2>max(p0,p1) and dret.iloc[i]<dret.iloc[i-1]:_emit(rows,base,"MOMENTUM_PRICE_DIVERGENCE","momentum",t,price,dp4,boundary,vw,rvol,b)
    ev=pd.DataFrame(rows)
    if len(ev):ev=ev.sort_values(["symbol","trade_date","decision_timestamp_et","event_type"]).drop_duplicates(["event_key","event_type","decision_timestamp_et"])
    out=root/"research_outputs/pmpd/edge/e3_batch2";out.mkdir(parents=True,exist_ok=True)
    ev.to_parquet(out/"trade_health_events.parquet",index=False)
    cov=(ev.groupby(["event_family","event_type"]).agg(events=("event_key","size"),unique_trades=("event_key","nunique"),symbols=("symbol","nunique"),median_minutes_from_dp4=("minutes_from_dp4","median")).reset_index() if len(ev) else pd.DataFrame())
    cov.to_csv(out/"event_coverage.csv",index=False)
    summary={"step":"PMPD-EDGE-E3-B2","protocol":PROTOCOL,"purpose":"Outcome-blind timestamped Trade Health event-path construction and causal availability/coverage certification.","source_events":int(paths.analyzable.fillna(False).sum()),"event_rows":int(len(ev)),"unique_trades_with_events":int(ev.event_key.nunique()) if len(ev) else 0,"symbols":int(ev.symbol.nunique()) if len(ev) else 0,"missing_cache_symbols":missing,"symbol_errors":errors,"outcomes_inspected":False,"threshold_search_performed":False,"operational_semantics":{"structure":"three completed 5m bars; middle-bar pivot becomes observable only at third-bar close","momentum":"threshold-free sign of two consecutive directional 5m close returns; divergence requires new directional closing extreme with weaker current directional return","vwap":"contemporaneous RTH VWAP; touch/penetration recognized no earlier than completed 5m decision bar; rejection/acceptance/reclaim require completed close","level_behavior":"reuse certified E2 causal hold/failure/reclaim timestamps"},"guardrails":{"research_only":True,"2026_development_evidence":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False,"trade_health_score_fit":False,"signal_quality_separate":True},"next_batch_if_integrity_passes":"E3-B3 pre-specified association of Trade Health events with subsequent path/outcomes from each event decision timestamp."}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str))
    print("PMPD_EDGE_E3_B2_SUMMARY="+json.dumps(summary,sort_keys=True,default=str))
    return {"status":"PASS","protocol":PROTOCOL,"output_paths":[str((out/"trade_health_events.parquet").relative_to(root)),str((out/"event_coverage.csv").relative_to(root)),str((out/"summary.json").relative_to(root))],"research_only":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False}
