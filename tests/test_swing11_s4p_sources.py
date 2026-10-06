import hashlib
import json
from pathlib import Path
import pytest
from tr_platform.research import swing11_s4p as s

def context():
    return dict(mwe_uuid=s.MWE,parent_mwe_uuid=s.PARENT,selected_architecture='S3-C0_PRICE_ONLY',
      preflight_only=True,scientific_outcomes_authorized=False,protected_validation_authorized=False,
      source_certification=True,source_option='A_FIRST',job_id='synthetic',attempt_id='synthetic',
      github_run_id='synthetic',research_revision='a'*40,infrastructure_revision='b'*40,
      contract_snapshot=[{'decision_id':s.SOURCE_AUTHORITY,'metadata_json':{'state':'FROZEN',
       'source_certification_option':'A_FIRST','s4_development_outcome_exposure_authorized':False}}])

@pytest.mark.parametrize('key,value', [('source_option','B'),('source_certification',False),
 ('scientific_outcomes_authorized',True),('protected_validation_authorized',True),
 ('selected_architecture','S3-C1_PRICE_RV20_CONDITIONED'),('inputs',[{'price':1}])])
def test_source_boundary(key,value):
    c=context();c[key]=value
    with pytest.raises(ValueError):s.source_guard(c)

def test_source_authority_required():
    c=context();c['contract_snapshot']=[]
    with pytest.raises(ValueError):s.source_guard(c)

@pytest.mark.parametrize('url',['https://api.massive.com/v2/aggs/ticker/MSFT/range/1/day/2025-02-03/2025-03-03',
 'https://api.massive.com/benzinga/v1/earnings?apiKey=bad','https://example.com',
 'https://api.massive.com/stocks/v1/short-interest'])
def test_closed_request_registry(url):
    with pytest.raises(ValueError,match='closed source'):s.source_request(url)

@pytest.mark.parametrize('status',[401,403,429,500,None])
def test_failure_body_never_persisted(status):
    r=s.project_probe('earnings',status,b'{"error":"SECRET"}',('date',),'SECRET')
    assert 'SECRET' not in json.dumps(r)
    assert not r['rows_projected']

def test_projection_excludes_outcomes_and_sensitive_extra():
    raw=json.dumps({'results':[{'date':'2025-04-30','actual_eps':9,'actual_revenue':999,
      'return':.2,'apiKey':'SECRET','last_updated':'2026-01-01'}],'next_url':'SECRET'}).encode()
    r=s.project_probe('earnings',200,raw,('date','last_updated'),'SECRET')
    assert r['rows_projected']==[{'date':'2025-04-30','last_updated':'2026-01-01'}]
    assert all(x not in json.dumps(r) for x in ('SECRET','actual_eps','actual_revenue'))
    assert r['access']=='AVAILABLE_ENDPOINT_ONLY'

def test_credential_projection_fail_closed():
    with pytest.raises(ValueError,match='credential'):
        s.project_probe('earnings',200,b'{"results":[{"date":"SECRET"}]}',('date',),'SECRET')

@pytest.mark.parametrize('date',['2025-02-02','2026-08-28','2026-10-06'])
def test_source_date_boundary(date):
    with pytest.raises(ValueError,match='outside'):
        s.project_probe('earnings',200,json.dumps({'results':[{'date':date}]}).encode(),('date',),'secret')

def test_no_current_date_means_absence():
    r=s.project_probe('splits',200,b'{"results":[]}',('date',),'secret')
    assert r['access']=='AVAILABLE_ENDPOINT_ONLY'
    assert r['projected_count']==0
    assert 'complete' not in r

def test_notice_hash_and_limited_timestamp_claim():
    body=b'<p>April 9, 2025 Microsoft will publish after the close of the market April 30, 2025.</p>'
    r=s.notice_evidence(200,body)
    assert r['raw_sha256']==hashlib.sha256(body).hexdigest()
    assert r['publication_time']=='UNKNOWN'
    assert not r['universe_completeness'] and not r['revisions_complete']
    assert r['earliest_conservative_daily_admission']=='2025-04-10'

def test_notice_missing_required_text_unavailable():
    assert s.notice_evidence(200,b'<p>earnings</p>')['certification']=='UNAVAILABLE'

def test_cashflow_conservation_and_insufficient_funding():
    r=s.funding_cashflows(cash=100,long_reserve=40,short_collateral=40,fees=2,dividend_debit=1)
    assert r['remaining_cash']==17 and r['fully_funded']
    assert not r['short_proceeds_reinvested']
    assert not s.funding_cashflows(cash=80,long_reserve=40,short_collateral=40,fees=1,dividend_debit=1)['fully_funded']

@pytest.mark.parametrize('x',[-1,float('nan'),float('inf')])
def test_cashflow_invalid(x):
    with pytest.raises(ValueError):s.funding_cashflows(cash=x,long_reserve=0,short_collateral=0,fees=0,dividend_debit=0)

def test_source_run_immutable_schema_no_prices_or_secret(tmp_path,monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS','true');monkeypatch.setenv('MASSIVE_API_KEY','SECRET')
    calls=[]
    def fake(url,**kw):
        calls.append(url)
        if url==s.NOTICE_URL:return 200,b'<p>April 9, 2025 April 30, 2025 after the close of the market</p>'
        return 403,b'SECRET'
    monkeypatch.setattr(s,'source_request',fake)
    p=tmp_path/'job_inputs/swing10';p.mkdir(parents=True)
    (p/'execution_context.json').write_text(json.dumps(context()))
    result=s.run(tmp_path)
    assert len(calls)==4 and len(result['output_paths'])==6
    docs={Path(x).name:json.loads((tmp_path/x).read_text()) for x in result['output_paths']}
    assert set(docs)==set(s.SOURCE_FILES)
    alltext=json.dumps(docs)
    assert 'SECRET' not in alltext and 'actual_eps' not in alltext
    gates=docs[s.SOURCE_FILES[4]]
    assert not gates['source_option_a_certified'] and not gates['new_s4_outcomes_exposed']
    assert not gates['option_b_authorized'] and len(gates['stress_views'])==12
    assert gates['frozen_candidate_registry']==['S4-TIME-5','S4-TIME-7','S4-TIME-10']
    for a in docs[s.SOURCE_FILES[-1]]['artifact_inventory']:
        b=(tmp_path/'research_outputs/swing11/s4p_option_a'/a['name']).read_bytes()
        assert hashlib.sha256(b).hexdigest()==a['sha256'] and len(b)==a['size_bytes']

def test_missing_credential_not_network_access(tmp_path,monkeypatch):
    monkeypatch.delenv('MASSIVE_API_KEY',raising=False);monkeypatch.delenv('TR_MASSIVE_API_KEY',raising=False)
    calls=[]
    monkeypatch.setattr(s,'source_request',lambda url,**kw:(calls.append(url) or (403,b'')))
    s.run_source_certification(tmp_path,context())
    assert calls==[s.NOTICE_URL]

def test_original_contract_still_ten_files():
    assert len(s.FILES)==10 and len(s.SOURCE_FILES)==6
    assert set(s.FILES).isdisjoint(s.SOURCE_FILES)
