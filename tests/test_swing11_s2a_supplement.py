import copy
import json
import numpy as np
import pytest
from tr_platform.research import swing11_s2a_supplement as s

IDS=[f"SYNTHETIC_{i:03}" for i in range(30)]

def rows():
    return {h:{"testable":True} for h in s.HORIZONS}

def qualify(r,h,kind):
    if kind=="C":r[h].update(interaction_primary=True,interaction_mean=.3,interaction_temporal=True,interaction_concentration=True)
    else:r[h].update(attenuation_primary=True,attenuation_fdr=True,d_mean=.3,d_ES=.3,ATTEN=.3,attenuation_temporal=True,attenuation_concentration=True,baseline_primary=True)

def test_snapshot_prospective_and_complete():
    from pathlib import Path
    d=json.loads(Path('research_protocols/swing11/SWING11_S1B_SUPPLEMENT_1.persisted.json').read_text())
    assert d['decision_id']==s.SUPPLEMENT
    assert d['metadata_json']['status']=='FROZEN' and not d['metadata_json']['s2b_authorized']
    assert 'paired attenuation-difference' in d['decision']

def test_exact_rank_ties_and_before_endpoint_mask():
    assert np.allclose(s.ranks([1,2,2,4]),[-.5,.25,.25,1])
    p=np.arange(30);m=np.sin(p);a=np.ones(30);z=np.ones(30);z[0]=np.nan
    mask,x=s.matched_designs(p,m,a,z,IDS)
    assert mask.sum()==29 and not mask[0]
    assert x[0][0,1]==s.ranks(p)[1] # ranks never recomputed on response sample
    assert all(len(v)==29 for v in x) and np.allclose(x[2][:,3],x[2][:,1]*x[2][:,2])

@pytest.mark.parametrize('h',s.HORIZONS)
def test_registered_calendar_return(h):
    closes=np.arange(1,32)[:,None]*np.ones((1,30))
    assert np.allclose(s.endpoint_return(closes,2,h,IDS),(3+h)/3-1)
    changed=closes.copy();changed[3+h:]=1e8
    assert np.allclose(s.endpoint_return(changed,2,h,IDS),s.endpoint_return(closes,2,h,IDS))

@pytest.mark.parametrize('ids',[['AAPL'],['SYNTHETIC_0','SPY'],[]])
def test_real_outcomes_denied(ids):
    with pytest.raises(ValueError):s.endpoint_return([[1],[2]],0,1,ids)

def test_endpoint_no_alternate_or_imputation():
    with pytest.raises(ValueError):s.endpoint_return([[1],[2]],0,2,['SYNTHETIC_0'])
    with pytest.raises(ValueError):s.endpoint_return([[1],[2]],0,4,['SYNTHETIC_0'])
    assert np.isnan(s.endpoint_return([[0],[2]],0,1,['SYNTHETIC_0'])[0])

def test_n_four_full_rank_identification():
    x=np.array([[1,-1,-1,1],[1,-1,1,-1],[1,1,-1,-1],[1,1,1,1]],float)
    y=x@np.arange(4);b,c=s.ols_contributions(x,y,IDS[:4],3)
    assert b==pytest.approx(3) and c.sum()==pytest.approx(3)
    with pytest.raises(ValueError):s.identify(x[:3])
    x[:,3]=x[:,1]
    with pytest.raises(ValueError):s.identify(x)

def test_known_paired_attenuation_not_nonlinear_ratio():
    b0=np.array([-.1,-.2,-.3]);b1=np.array([-.02,-.1,-.27])
    d,a=s.paired_difference(b0,b1,[-.2]*3)
    assert np.allclose(d,b1-b0) and a==pytest.approx(1-abs(b1.mean())/abs(b0.mean()))
    assert not np.allclose(d,1-abs(b1)/abs(b0))

@pytest.mark.parametrize('base',[[],[0,0],[np.nan,np.inf]])
def test_baseline_family_zero_unavailable(base):
    with pytest.raises(ValueError):s.paired_difference([-.1],[-.05],base)

@pytest.mark.parametrize('base',[0,1e-12,-1e-12])
def test_near_zero_matched_baseline(base):
    with pytest.raises(ValueError):s.paired_difference([base],[base/2],[-.1])

def test_paired_dates_identical_finite_intersection():
    d,a=s.paired_difference([-.2,np.nan,-.4],[-.1,-.1,-.2],[-.1])
    assert np.allclose(d,[.1,.2]) and a==pytest.approx(.5)
    with pytest.raises(ValueError):s.paired_difference([-.1],[-.1,-.2],[-.1])

