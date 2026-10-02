import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing10_s2_b5_acquisition as a

def panel():
 ds=pd.bdate_range('2024-06-03',periods=70)
 return pd.DataFrame([{'symbol':s,'trade_date':d,'open':100.+i+j,'high':102.+i+j,'low':99.+i+j,'close':101.+i+j,'volume':1000.+i} for j,s in enumerate(['SPY','A','B']) for i,d in enumerate(ds)])

def test_guard_self():a.guard_source(Path(a.__file__).read_text())

@pytest.mark.parametrize('s',['import subprocess','from tr_platform.research.swing10_s2_b4 import run','x.shift(-1)','x.shift(h)','x.pct_change()','requests.post(url)','pd.read_csv(path)','eval(x)','x.bfill()'])
def test_guard_fail_closed(s):
 with pytest.raises(ValueError):a.guard_source(s)

@pytest.mark.parametrize('c',['forward_return','p_value','effect_size','mfe','mae'])
def test_outcome_columns_rejected(c):
 p=panel();p[c]=0
 with pytest.raises(ValueError):a.validate_panel(p)

def test_frozen_cases_and_capacity():
 sc,cap=a.capacity(panel(),['SPY','A','B']);assert len(cap)==9 and cap.eligible_dates.gt(0).all() and cap.forward_returns_computed.eq(False).all()
 assert tuple(cap.horizon_days)==(5,7,10,3,5,7,10,7,10)
 assert a.SEEDS[0][1]=='NEGATIVE' and a.SEEDS[1][1]=='POSITIVE';assert len(sc)==3 and sc.rows.eq(70).all()

def test_ties_and_prospective_normalization():
 np.testing.assert_allclose(a.centered_rank(pd.Series([1.,1.,3.])),[0.,0.,1.]);x=pd.Series(np.arange(25,dtype=float));z=a.prospective_state(x)
 assert z.iloc[:20].isna().all();assert z.iloc[20]==pytest.approx((20-9.5)/np.std(np.arange(20),ddof=1));assert a.prospective_state(pd.Series(np.ones(25))).isna().all()

def test_semantics_and_future_invariance():
 p=panel();x=a.predictors(p);cut=sorted(p.trade_date.unique())[40];m=p.copy()
 for c in ('open','high','low','close'):m.loc[m.trade_date>cut,c]*=2
 m.loc[m.trade_date>cut,'volume']*=3;y=a.predictors(m);pd.testing.assert_frame_equal(x[x.trade_date<=cut],y[y.trade_date<=cut],check_exact=True)
 z=x[x.symbol=='A'].reset_index(drop=True);assert z.RET_MOM.iloc[10]==pytest.approx(z.close.iloc[10]/z.close.iloc[0]-1)

def test_boundary_is_authorization_not_outcomes():
 class Fake:
  def request(self,s,start,end):return {},{'http_status':200 if pd.Timestamp(start)>=pd.Timestamp('2024-10-02') else 403},None
 b,status=a.find_boundary(Fake(),'AAPL');assert b==pd.Timestamp('2024-10-02') and status=='EARLIEST_CALENDAR_AUTHORIZATION_BOUNDARY_PROBED'
 class Missing:
  def request(self,*args):return {},{'http_status':403},None
 assert a.find_boundary(Missing(),'AAPL')[1]=='NO_PRE_DISCOVERY_ACCESS'

def test_allowed_url_and_protected_boundary():
 assert a.validated_url('SPY','2024-01-01','2024-01-03').startswith('https://api.massive.com/v2/aggs/')
 for args in [('SPY','2024-01-01','2025-02-03'),('../SPY','2024-01-01','2024-01-03')]:
  with pytest.raises(ValueError):a.validated_url(*args)

