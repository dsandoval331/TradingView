"""Frozen S3 pure calculations; no file, network, control-plane or real-data entry point.
Only synthetic regression invokes these functions in S3P. Governed science is disabled.
"""
import math
import statistics
from tr_platform.research.swing10_s3_preparation import CAPS, ARCHITECTURES, SIDES

PARAMS={'TIME':(None,None),'BRACKET_1_1':(.01,.01),'BRACKET_2_1':(.02,.01),'BRACKET_2_2':(.02,.02),'TRAIL_2':(None,.02),'STRUCTURE_5':(None,.02)}

def bar_valid(b):
    try:
        o,h,l,c,v=(float(b[k]) for k in ('open','high','low','close','volume'))
        return all(math.isfinite(x) for x in (o,h,l,c,v)) and min(o,h,l,c)>0 and v>=0 and l<=min(o,c)<=max(o,c)<=h
    except (KeyError,ValueError,TypeError):return False

def event(side,architecture,cap,prior,bars,cost_bp=10,ordering='STOP_FIRST'):
    if side not in SIDES or architecture not in PARAMS or cap not in CAPS or cost_bp not in (0,10,25,50) or ordering not in ('STOP_FIRST','TARGET_FIRST'):raise ValueError('unregistered cell/scenario')
    if len(prior)<5 or len(bars)!=10 or not all(bar_valid(b) for b in prior[-5:]+bars):raise ValueError('common finite prior5/full10 required')
    direction=1 if side=='LONG_LOW' else -1
    entry=float(bars[0]['open']);target_frac,stop_frac=PARAMS[architecture]
    target=entry*(1+direction*target_frac) if target_frac else None
    stop=entry*(1-direction*stop_frac) if stop_frac else None
    best=entry;history=list(prior);completed=[];ambiguity=False;gap=False
    for day,b in enumerate(bars[:cap],1):
        if architecture=='STRUCTURE_5':
            level=min(float(x['low']) for x in history[-5:]) if direction==1 else max(float(x['high']) for x in history[-5:])
            stop=max(stop,level) if direction==1 else min(stop,level)
        o,h,l,c=(float(b[k]) for k in ('open','high','low','close'))
        hitstop=stop is not None and (o<=stop if direction==1 else o>=stop)
        hittarget=target is not None and (o>=target if direction==1 else o<=target)
        reason=None;fill=None
        if hitstop:reason='STOP_GAP';fill=o;gap=True
        elif hittarget:reason='TARGET_GAP';fill=target;gap=True
        else:
            hitstop=stop is not None and (l<=stop if direction==1 else h>=stop)
            hittarget=target is not None and (h>=target if direction==1 else l<=target)
            ambiguity=hitstop and hittarget
            if hitstop and (not hittarget or ordering=='STOP_FIRST'):reason='STOP';fill=stop
            elif hittarget:reason='TARGET';fill=target
        if reason is None and day==cap:reason='TIME';fill=c
        if reason:
            gross=direction*(fill-entry)/entry;net=gross-cost_bp/10000
            # Completed bars known before exit; exit-bar order unknown except opening gap.
            known=[0.0]+[direction*(float(x[k])-entry)/entry for x in completed for k in ('high','low')]+[direction*(o-entry)/entry,gross]
            possible=known+[direction*(x-entry)/entry for x in (h,l)]
            if reason=='TIME':known=possible
            return {'exit_reason':reason,'exit_price':fill,'held_sessions':day,'gross_return':gross,'net_return':net,'dailyized_net_return':net/day,'mfe_lower':max(known),'mfe_upper':max(known) if gap else max(possible),'mae_lower':min(known) if gap else min(possible),'mae_upper':min(known),'first_passage_day':day if reason!='TIME' else None,'time_to_target_days':day if reason.startswith('TARGET') else None,'ambiguous_bar':ambiguity,'gap_fill':gap,'data_status':'VALID','excursion_censored':not gap and reason!='TIME'}
        completed.append(b);history.append(b)
        if architecture=='TRAIL_2':
            best=max(best,c) if direction==1 else min(best,c)
            level=best*(1-direction*.02)
            stop=max(stop,level) if direction==1 else min(stop,level)
    raise AssertionError('forced exit missing')