@pytest.mark.parametrize('h',s.HORIZONS)
@pytest.mark.parametrize('kind',['BASELINE','ATTENUATION','INTERACTION'])
def test_hac_exact_known_fixture(h,kind):
    z=.15+.07*np.sin(np.arange(60))+.03*np.cos(np.arange(60)*.2)
    r=s.hac(z,h,kind);u=z-z.mean();n=len(z);L=h-1
    expected=(u@u+sum(2*(1-k/(L+1))*(u[k:]@u[:-k]) for k in range(1,L+1)))/n**2
    assert r['testable'] and r['hac_lag']==L
    assert r['hac_se']==pytest.approx(np.sqrt(expected))
    assert r['ES']==pytest.approx(z.mean()/z.std(ddof=1))
    assert r['ci_high']-r['mean']==pytest.approx(1.959963984540054*r['hac_se'])
    assert s.hac(-z,h,kind)['raw_p']==pytest.approx(r['raw_p']) # two-sided normal

@pytest.mark.parametrize('h',s.HORIZONS)
def test_minimum_count_exact(h):
    n=max(20,h+2)
    assert not s.hac(np.arange(n-1),h,'INTERACTION')['testable']
    assert s.hac(np.arange(n),h,'INTERACTION')['testable']

@pytest.mark.parametrize('z',[[0]*30,[np.nan]*30,[1e-13,-1e-13]*20])
def test_attenuation_variance_fails_closed(z):
    r=s.hac(z,1,'ATTENUATION');assert not r['testable'] and r['bh_slot_p']==1 and r['raw_p'] is None

@pytest.mark.parametrize('n',[8,48])
def test_fixed_bh_and_unavailable(n):
    p=[.001,.002]+[None]*(n-2);q=s.bh(p,n)
    assert q[0]==pytest.approx(n*.001/1) and q[1]==pytest.approx(n*.002/2)
    assert np.all(q[2:]==1)
    with pytest.raises(ValueError):s.bh(p[:-1],n)
    with pytest.raises(ValueError):s.bh([-1]*n,n)

@pytest.mark.parametrize('kind,mean,es,atten',[('BASELINE',-.3,-.2,None),('ATTENUATION',.3,.2,.25),('INTERACTION',-.3,-.2,None),('INTERACTION',.3,.2,None)])
def test_material_fdr_boundaries(kind,mean,es,atten):
    assert s.primary_gate(kind,mean,es,.05,atten)
    assert not s.primary_gate(kind,mean,es,.05000001,atten)
    assert not s.primary_gate(kind,0,es,.01,atten)
    assert not s.primary_gate(kind,mean,es*.999,.01,atten)
    assert not s.primary_gate(kind,mean,None,.01,atten)

def test_wrong_sign_and_atten_boundary():
    assert not s.primary_gate('BASELINE',.3,.3,.01)
    assert not s.primary_gate('ATTENUATION',-.3,-.3,.01,.5)
    assert not s.primary_gate('ATTENUATION',.3,.3,.01,.249999)

@pytest.mark.parametrize('kind,mean',[('BASELINE',-.3),('ATTENUATION',.3),('INTERACTION',-.3)])
def test_temporal_three_four_and_mass_boundaries(kind,mean):
    blocks=[dict(available=True,mean=mean,N=10,ATTEN=.2) for _ in range(4)]
    assert s.temporal_gate(kind,mean,blocks)
    blocks[3]['mean']=-mean;assert s.temporal_gate(kind,mean,blocks)
    blocks[2]['mean']=-mean;assert not s.temporal_gate(kind,mean,blocks)
    blocks=[dict(available=True,mean=mean*k,N=10,ATTEN=.2) for k in [3,1,1,1]]
    assert s.temporal_gate(kind,mean,blocks)
    blocks[0]['mean']*=1.00001;assert not s.temporal_gate(kind,mean,blocks)
    blocks[0]['available']=False;assert not s.temporal_gate(kind,mean,blocks)

def test_temporal_atten_description_and_zero_denominator():
    b=[dict(available=True,mean=.1,N=10,ATTEN=0) for _ in range(4)]
    assert not s.temporal_gate('ATTENUATION',.1,b)
    assert not s.temporal_gate('INTERACTION',.1,[dict(available=True,mean=0,N=10) for _ in range(4)])

@pytest.mark.parametrize('kind,mean',[('BASELINE',-.3),('ATTENUATION',.3),('INTERACTION',-.3)])
def test_concentration_standardized_75_percent(kind,mean):
    assert s.concentration_gate(kind,mean,mean,.4,.1,.2)
    assert not s.concentration_gate(kind,mean,mean,.4,.099999,.2)
    assert not s.concentration_gate(kind,mean,-mean,.4,.4,.2)
    assert not s.concentration_gate(kind,mean,None,.4,.4,.2)

