import json,pytest
from tr_platform.research import swing11_s4p as m
from cloud_compute.s4p_archive_schedule import validate_activation

def context():
 return {'mwe_uuid':m.MWE,'parent_mwe_uuid':m.PARENT,'selected_architecture':'S3-C0_PRICE_ONLY','preflight_only':True,'scientific_outcomes_authorized':False,'protected_validation_authorized':False,'prospective_archival':True,'source_option':'B','archive_symbols':list(m.ARCHIVE_SYMBOLS),'contract_snapshot':[{'decision_id':m.ARCHIVE_AUTHORITY,'metadata_json':{'state':'FROZEN','prospective_archival_authorized':True,'exact_future_boundary_frozen':False,'future_price_access_authorized':False,'protected_validation_authorized':False,'s4_development_outcome_exposure_authorized':False}}]}

def test_valid_guard():m.archive_guard(context())
@pytest.mark.parametrize('k',['price_rows','forward_returns','boundary_assignments','validation_input'])
def test_deny_outcome_fields(k):
 c=context();c[k]=[]
 with pytest.raises(ValueError):m.archive_guard(c)
@pytest.mark.parametrize('k',['exact_future_boundary_frozen','future_price_access_authorized','protected_validation_authorized','s4_development_outcome_exposure_authorized'])
def test_authority_boundary(k):
 c=context();c['contract_snapshot'][0]['metadata_json'][k]=True
 with pytest.raises(ValueError):m.archive_guard(c)
def test_no_authority():
 c=context();c['contract_snapshot']=[]
 with pytest.raises(ValueError):m.archive_guard(c)
def test_modes_exclusive():
 c=context();c['source_certification']=True
 with pytest.raises(ValueError):m.archive_guard(c)
@pytest.mark.parametrize('count',[0,111,113])
def test_universe_count(count):
 c=context();c['archive_symbols']=c['archive_symbols'][:count] if count<112 else c['archive_symbols']+['ZZZ']
 with pytest.raises(ValueError):m.archive_guard(c)
def project(body,status=200):return m.archive_projection('earnings',status,json.dumps(body).encode(),'topsecret',['MSFT'],'2026-10-06T14:00:00+00:00')
def test_timestamps_not_backdated():assert project({'results':[{'ticker':'MSFT','date':'2026-10-28','last_updated':'2020-01-01'}]})['records'][0]['known_no_earlier_than']=='2026-10-06T14:00:00+00:00'
def test_projection_excludes_secret_url_and_outcome():
 p=project({'results':[{'ticker':'MSFT','date':'2026-10-28','eps_actual':99,'forward_return':100}],'next_url':'https://x?apiKey=topsecret'})
 assert all(x not in json.dumps(p) for x in ('topsecret','eps_actual','forward_return')) and p['pagination_pending'] and not p['coverage_complete']
def test_secret_projection_fail():
 with pytest.raises(ValueError):project({'results':[{'ticker':'MSFT','date':'topsecret'}]})
@pytest.mark.parametrize('status',[401,403,429,500,None])
def test_failed_bodies_not_retained(status):
 p=project({'echo':'topsecret'},status);assert p['wire_sha256'] is None and p['missing_status']=='UNKNOWN' and 'topsecret' not in json.dumps(p)
def test_empty_not_no_earnings():assert not project({'results':[]})['coverage_complete']
def test_changed_event_version_hash():assert project({'results':[{'ticker':'MSFT','date':'2026-10-28'}]})['records'][0]['normalized_record_sha256']!=project({'results':[{'ticker':'MSFT','date':'2026-10-29'}]})['records'][0]['normalized_record_sha256']
def test_unknown_symbol():assert project({'results':[{'ticker':'X','date':'2026-10-28'}]})['records']==[]
def test_timezone_required():
 with pytest.raises(ValueError):m.archive_projection('earnings',200,b'{"results":[]}','',['MSFT'],'2026-10-06T14:00:00')
@pytest.mark.parametrize('d',['bars','quotes','aggs','prices','returns','broker_place_order'])
def test_closed_source(d):
 with pytest.raises(ValueError):m.archive_request(d,{},'')
def test_nonfinite_reject():
 with pytest.raises(ValueError):m.archive_projection('dividends',200,b'{"results":[{"ticker":"MSFT","cash_amount":NaN}]}','',['MSFT'],'2026-10-06T14:00:00Z')
