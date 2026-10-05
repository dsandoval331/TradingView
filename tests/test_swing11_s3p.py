import copy
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing11_s3p as p
from tr_platform.research import swing11_s3_contract as c
from tr_platform.research import swing11_s2a as certified

def frame(N=100,T=60):
 rows=[]
 for i in range(N):
  for t in range(T):
   close=10+i+(.5+i/100)*np.sin(t*(i%5+1)/7)
   rows.append(dict(symbol=f'SYNTHETIC_{i:03}',trade_date=f'{t:03}',open=close,high=close+1,low=close-1,close=close,volume=100))
 return pd.DataFrame(rows)[list(certified.CORE)]

def good():return dict(testable=True,mean=.001,ES=.2,q=.05,positive_horizons=3,adjacent_pair=True,temporal=True,concentration=True,capacity=True,sensitivity=True)
def rows():return {k:dict(absolute=good(),relative=good(),passing_horizons=4,minimum_positive_blocks=4,maximum_block_share=.3,maximum_top5_share=.2,active_rate=.9,paired_improvement=.01) for k in c.CANDIDATES}

def test_exact_registries():
 assert c.CANDIDATES==('S3-C0','S3-C1','S3-C2') and c.HORIZONS==(5,7,10,15)
 assert len(c.TESTS)==5 and len(c.SENSITIVITIES)==4 and len(p.FILES)==8 and len(c.FUTURE_SCHEMAS)==9
 assert p.advancement_registry().HAC_lag.eq(14).all()
 assert p.advancement_registry().real_disposition_computed.eq(False).all()

def test_exact_predictor_compatibility():
 f=frame(20,40);a=p.predictors(f);b=certified.predictors(f)
 for name in ('PRICE','PRICE_raw','RV20','RV20_raw'):np.testing.assert_allclose(a[name],b[name],equal_nan=True)
 assert a[a.trade_date<'020'].RV20.isna().all()

@pytest.mark.parametrize('date',['020','030','040'])
def test_future_invariance(date):
 f=frame(20,60);a=p.predictors(f)
 f.loc[f.trade_date>date,['open','high','low','close']]*=2
 b=p.predictors(f);pd.testing.assert_frame_equal(a[a.trade_date==date],b[b.trade_date==date])

def test_tail_ties_no_input_order_selection():
 f=frame(100,40);f.loc[f.symbol.isin(['SYNTHETIC_018','SYNTHETIC_019']),['open','close']]=20
 a=p.predictors(f);b=p.predictors(f.sample(frac=1,random_state=1))
 pd.testing.assert_frame_equal(a.reset_index(drop=True),b.reset_index(drop=True))
 assert a.C0_long.eq(a.PRICE_pct.le(.2)).all()
 assert a.C0_short.eq(a.PRICE_pct.ge(.8)).all()

def test_c1_exact_existing_tails_no_rerank():
 v=p.predictors(frame());np.testing.assert_array_equal(v.C1_long,v.C0_long&v.RV20_pct.ge(.5))
 np.testing.assert_array_equal(v.C1_short,v.C0_short&v.RV20_pct.ge(.5))
 assert not v[v.trade_date<'020'].C1_long.any()

def test_c2_exact_formula_and_rank():
 v=p.predictors(frame(30,40));np.testing.assert_allclose(v.C2_score,-v.PRICE*(1+v.RV20)/2,equal_nan=True)
 g=v[v.trade_date=='030'];np.testing.assert_allclose(g.C2_pct,(certified.centered_rank(g.C2_score)+1)/2)
 assert g.C2_long.eq(g.C2_pct.ge(.8)).all() and g.C2_short.eq(g.C2_pct.le(.2)).all()

@pytest.mark.parametrize('price',[-.8,.8])
def test_c2_orientation_monotone(price):
 scores=-price*(1+np.array([-.5,0,.5]))/2
 assert np.all(np.diff(scores)>0) if price<0 else np.all(np.diff(scores)<0)

@pytest.mark.parametrize('n,expected',[(4,True),(5,False),(6,False)])
def test_capacity_boundary(n,expected):
 g=pd.DataFrame(dict(symbol=[f'SYNTHETIC_{i}' for i in range(n*2)],C0_long=[True]*n+[False]*n,C0_short=[False]*n+[True]*n))
 assert p.memberships(g,'S3-C0')[2]==expected

def test_overlap_degeneracy():
 g=pd.DataFrame(dict(symbol=[str(i) for i in range(10)],C0_long=True,C0_short=True))
 assert p.memberships(g,'S3-C0')[2]