def test_response_flags_integrity_and_date():
 p={'ticker':'SPY','adjusted':True,'results':[{'t':int(pd.Timestamp('2024-01-02T05:00:00Z').timestamp()*1000),'o':100,'h':102,'l':99,'c':101,'v':1000}]};assert len(a.normalize('SPY',p))==1
 for x in ({**p,'adjusted':False},{**p,'next_url':'https://api.massive.com/next'},{**p,'ticker':'A'}):
  with pytest.raises(ValueError):a.normalize('SPY',x)

def test_missing_credential_full_artifact_contract(tmp_path,monkeypatch):
 here=Path(a.__file__).parent;root=Path(__file__).parents[1];snapshot=json.loads((root/'research_protocols/swing10'/a.SNAPSHOT).read_text());authority=here/a.SNAPSHOT;authority.write_text(json.dumps(snapshot))
 try:
  monkeypatch.delenv('MASSIVE_API_KEY',raising=False);monkeypatch.delenv('TR_MASSIVE_API_KEY',raising=False)
  ctx={'job_id':'fixture','attempt_id':'attempt','materialized_inputs':[],'research_revision':'r','infrastructure_revision':'i','github_run_id':'run'}
  p=tmp_path/'job_inputs/swing10/execution_context.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(ctx));result=a.run(tmp_path);assert len(result['output_paths'])==6
  m=json.loads((tmp_path/result['output_paths'][-1]).read_text());assert m['classification']=='BLOCKED_CREDENTIALS';assert not m['validation_outcomes_computed'] and not m['protected_data_access'];assert m['provider_request_count']==0 and m['certified_symbols']==0
  for r in m['artifacts']:
   b=(tmp_path/'research_outputs/swing10/s2_b5_acquisition'/r['name']).read_bytes();assert len(b)==r['size_bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
 finally:authority.unlink()

def test_complete_acquisition_synthetic_sources(tmp_path,monkeypatch):
 root=Path(__file__).parents[1];snapshot=json.loads((root/'research_protocols/swing10'/a.SNAPSHOT).read_text());authority=Path(a.__file__).parent/a.SNAPSHOT;authority.write_text(json.dumps(snapshot))
 class Fake:
  def __init__(self,key):self.records=[]
  def request(self,symbol,start,end):
   ds=pd.bdate_range('2024-06-03',periods=45);p={'ticker':symbol,'adjusted':True,'results':[{'t':int(pd.Timestamp(d).tz_localize('America/New_York').timestamp()*1000),'o':100+i,'h':102+i,'l':99+i,'c':101+i,'v':1000+i} for i,d in enumerate(ds)]};blob=json.dumps(p).encode();r={'http_status':200,'raw_response_sha256':hashlib.sha256(blob).hexdigest(),'raw_response_bytes':len(blob)};self.records.append(r);return p,r,blob
 try:
  monkeypatch.setenv('MASSIVE_API_KEY','synthetic-test-only');monkeypatch.delenv('TR_MASSIVE_API_KEY',raising=False);monkeypatch.setattr(a,'Provider',Fake)
  ctx={'job_id':'fixture','attempt_id':'attempt','materialized_inputs':[],'research_revision':'r','infrastructure_revision':'i','github_run_id':'run'};p=tmp_path/'job_inputs/swing10/execution_context.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(ctx))
  result=a.run(tmp_path);assert len(result['output_paths'])==119;m=json.loads((tmp_path/result['output_paths'][5]).read_text());assert m['classification']=='PRE_DISCOVERY_DAILY_CERTIFIABLE' and m['certified_symbols']==112 and len(m['artifacts'])==118
  assert not m['validation_outcomes_computed'] and not m['scientific_interval_selected'];assert m['stop_before_scientific_validation']
  for r in m['artifacts']:
   blob=(tmp_path/'research_outputs/swing10/s2_b5_acquisition'/r['name']).read_bytes();assert hashlib.sha256(blob).hexdigest()==r['sha256'] and len(blob)==r['size_bytes']
   if r['source_object']:assert r['sha256'] in r['name']
 finally:authority.unlink()
