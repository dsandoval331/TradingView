"""Frozen B5 independent validation, only exact immutable B5A bytes."""
from __future__ import annotations
import ast
import hashlib
import json
import math
from pathlib import Path
import uuid
import numpy as np
import pandas as pd
from tr_platform.research.swing10_s2_b5_validation_contract import (
    CASES, KEYS, FILES, INPUT_SHA, INPUT_BYTES, INPUT_ID, PANEL_COLUMNS,
    PROTOCOL, BASE_DECISION, SUPPLEMENT_DECISION, SNAPSHOTS, SCHEMAS,
    MATERIAL, FDR, centered_rank, normalize_state, validate_cases,
    registered_neighbors, adjacency, direction_pass, disposition)
from tr_platform.research.swing10_s2_b5_preparation import four_blocks

def verify_decisions():
    root=Path(__file__).parents[2]/'research_protocols/swing10'
    for name,expected in SNAPSHOTS.items():
        p=Path(__file__).parent/name
        if not p.exists():p=root/name
        if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise ValueError('prospective frozen decision snapshot changed')
    return SNAPSHOTS

def source_guard(source):
    tree=ast.parse(source)
    allowed={'__future__','ast','hashlib','json','math','pathlib','uuid','numpy','pandas',
      'tr_platform.research.swing10_s2_b5_validation_contract',
      'tr_platform.research.swing10_s2_b5_preparation'}
    for n in ast.walk(tree):
        if isinstance(n,ast.Import) and any(a.name not in allowed for a in n.names):
            raise ValueError('unapproved source import')
        if isinstance(n,ast.ImportFrom) and n.module not in allowed:
            raise ValueError('unapproved source import')
        if isinstance(n,ast.Call):
            name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
            if name in {'read_sql','read_parquet','read_pickle','urlopen','eval','exec','__import__'}:
                raise ValueError('unapproved source access')
            for a in ast.walk(n):
                if isinstance(a,ast.Constant) and isinstance(a.value,str) and name in {'open','Path','read_text','read_bytes','read_csv'} and any(s in a.value.lower() for s in ('holdout','protected/','b4_scientific_summary','factor_causal_summary','interaction_b3_summary')):
                    raise ValueError('protected or prior outcome access')
    for fn in [n for n in tree.body if isinstance(n,ast.FunctionDef)]:
        for n in ast.walk(fn):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='read_csv' and fn.name!='verify_input':
                raise ValueError('unvalidated panel read')

def validate_panel(p,exact=False):
    if tuple(p.columns)!=PANEL_COLUMNS:raise ValueError('exact OHLCV schema required; outcome columns rejected')
    if p.isna().any().any() or p.duplicated(['symbol','trade_date']).any():raise ValueError('invalid keys/nulls')
    x=p[['open','high','low','close','volume']]
    if not np.isfinite(x).all().all() or (x[['open','high','low','close']]<=0).any().any() or (p.volume<0).any():raise ValueError('invalid finite prices/volume')
    if ((p.low>p.high)|(p.low>p[['open','close']].min(axis=1))|(p.high<p[['open','close']].max(axis=1))).any():raise ValueError('OHLC integrity')
    dates=set(p.trade_date)
    if set(p[p.symbol=='SPY'].trade_date)!=dates:raise ValueError('SPY exact dates required')
    if exact and (len(p)!=9296 or p.symbol.nunique()!=112 or len(dates)!=83 or not p.groupby('symbol').size().eq(83).all() or min(dates)!=pd.Timestamp('2024-10-02') or max(dates)!=pd.Timestamp('2025-01-31')):
        raise ValueError('certified coverage mismatch')

def verify_input(path):
    b=path.read_bytes()
    if len(b)!=INPUT_BYTES or hashlib.sha256(b).hexdigest()!=INPUT_SHA:raise ValueError('immutable input mismatch')
    p=pd.read_csv(path,parse_dates=['trade_date']);validate_panel(p,exact=True)
    return p

def predictors(panel):
    validate_panel(panel)
    p=panel.sort_values(['symbol','trade_date'],kind='stable').copy()
    p['RET_MOM']=p.close/p.groupby('symbol').close.shift(10)-1
    p['RET_MOM_rank']=p.groupby('trade_date').RET_MOM.transform(lambda s:centered_rank(s).to_numpy())
    spy=p[p.symbol=='SPY'].set_index('trade_date').RET_MOM
    p['market_z']=p.trade_date.map(pd.Series(normalize_state(spy.to_numpy()).to_numpy(),index=spy.index))
    return p

