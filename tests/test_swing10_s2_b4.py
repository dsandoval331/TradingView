from pathlib import Path
import hashlib
import json
import math
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing10_s2_b4 as b
from tr_platform.research import swing10_s2_b4_preflight as p
from cloud_compute import research_revision_adapter as adapter
from cloud_compute.certify_dispatch_contracts import selected_tests

def panel(n=220):
    rows=[]
    for si,sym in enumerate(['SPY']+[f'S{i:02}' for i in range(12)]):
        for t,date in enumerate(pd.bdate_range('2025-01-01',periods=n)):
            close=100*np.exp(.0004*t+.04*np.sin(t/(5+si)+si)+.002*si*t)
            rows.append([sym,date,close*.999,close*1.02,close*.98,close,1000+si*100+200*np.sin(t/(3+si))])
    return pd.DataFrame(rows,columns=p.PANEL_COLUMNS)

def test_frozen_snapshots_and_family():
    assert len(b.require_frozen_decisions())==2
    assert len(b.FAMILY)==60 and len(b.FILES)==7
    assert 'tests/test_swing10_s2_b4.py' in selected_tests('SW10-S2-B4')
    assert adapter.GOVERNED_RESEARCH_TARGETS['SW10-S2-B4'].execution_mode=='swing10_b4_scientific_bundle'

def test_strict_past_standardization_analytic():
    s=pd.Series(np.arange(1.,31.),index=pd.bdate_range('2025-01-01',periods=30))
    z=b.standardize_state(s)
    assert z.standardized_state.iloc[:20].isna().all()
    assert z.standardized_state.iloc[20]==pytest.approx((21-10.5)/np.std(np.arange(1.,21.),ddof=1))
    q=s.copy();q.iloc[20]=1000
    zz=b.standardize_state(q)
    assert z.prior_mean.iloc[20]==zz.prior_mean.iloc[20]
    assert z.prior_sample_sd.iloc[20]==zz.prior_sample_sd.iloc[20]

def test_finite_history_count_floor_and_no_fill():
    s=pd.Series([1.]*21+[np.inf,np.nan,2.]+list(range(25)))
    z=b.standardize_state(s)
    assert z.standardized_state.iloc[:24].isna().all()
    assert z.prior_count.iloc[24]==22
    assert np.isfinite(z.standardized_state.iloc[24])

def test_standardization_future_invariance():
    s=pd.Series(np.arange(50.)**2);q=s.copy();q.iloc[30:]*=10
    pd.testing.assert_frame_equal(b.standardize_state(s).iloc[:30],b.standardize_state(q).iloc[:30],check_exact=True)

def test_stage1_intercept_slope_and_additive_weights():
    x=np.linspace(-1,1,112);y=3+2*x
    beta,contrib,diag=b.slope_fit(x,y)
    assert beta==pytest.approx(2);assert diag['intercept']==pytest.approx(3)
    assert contrib.sum()==pytest.approx(beta);assert diag['design_rank']==2
    with pytest.raises(ValueError):b.slope_fit(np.ones(112),y)

@pytest.mark.parametrize('h',b.HORIZONS)
def test_stage2_hac_independent_scalar_score_formula(h):
    z=np.sin(np.arange(80.)/5);slopes=.2+.07*z+.03*np.cos(np.arange(80.)/3)
    stats,_=b.hac_regression(z,slopes,h)
    c=z-z.mean();gamma=(c@slopes)/(c@c);alpha=slopes.mean()-gamma*z.mean()
    scores=c*(slopes-alpha-gamma*z)/(c@c)
    variance=scores@scores
    for k in range(1,h):variance+=2*(1-k/h)*(scores[k:]@scores[:-k])
    assert stats['primary_estimate']==pytest.approx(gamma)
    assert stats['hac_se']==pytest.approx(np.sqrt(variance))
    assert stats['standardized_effect']==pytest.approx(gamma/np.std(slopes,ddof=1))
    assert stats['hac_lag']==h-1
    assert stats['p_raw']==pytest.approx(math.erfc(abs(gamma/np.sqrt(variance))/np.sqrt(2)))
    assert stats['ci95_low']==pytest.approx(gamma-1.959963984540054*np.sqrt(variance))

