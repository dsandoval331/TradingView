"""Frozen B4 liquidity discovery and supplemented two-stage market conditioning."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import uuid
import ast
import numpy as np
import pandas as pd
from tr_platform.research.swing10_causal_inputs import causal_factors
from tr_platform.research.swing10_s2_b4_preflight import (
    construct, fixed_blocks, verify_input, guard_source, PANEL_COLUMNS, INPUT_SHA, INPUT_BYTES,
)
from tr_platform.research.swing10_s2_b4_contract import (
    HORIZONS, LIQUIDITY, INTERACTIONS, PRIMARY, FAMILY, DIAGNOSTIC_ONLY, EXCLUDED,
    FILES, centered_rank, liquidity_membership, validate_family, disposition,
)

PROTOCOL='SW10_S2_B4_PROTOCOL_V1'
DECISION='d573293a-1a84-42ee-b5ec-9a3173c7bed7'
SUPPLEMENT='f3e81d1f-83e0-4c8d-a5be-6d48d85b9700'
SOURCE_FILES=('swing10_s2_b4.py','swing10_s2_b4_contract.py',
              'swing10_s2_b4_preflight.py','swing10_causal_inputs.py')

def require_frozen_decisions():
    hashes={
       'SW10_S2_B4_PROTOCOL_V1.persisted.json':'6204466003bda4cd479483622c7ed7134be06d6d062b861098e5ff76bc649c06',
       'SW10_S2_B4_PROTOCOL_V1_SUPPLEMENT_1.persisted.json':'bdaa390e7fc64f4dd5430082bf4a24ea1e7ed18d3343fbfcc08f3bd7ffdbaebf'}
    for name,expected in hashes.items():
        path=Path(__file__).parent/name
        if not path.exists():path=Path(__file__).parents[2]/'research_protocols/swing10'/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('frozen decision snapshot changed')
    return hashes

def scientific_source_guard(source):
    tree=ast.parse(source)
    imports={'__future__','hashlib','json','math','pathlib','uuid','ast','numpy','pandas',
             'tr_platform.research.swing10_causal_inputs','tr_platform.research.swing10_s2_b4_preflight',
             'tr_platform.research.swing10_s2_b4_contract'}
    for n in ast.walk(tree):
        if isinstance(n,ast.Import) and any(a.name not in imports for a in n.names):raise ValueError('unapproved data/source import')
        if isinstance(n,ast.ImportFrom) and n.module not in imports:raise ValueError('unapproved data/source import')
        if isinstance(n,ast.Call):
            name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
            if name in {'read_csv','read_sql','read_parquet','read_pickle','urlopen','eval','exec','__import__'}:raise ValueError('unapproved data read')
            if name in {'read_text','read_bytes','open','Path'}:
                for x in ast.walk(n):
                    if isinstance(x,ast.Constant) and isinstance(x.value,str) and any(s in x.value.lower() for s in
                        ('holdout','protected/','factor_causal_summary','factor_date_spreads','interaction_b3_summary','interaction_date_coefficients')):
                        raise ValueError('protected or prior scientific artifact read')

def certify_future_invariance(panel,original):
    cutoff=sorted(panel.trade_date.unique())[197]
    changed=panel.copy();mask=changed.trade_date>cutoff
    changed.loc[mask,['open','high','low','close']]*=1.37;changed.loc[mask,'volume']*=2
    new=predictors(changed)
    for name in original[0]:
        a=original[0][name];b=new[0][name]
        pd.testing.assert_frame_equal(a[a.trade_date<=cutoff],b[b.trade_date<=cutoff],check_exact=True)
    pd.testing.assert_frame_equal(original[1][original[1].trade_date<=cutoff],new[1][new[1].trade_date<=cutoff],check_exact=True)
    for name in original[2]:
        pd.testing.assert_frame_equal(original[2][name].loc[:cutoff],new[2][name].loc[:cutoff],check_exact=True)

def standardize_state(series):
    """Only finite eligible history strictly before t; no fills."""
    s=series.sort_index().astype(float)
    finite=s.where(np.isfinite(s))
    past=finite.shift(1)
    mu=past.expanding(min_periods=20).mean()
    sd=past.expanding(min_periods=20).std(ddof=1)
    valid=np.isfinite(finite)&np.isfinite(mu)&np.isfinite(sd)&sd.gt(1e-12)
    z=((finite-mu)/sd).where(valid)
    return pd.DataFrame({'raw_state':s,'prior_count':past.expanding().count(),
                         'prior_mean':mu,'prior_sample_sd':sd,'standardized_state':z})

def forward_returns(panel):
    if tuple(panel.columns)!=PANEL_COLUMNS:raise ValueError('exact immutable panel schema required')
    z=panel.sort_values(['symbol','trade_date'],kind='stable').copy()
    if z.duplicated(['symbol','trade_date']).any():raise ValueError('duplicate panel keys')
    for h in HORIZONS:z[f'forward_{h}']=z.groupby('symbol').close.shift(-h)/z.close-1
    return z[['symbol','trade_date']+[f'forward_{h}' for h in HORIZONS]]

def slope_fit(x,y):
    x=np.asarray(x,float);y=np.asarray(y,float)
    if len(x)!=len(y) or len(x)<3 or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('finite identifiable slope requires at least three observations')
    c=x-x.mean();den=float(c@c)
    if den<=0:raise ValueError('rank-deficient slope design')
    weights=c/den;slope=float(weights@y);intercept=float(y.mean()-slope*x.mean())
    residual=y-intercept-slope*x
    design=np.column_stack([np.ones(len(x)),x]);sing=np.linalg.svd(design,compute_uv=False)
    return slope,weights*y,{'intercept':intercept,'design_rank':2,
           'condition_number':float(sing[0]/sing[-1]),'residual_sum_squares':float(residual@residual),
           'max_predictor_leverage':float((1/len(x)+c*c/den).max())}

def hac_regression(x,y,h):
    """Unscaled OLS sandwich, Bartlett scores in trading-date order."""
    if h not in HORIZONS:raise ValueError('unfrozen horizon')
    x=np.asarray(x,float);y=np.asarray(y,float);n=len(y);lag=h-1
    if n<=lag+1:raise ValueError('insufficient trading dates for frozen HAC lag')
    coefficient,_,diag=slope_fit(x,y)
    X=np.column_stack([np.ones(n),x]);beta=np.array([diag['intercept'],coefficient])
    scores=X*(y-X@beta)[:,None];meat=scores.T@scores
    for k in range(1,lag+1):
        cross=scores[k:].T@scores[:-k]
        meat+=(1-k/(lag+1))*(cross+cross.T)
    bread=np.linalg.inv(X.T@X);variance=(bread@meat@bread)[1,1]
    se=math.sqrt(max(float(variance),0.))
    return inference(coefficient,se,y,h),diag

def inference(coefficient,se,values,h):
    values=np.asarray(values,float);sd=float(values.std(ddof=1));t=coefficient/se if se else np.nan
    return {'eligible_dates':len(values),'primary_estimate':float(coefficient),
            'date_quantity_mean':float(values.mean()),'date_quantity_median':float(np.median(values)),
            'date_quantity_sample_sd':sd,'standardized_effect':coefficient/sd if sd else np.nan,
            'hac_lag':h-1,'hac_se':se,'hac_t':t,
            'p_raw':math.erfc(abs(t)/math.sqrt(2)) if np.isfinite(t) else np.nan,
            'ci95_low':coefficient-1.959963984540054*se,'ci95_high':coefficient+1.959963984540054*se}

def hac_mean(values,h):
    x=np.asarray(values,float);n=len(x);lag=h-1
    if h not in HORIZONS or not np.isfinite(x).all() or n<=lag+1:raise ValueError('invalid date spread series')
    u=x-x.mean();meat=float(u@u)
    for k in range(1,lag+1):meat+=2*(1-k/(lag+1))*float(u[k:]@u[:-k])
    return inference(float(x.mean()),math.sqrt(max(meat/(n*n),0.)),x,h)

def bh_adjust(pvalues):
    validate_family(tuple(pvalues))
    if any(not np.isfinite(p) or not 0<=p<=1 for p in pvalues.values()):
        raise ValueError('all 60 frozen primary raw p-values must be finite; fail closed')
    ordered=sorted(FAMILY,key=lambda k:pvalues[k]);running=1.;out={}
    for rank in range(60,0,-1):
        key=ordered[rank-1];running=min(running,pvalues[key]*60/rank);out[key]=running
    return out

def predictors(panel):
    """Freeze predictors, ranks and calendars before constructing outcomes."""
    values,_=construct(panel)
    f=causal_factors(panel)[['symbol','trade_date','RET_MOM','SHORT_REV']].copy()
    for name in ('RET_MOM','SHORT_REV'):
        f[name]=f.groupby('trade_date')[name].transform(lambda x:centered_rank(x).to_numpy())
    states={name:standardize_state(values[name].set_index('trade_date').value)
            for name in ('MARKET_SPY_TREND10','MARKET_PANEL_BREADTH10','MARKET_PANEL_DISPERSION10')}
    return values,f,states,fixed_blocks(panel.trade_date)

def primary_from_data(data,market,h):
    if market:return hac_regression([d['z'] for d in data],[d['quantity'] for d in data],h)[0]
    return hac_mean([d['quantity'] for d in data],h)

def refit_without(data,removed,market,h):
    refit=[]
    for d in data:
        keep=np.array([s not in removed for s in d['symbols']]);q=dict(d)
        if market:q['quantity']=slope_fit(d['x'][keep],d['y'][keep])[0]
        else:
            hi=d['high']&keep;lo=d['low']&keep
            if not hi.any() or not lo.any():raise ValueError('unavailable leave-out tails')
            q['quantity']=float(d['y'][hi].mean()-d['y'][lo].mean())
        refit.append(q)
    return primary_from_data(refit,market,h)['primary_estimate']

def concentration(data,market,h,full):
    if not data:raise ValueError('no additive symbol diagnostics')
    if market:
        z=np.array([d['z'] for d in data]);c=z-z.mean();date_weights=c/float(c@c)
    else:date_weights=np.full(len(data),1/len(data))
    totals={};counts={}
    for weight,d in zip(date_weights,data):
        for symbol,value in zip(d['symbols'],d['contributions']):
            totals[symbol]=totals.get(symbol,0.)+float(weight*value);counts[symbol]=counts.get(symbol,0)+1
    if not np.isclose(sum(totals.values()),full,rtol=1e-8,atol=1e-12):raise ValueError('non-additive symbol accounting')
    order=sorted(totals,key=lambda s:(-abs(totals[s]),s));den=sum(abs(v) for v in totals.values())
    removed=set(order[:5]);available=bool(den>0 and len(order)>=5)
    try:left=refit_without(data,removed,market,h)
    except ValueError:left=np.nan;available=False
    available=available and np.isfinite(left)
    reversal=bool(np.isfinite(left) and left*full<0)
    rows=[{'symbol':s,'eligible_symbol_dates':counts[s],'contribution_rank':i+1,
           'additive_primary_contribution':totals[s],'absolute_contribution_share':abs(totals[s])/den if den else np.nan,
           'removed_leave_top5':s in removed} for i,s in enumerate(order)]
    return rows,{'distinct_symbols':len(order),'additive_symbol_sum':sum(totals.values()),
       **{f'top{k}_absolute_share':sum(abs(totals[s]) for s in order[:k])/den if den else np.nan for k in (1,5,10)},
       'contribution_hhi':sum((v/den)**2 for v in totals.values()) if den else np.nan,
       'removed_top5_symbols':'|'.join(order[:5]),'leave_top5_primary_estimate':left,
       'leave_top5_sign_reversal':reversal,'symbol_diagnostics_available':bool(available),
       'symbol_sign_robustness':bool(available and not reversal)}

def temporal(data,market,h,full,mapping):
    rows=[]
    for block in range(1,5):
        local=[d for d in data if mapping[d['date']]==block]
        try:estimate=primary_from_data(local,market,h)['primary_estimate']
        except ValueError:estimate=np.nan
        rows.append({'block':block,'eligible_dates':len(local),'primary_estimate':estimate,
                     'aggregate_block_effect':estimate*len(local),
                     'same_nonzero_full_sign':bool(np.isfinite(estimate) and full!=0 and estimate*full>0)})
    available=all(np.isfinite(r['primary_estimate']) for r in rows)
    den=sum(abs(r['aggregate_block_effect']) for r in rows)
    available=bool(available and den>0)
    for r in rows:r['absolute_block_effect_share']=abs(r['aggregate_block_effect'])/den if available else np.nan
    same=sum(r['same_nonzero_full_sign'] for r in rows)
    maximum=max(r['absolute_block_effect_share'] for r in rows) if available else np.nan
    return rows,{'same_sign_blocks':same,'max_block_absolute_effect_share':maximum,
                 'temporal_sign_coherence':bool(available and same>=3),
                 'temporal_concentration_pass':bool(available and maximum<=.5),
                 'temporal_diagnostics_available':available}

def analyze(values,ranks,states,mapping,outcomes):
    summary=[];dates=[];temps=[];symbols=[];diagnostics=[]
    for label in PRIMARY:
        market=label in INTERACTIONS
        if market:
            factor,state=label.split(' x ')
            p=ranks[['symbol','trade_date',factor]].rename(columns={factor:'value'}).copy()
            p['z']=p.trade_date.map(states[state].standardized_state)
            p=p[np.isfinite(p[['value','z']]).all(axis=1)]
        else:p=values[label].copy()
        groups=list(p.merge(outcomes,on=['symbol','trade_date'],validate='one_to_one').groupby('trade_date',sort=True))
        for h in HORIZONS:
            data=[]
            for date,g in groups:
                # Membership/rank construction precedes outcome eligibility filtering.
                membership=None if market else liquidity_membership(g.value).to_numpy()
                valid=np.isfinite(g[f'forward_{h}']);v=g.loc[valid];y=v[f'forward_{h}'].to_numpy()
                if not len(v):continue
                if market:
                    try:q,contrib,diag=slope_fit(v.value.to_numpy(),y)
                    except ValueError:continue
                    datum={'date':date,'symbols':v.symbol.to_numpy(),'x':v.value.to_numpy(),'y':y,
                           'z':float(v.z.iloc[0]),'quantity':q,'contributions':contrib}
                    row={'hypothesis':label,'horizon_days':h,'trade_date':date,'temporal_block':mapping[date],
                         'eligible_symbols':len(v),'date_primary_quantity':q,'quantity_type':'stage1_slope',
                         'standardized_state':datum['z'],'stage1_intercept':diag['intercept']}
                    diagnostics.append({**row,'model_stage':'STAGE1','fit_status':'VALID',**diag})
                    diagnostics[-1].update(states[state].loc[date].to_dict())
                else:
                    low,high=membership[valid.to_numpy()].T
                    if not low.any() or not high.any():continue
                    weight=high/high.sum()-low/low.sum();contrib=weight*y;q=float(contrib.sum())
                    datum={'date':date,'symbols':v.symbol.to_numpy(),'y':y,'high':high,'low':low,
                           'quantity':q,'contributions':contrib}
                    row={'hypothesis':label,'horizon_days':h,'trade_date':date,'temporal_block':mapping[date],
                         'eligible_symbols':len(v),'date_primary_quantity':q,'quantity_type':'high_minus_low_spread',
                         'high_mean_return':float(y[high].mean()),'low_mean_return':float(y[low].mean()),
                         'high_count':int(high.sum()),'low_count':int(low.sum()),
                         'overlap_count':int((high&low).sum())}
                    diagnostics.append({**row,'model_stage':'LIQUIDITY','fit_status':'VALID',
                         'high_forward_sd':float(y[high].std(ddof=1)),'low_forward_sd':float(y[low].std(ddof=1)),
                         'high_positive_rate':float((y[high]>0).mean()),'low_positive_rate':float((y[low]>0).mean())})
                data.append(datum);dates.append(row)
            stats=primary_from_data(data,market,h)
            if not np.isfinite(stats['p_raw']) or not np.isfinite(stats['standardized_effect']):
                raise ValueError('required testability unavailable; no silent BH family substitution')
            tr,ts=temporal(data,market,h,stats['primary_estimate'],mapping)
            sr,ss=concentration(data,market,h,stats['primary_estimate'])
            if market:
                _,diag=hac_regression([d['z'] for d in data],[d['quantity'] for d in data],h)
                diagnostics.append({'hypothesis':label,'horizon_days':h,'model_stage':'STAGE2',
                                    'fit_status':'VALID',**stats,**diag})
            r={'hypothesis':label,'horizon_days':h,'design':'TWO_STAGE_MARKET_CONDITIONING' if market else 'LIQUIDITY_TAIL_SPREAD',
               'direction_registry':'NON_DIRECTIONAL_DISCOVERY','primary_family_tests':60,
               'eligible_symbol_date_observations':sum(len(d['symbols']) for d in data),
               'semantic_data_integrity_pass':True,**stats,**ts,**ss}
            summary.append(r);temps.extend({'hypothesis':label,'horizon_days':h,**x} for x in tr)
            symbols.extend({'hypothesis':label,'horizon_days':h,**x} for x in sr)
    adjusted=bh_adjust({(r['hypothesis'],r['horizon_days']):r['p_raw'] for r in summary})
    lookup={(r['hypothesis'],r['horizon_days']):r for r in summary}
    for r in summary:
        r['p_bh']=adjusted[r['hypothesis'],r['horizon_days']];r['fdr_pass']=r['p_bh']<=.05
        r['material_effect_pass']=abs(r['standardized_effect'])>=.20
        i=HORIZONS.index(r['horizon_days']);neighbors=[HORIZONS[j] for j in (i-1,i+1) if 0<=j<len(HORIZONS)]
        r['adjacent_horizon_coherence']=any(lookup[r['hypothesis'],h]['primary_estimate']*r['primary_estimate']>0 for h in neighbors)
        robust=all(r[k] for k in ('adjacent_horizon_coherence','temporal_sign_coherence','temporal_concentration_pass','symbol_sign_robustness'))
        r['disposition']=disposition(r['semantic_data_integrity_pass'],r['fdr_pass'],r['material_effect_pass'],robust)
        r['failed_gates']='|'.join(k for k in ('semantic_data_integrity_pass','fdr_pass','material_effect_pass',
            'adjacent_horizon_coherence','temporal_sign_coherence','temporal_concentration_pass','symbol_sign_robustness') if not r[k])
    return {FILES[0]:pd.DataFrame(summary),FILES[1]:pd.DataFrame(dates),FILES[2]:pd.DataFrame(temps),
            FILES[3]:pd.DataFrame(symbols),FILES[4]:pd.DataFrame(diagnostics),
            FILES[5]:pd.DataFrame([{k:r[k] for k in ('hypothesis','horizon_days','disposition','failed_gates')} for r in summary])}

def run(work_root:Path):
    validate_family(FAMILY)
    decision_hashes=require_frozen_decisions()
    scientific_source_guard(Path(__file__).read_text())
    for name in ('swing10_s2_b4_preflight.py','swing10_causal_inputs.py'):
        guard_source((Path(__file__).parent/name).read_text())
    context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text())
    inp=context['materialized_inputs']
    if len(inp)!=1 or inp[0]['sha256']!=INPUT_SHA or inp[0]['size_bytes']!=INPUT_BYTES:
        raise ValueError('only the certified immutable panel may be read')
    panel=verify_input(work_root/'job_inputs/swing10/market_daily_history.csv')
    prepared=predictors(panel);certify_future_invariance(panel,prepared)
    values,ranks,states,mapping=prepared
    tables=analyze(values,ranks,states,mapping,forward_returns(panel))
    if tuple(tables)!=FILES[:-1] or len(tables[FILES[0]])!=60:raise ValueError('exact scientific contract required')
    out=work_root/'research_outputs/swing10/s2_b4';out.mkdir(parents=True,exist_ok=True)
    ids={name:str(uuid.uuid4()) for name in FILES};declared=[]
    for name,table in tables.items():
        path=out/name;table.to_csv(path,index=False,float_format='%.17g',lineterminator='\n');blob=path.read_bytes()
        declared.append({'artifact_id':ids[name],'name':name,'size_bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),
                         'object_path':f"artifacts/{context['job_id']}/{context['attempt_id']}/{name}"})
    calendar=[{'block':b,'start':str(min(d for d,k in mapping.items() if k==b))[:10],
               'end':str(max(d for d,k in mapping.items() if k==b))[:10],
               'input_dates':sum(k==b for k in mapping.values())} for b in range(1,5)]
    manifest={'protocol':PROTOCOL,'decision_id':DECISION,'supplement_decision_id':SUPPLEMENT,
       'mwe_id':'MWE-SW10-S2B4-001','execution':context,
       'frozen_decision_snapshot_hashes':decision_hashes,'production_future_data_invariance':True,
       'parent':{'mwe_id':'MWE-SW10-S2B4P-001','job_id':'e08314b5-4055-4f19-aa27-abf7b0ec4cbf',
                 'research_sha':'518fa8620d2090bdb92a3922ff8760604550f169','infrastructure_sha':'4e719a450a193b8d5e9702ffd59e35c9446fba7f','run_id':37034198077},
       'input':{'identity':'market_daily_history_2025-02-03_2026-08-27','sha256':INPUT_SHA,'size_bytes':INPUT_BYTES,
                'rows':44128,'symbols':112,'dates':394,'start':'2025-02-03','end':'2026-08-27','regenerated':False},
       'primary_hypotheses':PRIMARY,'horizons_days':HORIZONS,'primary_family':FAMILY,
       'diagnostic_only':DIAGNOSTIC_ONLY,'excluded_unavailable':EXCLUDED,
       'diagnostic_only_findings':{
           'REL_MARKET_10':'subtracts same-date SPY return from RET_MOM; no independent within-date ordering information',
           'LIQ_PRIOR20_ACTIVITY':'identical to certified causal VOL_TURN_V2_CAUSAL',
           'MARKET_SPY_VOL14':'SPY instance of existing certified causal VOL_REGIME; not a primary B4 test'},
       'representation':'same-date finite eligible average_rank/N; centered=2*pct_rank-1',
       'state_standardization':{'formula':'(X_t-mean(X_<t))/sample_sd(X_<t)','current_date_excluded':True,'minimum_prior_finite':20,'ddof':1,'sd_floor':1e-12,'no_fill':True},
       'liquidity':{'tails':'inclusive same-date p20/p80','estimand':'mean date-level HIGH-minus-LOW spread'},
       'market_model':{'stage1':'per-date forward_return ~ intercept + primary_rank','stage2':'stage1_slope ~ intercept + Z_t','estimand':'gamma_h'},
       'inference':{'unit':'trading_date','kernel':'Bartlett','estimator':'Newey-West HAC','lag':'horizon-1','ci':.95,'two_sided':True,'asymptotic_normal':True,'small_sample_multiplier':False},
       'multiple_testing':{'method':'Benjamini-Hochberg','q':.05,'family_tests':60,'single_joint_family':True},
       'standardized_effect':{'liquidity':'mean(spread)/sample_sd(spread)','market':'gamma/sample_sd(stage1_slope)','ddof':1,'abs_threshold':.20},
       'fixed_block_definitions':calendar,'blocks_fixed_before_outcomes':True,
       'temporal':{'market':'Stage1 fits restricted to each block; Stage2 refit within block; prospectively frozen Z retains strictly past full-history normalization',
                   'block_effect':'block_primary_estimate * block_eligible_dates','absolute_share':'abs(block_effect)/sum(abs(block_effect))','same_sign_required':3,'max_share':.5},
       'symbol':{'additive':'Stage1 centered-rank OLS contributions weighted by Stage2 centered-state OLS weights; liquidity tail contributions weighted by 1/date_count',
                 'ranking':'absolute additive contribution descending, symbol ascending ties','top':[1,5,10],'hhi':True,
                 'leave5':'remove selected symbols, refit Stage1 and Stage2; original causal ranks and normalized market states retained; all full eligible dates required',
                 'zero_is_reversal':False,'unavailable_fails_closed':True},
       'protected_data_access':False,'historical_earnings_used':False,'prior_scientific_outcome_artifacts_read':False,
       'source_file_hashes':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in SOURCE_FILES},
       'artifacts':declared,'manifest_identity':{'artifact_id':ids[FILES[-1]],'name':FILES[-1],'integrity':'external registration/readback; no recursive self-hash'},
       'cost':{'executor':'github_actions','runner':'ubuntu-latest','paid_compute_selected':False,'incremental_billing_verified':False},
       'limitations':['observational discovery, not causal identification or scientific promotion','adjusted OHLCV and SPY/panel proxies retain preflight limitations','no transaction costs or protected independent validation evaluated']}
    (out/FILES[-1]).write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    paths=[str((out/name).relative_to(work_root)) for name in FILES]
    return {'status':'PASS','artifact':paths[0],'output_paths':paths,'output_artifact_ids':{p:ids[n] for p,n in zip(paths,FILES)}}
