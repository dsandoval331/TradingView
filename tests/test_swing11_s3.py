import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing11_s3 as s
from tr_platform.research import swing11_s3_contract as c
from tr_platform.research import swing11_s3p as p
from tests.test_swing11_s3p import frame,rows

def fixture():
    f=frame(60,135);v=p.predictors(f)
    # Deterministic synthetic members for known algebra; original ranks retained.
    for candidate in ('C0','C1','C2'):
        v[candidate+'_long']=v.symbol.isin([f'SYNTHETIC_{i:03}' for i in range(10)])
        v[candidate+'_short']=v.symbol.isin([f'SYNTHETIC_{i:03}' for i in range(30,40)])
    return f,v

def ctx():
    return dict(scientific_outcomes_authorized=True,preflight_only=False,authorization_decision_id=s.AUTH,contract_snapshot=json.loads(Path('research_protocols/swing11/SWING11_S3_EXECUTION_AUTHORITY.json').read_text()),github_job_id=123,mwe_uuid='synthetic')

@pytest.mark.parametrize('h',[5,7,10,15])
def test_known_next_open_cohort_and_daily_conservation(h):
    f,v=fixture();f.loc[f.trade_date=='001','open']*=1.07
    out=s.simulate(f,v,'S3-C0');r=out['cohorts'].query('decision_date=="000" and horizon==@h').iloc[0]
    bars=f.set_index(['trade_date','symbol']);long,short,_=p.memberships(v[v.trade_date=='000'],'S3-C0')
    ratios=lambda names:np.array([bars.loc[(f'{h:03}',x),'close']/bars.loc[('001',x),'open'] for x in names])
    known=.5*np.mean(ratios(long)-1)+.5*np.mean(1-ratios(short))
    assert r.cohort_return==pytest.approx(known) and r.dailyized_return==pytest.approx(known/h)
    a=out['accounts'].query('horizon==@h');co=out['cohorts'].query('horizon==@h')
    assert a.daily_fixed_capital_pnl.sum()==pytest.approx(co.dailyized_return.sum(),abs=1e-12)
    assert (a.active_cohorts+a.cash_sleeves).eq(h).all();assert a.active_cohorts.max()==h
    assert a.entry_turnover.sum()==pytest.approx(len(co)/h)
    assert a.iloc[-1].cumulative_fixed_capital_pnl==pytest.approx(co.dailyized_return.sum())

@pytest.mark.parametrize('candidate',c.CANDIDATES)
def test_zero_capacity_cash_no_renormalization(candidate):
    f,v=fixture();prefix=candidate[3:];v.loc[v.trade_date<'030',prefix+'_long']=False
    out=s.simulate(f,v,candidate)
    assert out['cohorts'].query('decision_date<"030"').dailyized_return.eq(0).all()
    assert out['active_rate']==pytest.approx(.75)
    a=out['accounts'];assert a.query('date<"031"').gross.eq(0).all()
    np.testing.assert_allclose(out['series'],out['contributions'].sum(axis=1))

def test_equal_family_not_best_cap():
    f,v=fixture();out=s.simulate(f,v,'S3-C0')
    expected=out['cohorts'].pivot(index='decision_date',columns='horizon',values='dailyized_return').mean(axis=1)
    np.testing.assert_allclose(out['series'],expected)

def test_leave_five_rebuilds_weights_and_cash_preserves_ranks():
    f,v=fixture();original=v.copy(deep=True);removed=[f'SYNTHETIC_{i:03}' for i in range(5)]
    out=s.simulate(f,v,'S3-C0',removed)
    assert out['cohorts'].long_N.eq(5).all() and not out['cohorts'].no_trade.any()
    pd.testing.assert_frame_equal(v,original)
    out=s.simulate(f,v,'S3-C0',removed+['SYNTHETIC_005'])
    assert out['cohorts'].no_trade.all() and not out['series'].any()

def test_relative_top_five_removed_from_both_full_refits():
    f,v=fixture();full=s.simulate(f,v,'S3-C1');base=s.simulate(f,v,'S3-C0')
    full['contributions']*=1.5;full['series']*=1.5
    info=s.infer(full['series']-base['series'])
    diagnostics,gate=s.concentration(full,base,f,v,'S3-C1','REL_S3-C1_vs_S3-C0',info)
    removed=[x['symbol'] for x in diagnostics if x['top5_removed']]
    rebuilt=s.simulate(f,v,'S3-C1',removed)['series']-s.simulate(f,v,'S3-C0',removed)['series']
    assert diagnostics[0]['leave5_effect']==pytest.approx(rebuilt.mean())
    assert sum(x['contribution'] for x in diagnostics)==pytest.approx((full['series']-base['series']).mean())

