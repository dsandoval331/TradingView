import itertools
import json
from pathlib import Path
import math
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing10_s2_b5_validation as v
from tr_platform.research import swing10_s2_b5_validation_contract as c

def panel(n=100,symbols=12):
    dates=pd.bdate_range('2024-01-01',periods=n)
    rows=[]
    for j in range(symbols):
        name='SPY' if j==0 else f'S{j:02}'
        for i,d in enumerate(dates):
            close=100+j+0.07*i+.6*np.sin(i*.19+j)
            rows.append([name,d,close,close+1,close-1,close,1000+j*10+i])
    return pd.DataFrame(rows,columns=c.PANEL_COLUMNS)

def market_data(n=80):
    z=np.linspace(-1,2,n)+.1*np.sin(np.arange(n))
    xs=np.linspace(-1,1,12);symbols=np.array([f'S{i:02}' for i in range(12)])
    data=[]
    for i,a in enumerate(z):
        slope=.2+.35*a+.07*np.sin(i*.4)
        y=.02+slope*xs+.003*np.cos(np.arange(12)+i)
        q,contributions,_=v.slope_fit(xs,y)
        data.append({'date':pd.Timestamp('2024-01-01')+pd.Timedelta(days=i),'symbols':symbols,
          'x':xs,'y':y,'z':a,'quantity':q,'contributions':contributions})
    return data

def test_frozen_snapshots_and_source_guard():
    v.verify_decisions();v.source_guard(Path(v.__file__).read_text())

@pytest.mark.parametrize('source',["import requests","import sqlite3","import os","x=eval('1')","pd.read_parquet('x')","Path('protected/holdout.csv').read_bytes()"])
def test_prohibited_source_rejected(source):
    with pytest.raises(ValueError):v.source_guard(source)

def test_panel_outcome_columns_rejected():
    p=panel();p['forward_7']=1
    with pytest.raises(ValueError):v.validate_panel(p)

@pytest.mark.parametrize('change',['null','dup','bad_price','bad_ohlc','negative_volume','missing_spy'])
def test_invalid_panel(change):
    p=panel()
    if change=='null':p.loc[0,'close']=np.nan
    elif change=='dup':p=pd.concat([p,p.iloc[:1]])
    elif change=='bad_price':p.loc[0,'close']=-1
    elif change=='bad_ohlc':p.loc[0,'low']=10000
    elif change=='negative_volume':p.loc[0,'volume']=-1
    else:p=p[p.symbol!='SPY']
    with pytest.raises(ValueError):v.validate_panel(p)

def test_input_hash_fail_closed(tmp_path):
    p=tmp_path/'x.csv';p.write_text('bad')
    with pytest.raises(ValueError,match='immutable'):v.verify_input(p)

def test_causal_predictors_exact():
    p=panel();q=v.predictors(p);spy=q[q.symbol=='SPY']
    expected=spy.close/spy.close.shift(10)-1
    np.testing.assert_allclose(spy.RET_MOM,expected,equal_nan=True)
    assert spy.market_z.iloc[:30].isna().all()
    s=expected.iloc[10:30]
    assert spy.market_z.iloc[30]==pytest.approx((expected.iloc[30]-s.mean())/s.std(ddof=1))
    v.future_invariance(p,q)

def test_eligible_dates_blocks_frozen_before_outcomes():
    p=panel();q=v.predictors(p);cases=v.prepare_cases(q)
    assert len(cases)==9
    for f,h,d,l in c.CASES:
        pc=cases[f,h];ns=[sum(b==i for b in pc['blocks'].values()) for i in range(1,5)]
        assert max(ns)-min(ns)<=1
        assert len(pc['dates'])==100-h-(30 if l else 0)

@pytest.mark.parametrize('h',[3,5,7,10])
def test_returns_horizon_and_overlap(h):
    p=panel();o=v.outcome(p,h);spy=p[p.symbol=='SPY'].reset_index(drop=True);got=o[o.symbol=='SPY'].reset_index(drop=True)
    assert got.forward_return.iloc[0]==pytest.approx(spy.close.iloc[h]/spy.close.iloc[0]-1)
    assert got.forward_return.iloc[1]==pytest.approx(spy.close.iloc[h+1]/spy.close.iloc[1]-1)
    assert got.forward_return.iloc[-h:].isna().all()

