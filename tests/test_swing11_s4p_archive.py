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