def test_zero_leave_interaction_no_reversal_but_es_loss_fails():
    assert not s.concentration_gate('INTERACTION',.3,0,.4,0)
    assert not s.concentration_gate('ATTENUATION',.3,.3,.4,.4,0)

def test_complete_leave_refit_not_contribution_subtraction():
    p=np.linspace(-1,1,30);m=np.cos(np.arange(30));x=np.column_stack([np.ones(30),p,m,p*m]);ys=[x@np.array([1,-.2,.3,.4])+i*np.sin(np.arange(30))*.001 for i in range(25)]
    cs=[s.ols_contributions(x,y,IDS,3)[1] for y in ys]
    leave,diag=s.leave_five_refit([x]*25,ys,IDS,3,cs)
    keep=[i for i in range(30) if i not in diag['top5']]
    assert np.allclose(leave,[np.linalg.lstsq(x[keep],y[keep],rcond=None)[0][3] for y in ys])
    assert diag['hhi']>0 and diag['top1_share']<=diag['top5_share']<=diag['top10_share']
    assert np.mean([c.sum() for c in cs])==pytest.approx(diag['contributions'].sum())

def test_symbol_tie_break_and_zero_contributions():
    ids=IDS[::-1];r=s.aggregate_contributions(np.ones((3,30)),ids)
    assert [ids[i] for i in r['top5']]==sorted(ids)[:5]
    with pytest.raises(ValueError):s.aggregate_contributions(np.zeros((3,30)),IDS)

def test_registered_adjacency():
    p={h:False for h in s.HORIZONS};p[1]=p[3]=True
    assert not any(s.adjacency(p).values())
    p[2]=True;assert all(s.adjacency(p)[h] for h in [1,2,3])
    with pytest.raises(ValueError):s.adjacency({1:True})

@pytest.mark.parametrize('case',['NOT_TESTABLE','COUNTEREVIDENCE','CONDITIONING_SUPPORTED','EXPLANATORY_EVIDENCE','MECHANISM_SUPPORTED'])
def test_every_disposition(case):
    r=rows()
    if case=='NOT_TESTABLE':r={h:{'testable':False} for h in s.HORIZONS}
    elif case=='CONDITIONING_SUPPORTED':qualify(r,5,'C');qualify(r,7,'C')
    elif case=='EXPLANATORY_EVIDENCE':qualify(r,5,'A');qualify(r,7,'A')
    elif case=='MECHANISM_SUPPORTED':qualify(r,5,'A');qualify(r,7,'A');r[5]['ATTEN']=r[7]['ATTEN']=.10;r[5]['attenuation_primary']=r[7]['attenuation_primary']=False
    assert s.disposition(r)[0]==case

def test_conditioning_precedence_secondary_explanation_retained_in_gates():
    r=rows()
    for h in [5,7]:qualify(r,h,'C');qualify(r,h,'A')
    assert s.disposition(r)[0]=='CONDITIONING_SUPPORTED'
    assert all(r[h]['attenuation_primary'] for h in [5,7])

def test_mechanism_weak_interaction_robustness_and_sign():
    r=rows();qualify(r,5,'C');qualify(r,7,'C');r[7]['interaction_temporal']=False
    assert s.disposition(r)[0]=='MECHANISM_SUPPORTED'
    r[7]['interaction_mean']=-.3;assert s.disposition(r)[0]=='COUNTEREVIDENCE'

def test_individual_unavailable_not_mechanism_not_testable():
    r={h:{'testable':False} for h in s.HORIZONS};r[5]={'testable':True}
    assert s.disposition(r)[0]=='COUNTEREVIDENCE'

def test_counterevidence_negative_and_insufficient_reasons():
    r=rows();r[5].update(ATTEN=-.1,d_mean=-.1);r[7].update(ATTEN=-.2,d_mean=0)
    assert s.disposition(r)[1]=='NEGATIVE_ATTENUATION'
    r=rows();r[5]['interaction_fdr']=True;assert s.disposition(r)[1]=='INSUFFICIENT_REGISTERED_SUPPORT'

def test_scientific_schemas_exact_seven_one_primary():
    assert len(s.SCIENTIFIC_SCHEMAS)==7 and list(s.SCIENTIFIC_SCHEMAS)[0]=='sw11_s2_primary_summary.csv'
    assert all(len(v)==len(set(v)) for v in s.SCIENTIFIC_SCHEMAS.values())
    for field in ['bh_slot_p','standardized_effect','hac_lag','concentration_gate']:assert field in s.SCIENTIFIC_SCHEMAS['sw11_s2_primary_summary.csv']
    assert s.certify()['scientific_execution_enabled'] is False