@pytest.mark.parametrize('h',c.HORIZONS)
def test_entry_exit_exact(h):
 assert c.indices(10,h,100)==(11,10+h)
 with pytest.raises(ValueError):c.indices(100-h,h,100)

def test_only_predictor_calendar_real_path():
 v,g,t,blocks=p.prepare(frame(100,60));assert len(blocks)==4 and sum(map(len,blocks))==45
 assert len(g)==3*4*45 and len(t)==3*4*4
 assert g.predictor_only.all() and g.exit_date.max()=='059'
 assert not any('return' in name for name in g.columns)
 assert g.loc[g.no_trade,'gross_inception'].eq(0).all()
 assert g.loc[~g.no_trade,'gross_inception'].eq(1).all()
 assert ((g.scheduled_active_cohorts+g.scheduled_cash_sleeves)==g.horizon).all()

def test_leave5_fixed_ranks_membership_rebuild():
 g=p.predictors(frame(100,40));g=g[g.trade_date=='030'];removed=g.loc[g.C0_long,'symbol'].head(5).tolist()
 long,short,no=p.memberships(g,'S3-C0',removed)
 assert not set(long)&set(removed) and len(long)==g.C0_long.sum()-5
 assert len(short)==g.C0_short.sum() and not no

def test_synthetic_long_short_additive():
 symbols=[f'SYNTHETIC_{i}' for i in range(10)];entry=np.ones(10)*100;exit=np.array([110]*5+[90]*5)
 r,v=c.synthetic_cohort(symbols,entry,exit,list(range(5)),list(range(5,10)))
 assert np.isclose(r,.1) and np.isclose(v.sum(),r)
 assert c.synthetic_cohort(symbols,entry,exit,list(range(4)),list(range(5,10)))[0]==0

@pytest.mark.parametrize('h',c.HORIZONS)
def test_sleeve_conservation_no_compounding(h):
 sy=[f'SYNTHETIC_{i}' for i in range(10)];w=np.array([.1]*5+[-.1]*5);entry=np.ones(10)*100
 a=c.synthetic_daily_sleeve(sy,entry,entry,np.array([105]*5+[95]*5),w,h)
 b=c.synthetic_daily_sleeve(sy,entry,np.array([105]*5+[95]*5),np.array([110]*5+[90]*5),w,h)
 assert np.isclose(a['pnl']+b['pnl'],.1/h)
 assert np.isclose(a['gross'],1/h)
 cash=c.synthetic_daily_sleeve(sy,entry,entry,entry,w*0,h);assert cash['pnl']==cash['gross']==0

def test_family_equal_horizon_no_best_cap():
 a=np.array([[.05,.07,.1,.15],[0,0,0,0]])
 np.testing.assert_allclose(c.synthetic_family(['SYNTHETIC_1'],a),[.01,0])

def test_exact_HAC_known_constant_offset_fixture():
 x=np.sin(np.arange(200))+0.3;r=c.synthetic_hac(['SYNTHETIC_1'],x)
 n=len(x);z=x-x.mean();variance=np.dot(z,z)/n
 for lag in range(1,15):variance+=2*(1-lag/15)*np.dot(z[lag:],z[:-lag])/n
 assert np.isclose(r['hac_se'],np.sqrt(variance/n)) and np.isclose(r['ES'],x.mean()/x.std(ddof=1))

def test_bh_five_slots_no_shrink():
 np.testing.assert_allclose(c.bh_five([.001,.01,None,.2,.9]),[.005,.025,1,1/3,1])
 with pytest.raises(ValueError):c.bh_five([.01])

@pytest.mark.parametrize('key,value', [('mean',0),('ES',.199999),('q',.050001),('positive_horizons',2),('adjacent_pair',False),('temporal',False),('concentration',False),('capacity',False),('sensitivity',False),('testable',False)])
def test_each_advancement_gate_fails(key,value):
 x=good();assert c.evidence_gate(x);x[key]=value;assert not c.evidence_gate(x)

def test_missing_robustness_fails_support():
 x=good();del x['concentration'];assert not c.evidence_gate(x)

@pytest.mark.parametrize('blocks,expected', [([dict(N=25,mean=.1)]*4,True),([dict(N=25,mean=.1)]*3+[dict(N=25,mean=.3)],True),([dict(N=25,mean=.1)]*3+[dict(N=25,mean=.31)],False),([dict(N=19,mean=.1)]*4,False),([dict(N=25,mean=0)]*4,False)])
def test_temporal_boundaries(blocks,expected):assert c.temporal(blocks)==expected