def test_manifest_contract(tmp_path,monkeypatch):
 c=context();c.update(job_id='j',attempt_id='a',github_run_id='r',research_revision='a'*40,infrastructure_revision='b'*40)
 monkeypatch.setattr(m,'archive_request',lambda *a:(200,b'{"results":[]}'));monkeypatch.setenv('MASSIVE_API_KEY','synthetic')
 result=m.run_prospective_archival(tmp_path,c);assert len(result['output_paths'])==14
 man=json.loads((tmp_path/result['output_paths'][-1]).read_text());assert len(man['artifacts'])==13 and man['boundary_assignments']==0 and not man['future_price_access']
 for a in man['artifacts']:
  p=tmp_path/'research_outputs/swing11/s4p'/a['name'];assert m.hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256'] and p.stat().st_size==a['size_bytes']
def test_disabled():assert validate_activation({'metadata_json':{}}) is None
def test_schedule_activation():
 c={'enabled':True,'research_sha':'a'*40,'scientific_outcomes_authorized':False,'future_price_access_authorized':False,'parameters':context()};row={'work_envelope_id':m.MWE,'status':'BLOCKED_USER','metadata_json':{'option_b_collector':c}}
 assert validate_activation(row)==c
 c['research_sha']='main'
 with pytest.raises(ValueError):validate_activation(row)
def test_proposal_only():
 b=m.BOUNDARY_RECOMMENDATION;assert 'NOT_FROZEN' in b['state'] and b['current_boundary_assignments']==0 and not b['future_price_access_authorized']
def test_queue_skip(monkeypatch):
 from cloud_compute import queue_watcher as q
 monkeypatch.setattr(q,'fetch_queued_jobs',lambda *a,**k:[{'parameters_json':{'persistent_collector_direct':True},'preferred_executor':'github_actions','git_sha':'a'*40,'job_id':'a'*36}]);assert q.eligible_jobs(None)==[]

@pytest.mark.parametrize('status',['COMPLETE','CANCELLED'])
def test_inactive_mwe_cannot_collect(status):
 c={'enabled':True,'research_sha':'a'*40,'scientific_outcomes_authorized':False,'future_price_access_authorized':False,'parameters':context()}
 with pytest.raises(ValueError):validate_activation({'work_envelope_id':m.MWE,'status':status,'metadata_json':{'option_b_collector':c}})

