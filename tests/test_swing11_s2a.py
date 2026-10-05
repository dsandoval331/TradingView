import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing11_s2a as m

def frame(n=50,symbols=12):
    rows=[]
    for j in range(symbols):
        for t in range(n):
            c=100+j*3+t*.5+np.sin(t*(j+1)*.1)
            rows.append((f"SYNTHETIC_{j:03}",f"2025-01-{t+1:03}",c,c+1,c-1,c,100+t+j*2))
    return pd.DataFrame(rows,columns=m.CORE)

def test_contract_registry():
    registry=m.inference_registry()
    assert len(registry)==104 and len(set(r[3] for r in registry))==104
    assert [sum(r[0]==f for r in registry) for f in ("A_BASELINE","B_ATTENUATION","C_INTERACTION")]==[8,48,48]
    assert all(r[4]==r[2]-1 for r in registry)
    with pytest.raises(ValueError,match="BLOCKED_USER"):m.require_scientific_contract()

def test_average_ties():
    assert m.centered_rank([1,1,2,4]).tolist()==[-.25,-.25,.5,1.]
    assert pd.isna(m.centered_rank([1,np.inf])[1])

@pytest.mark.parametrize("name",("PRICE",*m.MECHANISMS))
def test_future_invariance(name):
    f=frame();before=m.predictors(f)
    f.loc[f.trade_date>"2025-01-030",["close","volume"]]*=2
    after=m.predictors(f)
    pd.testing.assert_series_equal(before.loc[before.trade_date=="2025-01-030",name],after.loc[after.trade_date=="2025-01-030",name])

@pytest.mark.parametrize("current,expected",[(100,1),(200,2),(50,.5)])
def test_activity_semantics(current,expected):
    f=frame(21,1);f["volume"]=100;f.loc[20,"volume"]=current
    a=m.predictors(f)
    assert a.ACT20_raw.iloc[-1]==expected
    assert a.ACT20_raw.iloc[:20].isna().all()

def test_all_raw_formula():
    f=frame(25,1);a=m.predictors(f);c=f.close;v=f.volume;r=c/c.shift(1)-1
    assert a.MOM20_raw.iloc[20]==pytest.approx(c.iloc[20]/c.iloc[0]-1)
    assert a.REV5_raw.iloc[5]==pytest.approx(c.iloc[5]/c.iloc[0]-1)
    assert a.DOLLARVOL20_raw.iloc[19]==pytest.approx((c*v).iloc[:20].mean())
    assert a.ILLIQ20_raw.iloc[20]==pytest.approx((r.abs()/(c*v)).iloc[1:21].mean())
    assert a.RV20_raw.iloc[20]==pytest.approx(r.iloc[1:21].std(ddof=1))
    assert a.RV20_raw.iloc[:20].isna().all()

@pytest.mark.parametrize("column",["volume","close"])
def test_missing_full_warmup(column):
    f=frame(41,1);f.loc[10,column]=np.nan;a=m.predictors(f)
    assert pd.isna(a.DOLLARVOL20_raw.iloc[29])
    if column=="close":assert pd.isna(a.RV20_raw.iloc[30])

def test_zero_activity_denominator():
    f=frame(21,1);f["volume"]=0
    assert m.predictors(f).ACT20_raw.isna().all()

@pytest.mark.parametrize("kind",["baseline","adjusted","conditioning"])
def test_identification_and_synthetic_contributions(kind):
    p=np.linspace(-1,1,32);z=np.sin(np.arange(32)*.9)
    x,rank,_,_=m.design(p,None if kind=="baseline" else z,kind=="conditioning")
    beta=np.arange(1,x.shape[1]+1)*.2;y=x@beta
    out=m.synthetic_refit(x,y,[f"SYNTHETIC_{i:03}" for i in range(32)],1)
    assert out["coefficient"]==pytest.approx(beta[1])
    assert out["contributions"].sum()==pytest.approx(beta[1])
    assert out["leave5"]==pytest.approx(beta[1])

@pytest.mark.parametrize("bad",["flat","collinear","few","nonfinite"])
def test_design_fail_closed(bad):
    p=np.linspace(-1,1,20);z=np.sin(np.arange(20))
    if bad=="flat":p[:]=0
    if bad=="collinear":z=p.copy()
    if bad=="few":p=p[:3];z=z[:3]
    if bad=="nonfinite":p[0]=np.nan
    with pytest.raises(ValueError):m.design(p,z,True)

@pytest.mark.parametrize("column",["forward_return","p_value","profitability","win_rate"])
def test_outcome_schema_denied(column):
    with pytest.raises(ValueError):m.reject_schema([*m.CORE,column])

@pytest.mark.parametrize("code",["x.shift(-1)","x.shift(periods=-2)","import swing10_s2_b5_validation","x.pct_change(-5)","eval('x')"])
def test_source_future_outcome_denied(code):
    with pytest.raises(ValueError):m.source_guard(code)

def test_source_guard_itself():
    from pathlib import Path
    assert m.source_guard(Path(m.__file__).read_text())

def test_exact_immutable_rejection():
    with pytest.raises(ValueError):m.verified_input(b"unregistered")

def test_blocks_capacity_only():
    dates=list(range(103));blocks=m.four_blocks(dates)
    assert sum(blocks,[])==dates and [len(x) for x in blocks]==[26,26,26,25]
    _,coverage,_,b=m.audit(frame())
    assert len(coverage)==48 and len(b)==192
    assert len(m.FILES)==7

def test_real_estimator_and_local_runner_denied(monkeypatch,tmp_path):
    x,_,_,_=m.design(np.linspace(-1,1,20))
    with pytest.raises(ValueError):m.synthetic_refit(x,np.ones(20),["AAPL"]*20,1)
    monkeypatch.delenv("GITHUB_ACTIONS",raising=False)
    with pytest.raises(ValueError):m.run(tmp_path)
