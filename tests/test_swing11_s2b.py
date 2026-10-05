import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing11_s2b as b

@pytest.fixture(scope='module')
def fixture_panel():
    rng=np.random.default_rng(8713);n=16;t=70
    c=np.exp(np.log(np.linspace(15,170,n))[None,:]+np.cumsum(rng.normal(.001,.02,(t,n)),axis=0))
    v=np.exp(rng.normal(12,1,(t,n)))
    return pd.DataFrame([{'symbol':f'SYNTHETIC_{i:03}','trade_date':f'{j:04}','open':c[j,i],'high':c[j,i]*1.03,'low':c[j,i]*.97,'close':c[j,i],'volume':v[j,i]} for j in range(t) for i in range(n)])

@pytest.fixture(scope='module')
def result(fixture_panel):return b.analyze(fixture_panel)

@pytest.mark.parametrize('index',[1,2,3])
def test_known_ols_and_additive_projection(index):
    rng=np.random.default_rng(7);p=rng.normal(size=30);m=rng.normal(size=30);x=np.column_stack([np.ones(30),p,m,p*m]);coef=np.array([.1,-.3,.2,.4]);y=x@coef
    effect,c=b.coefficient(x,y,index)
    certified,cert_c=b.s.ols_contributions(x,y,[f'SYNTHETIC_{i}' for i in range(30)],index)
    assert effect==pytest.approx(coef[index]) and effect==pytest.approx(certified) and np.allclose(c,cert_c)

@pytest.mark.parametrize('h',b.s.HORIZONS)
def test_exact_horizon_endpoint_and_price_only_capacity(fixture_panel,h):
    p=b.prepare(fixture_panel);rec=p['cases'][f'BASELINE_PRICE_H{h}']['records'][0]
    v,beta,_,_,ids,c=b.estimate(rec,p['close'],h,'BASELINE')
    y=p['close'][h,ids]/p['close'][0,ids]-1
    assert beta==pytest.approx(b.coefficient(rec['designs'][0],y,1)[0])
    assert len(p['cases'][f'BASELINE_PRICE_H{h}']['records'])==70-h

def test_rank_scope_matched_warmup_and_blocks(fixture_panel):
    p=b.prepare(fixture_panel);base=p['cases']['BASELINE_PRICE_H20'];matched=p['cases']['ATTENUATION_ACT20_H20']
    assert base['records'][0]['date']=='0000' and matched['records'][0]['date']=='0020'
    assert base['blocks']!=matched['blocks']
    rec=matched['records'][0];assert all(len(x)==int(rec['mask'].sum()) for x in rec['designs'])

def test_global_baseline_anchor_and_paired_difference(result):
    dates=result['date_effects'];primary=result['primary']
    for h in b.s.HORIZONS:
        base=primary.query("family=='BASELINE' and horizon==@h").iloc[0];anchor=np.sign(base['mean'])
        for m in b.s.MECHANISMS:
            subset=dates.query("family=='ATTENUATION' and horizon==@h and mechanism==@m")
            assert np.all(subset.baseline_family_sign==anchor)
            assert np.allclose(subset.paired_attenuation_difference,anchor*(subset.baseline_coefficient-subset.adjusted_coefficient))

def test_all_104_slots_fixed_BH_and_raw_inference(result):
    p=result['primary'];assert len(p)==104 and p.test_id.nunique()==104
    for family,size in [('BASELINE',8),('ATTENUATION',48),('INTERACTION',48)]:
        rows=p[p.family==family];assert len(rows)==size and (rows.bh_family_size==size).all()
        assert np.allclose(rows.bh_p,b.s.bh([None if not np.isfinite(v) else v for v in rows.raw_p],size))
        for _,r in rows[rows.testable].iterrows():
            d=result['date_effects'].query('test_id==@r.test_id')
            z=d.baseline_coefficient if family=='BASELINE' else d.paired_attenuation_difference if family=='ATTENUATION' else d.interaction_coefficient
            s=b.s.hac(z,r.horizon,family)
            assert r.raw_p==pytest.approx(s['raw_p']) and r.standardized_effect==pytest.approx(s['ES']) and r.hac_lag==r.horizon-1

def test_temporal_fixed_blocks_and_mass(result):
    for key,g in result['temporal'].groupby('test_id'):
        assert len(g)==4 and list(g.block)==[1,2,3,4]
        d=result['date_effects'].query('test_id==@key');assert g.eligible_dates.sum()==len(d)
        masses=abs(g['mean']*g.finite_dates);assert np.allclose(g.absolute_contribution_share,masses/masses.sum())

