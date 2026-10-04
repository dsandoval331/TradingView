"""Frozen S3P private-byte/calendar/cohort audit. Never imports scientific engine."""
import ast
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import uuid
from tr_platform.research import swing10_s3_preparation as prep

DECISION='21091322-b757-42e5-9918-dba46b2e1252'
MWE='7d95c3a7-1c08-48a2-a865-3aa7eea8873a'
INPUT='131b6bd5-65d1-4dc7-a856-3300f73babcb'
PROTOCOL='SW10_S3_CANDIDATE_PROTOCOL_V1'
PROPOSAL_SHA='d4559d9d31fcb8a6d243d8e0342781fb228577196d528d1b835bf4bc33916904'
FILES=('s3_preflight_input_integrity.csv','s3_preflight_calendar_eligibility.csv','s3_preflight_cohort_coverage.csv','s3_preflight_symbol_participation.csv','s3_preflight_candidate_registry.csv','s3_preflight_protected_guards.csv','sw10_s3_preflight_manifest.json')
SCHEMAS={
FILES[0]:('check','passed','observed','expected'),
FILES[1]:('signal_date','prior5_capacity','next_entry_date','day10_endpoint_date','common_eligible','block'),
FILES[2]:('signal_date','side','eligible_symbols','tail_symbols','p20','p80','boundary_ties','overlap_symbols','candidate_cells','common_eligible'),
FILES[3]:('symbol','sessions','long_low_signals','short_high_signals','participation_share'),
FILES[4]:('candidate_id','side','architecture_id','cap_days','protocol_status','execution_authorized'),
FILES[5]:('check','passed','detail'),
}

def guard_source(source):
    tree=ast.parse(source)
    imports={'ast','csv','hashlib','io','json','math','pathlib','uuid','tr_platform.research'}
    banned={'shift','pct_change','forward_returns','event','hac_mean','bh12','family','concentration','temporal','select_for_review','read_sql','read_parquet','read_pickle','read_csv','eval','exec','compile','__import__','getattr','bfill','interpolate','post','urlopen'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import) and any(a.name not in imports for a in node.names):raise ValueError('unapproved import/outcome engine denied')
        if isinstance(node,ast.ImportFrom):
            if node.module not in imports or any('engine' in a.name or 'b5' in a.name for a in node.names):raise ValueError('scientific/protected import denied')
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
            if name in banned:raise ValueError('outcome/protected primitive denied')
    return True

def validate_freeze(snapshot,proposal):
    m=snapshot['metadata_json']
    if snapshot['decision_id']!=DECISION or m['decision_code']!=PROTOCOL or m['status']!='FROZEN' or m['user_approved'] is not True or m['prospective'] is not True:raise ValueError('frozen canonical authority required')
    if m['scientific_execution_authorized'] is not False or m['preflight_execution_authorized'] is not True or m['outcomes_computed_at_freeze'] is not False or m['outcomes_inspected_at_freeze'] is not False:raise ValueError('preflight-only prospective authorization')
    if m['frozen_contract']!=proposal:raise ValueError('unchanged complete proposal required')
    prep.validate_contract(proposal)
    return True

def decode_verified(blob):
    prep.opaque_bytes_verify(blob)
    reader=csv.DictReader(io.StringIO(blob.decode('utf-8')));prep.reject_outcome_columns(reader.fieldnames)
    panel={};symbols=set();rows=0
    for row in reader:
        symbol=row['symbol'];date=row['trade_date']
        if not symbol or not '2025-02-03'<=date<='2026-08-27':raise ValueError('protected/unknown source date')
        if symbol in panel.setdefault(date,{}):raise ValueError('duplicate symbol/date')
        values={k:float(row[k]) for k in ('open','high','low','close','volume')}
        if not all(math.isfinite(v) for v in values.values()):raise ValueError('nonfinite core')
        o,h,l,c,v=(values[k] for k in ('open','high','low','close','volume'))
        if min(o,h,l,c)<=0 or v<0 or not l<=min(o,c)<=max(o,c)<=h:raise ValueError('invalid OHLCV')
        panel[date][symbol]=values;symbols.add(symbol);rows+=1
    dates=sorted(panel)
    if (rows,len(symbols),len(dates),dates[0],dates[-1])!=(44128,112,394,'2025-02-03','2026-08-27') or any(set(p)!=symbols for p in panel.values()):raise ValueError('exact complete registered structure required')
    return panel,dates,sorted(symbols)