def hac_mean(values,lag=9):
    if lag!=9:raise ValueError('frozen S3 lag9')
    x=[float(v) for v in values];n=len(x)
    if n<2 or not all(math.isfinite(v) for v in x):raise ValueError('finite series required')
    mean=statistics.mean(x);sd=statistics.stdev(x)
    if sd<=0:raise ValueError('standardized effect numerically unavailable')
    u=[v-mean for v in x]
    variance=sum(v*v for v in u)
    for k in range(1,min(lag,n-1)+1):variance+=2*(1-k/(lag+1))*sum(u[i]*u[i-k] for i in range(k,n))
    se=math.sqrt(max(0,variance))/n
    if se<=0:raise ValueError('HAC inference unavailable')
    return {'mean':mean,'median':statistics.median(x),'sample_sd':sd,'standardized_effect':mean/sd,'hac_se':se,'ci95_low':mean-1.959963984540054*se,'ci95_high':mean+1.959963984540054*se,'p_raw':math.erfc(abs(mean/se)/math.sqrt(2))}

def bh12(pvalues):
    if len(pvalues)!=12:raise ValueError('exact12 primary family')
    p=[1.0 if v is None else float(v) for v in pvalues]
    if any(not math.isfinite(v) or not 0<=v<=1 for v in p):raise ValueError('invalid p')
    order=sorted(range(12),key=lambda i:(p[i],i));q=[1.]*12;last=1.
    for rank in range(12,0,-1):
        i=order[rank-1];last=min(last,p[i]*12/rank);q[i]=last
    return q

def blocks(dates):
    if len(set(dates))!=len(dates) or dates!=sorted(dates):raise ValueError('unique chronological signal calendar')
    n=len(dates);base,remainder=divmod(n,4);out=[];i=0
    for k in range(4):
        size=base+(k<remainder);out.append(dates[i:i+size]);i+=size
    return out

def family(date_cap_symbol):
    """Mapping date -> cap -> symbol -> net dailyized event return; exact cells only."""
    values={};contributions={};cap_values={h:[] for h in CAPS}
    for date,caps in sorted(date_cap_symbol.items()):
        if set(caps)!=set(CAPS):raise ValueError('all3 caps required')
        common=set(caps[5])
        if not common or any(set(caps[h])!=common for h in CAPS):raise ValueError('common symbols across caps')
        percap=[]
        for h in CAPS:
            if not all(math.isfinite(float(v)) for v in caps[h].values()):raise ValueError('nonfinite outcome')
            m=statistics.mean(caps[h].values());percap.append(m);cap_values[h].append(m)
            for s,v in caps[h].items():contributions[s]=contributions.get(s,0)+v/(3*len(common)*len(date_cap_symbol))
        values[date]=statistics.mean(percap)
    return values,contributions,{h:statistics.mean(v) for h,v in cap_values.items()}

def concentration(date_cap_symbol,contributions,effect):
    order=sorted(contributions,key=lambda s:(-abs(contributions[s]),s));total=sum(abs(v) for v in contributions.values())
    shares={s:abs(contributions[s])/total if total else 0 for s in order}
    removed=set(order[:5]);filtered={d:{h:{s:v for s,v in c.items() if s not in removed} for h,c in caps.items()} for d,caps in date_cap_symbol.items()}
    try:after=statistics.mean(family(filtered)[0].values());available=True
    except (ValueError,statistics.StatisticsError):after=None;available=False
    reversal=after is not None and effect*after<0
    return {'top1':sum(shares[s] for s in order[:1]),'top5':sum(shares[s] for s in order[:5]),'top10':sum(shares[s] for s in order[:10]),'hhi':sum(v*v for v in shares.values()),'removed':sorted(removed),'shares':shares,'leave5_effect':after,'sign_reversal':reversal,'available':available,'pass':available and not reversal}

def temporal(values,fixed_blocks):
    rows=[]
    for k,dates in enumerate(fixed_blocks,1):
        x=[values[d] for d in dates if d in values]
        rows.append({'block':k,'N':len(x),'mean':statistics.mean(x) if x else None,'median':statistics.median(x) if x else None,'start':dates[0] if dates else None,'end':dates[-1] if dates else None})
    total=sum(abs(r['mean']*r['N']) for r in rows if r['mean'] is not None)
    for r in rows:r['effect_share']=abs(r['mean']*r['N'])/total if total and r['mean'] is not None else None
    passed=all(r['N']>0 for r in rows) and sum(r['mean']>0 for r in rows)>=3 and total>0 and max(r['effect_share'] for r in rows)<=.5
    return rows,passed

def disposition(testable,mean,es,q,robustness):
    if not testable:return 'NOT_TESTABLE'
    if not all(math.isfinite(v) for v in (mean,es,q)):return 'NOT_TESTABLE'
    if mean<=0 or es<.2 or q>.05:return 'NO_S4_SUPPORT'
    return 'ELIGIBLE_FOR_CANONICAL_S4_REVIEW' if all(v is True for v in robustness) else 'DEVELOPMENT_ONLY_WEAK'

