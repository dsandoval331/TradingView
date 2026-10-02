from pathlib import Path
import itertools
import json
import math
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing10_s2_b3 as p


@pytest.mark.parametrize('h',p.HORIZONS)
def test_horizon_returns_exact_trading_rows_and_no_cross_symbol_leak(h):
    rows=[]
    dates=pd.bdate_range('2025-01-01',periods=15)
    for symbol in ('A','B'):
        for i,date in enumerate(dates):
            close=2.**i*(1 if symbol=='A' else 3)
            rows.append(dict(symbol=symbol,trade_date=date,open=close,high=close,low=close,close=close,volume=100))
    z=p.forward_returns(pd.DataFrame(rows))
    for _,g in z.groupby('symbol'):
        assert g[f'forward_{h}'].notna().sum()==15-h
        np.testing.assert_allclose(g[f'forward_{h}'].dropna(),2.**h-1)
    changed=pd.DataFrame(rows);changed.loc[changed.trade_date==dates[-1],'close']*=2
    zz=p.forward_returns(changed)
    assert zz[f'forward_{h}'].isna().sum()==2*h


def test_date_ols_all_main_effects_and_additive_decomposition():
    rng=np.random.default_rng(638);x=rng.uniform(0,1,100);z=rng.uniform(0,1,100)
    X=p.design(x,z);expected=np.array([.1,4.,2.,.5]);y=X@expected
    beta,contributions,diag=p.fit_date(X,y)
    np.testing.assert_allclose(beta,expected,atol=1e-13)
    np.testing.assert_allclose(contributions,np.linalg.pinv(X)[3]*y,atol=1e-13)
    assert contributions.sum()==pytest.approx(.5)
    omitted=np.linalg.lstsq(X[:,[0,3]],y,rcond=None)[0][1]
    assert abs(omitted-.5)>1
    assert diag['design_rank']==4 and diag['residual_sum_squares']<1e-20
    with pytest.raises(ValueError):p.fit_date(X[:,[0,1,3]],y)
    with pytest.raises(ValueError):p.fit_date(p.design(x,x),y)
    with pytest.raises(ValueError):p.fit_date(X[:3],y[:3])


@pytest.mark.parametrize('h',p.HORIZONS)
def test_hac_bartlett_matches_independent_kernel_quadratic_form(h):
    x=np.array([.03,-.02,.05,.01,.08,-.04,.06,.02,.03,.01,.02,.04,.01,.02,.01,.03])
    result=p.hac_mean(x,h);n=len(x);lag=h-1
    K=np.maximum(1-np.abs(np.arange(n)[:,None]-np.arange(n)[None,:])/(lag+1),0)
    u=x-x.mean();se=np.sqrt(u@K@u/n**2)
    assert result['hac_lag']==lag and result['hac_se']==pytest.approx(se)
    assert result['p_raw']==pytest.approx(math.erfc(abs(x.mean()/se)/np.sqrt(2)))
    assert result['ci95_low']==pytest.approx(x.mean()-1.959963984540054*se)
    assert result['standardized_effect']==pytest.approx(x.mean()/x.std(ddof=1))
    assert result['standardized_effect']!=pytest.approx(x.mean()/x.std(ddof=0))


def test_hac_insufficient_nonfinite_and_unfrozen_rejected():
    with pytest.raises(ValueError):p.hac_mean([1,2],10)
    with pytest.raises(ValueError):p.hac_mean([1,np.nan,2],1)
    with pytest.raises(ValueError):p.hac_mean(np.arange(20),4)
    assert np.isnan(p.hac_mean([0.]*20,1)['p_raw'])


def test_exact_joint_48_bh_and_unavailable_denominator_retained():
    values={key:1. for key in p.FAMILY};values[p.FAMILY[0]]=.0001
    adjusted=p.bh_adjust(values)
    assert len(adjusted)==48 and adjusted[p.FAMILY[0]]==pytest.approx(.0048)
    values[p.FAMILY[-1]]=np.nan
    adjusted=p.bh_adjust(values)
    assert adjusted[p.FAMILY[0]]==pytest.approx(.0048) and np.isnan(adjusted[p.FAMILY[-1]])
    del values[p.FAMILY[-1]]
    with pytest.raises(ValueError,match='48-test'):p.bh_adjust(values)


def temporal_fixture(means):
    dates=pd.bdate_range('2025-01-01',periods=16)
    mapping=p.blocks(dates)
    ds=pd.DataFrame({'trade_date':dates,'beta_interaction':np.repeat(means,4)})
    return ds,mapping


