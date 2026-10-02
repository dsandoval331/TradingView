"""Authorized same-provider daily acquisition and predictor-only certification."""
from __future__ import annotations
import ast
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from urllib.parse import urlparse
import numpy as np
import pandas as pd
import requests

RUNNER_ID='SW10-S2-B5-ACQUISITION'
SNAPSHOT='SW10_S2_B5A_ACQUISITION_AUTHORITY.json'
FILES=('daily_provider_entitlement_audit.json','daily_source_semantic_certification.csv','daily_symbol_coverage.csv','daily_case_endpoint_capacity.csv','daily_acquisition_source_registry.json','sw10_s2_b5a_acquisition_manifest.json')
COLUMNS=('symbol','trade_date','open','high','low','close','volume')
SEEDS=(('LIQ_ADJUSTED_PRICE','NEGATIVE',(5,7,10)),('LIQ_REPORTED_VOLUME','POSITIVE',(3,5,7,10)),('RET_MOM x MARKET_SPY_TREND10','POSITIVE',(7,10)))
END=pd.Timestamp('2025-02-02')
DISCOVERY_START=pd.Timestamp('2025-02-03')
BASE='https://api.massive.com'


def guard_source(source):
    tree=ast.parse(source)
    allowed={'__future__','ast','hashlib','json','os','pathlib','time','uuid','urllib.parse','numpy','pandas','requests'}
    deny={'eval','exec','__import__','pct_change','forward_returns','read_sql','read_csv','read_parquet','read_pickle','read_excel','bfill','interpolate','roll','lead','hac_mean','bh_adjust','post','put','patch','delete'}
    for n in ast.walk(tree):
        if isinstance(n,ast.Import) and any(a.name not in allowed for a in n.names):raise ValueError('unapproved scientific/network import')
        if isinstance(n,ast.ImportFrom) and n.module not in allowed:raise ValueError('unapproved scientific import')
        if isinstance(n,ast.Call):
            fn=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
            if fn in deny:raise ValueError('outcome/paid mutation primitive')
            if fn in {'shift','diff'}:
                a=n.args[0] if n.args else None
                if not isinstance(a,ast.Constant) or type(a.value)!=int or a.value<0:raise ValueError('literal past lag only')
            if fn=='get' and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Attribute) and n.func.value.attr=='session':
                if not any(isinstance(a,ast.Name) and a.id=='url' for a in n.args):raise ValueError('allowlisted GET only')


def validated_url(symbol,start,end):
    if not symbol or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in symbol):raise ValueError('invalid symbol')
    start=pd.Timestamp(start);end=pd.Timestamp(end)
    if start>end or end>=DISCOVERY_START:raise ValueError('pre-discovery date boundary')
    return BASE+f'/v2/aggs/ticker/{symbol}/range/1/day/{start.date()}/{end.date()}'


class Provider:
    def __init__(self,key):
        self.key=key;self.session=requests.Session();self.last=0.;self.records=[]
    def request(self,symbol,start,end):
        url=validated_url(symbol,start,end)
        gap=15.1-(time.monotonic()-self.last)
        if gap>0:time.sleep(gap)
        self.last=time.monotonic()
        params={'adjusted':'true','sort':'asc','limit':50000,'apiKey':self.key}
        try:r=self.session.get(url,params=params,timeout=45)
        except requests.RequestException as e:
            record={'symbol':symbol,'requested_start':str(pd.Timestamp(start).date()),'requested_end':str(pd.Timestamp(end).date()),'http_status':None,'transport_error_type':type(e).__name__};self.records.append(record);return None,record,None
        if self.key in r.text:raise ValueError('credential echo; persistence prohibited')
        try:p=r.json()
        except ValueError:p={}
        rows=p.get('results') or [];times=[z['t'] for z in rows if isinstance(z,dict) and 't' in z]
        record={'symbol':symbol,'requested_start':str(pd.Timestamp(start).date()),'requested_end':str(pd.Timestamp(end).date()),'http_status':r.status_code,'provider_status':p.get('status'),'provider_request_id':p.get('request_id'),'result_count':len(rows),'adjusted':p.get('adjusted'),'timestamp_min':min(times) if times else None,'timestamp_max':max(times) if times else None,'next_page_present':bool(p.get('next_url')),'raw_response_sha256':hashlib.sha256(r.content).hexdigest(),'raw_response_bytes':len(r.content),'endpoint':'/v2/aggs/ticker/{symbol}/range/1/day/{from}/{to}','acquired_at_utc':pd.Timestamp.now(tz='UTC').isoformat()}
        self.records.append(record)
        return p,record,r.content


