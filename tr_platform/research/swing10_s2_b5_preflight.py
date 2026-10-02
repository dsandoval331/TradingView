"""B5 inventory and timestamp-only independent-sample audit; no price decoder."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import uuid
import numpy as np
import pandas as pd

PROTOCOL='SW10_S2_B5_PREFLIGHT_V1'
DECISION='67f7cf88-dceb-47a3-8e1f-379ef19b6d08'
FILES=('independent_source_inventory.csv','independent_temporal_independence_audit.csv','independent_semantic_reproducibility.csv','independent_coverage_eligibility.csv','independent_universe_survivorship_audit.csv','sw10_s2_b5_preflight_manifest.json')
SNAPSHOT=PROTOCOL+'.persisted.json'
META_COLUMNS=('symbol','trade_date','timestamp_utc','session','source','adjusted','cache_version')
SEEDS=(('LIQ_ADJUSTED_PRICE','NEGATIVE',(5,7,10)),('LIQ_REPORTED_VOLUME','POSITIVE',(3,5,7,10)),('RET_MOM x MARKET_SPY_TREND10','POSITIVE',(7,10)))
DISCOVERY_START=pd.Timestamp('2025-02-03')
DISCOVERY_END=pd.Timestamp('2026-08-27')
DISCOVERY_SHA='ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2'


def guard_source(source):
    tree=ast.parse(source)
    allowed={'__future__','ast','hashlib','json','pathlib','uuid','numpy','pandas'}
    denied={'eval','exec','__import__','getattr','read_sql','read_csv','read_pickle','read_excel','read_feather','read_json','pct_change','forward_returns','hac_mean','bh_adjust','bfill','interpolate','roll','lead'}
    for n in ast.walk(tree):
        if isinstance(n,ast.Import) and any(a.name not in allowed for a in n.names):raise ValueError('non-approved import')
        if isinstance(n,ast.ImportFrom) and n.module not in allowed:raise ValueError('non-approved import')
        if isinstance(n,ast.Call):
            fn=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
            if fn in denied:raise ValueError('outcome-capable primitive')
            if fn in {'shift','diff'}:
                a=n.args[0] if n.args else None
                if not isinstance(a,ast.Constant) or type(a.value)!=int or a.value<0:raise ValueError('past-only literal lag')
            if fn=='read_parquet':
                if not any(k.arg=='columns' and isinstance(k.value,ast.Call) and isinstance(k.value.func,ast.Name) and k.value.func.id=='list' and len(k.value.args)==1 and isinstance(k.value.args[0],ast.Name) and k.value.args[0].id=='META_COLUMNS' for k in n.keywords):raise ValueError('timestamp/metadata-only parquet projection')
    for fn in (n for n in tree.body if isinstance(n,ast.FunctionDef)):
        if fn.name!='read_metadata' and any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='read_parquet' for n in ast.walk(fn)):raise ValueError('unvalidated parquet reader')


def read_metadata(path,expected_size,expected_sha,symbol):
    blob=path.read_bytes();digest=hashlib.sha256(blob).hexdigest()
    if len(blob)!=expected_size or digest!=expected_sha:raise ValueError('materialized byte identity mismatch')
    frame=pd.read_parquet(path,columns=list(META_COLUMNS))
    if tuple(frame.columns)!=META_COLUMNS or frame.isna().any().any():raise ValueError('strict metadata schema/nulls')
    if set(frame.symbol)!={symbol} or set(frame.cache_version)!={'MARKET_CACHE_V1'}:raise ValueError('wrong source identity')
    frame=frame.copy();frame['trade_date']=pd.to_datetime(frame.trade_date)
    ts=pd.to_datetime(frame.timestamp_utc,utc=True)
    if not frame.trade_date.dt.year.eq(2024).all():raise ValueError('only unprotected pre-discovery 2024 metadata allowed')
    if not (ts.dt.tz_convert('America/New_York').dt.date==frame.trade_date.dt.date).all():raise ValueError('ET date alignment')
    if frame.duplicated(['symbol','timestamp_utc']).any():raise ValueError('duplicate timestamp')
    return frame,{'size_bytes':len(blob),'sha256':digest,'decoded_columns':list(META_COLUMNS),'price_columns_decoded':False}


def timestamp_eligibility(dates,horizon,lookback):
    """Future availability keys only. No price/value arguments accepted."""
    if not isinstance(dates,pd.DatetimeIndex):raise ValueError('date keys only')
    dates=dates.sort_values().unique()
    if dates.hasnans:raise ValueError('invalid date key')
    out=[]
    for i,date in enumerate(dates):
        endpoint=dates[i+horizon] if i+horizon<len(dates) else pd.NaT
        independent=pd.notna(endpoint) and ((endpoint<DISCOVERY_START) or (date>DISCOVERY_END))
        out.append({'trade_date':date,'horizon_endpoint_date':endpoint,'timestamp_eligible':i>=lookback and pd.notna(endpoint),'temporally_independent':bool(independent)})
    return pd.DataFrame(out)


def centered_rank(values):
    x=values.where(np.isfinite(values));return 2*x.rank(method='average')/x.notna().sum()-1


def prospective_state(series):
    x=series.sort_index().where(np.isfinite(series.sort_index()));past=x.shift(1)
    mean=past.expanding(min_periods=20).mean();sd=past.expanding(min_periods=20).std(ddof=1)
    return ((x-mean)/sd).where(np.isfinite(x)&np.isfinite(mean)&np.isfinite(sd)&sd.gt(1e-12))


def predictor_fixture(panel):
    if tuple(panel.columns)!=('symbol','trade_date','close','volume'):raise ValueError('predictor schema only')
    x=panel.sort_values(['symbol','trade_date']).copy();prev=x.groupby('symbol').close.shift(10);x['RET_MOM']=x.close/prev-1
    x['primary_rank']=x.groupby('trade_date').RET_MOM.transform(centered_rank)
    spy=x[x.symbol=='SPY'].set_index('trade_date').RET_MOM
    x['market_state_z']=x.trade_date.map(prospective_state(spy))
    return x


def audit(snapshot,frames,identities):
    inventory=[];temporal=[];semantic=[];coverage=[];universe=[]
    sources=[('CANONICAL_DAILY','public.market_daily_history',True,False,'2025-02-03','2026-08-27',112,394,'OVERLAPS_DISCOVERY'),('CACHE_2024','private MARKET_CACHE_V1 1m/*/2024.parquet',False,True,None,None,len(frames),None,'TIMESTAMP_ONLY_CANDIDATE'),('INTRADAY_TABLE','public.market_intraday_history',True,False,'2025-05-23','2026-08-27',112,267,'OVERLAPS_DISCOVERY'),('CACHE_2025','private MARKET_CACHE_V1 2025 protected replication dataset',False,False,'2025-01-01','2025-12-31',112,None,'EXCLUDED_PROTECTED_NOT_OPENED'),('NEW_MASSIVE_DAILY','Massive daily adjusted aggregates via existing provider integration',True,False,None,None,None,None,'NOT_ACQUIRED_NOT_COST_OR_ENTITLEMENT_CERTIFIED'),('ALPHA_VANTAGE_DAILY','existing Alpha Vantage entitlement probe integration',None,False,None,None,None,None,'NOT_ACQUIRED_ADJUSTMENT_EQUIVALENCE_UNCERTIFIED'),('FMP_DAILY','existing FMP entitlement probe integration',None,False,None,None,None,None,'NOT_ACQUIRED_ADJUSTMENT_EQUIVALENCE_UNCERTIFIED'),('PROSPECTIVE_DAILY','future immutable same-provider daily acquisition after discovery',True,False,None,None,None,None,'NOT_YET_REGISTERED')]
    all_dates=sorted(set().union(*(set(f.trade_date) for f in frames.values()))) if frames else []
    for sid,source,adjusted,opened,start,end,n,d,status in sources:
        if sid=='CACHE_2024':start=str(min(all_dates))[:10] if all_dates else None;end=str(max(all_dates))[:10] if all_dates else None;d=len(all_dates)
        inventory.append({'source_id':sid,'source':source,'adjusted':adjusted,'metadata_opened':opened,'prices_decoded':False,'first_date':start,'last_date':end,'symbols':n,'dates':d,'status':status,'data_vintage':'retrospective acquisition; original historical vintage not certified','independent_certified_daily_available':False,'registered_cache_objects':len(identities) if sid=='CACHE_2024' else None})
        universe.append({'source_id':sid,'universe_status':'contemporary fixed symbol universe; historical PIT membership/delisted coverage not certified' if sid in {'CANONICAL_DAILY','CACHE_2024','INTRADAY_TABLE','CACHE_2025'} else 'not constructed','survivorship_bias_possible':True,'universe_selection_independent_of_B5_outcomes':True,'limitations':'same symbols may support temporal replication but do not establish untouched historical universe; no claim of survivorship-free evidence'})
        for family,direction,hs in SEEDS:
            reason='No registered certified daily input outside discovery; minute OHLCV is not silently substituted'
            if sid=='CANONICAL_DAILY' or sid=='INTRADAY_TABLE':reason='All available dates overlap discovery'
            if sid=='CACHE_2024':reason='Raw minute adjusted=false cannot reproduce adjusted daily price; reported minute volume aggregation equivalence and daily session completeness not certified; no daily SPY adjusted series'
            if sid=='CACHE_2025':reason='Protected source excluded without content access; majority period overlaps discovery'
            semantic.append({'source_id':sid,'family':family,'frozen_direction':direction,'frozen_horizons':','.join(map(str,hs)),'status':'UNAVAILABLE_FOR_VALIDATION','exact_semantics_reproduced':False,'point_in_time_status':'causal definitions frozen; source original-vintage certification absent','benchmark_requirement':'same-date adjusted daily SPY + trailing10 + >=20 prior finite trend observations' if family.startswith('RET_MOM') else 'not applicable','definition':'adjusted close_t' if family=='LIQ_ADJUSTED_PRICE' else 'reported daily volume_t' if family=='LIQ_REPORTED_VOLUME' else 'same-date average_rank/N centered RET_MOM10; SPY trend10 standardized strictly before t using >=20 priors and sample SD','reason':reason})
            for h in hs:
                potential=0;potential_dates=set();missing=0
                if sid=='CACHE_2024':
                    spy_dates=set(frames.get('SPY',pd.DataFrame({'trade_date':[]})).trade_date)
                    for symbol,frame in frames.items():
                        dates=pd.DatetimeIndex(sorted(set(frame.trade_date)))
                        e=timestamp_eligibility(dates,h,30 if family.startswith('RET_MOM') else 0)
                        keep=e.timestamp_eligible & e.temporally_independent
                        if family.startswith('RET_MOM'):keep &= e.trade_date.isin(spy_dates)
                        potential+=int(keep.sum());potential_dates.update(e.loc[keep,'trade_date']);missing+=int((~e.timestamp_eligible).sum())
                coverage.append({'source_id':sid,'family':family,'direction':direction,'horizon':h,'timestamp_only_potential_observations':potential if sid=='CACHE_2024' else None,'timestamp_only_potential_dates':len(potential_dates) if sid=='CACHE_2024' else None,'lookback_timestamp_proxy':30 if family.startswith('RET_MOM') else 0,'certified_semantic_eligible_observations':0,'certified_semantic_eligible_dates':0,'timestamp_ineligible_observations':missing if sid=='CACHE_2024' else None,'raw_price_missingness':'NOT_DECODED; fail closed due to semantic incompatibility','future_price_used':False,'notes':'timestamp capacity is an upper bound only; gaps/finite predictors/rank variability/benchmark prior eligibility remain uncertified'})
    for symbol,frame in frames.items():
        dates=pd.DatetimeIndex(sorted(set(frame.trade_date)))
        for h in (3,5,7,10):
            e=timestamp_eligibility(dates,h,0)
            temporal.append({'source_id':'CACHE_2024','symbol':symbol,'horizon':h,'dates':len(dates),'first_date':str(dates.min())[:10],'last_date':str(dates.max())[:10],'available_endpoint_dates':int(e.horizon_endpoint_date.notna().sum()),'independent_endpoint_dates':int(e.temporally_independent.sum()),'overlap_endpoint_dates':int((e.horizon_endpoint_date.notna() & ~e.temporally_independent).sum()),'adjusted_values':','.join(map(str,sorted(set(frame.adjusted)))),'source_values':','.join(sorted(set(frame.source))),'rth_dates':int(frame.loc[frame.session=='RTH','trade_date'].nunique()),'unique_timestamps':len(frame),'prices_decoded':False})
    return dict(zip(FILES[:5],map(pd.DataFrame,(inventory,temporal,semantic,coverage,universe))))


def run(work_root):
    here=Path(__file__).parent;guard_source((here/'swing10_s2_b5_preflight.py').read_text())
    snapshot=json.loads((here/SNAPSHOT).read_text());decision=snapshot['authority'][0]['record']
    if decision['decision_id']!=DECISION or decision['metadata_json']['seed_families']!=[{'factor':f,'direction':d,'horizons_days':list(h)} for f,d,h in SEEDS]:raise ValueError('frozen seed authority mismatch')
    context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text());items=context['materialized_inputs']
    expected={r['object_path']:r for r in snapshot['candidate_cache_inputs']}
    discovery=[r for r in items if r['sha256']==DISCOVERY_SHA]
    if len(discovery)!=1 or discovery[0]['size_bytes']!=2411604:raise ValueError('discovery byte identity')
    discovery_blob=(work_root/'job_inputs/swing10/market_daily_history.csv').read_bytes()
    if len(discovery_blob)!=2411604 or hashlib.sha256(discovery_blob).hexdigest()!=DISCOVERY_SHA:raise ValueError('discovery immutable bytes')
    caches=[r for r in items if r['object_path'] in expected]
    if len(caches)!=len(expected) or len(items)!=len(expected)+1:raise ValueError('only exact inventoried 2024 metadata inputs + discovery hash validation allowed')
    frames={};identities=[]
    for row in sorted(caches,key=lambda r:r['object_path']):
        name=row['object_path'];symbol=name.split('/')[1]
        if row['size_bytes']!=expected[name]['object_size_bytes']:raise ValueError('registered candidate size')
        frame,identity=read_metadata(work_root/'market_cache/MARKET_CACHE_V1'/name,row['size_bytes'],row['sha256'],symbol)
        frames[symbol]=frame;identities.append({**row,**identity})
    tables=audit(snapshot,frames,identities);out=work_root/'research_outputs/swing10/s2_b5_preflight';out.mkdir(parents=True,exist_ok=True)
    ids={n:str(uuid.uuid4()) for n in FILES};decl=[]
    for name in FILES[:-1]:
        path=out/name;tables[name].to_csv(path,index=False,lineterminator='\n');blob=path.read_bytes()
        decl.append({'name':name,'artifact_id':ids[name],'size_bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'object_path':f"artifacts/{context['job_id']}/{context['attempt_id']}/{name}"})
    manifest={'protocol':PROTOCOL,'decision_id':DECISION,'mwe_id':'MWE-SW10-S2B5P-001','mwe_uuid':'d954ac3e-1a69-4bbb-a107-d8bb863c372a','execution':context,'parent':snapshot['parent'],'seed_cases':decision['metadata_json']['seed_families'],'source_inventory_snapshot_sha256':hashlib.sha256((here/SNAPSHOT).read_bytes()).hexdigest(),'candidate_input_byte_verification':identities,'discovery_input':{'sha256':DISCOVERY_SHA,'size_bytes':2411604,'regenerated':False,'decoded':False},'recommendation':'NO_CERTIFIED_INDEPENDENT_SAMPLE_CURRENTLY_AVAILABLE','prospective_options':['Acquire an immutable same-provider adjusted daily pre-discovery panel with endpoints strictly before 2025-02-03; certify universe/vintage/session/volume semantics before scientific freeze','Acquire same-provider adjusted daily post-discovery panel beginning after 2026-08-27; define sample prospectively in canonical thread, retaining causal predictor warmup and horizon endpoints'],'canonical_protocol_freeze_required':True,'candidate_period_selected':False,'no_outcome_based_selection':True,'outcome_blind_columns':META_COLUMNS,'outcomes_read':False,'outcomes_computed':False,'protected_data_access':False,'price_columns_decoded':False,'source_guard_passed':True,'limitations':['2024 caches are unadjusted minute data; no semantic substitution','Timestamp capacity does not certify finite adjusted predictors or daily benchmark compatibility','Contemporary selected universe; historical PIT membership/delisted coverage and original adjustment vintages not certified','Provider acquisition entitlement and incremental billing unverified; no new acquisition or paid fallback performed'],'cost':{'executor':'github_actions','paid_compute_selected':False,'cloud_run_selected':False,'incremental_billing_verified':False},'artifacts':decl,'manifest_identity':{'name':FILES[-1],'artifact_id':ids[FILES[-1]],'self_hash':'external registration; no recursive hash'}}
    (out/FILES[-1]).write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return {'status':'PASS','artifact':str((out/FILES[0]).relative_to(work_root)),'output_paths':[str((out/n).relative_to(work_root)) for n in FILES],'output_artifact_ids':{str((out/n).relative_to(work_root)):ids[n] for n in FILES}}
