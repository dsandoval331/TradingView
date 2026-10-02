from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing10_s2_b3_continuous_preflight as p
from tr_platform.research.swing10_causal_inputs import causal_factors


def fixture(days=8,symbols=12):
    rng=np.random.default_rng(9273)
    rows=[]
    for date in pd.bdate_range('2025-01-01',periods=days):
        v=rng.normal(size=(symbols,len(p.FACTORS)))
        for i in range(symbols):
            rows.append({'symbol':f'S{i:03}','trade_date':date,**dict(zip(p.FACTORS,v[i]))})
    return pd.DataFrame(rows)


def test_average_ties_percentile_and_centered_mapping():
    f=fixture(1,4); f.RET_MOM=[1,1,3,4]
    z=p.centered_ranks(f)
    np.testing.assert_allclose(z.RET_MOM,[-.25,-.25,.5,1.])
    f.loc[0,'RET_MOM']=np.nan
    z=p.centered_ranks(f)
    np.testing.assert_allclose(z.RET_MOM.dropna(),[-1/3,1/3,1.])
    f.RET_MOM=7
    assert p.centered_ranks(f).RET_MOM.eq(.25).all()
    f.RET_MOM=[1,np.nan,np.nan,np.nan]
    assert p.centered_ranks(f).RET_MOM.isna().all()


def test_ranks_use_own_eligible_population_before_intersection():
    f=fixture(1,4);f.RET_MOM=[1,2,3,4];f.VOL_REGIME=[4,3,np.nan,np.nan]
    z=p.centered_ranks(f)
    np.testing.assert_allclose(z.RET_MOM,[-.5,0,.5,1.])
    np.testing.assert_allclose(z.VOL_REGIME.dropna(),[1.,0.])


@pytest.mark.parametrize('field',['forward_1','future_close','outcome','p_raw','effect','profit','VOL_TURN_B1_LEGACY'])
def test_all_outcome_extra_columns_rejected(field):
    f=fixture();f[field]=1
    with pytest.raises(ValueError,match='outcome-blind schema'):p.centered_ranks(f)
    with pytest.raises(ValueError,match='outcome-blind schema'):p.audit_factor_frame(f)
    panel=pd.DataFrame(columns=list(p.PANEL_COLUMNS)+[field])
    with pytest.raises(ValueError,match='outcome-blind schema'):p.audit_panel(panel)


@pytest.mark.parametrize('source',[
    'x.close.shift(-1)', 'forward_returns(x)', 'x.close.pct_change(-1)',
    'from tr_platform.research.swing10_s2_b2_core import forward_returns',
    'import statsmodels.api', 'import requests',
    'pd.read_csv("factor_causal_summary.csv")',
    'Path("factor_date_spreads.csv").read_text()',
    'pd.read_parquet("holdout.parquet")','pd.read_json("outcome.json")',
    'pd.read_csv("protected_holdout.csv")','x["forward_1"]','x["effect"]','x["p_value"]'])
def test_fail_closed_future_scientific_and_protected_paths(source):
    with pytest.raises(ValueError):p.continuous_source_guard(source)


def test_production_source_and_outcome_free_dispatch_tests():
    root=Path(__file__).resolve().parents[1]/'tr_platform/research'
    for name in p.SOURCE_FILES:p.continuous_source_guard((root/name).read_text())
    from cloud_compute.certify_dispatch_contracts import selected_tests
    names=selected_tests(p.RUNNER_ID)
    assert 'tests/test_swing10_s2_b3_continuous_preflight.py' in names
    assert not any('s2_b2' in name for name in names)


def test_predictor_geometry_correlations_vif_and_leverage_identity():
    rng=np.random.default_rng(337);x=rng.uniform(-1,1,2000);z=rng.uniform(-1,1,2000)
    matrix=p.design(x,z);stats,h=p.predictor_diagnostics(matrix)
    assert stats['design_rank']==4 and stats['condition_number']<4
    assert stats['vif_max']<1.02
    assert h.sum()==pytest.approx(4)
    expected=np.einsum('ij,jk,ik->i',matrix,np.linalg.inv(matrix.T@matrix),matrix)
    np.testing.assert_allclose(h,expected,atol=1e-13)
    np.testing.assert_allclose(stats['corr_primary_conditioner'],np.corrcoef(x,z)[0,1])


