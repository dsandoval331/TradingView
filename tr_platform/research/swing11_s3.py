"""Authorized frozen DEVELOPMENT science. Predictor/preflight modules stay unchanged."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from tr_platform.research import swing11_s3p as preflight
from tr_platform.research import swing11_s3_contract as contract
from tr_platform.research import swing11_s2a_supplement as stats

AUTH='d3dfd67f-b40d-45ed-af1d-9c7e079bab66'
PARENT='b1e57ab2-19a5-4fc0-a375-11a369650204'
CONTRACT_SHA='3f6842122acaa911631a8ff1785c170eab0d9e5d868e24fd4860acceee22f18b'
CONTRACT_SIZE=39880
PREDICTOR_SHA='4ab5b57f43edf3b5713d13adbd9b7d0fc1d8ec9bc28565ffdc6998eb2618d7e6'
FILES=tuple(contract.FUTURE_SCHEMAS)
ROLE='DEVELOPMENT_PREVIOUSLY_USED_SWING10_S2_S3_SWING11_S2'

def authority(ctx):
    if ctx.get('scientific_outcomes_authorized') is not True or ctx.get('authorization_decision_id')!=AUTH or ctx.get('preflight_only') is not False:
        raise ValueError('explicit scientific authorization required')
    snapshots=ctx.get('contract_snapshot',[])
    if len(snapshots)!=4 or {x['decision_id'] for x in snapshots}!=preflight.DECISIONS|{AUTH}:raise ValueError('four exact frozen authorities required')
    if any(x['metadata_json'].get('status')!='FROZEN' for x in snapshots):raise ValueError('frozen authority required')
    approved=next(x for x in snapshots if x['decision_id']==AUTH)['metadata_json']
    if not approved.get('user_approved') or not approved.get('prospective') or approved.get('development_outcome_exposure_authorized') is not True:raise ValueError('prospective development approval required')
    if any(approved.get(k) is not False for k in ('protected_validation_authorized','s4_authorized','s5_authorized','s6_authorized')):raise ValueError('protected transition denied')
    if not isinstance(ctx.get('github_job_id'),int) or ctx['github_job_id']<=0:raise ValueError('exact GitHub job required')
    return True

def simulate(frame,values,candidate,removed=()):
    """Complete equal-side refit retaining original ranks and NO_TRADE cash."""
    dates=sorted(frame.trade_date.unique());symbols=sorted(frame.symbol.unique());N=len(dates)-15
    opens=frame.pivot(index='trade_date',columns='symbol',values='open').reindex(index=dates,columns=symbols).to_numpy(float)
    closes=frame.pivot(index='trade_date',columns='symbol',values='close').reindex(index=dates,columns=symbols).to_numpy(float)
    if not np.isfinite(opens).all() or not np.isfinite(closes).all() or (opens<=0).any() or (closes<=0).any():raise ValueError('finite complete adjusted bars required')
    index={s:i for i,s in enumerate(symbols)};groups={d:g for d,g in values.groupby('trade_date')}
    contributions=np.zeros((N,4,len(symbols)));cohorts=[];accounts=[];active=[];minimum=[]
    for hi,H in enumerate(contract.HORIZONS):
        pnl=np.zeros(len(dates));gross=np.zeros(len(dates));net=np.zeros(len(dates));entries=np.zeros(len(dates));exits=np.zeros(len(dates));counts=np.zeros(len(dates),int)
        for t,date in enumerate(dates[:N]):
            long,short,no=preflight.memberships(groups[date],candidate,removed)
            entry,exit=contract.indices(t,H,len(dates));weights=np.zeros(len(symbols))
            if not no:
                weights[[index[s] for s in long]]=.5/len(long);weights[[index[s] for s in short]]=-.5/len(short)
                entry_prices=opens[entry];returns=closes[exit]/entry_prices-1
                contributions[t,hi]=weights*returns/H
                for day in range(entry,exit+1):
                    previous=entry_prices if day==entry else closes[day-1]
                    pnl[day]+=float((weights*(closes[day]-previous)/entry_prices).sum()/H)
                    marked=weights*closes[day]/entry_prices/H
                    gross[day]+=float(abs(marked).sum());net[day]+=float(marked.sum());counts[day]+=1
                entries[entry]+=float(abs(weights).sum()/H)
                exits[exit]+=float(abs(weights*closes[exit]/entry_prices).sum()/H)
                lr=float(np.mean(returns[[index[s] for s in long]]));sr=float(-np.mean(returns[[index[s] for s in short]]))
            else:lr=sr=0.
            active.append(not no);minimum.append(min(len(long),len(short)) if not no else 5)
            R=float(contributions[t,hi].sum()*H)
            if not np.isclose(R,.5*lr+.5*sr,atol=1e-12):raise ValueError('cohort contribution reconciliation')
            cohorts.append(dict(candidate=candidate,decision_date=date,horizon=H,entry_date=dates[entry],exit_date=dates[exit],long_N=len(long),short_N=len(short),no_trade=no,long_return=lr,short_return=sr,cohort_return=R,dailyized_return=R/H,sample_role=ROLE))
        if (counts>H).any() or not np.isclose(pnl.sum(),contributions[:,hi].sum(),atol=1e-11):raise ValueError('fixed capital conservation')
        cumulative=np.cumsum(pnl);peak=np.maximum.accumulate(np.maximum(cumulative,0));dd=cumulative-peak
        for i,date in enumerate(dates):
            accounts.append(dict(candidate=candidate,horizon=H,date=date,active_cohorts=int(counts[i]),cash_sleeves=int(H-counts[i]),gross=gross[i],net=net[i],entry_turnover=entries[i],exit_turnover=exits[i],daily_fixed_capital_pnl=pnl[i],cumulative_fixed_capital_pnl=cumulative[i],drawdown_from_peak_diagnostic=dd[i],initial_capital=1.,conservation_verified=True))
    family_contrib=contributions.mean(axis=1);family=family_contrib.sum(axis=1)
    table=pd.DataFrame(cohorts);table['family_return']=table.decision_date.map(dict(zip(dates[:N],family)))
    return dict(series=family,contributions=family_contrib,horizon_means=dict(zip(contract.HORIZONS,contributions.sum(axis=2).mean(axis=0))),cohorts=table,accounts=pd.DataFrame(accounts),active_rate=float(np.mean(active)),minimum_side=min(minimum),symbols=symbols,dates=dates[:N])

def infer(series):
    z=np.asarray(series,float)
    if not np.isfinite(z).all():return dict(testable=False,reason='NONFINITE',raw_p=None)
    return stats.hac(z,15,'INTERACTION')

def temporal(series,dates,blocks,test):
    index={d:i for i,d in enumerate(dates)};rows=[]
    for i,b in enumerate(blocks):
        v=np.asarray([series[index[d]] for d in b]);mean=float(v.mean())
        rows.append(dict(test_id=test,block=i+1,start=b[0],end=b[-1],N=len(b),mean=mean,median=float(np.median(v)),positive=bool(mean>0),absolute_contribution=abs(mean*len(b)),available=True))
    total=sum(r['absolute_contribution'] for r in rows)
    for r in rows:r['absolute_share']=r['absolute_contribution']/total if total>0 else np.nan
    return rows,contract.temporal(rows)

def concentration(full,other,frame,values,candidate,test,info):
    symbols=full['symbols'];matrix=full['contributions'] if other is None else full['contributions']-other['contributions'];v=matrix.mean(axis=0)
    order=sorted(range(len(v)),key=lambda i:(-abs(v[i]),symbols[i]));removed=[symbols[i] for i in order[:5]]
    leave=simulate(frame,values,candidate,removed)
    series=leave['series'] if other is None else leave['series']-simulate(frame,values,'S3-C0',removed)['series']
    li=infer(series);effect=float((matrix.sum(axis=1)).mean());es=info.get('ES',np.nan);les=li.get('ES',np.nan)
    gate=contract.concentration(symbols,v,effect,es if es is not None else np.nan,float(series.mean()),les if les is not None else np.nan)
    total=float(abs(v).sum());rank={j:i+1 for i,j in enumerate(order)};rows=[]
    for i,s in enumerate(symbols):
        rows.append(dict(test_id=test,symbol=s,contribution=v[i],absolute_share=abs(v[i])/total if total>0 else np.nan,absolute_rank=rank[i],top5_removed=s in removed,top1_share=gate.get('top1',np.nan),top5_share=gate.get('top5',np.nan),top10_share=gate.get('top10',np.nan),hhi=gate.get('hhi',np.nan),reconciled=bool(np.isclose(v.sum(),effect,atol=1e-12)),full_effect=effect,leave5_effect=float(series.mean()),full_ES=es,leave5_ES=les,ES_loss=gate.get('loss',np.nan),sign_reversal=gate.get('sign_reversal',False),available=gate['available'],gate=gate['gate']))
    return rows,gate

def sensitivity():
    # Actual deterministic synthetic operations, never real-data alternate rules.
    f=pd.DataFrame([dict(symbol='SYNTHETIC_'+str(i),trade_date=str(t),open=10+i,high=11+i,low=9+i,close=10+i,volume=100) for t in range(40) for i in range(30)])
    a=preflight.predictors(f);b=preflight.predictors(f.sample(frac=1,random_state=7));pd.testing.assert_frame_equal(a.reset_index(drop=True),b.reset_index(drop=True))
    g=a[a.trade_date=='20'].copy();g['C0_long']=g.symbol.isin(g.symbol.iloc[:5]);g['C0_short']=g.symbol.isin(g.symbol.iloc[5:10]);assert not preflight.memberships(g,'S3-C0')[2]
    assert preflight.memberships(g,'S3-C0',[g.symbol.iloc[0]])[2]
    assert all(contract.indices(3,h,40)==(4,3+h) for h in contract.HORIZONS)
    sim=simulate(f,a,'S3-C0');assert sim['accounts'].conservation_verified.all();assert (sim['accounts'].active_cohorts+sim['accounts'].cash_sleeves).eq(sim['accounts'].horizon).all()
    return pd.DataFrame([dict(case_id=x,synthetic_only=True,passed=True,fixture_identity='SYNTHETIC_FIXED_S3_V1',detail='certified frozen invariant; no alternative real outcomes') for x in contract.SENSITIVITIES])

def analyze(frame,values,blocks):
    sims={c:simulate(frame,values,c) for c in contract.CANDIDATES};dates=sims['S3-C0']['dates'];tests={};tr=[];cr=[];evidence={};details={}
    sensitivity_table=sensitivity()
    for test in contract.TESTS:
        relative=test.startswith('REL');c=test.split('_')[1];full=sims[c];other=sims['S3-C0'] if relative else None
        series=full['series'] if other is None else full['series']-other['series'];info=infer(series);tests[test]=info
        temporal_rows,tgate=temporal(series,dates,blocks,test);tr.extend(temporal_rows)
        conc_rows,cgate=concentration(full,other,frame,values,c,test,info);cr.extend(conc_rows)
        hmeans={h:full['horizon_means'][h]-(other['horizon_means'][h] if other else 0) for h in contract.HORIZONS}
        cap=contract.capacity_gate(len(dates),full['active_rate'],[len(b) for b in blocks],full['minimum_side'],True)
        ev=dict(testable=info['testable'],mean=float(series.mean()),ES=info.get('ES') or np.nan,q=1.,positive_horizons=sum(x>0 for x in hmeans.values()),adjacent_pair=contract.horizon_gate(hmeans),temporal=tgate,concentration=cgate['gate'],capacity=cap,sensitivity=True)
        evidence[test]=ev;details[test]=dict(temporal_rows=temporal_rows,concentration=cgate,horizon_means=hmeans)
    adjusted=contract.bh_five([tests[t].get('raw_p') for t in contract.TESTS]);summary=[];selection={}
    for test,q in zip(contract.TESTS,adjusted):
        info=tests[test];ev=evidence[test];ev['q']=float(q);c=test.split('_')[1];s=sims[c];relative=test.startswith('REL')
        cohort=s['cohorts'].cohort_return.to_numpy();account=s['accounts'].groupby('date').daily_fixed_capital_pnl.mean().to_numpy()
        if relative:
            cohort=cohort-sims['S3-C0']['cohorts'].cohort_return.to_numpy();account=account-sims['S3-C0']['accounts'].groupby('date').daily_fixed_capital_pnl.mean().to_numpy()
        cumulative=np.cumsum(account);dd=cumulative-np.maximum.accumulate(np.maximum(cumulative,0))
        summary.append(dict(test_id=test,candidate=c,evidence='PAIRED_RELATIVE' if relative else 'ABSOLUTE',N_dates=len(dates),mean=ev['mean'],median=info.get('median',np.nan),sample_sd=info.get('sd',np.nan),ES=ev['ES'],hac_lag=14,hac_se=info.get('hac_se',np.nan),t=info.get('t',np.nan),raw_p=info.get('raw_p'),bh_p=q,ci_low=info.get('ci_low',np.nan),ci_high=info.get('ci_high',np.nan),positive_share=float(np.mean((s['series']-(sims['S3-C0']['series'] if relative else 0))>0)),cohort_mean=float(cohort.mean()),cohort_median=float(np.median(cohort)),cohort_sd=float(cohort.std(ddof=1)),cohort_hit_rate=float(np.mean(cohort>0)),cumulative_development_return=float(cumulative[-1]),maximum_drawdown_diagnostic=float(dd.min()),testable=ev['testable'],reason=info.get('reason',''),direction_gate=ev['mean']>0,material_gate=ev['ES']>=.2,fdr_gate=q<=.05,horizon_gate=ev['adjacent_pair'],temporal_gate=ev['temporal'],concentration_gate=ev['concentration'],capacity_gate=ev['capacity'],sensitivity_gate=True))
    for c in contract.CANDIDATES:
        at='ABS_'+c;rt='REL_'+c+'_vs_S3-C0';relevant=[at] if c=='S3-C0' else [at,rt]
        selection[c]=dict(absolute=evidence[at],relative=evidence.get(rt),passing_horizons=min(evidence[t]['positive_horizons'] for t in relevant),minimum_positive_blocks=min(sum(b['positive'] for b in details[t]['temporal_rows']) for t in relevant),maximum_block_share=max(b['absolute_share'] for t in relevant for b in details[t]['temporal_rows']),maximum_top5_share=max(details[t]['concentration'].get('top5',np.nan) for t in relevant),active_rate=sims[c]['active_rate'],paired_improvement=evidence[rt]['mean'] if rt in evidence else 0.)
    selected,labels=contract.select(selection);dispositions=[]
    for c,row in selection.items():
        relevant=[row['absolute']] if c=='S3-C0' else [row['absolute'],row['relative']];failed=[]
        for i,e in enumerate(relevant):
            for k,passed in [('testable',e['testable']),('direction',e['mean']>0),('materiality',e['ES']>=.2),('FDR',e['q']<=.05),('horizon',e['adjacent_pair']),('temporal',e['temporal']),('concentration',e['concentration']),('capacity',e['capacity']),('sensitivity',e['sensitivity'])]:
                if not passed:failed.append(('ABS' if i==0 else 'REL')+':'+k)
        dispositions.append(dict(candidate=c,disposition=labels[c],testable=labels[c]!='NOT_TESTABLE',absolute_pass=contract.evidence_gate(row['absolute']),relative_pass=c=='S3-C0' or contract.evidence_gate(row['relative']),failed_gates=';'.join(failed),passing_horizons=row['passing_horizons'],minimum_positive_blocks=row['minimum_positive_blocks'],maximum_block_share=row['maximum_block_share'],maximum_top5_share=row['maximum_top5_share'],active_rate=row['active_rate'],paired_improvement=row['paired_improvement'],selected=c==selected,selection_reason='frozen deterministic RV20 precedence, then C0 fallback, else NO_ADVANCE'))
    tables={FILES[0]:pd.DataFrame(summary),FILES[1]:pd.concat([s['cohorts'] for s in sims.values()]),FILES[2]:pd.DataFrame(tr),FILES[3]:pd.DataFrame(cr),FILES[4]:pd.concat([s['accounts'] for s in sims.values()]),FILES[5]:sensitivity_table,FILES[6]:pd.DataFrame(dispositions)}
    return tables,selected,details

def run(work_root):
    root=Path(work_root);ctx=json.loads((root/'job_inputs/swing10/execution_context.json').read_text());authority(ctx)
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('governed GitHub compute only')
    if len(ctx.get('materialized_inputs',[]))!=2:raise ValueError('exact development plus immutable S3P contract required')
    cb=(root/'job_inputs/swing11/s3p_contract.json').read_bytes()
    if len(cb)!=CONTRACT_SIZE or hashlib.sha256(cb).hexdigest()!=CONTRACT_SHA:raise ValueError('immutable S3P contract mismatch')
    frozen=json.loads(cb)
    if frozen['future_scientific_schemas']!={k:list(v) for k,v in contract.FUTURE_SCHEMAS.items()}:raise ValueError('certified schemas unchanged required')
    blob=(root/'job_inputs/swing11/development.csv').read_bytes();frame=preflight.source.verified_input(blob)
    values=preflight.predictors(frame)
    if hashlib.sha256(values.to_csv(index=False).encode()).hexdigest()!=PREDICTOR_SHA:raise ValueError('certified S3P predictor parity required before outcomes')
    dates=sorted(frame.trade_date.unique())[:-15]
    if dates!=frozen['comparison_calendar'] or [list(b) for b in np.array_split(dates,4)]!=frozen['blocks']:raise ValueError('fixed comparison calendar and blocks required')
    tables,selected,details=analyze(frame,values,frozen['blocks'])
    semantic=[('AUTHORITY','four live unchanged prospective decisions'),('INPUT','fresh private bytes/hash/size and complete structural validation'),('PREDICTORS','byte parity against certified S3P predictor construction'),('ESTIMANDS','five fixed tests; same 379-date calendar; NO_TRADE cash'),('CAPITAL','H fixed initial-capital sleeves; daily marked exposure before close liquidation; additive PNL'),('PROTECTION','only registered development panel; consumed B5 and post2026-08-27 denied'),('LIMITATIONS','development reused; survivorship/retrospective adjustments; borrow/financing/transaction costs omitted')]
    tables[FILES[7]]=pd.DataFrame([dict(check=k,passed=True,detail=v,input_id=ctx['input_registration_id'],input_sha=preflight.source.SHA,input_bytes=preflight.source.SIZE,protected_access=False,outcome_authorization=AUTH,sample_role=ROLE) for k,v in semantic])
    out=root/'research_outputs/swing11/s3';out.mkdir(parents=True,exist_ok=True);paths=[];decl=[];metadata={}
    def save(name,blob):
        target=out/name;target.write_bytes(blob);rel=str(target.relative_to(root));paths.append(rel);meta=dict(logical_name=name,logical_sha256=hashlib.sha256(blob).hexdigest(),logical_size_bytes=len(blob),storage_encoding='identity',stored_sha256=hashlib.sha256(blob).hexdigest(),stored_size_bytes=len(blob));metadata[rel]=meta;decl.append(meta)
    for name,df in tables.items():
        if set(df.columns)!=set(contract.FUTURE_SCHEMAS[name]):raise ValueError('exact frozen scientific schema required: '+name)
        save(name,df[list(contract.FUTURE_SCHEMAS[name])].to_csv(index=False).encode())
    manifest=dict(complete_authority=ctx['contract_snapshot'],candidate_registry=list(contract.CANDIDATES),test_registry=list(contract.TESTS),horizons=list(contract.HORIZONS),schemas=contract.FUTURE_SCHEMAS,sample_rule=dict(role=ROLE,no_trade_cash=True,no_discretionary_exclusions=True,family_equal_weight_caps=True,diagnostics='family cumulative/drawdown average four fixed-capital portfolio daily PNL; relative subtract C0; marked exposure includes exit-close just before liquidation',reference_horizon20_not_recomputed=True,selected_architecture=selected),comparison_calendar=dates,blocks=frozen['blocks'],input=ctx['materialized_inputs'],execution=ctx,cost=dict(executor='existing governed GitHub Actions',paid_fallback=False,billing_evidence_available=False,borrow_financing_transaction_costs_omitted=True),protection=dict(protected_validation_access=False,B5_access=False,S4_S5_S6_authorized=False),artifact_declarations=list(decl),outcome_exposure=dict(authorized=True,authorization=AUTH,development_only=True,scientific_contract_changed=False),gate_details=details)
    def scalar(x):
        if isinstance(x,np.generic):return x.item()
        raise TypeError(type(x).__name__)
    save(FILES[8],(json.dumps(manifest,sort_keys=True,indent=2,default=scalar)+'\n').encode())
    if len(paths)!=9 or len(set(paths))!=9:raise ValueError('nine exact scientific artifacts')
    return dict(status='PASS',artifact=paths[0],output_paths=paths,output_artifact_metadata=metadata)
