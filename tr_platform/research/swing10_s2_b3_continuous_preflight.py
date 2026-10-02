"""Predictor-only continuous interaction feasibility. No outcomes API."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import uuid
import numpy as np
import pandas as pd
from tr_platform.research.swing10_causal_inputs import causal_factors
from tr_platform.research.swing10_s2_b3_preflight import (
    FACTORS, INTERACTIONS, PANEL_COLUMNS, INPUT_SHA, INPUT_BYTES,
    reject_columns, guard_source, blocks, verify_input,
)

PROTOCOL = 'SW10_S2_B3_CONTINUOUS_PREFLIGHT_V1'
SUPPLEMENT = PROTOCOL + '_SUPPLEMENT_1'
RUNNER_ID = 'SW10-S2-B3-CONTINUOUS-PREFLIGHT'
VAR_EPS = 1e-12
FILES = ('continuous_interaction_coverage.csv',
         'continuous_interaction_collinearity.csv',
         'continuous_interaction_temporal_coverage.csv',
         'continuous_interaction_symbol_participation.csv',
         'continuous_interaction_preflight_summary.csv',
         'sw10_s2_b3_continuous_preflight_manifest.json')
SOURCE_FILES = ('swing10_s2_b3_continuous_preflight.py',
                'swing10_s2_b3_preflight.py', 'swing10_causal_inputs.py')
GATES = {'minimum_eligible_dates':100, 'minimum_median_symbols_per_date':50,
         'minimum_distinct_symbols':80, 'minimum_block_dates':20,
         'minimum_block_median_symbols_per_date':50,
         'max_top5_observation_share':.20, 'max_rank_deficient_date_fraction':.05,
         'max_near_zero_interaction_variance_date_fraction':.05,
         'aggregate_design_condition_number_max':30, 'vif_max':10}


def continuous_source_guard(source):
    guard_source(source)
    tree=ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node,ast.Call):
            fn=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
            if fn in {'read_excel','read_hdf','read_feather','read_json','urlopen'}:
                raise ValueError('external/scientific data access prohibited')
            if fn in {'read_csv','read_text','read_bytes','open','Path'}:
                for arg in ast.walk(node):
                    if isinstance(arg,ast.Constant) and isinstance(arg.value,str):
                        if any(x in arg.value.lower() for x in ('factor_causal_summary','factor_date_spreads','factor_b2_dispositions','factor_tail_summary')):
                            raise ValueError('scientific outcome artifact access prohibited')


def centered_ranks(frame):
    reject_columns(frame,('symbol','trade_date')+FACTORS)
    if frame.duplicated(['symbol','trade_date']).any():
        raise ValueError('duplicate symbol/date')
    result=frame[['symbol','trade_date']].copy()
    for factor in FACTORS:
        values=pd.to_numeric(frame[factor],errors='raise').where(np.isfinite(frame[factor]))
        eligible=values.groupby(frame.trade_date).transform('count')
        result[factor]=2*values.groupby(frame.trade_date).rank(method='average',pct=True)-1
        result[factor]=result[factor].where(eligible>=2)
    return result


def design(x,z):
    x=np.asarray(x,dtype=float); z=np.asarray(z,dtype=float)
    return np.column_stack((np.ones(len(x)),x,z,x*z))


def predictor_diagnostics(matrix):
    """SVD geometry and predictor-on-predictor VIF; no response variable."""
    matrix=np.asarray(matrix,dtype=float)
    n=len(matrix)
    if matrix.shape!=(n,4) or not np.isfinite(matrix).all():
        raise ValueError('exact four-column finite predictor design required')
    if not n:
        return {'design_rank':0,'condition_number':float('inf'),
                **{k:float('nan') for k in ('corr_primary_conditioner','corr_primary_interaction','corr_conditioner_interaction','leverage_max','leverage_p99','leverage_mean')},
                'leverage_flag_count':0, 'leverage_flag_rate':0.,
                **{k:float('inf') for k in ('vif_primary','vif_conditioner','vif_interaction','vif_max')}},np.array([])
    u,s,_=np.linalg.svd(matrix,full_matrices=False)
    tol=max(matrix.shape)*np.finfo(float).eps*s[0]
    rank=int((s>tol).sum())
    cond=float(s[0]/s[-1]) if rank==4 else float('inf')
    h=np.square(u[:,:rank]).sum(axis=1)
    correlations=[]
    for j,k in ((1,2),(1,3),(2,3)):
        a=matrix[:,j]-matrix[:,j].mean(); b=matrix[:,k]-matrix[:,k].mean()
        norm=np.linalg.norm(a)*np.linalg.norm(b)
        correlations.append(float(a@b/norm) if norm>0 else float('nan'))
    vifs=[]
    for j in (1,2,3):
        others=matrix[:,[k for k in range(4) if k!=j]]
        predictor=matrix[:,j]
        resid=predictor-others@np.linalg.lstsq(others,predictor,rcond=None)[0]
        total=float(np.square(predictor-predictor.mean()).sum())
        residual=float(np.square(resid).sum())
        vifs.append(float(total/residual) if total>0 and residual>np.finfo(float).eps*total else float('inf'))
    flags=h>2*rank/n
    return {'design_rank':rank,'condition_number':cond,
            **dict(zip(('corr_primary_conditioner','corr_primary_interaction','corr_conditioner_interaction'),correlations)),
            **dict(zip(('vif_primary','vif_conditioner','vif_interaction'),vifs)),
            'vif_max':max(vifs),'leverage_max':float(h.max()),'leverage_p99':float(np.quantile(h,.99)),
            'leverage_mean':float(h.mean()),'leverage_flag_count':int(flags.sum()),'leverage_flag_rate':float(flags.mean())},h


def dispersion(values,prefix):
    x=np.asarray(values,dtype=float); x=x[np.isfinite(x)]
    variance=float(x.var(ddof=1)) if len(x)>1 else float('nan')
    return {prefix+'_mean':float(x.mean()) if len(x) else float('nan'),
            prefix+'_sample_variance':variance,
            prefix+'_sample_sd':float(np.sqrt(variance)),
            prefix+'_min':float(x.min()) if len(x) else float('nan'),
            prefix+'_max':float(x.max()) if len(x) else float('nan'),
            prefix+'_unique_values':len(np.unique(x)),
            prefix+'_excess_tie_fraction':1-len(np.unique(x))/len(x) if len(x) else float('nan')}


def evaluate_gates(summary,temporal):
    checks={'eligible_dates':summary['eligible_dates']>=100,
            'median_joint_symbols':summary['median_joint_symbols']>=50,
            'distinct_symbols':summary['distinct_symbols']>=80,
            'four_blocks':len(temporal)==4,
            'top5_observation_share':np.isfinite(summary['top5_observation_share']) and summary['top5_observation_share']<=.20,
            'rank_deficient_date_fraction':np.isfinite(summary['rank_deficient_date_fraction']) and summary['rank_deficient_date_fraction']<=.05,
            'near_zero_interaction_variance_date_fraction':np.isfinite(summary['near_zero_interaction_variance_date_fraction']) and summary['near_zero_interaction_variance_date_fraction']<=.05,
            'aggregate_condition_number':np.isfinite(summary['aggregate_condition_number']) and summary['aggregate_condition_number']<=30,
            'vif':np.isfinite(summary['vif_max']) and summary['vif_max']<=10}
    for row in temporal:
        checks['block_'+str(row['block'])+'_eligible_dates']=row['eligible_dates']>=20
        checks['block_'+str(row['block'])+'_median_joint_symbols']=row['median_joint_symbols']>=50
    failed=[key for key,ok in checks.items() if not ok]
    return {'disposition':'NOT_FEASIBLE' if failed else 'FEASIBLE',
            'failed_gates':'|'.join(failed),**{key+'_pass':bool(ok) for key,ok in checks.items()}}


def audit_factor_frame(frame):
    reject_columns(frame,('symbol','trade_date')+FACTORS)
    ranks=centered_ranks(frame)
    dates=sorted(frame.trade_date.unique())
    coverage=[]; collinearity=[]; temporal=[]; participation=[]; summaries=[]; definitions={}
    population=frame.groupby('trade_date').size()
    rawgroups={d:g for d,g in frame.groupby('trade_date')}
    rankgroups={d:g for d,g in ranks.groupby('trade_date')}
    for primary,conditioner in INTERACTIONS:
        label=primary+' x '+conditioner
        # Eligibility calendar is fixed without inspecting design diagnostics.
        candidate_dates=[d for d in dates if int(np.isfinite(rankgroups[d][[primary,conditioner]]).all(axis=1).sum())>=4]
        mapping=blocks(candidate_dates)
        definitions[label]=[{'block':k,'date_start':str(min(ds))[:10] if ds else '',
                             'date_end':str(max(ds))[:10] if ds else '',
                             'candidate_dates':len(ds)} for k in range(1,5)
                            for ds in [[d for d in candidate_dates if mapping[d]==k]]]
        local=[]; matrices=[]; selected_groups=[]
        for date in dates:
            raw=rawgroups[date]; rg=rankgroups[date]
            valid=np.isfinite(rg[[primary,conditioner]]).all(axis=1)
            joint=raw.loc[valid]; rj=rg.loc[valid]
            x=rj[primary].to_numpy(); z=rj[conditioner].to_numpy()
            matrix=design(x,z); stats,h=predictor_diagnostics(matrix)
            product_var=float(np.var(x*z,ddof=1)) if len(x)>1 else float('nan')
            nearzero=not np.isfinite(product_var) or product_var<=VAR_EPS
            candidate=len(joint)>=4
            eligible=candidate and not nearzero
            row={'interaction':label,'trade_date':date,'fixed_block':mapping.get(date,0),
                 'panel_symbols':int(population[date]),
                 'primary_finite_symbols':int(np.isfinite(raw[primary]).sum()),
                 'conditioner_finite_symbols':int(np.isfinite(raw[conditioner]).sum()),
                 'joint_symbols':len(joint),'candidate_date':candidate,'eligible_date':eligible,
                 'exclusion_reason':'INSUFFICIENT_JOINT_CROSS_SECTION' if not candidate else 'ZERO_OR_NEAR_ZERO_PRODUCT_VARIANCE' if nearzero else '',
                 'rank_deficient':stats['design_rank']<4,'near_zero_interaction_variance':nearzero,
                 **dispersion(joint[primary],'raw_primary'),**dispersion(joint[conditioner],'raw_conditioner'),
                 **dispersion(x,'rank_primary'),**dispersion(z,'rank_conditioner'),**dispersion(x*z,'interaction')}
            local.append(row)
            collinearity.append({'interaction':label,'scope':'DATE','trade_date':date,
                                 'candidate_date':candidate,'eligible_date':eligible,'observations':len(joint),**stats})
            if eligible:
                matrices.append(matrix)
                selected_groups.append(pd.DataFrame({'symbol':joint.symbol.to_numpy(),'trade_date':date}))
        dr=pd.DataFrame(local); ed=dr[dr.eligible_date]; cd=dr[dr.candidate_date]
        matrix=np.concatenate(matrices) if matrices else np.empty((0,4))
        aggregate,h=predictor_diagnostics(matrix)
        collinearity.append({'interaction':label,'scope':'AGGREGATE','trade_date':'',
                             'candidate_date':True,'eligible_date':bool(len(matrix)), 'observations':len(matrix),**aggregate})
        chosen=pd.concat(selected_groups,ignore_index=True) if selected_groups else pd.DataFrame(columns=['symbol','trade_date'])
        chosen['leverage']=h
        counts=chosen.groupby('symbol').size()
        total=int(counts.sum())
        ordered=sorted(counts.index,key=lambda symbol:(-int(counts[symbol]),symbol))
        top={n:sum(int(counts[symbol]) for symbol in ordered[:n])/total if total else float('nan') for n in (1,5,10)}
        for symbol in sorted(frame.symbol.unique()):
            ss=chosen[chosen.symbol==symbol]; n=int(counts.get(symbol,0))
            participation.append({'interaction':label,'symbol':symbol,'eligible_symbol_dates':n,
                                  'observation_share':n/total if total else 0.,
                                  'eligible_date_participation_rate':n/len(ed) if len(ed) else 0.,
                                  'observation_count_rank':ordered.index(symbol)+1 if symbol in ordered else None,
                                  'aggregate_leverage_sum':float(ss.leverage.sum()),
                                  'aggregate_leverage_max':float(ss.leverage.max()) if len(ss) else float('nan'),
                                  **{f'block_{k}_symbol_dates':int(ss.trade_date.isin([d for d in candidate_dates if mapping[d]==k]).sum()) for k in range(1,5)}})
        blockrows=[]
        for k in range(1,5):
            bd=dr[dr.fixed_block==k]; be=bd[bd.eligible_date]
            row={'interaction':label,'block':k,**{key:value for key,value in definitions[label][k-1].items() if key!='block'},
                 'eligible_dates':len(be),'excluded_candidate_dates':len(bd)-len(be),
                 'eligible_symbol_date_observations':int(be.joint_symbols.sum()),
                 'median_joint_symbols':float(be.joint_symbols.median()) if len(be) else 0.,
                 'minimum_joint_symbols':int(be.joint_symbols.min()) if len(be) else 0,
                 'distinct_symbols':int(chosen[chosen.trade_date.isin(be.trade_date)].symbol.nunique()),
                 'rank_deficient_date_fraction':float(bd.rank_deficient.mean()) if len(bd) else float('nan'),
                 'near_zero_interaction_variance_date_fraction':float(bd.near_zero_interaction_variance.mean()) if len(bd) else float('nan')}
            row['block_coverage_pass']=row['eligible_dates']>=20 and row['median_joint_symbols']>=50
            blockrows.append(row)
        summary={'interaction':label,'panel_dates':len(dates),'candidate_dates':len(cd),
                 'eligible_dates':len(ed),'insufficient_cross_section_dates':len(dr)-len(cd),
                 'excluded_degenerate_dates':len(cd)-len(ed),
                 'eligible_symbol_date_observations':total,
                 'median_joint_symbols':float(ed.joint_symbols.median()) if len(ed) else 0.,
                 'minimum_joint_symbols':int(ed.joint_symbols.min()) if len(ed) else 0,
                 'distinct_symbols':len(counts),
                 'primary_eligibility_loss':int((dr.panel_symbols-dr.primary_finite_symbols).sum()),
                 'conditioner_eligibility_loss':int((dr.panel_symbols-dr.conditioner_finite_symbols).sum()),
                 'joint_eligibility_loss':int(dr.panel_symbols.sum()-dr.joint_symbols.sum()),
                 'rank_deficient_date_fraction':float(cd.rank_deficient.mean()) if len(cd) else float('nan'),
                 'near_zero_interaction_variance_date_fraction':float(cd.near_zero_interaction_variance.mean()) if len(cd) else float('nan'),
                 'top1_observation_share':top[1],'top5_observation_share':top[5],'top10_observation_share':top[10],
                 'hhi_observation_share':float(np.square(counts/total).sum()) if total else float('nan'),
                 'aggregate_condition_number':aggregate['condition_number'],
                 **{key:aggregate[key] for key in ('design_rank','vif_primary','vif_conditioner','vif_interaction','vif_max','corr_primary_conditioner','corr_primary_interaction','corr_conditioner_interaction','leverage_max','leverage_p99','leverage_flag_rate')},
                 **{f'block_{r["block"]}_eligible_dates':r['eligible_dates'] for r in blockrows},
                 **{f'block_{r["block"]}_median_symbols':r['median_joint_symbols'] for r in blockrows}}
        summary.update(evaluate_gates(summary,blockrows))
        summaries.append(summary); temporal.extend(blockrows); coverage.extend(local)
    return {FILES[0]:pd.DataFrame(coverage),FILES[1]:pd.DataFrame(collinearity),
            FILES[2]:pd.DataFrame(temporal),FILES[3]:pd.DataFrame(participation),
            FILES[4]:pd.DataFrame(summaries)}, {'block_definitions':definitions,
            'dispositions':{r['interaction']:r['disposition'] for r in summaries}}


def audit_panel(panel):
    reject_columns(panel,PANEL_COLUMNS)
    values=causal_factors(panel)
    return audit_factor_frame(values[['symbol','trade_date']+list(FACTORS)])


def run(work_root:Path):
    for name in SOURCE_FILES:
        continuous_source_guard((Path(__file__).parent/name).read_text())
    context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text())
    inputs=context['materialized_inputs']
    if len(inputs)!=1 or inputs[0]['sha256']!=INPUT_SHA or inputs[0]['size_bytes']!=INPUT_BYTES:
        raise ValueError('continuous preflight must materialize ONLY the certified daily panel')
    panel=verify_input(work_root/'job_inputs/swing10/market_daily_history.csv')
    tables,evidence=audit_panel(panel)
    out=work_root/'research_outputs/swing10/s2_b3_continuous_preflight'
    out.mkdir(parents=True,exist_ok=True)
    ids={name:str(uuid.uuid4()) for name in FILES}; declarations=[]
    for name,table in tables.items():
        path=out/name; table.to_csv(path,index=False,float_format='%.17g',lineterminator='\n')
        blob=path.read_bytes()
        declarations.append({'artifact_id':ids[name],'name':name,'size_bytes':len(blob),
                             'sha256':hashlib.sha256(blob).hexdigest(),
                             'object_path':f"artifacts/{context['job_id']}/{context['attempt_id']}/{name}"})
    manifest={'protocol':PROTOCOL,'decision_id':'971aac8a-3a0e-4d5c-a1d9-609d4988a327',
              'supplement':SUPPLEMENT,'supplement_decision_id':'a8142bfb-564a-40ca-95f8-4d2f2f3094c7',
              'mwe_id':'MWE-SW10-S2B3CP-001','execution':context,
              'input':{'identity':'market_daily_history_2025-02-03_2026-08-27','sha256':INPUT_SHA,'size_bytes':INPUT_BYTES,
                       'rows':44128,'symbols':112,'dates':394,'date_start':'2025-02-03','date_end':'2026-08-27','regenerated':False},
              'factor_source_revision':'b912f0c78d9593f2b8d866856217a389ce9baf68',
              'factor_registry':list(FACTORS),'legacy_factor_excluded':True,
              'interactions':[f+' x '+c for f,c in INTERACTIONS],
              'normalization':'same-date factor-eligible average rank/n; 2*pct_rank-1; N>=2; no winsorization or z-scores',
              'design_columns':['intercept','primary_centered_rank','conditioner_centered_rank','rank_product'],
              'numerical_conventions':{'sample_variance_ddof':1,'near_zero_variance_max':VAR_EPS,
                'minimum_joint_cross_section':4,'svd_rank_tolerance':'max(shape)*float64_eps*largest_singular_value',
                'condition_number':'2-norm four-column frozen raw rank-design',
                'vif':'predictor-on-other-predictors least squares with intercept; total/residual sum squares; exact degeneracy infinity',
                'diagnostic_fraction_denominator':'all candidate dates before variance/design exclusion',
                'blocks':'four chronological candidate-input-date blocks before variance/design exclusion',
                'leverage_flag':'h>2*rank/n, descriptive only'},
              'feasibility_gates':GATES,'pass_rule':'independent each interaction; every applicable gate required',
              **evidence,'forward_outcomes_read':False,'forward_outcomes_computed':False,
              'b2_outcome_artifacts_accessed':False,'protected_data_access':False,'source_guard_passed':True,
              'strict_input_schema':list(PANEL_COLUMNS),
              'source_file_hashes':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in SOURCE_FILES},
              'artifacts':declarations,'manifest_identity':{'artifact_id':ids[FILES[-1]],'name':FILES[-1],
                    'sha_size_verification':'external registration/readback; no recursive self-hash'},
              'cost':{'executor':'github_actions','runner':'ubuntu-latest','paid_compute_selected':False,'incremental_billing_verified':False},
              'limitations':['predictor observability/geometry only, not predictive value or power assurance',
                             'input eligibility is an upper bound on future horizon-specific inference eligibility',
                             'no scientific B3 execution or protocol freeze']}
    (out/FILES[-1]).write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    paths=[str((out/name).relative_to(work_root)) for name in FILES]
    return {'status':'PASS','artifact':paths[4],'output_paths':paths,
            'output_artifact_ids':{path:ids[name] for path,name in zip(paths,FILES)}}