def test_symbol_reconciliation_top5_and_full_refit(result):
    primary=result['primary']
    for key,g in result['concentration'].groupby('test_id'):
        row=primary.query('test_id==@key').iloc[0]
        assert g.additive_contribution.sum()==pytest.approx(row['mean'])
        order=g.sort_values(['absolute_contribution_share','symbol'],ascending=[False,True])
        assert set(g[g.top_five_removed].symbol)==set(order.head(5).symbol)
        assert g.top5_share.iloc[0]==pytest.approx(order.head(5).absolute_contribution_share.sum())
        assert g.hhi.iloc[0]==pytest.approx(sum(g.absolute_contribution_share**2))

def test_leave5_does_not_rerank(fixture_panel):
    prep=b.prepare(fixture_panel);r=prep['cases']['BASELINE_PRICE_H1']['records'][0];keep=set(range(5,16))
    v,*_=b.estimate(r,prep['close'],1,'BASELINE',keep=keep)
    y=prep['close'][1,5:]/prep['close'][0,5:]-1
    assert v==pytest.approx(b.coefficient(r['designs'][0][5:],y,1)[0])

def test_registered_schemas_and_mechanisms_only(result):
    tables={'sw11_s2_primary_summary.csv':result['primary'],'sw11_s2_date_effects.csv':result['date_effects'],'sw11_s2_temporal_stability.csv':result['temporal'],'sw11_s2_symbol_concentration.csv':result['concentration'],'sw11_s2_mechanism_dispositions.csv':result['dispositions']}
    for name,table in tables.items():assert set(table.columns)==set(b.SCHEMAS[name])
    assert len(b.FILES)==7 and set(result['dispositions'].mechanism)==set(b.s.MECHANISMS)
    assert set(result['dispositions'].disposition)<= {'NOT_TESTABLE','COUNTEREVIDENCE','CONDITIONING_SUPPORTED','EXPLANATORY_EVIDENCE','MECHANISM_SUPPORTED'}

def test_future_predictor_invariance(fixture_panel):
    changed=fixture_panel.copy();changed.loc[changed.trade_date>'0040','close']*=2
    a=b.p.predictors(fixture_panel);z=b.p.predictors(changed)
    cols=['PRICE',*b.s.MECHANISMS]
    assert np.allclose(a[a.trade_date<='0040'][cols],z[z.trade_date<='0040'][cols],equal_nan=True)

def test_real_panel_denied_offline(fixture_panel):
    real=fixture_panel.copy();real['symbol']='SPY'
    with pytest.raises(ValueError):b.analyze(real)

def test_invalid_immutable_source_rejected():
    with pytest.raises(ValueError):b.p.verified_input(b'not the certified panel')

def test_governed_authority_precedes_input(tmp_path,monkeypatch):
    path=tmp_path/'job_inputs/swing10/execution_context.json';path.parent.mkdir(parents=True);path.write_text('{}')
    monkeypatch.setenv('GITHUB_ACTIONS','true')
    with pytest.raises(ValueError,match='authority'):b.run(tmp_path)

def test_full_artifact_contract_on_synthetic_fixture(tmp_path,monkeypatch,fixture_panel):
    monkeypatch.setenv('GITHUB_ACTIONS','true')
    ids=[*b.p.DECISIONS,b.s.SUPPLEMENT,b.s.SUPPLEMENT_2,b.AUTH]
    ctx={'mwe_uuid':b.MWE,'authorization_decision_id':b.AUTH,'scientific_outcomes_authorized':True,'contract_snapshot':[{'decision_id':i,'metadata_json':{'status':'FROZEN'}} for i in ids],'materialized_inputs':[{'input_id':'synthetic','sha256':b.p.SHA,'size_bytes':b.p.SIZE}],'research_revision':'testresearch','infrastructure_revision':'testinfra','job_id':'synthetic','attempt_id':'synthetic','github_run_id':'synthetic','attempt_no':1,'github_job_id':123}
    path=tmp_path/'job_inputs/swing10/execution_context.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(ctx));source=tmp_path/'job_inputs/swing11/development.csv';source.parent.mkdir();source.write_bytes(b'EXPLICIT_SYNTHETIC_FIXTURE')
    with patch.object(b.p,'verified_input',return_value=fixture_panel):result=b.run(tmp_path)
    assert len(result['output_paths'])==7 and result['artifact'].endswith('sw11_s2_primary_summary.csv')
    manifest=json.loads((tmp_path/'research_outputs/swing11/s2b/sw11_s2_manifest.json').read_text());assert len(manifest['coefficient_registry'])==104
    for rel,meta in result['output_artifact_metadata'].items():
        blob=(tmp_path/rel).read_bytes();assert hashlib.sha256(blob).hexdigest()==meta['stored_sha256']
        logical=gzip.decompress(blob) if meta['storage_encoding']=='gzip' else blob
        assert hashlib.sha256(logical).hexdigest()==meta['logical_sha256']

def test_exact_bundle_whitelisting():
    from cloud_compute.research_revision_adapter import GOVERNED_RESEARCH_TARGETS
    assert GOVERNED_RESEARCH_TARGETS['SW11-S2B'].execution_mode=='sw11_s2b_bundle'