@pytest.mark.parametrize('means,coherent,concentrated',[
    ([.3,.3,.3,-.1],True,True),([.9,.03,.03,-.04],True,False),
    ([.3,.3,-.1,-.1],False,True),([0.,0.,0.,0.],False,False),
    ([-.3,-.3,-.3,.1],True,True)])
def test_temporal_sign_and_additive_block_concentration(means,coherent,concentrated):
    ds,mapping=temporal_fixture(means);rows,stats=p.temporal_stats(ds,mapping)
    assert stats['temporal_sign_coherence']==coherent
    assert stats['temporal_concentration_pass']==concentrated
    if sum(abs(x) for x in means):
        np.testing.assert_allclose([r['absolute_block_effect_share'] for r in rows],np.abs(means)/np.abs(means).sum())
    original=dict(mapping);p.temporal_stats(ds.head(14),mapping)
    assert mapping==original


def symbol_fixture(mode):
    x=np.repeat([-1.,-1.,1.,1.],8);z=np.repeat([-1.,1.,-1.,1.],8)
    X=p.design(x,z);product=X[:,3];symbols=np.array([f'S{i:02}' for i in range(32)])
    y=product.copy() if mode=='steady' else -product.copy() if mode=='reversal' else np.zeros(32)
    if mode!='steady':y[:5]=10*product[:5]
    beta,contributions,_=p.fit_date(X,y)
    return [(pd.Timestamp('2025-01-01'),symbols,X,y,contributions)],float(beta[3])


@pytest.mark.parametrize('mode,reverse,left', [('steady',False,1.),('reversal',True,-1.),('zero',False,0.)])
def test_additive_symbol_shares_tie_order_and_leave_five_refit(mode,reverse,left):
    data,full=symbol_fixture(mode);rows,stats=p.concentration_stats(data,full)
    assert stats['additive_contribution_sum']==pytest.approx(full)
    assert stats['removed_top5_symbols']=='S00|S01|S02|S03|S04'
    assert stats['leave_top5_mean_beta_interaction']==pytest.approx(left,abs=1e-12)
    assert stats['leave_top5_sign_reversal']==reverse
    assert stats['symbol_sign_robustness']==(not reverse)
    assert sum(r['absolute_contribution_share'] for r in rows)==pytest.approx(1.)
    if mode=='steady':
        assert stats['top1_absolute_contribution_share']==pytest.approx(1/32)
        assert stats['top5_absolute_contribution_share']==pytest.approx(5/32)
        assert stats['top10_absolute_contribution_share']==pytest.approx(10/32)
        assert stats['contribution_hhi']==pytest.approx(1/32)


@pytest.mark.parametrize('full,left,result',[(1,0,False),(-1,0,False),(0,1,False),(1,-1,True),(-1,1,True),(1,np.nan,False)])
def test_zero_is_not_sign_reversal(full,left,result):
    assert p.is_sign_reversal(full,left)==result


def test_unavailable_symbol_diagnostics_fail_closed():
    data,full=symbol_fixture('steady');date,symbols,X,y,c=data[0]
    beta,contributions,_=p.fit_date(X[[0,8,16,24]],y[[0,8,16,24]])
    data=[(date,symbols[[0,8,16,24]],X[[0,8,16,24]],y[[0,8,16,24]],contributions)]
    _,stats=p.concentration_stats(data,float(beta[3]))
    assert not stats['symbol_diagnostics_available'] and not stats['symbol_sign_robustness']


@pytest.mark.parametrize('flags',list(itertools.product((False,True),repeat=6)))
def test_every_literal_disposition_branch(flags):
    semantic,fdr,material,coherent,concentrated,symbol=flags
    row=dict(zip(('semantic_data_integrity_pass','fdr_pass','material_effect_pass',
                  'temporal_sign_coherence','temporal_concentration_pass','symbol_sign_robustness'),flags))
    expected='INVALID_SEMANTICS_NOT_TESTABLE' if not semantic else 'ADVANCE' if fdr and material and coherent and concentrated and symbol else 'WEAK_EVIDENCE' if (fdr!=material) and coherent and concentrated and symbol else 'RETAIN_AS_COUNTEREVIDENCE'
    assert p.disposition(row)==expected