def coverage(panel,dates,symbols):
    # Future bars were validated structurally at decoding; never compute price changes.
    eligible=[d for d in dates if prep.common_date_eligibility(dates,d)]
    base,extra=divmod(len(eligible),4);blockmap={};cursor=0;definitions=[]
    for k in range(4):
        part=eligible[cursor:cursor+base+(k<extra)];cursor+=len(part)
        for d in part:blockmap[d]=k+1
        definitions.append({'block':k+1,'start':part[0] if part else None,'end':part[-1] if part else None,'dates':len(part)})
    calendar=[];cohorts=[];counts={s:[0,0] for s in symbols}
    for i,date in enumerate(dates):
        valid=date in blockmap
        calendar.append(dict(zip(SCHEMAS[FILES[1]],(date,i>=5,dates[i+1] if i+1<len(dates) else None,dates[i+10] if i+10<len(dates) else None,valid,blockmap.get(date)))))
        current=[(s,panel[date][s]['close']) for s in symbols]
        low,high=prep.tail_membership(current);p20=prep.quantile([v for s,v in current],.2);p80=prep.quantile([v for s,v in current],.8)
        for side,selected,j,boundary in (('LONG_LOW',low,0,p20),('SHORT_HIGH',high,1,p80)):
            cohorts.append(dict(zip(SCHEMAS[FILES[2]],(date,side,len(symbols),len(selected),p20,p80,sum(v==boundary for s,v in current),len(low&high),18,valid))))
            if valid:
                for s in selected:counts[s][j]+=1
    total=sum(sum(v) for v in counts.values())
    participation=[dict(zip(SCHEMAS[FILES[3]],(s,len(dates),*counts[s],sum(counts[s])/total if total else 0))) for s in symbols]
    return calendar,cohorts,participation,definitions