@pytest.mark.parametrize('h',[1,2,4,11])
def test_no_extra_horizon(h):
    with pytest.raises(ValueError):v.outcome(panel(),h)

def test_strict_discovery_endpoint():
    p=panel();p.trade_date+=pd.Timedelta(days=280)
    pcs=v.prepare_cases(v.predictors(p));ds=sorted(p.trade_date.unique())
    for (f,h),pc in pcs.items():
        assert all(pd.Timestamp(ds[ds.index(d)+h])<pd.Timestamp('2025-02-03') for d in pc['dates'])

def test_known_stage1_main_effect_included():
    x=np.array([-1,-.5,0,.5,1])
    coef,contrib,intercept=v.slope_fit(x,3+2*x)
    assert coef==pytest.approx(2) and intercept==pytest.approx(3) and sum(contrib)==pytest.approx(2)

def test_known_stage2_gamma_is_not_mean_stage1():
    z=np.linspace(-1,1,80);b=4+.3*z+.01*np.sin(np.arange(80))
    got=v.hac_regression(z,b,7)
    expected=np.linalg.lstsq(np.column_stack([np.ones(80),z]),b,rcond=None)[0][1]
    assert got['primary_estimate']==pytest.approx(expected)
    assert got['standardized_effect']==pytest.approx(expected/np.std(b,ddof=1))
    assert abs(got['primary_estimate']-got['date_effect_mean'])>3

@pytest.mark.parametrize('h',[3,5,7,10])
def test_hac_mean_known_fixture(h):
    y=np.array([.03,.01,-.02,.04,.05,-.01,.02,.06,-.03,.01]*5)
    u=y-y.mean();lag=h-1
    meat=sum(u*u)+sum(2*(1-k/(lag+1))*sum(u[k:]*u[:-k]) for k in range(1,lag+1))
    got=v.hac_mean(y,h)
    assert got['hac_lag']==h-1
    assert got['hac_se']==pytest.approx(np.sqrt(meat/len(y)**2))
    assert got['p_raw']==pytest.approx(math.erfc(abs(y.mean()/got['hac_se'])/np.sqrt(2)))
    assert got['ci95_high']-got['primary_estimate']==pytest.approx(1.959963984540054*got['hac_se'])

def test_hac_regression_known_sandwich_fixture():
    z=np.linspace(-1,1,60);y=.1+.3*z+.1*np.sin(np.arange(60));h=7
    X=np.column_stack([np.ones(len(z)),z]);beta=np.linalg.solve(X.T@X,X.T@y);u=y-X@beta
    scores=X*u[:,None];M=scores.T@scores
    for k in range(1,h):
        cross=scores[k:].T@scores[:-k];M+=(1-k/h)*(cross+cross.T)
    B=np.linalg.inv(X.T@X);se=np.sqrt((B@M@B)[1,1]);r=v.hac_regression(z,y,h)
    assert r['primary_estimate']==pytest.approx(beta[1]) and r['hac_se']==pytest.approx(se)

def test_joint9_bh_with_unavailable_slot():
    ps={k:p for k,p in zip(c.KEYS,[.001,.01,.02,.03,.05,.1,.2,.6,np.nan])}
    result=v.bh_adjust(ps)
    assert result[c.KEYS[0]]==pytest.approx(.009)
    assert result[c.KEYS[1]]==pytest.approx(.045)
    assert result[c.KEYS[-1]]==1
    with pytest.raises(ValueError):v.bh_adjust(dict(list(ps.items())[:-1]))

@pytest.mark.parametrize('valid,directional,material,fdr,robust',list(itertools.product([False,True],repeat=5)))
def test_all_disposition_branches(valid,directional,material,fdr,robust):
    expected='NOT_TESTABLE' if not valid else 'INDEPENDENT_VALIDATION_FAILED' if not(directional and material and fdr) else 'INDEPENDENT_VALIDATION_SUPPORTED' if robust else 'PARTIAL_VALIDATION_EVIDENCE'
    assert c.disposition(valid,directional,material,fdr,robust)==expected

@pytest.mark.parametrize('direction',['POSITIVE','NEGATIVE'])
def test_zero_direction_fails(direction):assert not c.direction_pass(0,direction)

