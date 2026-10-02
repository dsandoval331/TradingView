from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing10_s2_b5_preflight as b
from cloud_compute.certify_dispatch_contracts import selected_tests


def fixture():
    dates=pd.bdate_range('2024-01-01',periods=70)
    return pd.DataFrame([{'symbol':s,'trade_date':d,'close':float(100+i+(i%7)*(j+1)),'volume':float(100+j)} for j,s in enumerate(['SPY','A','B']) for i,d in enumerate(dates)])


def test_guard_self():b.guard_source(Path(b.__file__).read_text())

@pytest.mark.parametrize('source',['import requests','from tr_platform.research.swing10_s2_b4 import run','x.shift(-1)','x.shift(h)','x.pct_change()','pd.read_parquet(path)','pd.read_parquet(path,columns=["close"])','pd.read_sql(q,c)','eval(x)','x.bfill()'])
def test_guard_denies_outcomes_and_future(source):
    with pytest.raises(ValueError):b.guard_source(source)


def test_frozen_nine_cases():
    assert b.SEEDS==( ('LIQ_ADJUSTED_PRICE','NEGATIVE',(5,7,10)),('LIQ_REPORTED_VOLUME','POSITIVE',(3,5,7,10)),('RET_MOM x MARKET_SPY_TREND10','POSITIVE',(7,10)))


def test_exact_average_rank_representation():np.testing.assert_allclose(b.centered_rank(pd.Series([1.,1.,3.,np.nan])),[0,0,1,np.nan])


def test_strict_prior_standardization():
    x=pd.Series(np.arange(25,dtype=float),index=pd.bdate_range('2024-01-01',periods=25));z=b.prospective_state(x)
    assert z.iloc[:20].isna().all()
    assert z.iloc[20]==pytest.approx((20-np.mean(np.arange(20)))/np.std(np.arange(20),ddof=1))
    y=x.copy();y.iloc[20]=200
    assert b.prospective_state(y).iloc[20]==pytest.approx((200-np.mean(np.arange(20)))/np.std(np.arange(20),ddof=1))
    assert b.prospective_state(pd.Series(np.ones(25))).isna().all()


def test_ret_mom_and_future_invariance():
    x=fixture();a=b.predictor_fixture(x);mut=x.copy();cut=sorted(x.trade_date.unique())[40];mut.loc[mut.trade_date>cut,'close']*=5;mut.loc[mut.trade_date>cut,'volume']*=2;c=b.predictor_fixture(mut)
    pd.testing.assert_frame_equal(a[a.trade_date<=cut],c[c.trade_date<=cut],check_exact=True)
    z=a[a.symbol=='A'].reset_index(drop=True)
    assert z.RET_MOM.iloc[10]==pytest.approx(z.close.iloc[10]/z.close.iloc[0]-1)

@pytest.mark.parametrize('column',['forward_return','p_value','effect_size','mfe','mae','protected_holdout'])
def test_outcome_column_rejection(column):
    x=fixture();x[column]=0
    with pytest.raises(ValueError):b.predictor_fixture(x)


def test_timestamp_endpoints_and_nonoverlap():
    e=b.timestamp_eligibility(pd.DatetimeIndex(['2025-01-30','2025-01-31','2025-02-03','2025-02-04']),1,0)
    assert e.temporally_independent.tolist()==[True,False,False,False]
    assert e.timestamp_eligible.tolist()==[True,True,True,False]
    with pytest.raises(ValueError):b.timestamp_eligibility(pd.Series([10,20]),1,0)
    assert b.timestamp_eligibility(pd.bdate_range('2026-08-28',periods=12),10,0).temporally_independent.sum()==2


def test_metadata_projection_only_hash_and_protected_rejection(tmp_path,monkeypatch):
    p=tmp_path/'2024.parquet';p.write_bytes(b'fixture');seen=[]
    f=pd.DataFrame({'symbol':['A'],'trade_date':[pd.Timestamp('2024-01-02')],'timestamp_utc':[pd.Timestamp('2024-01-02T15:00:00Z')],'session':['RTH'],'source':['massive'],'adjusted':[False],'cache_version':['MARKET_CACHE_V1']})
    def read(p,columns):seen.append(columns);return f.copy()
    monkeypatch.setattr(pd,'read_parquet',read);sha=hashlib.sha256(b'fixture').hexdigest()
    z,identity=b.read_metadata(p,7,sha,'A')
    assert seen==[list(b.META_COLUMNS)] and identity['price_columns_decoded'] is False
    with pytest.raises(ValueError):b.read_metadata(p,8,'x','A')
    f['trade_date']=pd.Timestamp('2025-01-02')
    with pytest.raises(ValueError):b.read_metadata(p,7,sha,'A')


def test_no_semantic_substitution_and_exact_artifacts():
    f=pd.DataFrame({'trade_date':pd.bdate_range('2024-01-01',periods=50),'session':'RTH','adjusted':False,'source':'massive'});t=b.audit({}, {'SPY':f,'A':f},[{},{}])
    assert set(t)==set(b.FILES[:5]) and len(b.FILES)==6
    assert len(t[b.FILES[3]])==8*9
    assert t[b.FILES[3]].certified_semantic_eligible_observations.eq(0).all()
    assert set(t[b.FILES[2]].status)=={'UNAVAILABLE_FOR_VALIDATION'}
    assert t[b.FILES[3]].loc[t[b.FILES[3]].source_id=='CACHE_2024','timestamp_only_potential_observations'].gt(0).all()
    assert len(t[b.FILES[1]])==8


def test_dispatch_and_authority():
    paths=selected_tests('SW10-S2-B5-PREFLIGHT');assert 'tests/test_swing10_s2_b5_preflight.py' in paths
    assert 'tests/test_swing10_s2_b4.py' not in paths and 'tests/test_swing10_s2_b2.py' not in paths
    s=json.loads((Path(__file__).parents[1]/'research_protocols/swing10'/b.SNAPSHOT).read_text())
    assert s['authority'][0]['record']['decision_id']==b.DECISION
    assert len(s['candidate_cache_inputs'])==112
    assert all(r['object_path'].endswith('/2024.parquet') for r in s['candidate_cache_inputs'])