@pytest.mark.parametrize('h',b.HORIZONS)
def test_horizon_returns_and_terminal_missing(h):
    f=b.forward_returns(panel(40));z=f[f.symbol=='SPY'];raw=panel(40).query("symbol=='SPY'").close.to_numpy()
    np.testing.assert_allclose(z[f'forward_{h}'].iloc[:-h],raw[h:]/raw[:-h]-1)
    assert z[f'forward_{h}'].iloc[-h:].isna().all()

def test_bh60_joint_known_family_and_missing_fail_closed():
    values={k:(i+1)*.001 for i,k in enumerate(b.FAMILY)}
    adjusted=b.bh_adjust(values)
    assert all(v==pytest.approx(.06) for v in adjusted.values())
    with pytest.raises(ValueError):b.bh_adjust(dict(list(values.items())[:-1]))
    values[b.FAMILY[0]]=np.nan
    with pytest.raises(ValueError):b.bh_adjust(values)

def test_complete_stage_refit_symbol_and_zero_sign():
    data=[]
    for i in range(40):
        x=np.linspace(-1,1,12);y=(.4+.1*i)*x+.5
        qty,contrib,_=b.slope_fit(x,y)
        data.append({'date':i,'symbols':np.array([f'S{j}' for j in range(12)]),'x':x,'y':y,'z':float(i),'quantity':qty,'contributions':contrib})
    full=b.primary_from_data(data,True,1)['primary_estimate']
    assert full==pytest.approx(.1)
    rows,stats=b.concentration(data,True,1,full)
    assert sum(r['additive_primary_contribution'] for r in rows)==pytest.approx(full)
    assert stats['leave_top5_primary_estimate']==pytest.approx(.1)
    assert stats['symbol_sign_robustness']
    assert b.refit_without(data,{'S1','S2'},True,1)==pytest.approx(full)

def test_temporal_complete_stage2_refits():
    data=[];mapping={}
    for i in range(100):
        block=i//25+1;z=float(i%25)
        data.append({'date':i,'quantity':block*z+np.sin(i),'z':z});mapping[i]=block
    full=b.primary_from_data(data,True,1)['primary_estimate']
    rows,stats=b.temporal(data,True,1,full,mapping)
    for block,row in enumerate(rows,1):
        selected=[d for d in data if mapping[d['date']]==block]
        assert row['primary_estimate']==pytest.approx(b.primary_from_data(selected,True,1)['primary_estimate'])
    assert stats['same_sign_blocks']==4

@pytest.mark.parametrize('slopes,coherent,concentrated',[
    ([1,1,1,-1],True,True),([1,1,-1,-1],False,True),
    ([4,1,1,1],True,False),([-1,-1,-1,1],True,True)])
def test_temporal_gate_boundaries(slopes,coherent,concentrated):
    data=[];mapping={}
    for i in range(100):
        block=i//25+1;z=float(i%25)
        data.append({'date':i,'quantity':slopes[block-1]*z,'z':z});mapping[i]=block
    full=b.primary_from_data(data,True,1)['primary_estimate']
    _,stats=b.temporal(data,True,1,full,mapping)
    assert stats['temporal_sign_coherence']==coherent
    assert stats['temporal_concentration_pass']==concentrated

@pytest.mark.parametrize('left,reverse',[(0.,False),(-1.,True),(1.,False)])
def test_leave5_zero_and_reversal_fail_closed(monkeypatch,left,reverse):
    data=[]
    for date in range(30):
        x=np.array([-1.]*6+[1.]*6);y=date*x
        q,c,_=b.slope_fit(x,y)
        data.append({'date':date,'symbols':np.array([f'S{i:02}' for i in reversed(range(12))]),
                     'x':x,'y':y,'z':float(date),'quantity':q,'contributions':c})
    monkeypatch.setattr(b,'refit_without',lambda *args:left)
    rows,stats=b.concentration(data,True,1,1.)
    assert stats['removed_top5_symbols']=='S00|S01|S02|S03|S04'
    assert stats['leave_top5_sign_reversal']==reverse
    assert stats['symbol_sign_robustness']==(not reverse)

