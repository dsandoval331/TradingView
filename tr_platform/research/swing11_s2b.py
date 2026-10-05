"""Frozen SWING11 S2-B science. Real compute only via authorized governed run.

Uses the unchanged S2-A predictor implementation and frozen rule functions.
Source materialization is limited to the single certified development object.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from tr_platform.research import swing11_s2a as p
from tr_platform.research import swing11_s2a_supplement as s

MWE="40b5af4a-557e-4fb4-90e6-76fc33a54ff8"
AUTH="3a960763-a1c2-42be-bebd-9adbe4ff9d58"
FILES=tuple(s.final_schemas())
SCHEMAS=s.final_schemas()
REGISTRY=s.final_registry()
COMPRESSED={"sw11_s2_date_effects.csv","sw11_s2_symbol_concentration.csv"}

def coefficient(x,y,index):
    """Certified full-rank QR and additive projection row; no pseudoinverse."""
    x=s.identify(x);y=np.asarray(y,float)
    if len(x)!=len(y) or not np.isfinite(y).all():raise ValueError("invalid response")
    q,r=np.linalg.qr(x,mode="reduced")
    row=np.linalg.solve(r.T,np.eye(x.shape[1])[:,index])@q.T
    c=row*y;b=float(np.linalg.solve(r,q.T@y)[index])
    if not np.isclose(c.sum(),b,rtol=1e-10,atol=1e-12):raise ValueError("additive contribution mismatch")
    return b,c

def prepare(frame):
    """Predictor/calendar eligibility and blocks fixed before any responses."""
    values=p.predictors(frame)
    dates=sorted(frame.trade_date.unique());symbols=sorted(frame.symbol.unique())
    def matrix(table,name):
        return table.pivot(index="trade_date",columns="symbol",values=name).reindex(index=dates,columns=symbols).to_numpy(float)
    close=matrix(frame,"close");ranks={k:matrix(values,k) for k in ("PRICE",*s.MECHANISMS)}
    cases={}
    for row in REGISTRY:
        h=row["horizon"];m=row["mechanism"];records=[]
        for t in range(len(dates)-h):
            mask=np.isfinite(ranks['PRICE'][t])&np.isfinite(close[t])&np.isfinite(close[t+h])&(close[t]>0)&(close[t+h]>0)
            if m:mask &= np.isfinite(ranks[m][t])
            price=ranks['PRICE'][t,mask]
            x0=np.column_stack([np.ones(len(price)),price]);designs=[x0]
            if m:
                mechanism=ranks[m][t,mask]
                designs += [np.column_stack([np.ones(len(price)),price,mechanism]),np.column_stack([np.ones(len(price)),price,mechanism,price*mechanism])]
            reason=None
            try:
                for x in designs:s.identify(x)
            except ValueError as e:reason=str(e)
            if len(price)>=4:records.append({'t':t,'date':dates[t],'mask':mask,'designs':designs,'identified':reason is None,'reason':reason})
        blocks=s.baseline_blocks([r['date'] for r in records])
        block_map={date:i+1 for i,b in enumerate(blocks) for date in b}
        for r in records:r['block']=block_map[r['date']]
        cases[row['test_id']]={'registry':row,'records':records,'blocks':blocks}
    return {'dates':dates,'symbols':symbols,'close':close,'cases':cases}

def estimate(record,close,horizon,family,anchor=1,keep=None):
    selected=np.flatnonzero(record['mask'])
    if keep is not None:
        retained=np.asarray([j for j,i in enumerate(selected) if i in keep],int)
        selected=selected[retained];designs=[x[retained] for x in record['designs']]
    else:designs=record['designs']
    if not record['identified']:raise ValueError(record['reason'])
    for x in designs:s.identify(x)
    t=record['t'];y=close[t+horizon,selected]/close[t,selected]-1
    b0,c0=coefficient(designs[0],y,1)
    if family=='BASELINE':return b0,b0,np.nan,np.nan,selected,c0
    b1,c1=coefficient(designs[1],y,1)
    if family=='ATTENUATION':return anchor*(b0-b1),b0,b1,np.nan,selected,anchor*(c0-c1)
    g,cg=coefficient(designs[2],y,3)
    return g,b0,b1,g,selected,cg

def descriptive(b0,b1):
    mask=np.isfinite(b0)&np.isfinite(b1)
    if not mask.any():return np.nan,np.nan,None
    a=float(np.asarray(b0)[mask].mean());b=float(np.asarray(b1)[mask].mean())
    return a,b,(1-abs(b)/abs(a) if np.isfinite(a) and abs(a)>s.EPS else None)

def summarize(values,h,family,b0,b1):
    stats=s.hac(values,h,family)
    a,b,atten=descriptive(np.asarray(b0),np.asarray(b1))
    if family=='ATTENUATION' and atten is None:stats={'testable':False,'reason':'MATCHED_BASELINE_NEAR_ZERO','raw_p':None,'bh_slot_p':1.}
    stats.update({'baseline_mean':a,'adjusted_mean':b,'ATTEN':atten})
    return stats

def analyze(frame, *, governed=False):
    if not governed and any(not str(x).startswith('SYNTHETIC_') for x in frame.symbol.unique()):
        raise ValueError('real science requires governed authorization')
    prep=prepare(frame);close=prep['close'];n_symbols=len(prep['symbols'])
    results={};date_rows=[];temporal=[];concentration=[]
    # Complete PRICE-only series establish one sign source per horizon first.
    for row in REGISTRY:
        key=row['test_id'];family=row['family'];h=row['horizon'];case=prep['cases'][key]
        anchor=1.;anchor_available=True
        if family=='ATTENUATION':
            base=results[f'BASELINE_PRICE_H{h}']['values'];finite=base[np.isfinite(base)]
            mean=float(finite.mean()) if len(finite) else np.nan
            anchor_available=np.isfinite(mean) and mean!=0
            anchor=float(np.sign(mean)) if anchor_available else np.nan
        values=[];b0=[];b1=[];contributions=[]
        for rec in case['records']:
            v=a=b=g=np.nan;c=np.zeros(n_symbols);reason=rec['reason']
            try:
                if not anchor_available:raise ValueError('complete PRICE-only baseline sign unavailable')
                v,a,b,g,selected,part=estimate(rec,close,h,family,anchor)
                c[selected]=part
            except ValueError as e:reason=str(e)
            values.append(v);b0.append(a);b1.append(b);contributions.append(c)
            date_rows.append({'test_id':key,'family':family,'mechanism':row['mechanism'],'horizon':h,'trade_date':rec['date'],'N_symbols':int(rec['mask'].sum()),'baseline_coefficient':a,'adjusted_coefficient':b,'interaction_coefficient':g,'baseline_family_sign':anchor if family=='ATTENUATION' else None,'paired_attenuation_difference':v if family=='ATTENUATION' else None,'identified':np.isfinite(v),'unavailable_reason':reason,'block':rec['block'],'sample_binding':row['sample_binding'],'baseline_family_test_id':f'BASELINE_PRICE_H{h}','baseline_family_sign_source':f'BASELINE_PRICE_H{h}' if family=='ATTENUATION' else None})
        values=np.asarray(values);b0=np.asarray(b0);b1=np.asarray(b1);finite=np.isfinite(values)
        stats=summarize(values,h,family,b0,b1)
        if not anchor_available:stats.update(testable=False,reason='BASELINE_SIGN',raw_p=None,bh_slot_p=1.)
        blocks=[]
        for block in range(1,5):
            eligible=np.asarray([r['block']==block for r in case['records']]);mask=eligible&finite
            z=values[mask];a,b,atten=descriptive(b0[mask],b1[mask]);mean=float(z.mean()) if len(z) else np.nan
            blocks.append({'available':bool(len(z)),'N':int(len(z)),'mean':mean,'ATTEN':atten})
            temporal.append({'test_id':key,'block':block,'start_date':case['blocks'][block-1][0] if case['blocks'][block-1] else None,'end_date':case['blocks'][block-1][-1] if case['blocks'][block-1] else None,'eligible_dates':int(eligible.sum()),'finite_dates':len(z),'mean':mean,'median':float(np.median(z)) if len(z) else None,'sign':np.sign(mean) if np.isfinite(mean) else None,'baseline_mean_matched':a,'adjusted_mean_matched':b,'descriptive_attenuation':atten,'direction_pass':bool(mean<0) if family=='BASELINE' else bool(mean>0 and atten is not None and atten>0) if family=='ATTENUATION' else bool(np.isfinite(mean) and mean*stats.get('mean',np.nan)>0),'absolute_contribution':abs(mean*len(z)) if len(z) else None,'available':bool(len(z))})
        these=temporal[-4:];total=sum(r['absolute_contribution'] or 0 for r in these)
        for r in these:r['absolute_contribution_share']=r['absolute_contribution']/total if total and r['absolute_contribution'] is not None else None
        temporal_pass=s.temporal_gate(family,stats.get('mean',np.nan),blocks)
        symbol_available=False;leave_stats={};leave_atten=None
        if finite.any():
            aggregate=np.asarray(contributions)[finite].mean(axis=0)
            if not np.isclose(aggregate.sum(),float(values[finite].mean()),rtol=1e-9,atol=1e-12):raise ValueError('symbol aggregate reconciliation')
            absolute=abs(aggregate);total=float(absolute.sum());order=sorted(range(n_symbols),key=lambda i:(-absolute[i],prep['symbols'][i]));removed=set(order[:5]);keep=set(range(n_symbols))-removed
            lv=[];la=[];lb=[]
            for rec,valid in zip(case['records'],finite):
                # Freeze complete scientific sample, refit original ranks, never rerank.
                if not valid:continue
                try:
                    v,a,b,_,_,_=estimate(rec,close,h,family,anchor,keep)
                except ValueError:v=a=b=np.nan
                lv.append(v);la.append(a);lb.append(b)
            leave_stats=summarize(np.asarray(lv),h,family,np.asarray(la),np.asarray(lb));leave_atten=leave_stats['ATTEN']
            symbol_available=total>0 and len(lv)==int(finite.sum()) and np.isfinite(lv).all() and leave_stats.get('testable',False)
            passed=symbol_available and s.concentration_gate(family,stats.get('mean'),leave_stats.get('mean'),stats.get('ES'),leave_stats.get('ES'),leave_atten)
            shares=absolute/total if total else np.zeros(n_symbols)
            for i,symbol in enumerate(prep['symbols']):
                concentration.append({'test_id':key,'symbol':symbol,'additive_contribution':aggregate[i],'absolute_contribution_share':shares[i] if total else None,'absolute_rank':order.index(i)+1,'top_five_removed':i in removed,'top1_share':shares[order[:1]].sum(),'top5_share':shares[order[:5]].sum(),'top10_share':shares[order[:10]].sum(),'hhi':float(shares@shares),'contribution_reconciled':True,'full_effect':stats.get('mean'),'leave5_effect':leave_stats.get('mean'),'full_standardized_effect':stats.get('ES'),'leave5_standardized_effect':leave_stats.get('ES'),'standardized_effect_attenuation':1-abs(leave_stats['ES'])/abs(stats['ES']) if leave_stats.get('ES') is not None and stats.get('ES') not in (None,0) else None,'leave5_sign_reversal':stats.get('mean',np.nan)*leave_stats.get('mean',np.nan)<0,'leave5_descriptive_attenuation':leave_atten,'available':symbol_available,'concentration_gate':bool(passed)})
        else:passed=False
        results[key]={'registry':row,'values':values,'stats':stats,'temporal':temporal_pass,'concentration':bool(passed),'robustness_available':symbol_available and all(b['available'] for b in blocks)}
    # Fixed separate families; unavailable slots remain p=1.
    for family,size in [('BASELINE',8),('ATTENUATION',48),('INTERACTION',48)]:
        records=[r for r in results.values() if r['registry']['family']==family]
        for r,q in zip(records,s.bh([r['stats']['raw_p'] for r in records],size)):
            r['q']=float(q);st=r['stats'];r['primary']=st.get('testable',False) and s.primary_gate(family,st.get('mean'),st.get('ES'),q,st['ATTEN'])
    for family in ['BASELINE','ATTENUATION','INTERACTION']:
        for mechanism in ([None] if family=='BASELINE' else s.MECHANISMS):
            rows=[r for r in results.values() if r['registry']['family']==family and r['registry']['mechanism']==mechanism]
            coherence=s.adjacency({r['registry']['horizon']:r['primary'] for r in rows})
            for r in rows:r['adjacency']=coherence[r['registry']['horizon']]
    primary=[]
    for key,r in results.items():
        row=r['registry'];st=r['stats'];family=row['family'];mean=st.get('mean');es=st.get('ES');v=r['values'];finite=v[np.isfinite(v)]
        direction=mean is not None and (mean<0 if family=='BASELINE' else mean>0 if family=='ATTENUATION' else mean!=0)
        material=es is not None and ((es>=.20 and st['ATTEN'] is not None and st['ATTEN']>=.25) if family=='ATTENUATION' else abs(es)>=.20)
        primary.append({'test_id':key,'family':family,'mechanism':row['mechanism'],'horizon':row['horizon'],'estimand':'PRICE coefficient' if family=='BASELINE' else 's_H*(matched baseline PRICE - adjusted PRICE)' if family=='ATTENUATION' else 'PRICE_rank*mechanism_rank coefficient','direction':'NEGATIVE' if family=='BASELINE' else 'POSITIVE' if family=='ATTENUATION' else 'NONZERO_TWO_SIDED','testable':st['testable'],'unavailable_reason':st.get('reason'),'N_dates':len(finite),'mean':mean,'median':st.get('median'),'sd_ddof1':st.get('sd'),'standardized_effect':es,'hac_lag':row['horizon']-1,'hac_se':st.get('hac_se'),'t_statistic':st.get('t'),'raw_p':st['raw_p'],'bh_p':r['q'],'bh_slot_p':st['bh_slot_p'],'bh_family_size':row['bh_family_size'],'ci_low':st.get('ci_low'),'ci_high':st.get('ci_high'),'direction_share':float(np.mean(finite<0)) if family=='BASELINE' and len(finite) else float(np.mean(finite>0)) if family=='ATTENUATION' and len(finite) else float(np.mean(finite*np.sign(mean)>0)) if mean is not None and len(finite) else None,'baseline_mean_matched':st['baseline_mean'],'adjusted_mean_matched':st['adjusted_mean'],'descriptive_attenuation':st['ATTEN'],'direction_gate':bool(direction),'fdr_gate':bool(st['testable'] and r['q']<=.05),'materiality_gate':bool(material),'temporal_gate':r['temporal'],'concentration_gate':r['concentration'],'adjacency_gate':r['adjacency'],'required_robustness_available':r['robustness_available'],'sample_binding':row['sample_binding'],'baseline_family_test_id':f"BASELINE_PRICE_H{row['horizon']}",'baseline_family_sign_source':row['sign_source'] if family=='ATTENUATION' else None})
    dispositions=[]
    for m in s.MECHANISMS:
        rows={}
        for h in s.HORIZONS:
            a=results[f'ATTENUATION_{m}_H{h}'];g=results[f'INTERACTION_{m}_H{h}'];b=results[f'BASELINE_PRICE_H{h}'];st=a['stats']
            rows[h]={'testable':st['testable'] or g['stats']['testable'],'interaction_primary':g['primary'],'interaction_temporal':g['temporal'],'interaction_concentration':g['concentration'],'interaction_mean':g['stats'].get('mean',0),'attenuation_primary':a['primary'],'attenuation_temporal':a['temporal'],'attenuation_concentration':a['concentration'],'baseline_primary':b['primary'],'attenuation_fdr':st['testable'] and a['q']<=.05,'interaction_fdr':g['stats']['testable'] and g['q']<=.05,'d_mean':st.get('mean',0),'d_ES':st.get('ES') if st.get('ES') is not None else -np.inf,'ATTEN':st['ATTEN'] if st['ATTEN'] is not None else np.nan}
        label,reason,hs=s.disposition(rows)
        # Retain explanatory evidence as secondary even when conditioning wins.
        explanatory=[h for h in s.HORIZONS if rows[h]['attenuation_primary'] and rows[h]['attenuation_temporal'] and rows[h]['attenuation_concentration'] and rows[h]['baseline_primary']]
        second=any(a in explanatory and b in explanatory for a,b in zip(s.HORIZONS,s.HORIZONS[1:]))
        dispositions.append({'mechanism':m,'disposition':label,'reason':reason,'qualifying_evidence_type':reason,'qualifying_horizons':json.dumps(hs),'secondary_supported_aspects':'EXPLANATORY_EVIDENCE' if label=='CONDITIONING_SUPPORTED' and second else '', 'failed_aspects_denied_to_S3':'All aspects failing their own frozen gates; S3 not authorized','testable_horizons':json.dumps([h for h in s.HORIZONS if rows[h]['testable']]),'protocol_ids':'pending execution authority'})
    return {'date_effects':pd.DataFrame(date_rows), 'primary':pd.DataFrame(primary),'temporal':pd.DataFrame(temporal),'concentration':pd.DataFrame(concentration),'dispositions':pd.DataFrame(dispositions),'preparation':prep}

def run(work_root):
    root=Path(work_root);context=json.loads((root/'job_inputs/swing10/execution_context.json').read_text())
    if os.environ.get('GITHUB_ACTIONS')!='true' or context.get('mwe_uuid')!=MWE or context.get('scientific_outcomes_authorized') is not True or context.get('authorization_decision_id')!=AUTH:raise ValueError('exact governed scientific authority required')
    snapshots=context.get('contract_snapshot',[]);ids={x['decision_id'] for x in snapshots}
    required={*p.DECISIONS,s.SUPPLEMENT,s.SUPPLEMENT_2,AUTH}
    if len(snapshots)!=6 or ids!=required or any(x['metadata_json'].get('status')!='FROZEN' for x in snapshots):raise ValueError('six complete frozen snapshots required')
    if len(context.get('materialized_inputs',[]))!=1:raise ValueError('one exact development dependency required')
    if not isinstance(context.get('github_job_id'),int) or context['github_job_id']<=0:raise ValueError('exact external GitHub job identity required before outcomes')
    frame=p.verified_input((root/'job_inputs/swing11/development.csv').read_bytes())
    # Byte/hash/structural/protected boundary verification precedes all responses.
    tables=analyze(frame,governed=True);tables['dispositions']['protocol_ids']=json.dumps(sorted(ids))
    semantic=pd.DataFrame([{'check':c,'scope':'S2-B','passed':True,'detail':d,'source_input_id':context['materialized_inputs'][0]['input_id'],'source_sha256':p.SHA,'source_bytes':p.SIZE,'protected_access':False,'scientific_execution_authorized':True} for c,d in [('IMMUTABLE_SOURCE','exact SHA/bytes,112 symbols,394 sessions,full valid panel'),('SEMANTICS','unchanged S2-A causal predictors and finite same-date average ranks'),('AUTHORITY','six frozen decisions verified live before input materialization'),('REGISTRY','8/48/48 fixed families, unavailable slots p=1'),('PROTECTED_DENIAL','only certified development; consumed B5/future validation denied'),('OUTCOME_EXPOSURE','authorized S2-B outcomes first computed in this governed attempt')]])
    mapping={'sw11_s2_primary_summary.csv':tables['primary'],'sw11_s2_date_effects.csv':tables['date_effects'],'sw11_s2_temporal_stability.csv':tables['temporal'],'sw11_s2_symbol_concentration.csv':tables['concentration'],'sw11_s2_predictor_semantic_audit.csv':semantic,'sw11_s2_mechanism_dispositions.csv':tables['dispositions']}
    out=root/'research_outputs/swing11/s2b';out.mkdir(parents=True,exist_ok=True);paths=[];metadata={};declarations=[]
    for name,df in mapping.items():
        if set(df.columns)!=set(SCHEMAS[name]):raise ValueError('frozen scientific schema mismatch '+name)
        df=df[SCHEMAS[name]];df.to_csv(out/name,index=False);blob=(out/name).read_bytes();stored=out/name
        if name in COMPRESSED:
            stored=out/(name+'.gz')
            with stored.open('wb') as f:
                with gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0) as z:z.write(blob)
        physical=stored.read_bytes();rel=str(stored.relative_to(root));paths.append(rel)
        meta={'logical_name':name,'logical_sha256':hashlib.sha256(blob).hexdigest(),'logical_size_bytes':len(blob),'storage_encoding':'gzip' if name in COMPRESSED else 'identity','stored_sha256':hashlib.sha256(physical).hexdigest(),'stored_size_bytes':len(physical)}
        metadata[rel]=meta;declarations.append({'name':name,**meta})
    manifest={'protocol_ids':sorted(ids),'complete_decision_snapshots':snapshots,'research_sha':context['research_revision'],'infrastructure_sha':context['infrastructure_revision'],'job_id':context['job_id'],'attempt_id':context['attempt_id'],'github_run_id':context['github_run_id'],'github_job_id':context['github_job_id'],'immutable_inputs':context['materialized_inputs'],'sample_role':'DEVELOPMENT_PREVIOUSLY_USED_SWING10_S2_S3','rank_scope':'finite same-date predictor before endpoint mask','matched_sample_rule':'identical PRICE/M/current/endpoint intersection for all matched models','baseline_family_case_registry':[r for r in REGISTRY if r['family']=='BASELINE'],'endpoint_rule':'adjusted_close(t+H)/adjusted_close(t)-1 exact registered sessions','coefficient_registry':REGISTRY,'bh_families':{'BASELINE':8,'ATTENUATION':48,'INTERACTION':48},'unavailable_slot_policy':'p=1, no shrinkage','hac':{'kernel':'Bartlett','lag':'H-1','reference':'two-sided asymptotic normal','CI':.95,'small_sample_multiplier':False},'standardized_effect':'mean coefficient / sampleSD ddof1; materiality0.20','attenuation':'paired d_t=s_H*(b0_t-b1_t); ATTEN=1-|meanb1|/|meanb0|','temporal_blocks':{k:v['blocks'] for k,v in tables['preparation']['cases'].items()},'symbol_rules':'additive date coefficient contributions; deterministic absolute top5 then symbol order; full refit fixed ranks/sample','adjacency':'immediately adjacent registered horizon primary gates','disposition_mapping':'frozen Supplement1 exact certified truth table','schemas':SCHEMAS,'artifacts_excluding_manifest_self_hash':declarations,'protected_data_access':False,'outcome_authorization':AUTH,'compute_cost_provenance':{'executor':'governed Github Actions','paid_fallback':False,'billing_evidence_available':False},'failures_recovery':{'attempt_no':context['attempt_no'],'prior_attempts_preserved':True},'baseline_family_sample_rule':'PRICE_ONLY; no mechanism eligibility','baseline_sign_anchor_rule':'complete PRICE-only baseline perH frozen shareds_H','baseline_blocks_rule':'own PRICE-only eligible dates eachH','baseline_leave5_rule':'fixed original sample/ranks and full PRICE-only refit','matched_comparison_separation':True,'scientific_outcomes_exposed':True,'S3_authorized':False}
    (out/'sw11_s2_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True,allow_nan=False)+'\n')
    paths.append(str((out/'sw11_s2_manifest.json').relative_to(root)))
    if len(paths)!=7 or len(tables['primary'])!=104 or len(tables['dispositions'])!=6:raise ValueError('exact scientific artifact/registry contract')
    return {'status':'PASS','artifact':str((out/'sw11_s2_primary_summary.csv').relative_to(root)),'output_paths':paths,'output_artifact_metadata':metadata}
