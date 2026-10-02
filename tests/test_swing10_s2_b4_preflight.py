from pathlib import Path
import ast,json,hashlib
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing10_s2_b4_preflight as b
from cloud_compute import research_revision_adapter as adapter
from cloud_compute.certify_dispatch_contracts import selected_tests


def panel(n=100):
    rows=[]
    for si,sym in enumerate(('AAA','BBB','SPY')):
        for i,date in enumerate(pd.bdate_range('2025-01-01',periods=n)):
            close=100+si*20+i*(si+1)
            rows.append([sym,date,close,close+2,close-2,close,100+i*(si+1)])
    return pd.DataFrame(rows,columns=b.PANEL_COLUMNS)


def context():
    return {'job_id':'synthetic','attempt_id':'synthetic','research_revision':'1'*40,'infrastructure_revision':'2'*40,'materialized_inputs':[{'sha256':b.INPUT_SHA,'size_bytes':b.INPUT_BYTES,'object_path':'governed_inputs/swing10/s2_b1/market_daily_history_2025-02-03_2026-08-27/'+b.INPUT_SHA+'.csv'}]}


@pytest.mark.parametrize('field',['forward_return','future_close','mfe','mae','first_passage','time_to_target','effect_size','p_value','p_raw','beta_interaction','protected_holdout'])
def test_outcome_columns_rejected(field):
    x=panel();x[field]=1
    with pytest.raises(ValueError,match='exact schema'):b.construct(x)


@pytest.mark.parametrize('code',[
 'x.shift(-1)','x.diff(-1)','x.shift(periods=-2)','x.shift(h)','x.pct_change()', 'x.rolling(20,center=True)', 'x.bfill()', 'x.interpolate()', 'np.load("holdout.npy")',
 'forward_returns(x)','first_passage(x)','hac_mean(x)','bh_adjust(x)',
 'import requests','import statsmodels','from tr_platform.research.swing10_s2_b3 import run',
 "pd.read_csv('interaction_b3_summary.csv')","Path('protected/holdout.csv').read_bytes()",
 "Path('factor_causal_summary.csv').read_text()","eval('x')","__import__('os')",'x.iloc[1:]',
])
def test_outcome_primitives_and_scientific_artifacts_rejected(code):
    with pytest.raises(ValueError):b.guard_source(code)


def test_exact_sources_guards_pass():
    for name in b.SOURCE_FILES:b.guard_source((Path(b.__file__).parent/name).read_text())


def test_exact_component_registry_and_no_composite():
    assert len(b.COMPONENTS)==16 and len(set(b.COMPONENT_IDS))==16 and len(b.UNAVAILABLE_IDS)==6
    assert {x[1] for x in b.COMPONENTS}=={'REL_STRENGTH','LIQUIDITY','MARKET_REG'}


def test_exact_b2_source_reused_without_outcome_imports():
    root=Path(b.__file__).parent
    text=(root/'swing10_causal_inputs.py').read_text()
    assert 'b912f0c78d9593f2b8d866856217a389ce9baf68' in text
    assert set(n.module for n in ast.walk(ast.parse(text)) if isinstance(n,ast.ImportFrom))=={'__future__'}


def test_relative_strength_alignment_and_spy_exclusion():
    p=panel();v,_=b.construct(p);d=pd.Timestamp('2025-01-15');x=v['REL_MARKET_10'];a=x[(x.symbol=='AAA')&(x.trade_date==d)].value.item()
    assert a==pytest.approx(110/100-170/140)
    assert 'SPY' not in set(x.symbol);assert len(x)==180


def test_missing_benchmark_date_fails_closed():
    p=panel();p=p.drop(p[(p.symbol=='SPY')&(p.trade_date==p.trade_date.min())].index)
    with pytest.raises(ValueError,match='alignment'):b.construct(p)