def test_exact_sha_scientific_adapter_bundle(monkeypatch,tmp_path):
    seen=[];sha='a'*40
    def materialize(repo,s,path,dest):
        assert s==sha;seen.append(path);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('# fixture')
        return dest
    monkeypatch.setattr(adapter,'materialize_module',materialize)
    class Proc:returncode=0
    def run(args,**kwargs):
        assert 'from tr_platform.research.swing10_s2_b4 import run' in args[2]
        Path(args[-1]).write_text(json.dumps({'status':'PASS'}));return Proc()
    monkeypatch.setattr(adapter.subprocess,'run',run)
    assert adapter._run_b4_bundle(tmp_path,sha,tmp_path/'bundle',tmp_path,scientific=True)=={'status':'PASS'}
    assert set(seen)=={*(f'tr_platform/research/{n}' for n in b.SOURCE_FILES),
        'research_protocols/swing10/SW10_S2_B4_PREFLIGHT_V1.persisted.json',
        'research_protocols/swing10/SW10_S2_B4_PROTOCOL_V1.persisted.json',
        'research_protocols/swing10/SW10_S2_B4_PROTOCOL_V1_SUPPLEMENT_1.persisted.json'}

@pytest.mark.parametrize('source',[
 "import requests", "from tr_platform.research.swing10_s2_b3 import run",
 "pd.read_csv('factor_causal_summary.csv')", "Path('protected/holdout.csv').read_bytes()",
 "Path('interaction_b3_summary.csv').read_text()", "eval('x')"])
def test_scientific_source_restrictions(source):
    with pytest.raises(ValueError):b.scientific_source_guard(source)

def test_production_source_guard():
    b.scientific_source_guard(Path(b.__file__).read_text())

def test_synthetic_full_artifact_contract_and_semantic_diagnostics(tmp_path,monkeypatch):
    raw=panel();monkeypatch.setattr(b,'verify_input',lambda _:raw)
    inp=tmp_path/'job_inputs/swing10';inp.mkdir(parents=True)
    context={'job_id':'synthetic','attempt_id':'synthetic','research_revision':'1'*40,
             'infrastructure_revision':'2'*40,'materialized_inputs':[{'sha256':p.INPUT_SHA,'size_bytes':p.INPUT_BYTES,'object_path':'certified'}]}
    (inp/'execution_context.json').write_text(json.dumps(context))
    result=b.run(tmp_path)
    assert result['status']=='PASS' and len(result['output_paths'])==7
    out=tmp_path/'research_outputs/swing10/s2_b4';s=pd.read_csv(out/b.FILES[0])
    assert len(s)==60 and set(s.hypothesis)==set(b.PRIMARY)
    assert s.primary_family_tests.eq(60).all()
    assert len(pd.read_csv(out/b.FILES[2]))==240
    manifest=json.loads((out/b.FILES[-1]).read_text())
    assert manifest['supplement_decision_id']==b.SUPPLEMENT
    assert manifest['production_future_data_invariance'] and not manifest['protected_data_access']
    for artifact in manifest['artifacts']:
        blob=(out/artifact['name']).read_bytes()
        assert len(blob)==artifact['size_bytes'] and hashlib.sha256(blob).hexdigest()==artifact['sha256']
        assert result['output_artifact_ids'][str((out/artifact['name']).relative_to(tmp_path))]==artifact['artifact_id']
    symbol=pd.read_csv(out/b.FILES[3]).groupby(['hypothesis','horizon_days']).additive_primary_contribution.sum()
    np.testing.assert_allclose(s.set_index(['hypothesis','horizon_days']).primary_estimate.sort_index(),symbol.sort_index(),rtol=1e-8,atol=1e-12)

def test_immutable_input_rejected_before_outcomes(tmp_path):
    inp=tmp_path/'job_inputs/swing10';inp.mkdir(parents=True)
    (inp/'execution_context.json').write_text(json.dumps({'materialized_inputs':[{'sha256':'wrong','size_bytes':p.INPUT_BYTES}]}))
    with pytest.raises(ValueError,match='certified immutable'):b.run(tmp_path)
