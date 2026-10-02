"""Frozen predictor-only remaining-factor semantic certification. No outcome API."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import uuid
import numpy as np
import pandas as pd
from tr_platform.research.swing10_causal_inputs import causal_factors

PROTOCOL='SW10_S2_B4_PREFLIGHT_V1'
DECISION='79a7238b-fb84-423a-8326-b75d53703181'
RUNNER_ID='SW10-S2-B4-PREFLIGHT'
INPUT_SHA='ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2'
INPUT_BYTES=2411604
PANEL_COLUMNS=('symbol','trade_date','open','high','low','close','volume')
SOURCE_FILES=('swing10_s2_b4_preflight.py','swing10_causal_inputs.py')
SNAPSHOT='SW10_S2_B4_PREFLIGHT_V1.persisted.json'
FILES=('b4_component_semantic_registry.csv','b4_source_inventory.json',
       'b4_component_date_coverage.csv','b4_component_temporal_coverage.csv',
       'b4_component_symbol_participation.csv','b4_component_geometry.csv',
       'b4_component_summary.csv','b4_representation_recommendations.json',
       'sw10_s2_b4_preflight_manifest.json')
# Single prospective construction per component; no window or normalization search.
COMPONENTS=(
 ('REL_MARKET_10','REL_STRENGTH','SYMBOL_DATE','trailing10 adjusted price change minus SPY same-date trailing10 adjusted price change; exclude SPY self-reference',10,'SPY proxy for US large-cap market; mixed equity/ETF panel, not total market or total return'),
 ('REL_SECTOR_10','REL_STRENGTH','SYMBOL_DATE','trailing10 relative price change versus causally aligned sector benchmark with certified historical membership',10,'UNAVAILABLE: sector benchmarks absent from certified panel; retrospective PMS mapping audit is not an independently registered SW10 PIT membership/benchmark input'),
 ('REL_INDUSTRY_10','REL_STRENGTH','SYMBOL_DATE','trailing10 relative price change versus causally aligned industry benchmark with certified historical membership',10,'UNAVAILABLE: industry benchmark and membership identities absent; no current membership backfill'),
 ('LIQ_CLOSE_DOLLAR_VOLUME','LIQUIDITY','SYMBOL_DATE','adjusted close_t * reported volume_t',0,'Closing-price notional proxy, not exact transaction dollar volume; adjustment vintage not independently certified'),
 ('LIQ_ADJUSTED_PRICE','LIQUIDITY','SYMBOL_DATE','adjusted close_t',0,'Price/tradability proxy; not historical nominal share price, order fillability or broker constraint'),
 ('LIQ_REPORTED_VOLUME','LIQUIDITY','SYMBOL_DATE','reported daily volume_t',0,'Activity proxy; not transaction count, order flow, shares outstanding or shares turnover'),
 ('LIQ_PRIOR20_ACTIVITY','LIQUIDITY','SYMBOL_DATE','volume_t / mean(20 immediately preceding valid completed volumes); denominator > 0',20,'Relative activity proxy; exact causal VOL_TURN_V2 definition, not shares turnover'),
 ('LIQ_RANGE_SPREAD_PROXY','LIQUIDITY','SYMBOL_DATE','(high_t-low_t)/close_t',0,'Daily range-based spread proxy only; contains volatility; not a bid/ask estimator, true spread or transaction cost estimate'),
 ('LIQ_TRUE_BID_ASK','LIQUIDITY','SYMBOL_DATE','causally observed ask-minus-bid quote spread',0,'UNAVAILABLE: daily OHLCV contains no quotes; no certified quote input'),
 ('LIQ_SHARES_TURNOVER','LIQUIDITY','SYMBOL_DATE','volume_t / PIT shares_outstanding_t',0,'UNAVAILABLE: no independently certified point-in-time shares-outstanding input'),
 ('LIQ_TRANSACTION_COUNT','LIQUIDITY','SYMBOL_DATE','reported daily transaction count',0,'UNAVAILABLE on certified input: live table has transactions, but immutable seven-column panel does not; separate immutable source certification required'),
 ('LIQ_VWAP_DOLLAR_VOLUME','LIQUIDITY','SYMBOL_DATE','daily VWAP_t * volume_t',0,'UNAVAILABLE on certified input: live table has vwap, but immutable seven-column panel does not; separate immutable source certification required'),
 ('MARKET_SPY_TREND10','MARKET_REG','MARKET_DATE','SPY close_t/close_t-10 - 1',10,'SPY large-cap ETF trend proxy; continuous, no favorable trend-state thresholds'),
 ('MARKET_SPY_VOL14','MARKET_REG','MARKET_DATE','SPY prior14 true-range mean / previous close',14,'SPY volatility proxy; exact existing causal VOL_REGIME definition, not an implied-volatility index'),
 ('MARKET_PANEL_BREADTH10','MARKET_REG','MARKET_DATE','same-date equal-weight non-SPY panel fraction with trailing10 price change > 0',10,'Frozen mixed equity/ETF panel breadth proxy, not historical market constituent breadth; no market-cap weighting'),
 ('MARKET_PANEL_DISPERSION10','MARKET_REG','MARKET_DATE','same-date sample SD (ddof=1) of non-SPY panel trailing10 price changes',10,'Frozen panel dispersion proxy, not future-return dispersion or predictive effect size'),
)
COMPONENT_IDS=tuple(c[0] for c in COMPONENTS)
UNAVAILABLE_IDS=tuple(c[0] for c in COMPONENTS if c[5].startswith('UNAVAILABLE'))


def reject_columns(frame,allowed):
    if tuple(frame.columns)!=tuple(allowed):
        raise ValueError('outcome-blind exact schema required')


def guard_source(source):
    tree=ast.parse(source)
    allowed={'__future__','ast','hashlib','json','pathlib','uuid','numpy','pandas','tr_platform.research.swing10_causal_inputs'}
    denied={'pct_change','forward_returns','hac_mean','bh_adjust','read_sql','read_parquet','read_pickle','read_excel','read_feather','read_hdf','read_json','urlopen','eval','exec','__import__','getattr','setattr','roll','lead','future_returns','mfe','mae','first_passage','bfill','backfill','interpolate','merge_asof','load','loadtxt','genfromtxt','fromfile'}
    for n in ast.walk(tree):
        if isinstance(n,ast.Import) and any(a.name not in allowed for a in n.names):raise ValueError('non-approved/outcome-capable import')
        if isinstance(n,ast.ImportFrom) and n.module not in allowed:raise ValueError('non-approved/outcome-capable import')
        if isinstance(n,ast.Attribute) and n.attr in {'iloc','iat'}:raise ValueError('positional future access prohibited')
        if isinstance(n,ast.Call):
            fn=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
            if fn in denied:raise ValueError('outcome/future primitive prohibited')
            if fn=='rolling' and any(k.arg=='center' and not (isinstance(k.value,ast.Constant) and k.value.value is False) for k in n.keywords):raise ValueError('centered future window prohibited')
            if fn in {'shift','diff'}:
                arg=n.args[0] if n.args else next((k.value for k in n.keywords if k.arg=='periods'),None)
                if not isinstance(arg,ast.Constant) or type(arg.value)!=int or arg.value<0:raise ValueError('literal past shift only')
            if fn in {'read_csv','read_text','read_bytes','open','Path'}:
                for a in ast.walk(n):
                    if isinstance(a,ast.Constant) and isinstance(a.value,str) and any(x in a.value.lower() for x in ('holdout','protected','factor_causal_summary','interaction_b3_summary','factor_date_spreads','interaction_date_coefficients','s2_b2','s2_b3')):
                        raise ValueError('prohibited scientific/protected artifact access')
    # Data CSV reads only belong to the exact-hash validating input reader.
    for fn in (n for n in tree.body if isinstance(n,ast.FunctionDef)):
        for n in ast.walk(fn):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='read_csv' and fn.name!='verify_input':raise ValueError('unvalidated data read prohibited')


def validate_panel(panel):
    reject_columns(panel,PANEL_COLUMNS)
    if panel.duplicated(['symbol','trade_date']).any() or panel.isna().any().any():raise ValueError('invalid panel keys/nulls')
    z=panel[['open','high','low','close','volume']]
    if not np.isfinite(z).all().all() or (z[['open','high','low','close']]<=0).any().any() or (panel.volume<0).any():raise ValueError('invalid prices/volume')
    if ((panel.low>panel.high)|(panel.low>panel[['open','close']].min(axis=1))|(panel.high<panel[['open','close']].max(axis=1))).any():raise ValueError('invalid OHLC')


def verify_input(path):
    blob=path.read_bytes()
    if len(blob)!=INPUT_BYTES or hashlib.sha256(blob).hexdigest()!=INPUT_SHA:raise ValueError('immutable SHA/bytes mismatch')
    panel=pd.read_csv(path,parse_dates=['trade_date'])
    validate_panel(panel)
    if len(panel)!=44128 or panel.symbol.nunique()!=112 or panel.trade_date.nunique()!=394 or not panel.groupby('symbol').size().eq(394).all():raise ValueError('immutable universe mismatch')
    if panel.trade_date.min()!=pd.Timestamp('2025-02-03') or panel.trade_date.max()!=pd.Timestamp('2026-08-27'):raise ValueError('immutable date mismatch')
    return panel


def construct(panel):
    validate_panel(panel)
    f=causal_factors(panel)
    spy=f[f.symbol=='SPY'].set_index('trade_date')
    if len(spy)!=panel.trade_date.nunique() or set(spy.index)!=set(panel.trade_date):raise ValueError('SPY exact date alignment required; no fill')
    values={};participants={}
    def put(name,z,v):
        a=z[['symbol','trade_date']].copy();a['value']=np.asarray(v,dtype=float);a=a[np.isfinite(a.value)].copy();values[name]=a;participants[name]=a[['symbol','trade_date']].copy()
    z=f[f.symbol!='SPY'].copy()
    put('REL_MARKET_10',z,z.RET_MOM-z.trade_date.map(spy.RET_MOM))
    put('LIQ_CLOSE_DOLLAR_VOLUME',f,f.close*f.volume)
    put('LIQ_ADJUSTED_PRICE',f,f.close)
    put('LIQ_REPORTED_VOLUME',f,f.volume)
    put('LIQ_PRIOR20_ACTIVITY',f,f.VOL_TURN_V2_CAUSAL)
    put('LIQ_RANGE_SPREAD_PROXY',f,(f.high-f.low)/f.close)
    sp=f[f.symbol=='SPY']
    put('MARKET_SPY_TREND10',sp,sp.RET_MOM)
    put('MARKET_SPY_VOL14',sp,sp.VOL_REGIME)
    q=z[np.isfinite(z.RET_MOM)].copy()
    for name in ('MARKET_PANEL_BREADTH10','MARKET_PANEL_DISPERSION10'):
        g=q.groupby('trade_date').RET_MOM
        v=g.apply(lambda x:float((x>0).mean())) if name=='MARKET_PANEL_BREADTH10' else g.std(ddof=1)
        a=v.rename('value').reset_index();a['symbol']='PANEL_AGGREGATE';values[name]=a[['symbol','trade_date','value']];participants[name]=q[['symbol','trade_date']].copy()
    for name in UNAVAILABLE_IDS:
        values[name]=pd.DataFrame(columns=['symbol','trade_date','value']);participants[name]=pd.DataFrame(columns=['symbol','trade_date'])
    if set(values)!=set(COMPONENT_IDS):raise ValueError('exact component family required')
    return values,participants


def fixed_blocks(dates):
    return {d:i for i,a in enumerate(np.array_split(np.array(sorted(set(dates)),dtype=object),4),1) for d in a}


def dispersion(values):
    x=np.asarray(values,dtype=float);x=x[np.isfinite(x)]
    if not len(x):return dict.fromkeys(('mean','median','sample_sd','min','p10','p25','p75','p90','max','unique_fraction','excess_tie_rate','zero_rate','near_zero_variance'),np.nan)
    unique=len(np.unique(x));sd=float(np.std(x,ddof=1)) if len(x)>1 else np.nan
    return {'mean':float(x.mean()),'median':float(np.median(x)),'sample_sd':sd,'min':float(x.min()),'p10':float(np.quantile(x,.1)),'p25':float(np.quantile(x,.25)),'p75':float(np.quantile(x,.75)),'p90':float(np.quantile(x,.9)),'max':float(x.max()),'unique_fraction':unique/len(x),'excess_tie_rate':1-unique/len(x),'zero_rate':float((x==0).mean()),'near_zero_variance':bool(len(x)>1 and sd<=1e-12)}


def audit(panel):
    values,participation=construct(panel);dates=sorted(panel.trade_date.unique());mapping=fixed_blocks(dates);symbols=sorted(panel.symbol.unique())
    registry=[];dr=[];temporal=[];sr=[];geometry=[];summary=[]
    for name,family,scope,definition,lookback,limitation in COMPONENTS:
        v=values[name];part=participation[name];counts=part.groupby('trade_date').size();rawcounts=v.groupby('trade_date').size()
        ed=sorted(v.trade_date.unique());available=name not in UNAVAILABLE_IDS;block_dates=[]
        for b in range(1,5):
            cal=[d for d in dates if mapping[d]==b];p=part[part.trade_date.isin(cal)];x=v[v.trade_date.isin(cal)];c=p.groupby('trade_date').size().reindex(cal,fill_value=0);n=x.trade_date.nunique();block_dates.append(n)
            temporal.append({'component':name,'block':b,'fixed_date_start':str(min(cal))[:10],'fixed_date_end':str(max(cal))[:10],'panel_dates':len(cal),'eligible_dates':n,'participating_symbol_dates':len(p),'distinct_symbols':p.symbol.nunique(),'median_symbols_per_panel_date':float(c.median()),'minimum_symbols_per_panel_date':int(c.min()),**dispersion(x.value)})
        disposition='CERTIFIED_PROXY' if available and all(n>0 for n in block_dates) else 'UNAVAILABLE'
        reason='Exact causal proxy construction; finite coverage in every fixed chronological block; not original-vintage or microstructure certification' if disposition=='CERTIFIED_PROXY' else limitation if not available else 'No finite coverage in one or more fixed blocks'
        registry.append({'component':name,'family':family,'scope':scope,'definition':definition,'lookback_completed_observations':lookback,'timing':'after completed daily bar t','source':'certified immutable OHLCV panel; SPY same-date only' if available else 'required supplemental certified source absent','point_in_time_status':'CAUSAL_THROUGH_T_ON_CERTIFIED_SNAPSHOT; ORIGINAL_VINTAGE_UNVERIFIED' if available else 'NOT_CERTIFIED_FOR_REQUIRED_SOURCE','disposition':disposition,'reason':reason,'limitations':limitation})
        for date in dates:
            x=v[v.trade_date==date];dr.append({'component':name,'trade_date':date,'fixed_block':mapping[date],'panel_symbols':len(symbols),'eligible_symbols':int(counts.get(date,0)),'predictor_value_rows':int(rawcounts.get(date,0)),'eligible':len(x)>0,**dispersion(x.value)})
        pc=part.groupby('symbol').size();total=int(pc.sum());shares=pc/total if total else pc.astype(float);order=sorted(pc.index,key=lambda s:(-int(pc[s]),s));top={n:float(sum(shares[s] for s in order[:n])) if total else 0. for n in (1,5,10)}
        for symbol in symbols:
            sr.append({'component':name,'symbol':symbol,'eligible_symbol_dates':int(pc.get(symbol,0)),'share_of_predictor_source_observations':float(shares.get(symbol,0)),'participation_rate_of_panel_dates':int(pc.get(symbol,0))/len(dates),'source_count_rank':order.index(symbol)+1 if symbol in order else None})
        # Predictor-only one-column geometry, not a response model or significance test.
        x=np.asarray(v.value,dtype=float);sd=float(np.std(x,ddof=1)) if len(x)>1 else np.nan
        geometry.append({'component':name,'scope':scope,'observations':len(x),'centered_predictor_rank':int(np.isfinite(sd) and sd>1e-12),'centered_predictor_norm':float(np.linalg.norm(x-x.mean())) if len(x) else np.nan,'geometry_applicability':'single predictor only; multivariable condition/VIF not applicable; market_date values not cross-sectional fits',**dispersion(x)})
        base=len(panel[panel.symbol!='SPY']) if name=='REL_MARKET_10' else len(dates) if scope=='MARKET_DATE' else len(panel)
        obs=len(v);summary.append({'component':name,'family':family,'scope':scope,'disposition':disposition,'reason':reason,'lookback_completed_observations':lookback,'panel_dates':len(dates),'eligible_dates':len(ed),'eligible_predictor_observations':obs,'candidate_observations':base,'missing_predictor_observations':base-obs,'missing_rate':(base-obs)/base,'eligible_symbols':part.symbol.nunique(),'median_symbols_per_eligible_date':float(counts.median()) if len(counts) else 0.,'minimum_symbols_per_eligible_date':int(counts.min()) if len(counts) else 0,'first_eligible_date':str(min(ed))[:10] if ed else None,'last_eligible_date':str(max(ed))[:10] if ed else None,'four_block_coverage':all(n>0 for n in block_dates),'source_participation_observations':total,'top1_observation_share':top[1],'top5_observation_share':top[5],'top10_observation_share':top[10],'observation_hhi':float(np.square(shares).sum()),'future_data_invariance':True if available else None,'limitations':limitation,**dispersion(x)})
    tables=dict(zip((FILES[0],FILES[2],FILES[3],FILES[4],FILES[5],FILES[6]),map(pd.DataFrame,(registry,dr,temporal,sr,geometry,summary))))
    return tables,{'fixed_blocks':[{'block':b,'date_start':str(min(d for d in dates if mapping[d]==b))[:10],'date_end':str(max(d for d in dates if mapping[d]==b))[:10],'dates':sum(mapping[d]==b for d in dates)} for b in range(1,5)],'summary':summary}


def invariance_check(panel):
    dates=sorted(panel.trade_date.unique());cut=dates[len(dates)//2];mutated=panel.astype({c:float for c in ('open','high','low','close','volume')}).copy();mask=mutated.trade_date>cut
    for col in ('open','high','low','close'):mutated.loc[mask,col]*=1.37
    mutated.loc[mask,'volume']*=2
    a,_=construct(panel);b,_=construct(mutated)
    for name in COMPONENT_IDS:
        x=a[name][a[name].trade_date<=cut].sort_values(['symbol','trade_date']).reset_index(drop=True)
        y=b[name][b[name].trade_date<=cut].sort_values(['symbol','trade_date']).reset_index(drop=True)
        pd.testing.assert_frame_equal(x,y,check_exact=True)
    return {'cutoff':str(cut)[:10],'all_components_passed':True,'method':'mutate prices/volume only strictly after cutoff; past predictor frames must match exactly','outcomes_used':False}


def validate_context(context):
    items=context['materialized_inputs']
    if len(items)!=1 or items[0]['sha256']!=INPUT_SHA or items[0]['size_bytes']!=INPUT_BYTES or items[0]['object_path']!='governed_inputs/swing10/s2_b1/market_daily_history_2025-02-03_2026-08-27/'+INPUT_SHA+'.csv':raise ValueError('only exact immutable input permitted')


def run(work_root):
    here=Path(__file__).parent
    for name in SOURCE_FILES:guard_source((here/name).read_text())
    snapshot=json.loads((here/SNAPSHOT).read_text())
    if snapshot['authority']['decision']['decision_id']!=DECISION:raise ValueError('wrong frozen authority')
    context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text());validate_context(context)
    panel=verify_input(work_root/'job_inputs/swing10/market_daily_history.csv')
    invariant=invariance_check(panel);tables,evidence=audit(panel)
    recommendations={'protocol':PROTOCOL,'basis':'only source semantics, coverage and predictor-side geometry; no predictive quantity','later_canonical_freeze_required':True,'recommended_proxy_components':[r['component'] for r in evidence['summary'] if r['disposition']=='CERTIFIED_PROXY'],'excluded_components':[r['component'] for r in evidence['summary'] if r['disposition']=='UNAVAILABLE'],'no_composite_scoring':True,'no_parameter_search':True,'original_vintage_caveat':'certified adjusted snapshot does not independently establish values as originally disseminated at historical t','market_scope':'SPY ETF large-cap proxy; frozen mixed equity/ETF non-SPY panel proxies; no market-constituent universe claim','future_data_invariance':invariant}
    documents={FILES[1]:{'source_audit':snapshot['source_audit'],'inventory':snapshot['source_inventory'],'benchmark_identity_source':snapshot['benchmark_identity_source'],'new_source_materialized':False,'membership_backfill_used':False},FILES[7]:recommendations}
    out=work_root/'research_outputs/swing10/s2_b4_preflight';out.mkdir(parents=True,exist_ok=True);ids={n:str(uuid.uuid4()) for n in FILES};decl=[]
    for name in FILES[:-1]:
        path=out/name
        if name in tables:tables[name].to_csv(path,index=False,float_format='%.17g',lineterminator='\n')
        else:path.write_text(json.dumps(documents[name],indent=2,sort_keys=True)+'\n')
        blob=path.read_bytes();decl.append({'artifact_id':ids[name],'name':name,'size_bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'object_path':f"artifacts/{context['job_id']}/{context['attempt_id']}/{name}"})
    manifest={'protocol':PROTOCOL,'decision_id':DECISION,'mwe_id':'MWE-SW10-S2B4P-001','mwe_uuid':'0117f1d1-34a0-4354-8545-a1a97cfec076','execution':context,'parent':snapshot['authority']['parent'],'input':{'identity':'market_daily_history_2025-02-03_2026-08-27','sha256':INPUT_SHA,'size_bytes':INPUT_BYTES,'rows':44128,'symbols':112,'dates':394,'date_start':'2025-02-03','date_end':'2026-08-27','regenerated':False},'prospective_representation_spec':snapshot['prospective_representation_spec'],'component_ids':COMPONENT_IDS,'dispositions':{r['component']:r['disposition'] for r in evidence['summary']},'fixed_blocks':evidence['fixed_blocks'],'future_data_invariance':invariant,'near_zero_variance_diagnostic_epsilon':1e-12,'epsilon_used_for_selection':False,'source_guard_passed':True,'strict_panel_schema':PANEL_COLUMNS,'forward_outcomes_read':False,'forward_outcomes_computed':False,'path_outcomes_read':False,'path_outcomes_computed':False,'protected_data_access':False,'scientific_outcome_artifacts_accessed':False,'historical_earnings_used':False,'no_composite_scoring':True,'scientific_protocol_frozen_by_work':False,'artifacts':decl,'manifest_identity':{'artifact_id':ids[FILES[-1]],'name':FILES[-1],'self_hash':'external registration; no recursive self-hash'},'source_file_hashes':{n:hashlib.sha256((here/n).read_bytes()).hexdigest() for n in SOURCE_FILES+(SNAPSHOT,)},'cost':{'executor':'github_actions','runner':'ubuntu-latest','paid_compute_selected':False,'incremental_billing_verified':False}}
    (out/FILES[-1]).write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return {'status':'PASS','artifact':str((out/FILES[6]).relative_to(work_root)),'output_paths':[str((out/n).relative_to(work_root)) for n in FILES],'output_artifact_ids':{str((out/n).relative_to(work_root)):ids[n] for n in FILES},'artifact_contract':[{'artifact_id':ids[n],'relative_path':str((out/n).relative_to(work_root)),'is_primary':n==FILES[6]} for n in FILES]}