@pytest.mark.parametrize('field',['open','high','low','close','volume'])
def test_future_data_invariance(field):
    p=panel();cut=p.trade_date.unique()[50];a,_=b.construct(p);q=p.copy();mask=q.trade_date>cut
    # Preserve OHLC consistency while changing future prices.
    if field=='volume':q.loc[mask,'volume']*=3
    else:
        for c in ('open','high','low','close'):q.loc[mask,c]*=2
    z,_=b.construct(q)
    for name in b.COMPONENT_IDS:pd.testing.assert_frame_equal(a[name][a[name].trade_date<=cut],z[name][z[name].trade_date<=cut],check_exact=True)


def test_prefix_invariance():
    p=panel();cut=p.trade_date.unique()[50];a,_=b.construct(p);z,_=b.construct(p[p.trade_date<=cut])
    for name in b.COMPONENT_IDS:pd.testing.assert_frame_equal(a[name][a[name].trade_date<=cut].reset_index(drop=True),z[name].reset_index(drop=True),check_exact=True)


def test_current_volume_only_numerator_prior20_semantics():
    p=panel();p['volume']=100;target=(p.symbol=='AAA')&(p.trade_date==sorted(p.trade_date.unique())[20]);p.loc[target,'volume']=200
    v,_=b.construct(p);assert v['LIQ_PRIOR20_ACTIVITY'][lambda d:(d.symbol=='AAA')&(d.trade_date==p.loc[target,'trade_date'].item())].value.item()==2
    assert v['LIQ_PRIOR20_ACTIVITY'][lambda d:d.symbol=='AAA'].trade_date.min()==sorted(p.trade_date.unique())[20]


def test_zero_activity_denominator_ineligible():
    p=panel();p['volume']=0;v,_=b.construct(p);assert v['LIQ_PRIOR20_ACTIVITY'].empty


def test_liquidity_exact_proxy_formula():
    p=panel();v,_=b.construct(p)
    np.testing.assert_array_equal(v['LIQ_CLOSE_DOLLAR_VOLUME'].value,p.close*p.volume)
    np.testing.assert_array_equal(v['LIQ_ADJUSTED_PRICE'].value,p.close)
    np.testing.assert_array_equal(v['LIQ_REPORTED_VOLUME'].value,p.volume)
    np.testing.assert_array_equal(v['LIQ_RANGE_SPREAD_PROXY'].value,(p.high-p.low)/p.close)


def test_market_values_are_date_level_not_broadcast():
    v,part=b.construct(panel());assert len(v['MARKET_SPY_TREND10'])==90;assert len(v['MARKET_PANEL_BREADTH10'])==90
    assert v['MARKET_PANEL_BREADTH10'].value.eq(1).all();assert part['MARKET_PANEL_BREADTH10'].symbol.nunique()==2
    expected=np.std([110/100-1,140/120-1],ddof=1);assert v['MARKET_PANEL_DISPERSION10'].value.to_numpy()[0]==pytest.approx(expected)


def test_fixed_blocks_and_coverage_concentration():
    tables,e=b.audit(panel());assert [a['dates'] for a in e['fixed_blocks']]==[25]*4
    s=tables[b.FILES[6]].set_index('component');assert set(s.disposition)=={'CERTIFIED_PROXY','UNAVAILABLE'}
    assert s.loc['LIQ_REPORTED_VOLUME','eligible_dates']==100
    assert s.loc['LIQ_REPORTED_VOLUME','top1_observation_share']==pytest.approx(1/3)
    assert s.loc['REL_SECTOR_10','eligible_dates']==0
    assert s.loc['MARKET_PANEL_BREADTH10','median_symbols_per_eligible_date']==2
    assert len(tables[b.FILES[3]])==64


def test_dispersion_ties_and_single_predictor_geometry():
    d=b.dispersion([1,1,1,1]);assert d['excess_tie_rate']==.75 and d['near_zero_variance']
    tables,_=b.audit(panel());g=tables[b.FILES[5]].set_index('component');assert g.loc['MARKET_PANEL_BREADTH10','centered_predictor_rank']==0


@pytest.mark.parametrize('change',['sha','size','extra','path'])
def test_only_immutable_input_context(change):
    c=context()
    if change=='sha':c['materialized_inputs'][0]['sha256']='0'*64
    if change=='size':c['materialized_inputs'][0]['size_bytes']=1
    if change=='extra':c['materialized_inputs'].append(c['materialized_inputs'][0])
    if change=='path':c['materialized_inputs'][0]['object_path']='protected/holdout.csv'
    with pytest.raises(ValueError,match='immutable'):b.validate_context(c)