def test_universe_identity_not_just_size():
 c=context();c['archive_symbols']=['FAKE'+chr(65+i//26)+chr(65+i%26) for i in range(112)]
 with pytest.raises(ValueError):m.archive_guard(c)

@pytest.mark.parametrize('k',['scientific_outcomes_authorized','future_price_access_authorized'])
def test_activation_cannot_open_science(k):
 c={'enabled':True,'research_sha':'a'*40,'scientific_outcomes_authorized':False,'future_price_access_authorized':False,'parameters':context()};c[k]=True
 with pytest.raises(ValueError):validate_activation({'work_envelope_id':m.MWE,'status':'ACTIVE','metadata_json':{'option_b_collector':c}})


def test_exact_claim_env_preserves_infrastructure(monkeypatch):
 from cloud_compute.s4p_archive_schedule import execution_env
 monkeypatch.setenv('GITHUB_SHA','b'*40);monkeypatch.setenv('TR_RESEARCH_SHA','b'*40)
 e=execution_env('a'*40)
 assert e['TR_RESEARCH_SHA']=='a'*40 and e['TR_GIT_REF']=='a'*40 and e['GITHUB_SHA']=='b'*40
 with pytest.raises(ValueError):execution_env('main')


def test_safe_cursor_removes_credential():
 assert m.archive_cursor('dividends','https://api.massive.com/stocks/v1/dividends?cursor=abc&apiKey=neverpersist')=={'cursor':'abc','limit':1000}

@pytest.mark.parametrize('url',['http://api.massive.com/stocks/v1/dividends?cursor=x','https://evil.test/stocks/v1/dividends?cursor=x','https://api.massive.com/v2/aggs?cursor=x','https://api.massive.com/stocks/v1/dividends?cursor=x&price=1'])
def test_unsafe_cursor(url):
 with pytest.raises(ValueError):m.archive_cursor('dividends',url)

def test_bounded_pages_preserve_versions(monkeypatch):
 bodies=[{'results':[{'ticker':'MSFT','id':'e','cash_amount':1}],'next_url':'https://api.massive.com/stocks/v1/dividends?cursor=abc'}, {'results':[{'ticker':'MSFT','id':'e','cash_amount':2}]}]
 monkeypatch.setattr(m,'archive_request',lambda *a:(200,json.dumps(bodies.pop(0)).encode()))
 r=m.archive_collect('dividends',{},'secret',['MSFT'])
 assert r['page_count']==2 and len(r['records'])==2 and r['listing_exhausted'] and r['conflicting_event_ids']==1 and not r['coverage_complete']

def test_repeated_cursor_stops(monkeypatch):
 b={'results':[],'next_url':'https://api.massive.com/stocks/v1/dividends?cursor=abc'}
 monkeypatch.setattr(m,'archive_request',lambda *a:(200,json.dumps(b).encode()))
 r=m.archive_collect('dividends',{},'secret',['MSFT']);assert r['page_count']==2 and r['pagination_pending'] and not r['listing_exhausted']

def test_max_pages_fail_closed(monkeypatch):
 n=[0]
 def get(*a):
  n[0]+=1
  return 200,json.dumps({'results':[],'next_url':'https://api.massive.com/stocks/v1/dividends?cursor='+str(n[0])}).encode()
 monkeypatch.setattr(m,'archive_request',get)
 r=m.archive_collect('dividends',{},'secret',['MSFT']);assert r['page_count']==10 and r['pagination_pending']

def test_missing_credential_makes_no_request(monkeypatch):
 monkeypatch.setattr(m,'archive_request',lambda *a:pytest.fail('request without existing credential'))
 r=m.archive_collect('dividends',{},None,['MSFT']);assert r['page_count']==1 and r['missing_status']=='UNKNOWN' and not r['listing_exhausted']

def test_credential_bearing_cursor_never_replayed(monkeypatch):
 calls=[]
 def get(*a):
  calls.append(a)
  return 200,json.dumps({'results':[],'next_url':'https://api.massive.com/stocks/v1/dividends?cursor=secret'}).encode()
 monkeypatch.setattr(m,'archive_request',get)
 r=m.archive_collect('dividends',{},'secret',['MSFT'])
 assert len(calls)==1 and r['pagination_pending'] and 'secret' not in json.dumps(r)

def test_duplicate_observations_do_not_create_false_conflict(monkeypatch):
 row={'ticker':'MSFT','id':'e','cash_amount':1}
 monkeypatch.setattr(m,'archive_request',lambda *a:(200,json.dumps({'results':[row,row]}).encode()))
 r=m.archive_collect('dividends',{},'secret',['MSFT'])
 assert r['identical_projection_duplicates']==1 and r['conflicting_event_ids']==0 and len(r['records'])==2


def test_documented_dividend_filter():
 from datetime import datetime,timezone
 p=m.archive_parameters('dividends',datetime(2026,10,6,tzinfo=timezone.utc))
 assert p['ex_dividend_date.gte']=='2026-09-06' and p['ex_dividend_date.lte']=='2026-11-17'
 assert not any('declaration' in k for k in p)

def test_request_pacing_synthetic(monkeypatch):
 import time
 clock=[100.];sleeps=[]
 monkeypatch.setattr(m,'_ARCHIVE_LAST_REQUEST',None);monkeypatch.setattr(m,'_ARCHIVE_DEADLINE',1000.)
 monkeypatch.setattr(time,'monotonic',lambda:clock[0])
 def sleep(s):sleeps.append(s);clock[0]+=s
 monkeypatch.setattr(time,'sleep',sleep)
 assert m.archive_pace() and m.archive_pace() and sleeps==[16.]

def test_source_budget_fails_closed(monkeypatch):
 import time
 monkeypatch.setattr(time,'monotonic',lambda:100.)
 monkeypatch.setattr(m,'_ARCHIVE_DEADLINE',130.)
 assert not m.archive_pace()

def test_response_window_mismatch_reported(monkeypatch):
 monkeypatch.setattr(m,'archive_request',lambda *a:(200,json.dumps({'results':[{'ticker':'MSFT','ex_dividend_date':'2012-08-09'}]}).encode()))
 r=m.archive_collect('dividends',{'ex_dividend_date.gte':'2026-09-06','ex_dividend_date.lte':'2026-11-17'},'secret',['MSFT'])
 assert r['outside_window_records']==1 and not r['requested_window_pass'] and not r['coverage_complete']