@pytest.mark.parametrize('es,passed',[(.199999,False),(.20,True),(-.20,True),(-.199999,False)])
def test_material_boundary(es,passed):assert (abs(es)>=c.MATERIAL)==passed

def test_registered_only_adjacency():
    f='RET_MOM x MARKET_SPY_TREND10'
    assert c.registered_neighbors(f,7)==(10,)
    assert c.registered_neighbors('LIQ_REPORTED_VOLUME',3)==(5,)
    assert c.adjacency(f,7,{(f,10):.2},.1)
    assert not c.adjacency(f,7,{(f,10):-.2},.1)
    assert c.registered_neighbors('UNREGISTERED',3)==()
    assert c.adjacency('UNREGISTERED',3,{},.1)

def test_full_two_stage_temporal_and_concentration():
    data=market_data();full=v.primary(data,True,7)['primary_estimate']
    mapping={d['date']:i//20+1 for i,d in enumerate(data)}
    rows,stats=v.temporal(data,True,7,'POSITIVE',mapping)
    for i,r in enumerate(rows):
        assert r['primary_estimate']==pytest.approx(v.primary(data[i*20:(i+1)*20],True,7)['primary_estimate'])
    sr,ss=v.concentration(data,True,7,full)
    assert sum(x['additive_primary_contribution'] for x in sr)==pytest.approx(full)
    assert ss['top1_absolute_share']<=ss['top5_absolute_share']<=ss['top10_absolute_share']<=1
    removed={x['symbol'] for x in sr[:5]}
    assert ss['leave_top5_estimate']==pytest.approx(v.refit_without(data,removed,True,7))

def test_leave5_sign_rules(monkeypatch):
    data=market_data();full=v.primary(data,True,7)['primary_estimate']
    monkeypatch.setattr(v,'refit_without',lambda *args: -full)
    assert v.concentration(data,True,7,full)[1]['leave_top5_sign_reversal']
    monkeypatch.setattr(v,'refit_without',lambda *args: 0)
    assert not v.concentration(data,True,7,full)[1]['leave_top5_sign_reversal']

def test_temporal_recomputes_stage1_not_cached_slopes():
    data=market_data();mapping={d['date']:i//20+1 for i,d in enumerate(data)}
    expected=v.temporal(data,True,7,'POSITIVE',mapping)[0]
    for d in data:d['quantity']=999.
    recomputed=v.temporal(data,True,7,'POSITIVE',mapping)[0]
    for a,b in zip(expected,recomputed):assert a['primary_estimate']==pytest.approx(b['primary_estimate'])

def test_unavailable_block_not_primary_not_testable():
    data=market_data(43);full=v.primary(data,True,10)
    chunks=np.array_split(range(43),4);mapping={data[i]['date']:b for b,ch in enumerate(chunks,1) for i in ch}
    rows,stats=v.temporal(data,True,10,'POSITIVE',mapping)
    assert full['eligible_dates']==43 and not rows[-1]['diagnostic_available']
    assert not stats['temporal_concentration_pass']

def test_exact_schemas_flags_synthetic_analyze():
    p=panel();q=v.predictors(p);prepared=v.prepare_cases(q)
    tables=v.analyze(p,q,prepared)
    assert tuple(tables)==c.FILES[:-1]
    for name,t in tables.items():assert tuple(t.columns)==c.SCHEMAS[name]
    s=tables[c.FILES[0]]
    assert len(s)==9 and s.limited_temporal_capacity.sum()==2
    assert set(s.disposition)<=set(('INDEPENDENT_VALIDATION_SUPPORTED','PARTIAL_VALIDATION_EVIDENCE','INDEPENDENT_VALIDATION_FAILED','NOT_TESTABLE'))

def test_liquidity_inclusive_tails_and_contribution():
    p=panel();q=v.predictors(p);pc=v.prepare_cases(q)['LIQ_ADJUSTED_PRICE',5]
    data,rows=v.make_data(pc,'LIQ_ADJUSTED_PRICE',5,v.outcome(p,5))
    for d in data:assert d['quantity']==pytest.approx(d['y'][d['high']].mean()-d['y'][d['low']].mean())
    full=v.primary(data,False,5)['primary_estimate'];rows,stats=v.concentration(data,False,5,full)
    assert sum(r['additive_primary_contribution'] for r in rows)==pytest.approx(full)