def test_rank_deficiency_and_exact_collinearity_fail_closed():
    x=np.linspace(-1,1,100)
    stats,_=p.predictor_diagnostics(p.design(x,x))
    assert stats['design_rank']==3 and np.isinf(stats['condition_number'])
    assert np.isinf(stats['vif_primary']) and np.isinf(stats['vif_conditioner'])
    stats,_=p.predictor_diagnostics(p.design(x,np.ones(100)))
    assert stats['design_rank']==2 and np.isinf(stats['vif_interaction'])


def gate_fixture():
    return {'eligible_dates':100,'median_joint_symbols':50,'distinct_symbols':80,
            'top5_observation_share':.20,'rank_deficient_date_fraction':.05,
            'near_zero_interaction_variance_date_fraction':.05,
            'aggregate_condition_number':30.,'vif_max':10.},[
            {'block':i,'eligible_dates':20,'median_joint_symbols':50} for i in range(1,5)]


@pytest.mark.parametrize('key,value,failed',[
    ('eligible_dates',99,'eligible_dates'),('median_joint_symbols',49,'median_joint_symbols'),
    ('distinct_symbols',79,'distinct_symbols'),('top5_observation_share',.20001,'top5_observation_share'),
    ('rank_deficient_date_fraction',.050001,'rank_deficient_date_fraction'),
    ('near_zero_interaction_variance_date_fraction',.050001,'near_zero_interaction_variance_date_fraction'),
    ('aggregate_condition_number',30.001,'aggregate_condition_number'),('vif_max',10.001,'vif'),
    ('aggregate_condition_number',np.nan,'aggregate_condition_number'),('vif_max',np.inf,'vif')])
def test_frozen_gate_boundaries_and_independent_results(key,value,failed):
    s,b=gate_fixture()
    assert p.evaluate_gates(s,b)['disposition']=='FEASIBLE'
    bad=dict(s);bad[key]=value
    result=p.evaluate_gates(bad,b)
    assert result['disposition']=='NOT_FEASIBLE' and result['failed_gates']==failed
    assert p.evaluate_gates(s,b)['disposition']=='FEASIBLE'


def test_each_block_gate_and_four_fixed_blocks():
    s,b=gate_fixture();b[1]['eligible_dates']=19;b[3]['median_joint_symbols']=49
    result=p.evaluate_gates(s,b)
    assert result['failed_gates']=='block_2_eligible_dates|block_4_median_joint_symbols'
    assert 'four_blocks' in p.evaluate_gates(s,b[:3])['failed_gates']


def test_degenerate_dates_are_visible_in_denominators():
    f=fixture(8,12);f.RET_MOM=1
    tables,e=p.audit_factor_frame(f)
    summary=tables[p.FILES[4]].set_index('interaction')
    a=summary.loc['RET_MOM x VOL_REGIME']
    assert a.candidate_dates==8 and a.rank_deficient_date_fraction==1
    assert a.disposition=='NOT_FEASIBLE'
    f.loc[f.trade_date==f.trade_date.min(),list(p.FACTORS)]=1
    tables,e=p.audit_factor_frame(f)
    summary=tables[p.FILES[4]]
    assert summary.near_zero_interaction_variance_date_fraction.eq(1/8).all()
    assert summary.excluded_degenerate_dates.eq(1).all()
    assert all(len(v)==4 for v in e['block_definitions'].values())


def test_all_interactions_independent_with_one_structural_failure():
    f=fixture(104,80);f.VOL_REGIME=f.RET_MOM
    tables,e=p.audit_factor_frame(f)
    summary=tables[p.FILES[4]].set_index('interaction')
    assert len(summary)==8 and summary.loc['RET_MOM x VOL_REGIME','disposition']=='NOT_FEASIBLE'
    assert summary.loc['SHORT_REV x VOL_REGIME','disposition']=='FEASIBLE'
    assert summary.loc['RET_MOM x GAP_OVN','disposition']=='FEASIBLE'
    assert len(tables[p.FILES[0]])==8*104
    assert len(tables[p.FILES[1]])==8*105
    assert len(tables[p.FILES[2]])==32 and len(tables[p.FILES[3]])==8*80
    assert summary.top5_observation_share.eq(5/80).all()