def run(work_root):
    work_root=Path(work_root);root=Path(__file__).resolve().parents[2]
    guard_source(Path(__file__).read_text())
    proposal_path=root/'research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.proposed.json'
    proposal_blob=proposal_path.read_bytes()
    if hashlib.sha256(proposal_blob).hexdigest()!=PROPOSAL_SHA:raise ValueError('frozen unchanged proposal byte drift')
    frozen_path=root/'research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.persisted.json'
    frozen=json.loads(frozen_path.read_text());validate_freeze(frozen,json.loads(proposal_blob))
    context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text())
    if context.get('mwe_uuid')!=MWE or context.get('protocol_decision_id')!=DECISION or context.get('scientific_outcomes_authorized') is not False or context.get('preflight_only') is not True:raise ValueError('exact outcome-blind envelope context required')
    items=context['materialized_inputs']
    if len(items)!=1 or items[0]['input_id']!=INPUT or items[0]['sha256']!=prep.DEVELOPMENT_SHA or items[0]['size_bytes']!=prep.DEVELOPMENT_BYTES or items[0]['object_path']!=prep.OBJECT:raise ValueError('only approved development object; B5/S5 denied')
    blob=(work_root/'job_inputs/swing10/s3_development_daily_history.csv').read_bytes()
    panel,dates,symbols=decode_verified(blob);calendar,cohorts,participation,fixed_blocks=coverage(panel,dates,symbols)
    checks=[('sha256',hashlib.sha256(blob).hexdigest(),prep.DEVELOPMENT_SHA),('bytes',len(blob),prep.DEVELOPMENT_BYTES),('rows',sum(len(p) for p in panel.values()),44128),('symbols',len(symbols),112),('dates',len(dates),394),('first_date',dates[0],'2025-02-03'),('last_date',dates[-1],'2026-08-27'),('duplicates',0,0),('null_nonfinite_invalid',0,0)]
    tables={FILES[0]:[dict(zip(SCHEMAS[FILES[0]],(k,v==e,v,e))) for k,v,e in checks],FILES[1]:calendar,FILES[2]:cohorts,FILES[3]:participation,FILES[4]:[{k:r[k] for k in ('candidate_id','side','architecture_id','cap_days')}|{'protocol_status':'FROZEN','execution_authorized':False} for r in prep.registry()],FILES[5]:[{'check':k,'passed':True,'detail':detail} for k,detail in [('B5_DENIED',prep.CONSUMED_B5_SHA+' not materialized/read'),('S5_DENIED','all dates after2026-08-27 rejected; no S5 dataset authorized'),('S6_LOCKED','no production or protected transition'),('REAL_SCIENCE_DISABLED','preflight never imports engine; no candidate outcome computation'),('SOURCE_GUARD','reviewed import/primitive whitelist'),('FROZEN_READBACK','unchanged complete proposal matches prospective decision')]]}
    out=work_root/'research_outputs/swing10/s3_preflight';out.mkdir(parents=True,exist_ok=True)
    ids={n:str(uuid.uuid4()) for n in FILES};declarations=[]
    for name in FILES[:-1]:
        path=out/name
        with path.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=SCHEMAS[name],lineterminator='\n');writer.writeheader();writer.writerows(tables[name])
        data=path.read_bytes();declarations.append({'name':name,'artifact_id':ids[name],'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'object_path':f"artifacts/{context['job_id']}/{context['attempt_id']}/{name}"})
    manifest={'protocol':PROTOCOL,'decision_id':DECISION,'approved_proposal_id':'831660de-f547-48e0-8742-fdfb7ad37a73','mwe_uuid':MWE,'execution':context,'input':items[0],'fresh_private_bytes_verified':True,'proposal_snapshot_sha256':PROPOSAL_SHA,'freeze_snapshot_sha256':hashlib.sha256(frozen_path.read_bytes()).hexdigest(),'role':'DEVELOPMENT_PREVIOUSLY_USED_S2','calendar':{'dates':len(dates),'common_signal_dates':sum(r['common_eligible'] for r in calendar),'blocks':fixed_blocks,'next_open_entry':True,'prior_completed_sessions':5,'endpoint_capacity':10},'registry_cells':36,'primary_future_tests':12,'preflight_schemas':SCHEMAS,'future_scientific_schemas':frozen['metadata_json']['frozen_contract']['artifact_schemas'],'outcomes_computed':False,'outcomes_inspected':False,'B5_read':False,'S5_read':False,'protected_access':False,'S6_locked':True,'scientific_execution_authorized':False,'cost':{'executor':'github_actions','paid_fallback':False,'billing_evidence_available':False},'artifacts':declarations,'manifest_identity':{'artifact_id':ids[FILES[-1]],'self_hash':'external registration; no recursion'},'limitations':['previously used S2 development; no untouched-validation claim','adjusted coordinates and daily OHLC; no executable intraday sequence or borrow claim','predictor/calendar coverage does not estimate candidate performance'],'next_state':'NEW_SEPARATELY_AUTHORIZED_S3_SCIENTIFIC_MWE_REQUIRED'}
    (out/FILES[-1]).write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return {'status':'PASS','artifact':str((out/FILES[0]).relative_to(work_root)),'output_paths':[str((out/n).relative_to(work_root)) for n in FILES],'output_artifact_ids':{str((out/n).relative_to(work_root)):ids[n] for n in FILES}}
