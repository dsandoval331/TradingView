"""Frozen S2-B3 date-level interaction inference; no scientific promotion."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import uuid
import numpy as np
import pandas as pd
from tr_platform.research.swing10_causal_inputs import causal_factors
from tr_platform.research.swing10_s2_b3_preflight import (
    FACTORS, INTERACTIONS, PANEL_COLUMNS, INPUT_SHA, INPUT_BYTES, reject_columns, blocks, verify_input,
)
from tr_platform.research.swing10_s2_b3_continuous_preflight import (
    centered_ranks, design, continuous_source_guard, audit_factor_frame as predictor_audit,
)

PROTOCOL='SW10_S2_B3_PROTOCOL_V1'
DECISION='b60b0a56-75fb-4db1-b584-b6bf0eb819f0'
HORIZONS=(1,2,3,5,7,10)
FAMILY=tuple((f+' x '+c,h) for f,c in INTERACTIONS for h in HORIZONS)
FILES=('interaction_b3_summary.csv','interaction_date_coefficients.csv',
       'interaction_temporal_stability.csv','interaction_symbol_concentration.csv',
       'interaction_model_diagnostics.csv','interaction_b3_dispositions.csv','sw10_s2_b3_manifest.json')
SOURCE_FILES=('swing10_s2_b3.py','swing10_s2_b3_continuous_preflight.py',
              'swing10_s2_b3_preflight.py','swing10_causal_inputs.py')


def require_contract():
    expected=tuple((f+' x '+c,h) for c in ('VOL_REGIME','VOL_TURN_V2_CAUSAL','HIGH52','GAP_OVN')
                   for f in ('RET_MOM','SHORT_REV') for h in (1,2,3,5,7,10))
    if FAMILY!=expected or len(FAMILY)!=48 or HORIZONS!=(1,2,3,5,7,10):
        raise ValueError('frozen 48-test interaction/horizon contract violated')


def forward_returns(panel):
    reject_columns(panel,PANEL_COLUMNS)
    if panel.duplicated(['symbol','trade_date']).any():raise ValueError('duplicate symbol/date')
    d=panel.sort_values(['symbol','trade_date'],kind='stable').copy()
    g=d.groupby('symbol').close
    for h in HORIZONS:d[f'forward_{h}']=g.shift(-h)/d.close-1
    return d[['symbol','trade_date']+[f'forward_{h}' for h in HORIZONS]]


def hac_mean(values,horizon):
    if horizon not in HORIZONS:raise ValueError('unfrozen horizon')
    x=np.asarray(values,dtype=float);lag=horizon-1;n=len(x)
    if not np.isfinite(x).all() or n<=lag+1:raise ValueError('insufficient/nonfinite date coefficients')
    mean=float(x.mean());u=x-mean;meat=float(u@u)
    for k in range(1,lag+1):meat+=2*(1-k/(lag+1))*float(u[k:]@u[:-k])
    variance=max(meat/(n*n),0.);se=math.sqrt(variance)
    t=mean/se if se else float('nan')
    p=math.erfc(abs(t)/math.sqrt(2)) if se else float('nan')
    sd=float(x.std(ddof=1));es=mean/sd if sd else float('nan')
    return {'eligible_dates':n,'mean_beta_interaction':mean,'median_beta_interaction':float(np.median(x)),
            'sample_sd_beta_interaction':sd,'standardized_effect':es,'hac_lag':lag,'hac_se':se,
            'hac_t':t,'p_raw':p,'ci95_low':mean-1.959963984540054*se,'ci95_high':mean+1.959963984540054*se}


def bh_adjust(pvalues):
    require_contract()
    if set(pvalues)!=set(FAMILY):raise ValueError('exact 48-test primary BH family required')
    for value in pvalues.values():
        if np.isfinite(value) and not 0<=value<=1:raise ValueError('invalid p value')
    ordered=sorted(FAMILY,key=lambda k:pvalues[k] if np.isfinite(pvalues[k]) else 1.)
    result={};running=1.
    for rank in range(48,0,-1):
        key=ordered[rank-1];value=pvalues[key] if np.isfinite(pvalues[key]) else 1.
        running=min(running,value*48/rank)
        result[key]=running if np.isfinite(pvalues[key]) else float('nan')
    return result


def fit_date(matrix,response):
    X=np.asarray(matrix,dtype=float);y=np.asarray(response,dtype=float)
    if X.ndim!=2 or X.shape[1]!=4 or len(y)!=len(X) or not np.isfinite(X).all() or not np.isfinite(y).all():
        raise ValueError('exact finite four-column OLS design required')
    if len(X)<4 or not np.all(X[:,0]==1):raise ValueError('intercept/full design required')
    u,s,_=np.linalg.svd(X,full_matrices=False)
    rank=int((s>max(X.shape)*np.finfo(float).eps*s[0]).sum())
    if rank!=4:raise ValueError('rank deficient date design')
    beta=np.linalg.lstsq(X,y,rcond=None)[0]
    main=X[:,:3];residualized=X[:,3]-main@np.linalg.lstsq(main,X[:,3],rcond=None)[0]
    denominator=float(residualized@residualized)
    if denominator<=0:raise ValueError('undefined interaction weights')
    contributions=residualized/denominator*y
    if not np.isclose(contributions.sum(),beta[3],rtol=1e-9,atol=1e-12):
        raise ValueError('additive OLS decomposition failed')
    residual=y-X@beta;ss=float(residual@residual);total=float(np.square(y-y.mean()).sum())
    h=np.square(u).sum(axis=1)
    return beta,contributions,{'design_rank':rank,'condition_number':float(s[0]/s[-1]),
           'residual_sum_squares':ss,'cross_section_r_squared':1-ss/total if total else float('nan'),
           'predictor_leverage_max':float(h.max()),'observations':len(y)}


def temporal_stats(coefficients,mapping):
    values=np.asarray(coefficients.beta_interaction,dtype=float)
    sign=float(np.sign(values.mean())) if len(values) else 0.
    rows=[]
    for k in range(1,5):
        x=coefficients.loc[coefficients.trade_date.map(mapping)==k,'beta_interaction'].to_numpy()
        rows.append({'block':k,'eligible_dates':len(x),'mean_beta_interaction':float(x.mean()) if len(x) else float('nan'),
                     'median_beta_interaction':float(np.median(x)) if len(x) else float('nan'),
                     'aggregate_date_effect':float(x.sum()),'same_nonzero_full_sign':bool(len(x) and sign and np.sign(x.mean())==sign)})
    total=sum(abs(r['aggregate_date_effect']) for r in rows)
    for row in rows:row['absolute_block_effect_share']=abs(row['aggregate_date_effect'])/total if total else float('nan')
    available=all(r['eligible_dates']>0 for r in rows) and total>0
    share=max(r['absolute_block_effect_share'] for r in rows) if available else float('nan')
    same=sum(r['same_nonzero_full_sign'] for r in rows)
    return rows,{'same_sign_blocks':same,'max_block_absolute_effect_share':share,
                 'temporal_sign_coherence':bool(available and sign and same>=3),
                 'temporal_concentration_pass':bool(available and share<=.5),
                 'temporal_diagnostics_available':available}


def concentration_stats(date_data,full_mean):
    """Additive OLS coefficient accounting and frozen-rank leave-five refit."""
    totals={};counts={}
    for date,symbols,X,y,contributions in date_data:
        for symbol,value in zip(symbols,contributions):
            totals[symbol]=totals.get(symbol,0.)+float(value)
            counts[symbol]=counts.get(symbol,0)+1
    n=len(date_data);contribution={symbol:value/n for symbol,value in totals.items()} if n else {}
    if n and not np.isclose(sum(contribution.values()),full_mean,rtol=1e-8,atol=1e-12):
        raise ValueError('symbol contributions do not recover full mean beta_I')
    ranked=sorted(contribution,key=lambda symbol:(-abs(contribution[symbol]),symbol))
    denominator=sum(abs(value) for value in contribution.values())
    removed=set(ranked[:5]);left=[];failed=0
    for date,symbols,X,y,contributions in date_data:
        keep=np.array([s not in removed for s in symbols])
        try:beta,_,_=fit_date(X[keep],y[keep]);left.append(float(beta[3]))
        except ValueError:failed+=1
    mean=float(np.mean(left)) if left else float('nan')
    available=bool(n and denominator>0 and len(ranked)>=5 and failed==0 and len(left)==n and np.isfinite(mean))
    reversal=is_sign_reversal(full_mean,mean)
    top={k:sum(abs(contribution[s]) for s in ranked[:k])/denominator if denominator else float('nan') for k in (1,5,10)}
    rows=[{'symbol':symbol,'eligible_symbol_dates':counts[symbol],'absolute_contribution_rank':i+1,
           'mean_interaction_coefficient_contribution':contribution[symbol],
           'absolute_contribution_share':abs(contribution[symbol])/denominator if denominator else float('nan'),
           'removed_in_leave_top5':symbol in removed} for i,symbol in enumerate(ranked)]
    return rows,{'distinct_symbols':len(ranked),'additive_contribution_sum':sum(contribution.values()),
                 **{f'top{k}_absolute_contribution_share':top[k] for k in (1,5,10)},
                 'contribution_hhi':sum((abs(v)/denominator)**2 for v in contribution.values()) if denominator else float('nan'),
                 'removed_top5_symbols':'|'.join(ranked[:5]),'leave_top5_mean_beta_interaction':mean,
                 'leave_top5_eligible_dates':len(left),'leave_top5_failed_dates':failed,
                 'leave_top5_sign_reversal':reversal,'symbol_diagnostics_available':available,
                 'symbol_sign_robustness':bool(available and not reversal)}


def is_sign_reversal(full_mean,left_mean):
    return bool(np.isfinite(full_mean) and np.isfinite(left_mean) and full_mean*left_mean<0)


def disposition(row):
    if not row['semantic_data_integrity_pass']:return 'INVALID_SEMANTICS_NOT_TESTABLE'
    robust=all(row[k] for k in ('temporal_sign_coherence','temporal_concentration_pass','symbol_sign_robustness'))
    primary=int(row['fdr_pass'])+int(row['material_effect_pass'])
    return 'ADVANCE' if robust and primary==2 else 'WEAK_EVIDENCE' if robust and primary==1 else 'RETAIN_AS_COUNTEREVIDENCE'


def analyze(factors,outcomes,mappings):
    require_contract();reject_columns(factors,('symbol','trade_date')+FACTORS)
    reject_columns(outcomes,('symbol','trade_date')+tuple(f'forward_{h}' for h in HORIZONS))
    if outcomes.duplicated(['symbol','trade_date']).any():raise ValueError('duplicate outcome symbol/date')
    ranks=centered_ranks(factors)
    if set(mappings)!={f+' x '+c for f,c in INTERACTIONS}:raise ValueError('eight fixed predictor block maps required')
    if any(set(mapping.values())!={1,2,3,4} for mapping in mappings.values()):
        raise ValueError('four fixed chronological predictor blocks required')
    merged=ranks.merge(outcomes,on=['symbol','trade_date'],how='left',validate='one_to_one')
    summaries=[];date_rows=[];temporal_rows=[];symbol_rows=[];diagnostic_rows=[]
    for primary,conditioner in INTERACTIONS:
        label=primary+' x '+conditioner;mapping=mappings[label]
        z=merged[np.isfinite(merged[[primary,conditioner]]).all(axis=1)]
        groups=list(z.groupby('trade_date',sort=True))
        for h in HORIZONS:
            local=[];date_data=[];dropped=0
            for date,g in groups:
                if date not in mapping:continue
                valid=np.isfinite(g[f'forward_{h}']);v=g.loc[valid]
                X=design(v[primary],v[conditioner]);y=v[f'forward_{h}'].to_numpy()
                try:
                    beta,contributions,diag=fit_date(X,y)
                except ValueError as exc:
                    dropped+=1
                    diagnostic_rows.append({'interaction':label,'horizon_days':h,'trade_date':date,
                         'fit_status':'EXCLUDED','exclusion_reason':str(exc),'predictor_observations':len(g),
                         'outcome_eligible_observations':len(v)})
                    continue
                row={'interaction':label,'horizon_days':h,'trade_date':date,'temporal_block':mapping[date],
                     'observations':len(v),'beta_intercept':float(beta[0]),'beta_primary':float(beta[1]),
                     'beta_conditioner':float(beta[2]),'beta_interaction':float(beta[3])}
                local.append(row);date_data.append((date,v.symbol.to_numpy(),X,y,contributions))
                diagnostic_rows.append({'interaction':label,'horizon_days':h,'trade_date':date,'fit_status':'VALID',
                       'exclusion_reason':'','predictor_observations':len(g),'outcome_eligible_observations':len(v),**diag})
            ds=pd.DataFrame(local,columns=['interaction','horizon_days','trade_date','temporal_block','observations',
                                           'beta_intercept','beta_primary','beta_conditioner','beta_interaction'])
            try:
                stats=hac_mean(ds.beta_interaction.to_numpy(),h)
                testable=bool(np.isfinite(stats['p_raw']) and np.isfinite(stats['standardized_effect']))
            except ValueError:
                stats={k:float('nan') for k in ('mean_beta_interaction','median_beta_interaction','sample_sd_beta_interaction',
                        'standardized_effect','hac_se','hac_t','p_raw','ci95_low','ci95_high')}
                stats.update(eligible_dates=len(ds),hac_lag=h-1);testable=False
            tr,ts=temporal_stats(ds,mapping)
            sr,ss=concentration_stats(date_data,stats['mean_beta_interaction'])
            summary={'interaction':label,'horizon_days':h,'primary_family_tests':48,
                     'predictor_eligible_dates':len(mapping),'excluded_fit_dates':dropped,
                     'eligible_symbol_date_observations':int(ds.observations.sum()),**stats,**ts,**ss,
                     'semantic_data_integrity_pass':testable,
                     'semantic_failure_reason':'' if testable else 'UNAVAILABLE_HAC_OR_STANDARDIZED_EFFECT'}
            summaries.append(summary);date_rows.extend(local)
            temporal_rows.extend({'interaction':label,'horizon_days':h,**r} for r in tr)
            symbol_rows.extend({'interaction':label,'horizon_days':h,**r} for r in sr)
    adjusted=bh_adjust({(r['interaction'],r['horizon_days']):r['p_raw'] for r in summaries})
    for row in summaries:
        row['p_bh']=adjusted[row['interaction'],row['horizon_days']]
        row['fdr_pass']=bool(np.isfinite(row['p_bh']) and row['p_bh']<=.05)
        row['material_effect_pass']=bool(np.isfinite(row['standardized_effect']) and abs(row['standardized_effect'])>=.20)
        row['disposition']=disposition(row)
        row['failed_gates']='|'.join(k for k in ('semantic_data_integrity_pass','fdr_pass','material_effect_pass',
            'temporal_sign_coherence','temporal_concentration_pass','symbol_sign_robustness') if not row[k])
    disposition_fields=('interaction','horizon_days','disposition','failed_gates','semantic_data_integrity_pass',
                        'fdr_pass','material_effect_pass','temporal_sign_coherence','temporal_concentration_pass','symbol_sign_robustness')
    return {FILES[0]:pd.DataFrame(summaries),FILES[1]:pd.DataFrame(date_rows),FILES[2]:pd.DataFrame(temporal_rows),
            FILES[3]:pd.DataFrame(symbol_rows),FILES[4]:pd.DataFrame(diagnostic_rows),
            FILES[5]:pd.DataFrame([{k:r[k] for k in disposition_fields} for r in summaries])}


def audit_panel(panel):
    reject_columns(panel,PANEL_COLUMNS);require_contract()
    values=causal_factors(panel)[['symbol','trade_date']+list(FACTORS)]
    # Certify predictors and freeze calendars BEFORE constructing any outcome.
    pred,evidence=predictor_audit(values)
    summary=pred['continuous_interaction_preflight_summary.csv']
    if len(summary)!=8 or not summary.disposition.eq('FEASIBLE').all():
        raise ValueError('certified parent predictor feasibility mismatch')
    coverage=pred['continuous_interaction_coverage.csv']
    maps={label:dict(zip(g.trade_date,g.fixed_block.astype(int)))
          for label,g in coverage[coverage.eligible_date].groupby('interaction')}
    results=analyze(values,forward_returns(panel),maps)
    return results,evidence['block_definitions']


def run(work_root:Path):
    require_contract()
    for name in SOURCE_FILES[1:]:continuous_source_guard((Path(__file__).parent/name).read_text())
    context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text())
    inputs=context['materialized_inputs']
    if len(inputs)!=1 or inputs[0]['sha256']!=INPUT_SHA or inputs[0]['size_bytes']!=INPUT_BYTES:
        raise ValueError('B3 must materialize ONLY the certified immutable daily panel')
    panel=verify_input(work_root/'job_inputs/swing10/market_daily_history.csv')
    tables,calendar=audit_panel(panel)
    if len(tables)!=6 or len(tables[FILES[0]])!=48:raise ValueError('scientific artifact/family contract failure')
    out=work_root/'research_outputs/swing10/s2_b3';out.mkdir(parents=True,exist_ok=True)
    ids={name:str(uuid.uuid4()) for name in FILES};declared=[]
    for name,table in tables.items():
        file=out/name;table.to_csv(file,index=False,float_format='%.17g',lineterminator='\n');blob=file.read_bytes()
        declared.append({'artifact_id':ids[name],'name':name,'size_bytes':len(blob),
                         'sha256':hashlib.sha256(blob).hexdigest(),
                         'object_path':f"artifacts/{context['job_id']}/{context['attempt_id']}/{name}"})
    manifest={'protocol':PROTOCOL,'decision_id':DECISION,'mwe_id':'MWE-SW10-S2B3-001','execution':context,
       'parent':{'mwe_id':'MWE-SW10-S2B3CP-001','job_id':'0e7d6edc-2e4f-412d-947b-540fd6e105bd',
                 'research_sha':'bd1deb3afbec2b7c89be78f2a77e630a9fc9e66a','infrastructure_sha':'4ec18ae7eed4a4cb2a4b9d050894f3f21de35846','run_id':36969310710},
       'input':{'identity':'market_daily_history_2025-02-03_2026-08-27','sha256':INPUT_SHA,'size_bytes':INPUT_BYTES,
                'rows':44128,'symbols':112,'dates':394,'date_start':'2025-02-03','date_end':'2026-08-27','regenerated':False},
       'factor_semantics_revision':'b912f0c78d9593f2b8d866856217a389ce9baf68','factors':list(FACTORS),'legacy_excluded':True,
       'representation':'same-date own-factor finite eligible average_rank/N; 2*pct_rank-1; interaction product',
       'model':'date-level OLS with intercept, two main rank effects and rank interaction product',
       'primary_quantity':'beta_interaction','horizons_days':list(HORIZONS),
       'primary_family':[{'interaction':label,'horizon_days':h} for label,h in FAMILY],
       'inference':{'unit':'trading_date','estimator':'Newey-West HAC','kernel':'Bartlett','lag_rule':'horizon-1',
                    'two_sided':True,'distribution':'asymptotic normal','ci':.95,'small_sample_multiplier':False},
       'multiple_testing':{'method':'Benjamini-Hochberg','q':.05,'family_tests':48,'single_joint_family':True},
       'standardized_effect':{'formula':'mean(date_beta_I)/sample_sd(date_beta_I)','ddof':1,'abs_threshold':.20},
       'block_definitions':calendar,'blocks_fixed_before_outcome_construction':True,
       'temporal':{'same_nonzero_full_sign_blocks':3,'max_abs_block_sum_share':.5,
                   'share_formula':'abs(block_sum)/sum(abs(each_block_sum))'},
       'symbol_concentration':{'additive_formula':'residualized product weight times outcome, per-date; symbol sum/T',
         'absolute_shares':True,'top':[1,5,10],'hhi':True,'ranking':'absolute contribution descending; symbol ascending ties',
         'leave_top5':'original ranks/product retained; same four-column OLS refit; every full date required',
         'zero_is_sign_reversal':False,'unavailable_fails_closed':True},
       'disposition_rules':{'ADVANCE':'all primary, robustness and semantic gates pass',
         'WEAK_EVIDENCE':'valid, exactly one primary failure, all robustness gates pass',
         'RETAIN_AS_COUNTEREVIDENCE':'all other valid/testable cases',
         'INVALID_SEMANTICS_NOT_TESTABLE':'scientific-contract/semantic or inference testability failure'},
       'protected_data_access':False,'historical_earnings_used':False,'b2_outcome_artifacts_accessed':False,
       'scientific_outcomes_authorized_by':DECISION,'source_file_hashes':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in SOURCE_FILES},
       'artifacts':declared,'manifest_identity':{'artifact_id':ids[FILES[-1]],'name':FILES[-1],'sha_size_verification':'external registration/readback; no recursive self-hash'},
       'cost':{'executor':'github_actions','runner':'ubuntu-latest','paid_compute_selected':False,'incremental_billing_verified':False},
       'limitations':['mechanical evidence dispositions only; canonical promotion authority retained','observational cross-sectional design does not establish causation','no trading costs or out-of-sample protected holdout evaluated']}
    (out/FILES[-1]).write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    paths=[str((out/name).relative_to(work_root)) for name in FILES]
    return {'status':'PASS','artifact':paths[0],'output_paths':paths,'output_artifact_ids':{path:ids[name] for path,name in zip(paths,FILES)}}