def factor_outcome_fixture():
    rng=np.random.default_rng(557);dates=pd.bdate_range('2025-01-01',periods=16)
    records=[]
    for date in dates:
        for i in range(20):records.append({'symbol':f'S{i:02}','trade_date':date,**dict(zip(p.FACTORS,rng.normal(size=6)))})
    f=pd.DataFrame(records);r=p.centered_ranks(f)
    # Synthetic values only, no market outcome computation.
    y=r[['symbol','trade_date']].copy()
    for h in p.HORIZONS:y[f'forward_{h}']=.01*r.RET_MOM+.02*r.VOL_REGIME+.005*r.RET_MOM*r.VOL_REGIME+rng.normal(0,.01,len(f))
    return f,y,{name:p.blocks(dates) for name,h in p.FAMILY}


def test_synthetic_full_48_family_artifact_contract_and_gate_columns():
    f,y,m=factor_outcome_fixture();tables=p.analyze(f,y,m)
    assert set(tables)==set(p.FILES[:-1])
    assert len(tables[p.FILES[0]])==48 and len(tables[p.FILES[5]])==48
    assert len(tables[p.FILES[1]])==48*16 and len(tables[p.FILES[2]])==48*4
    assert len(tables[p.FILES[3]])==48*20
    assert tables[p.FILES[0]].primary_family_tests.eq(48).all()
    assert set(tables[p.FILES[0]].disposition)<=set(['ADVANCE','WEAK_EVIDENCE','RETAIN_AS_COUNTEREVIDENCE','INVALID_SEMANTICS_NOT_TESTABLE'])
    for row in tables[p.FILES[0]].to_dict('records'):assert p.disposition(row)==row['disposition']
    y['extra_outcome']=1
    with pytest.raises(ValueError):p.analyze(f,y,m)


def test_contract_mutation_rejected_and_scientific_cert_selection(monkeypatch):
    monkeypatch.setattr(p,'HORIZONS',(1,2,3,5,7))
    with pytest.raises(ValueError):p.require_contract()
    from cloud_compute.certify_dispatch_contracts import selected_tests
    tests=selected_tests('SW10-S2-B3')
    assert 'tests/test_swing10_s2_b3.py' in tests
    assert 'tests/test_swing10_s2_b3_continuous_preflight.py' in tests
    assert 'tests/test_swing10_s2_b3_preflight.py' in tests


def test_seven_artifacts_ids_manifest_and_single_input(monkeypatch,tmp_path):
    ctx={'job_id':'job','attempt_id':'attempt','materialized_inputs':[{'sha256':p.INPUT_SHA,'size_bytes':p.INPUT_BYTES}]}
    path=tmp_path/'job_inputs/swing10/execution_context.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(ctx))
    f,y,m=factor_outcome_fixture();tables=p.analyze(f,y,m)
    monkeypatch.setattr(p,'verify_input',lambda path:pd.DataFrame())
    monkeypatch.setattr(p,'audit_panel',lambda panel:(tables,{}))
    result=p.run(tmp_path);assert len(result['output_paths'])==7 and len(result['output_artifact_ids'])==7
    out=tmp_path/'research_outputs/swing10/s2_b3'
    manifest=json.loads((out/p.FILES[-1]).read_text())
    assert len(manifest['primary_family'])==48 and len(manifest['artifacts'])==6
    assert manifest['blocks_fixed_before_outcome_construction'] and not manifest['protected_data_access']
    assert not manifest['historical_earnings_used'] and manifest['multiple_testing']['single_joint_family']
    assert set(manifest['source_file_hashes'])==set(p.SOURCE_FILES)
    ctx['materialized_inputs'][0]['size_bytes']=1;path.write_text(json.dumps(ctx))
    with pytest.raises(ValueError,match='ONLY'):p.run(tmp_path)


def test_scientific_exact_revision_bundle(monkeypatch,tmp_path):
    from cloud_compute import research_revision_adapter as a
    calls=[]
    def materialize(root,sha,path,dest):
        calls.append((sha,path));dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('')
    def execute(args,**kwargs):
        Path(args[-1]).write_text(json.dumps({'status':'PASS'}))
        assert 'swing10_s2_b3 import run' in args[2]
        return type('Proc',(),{'returncode':0,'stderr':''})()
    monkeypatch.setattr(a,'materialize_module',materialize);monkeypatch.setattr(a.subprocess,'run',execute)
    a._run_b2_bundle(tmp_path,'b'*40,tmp_path/'dest',tmp_path,scientific=True)
    assert {path.rsplit('/',1)[-1] for sha,path in calls}==set(p.SOURCE_FILES)
    assert all(sha=='b'*40 for sha,path in calls)