def test_input_hash_fail_closed(tmp_path):
    p=tmp_path/'x.csv';p.write_text('symbol,trade_date,close,forward_return\n')
    with pytest.raises(ValueError,match='SHA/bytes'):b.verify_input(p)


@pytest.mark.parametrize('defect',['duplicate','null','bad_price','bad_volume','bad_ohlc'])
def test_input_integrity_fail_closed(defect):
    p=panel()
    if defect=='duplicate':p=pd.concat([p,p.head(1)])
    if defect=='null':p.loc[0,'close']=np.nan
    if defect=='bad_price':p.loc[0,'close']=0
    if defect=='bad_volume':p.loc[0,'volume']=-1
    if defect=='bad_ohlc':p.loc[0,'high']=1
    with pytest.raises(ValueError):b.construct(p)


def test_exact_nine_artifacts_manifest_and_flags(tmp_path,monkeypatch):
    (tmp_path/'job_inputs/swing10').mkdir(parents=True);(tmp_path/'job_inputs/swing10/execution_context.json').write_text(json.dumps(context()))
    monkeypatch.setattr(b,'verify_input',lambda path:panel());here=Path(b.__file__).parent;original=b.SNAPSHOT
    # The runner materializes the frozen snapshot adjacent to both exact research modules.
    snapshot=json.loads((here.parents[1]/'research_protocols/swing10'/original).read_text())
    original_read=Path.read_text
    def read(path,*a,**kw):
        if path==here/original:return json.dumps(snapshot)
        return original_read(path,*a,**kw)
    monkeypatch.setattr(Path,'read_text',read)
    original_bytes=Path.read_bytes
    monkeypatch.setattr(Path,'read_bytes',lambda path: json.dumps(snapshot).encode() if path==here/original else original_bytes(path))
    result=b.run(tmp_path);assert len(result['artifact_contract'])==9;assert len(result['output_artifact_ids'])==9;assert set(result['output_artifact_ids'])==set(result['output_paths']);assert sum(x['is_primary'] for x in result['artifact_contract'])==1
    out=tmp_path/'research_outputs/swing10/s2_b4_preflight';assert set(x.name for x in out.iterdir())==set(b.FILES)
    m=json.loads((out/b.FILES[-1]).read_text());assert len(m['artifacts'])==8 and len(m['dispositions'])==16
    assert all(m[x] is False for x in ('forward_outcomes_read','forward_outcomes_computed','path_outcomes_read','path_outcomes_computed','protected_data_access','scientific_outcome_artifacts_accessed'))
    for a in m['artifacts']:
        assert result['output_artifact_ids'][str((out/a['name']).relative_to(tmp_path))]==a['artifact_id']
        data=(out/a['name']).read_bytes();assert len(data)==a['size_bytes'] and hashlib.sha256(data).hexdigest()==a['sha256']


def test_b4_exact_adapter_bundle_and_certification_selection(monkeypatch,tmp_path):
    calls=[]
    def materialize(root,sha,path,dest):calls.append((sha,path));dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('');return dest
    monkeypatch.setattr(adapter,'materialize_module',materialize)
    def subprocess(args,**kw):
        Path(args[-1]).write_text('{"status":"PASS"}');return type('P',(),{'returncode':0})()
    monkeypatch.setattr(adapter.subprocess,'run',subprocess)
    assert adapter._run_b4_bundle(tmp_path,'1'*40,tmp_path/'bundle',tmp_path)['status']=='PASS'
    assert len(calls)==3 and {sha for sha,_ in calls}=={'1'*40}
    assert not any('s2_b2' in p or 's2_b3' in p for _,p in calls)
    assert 'tests/test_swing10_s2_b4_preflight.py' in selected_tests(b.RUNNER_ID)
    assert not any('s2_b2' in x or 's2_b3' in x for x in selected_tests(b.RUNNER_ID))