def find_boundary(provider,symbol):
    """Binary search authorization, never return performance or sample size."""
    oldest=pd.Timestamp('2003-09-10');latest=pd.Timestamp('2025-01-31')
    p,r,_=provider.request(symbol,oldest,END)
    if r['http_status']==200:return oldest,'PROVIDER_HISTORICAL_FLOOR_AUTHORIZED'
    if r['http_status']!=403:return None,'PROVIDER_PROBE_INCONCLUSIVE'
    p,r,_=provider.request(symbol,latest,END)
    if r['http_status']!=200:return None,'NO_PRE_DISCOVERY_ACCESS'
    lo=oldest;hi=latest
    while (hi-lo).days>1:
        mid=lo+pd.Timedelta(days=(hi-lo).days//2);p,r,_=provider.request(symbol,mid,END)
        if r['http_status']==200:hi=mid
        elif r['http_status']==403:lo=mid
        else:return None,'PROVIDER_PROBE_INCONCLUSIVE'
    return hi,'EARLIEST_CALENDAR_AUTHORIZATION_BOUNDARY_PROBED'


def normalize(symbol,payload):
    if payload.get('adjusted') is not True or payload.get('ticker')!=symbol or payload.get('next_url'):raise ValueError('adjusted source identity or pagination incomplete')
    raw=payload.get('results') or []
    if not raw:raise ValueError('no daily bars')
    frame=pd.DataFrame(raw)
    if any(c not in frame for c in ('t','o','h','l','c','v')):raise ValueError('daily OHLCV fields missing')
    out=pd.DataFrame({'symbol':symbol,'trade_date':pd.to_datetime(frame.t,unit='ms',utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize(),'open':frame.o,'high':frame.h,'low':frame.l,'close':frame.c,'volume':frame.v})
    validate_panel(out)
    return out.sort_values(['symbol','trade_date']).reset_index(drop=True)


def validate_panel(panel):
    if tuple(panel.columns)!=COLUMNS:raise ValueError('exact predictor schema; outcome columns forbidden')
    if panel.isna().any().any() or panel.duplicated(['symbol','trade_date']).any():raise ValueError('null/duplicate source rows')
    if panel.trade_date.max()>=DISCOVERY_START:raise ValueError('discovery/protected dates prohibited')
    x=panel[['open','high','low','close','volume']]
    if not np.isfinite(x).all().all() or (x[['open','high','low','close']]<=0).any().any() or (x.volume<0).any():raise ValueError('invalid finite/price/volume fields')
    if ((panel.low>panel.high)|(panel.low>panel[['open','close']].min(axis=1))|(panel.high<panel[['open','close']].max(axis=1))).any():raise ValueError('OHLC integrity')


def centered_rank(series):
    x=series.where(np.isfinite(series));return 2*x.rank(method='average')/x.notna().sum()-1


def prospective_state(series):
    x=series.sort_index().where(np.isfinite(series.sort_index()));past=x.shift(1)
    mu=past.expanding(min_periods=20).mean();sd=past.expanding(min_periods=20).std(ddof=1)
    return ((x-mu)/sd).where(np.isfinite(x)&np.isfinite(mu)&np.isfinite(sd)&sd.gt(1e-12))


def predictors(panel):
    validate_panel(panel);x=panel.sort_values(['symbol','trade_date']).copy()
    x['RET_MOM']=x.close/x.groupby('symbol').close.shift(10)-1
    x['primary_rank']=x.groupby('trade_date').RET_MOM.transform(centered_rank)
    spy=x[x.symbol=='SPY'].set_index('trade_date').RET_MOM
    x['market_state_z']=x.trade_date.map(prospective_state(spy))
    return x


def capacity(panel,symbols):
    x=predictors(panel);rows=[];sc=[];dates=sorted(set(panel.trade_date));mapping={d:b for b,block in enumerate(np.array_split(dates,4),1) for d in block}
    for symbol in symbols:
        z=x[x.symbol==symbol];sc.append({'symbol':symbol,'rows':len(z),'first_date':str(z.trade_date.min())[:10] if len(z) else None,'last_date':str(z.trade_date.max())[:10] if len(z) else None,'finite_RET_MOM_dates':int(np.isfinite(z.RET_MOM).sum()),'finite_market_state_dates':int(np.isfinite(z.market_state_z).sum()),'source_covered':len(z)>0,'historical_universe_pit_certified':False})
    for family,direction,hs in SEEDS:
        for h in hs:
            eligible_dates=set();obs=0;counts={};blockobs={b:0 for b in range(1,5)}
            for symbol in symbols:
                z=x[x.symbol==symbol];ds=list(z.trade_date);finite=np.isfinite(z.primary_rank)&np.isfinite(z.market_state_z) if family.startswith('RET_MOM') else np.isfinite(z.close if family=='LIQ_ADJUSTED_PRICE' else z.volume)
                # Endpoint is a timestamp lookup only; never access its price/value.
                for i,date in enumerate(ds):
                    endpoint=ds[i+h] if i+h<len(ds) else None
                    if bool(finite.to_numpy()[i]) and endpoint is not None and endpoint<DISCOVERY_START:
                        obs+=1;eligible_dates.add(date);counts[date]=counts.get(date,0)+1;blockobs[mapping[date]]+=1
            rows.append({'family':family,'direction':direction,'horizon_days':h,'eligible_symbol_dates':obs,'eligible_dates':len(eligible_dates),'eligible_symbols':sum(r['source_covered'] for r in sc),'median_symbols_per_eligible_date':float(np.median(list(counts.values()))) if counts else 0,'first_eligible_date':str(min(eligible_dates))[:10] if eligible_dates else None,'last_eligible_date':str(max(eligible_dates))[:10] if eligible_dates else None,'chronological_block_observations':json.dumps(blockobs,sort_keys=True),'forward_returns_computed':False,'future_endpoint_prices_accessed_for_evaluation':False,'scientific_interval_selected':False})
    return pd.DataFrame(sc),pd.DataFrame(rows)


def run(work_root):
    here=Path(__file__).parent;guard_source((here/'swing10_s2_b5_acquisition.py').read_text())
    snapshot=json.loads((here/SNAPSHOT).read_text());context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text())
    symbols=snapshot['symbols']
    if len(symbols)!=112 or len(set(symbols))!=112 or 'SPY' not in symbols:raise ValueError('exact 112-symbol universe including SPY')
    if context['materialized_inputs']:raise ValueError('no protected/discovery input content permitted')
    out=work_root/'research_outputs/swing10/s2_b5_acquisition';out.mkdir(parents=True,exist_ok=True)
    key=os.environ.get('TR_MASSIVE_API_KEY') or os.environ.get('MASSIVE_API_KEY');source_paths=[];registry=[];panelparts=[];failed=[];entitlement={'credential_available':bool(key),'paid_activation_attempted':False,'literal_zero_billing_verified':False,'source_documentation':snapshot['documentation'],'prior_entitlement_decisions':snapshot['entitlement_evidence']}
    status='BLOCKED_CREDENTIALS';boundary=None
    if key:
        provider=Provider(key);boundary,reason=find_boundary(provider,'AAPL');entitlement['boundary_probe_status']=reason;entitlement['earliest_authorized_request_start']=str(boundary.date()) if boundary is not None else None
        status='PRE_DISCOVERY_DAILY_NOT_CERTIFIABLE'
        if boundary is not None:
            for symbol in symbols:
                payload,record,raw=provider.request(symbol,boundary,END)
                if record['http_status']!=200:
                    failed.append({'symbol':symbol,'reason':'SOURCE_ACCESS_FAILURE','http_status':record['http_status']});continue
                try:p=normalize(symbol,payload)
                except ValueError as e:failed.append({'symbol':symbol,'reason':str(e)});continue
                path=out/f'raw_{symbol}_{hashlib.sha256(raw).hexdigest()}.json';path.write_bytes(raw);source_paths.append(path);panelparts.append(p)
                registry.append({'symbol':symbol,'file':path.name,'source_record':record,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'adjusted':True,'daily_volume_semantics':'provider reported daily aggregate v, unchanged','price_semantics':'provider split-adjusted daily aggregate c; no dividend reinvestment','historical_original_vintage_certified':False,'source_schema':'Massive /v2/aggs/ticker/{symbol}/range/1/day adjusted=true','source_session':'provider daily ET aggregate; no minute resampling'})
            if len(panelparts)==112:status='PRE_DISCOVERY_DAILY_CERTIFIABLE'
        entitlement['probe_records']=provider.records
        if boundary is None and reason=='NO_PRE_DISCOVERY_ACCESS':status='BLOCKED_ENTITLEMENT'
        elif boundary is None:status='BLOCKED_OPERATIONAL_PROBE'
    else:entitlement['blocker']='No existing MASSIVE_API_KEY or TR_MASSIVE_API_KEY credential available to governed execution; no key printed or persisted'
    (out/FILES[0]).write_text(json.dumps(entitlement,indent=2,sort_keys=True)+'\n')
    if panelparts:
        panel=pd.concat(panelparts,ignore_index=True).sort_values(['symbol','trade_date']);validate_panel(panel);sc,cases=capacity(panel,symbols)
        blob=panel.to_csv(index=False,lineterminator='\n',float_format='%.17g').encode('utf-8');path=out/f'independent_adjusted_daily_panel_{hashlib.sha256(blob).hexdigest()}.csv';path.write_bytes(blob);source_paths.append(path)
        if not cases.eligible_dates.gt(0).all():status='PRE_DISCOVERY_DAILY_NOT_CERTIFIABLE'
    else:
        sc=pd.DataFrame([{'symbol':s,'rows':0,'source_covered':False,'historical_universe_pit_certified':False,'reason':status} for s in symbols]);cases=pd.DataFrame([{'family':f,'direction':d,'horizon_days':h,'eligible_symbol_dates':0,'eligible_dates':0,'capacity_status':'NOT_MEASURED_SOURCE_UNAVAILABLE','forward_returns_computed':False} for f,d,hs in SEEDS for h in hs])
    sc.to_csv(out/FILES[2],index=False,lineterminator='\n');cases.to_csv(out/FILES[3],index=False,lineterminator='\n')
    semantic=pd.DataFrame([{'family':f,'direction':d,'definition':'adjusted close_t' if f=='LIQ_ADJUSTED_PRICE' else 'reported daily volume_t' if f=='LIQ_REPORTED_VOLUME' else 'RET_MOM10 same-date finite average ranks/N centered; SPY trend10 normalized on >=20 strictly prior finite observations, ddof1, SD>1e-12','compatible_as_frozen_proxy':status=='PRE_DISCOVERY_DAILY_CERTIFIABLE','source_status':status,'original_vintage_pit_certified':False,'survivorship_universe_certified':False,'limitation':'frozen contemporary 112-symbol universe; retrospective adjusted-price snapshot, not original-vintage historical prices; no earnings calendars'} for f,d,hs in SEEDS]);semantic.to_csv(out/FILES[1],index=False,lineterminator='\n')
    (out/FILES[4]).write_text(json.dumps({'sources':registry,'failed_symbols':failed,'symbols_accounted_for':symbols,'source_price_fields_inspected_only_for':'OHLCV integrity, adjustment semantics and causal predictor construction; no outcome evaluation','prospective_post_discovery_route':{'decision_dates':'strictly after 2026-08-27','requires':'same provider daily adjusted=true, all112/SPY, >=10 trailing +20 prior finite trend observations, endpoint timestamps, immutable vintage metadata','credential_required':not bool(key),'no_post_discovery_price_request_performed':True,'canonical_scientific_freeze_required':True}},indent=2,sort_keys=True)+'\n')
    allpaths=[out/n for n in FILES]+source_paths;ids={p.name:str(uuid.uuid4()) for p in allpaths};decl=[]
    for path in allpaths:
        if path.name==FILES[-1]:continue
        blob=path.read_bytes();decl.append({'name':path.name,'artifact_id':ids[path.name],'size_bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'object_path':f"artifacts/{context['job_id']}/{context['attempt_id']}/{path.name}",'source_object':path in source_paths})
    manifest={'mwe_id':snapshot['mwe_id'],'mwe_uuid':snapshot['mwe_uuid'],'parent_decision_id':snapshot['authority']['decision_id'],'user_authority_snapshot_sha':hashlib.sha256((here/SNAPSHOT).read_bytes()).hexdigest(),'execution':context,'classification':status,'pre_discovery_requested_end':'2025-02-02','account_boundary_start':str(boundary.date()) if boundary is not None else None,'scientific_interval_selected':False,'scientific_validation_executed':False,'nine_frozen_cases':SEEDS,'source_guard_passed':True,'protected_data_access':False,'validation_outcomes_read':False,'validation_outcomes_computed':False,'original_vintage_pit_certified':False,'universe_survivorship_certified':False,'source_identity':'Massive daily aggregates adjusted=true; no minute substitution','paid_compute_selected':False,'provider_upgrade_selected':False,'incremental_billing_verified':False,'artifacts':decl,'manifest_identity':{'name':FILES[-1],'artifact_id':ids[FILES[-1]],'self_hash':'external registration'},'provider_request_count':len(entitlement.get('probe_records',[])),'certified_symbols':len(panelparts),'stop_before_scientific_validation':True}
    (out/FILES[-1]).write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return {'status':'PASS','artifact':str((out/FILES[0]).relative_to(work_root)),'output_paths':[str(p.relative_to(work_root)) for p in allpaths],'output_artifact_ids':{str(p.relative_to(work_root)):ids[p.name] for p in allpaths}}