def test_runner_no_materialization_and_context_guards(tmp_path,monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS','true');p=tmp_path/'job_inputs/swing10/execution_context.json';p.parent.mkdir(parents=True)
    p.write_text(json.dumps({'mwe_uuid':s.MWE,'synthetic_only':True,'scientific_outcomes_authorized':False,'materialized_inputs':[{'path':'protected'}]}))
    with pytest.raises(ValueError):s.run(tmp_path)
    p.write_text(json.dumps({'mwe_uuid':s.MWE,'synthetic_only':True,'scientific_outcomes_authorized':False,'materialized_inputs':[],'contract_snapshot':[{'decision_id':x} for x in [s.SUPPLEMENT,'7c6279c1-a86d-4336-a08d-244bb5e005b4','11407ad3-97cd-459e-b78e-9162a115b8e4','f240f40d-65a0-40dd-91dc-bdf722431e2b']]}))
    assert len(s.run(tmp_path)['output_paths'])==3

def test_complete_paired_symbol_contributions_reconcile_and_leave_refits():
    p=np.linspace(-1,1,30);m=np.sin(np.arange(30))
    x0=np.column_stack([np.ones(30),p]);x1=np.column_stack([np.ones(30),p,m])
    y=-.4*p+.2*m+.03*np.cos(np.arange(30))
    b0,c0=s.ols_contributions(x0,y,IDS,1);b1,c1=s.ols_contributions(x1,y,IDS,1)
    d,atten=s.paired_difference([b0],[b1],[b0]);cd=np.sign(b0)*(c0-c1)
    assert cd.sum()==pytest.approx(d[0])
    top=s.aggregate_contributions([cd],IDS)['top5'];keep=[i for i in range(30) if i not in top];ids=[IDS[i] for i in keep]
    l0,_=s.ols_contributions(x0[keep],y[keep],ids,1);l1,_=s.ols_contributions(x1[keep],y[keep],ids,1)
    ld,la=s.paired_difference([l0],[l1],[l0]);assert ld[0]==pytest.approx(np.sign(l0)*(l0-l1))
    assert la==pytest.approx(1-abs(l1)/abs(l0))

def test_worker_synthetic_certification_never_materializes_market_sources(tmp_path):
    from unittest.mock import patch
    from cloud_compute.control_plane import ControlPlaneConfig
    from cloud_compute.control_plane_worker import run_one
    from pathlib import Path
    authority=json.loads(Path('research_protocols/swing11/SWING11_S1_FROZEN_SNAPSHOT.json').read_text())
    # Snapshot file is the original complete list.
    original=authority if isinstance(authority,list) else authority.get('decisions')
    supplement=json.loads(Path('research_protocols/swing11/SWING11_S1B_SUPPLEMENT_1.persisted.json').read_text())
    snapshot=original+[supplement]
    job={'job_id':'synthetic-cert-job','runner_job_id':'SW11-S2A-CERT','git_sha':'abc','parameters_json':{'mwe_uuid':s.MWE,'synthetic_only':True,'scientific_outcomes_authorized':False,'contract_snapshot':snapshot}}
    def fetch(config,table,filters):
        if table=='research_job_inputs':return []
        return [x for x in snapshot if filters['decision_id']=='eq.'+x['decision_id']]
    with patch.dict('os.environ',{'TR_RESEARCH_SHA':'abc'}),patch('cloud_compute.control_plane_worker.runner._git_sha',return_value='abc'),patch('cloud_compute.control_plane_worker.runner.WORK_ROOT',tmp_path),patch('cloud_compute.control_plane_worker.claim_job',return_value={'job':job,'attempt_id':'cert-attempt','attempt_no':1}),patch('cloud_compute.control_plane._fetch_rows',side_effect=fetch),patch('cloud_compute.control_plane_worker.materialize_job_inputs') as materialize,patch('cloud_compute.control_plane_worker.runner.run_id',return_value=0),patch('cloud_compute.control_plane_worker._record_stream_logs'),patch('cloud_compute.control_plane_worker._persist_runner_artifacts',return_value=[{'artifact_id':'cert-output','is_primary':True}]),patch('cloud_compute.control_plane_worker.update_job'),patch('cloud_compute.control_plane_worker.update_attempt'):
        assert run_one(ControlPlaneConfig('https://example.supabase.co','fixture'))==0
        materialize.assert_not_called()
    context=json.loads((tmp_path/'job_inputs/swing10/execution_context.json').read_text())
    assert context['synthetic_only'] and context['materialized_inputs']==[]