def future_invariance(panel,prepared):
    dates=sorted(panel.trade_date.unique());cut=dates[len(dates)//2]
    changed=panel.copy();mask=changed.trade_date>cut
    changed.loc[mask,['open','high','low','close']]*=1.23;changed.loc[mask,'volume']*=7
    got=predictors(changed)
    pd.testing.assert_frame_equal(prepared[prepared.trade_date<=cut],got[got.trade_date<=cut],check_exact=True)
    return True

def prepare_cases(p):
    """Freeze every case's eligible calendar/blocks from predictors and endpoint dates."""
    all_dates=sorted(p.trade_date.unique());prepared={}
    for family,h,direction,limited in CASES:
        market=family.startswith('RET_MOM')
        q=p[np.isfinite(p[['RET_MOM_rank','market_z']]).all(axis=1)] if market else p
        dates=[d for i,d in enumerate(all_dates) if i+h<len(all_dates) and all_dates[i+h]<pd.Timestamp('2025-02-03') and d in set(q.trade_date)]
        blocks=four_blocks(dates) if len(dates)>=4 else {}
        prepared[family,h]={'predictors':q[q.trade_date.isin(dates)].copy(),'dates':dates,'blocks':blocks}
    return prepared

def outcome(panel,h):
    if h not in {c[1] for c in CASES}:raise ValueError('unfrozen B5 return horizon')
    p=panel.sort_values(['symbol','trade_date'],kind='stable')
    y=p.groupby('symbol').close.shift(-h)/p.close-1
    return p[['symbol','trade_date']].assign(forward_return=y.to_numpy())

def slope_fit(x,y):
    x=np.asarray(x,float);y=np.asarray(y,float)
    if len(x)!=len(y) or len(x)<3 or not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('finite slope design requires >=3')
    c=x-x.mean();den=float(c@c)
    if den<=0:raise ValueError('rank deficient slope')
    w=c/den;coef=float(w@y)
    return coef,w*y,float(y.mean()-coef*x.mean())

def inference(coef,se,values,h):
    v=np.asarray(values,float);sd=float(v.std(ddof=1))
    if not np.isfinite(coef) or not np.isfinite(se) or se<=0 or not np.isfinite(sd) or sd<=0:
        raise ValueError('nonfinite/degenerate primary inference')
    t=coef/se
    return {'eligible_dates':len(v),'primary_estimate':float(coef),'date_effect_mean':float(v.mean()),
            'date_effect_median':float(np.median(v)),'date_effect_sample_sd':sd,
            'standardized_effect':coef/sd,'positive_date_share':float((v>0).mean()),
            'negative_date_share':float((v<0).mean()),'hac_lag':h-1,'hac_se':se,'hac_t':t,
            'p_raw':math.erfc(abs(t)/math.sqrt(2)),'ci95_low':coef-1.959963984540054*se,
            'ci95_high':coef+1.959963984540054*se}

def hac_mean(v,h):
    v=np.asarray(v,float);n=len(v);lag=h-1
    if n<=lag+1 or not np.isfinite(v).all():raise ValueError('insufficient dates for frozen HAC')
    u=v-v.mean();meat=float(u@u)
    for k in range(1,lag+1):meat+=2*(1-k/(lag+1))*float(u[k:]@u[:-k])
    return inference(float(v.mean()),math.sqrt(max(meat/n**2,0)),v,h)

def hac_regression(z,b,h):
    z=np.asarray(z,float);b=np.asarray(b,float);n=len(b);lag=h-1
    if n<=lag+1:raise ValueError('insufficient dates for frozen Stage2 HAC')
    coef,_,intercept=slope_fit(z,b);X=np.column_stack([np.ones(n),z]);res=b-intercept-coef*z
    score=X*res[:,None];meat=score.T@score
    for k in range(1,lag+1):
        cross=score[k:].T@score[:-k];meat+=(1-k/(lag+1))*(cross+cross.T)
    bread=np.linalg.inv(X.T@X);var=float((bread@meat@bread)[1,1])
    return inference(coef,math.sqrt(max(var,0)),b,h)

def primary(data,market,h):
    return hac_regression([d['z'] for d in data],[d['quantity'] for d in data],h) if market else hac_mean([d['quantity'] for d in data],h)

def bh_adjust(pvalues):
    validate_cases(tuple(pvalues))
    # Unavailable primary tests retain a conservative p=1 bookkeeping slot.
    # Their published raw/adjusted inference remains unavailable; family size stays9.
    values={k:float(p) if np.isfinite(p) else 1. for k,p in pvalues.items()}
    if any(not 0<=p<=1 for p in values.values()):raise ValueError('invalid p value')
    order=sorted(KEYS,key=lambda k:values[k]);out={};running=1.
    for i in range(9,0,-1):
        key=order[i-1];running=min(running,values[key]*9/i);out[key]=running
    return out

def refit_without(data,removed,market,h):
    result=[]
    for d in data:
        keep=np.array([s not in removed for s in d['symbols']]);q=dict(d)
        if market:q['quantity']=slope_fit(d['x'][keep],d['y'][keep])[0]
        else:
            lo=d['low']&keep;hi=d['high']&keep
            if not lo.any() or not hi.any():raise ValueError('missing retained tails')
            q['quantity']=float(d['y'][hi].mean()-d['y'][lo].mean())
        result.append(q)
    return primary(result,market,h)['primary_estimate']

def concentration(data,market,h,estimate):
    if not data:raise ValueError('no symbol contributions')
    if market:
        z=np.array([d['z'] for d in data]);c=z-z.mean();den=float(c@c)
        if den<=0:raise ValueError('Stage2 contribution geometry')
        date_weights=c/den
    else:date_weights=np.full(len(data),1/len(data))
    totals={};counts={}
    for w,d in zip(date_weights,data):
        for symbol,v in zip(d['symbols'],d['contributions']):
            totals[symbol]=totals.get(symbol,0)+float(w*v);counts[symbol]=counts.get(symbol,0)+1
    if not np.isclose(sum(totals.values()),estimate,rtol=1e-8,atol=1e-12):raise ValueError('symbol contributions do not reconcile')
    order=sorted(totals,key=lambda s:(-abs(totals[s]),s));den=sum(abs(v) for v in totals.values())
    if den<=0 or len(order)<5:raise ValueError('unavailable concentration')
    removed=set(order[:5])
    try:left=refit_without(data,removed,market,h)
    except ValueError:left=np.nan
    available=bool(np.isfinite(left));reversal=bool(available and left*estimate<0)
    rows=[{'symbol':s,'eligible_symbol_dates':counts[s],'contribution_rank':i+1,
      'additive_primary_contribution':totals[s],'absolute_contribution_share':abs(totals[s])/den,
      'removed_leave_top5':s in removed} for i,s in enumerate(order)]
    return rows,{'symbol_diagnostics_available':available,
      **{f'top{k}_absolute_share':sum(abs(totals[s]) for s in order[:k])/den for k in (1,5,10)},
      'contribution_hhi':sum((v/den)**2 for v in totals.values()),'removed_top5_symbols':'|'.join(order[:5]),
      'leave_top5_estimate':left,'leave_top5_sign_reversal':reversal,'symbol_sign_pass':available and not reversal}

def temporal(data,market,h,direction,mapping):
    rows=[]
    for block in range(1,5):
        local=[dict(d) for d in data if mapping[d['date']]==block];available=True;reason=''
        if market:
            for d in local:d['quantity']=slope_fit(d['x'],d['y'])[0]
        try:estimate=primary(local,market,h)['primary_estimate']
        except ValueError as e:estimate=np.nan;available=False;reason=str(e)
        vals=np.array([d['quantity'] for d in local])
        rows.append({'block':block,'start':str(min(d['date'] for d in local))[:10] if local else '',
          'end':str(max(d['date'] for d in local))[:10] if local else '','eligible_dates':len(local),
          'primary_estimate':estimate,'date_effect_mean':float(vals.mean()) if len(vals) else np.nan,
          'date_effect_median':float(np.median(vals)) if len(vals) else np.nan,
          'primary_sign':int(np.sign(estimate)) if np.isfinite(estimate) else np.nan,
          'required_direction_pass':bool(available and direction_pass(estimate,direction)),
          'absolute_block_effect':abs(estimate*len(local)),'diagnostic_available':available,'unavailable_reason':reason})
    available=all(r['diagnostic_available'] for r in rows)
    den=sum(r['absolute_block_effect'] for r in rows) if available else np.nan
    available=bool(available and np.isfinite(den) and den>0)
    for r in rows:r['absolute_block_share']=r['absolute_block_effect']/den if available else np.nan
    same=sum(r['required_direction_pass'] for r in rows);maxshare=max(r['absolute_block_share'] for r in rows) if available else np.nan
    return rows,{'same_direction_blocks':same,'max_absolute_block_share':maxshare,
      'temporal_direction_pass':bool(all(r['diagnostic_available'] for r in rows) and same>=3),
      'temporal_concentration_pass':bool(available and maxshare<=.5)}

def make_data(prepared,family,h,returns):
    market=family.startswith('RET_MOM');q=prepared['predictors'].merge(returns,on=['symbol','trade_date'],validate='one_to_one')
    data=[];rows=[]
    for date,g in q.groupby('trade_date',sort=True):
        g=g.sort_values('symbol');y=g.forward_return.to_numpy()
        if not np.isfinite(y).all():raise ValueError('complete frozen endpoint unavailable')
        sy=g.symbol.to_numpy();row={'trade_date':str(date)[:10],'temporal_block':prepared['blocks'][date],'eligible_symbols':len(g)}
        if market:
            x=g.RET_MOM_rank.to_numpy();coef,contrib,intercept=slope_fit(x,y)
            d={'date':date,'symbols':sy,'x':x,'y':y,'z':float(g.market_z.iloc[0]),'quantity':coef,'contributions':contrib}
            row.update(date_effect=coef,effect_type='STAGE1_SLOPE_DIAGNOSTIC',standardized_market_state=d['z'],stage1_intercept=intercept)
        else:
            v=g.close if family=='LIQ_ADJUSTED_PRICE' else g.volume
            lo=v.le(v.quantile(.2)).to_numpy();hi=v.ge(v.quantile(.8)).to_numpy()
            if not lo.any() or not hi.any():raise ValueError('unavailable inclusive tails')
            w=hi/hi.sum()-lo/lo.sum();coef=float(w@y)
            d={'date':date,'symbols':sy,'y':y,'low':lo,'high':hi,'quantity':coef,'contributions':w*y}
            row.update(date_effect=coef,effect_type='HIGH_MINUS_LOW_SPREAD',low_count=int(lo.sum()),high_count=int(hi.sum()),low_mean_return=float(y[lo].mean()),high_mean_return=float(y[hi].mean()),overlap_count=int((lo&hi).sum()))
        data.append(d);rows.append(row)
    return data,rows

def analyze(panel,p,prepared):
    # Predictor eligibility and all block maps have already been frozen.
    returns={h:outcome(panel,h) for h in sorted({c[1] for c in CASES})}
    summary=[];date_rows=[];temporal_rows=[];symbol_rows=[];audits=[]
    for family,h,direction,limited in CASES:
        common={'family':family,'horizon_days':h,'frozen_direction':direction,'limited_temporal_capacity':limited}
        market=family.startswith('RET_MOM');pc=prepared[family,h]
        r={**common,'testable':False,'testability_reason':'','primary_quantity_type':'STAGE2_GAMMA' if market else 'MEAN_TAIL_SPREAD',
          'eligible_dates':len(pc['dates']),'eligible_symbol_dates':len(pc['predictors'])}
        try:
            data,dr=make_data(pc,family,h,returns[h]);stats=primary(data,market,h);r.update(stats,testable=True)
            r['hypothesized_date_share']=stats['positive_date_share'] if direction=='POSITIVE' else stats['negative_date_share']
            date_rows.extend({**common,**x} for x in dr)
            tr,ts=temporal(data,market,h,direction,pc['blocks']);r.update(ts);temporal_rows.extend({**common,**x} for x in tr)
            try:sr,ss=concentration(data,market,h,stats['primary_estimate']);r.update(ss);symbol_rows.extend({**common,**x} for x in sr)
            except ValueError:r.update(symbol_diagnostics_available=False,symbol_sign_pass=False)
        except ValueError as e:r['testability_reason']=str(e);r.update(p_raw=np.nan,primary_estimate=np.nan,standardized_effect=np.nan)
        summary.append(r)
        audits.append({**common,'semantic_data_integrity_pass':True,'predictor_future_invariance':True,
          'input_sha256':INPUT_SHA,'input_bytes':INPUT_BYTES,'parent_input_id':INPUT_ID,
          'strict_endpoint_before':'2025-02-03','eligibility_dates':len(pc['dates']),
          'blocks_fixed_before_outcomes':True,'raw_p_available':r['testable'],
          'bh_unavailable_bookkeeping':'p=1 conservative slot in fixed9; published p unavailable' if not r['testable'] else 'none',
          'protected_data_access':False,'earnings_used':False,'reason':r['testability_reason']})
    bh=bh_adjust({(r['family'],r['horizon_days']):r['p_raw'] for r in summary})
    estimates={(r['family'],r['horizon_days']):r['primary_estimate'] for r in summary}
    for r in summary:
        family,h=r['family'],r['horizon_days'];testable=r['testable']
        r['p_bh']=bh[family,h] if testable else np.nan
        r['direction_pass']=testable and direction_pass(r['primary_estimate'],r['frozen_direction'])
        r['material_pass']=testable and abs(r['standardized_effect'])>=MATERIAL
        r['fdr_pass']=testable and r['p_bh']<=FDR
        ns=registered_neighbors(family,h);r['registered_adjacent_horizons']='|'.join(map(str,ns))
        r['adjacency_applicable']=bool(ns)
        r['adjacent_coherence_pass']=adjacency(family,h,estimates,r['primary_estimate']) if testable else False
        robust_keys=('temporal_direction_pass','temporal_concentration_pass','symbol_sign_pass','adjacent_coherence_pass')
        r['robustness_pass']=all(r.get(k,False) for k in robust_keys)
        r['disposition']=disposition(testable,r['direction_pass'],r['material_pass'],r['fdr_pass'],r['robustness_pass'])
        r['failed_gates']='|'.join(k for k in ('testable','direction_pass','material_pass','fdr_pass')+robust_keys if not r.get(k,False))
    data={FILES[0]:summary,FILES[1]:date_rows,FILES[2]:temporal_rows,FILES[3]:symbol_rows,FILES[4]:summary,FILES[5]:audits}
    return {name:pd.DataFrame(rows).reindex(columns=SCHEMAS[name]) for name,rows in data.items()}

def run(work_root):
    validate_cases(KEYS);verify_decisions();source_guard(Path(__file__).read_text())
    context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text())
    ins=context['materialized_inputs']
    if len(ins)!=1 or ins[0]['sha256']!=INPUT_SHA or ins[0]['size_bytes']!=INPUT_BYTES or context.get('parent_input_id')!=INPUT_ID or ins[0]['input_id']!=context.get('input_registration_id'):
        raise ValueError('only certified parent input UUID/hash/bytes allowed')
    panel=verify_input(work_root/'job_inputs/swing10/b5_independent_daily_history.csv')
    p=predictors(panel);future_invariance(panel,p);prepared=prepare_cases(p)
    expected=(78,76,73,80,78,76,73,46,43)
    if tuple(len(prepared[f,h]['dates']) for f,h,_,_ in CASES)!=expected:
        raise ValueError('causal eligibility drift from certified B5A')
    tables=analyze(panel,p,prepared)
    if len(tables[FILES[0]])!=9 or tuple(tables)!=FILES[:-1]:raise ValueError('exact nine-case/seven-artifact contract')
    out=work_root/'research_outputs/swing10/s2_b5_validation';out.mkdir(parents=True,exist_ok=True)
    ids={name:str(uuid.uuid4()) for name in FILES};artifacts=[]
    for name,table in tables.items():
        path=out/name;table.to_csv(path,index=False,float_format='%.17g',lineterminator='\n');blob=path.read_bytes()
        artifacts.append({'artifact_id':ids[name],'name':name,'sha256':hashlib.sha256(blob).hexdigest(),'size_bytes':len(blob),'object_path':f"artifacts/{context['job_id']}/{context['attempt_id']}/{name}"})
    blocks=[{'family':f,'horizon_days':h,'block':b,'start':str(min(d for d,k in pc['blocks'].items() if k==b))[:10],'end':str(max(d for d,k in pc['blocks'].items() if k==b))[:10],'eligible_dates':sum(k==b for k in pc['blocks'].values())} for (f,h),pc in prepared.items() for b in range(1,5)]
    manifest={'protocol':PROTOCOL,'base_decision_id':BASE_DECISION,'supplement_decision_id':SUPPLEMENT_DECISION,
      'frozen_decision_snapshot_sha256':SNAPSHOTS,'execution':context,'mwe_id':'MWE-SW10-S2B5-001',
      'input':{'parent_input_id':INPUT_ID,'identity':'massive_adjusted_daily_pre_discovery_2024-10-02_2025-01-31_asof_2026-10-03','sha256':INPUT_SHA,'size_bytes':INPUT_BYTES,'rows':9296,'symbols':112,'dates':83,'start':'2024-10-02','end':'2025-01-31','regenerated':False},
      'registry':[{'family':f,'horizon_days':h,'frozen_direction':d,'limited_temporal_capacity':l} for f,h,d,l in CASES],
      'sample_rule':'all causally eligible dates in entire immutable envelope; endpoint strictly before2025-02-03; no discretionary exclusions',
      'liquidity':{'tails':'inclusive same-date p20/p80','estimand':'mean date-level HIGH-minus-LOW spread','ES':'mean(spread)/sampleSD(spread)'},
      'market':{'stage1':'per-date forward_return~intercept+RET_MOM_rank','stage2':'b_t~intercept+Z_t','primary_estimand':'gamma','ES':'gamma/sampleSD(b_t)','stage1_statistics':'diagnostic only'},
      'predictors':{'RET_MOM':'close_t/close_(t-10)-1','rank':'finite same-date average_rank/N; centered2pct-1','SPY_TREND10':'SPY close_t/close_(t-10)-1','state':'strict prior finite expanding mean/SD; min20; ddof1; SD>1e-12; no fill','volume':'reported daily volume unchanged'},
      'inference':{'unit':'trading_date','HAC':'Newey-West','kernel':'Bartlett','lag':'horizon-1','two_sided':True,'reference':'asymptotic_normal','ci':.95,'small_sample_multiplier':False,'ddof':1},
      'multiple_testing':{'method':'Benjamini-Hochberg','family_tests':9,'q':.05,'unavailable':'retain conservativep=1 slot; publish unavailable inferential fields'},
      'material_abs_threshold':.20,'case_specific_block_definitions':blocks,'blocks_frozen_before_outcomes':True,
      'temporal':{'required_direction_blocks':3,'blocks':4,'market':'complete two-stage estimator refit within each block; original past-only standardized Z retained','max_absolute_block_share':.5,'block_effect':'block primary estimate*block eligible dates','unavailable':'fails robustness'},
      'symbol':{'additive':'liquidity date-tail contributions weighted1/Ndates; Stage1 OLS symbol contributions weighted Stage2 centeredZ OLS weights','ranking':'absolute contribution descending; symbol ascending tie','top':[1,5,10],'HHI':True,'leave5':'original ranks/tails/Z fixed; remove5 then refit full estimand; no primary symbol removal','zero_is_reversal':False,'unavailable_fails_support':True},
      'adjacency':'grid1-2-3-5-7-10; at least one same-sign registered immediate neighbor; absent neighbor ignored',
      'disposition_truth_table':'NOT_TESTABLE primary insufficiency; otherwise FAILED any directional/material/FDR fail; otherwise PARTIAL any robustness fail; otherwise SUPPORTED',
      'artifact_schemas':{k:list(v) for k,v in SCHEMAS.items()},'artifacts':artifacts,
      'manifest_identity':{'artifact_id':ids[FILES[-1]],'name':FILES[-1],'integrity':'external registration/readback; no recursive self-hash'},
      'source_sha256':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('swing10_s2_b5_validation.py','swing10_s2_b5_validation_contract.py','swing10_s2_b5_preparation.py')},
      'validation_sample_used':True,'no_validation_sample_recycling':True,'protected_data_access':False,'earnings_used':False,
      'prior_scientific_artifact_contents_read':False,'scientific_promotion_decision_made':False,
      'cost':{'executor':'github_actions','paid_fallback_selected':False,'provider_purchase_or_upgrade':False,'literal_zero_incremental_billing_verified':False},
      'limitations':['contemporary frozen112-symbol universe not historical PIT/survivorship-free','retrospective split-adjusted source snapshot not original vintage','83-date envelope; market46/43 dates and immutable LIMITED_TEMPORAL_CAPACITY','no transaction-cost model or factor promotion']}
    (out/FILES[-1]).write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    paths=[str((out/name).relative_to(work_root)) for name in FILES]
    return {'status':'PASS','artifact':paths[0],'output_paths':paths,'output_artifact_ids':{p:ids[n] for p,n in zip(paths,FILES)}}