def select_for_review(summaries):
    chosen={}
    for side in SIDES:
        eligible=[r for r in summaries if r['side']==side and r['disposition']=='ELIGIBLE_FOR_CANONICAL_S4_REVIEW']
        if eligible:chosen[side]=sorted(eligible,key=lambda r:(-r['ci95_low'],r['architecture_id']))[0]['architecture_id']
    return chosen

def execute_science(*args,**kwargs):
    raise RuntimeError('S3P cannot execute real outcomes; NEW separately authorized S3 scientific MWE required')

def build_synthetic_tables(cohorts,contract):
    """End-to-end prospective artifact calculation on labeled synthetic fixtures only.
    No real-data entry point is registered. A future science MWE must activate its
    own authorized boundary; S3P never imports this module during real-input audit.
    cohorts[signal_date][side][FIXTURE_symbol] = {'prior':5bars,'bars':10bars}.
    """
    if not cohorts or any(not s.startswith('FIXTURE_') for sides in cohorts.values() for rows in sides.values() for s in rows):raise ValueError('synthetic-only orchestration boundary')
    dates=sorted(cohorts);fixed_blocks=blocks(dates);schemas=contract['artifact_schemas']
    if len(schemas)!=10 or contract['primary_tests']!=12 or contract['candidate_cells']!=36:raise ValueError('frozen artifact/test grid drift')
    tables={name:[] for name in schemas if name.endswith('.csv')};summaries=[]
    rawpaths=tables['s3_event_paths.csv'];exits=tables['s3_event_exits.csv'];datemetrics=tables['s3_date_candidate_metrics.csv'];costs=tables['s3_cost_path_diagnostics.csv']
    archparams={a['id']:a for a in contract['architectures']}
    for side in SIDES:
        for architecture in ARCHITECTURES:
            capmap={};eventcount=0;event_index={}
            for cap in CAPS:
                candidate=f'{side}__{architecture}__CAP{cap}';a=archparams[architecture]
                tables['s3_candidate_registry.csv'].append(dict(candidate_id=candidate,side=side,architecture_id=architecture,cap_days=cap,factor_semantics='adjusted close_t',entry_definition='next-session adjusted open',target_fraction=a['profit_target'],stop_fraction=a['initial_stop'],trailing_definition=a['trailing'],cost_primary_bp=10,primary_family_id=f'{side}__{architecture}'))
                scenario_values={b:[] for b in (0,10,25,50)};target_first=[];event_records=[];full_mfe=[];full_mae=[];adverse_gaps=[]
                for date in dates:
                    rows=cohorts[date].get(side,{})
                    if not rows:raise ValueError('common side/date fixture cohorts required')
                    for symbol,record in sorted(rows.items()):
                        bars=record['bars'];entry=bars[0]['open'];result=event(side,architecture,cap,record['prior'],bars)
                        capmap.setdefault(date,{}).setdefault(cap,{})[symbol]=result['dailyized_net_return'];eventcount+=1;event_records.append(result)
                        direction=1 if side=='LONG_LOW' else -1
                        for day,b in enumerate(bars,1):rawpaths.append(dict(candidate_id=candidate,symbol=symbol,signal_date=date,entry_date=bars[0]['date'],entry_price=entry,path_day=day,session_date=b['date'],open=b['open'],high=b['high'],low=b['low'],close=b['close'],side_return=direction*(b['close']-entry)/entry,path_eligible=True,censor_reason='FULL10_DIAGNOSTIC_NOT_POST_EXIT_PNL' if day>result['held_sessions'] else 'DAILY_OHLC_ORDER_UNKNOWN'))
                        exitrow={k:result.get(k) for k in schemas['s3_event_exits.csv']}
                        exitrow.update(candidate_id=candidate,symbol=symbol,signal_date=date,exit_date=bars[result['held_sessions']-1]['date'])
                        exits.append(exitrow);event_index.setdefault((cap,date),[]).append(exitrow)
                        full_excursions=[0.]+[direction*(b[k]-entry)/entry for b in bars for k in ('high','low')]
                        full_mfe.append(max(full_excursions));full_mae.append(min(full_excursions))
                        adverse_gaps.append(min([0.]+[direction*(bars[k]['open']-bars[k-1]['close'])/entry for k in range(1,10)]))
                        for b in scenario_values:scenario_values[b].append(event(side,architecture,cap,record['prior'],bars,b)['dailyized_net_return'])
                        target_first.append(event(side,architecture,cap,record['prior'],bars,ordering='TARGET_FIRST')['dailyized_net_return'])
                for bp,values in scenario_values.items():costs.append(dict(candidate_id=candidate,cost_bp=bp,metric='mean_event_dailyized_net',value=statistics.mean(values),available=True,ordering_scenario='STOP_FIRST',reason='fixed diagnostic scenario; primary10bp'))
                costs.append(dict(candidate_id=candidate,cost_bp=10,metric='mean_event_dailyized_net',value=statistics.mean(target_first),available=True,ordering_scenario='TARGET_FIRST_DIAGNOSTIC',reason='never replaces primary'))
                for key in ('ambiguous_bar','gap_fill','held_sessions','gross_return','net_return','mfe_lower','mfe_upper','mae_lower','mae_upper'):
                    costs.append(dict(candidate_id=candidate,cost_bp=10,metric=key,value=statistics.mean(float(r[key]) for r in event_records),available=True,ordering_scenario='STOP_FIRST',reason='bounded/censored daily-bar path diagnostics'))
                extras={'full10_mfe_mean':statistics.mean(full_mfe),'full10_mae_mean':statistics.mean(full_mae),'worst_adverse_gap':min(adverse_gaps),'median_event_net_return':statistics.median(r['net_return'] for r in event_records),'positive_event_share':sum(r['net_return']>0 for r in event_records)/len(event_records)}
                for key in ('first_passage_day','time_to_target_days'):
                    finite=[r[key] for r in event_records if r[key] is not None];extras['mean_'+key]=statistics.mean(finite) if finite else None
                for metric,value in extras.items():costs.append(dict(candidate_id=candidate,cost_bp=10,metric=metric,value=value,available=value is not None,ordering_scenario='STOP_FIRST',reason='fixed path diagnostic; unavailable first passage remains censored'))
                for reason in ('STOP','STOP_GAP','TARGET','TARGET_GAP','TIME'):
                    costs.append(dict(candidate_id=candidate,cost_bp=10,metric='exit_frequency_'+reason,value=sum(r['exit_reason']==reason for r in event_records)/len(event_records),available=True,ordering_scenario='STOP_FIRST',reason='fixed exit-reason registry'))
            v,c,capmeans=family(capmap);temporal_rows,tp=temporal(v,fixed_blocks);effect=statistics.mean(v.values());conc=concentration(capmap,c,effect)
            try:infer=hac_mean(list(v.values()));testable=True
            except ValueError:infer={k:None for k in ('mean','median','sample_sd','standardized_effect','hac_se','ci95_low','ci95_high','p_raw')};testable=False
            summary=dict(side=side,architecture_id=architecture,testable=testable,eligible_dates=len(dates),eligible_events=eventcount,mean_family_dailyized=infer['mean'],median_family_dailyized=infer['median'],sample_sd=infer['sample_sd'],standardized_effect=infer['standardized_effect'],hac_se=infer['hac_se'],ci95_low=infer['ci95_low'],ci95_high=infer['ci95_high'],p_raw=infer['p_raw'],p_bh=None,cap5_mean=capmeans[5],cap7_mean=capmeans[7],cap10_mean=capmeans[10],cost_bp=10,temporal_pass=tp,concentration_pass=conc['pass'],horizon_pass=all(x>0 for x in capmeans.values()),disposition=None,rank=None,selected_for_canonical_review=False)
            summaries.append(summary)
            for r in temporal_rows:tables['s3_temporal_stability.csv'].append(dict(side=side,architecture_id=architecture,block=r['block'],start=r['start'],end=r['end'],N=r['N'],mean=r['mean'],median=r['median'],effect_share=r['effect_share'],direction_pass=r['mean'] is not None and r['mean']>0,available=r['N']>0))
            ordered=sorted(c,key=lambda s:(-abs(c[s]),s))
            for rank,symbol in enumerate(ordered,1):tables['s3_symbol_concentration.csv'].append(dict(side=side,architecture_id=architecture,symbol=symbol,contribution=c[symbol],absolute_share=conc['shares'][symbol],rank=rank,top5_removed=symbol in conc['removed'],leave5_effect=conc['leave5_effect'],sign_reversal=conc['sign_reversal'],available=conc['available']))
            for key in ('top1','top5','top10','hhi'):
                costs.append(dict(candidate_id=f'{side}__{architecture}__FAMILY',cost_bp=10,metric=key,value=conc[key],available=True,ordering_scenario='STOP_FIRST',reason='additive date-family symbol diagnostics'))
            for date in dates:
                for cap in CAPS:
                    events=event_index[(cap,date)]
                    datemetrics.append(dict(side=side,architecture_id=architecture,signal_date=date,cap_days=cap,eligible_symbols=len(events),mean_gross_total_return=statistics.mean(r['gross_return'] for r in events),mean_net_total_return=statistics.mean(r['net_return'] for r in events),mean_net_dailyized_return=statistics.mean(r['dailyized_net_return'] for r in events),family_dailyized_return=v[date]))
            # Explicit cohort index, never portfolio capital simulation.
            total=0.;peak=0.;drawdown=0.
            for date in dates:
                date_total=statistics.mean(r['mean_net_total_return'] for r in datemetrics if r['side']==side and r['architecture_id']==architecture and r['signal_date']==date)
                total+=date_total;peak=max(peak,total);drawdown=min(drawdown,total-peak)
            costs.append(dict(candidate_id=f'{side}__{architecture}__FAMILY',cost_bp=10,metric='cohort_index_max_drawdown',value=drawdown,available=True,ordering_scenario='STOP_FIRST',reason='additive cohort index; not self-financing portfolio'))
    for side in SIDES:
        for architecture in ARCHITECTURES:
            for cap in CAPS:
                base={r['signal_date']:r['mean_net_dailyized_return'] for r in datemetrics if r['side']==side and r['architecture_id']=='TIME' and r['cap_days']==cap}
                delta=[r['mean_net_dailyized_return']-base[r['signal_date']] for r in datemetrics if r['side']==side and r['architecture_id']==architecture and r['cap_days']==cap]
                costs.append(dict(candidate_id=f'{side}__{architecture}__CAP{cap}',cost_bp=10,metric='paired_dailyized_difference_to_TIME',value=statistics.mean(delta),available=True,ordering_scenario='STOP_FIRST',reason='paired diagnostic; never additional primary hypothesis'))
    q=bh12([r['p_raw'] for r in summaries])
    for r,adjusted in zip(summaries,q):
        r['p_bh']=adjusted;r['disposition']=disposition(r['testable'],r['mean_family_dailyized'] if r['testable'] else 0,r['standardized_effect'] if r['testable'] else 0,adjusted,[r['temporal_pass'],r['concentration_pass'],r['horizon_pass']])
    chosen=select_for_review(summaries)
    for side in SIDES:
        eligible=sorted([r for r in summaries if r['side']==side and r['disposition']=='ELIGIBLE_FOR_CANONICAL_S4_REVIEW'],key=lambda r:(-r['ci95_low'],r['architecture_id']))
        for rank,r in enumerate(eligible,1):r['rank']=rank
    for r in summaries:r['selected_for_canonical_review']=chosen.get(r['side'])==r['architecture_id']
    tables['s3_candidate_summary.csv']=summaries
    tables['s3_semantic_integrity.csv']=[dict(check_id='SYNTHETIC_ONLY_FULL_CONTRACT',pass_=True,reason='synthetic certification; no real scientific execution',input_uuid=None,input_sha256=None,input_bytes=None,B5_read=False,S5_read=False,future_information=False,unavailable_cells=sum(not r['testable'] for r in summaries))]
    tables['s3_semantic_integrity.csv'][0]['pass']=tables['s3_semantic_integrity.csv'][0].pop('pass_')
    tables['sw10_s3_manifest.json']={k:None for k in schemas['sw10_s3_manifest.json']}
    tables['sw10_s3_manifest.json'].update({'protocol_decision_ids':['21091322-b757-42e5-9918-dba46b2e1252'],'synthetic_only':True,'36_cell_registry':[r['candidate_id'] for r in tables['s3_candidate_registry.csv']],'12_test_family':[r['side']+'__'+r['architecture_id'] for r in summaries],'four_block_definitions':fixed_blocks,'cost_scenarios':[0,10,25,50],'protected_flags':{'B5_read':False,'S5_read':False},'S5_locked':True,'scientific_execution_authorized':False,'artifact_identities_hashes_bytes':'assigned only by separately authorized governed execution; no self-hash','eligibility_dates':dates,'development_consumed_boundary':'DEVELOPMENT_PREVIOUSLY_USED_S2','billing_evidence':'not available; synthetic certification only'})
    for name,rows in tables.items():
        if name.endswith('.csv') and any(set(row)!=set(schemas[name]) for row in rows):raise ValueError('exact frozen schema mismatch '+name)
    return tables
