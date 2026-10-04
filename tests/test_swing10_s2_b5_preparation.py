import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing10_s2_b5_preparation as b

def test_registry():
    b.validate_cases(b.KEYS)
    assert len(b.CASES)==9 and sum(c[3] for c in b.CASES)==2
    assert len(b.FILES)==7 and b.MATERIAL_ABS_THRESHOLD==.20

@pytest.mark.parametrize('keys',[b.KEYS[:-1],b.KEYS+(('EXTRA',1),),b.KEYS[:-1]+(b.KEYS[0],)])
def test_no_changed_family(keys):
    with pytest.raises(ValueError):b.validate_cases(keys)

@pytest.mark.parametrize('h', [3,5,7,10])
def test_frozen_lags(h):assert b.lag(h)==h-1

@pytest.mark.parametrize('h',[1,2,6,11])
def test_extra_horizons_rejected(h):
    with pytest.raises(ValueError):b.lag(h)

def test_directions_capacity_flags():
    assert all(c[2]=='NEGATIVE' for c in b.CASES[:3])
    assert all(c[2]=='POSITIVE' for c in b.CASES[3:])
    assert [c[1] for c in b.CASES if c[3]]==[7,10]

def test_average_rank_ties():
    np.testing.assert_allclose(b.centered_rank([1,1,3,np.nan]),[0,0,1,np.nan],equal_nan=True)

def test_rank_current_date_only():
    a=b.centered_rank([2,3,4])
    pd.testing.assert_series_equal(a,b.centered_rank([2,3,4]))

def test_trend_causal():
    x=np.arange(1.,41.)
    a=b.trend10(x)
    assert a.iloc[:10].isna().all() and a.iloc[10]==10
    x[21:]*=100
    pd.testing.assert_series_equal(a.iloc[:21],b.trend10(x).iloc[:21])

def test_past_only_mean_sd():
    x=np.arange(41.,dtype=float);z=b.normalize_state(x)
    assert z.iloc[:20].isna().all()
    assert z.iloc[20]==pytest.approx((20-np.mean(x[:20]))/np.std(x[:20],ddof=1))
    x[20]=500
    assert b.normalize_state(x).iloc[20]==pytest.approx((500-9.5)/np.std(np.arange(20),ddof=1))

def test_normalization_future_invariance():
    x=np.arange(41.,dtype=float);a=b.normalize_state(x);x[21:]*=70
    pd.testing.assert_series_equal(a.iloc[:21],b.normalize_state(x).iloc[:21])

def test_zero_variance_ineligible():assert b.normalize_state(np.ones(50)).isna().all()

def test_nonfinite_not_prior_eligible():
    x=np.arange(45.,dtype=float);x[5]=np.inf
    z=b.normalize_state(x);assert np.isnan(z.iloc[20]) and np.isfinite(z.iloc[21])

@pytest.mark.parametrize('h',[3,5,7,10])
def test_calendar_endpoints(h):
    ds=pd.bdate_range('2024-12-01','2025-02-10')
    out=b.eligible_calendar(ds,[True]*len(ds),h)
    assert all(ds[list(ds).index(d)+h]<pd.Timestamp('2025-02-03') for d in out)
    assert out==[d for i,d in enumerate(ds) if i+h<len(ds) and ds[i+h]<pd.Timestamp('2025-02-03')]

def test_blocks_before_outcomes():
    ds=list(pd.date_range('2024-01-01',periods=43));m=b.four_blocks(ds)
    assert [sum(v==i for v in m.values()) for i in range(1,5)]==[11,11,11,10]

@pytest.mark.parametrize('field',['forward_7','effect','p_raw','holdout','MFE','MAE','protected_return'])
def test_outcome_fields_rejected(field):
    with pytest.raises(ValueError):b.guard_predictor_columns(['symbol','close',field])

def test_immutable_rejection():
    with pytest.raises(ValueError):b.verify_bytes(b'changed')

def test_real_scientific_execution_fail_closed():
    with pytest.raises(RuntimeError,match='BLOCKED_USER'):b.scientific_entrypoint()
