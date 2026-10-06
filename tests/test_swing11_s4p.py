import ast
import copy
import json
from datetime import date,timedelta
from pathlib import Path
import pytest
from tr_platform.research import swing11_s4p as p

def context():
    return {'mwe_uuid':p.MWE,'parent_mwe_uuid':p.PARENT,'selected_architecture':'S3-C0_PRICE_ONLY','preflight_only':True,'scientific_outcomes_authorized':False,'protected_validation_authorized':False}

def gates():
    keys=('testable','direction','materiality','FDR','temporal','concentration','leave_five','capacity','holding','cost_stress','earnings','borrow','funding','integrity')
    return {f'S4-TIME-{h}':dict.fromkeys(keys,True) for h in (5,7,10)}

def test_ranks_average_ties():assert p.finite_rank({'A':1,'B':1,'C':2})=={'A':.5,'B':.5,'C':1}
def test_finite_eligibility():assert p.finite_rank({'A':1,'B':float('nan'),'C':0,'D':-1})=={'A':1}
def test_tail_minimum():assert p.membership({str(i):i+1 for i in range(20)})['active'] is False
def test_inclusive_tail_boundary():assert len(p.membership({str(i):i+1 for i in range(25)})['long'])==5
def test_all_ties_cash():assert not p.membership(dict.fromkeys(range(50),100))['active']
def test_future_invariance():
    today={str(i):i+1 for i in range(30)};before=p.membership(today)
    future={str(i):10000-i for i in range(30)};future['0']=1e20
    assert before==p.membership(today)
@pytest.mark.parametrize('h',[5,7,10])
def test_session_timing(h):
    cal=[str(date(2025,1,1)+timedelta(days=i)) for i in range(20)]
    assert p.schedule(cal,0,h)==(cal[1],cal[h])
@pytest.mark.parametrize('h',[1,15,20])
def test_holding_cap(h):
    with pytest.raises(ValueError):p.schedule(['2025-01-01']*30,0,h)
def test_calendar_endpoint_capacity():
    with pytest.raises(ValueError):p.schedule(['2025-01-01'],0,10)
def test_protected_calendar():
    with pytest.raises(ValueError):p.schedule([str(date(2026,8,20)+timedelta(days=i)) for i in range(20)],0,5)
def test_calendar_duplicates():
    with pytest.raises(ValueError):p.schedule(['2025-01-01']*20,0,5)
def earnings():return {'complete':True,'observed_at':'2025-01-01T20:00:00Z','events':[]}
def safe(r):return p.earnings_safe(r,'2025-01-01T21:00:00Z','2025-01-02T14:30:00Z','2025-01-10T21:00:00Z')
def test_unknown_earnings_fail():assert safe(None) is False
def test_incomplete_earnings_fail():assert safe({'complete':False}) is False
def test_complete_known_empty_pass():assert safe(earnings()) is True
def test_later_observation_fail():
    r=earnings();r['observed_at']='2025-01-02T00:00:00Z';assert safe(r) is False
def test_holding_event_fail():
    r=earnings();r['events']=[{'expected_at':'2025-01-07T13:00:00Z','published_at':'2024-12-15T12:00:00Z'}];assert safe(r) is False
def test_unpublished_event_fail():
    r=earnings();r['events']=[{'expected_at':'2025-01-07T13:00:00Z'}];assert safe(r) is False
def test_later_publication_fail():
    r=earnings();r['events']=[{'expected_at':'2025-01-15T13:00:00Z','published_at':'2025-01-03T12:00:00Z'}];assert safe(r) is False
def test_no_timezone_fail():
    r=earnings();r['observed_at']='2025-01-01T20:00:00';assert safe(r) is False
@pytest.mark.parametrize('h',[5,7,10])
def test_sleeve_conservation(h):
    r=p.allocation(True,h,.9,.05);assert sum(r.values())==pytest.approx(1/h);assert r['long']==r['short'];assert r['long']+r['short']<=.05
def test_no_trade_cash():assert p.allocation(False,5,0,1)=={'long':0,'short':0,'cash':.2}
def test_no_gross_room_cash():assert p.allocation(True,5,1.1,1)['cash']==.2
def test_cost_accounting():assert p.cost(1,25,.5,.05,10)==pytest.approx(.0025+.5*.05*10/365)
def test_negative_cost_rejected():
    with pytest.raises(ValueError):p.cost(1,-5,.5,.05,10)
def test_precedence_shortest():assert p.select(gates())=='S4-TIME-5'
def test_precedence_next():
    g=gates();g['S4-TIME-5']['FDR']=False;assert p.select(g)=='S4-TIME-7'
def test_no_advance_earnings():
    g=gates()
    for v in g.values():v['earnings']=False
    assert p.select(g)=='NO_ADVANCE'
def test_missing_gate_failclosed():
    g=gates();del g['S4-TIME-5']['borrow']
    with pytest.raises(ValueError):p.select(g)
def test_unknown_gate_failclosed():
    g=gates();g['S4-TIME-5']['FDR']=None;assert p.select(g)=='S4-TIME-7'
def test_extra_candidate_denied():
    g=gates();g['S4-TIME-15']=g['S4-TIME-5']
    with pytest.raises(ValueError):p.select(g)
def test_no_s4_exposure_authority():
    c=context();c['scientific_outcomes_authorized']=True
    with pytest.raises(ValueError):p.guard(c)
def test_protected_authority_denied():
    c=context();c['protected_validation_authorized']=True
    with pytest.raises(ValueError):p.guard(c)
def test_rv20_parent_denied():
    c=context();c['selected_architecture']='S3-C1_PRICE_RV20_CONDITIONED'
    with pytest.raises(ValueError):p.guard(c)
def test_data_input_denied():
    c=context();c['input_provenance']=[{'sha':'real'}]
    with pytest.raises(ValueError):p.guard(c)
@pytest.mark.parametrize('field',['forward_return','future_return','pnl','effect','p_value','win_rate'])
def test_outcome_fields_denied(field):
    c=context();c['source_payload']={field:[]}
    with pytest.raises(ValueError):p.guard(c)
def test_exact_artifact_contract():assert len(p.FILES)==10 and len(set(p.FILES))==10
def test_proposal_not_frozen():assert p.PROPOSAL['status']=='DRAFT_REQUIRES_CANONICAL_PROSPECTIVE_APPROVAL'
def test_no_future_return_primitive():
    tree=ast.parse(Path(p.__file__).read_text())
    calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
    assert not set(calls)&{'shift','pct_change','read_csv','read_parquet'}
def test_real_runner_refuses_local(tmp_path):
    target=tmp_path/'job_inputs/swing10';target.mkdir(parents=True);(target/'execution_context.json').write_text(json.dumps(context()))
    with pytest.raises(ValueError,match='governed'):p.run(tmp_path)