def test_future_raw_factor_rank_product_invariance():
    rng=np.random.default_rng(815);rows=[];dates=pd.bdate_range('2025-01-01',periods=145)
    for i in range(8):
        prices=100*np.exp(np.cumsum(rng.normal(0,.01,len(dates))))
        for j,d in enumerate(dates):
            rows.append(dict(symbol=f'S{i}',trade_date=d,open=prices[j]*.998,
                high=prices[j]*1.02,low=prices[j]*.98,close=prices[j],volume=float(rng.integers(1,10000))))
    panel=pd.DataFrame(rows);cut=dates[130];changed=panel.copy()
    changed.loc[changed.trade_date>cut,['open','high','low','close','volume']]*=100
    a=causal_factors(panel)[['symbol','trade_date']+list(p.FACTORS)]
    b=causal_factors(changed)[a.columns]
    pd.testing.assert_frame_equal(a[a.trade_date<=cut],b[b.trade_date<=cut])
    ar=p.centered_ranks(a);br=p.centered_ranks(b)
    pd.testing.assert_frame_equal(ar[ar.trade_date<=cut],br[br.trade_date<=cut])
    for primary,conditioner in p.INTERACTIONS:
        np.testing.assert_allclose((ar[primary]*ar[conditioner])[ar.trade_date<=cut],
                                   (br[primary]*br[conditioner])[br.trade_date<=cut],equal_nan=True)


def test_six_outputs_single_input_manifest_and_primary(monkeypatch,tmp_path):
    path=tmp_path/'job_inputs/swing10/execution_context.json';path.parent.mkdir(parents=True)
    ctx={'job_id':'job','attempt_id':'attempt','materialized_inputs':[{'sha256':p.INPUT_SHA,'size_bytes':p.INPUT_BYTES}]}
    path.write_text(json.dumps(ctx))
    monkeypatch.setattr(p,'verify_input',lambda path:pd.DataFrame())
    monkeypatch.setattr(p,'audit_panel',lambda value:p.audit_factor_frame(fixture()))
    result=p.run(tmp_path)
    assert result['artifact'].endswith(p.FILES[4]) and len(result['output_paths'])==6
    out=tmp_path/'research_outputs/swing10/s2_b3_continuous_preflight'
    m=json.loads((out/p.FILES[-1]).read_text())
    assert len(m['interactions'])==8 and len(m['artifacts'])==5
    assert not any(m[k] for k in ('forward_outcomes_read','forward_outcomes_computed','b2_outcome_artifacts_accessed','protected_data_access'))
    assert m['feasibility_gates']==p.GATES and m['legacy_factor_excluded']
    assert set(m['source_file_hashes'])==set(p.SOURCE_FILES)
    ctx['materialized_inputs'].append(ctx['materialized_inputs'][0]);path.write_text(json.dumps(ctx))
    with pytest.raises(ValueError,match='ONLY'):p.run(tmp_path)


def test_adapter_continuous_bundle_is_exact_and_has_no_outcome_module(monkeypatch,tmp_path):
    from cloud_compute import research_revision_adapter as a
    calls=[]
    def materialize(root,sha,path,dest):
        calls.append((sha,path));dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('')
    def execute(args,**kwargs):
        Path(args[-1]).write_text(json.dumps({'status':'PASS'}))
        assert 'swing10_s2_b3_continuous_preflight' in args[2]
        return type('Proc',(),{'returncode':0,'stderr':''})()
    monkeypatch.setattr(a,'materialize_module',materialize);monkeypatch.setattr(a.subprocess,'run',execute)
    a._run_b2_bundle(tmp_path,'a'*40,tmp_path/'dest',tmp_path,continuous=True)
    assert {path.rsplit('/',1)[-1] for sha,path in calls}==set(p.SOURCE_FILES)
    assert all(sha=='a'*40 for sha,path in calls)
