from pathlib import Path
import ast
import json
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing10_s2_b3_preflight as p
from tr_platform.research import swing10_causal_inputs as c


def panel():
    rng=np.random.default_rng(613)
    dates=pd.bdate_range('2024-01-01',periods=150)
    rows=[]
    for i in range(12):
        x=100*np.exp(np.cumsum(rng.normal(0,.01,len(dates))))
        for j,d in enumerate(dates):
            rows.append(dict(symbol=f'S{i}',trade_date=d,open=x[j]*.999,high=x[j]*1.02,low=x[j]*.98,close=x[j],volume=float(rng.integers(100,10000))))
    return pd.DataFrame(rows)


def test_factor_function_ast_matches_certified_b2_without_importing_outcomes():
    root=Path(__file__).resolve().parents[1]
    def selected(path):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ('volume_turnover','causal_factors')}
    assert selected(root/'tr_platform/research/swing10_causal_inputs.py')==selected(root/'tr_platform/research/swing10_s2_b2_core.py')


@pytest.mark.parametrize('current,expected',[(100,1.),(200,2.),(50,.5)])
def test_causal_volume(current,expected):
    x=c.volume_turnover(pd.Series([100.]*20+[current]))
    assert x.VOL_TURN_V2_CAUSAL.iloc[-1]==expected
    assert x.prior20_mean.iloc[-1]==100


def test_eligibility_volume_history_and_zero():
    assert c.volume_turnover(pd.Series([100.]*20)).VOL_TURN_V2_CAUSAL.isna().all()
    assert c.volume_turnover(pd.Series([0.]*20+[100.])).VOL_TURN_V2_CAUSAL.isna().all()


def test_future_factor_and_both_scheme_membership_invariance():
    z=panel();cut=sorted(z.trade_date.unique())[130]
    changed=z.copy(); mask=changed.trade_date>cut
    changed.loc[mask,['open','high','low','close','volume']]*=100
    a=c.causal_factors(z);b=c.causal_factors(changed)
    a=a[['symbol','trade_date']+list(p.FACTORS)];b=b[a.columns]
    pd.testing.assert_frame_equal(a[a.trade_date<=cut],b[b.trade_date<=cut])
    for qs in p.SCHEMES.values():
        for f in p.FACTORS:
            m1=p.membership(a,f,*qs);m2=p.membership(b,f,*qs)
            pd.testing.assert_frame_equal(m1[m1.trade_date<=cut],m2[m2.trade_date<=cut])


@pytest.mark.parametrize('column',['forward_1','f10','p_raw','effect','future_close','VOL_TURN_B1_LEGACY'])
def test_outcome_or_extra_column_rejected(column):
    z=panel();z[column]=1
    with pytest.raises(ValueError,match='outcome-blind schema'):p.audit_panel(z)
    f=c.causal_factors(panel())[['symbol','trade_date']+list(p.FACTORS)]
    f[column]=1
    with pytest.raises(ValueError,match='outcome-blind schema'):p.audit_factor_frame(f)


@pytest.mark.parametrize('source',['x.close.shift(-1)','x.close.shift(h)','x.close.pct_change(-1)',
                                   'forward_returns(x)','x.close.iloc[2:]','from tr_platform.research.swing10_s2_b2_core import hac_mean'])
def test_source_guard_rejects_future_and_outcome_calculations(source):
    with pytest.raises(ValueError):p.guard_source(source)


def test_live_preflight_source_guard():
    root=Path(__file__).resolve().parents[1]/'tr_platform/research'
    for name in ('swing10_s2_b3_preflight.py','swing10_causal_inputs.py'):
        p.guard_source((root/name).read_text())


def factor_fixture():
    dates=pd.bdate_range('2025-01-01',periods=8)
    rows=[]
    for date in dates:
        for i in range(12):
            rows.append({'symbol':f'S{i:02}','trade_date':date,**{f:float(i) for f in p.FACTORS}})
    return pd.DataFrame(rows)


