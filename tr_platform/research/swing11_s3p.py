"""Outcome-blind SWING11 S3P. No candidate outcome operation is available."""
import ast
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from tr_platform.research import swing11_s2a as source
from tr_platform.research import swing11_s3_contract as contract

MWE='b1e57ab2-19a5-4fc0-a375-11a369650204'
DECISIONS={'5a2508a3-0837-4080-b3e2-9dec28eecc31','f41b3c8b-3d19-4fb6-9ded-2d91c9ab037a','8ef41b93-e42c-4b53-bcca-23c8f8eb3f4e'}
SCHEMAS={
 'sw11_s3p_candidate_registry.csv':('candidate','PRICE_rule','RV20_rule','score','long_rule','short_rule','minimum_side','primary_horizons','scientific_execution_authorized'),
 'sw11_s3p_predictor_candidate_values.csv':('symbol','trade_date','PRICE_raw','PRICE','PRICE_pct','RV20_raw','RV20','RV20_pct','C2_score','C2_pct','C0_long','C0_short','C1_long','C1_short','C2_long','C2_short'),
 'sw11_s3p_capacity_geometry.csv':('candidate','horizon','decision_date','entry_date','exit_date','calendar_capacity','long_N','short_N','no_trade','gross_inception','net_inception','planned_long_weight','planned_short_weight','scheduled_active_cohorts','scheduled_cash_sleeves','block','predictor_only'),
 'sw11_s3p_temporal_blocks.csv':('candidate','horizon','block','start','end','comparison_dates','active_dates','active_rate','minimum_side_N','median_long_N','median_short_N','predictor_only'),
 'sw11_s3p_advancement_registry.csv':('test_id','candidate','type','BH_size','BH_q','HAC_lag','ES_threshold','positive_horizons','minimum_dates','minimum_active_rate','minimum_block_dates','positive_blocks','maximum_block_share','maximum_top5','maximum_HHI','maximum_leave5_ES_loss','synthetic_only_certified','real_disposition_computed'),
 'sw11_s3p_semantic_audit.csv':('check','passed','detail','input_id','input_sha','input_bytes','protected_access','real_outcomes_computed'),
}
FILES=tuple(SCHEMAS)+('sw11_s3p_execution_contract.json','sw11_s3p_manifest.json')

def guard_source(text):
 tree=ast.parse(text)
 tree.body=[n for n in tree.body if not (isinstance(n,ast.FunctionDef) and n.name=='guard_source')]
 forbidden={'synthetic_cohort','synthetic_daily_sleeve','synthetic_family','synthetic_hac','analyze','estimate','select','read_sql','read_parquet','bfill','interpolate','eval','exec','__import__','forward_return','profitability','win_rate','candidate_return','portfolio_return'}
 for n in ast.walk(tree):
  if isinstance(n,ast.ImportFrom) and n.module not in {'pathlib','tr_platform.research'}:raise ValueError('unauthorized preflight import')
  if isinstance(n,ast.ImportFrom) and n.module=='tr_platform.research' and any(a.name not in {'swing11_s2a','swing11_s3_contract'} for a in n.names):raise ValueError('scientific artifact/module import denied')
  if isinstance(n,ast.Call):
   name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
   if name in forbidden:raise ValueError('outcome primitive denied from preflight')
   if name=='shift' and (not n.args or not isinstance(n.args[0],ast.Constant) or not isinstance(n.args[0].value,int) or n.args[0].value<=0):raise ValueError('future shift denied')
  if isinstance(n,ast.Constant) and isinstance(n.value,str) and ('b905affcb0843a4d' in n.value or '86045cd0-8e49' in n.value):raise ValueError('protected source denied')
 return True

def predictors(frame):
 source.reject_schema(frame.columns)
 if frame.duplicated(['symbol','trade_date']).any():raise ValueError('duplicate predictor bars')
 parts=[]
 for symbol,g in frame.groupby('symbol',sort=True):
  g=g.sort_values('trade_date').copy();c=pd.to_numeric(g.close,errors='coerce').where(lambda x:np.isfinite(x)&(x>0))
  g['PRICE_raw']=c
  g['RV20_raw']=(c/c.shift(1)-1).rolling(20,min_periods=20).std(ddof=1)
  parts.append(g[['symbol','trade_date','PRICE_raw','RV20_raw']])
 out=pd.concat(parts).sort_values(['trade_date','symbol'])
 for name in ('PRICE','RV20'):
  out[name+'_raw']=out[name+'_raw'].where(np.isfinite(out[name+'_raw']))
  out[name]=out.groupby('trade_date')[name+'_raw'].transform(source.centered_rank)
  out[name+'_pct']=(out[name]+1)/2
 out['C2_score']=-out.PRICE*(1+out.RV20)/2
 out['C2_pct']=out.groupby('trade_date').C2_score.transform(lambda x:(source.centered_rank(x)+1)/2)
 for c in ('C0','C1','C2'):
  pct=out.C2_pct if c=='C2' else out.PRICE_pct
  out[c+'_long']=np.isfinite(pct)&(pct>=.8 if c=='C2' else pct<=.2)
  out[c+'_short']=np.isfinite(pct)&(pct<=.2 if c=='C2' else pct>=.8)
  if c=='C1':
   out[c+'_long'] &= np.isfinite(out.RV20_pct)&(out.RV20_pct>=.5)
   out[c+'_short'] &= np.isfinite(out.RV20_pct)&(out.RV20_pct>=.5)
 return out[list(SCHEMAS[FILES[1]])]