def test_four_frozen_blocks_and_zero_dates_retained():
    z=np.arange(120)/1000;dates=[f'{i:03}' for i in range(120)];blocks=[list(x) for x in np.array_split(dates,4)]
    out,gate=s.temporal(z,dates,blocks,'synthetic');assert len(out)==4 and sum(x['N'] for x in out)==120
    assert sum(x['absolute_share'] for x in out)==pytest.approx(1.)
    assert out[0]['start']=='000' and out[3]['end']=='119'

def test_known_hac_lag14_normal_and_fixed_five():
    z=np.arange(100)/1000+.01;r=s.infer(z);u=z-z.mean();n=len(z)
    variance=(u@u)/n+sum(2*(1-k/15)*(u[k:]@u[:-k])/n for k in range(1,15))
    assert r['hac_se']==pytest.approx(np.sqrt(variance/n));assert r['hac_lag']==14
    assert r['ES']==pytest.approx(z.mean()/z.std(ddof=1))
    q=c.bh_five([.01,None,.02,.1,.3]);assert q[0]==pytest.approx(.05) and q[1]==1

@pytest.mark.parametrize('field,value',[('scientific_outcomes_authorized',False),('preflight_only',True),('authorization_decision_id','wrong'),('github_job_id',None)])
def test_authority_fails_before_private_reads(field,value,tmp_path,monkeypatch):
    x=ctx();x[field]=value;path=tmp_path/'job_inputs/swing10/execution_context.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(x))
    monkeypatch.setenv('GITHUB_ACTIONS','true')
    with pytest.raises(ValueError):s.run(tmp_path)

@pytest.mark.parametrize('field',['protected_validation_authorized','s4_authorized','s5_authorized','s6_authorized'])
def test_protected_transitions_rejected(field):
    x=ctx();next(r for r in x['contract_snapshot'] if r['decision_id']==s.AUTH)['metadata_json'][field]=True
    with pytest.raises(ValueError):s.authority(x)

def test_no_local_real_execution(tmp_path,monkeypatch):
    path=tmp_path/'job_inputs/swing10/execution_context.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(ctx()));monkeypatch.delenv('GITHUB_ACTIONS',raising=False)
    with pytest.raises(ValueError,match='governed'):s.run(tmp_path)

def test_bad_contract_bytes_rejected_before_price(tmp_path,monkeypatch):
    x=ctx();x['materialized_inputs']=[{},{}];path=tmp_path/'job_inputs/swing10/execution_context.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(x));path=tmp_path/'job_inputs/swing11/s3p_contract.json';path.parent.mkdir(parents=True);path.write_bytes(b'wrong')
    monkeypatch.setenv('GITHUB_ACTIONS','true')
    with pytest.raises(ValueError,match='contract mismatch'):s.run(tmp_path)

def test_exact_nine_artifacts_end_to_end_synthetic(tmp_path,monkeypatch):
    certified_sensitivity=s.sensitivity()
    monkeypatch.setattr(s,"sensitivity",lambda:certified_sensitivity)
    f,v=fixture();dates=sorted(f.trade_date.unique())[:-15];frozen=dict(future_scientific_schemas=c.FUTURE_SCHEMAS,comparison_calendar=dates,blocks=[list(x) for x in np.array_split(dates,4)])
    cb=json.dumps(frozen).encode();x=ctx();x['materialized_inputs']=[{},{}];x['input_registration_id']='synthetic-input'
    for name,data in [('job_inputs/swing10/execution_context.json',json.dumps(x).encode()),('job_inputs/swing11/s3p_contract.json',cb),('job_inputs/swing11/development.csv',b'SYNTHETIC')]:
        pth=tmp_path/name;pth.parent.mkdir(parents=True,exist_ok=True);pth.write_bytes(data)
    monkeypatch.setenv('GITHUB_ACTIONS','true');monkeypatch.setattr(s,'CONTRACT_SIZE',len(cb));monkeypatch.setattr(s,'CONTRACT_SHA',hashlib.sha256(cb).hexdigest());monkeypatch.setattr(s,'PREDICTOR_SHA',hashlib.sha256(v.to_csv(index=False).encode()).hexdigest());monkeypatch.setattr(p.source,'verified_input',lambda b:f);monkeypatch.setattr(p,'predictors',lambda f:v)
    result=s.run(tmp_path);assert len(result['output_paths'])==9 and result['artifact'].endswith(s.FILES[0])
    manifest=json.loads((tmp_path/result['output_paths'][-1]).read_text());assert len(manifest['artifact_declarations'])==8
    for path,meta in result['output_artifact_metadata'].items():
        b=(tmp_path/path).read_bytes();assert len(b)==meta['stored_size_bytes'] and hashlib.sha256(b).hexdigest()==meta['stored_sha256']
        if path.endswith('.csv'):assert b.decode().splitlines()[0].split(',')==list(c.FUTURE_SCHEMAS[meta['logical_name']])
    primary=pd.read_csv(tmp_path/result['artifact']);assert len(primary)==5 and primary.hac_lag.eq(14).all()
    cohorts=pd.read_csv(tmp_path/result['output_paths'][1]);assert len(cohorts)==120*12
    assert not manifest['protection']['protected_validation_access']