def test_quantile_membership_and_overlap_are_inclusive():
    z=factor_fixture()
    tail=p.membership(z,'RET_MOM',.2,.8)
    tercile=p.membership(z,'RET_MOM',1/3,2/3)
    assert tail.groupby('trade_date').LOW.sum().eq(3).all()
    assert tercile.groupby('trade_date').LOW.sum().eq(4).all()
    z.RET_MOM=0
    tied=p.membership(z,'RET_MOM',.2,.8)
    assert tied.overlap.all()
    with pytest.raises(ValueError):p.membership(z,'RET_MOM',.1,.9)
    with pytest.raises(ValueError):p.membership(z,'VOL_TURN_B1_LEGACY',.2,.8)


def test_all_interactions_counted_without_outcomes_and_sparse_cells_visible():
    tables,evidence=p.audit_factor_frame(factor_fixture())
    assert len(tables[p.FILES[0]])==2
    assert len(tables[p.FILES[1]])==64
    assert len(tables[p.FILES[2]])==2*8*8
    assert len(tables[p.FILES[4]])==2*8*4*4
    cells=tables[p.FILES[1]]
    assert cells[cells.cell=='LOW_HIGH'].empty_date_rate.eq(1).all()
    assert evidence['recommendation']=='NEITHER_FEASIBLE'
    counts=tables[p.FILES[2]]
    assert counts.interaction_eligible_block.isin([1,2,3,4]).all()
    assert counts.LOW_LOW_count.min()==3


@pytest.mark.parametrize('tail,tercile,result',[(True,True,'TAIL_20_80'),(True,False,'TAIL_20_80'),(False,True,'TERCILE_33_67'),(False,False,'NEITHER_FEASIBLE')])
def test_recommendation_predeclared_priority(tail,tercile,result):
    assert p.recommendation({'TAIL_20_80':tail,'TERCILE_33_67':tercile})==result


def test_preflight_certification_selects_no_outcome_tests():
    from cloud_compute.certify_dispatch_contracts import selected_tests
    tests=selected_tests('SW10-S2-B3-PREFLIGHT')
    assert 'tests/test_swing10_s2_b3_preflight.py' in tests
    assert not any('s2_b2' in t for t in tests)


def test_causal_denominator_current_and_future_invariance():
    x=pd.Series([100.]*20+[200.,300.])
    y=x.copy();y.iloc[20]=50.;y.iloc[21]=99999.
    a=c.volume_turnover(x);b=c.volume_turnover(y)
    assert a.prior20_mean.iloc[20]==b.prior20_mean.iloc[20]==100.
    assert a.VOL_TURN_V2_CAUSAL.iloc[20]==2.
    assert b.VOL_TURN_V2_CAUSAL.iloc[20]==.5


def test_input_hash_fail_closed(tmp_path):
    path=tmp_path/'data.csv';path.write_text('forward_1\n1\n')
    with pytest.raises(ValueError,match='SHA/bytes'):p.verify_input(path)


def test_six_artifacts_and_single_certified_input_contract(monkeypatch,tmp_path):
    context=tmp_path/'job_inputs/swing10/execution_context.json'
    context.parent.mkdir(parents=True)
    ctx={'job_id':'job','attempt_id':'attempt','materialized_inputs':[{'sha256':p.INPUT_SHA}]}
    context.write_text(json.dumps(ctx))
    monkeypatch.setattr(p,'verify_input',lambda path:panel())
    # Count fixture keeps test fast while production run still exercises causal
    # construction separately in future-invariance and AST-parity fixtures.
    monkeypatch.setattr(p,'audit_panel',lambda value:p.audit_factor_frame(factor_fixture()))
    result=p.run(tmp_path)
    assert len(result['output_paths'])==6 and len(result['output_artifact_ids'])==6
    out=tmp_path/'research_outputs/swing10/s2_b3_preflight'
    manifest=json.loads((out/p.FILES[-1]).read_text())
    assert len(manifest['interactions'])==8 and len(manifest['conditioning_schemes'])==2
    assert not manifest['forward_outcomes_read'] and not manifest['forward_outcomes_computed']
    assert not manifest['b2_outcome_artifacts_accessed'] and not manifest['protected_data_access']
    ctx['materialized_inputs'].append({'sha256':p.INPUT_SHA})
    context.write_text(json.dumps(ctx))
    with pytest.raises(ValueError,match='ONLY'):p.run(tmp_path)