def memberships(group,candidate,removed=()):
 # Leave-five keeps original predictor/score ranks; membership is not reranked.
 c=candidate.replace('S3-','');g=group[~group.symbol.isin(removed)]
 long=g.loc[g[c+'_long'],'symbol'].tolist();short=g.loc[g[c+'_short'],'symbol'].tolist()
 no_trade=len(long)<5 or len(short)<5 or bool(set(long)&set(short))
 return long,short,no_trade

def registry():
 return pd.DataFrame([dict(candidate=c,PRICE_rule='full finite same-date average rank/N',RV20_rule='none' if c=='S3-C0' else 'previous20 historical-return SD ddof1;finite rank;'+('p>=0.50' if c=='S3-C1' else 'bounded continuous'),score='-PRICE*(1+RV20)/2' if c=='S3-C2' else '',long_rule='score p>=.80' if c=='S3-C2' else 'PRICE p<=.20',short_rule='score p<=.20' if c=='S3-C2' else 'PRICE p>=.80',minimum_side=5,primary_horizons='5/7/10/15',scientific_execution_authorized=False) for c in contract.CANDIDATES])

def prepare(frame):
 values=predictors(frame);dates=sorted(frame.trade_date.unique());comparison=dates[:-15]
 blocks=[list(x) for x in np.array_split(comparison,4)];blockmap={d:i+1 for i,b in enumerate(blocks) for d in b}
 groups={date:g for date,g in values.groupby('trade_date')};capacity=[];temporal=[]
 for candidate in contract.CANDIDATES:
  schedule={}
  for t,date in enumerate(comparison):
   long,short,no=memberships(groups[date],candidate);schedule[t]=not no
   for h in contract.HORIZONS:
    entry,exit=contract.indices(t,h,len(dates))
    active=sum(schedule.get(x,False) for x in range(max(0,t-h+1),t+1));cash=h-active
    capacity.append(dict(candidate=candidate,horizon=h,decision_date=date,entry_date=dates[entry],exit_date=dates[exit],calendar_capacity=True,long_N=len(long),short_N=len(short),no_trade=no,gross_inception=0 if no else 1,net_inception=0,planned_long_weight=0 if no else .5/len(long),planned_short_weight=0 if no else -.5/len(short),scheduled_active_cohorts=active,scheduled_cash_sleeves=cash,block=blockmap[date],predictor_only=True))
  for h in contract.HORIZONS:
   for i,b in enumerate(blocks):
    rows=[r for r in capacity if r['candidate']==candidate and r['horizon']==h and r['decision_date'] in b]
    active=[r for r in rows if not r['no_trade']]
    temporal.append(dict(candidate=candidate,horizon=h,block=i+1,start=b[0] if b else None,end=b[-1] if b else None,comparison_dates=len(rows),active_dates=len(active),active_rate=len(active)/len(rows) if rows else None,minimum_side_N=min([min(r['long_N'],r['short_N']) for r in active],default=None),median_long_N=float(np.median([r['long_N'] for r in active])) if active else None,median_short_N=float(np.median([r['short_N'] for r in active])) if active else None,predictor_only=True))
 return values,pd.DataFrame(capacity),pd.DataFrame(temporal),blocks

def advancement_registry():
 return pd.DataFrame([dict(test_id=t,candidate=t.split('_')[1],type='ABSOLUTE' if t.startswith('ABS') else 'PAIRED_RELATIVE',BH_size=5,BH_q=.05,HAC_lag=14,ES_threshold=.2,positive_horizons=3,minimum_dates=100,minimum_active_rate=.8,minimum_block_dates=20,positive_blocks=3,maximum_block_share=.5,maximum_top5=.5,maximum_HHI=.1,maximum_leave5_ES_loss=.75,synthetic_only_certified=True,real_disposition_computed=False) for t in contract.TESTS])