@pytest.mark.parametrize('invalid',['open','close'])
def test_nonfinite_missing_bars_fail_closed(invalid):
    f,v=fixture();f.loc[0,invalid]=np.nan
    with pytest.raises(ValueError,match='finite'):s.simulate(f,v,'S3-C0')

def test_all_four_synthetic_sensitivities_actual_operations():
    out=s.sensitivity();assert tuple(out.case_id)==c.SENSITIVITIES and out.synthetic_only.all() and out.passed.all()

@pytest.mark.parametrize('gate',['testable','temporal','concentration','capacity','sensitivity'])
def test_missing_required_gates_no_advance(gate):
    r=rows()
    for row in r.values():row['absolute'][gate]=False
    assert c.select(r)[0]=='NO_ADVANCE'

def test_certified_preflight_remains_outcome_blind():
    assert p.guard_source(Path(p.__file__).read_text())

@pytest.mark.parametrize('changed,parent,authorized',[(False,True,True),(True,True,True),(False,False,True),(False,True,False)])
def test_worker_live_authority_and_exact_two_input_admission(tmp_path,changed,parent,authorized):
    from cloud_compute.control_plane import ControlPlaneConfig
    from cloud_compute.control_plane_worker import run_one
    x=ctx();x['scientific_outcomes_authorized']=authorized;x['input_registration_id']='synthetic-input';x['contract_input_id']='synthetic-contract'
    job=dict(job_id='synthetic-job',runner_job_id='SW11-S3',git_sha='abc',parameters_json=x)
    def fetch(config,table,filters):
        if table=='work_envelopes':
            if filters['work_envelope_id']=='eq.synthetic':return [dict(mwe_id='MWE-SW11-S3-001',status='ACTIVE')]
            return [dict(status='COMPLETE' if parent else 'ACTIVE',metadata_json={'state':'VERIFIED'})]
        out=[copy.deepcopy(v) for v in x['contract_snapshot'] if filters['decision_id']=='eq.'+v['decision_id']]
        if changed:out[0]['decision']='altered'
        return out
    with patch.dict('os.environ',{'TR_RESEARCH_SHA':'abc'}),patch('cloud_compute.control_plane_worker.runner._git_sha',return_value='abc'),patch('cloud_compute.control_plane_worker.runner.WORK_ROOT',tmp_path),patch('cloud_compute.control_plane_worker.claim_job',return_value={'job':job,'attempt_id':'synthetic-attempt','attempt_no':1}),patch('cloud_compute.control_plane._fetch_rows',side_effect=fetch),patch('cloud_compute.control_plane_worker.materialize_job_inputs',return_value=[]) as mat,patch('cloud_compute.control_plane_worker.runner.run_id',return_value=0),patch('cloud_compute.control_plane_worker._record_stream_logs'),patch('cloud_compute.control_plane_worker._persist_runner_artifacts',return_value=[{'artifact_id':'synthetic','is_primary':True}]),patch('cloud_compute.control_plane_worker.update_job'),patch('cloud_compute.control_plane_worker.update_attempt'):
        result=run_one(ControlPlaneConfig('https://example.supabase.co','fixture'))
        if changed or not parent or not authorized:assert result!=0;mat.assert_not_called()
        else:
            assert result==0;mat.assert_called_once();admitted=mat.call_args.kwargs['allowed_inputs']
            assert len(admitted)==2 and admitted[0]['sha256']==p.source.SHA and admitted[1]['sha256']==s.CONTRACT_SHA
            context=json.loads((tmp_path/'job_inputs/swing10/execution_context.json').read_text());assert context['scientific_outcomes_authorized'] is True and context['preflight_only'] is False
