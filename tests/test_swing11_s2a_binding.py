import json
import numpy as np
import pytest
from tr_platform.research import swing11_s2a_supplement as s

IDS=[f'SYNTHETIC_{i:03}' for i in range(12)]
P=np.arange(1.,13.)

def series_registry(value=-.4):
    return {h:{'test_id':f'BASELINE_PRICE_H{h}','sample_binding':'PRICE_ONLY','complete_series':True,'coefficient_series':[value,value]} for h in s.HORIZONS}

@pytest.mark.parametrize('h',s.HORIZONS)
def test_global_sign_each_horizon(h):
    registry=series_registry()
    # A matched mechanism has the opposite sign: it cannot replace the anchor.
    d,a=s.bound_paired_difference([.4,.6],[.2,.3],h,registry)
    assert np.allclose(d,[-.2,-.3]) and a==pytest.approx(.5)
    for m in s.MECHANISMS:assert s.baseline_anchor(h,registry)==-1

def test_price_sample_unrestricted_by_mechanism():
    mask,x=s.price_only_design(P,P,P+1,IDS)
    m=np.sin(P);m[:4]=np.nan
    matched,designs=s.matched_designs(P,m,P,P+1,IDS)
    assert mask.sum()==12 and matched.sum()==8
    assert all(len(a)==8 for a in designs)
    assert np.allclose(x[matched,1],designs[0][:,1])

@pytest.mark.parametrize('field',['price','current','endpoint'])
def test_baseline_finite_mask_and_original_ranks(field):
    p,a,z=P.copy(),P.copy(),P+1
    {'price':p,'current':a,'endpoint':z}[field][0]=np.nan
    mask,x=s.price_only_design(p,a,z,IDS)
    assert not mask[0] and mask.sum()==11
    assert np.allclose(x[:,1],s.ranks(p)[mask])

@pytest.mark.parametrize('binding',['MECHANISM_MATCHED','ACT20',None])
def test_sign_cannot_come_from_matched_binding(binding):
    r=series_registry();r[5]['sample_binding']=binding
    with pytest.raises(ValueError):s.baseline_anchor(5,r)

@pytest.mark.parametrize('mutation',['missing_horizon','wrong_id','incomplete','zero','nonfinite'])
def test_anchor_fail_closed(mutation):
    r=series_registry()
    if mutation=='missing_horizon':del r[1]
    elif mutation=='wrong_id':r[5]['test_id']='ATTENUATION_ACT20_H5'
    elif mutation=='incomplete':r[5]['complete_series']=False
    elif mutation=='zero':r[5]['coefficient_series']=[-.2,.2]
    else:r[5]['coefficient_series']=[np.nan,np.inf]
    with pytest.raises(ValueError):s.baseline_anchor(5,r)

def test_baseline_blocks_not_mechanism_warmup():
    dates=list(range(40));blocks=s.baseline_blocks(dates)
    matched=s.baseline_blocks(dates[20:])
    assert [len(b) for b in blocks]==[10]*4
    assert list(np.concatenate(blocks))==dates
    assert blocks[0][0]==0 and matched[0][0]==20

@pytest.mark.parametrize('dates',[[2,1],[1,1]])
def test_blocks_reject_nonchronological(dates):
    with pytest.raises(ValueError):s.baseline_blocks(dates)

def test_full_leave5_fixed_price_only_sample_and_ranks():
    mask,x=s.price_only_design(P,P,P+1,IDS);y=.3-.7*x[:,1]
    effect,c=s.ols_contributions(x,y,IDS,1)
    result,diag=s.leave_five_refit([x],[y],IDS,1,[c])
    assert effect==pytest.approx(-.7) and result[0]==pytest.approx(-.7)
    assert len(diag['top5'])==5
    assert np.allclose(x[:,1],s.ranks(P))

def test_registry_fixed_families_and_exact_binding():
    rows=s.final_registry();assert len(rows)==104
    assert len({r['test_id'] for r in rows})==104
    assert {f:sum(r['family']==f for r in rows) for f in ['BASELINE','ATTENUATION','INTERACTION']}=={'BASELINE':8,'ATTENUATION':48,'INTERACTION':48}
    for r in rows:
        if r['family']=='BASELINE':assert r['mechanism'] is None and r['sample_binding']=='PRICE_ONLY'
        else:assert r['sample_binding']=='MECHANISM_MATCHED'
        if r['family']=='ATTENUATION':assert r['sign_source']==f"BASELINE_PRICE_H{r['horizon']}"

def test_schemas_seven_outputs_with_sample_binding():
    schemas=s.final_schemas();assert len(schemas)==7
    for name in ['sw11_s2_primary_summary.csv','sw11_s2_date_effects.csv']:
        assert {'sample_binding','baseline_family_test_id','baseline_family_sign_source'}<=set(schemas[name])
    assert s.certify_binding()['S2B_readiness']=='READY_FOR_CANONICAL_AUTHORIZATION'

def test_real_symbols_rejected():
    with pytest.raises(ValueError):s.price_only_design(P,P,P+1,['SPY']*12)

def test_final_runner_zero_sources_and_manifest(tmp_path,monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS','true')
    ids=[s.SUPPLEMENT,s.SUPPLEMENT_2,'7c6279c1-a86d-4336-a08d-244bb5e005b4','11407ad3-97cd-459e-b78e-9162a115b8e4','f240f40d-65a0-40dd-91dc-bdf722431e2b']
    context={'mwe_uuid':s.MWE,'synthetic_only':True,'scientific_outcomes_authorized':False,'final_binding_certification':True,'materialized_inputs':[],'contract_snapshot':[{'decision_id':i,'metadata_json':{'status':'FROZEN'}} for i in ids]}
    path=tmp_path/'job_inputs/swing10/execution_context.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(context))
    result=s.run(tmp_path);assert len(result['output_paths'])==4
    manifest=json.loads((tmp_path/result['output_paths'][-1]).read_text())
    assert not manifest['real_forward_outcomes_computed'] and len(manifest['artifacts'])==3
    context['materialized_inputs']=['DENIED'];path.write_text(json.dumps(context))
    with pytest.raises(ValueError):s.run(tmp_path)