def run(work_root):
 root=Path(work_root);ctx=json.loads((root/'job_inputs/swing10/execution_context.json').read_text())
 if os.environ.get('GITHUB_ACTIONS')!='true' or ctx.get('mwe_uuid')!=MWE or ctx.get('preflight_only') is not True or ctx.get('scientific_outcomes_authorized') is not False:raise ValueError('exact outcome-blind governed envelope required')
 snapshots=ctx.get('contract_snapshot',[])
 if len(snapshots)!=3 or {x['decision_id'] for x in snapshots}!=DECISIONS or any(x['metadata_json'].get('status')!='FROZEN' for x in snapshots):raise ValueError('three exact frozen snapshots required')
 supplement=next(x for x in snapshots if x['decision_id']=='8ef41b93-e42c-4b53-bcca-23c8f8eb3f4e')
 if supplement['metadata_json'].get('s3_outcome_execution_authorized') is not False:raise ValueError('S3P cannot expose outcomes')
 if len(ctx.get('materialized_inputs',[]))!=1:raise ValueError('one exact development input only')
 if not isinstance(ctx.get('github_job_id'),int) or ctx['github_job_id']<=0:raise ValueError('exact GitHub job identity required')
 guard_source(Path(__file__).read_text())
 blob=(root/'job_inputs/swing11/development.csv').read_bytes();frame=source.verified_input(blob)
 values,capacity,temporal,blocks=prepare(frame)
 semantic=pd.DataFrame([dict(check=k,passed=True,detail=v,input_id=ctx['materialized_inputs'][0]['input_id'],input_sha=source.SHA,input_bytes=source.SIZE,protected_access=False,real_outcomes_computed=False) for k,v in [('INPUT','fresh private materialization SHA/byte/44128row/112symbol/394date/OHLC integrity'),('SEMANTICS','PRICE/RV20 only;causal ddof1;average ranks;no imputation'),('CONTRACT','three live frozen decisions reconciled;synthetic-only outcome machinery'),('CAPACITY','common complete H15 calendar;NO_TRADE cash;no response calculations'),('GUARDS','future shifts/outcome primitives/protected source rejected'),('S3_BOUNDARY','real candidate outcomes/selection/protected validation remain denied')]])
 tables={FILES[0]:registry(),FILES[1]:values,FILES[2]:capacity,FILES[3]:temporal,FILES[4]:advancement_registry(),FILES[5]:semantic}
 out=root/'research_outputs/swing11/s3p';out.mkdir(parents=True,exist_ok=True);paths=[];metadata={};decl=[]
 def save(name,blob,compress=False):
  stored=gzip.compress(blob,mtime=0) if compress else blob;physical=name+'.gz' if compress else name
  target=out/physical;target.write_bytes(stored);rel=str(target.relative_to(root));paths.append(rel)
  meta=dict(logical_name=name,logical_sha256=hashlib.sha256(blob).hexdigest(),logical_size_bytes=len(blob),storage_encoding='gzip' if compress else 'identity',stored_sha256=hashlib.sha256(stored).hexdigest(),stored_size_bytes=len(stored))
  metadata[rel]=meta;decl.append(meta)
 for name,df in tables.items():
  if set(df.columns)!=set(SCHEMAS[name]):raise ValueError('preflight schema mismatch')
  save(name,df[list(SCHEMAS[name])].to_csv(index=False).encode(),name==FILES[1])
 execution=dict(complete_decisions=snapshots,candidates=list(contract.CANDIDATES),horizons=list(contract.HORIZONS),test_registry=list(contract.TESTS),preflight_schemas=SCHEMAS,future_scientific_schemas=contract.FUTURE_SCHEMAS,sole_future_primary='sw11_s3_candidate_primary_summary.csv',synthetic_sensitivities=list(contract.SENSITIVITIES),comparison_calendar=sorted(capacity.decision_date.unique()),blocks=blocks,return_execution_disabled=True,real_dispositions_disabled=True,sample_role='DEVELOPMENT_PREVIOUSLY_USED_SWING10_S2_S3_SWING11_S2',input=ctx['materialized_inputs'][0],no_trade_cash=True,rank_scope='original full finite cross-section;C2 score rank on joint eligibility',reference_only_horizon=20,reference_outcome_not_computed=True)
 save(FILES[6],(json.dumps(execution,sort_keys=True,indent=2)+'\n').encode())
 manifest=dict(execution=ctx,artifact_declarations=decl,schemas=SCHEMAS,real_s3_outcomes_exposed=False,protected_data_access=False,S4_S5_S6_authorized=False,cost=dict(executor='governed GitHub Actions',paid_fallback=False,billing_evidence_available=False),parent_evidence_preserved=True)
 save(FILES[7],(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode())
 if len(paths)!=8:raise ValueError('eight frozen preflight artifacts')
 return dict(status='PASS',artifact=paths[6],output_paths=paths,output_artifact_metadata=metadata)