def test_concentration_share_HHI_ties_and_losses():
 sy=[f'SYNTHETIC_{i:03}' for i in range(20)];v=np.ones(20)/20
 r=c.concentration(sy,v,1,.4,.1,.1);assert r['gate'] and r['removed']==sy[:5] and r['loss']==.75
 assert not c.concentration(sy,v,1,.4,-.1,-.1)['gate']
 assert not c.concentration(sy,v,1,.4,0,0)['gate']
 assert not c.concentration(sy,v,1,.4,.1,.099)['gate']
 with pytest.raises(ValueError):c.concentration(sy,v,2,.4,.1,.1)

def test_all_selection_branches_and_preserved_counterevidence():
 r=rows();selected,labels=c.select(r);assert selected=='S3-C1'
 r['S3-C2']['passing_horizons']=5;assert c.select(r)[0]=='S3-C2'
 r['S3-C1']['relative']['q']=1;r['S3-C2']['relative']['q']=1;assert c.select(r)[0]=='S3-C0'
 r['S3-C0']['absolute']['mean']=0;assert c.select(r)[0]=='NO_ADVANCE'
 r['S3-C0']['absolute']['testable']=False;assert c.select(r)[1]['S3-C0']=='NOT_TESTABLE'
 with pytest.raises(ValueError):c.select({})

@pytest.mark.parametrize('field,value', [('passing_horizons',5),('minimum_positive_blocks',5),('maximum_block_share',.2),('maximum_top5_share',.1),('active_rate',.95),('paired_improvement',.02)])
def test_each_ordered_precedence_field(field,value):
 r=rows();r['S3-C2'][field]=value;assert c.select(r)[0]=='S3-C2'

def test_robustness_before_improvement_and_tolerance():
 r=rows();r['S3-C1']['passing_horizons']=5;r['S3-C2']['paired_improvement']=100;assert c.select(r)[0]=='S3-C1'
 r=rows();r['S3-C2']['paired_improvement']+=1e-13;assert c.select(r)[0]=='S3-C1'

@pytest.mark.parametrize('name',['synthetic_cohort','synthetic_daily_sleeve','synthetic_family','synthetic_hac'])
def test_real_price_operation_denied(name):
 with pytest.raises(ValueError):getattr(c,name)(['AAPL'],None) if name in ('synthetic_family','synthetic_hac') else getattr(c,name)(['AAPL'],None,None,None,None) if name=='synthetic_cohort' else getattr(c,name)(['AAPL'],None,None,None,None,5)

@pytest.mark.parametrize('text',['def f(x):\n return x.shift(-1)','def f(x):\n return synthetic_cohort(x)','from tr_platform.research import swing11_s2b','def f(x):\n return x.read_parquet("outcomes")','p="b905affcb0843a4d"'])
def test_fail_closed_source(text):
 with pytest.raises(ValueError):p.guard_source(text)

def test_self_source_and_input_rejection():
 assert p.guard_source(Path(p.__file__).read_text())
 with pytest.raises(ValueError):certified.verified_input(b'bad immutable bytes')
 with pytest.raises(ValueError):p.predictors(frame().assign(forward_return=1))

@pytest.mark.parametrize('N,rate,blocks,side,reconciled,expected',[(100,.8,[25]*4,5,True,True),(99,.8,[25]*4,5,True,False),(100,.799,[25]*4,5,True,False),(100,.8,[19,27,27,27],5,True,False),(100,.8,[25]*4,4,True,False),(100,.8,[25]*4,5,False,False)])
def test_capacity_gate_exact(N,rate,blocks,side,reconciled,expected):assert c.capacity_gate(N,rate,blocks,side,reconciled)==expected

def test_family_horizon_boundaries():
 assert c.horizon_gate(dict(zip(c.HORIZONS,[1,1,1,-1])))
 assert not c.horizon_gate(dict(zip(c.HORIZONS,[1,-1,1,-1])))
 assert not c.horizon_gate(dict(zip(c.HORIZONS,[1,1,np.nan,1])))

def test_leave_five_full_equal_weight_refit_changes_capacity():
 symbols=[f'SYNTHETIC_{i:02}' for i in range(12)];en=np.ones(12)*100;ex=np.array([110]*6+[90]*6)
 full,_=c.synthetic_cohort(symbols,en,ex,list(range(6)),list(range(6,12)))
 five,_=c.synthetic_cohort(symbols,en,ex,list(range(1,6)),list(range(6,12)))
 no,_=c.synthetic_cohort(symbols,en,ex,[5],list(range(6,12)))
 assert np.isclose(full,.1) and np.isclose(five,.1) and no==0
