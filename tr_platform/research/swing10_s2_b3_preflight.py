"""Coverage-only preflight. No outcome data or outcome computation API."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import uuid

import numpy as np
import pandas as pd
from tr_platform.research.swing10_causal_inputs import causal_factors

PROTOCOL = 'SW10_S2_B3_PREFLIGHT_V1'
PANEL_COLUMNS = ('symbol', 'trade_date', 'open', 'high', 'low', 'close', 'volume')
FACTORS = ('RET_MOM', 'SHORT_REV', 'VOL_REGIME', 'VOL_TURN_V2_CAUSAL', 'HIGH52', 'GAP_OVN')
SCHEMES = {'TAIL_20_80': (.2, .8), 'TERCILE_33_67': (1/3, 2/3)}
INTERACTIONS = tuple((f, c) for c in ('VOL_REGIME', 'VOL_TURN_V2_CAUSAL', 'HIGH52', 'GAP_OVN')
                     for f in ('RET_MOM', 'SHORT_REV'))
CELLS = ('LOW_LOW', 'LOW_HIGH', 'HIGH_LOW', 'HIGH_HIGH')
SPARSE_BELOW = 5
MIN_DATES = 100
ALL_CELL_RATE = .90
BLOCK_RATE = .80
MIN_BLOCK_DATES = 20
MIN_SYMBOLS = 20
INPUT_SHA = 'ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2'
INPUT_BYTES = 2411604
FILES = ('conditioning_scheme_coverage.csv', 'conditioning_interaction_cells.csv',
         'conditioning_date_counts.csv', 'conditioning_symbol_participation.csv',
         'conditioning_temporal_coverage.csv', 'sw10_s2_b3_preflight_manifest.json')


def reject_columns(frame: pd.DataFrame, allowed) -> None:
    if set(frame.columns) != set(allowed) or len(frame.columns) != len(set(frame.columns)):
        raise ValueError('outcome-blind schema: unexpected or missing columns')


def guard_source(source: str) -> None:
    """Fail closed on outcome APIs, external data access, or noncausal shifts."""
    tree = ast.parse(source)
    denied = {'forward_returns', 'date_spreads', 'hac_mean', 'bh_adjust', 'pct_change',
              'read_sql', 'read_parquet', 'read_pickle', 'eval', 'exec', 'roll'}
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in n.names] + [getattr(n, 'module', '') or '']
            if any('swing10_s2_b2' in x or x.startswith(('requests', 'sqlalchemy', 'scipy', 'statsmodels')) for x in names):
                raise ValueError('outcome-capable dependency prohibited')
        if isinstance(n, ast.Call):
            fn = n.func.id if isinstance(n.func, ast.Name) else n.func.attr if isinstance(n.func, ast.Attribute) else ''
            if fn in denied:
                raise ValueError('outcome/future-capable computation prohibited')
            if fn in ('shift', 'diff'):
                arg = n.args[0] if n.args else next((k.value for k in n.keywords if k.arg == 'periods'), None)
                if not isinstance(arg, ast.Constant) or not isinstance(arg.value, int) or arg.value < 0:
                    raise ValueError('only literal nonnegative past shifts allowed')
        if isinstance(n, ast.Attribute) and n.attr in ('iloc', 'iat'):
            raise ValueError('positional future-access API prohibited')


def membership(frame: pd.DataFrame, factor: str, low_q: float, high_q: float) -> pd.DataFrame:
    reject_columns(frame, ('symbol', 'trade_date') + FACTORS)
    if factor not in FACTORS or (low_q, high_q) not in ((.2, .8), (1/3, 2/3)):
        raise ValueError('unauthorized factor or quantile scheme')
    z = frame[['symbol', 'trade_date', factor]].copy()
    z = z[np.isfinite(z[factor])].copy()
    g = z.groupby('trade_date')[factor]
    z['low_boundary'] = g.transform(lambda x: x.quantile(low_q, interpolation='linear'))
    z['high_boundary'] = g.transform(lambda x: x.quantile(high_q, interpolation='linear'))
    z['LOW'] = z[factor] <= z.low_boundary
    z['HIGH'] = z[factor] >= z.high_boundary
    z['low_boundary_tie'] = z[factor] == z.low_boundary
    z['high_boundary_tie'] = z[factor] == z.high_boundary
    z['overlap'] = z.LOW & z.HIGH
    return z.drop(columns=factor)


def blocks(dates) -> dict:
    return {d: i for i, group in enumerate(np.array_split(np.array(sorted(set(dates)), dtype=object), 4), 1) for d in group}


def recommendation(feasible: dict) -> str:
    if set(feasible) != set(SCHEMES):
        raise ValueError('both authorized schemes required')
    return 'TAIL_20_80' if feasible['TAIL_20_80'] else 'TERCILE_33_67' if feasible['TERCILE_33_67'] else 'NEITHER_FEASIBLE'


def audit_factor_frame(frame: pd.DataFrame) -> tuple[dict, dict]:
    reject_columns(frame, ('symbol', 'trade_date') + FACTORS)
    if frame.duplicated(['symbol', 'trade_date']).any():
        raise ValueError('duplicate symbol/date')
    dates = sorted(frame.trade_date.unique())
    global_blocks = blocks(dates)
    population = frame.groupby('trade_date').size()
    fixed = {f: membership(frame, f, .2, .8) for f in ('RET_MOM', 'SHORT_REV')}
    schemes, cells, date_rows, symbols, temporal = [], [], [], [], []
    block_definitions = {}
    for scheme, (lo, hi) in SCHEMES.items():
        feasible_interactions = 0
        for factor, conditioner in INTERACTIONS:
            label = factor+' x '+conditioner
            a = fixed[factor].add_prefix('factor_').rename(columns={'factor_symbol':'symbol','factor_trade_date':'trade_date'})
            b = membership(frame, conditioner, lo, hi).add_prefix('conditioner_').rename(columns={'conditioner_symbol':'symbol','conditioner_trade_date':'trade_date'})
            z = a.merge(b, on=['symbol','trade_date'], validate='one_to_one')
            eligible_dates = sorted(z.trade_date.unique())
            mapping = blocks(eligible_dates)
            block_definitions[label] = [{ 'block': i, 'date_start': str(min(d for d,n in mapping.items() if n==i))[:10],
                                         'date_end': str(max(d for d,n in mapping.items() if n==i))[:10],
                                         'eligible_dates': sum(n==i for n in mapping.values())} for i in range(1,5) if any(n==i for n in mapping.values())]
            local_dates = []
            for date in dates:
                g = z[z.trade_date == date]
                af = a[a.trade_date == date]
                bc = b[b.trade_date == date]
                counts = {cell: int((g['factor_'+cell.split('_')[0]] & g['conditioner_'+cell.split('_')[1]]).sum()) for cell in CELLS}
                row = {'scheme':scheme,'interaction':label,'trade_date':date,
                       'global_panel_block':global_blocks[date], 'interaction_eligible_block':mapping.get(date,0),
                       'panel_observations':int(population[date]), 'factor_eligible_observations':len(af),
                       'conditioner_eligible_observations':len(bc),'joint_eligible_observations':len(g),
                       'factor_eligibility_loss':int(population[date])-len(af),
                       'conditioner_eligibility_loss':int(population[date])-len(bc),
                       'factor_low_boundary':af.factor_low_boundary.mean(),'factor_high_boundary':af.factor_high_boundary.mean(),
                       'conditioner_low_boundary':bc.conditioner_low_boundary.mean(),'conditioner_high_boundary':bc.conditioner_high_boundary.mean(),
                       'factor_LOW_count':int(af.factor_LOW.sum()),'factor_HIGH_count':int(af.factor_HIGH.sum()),
                       'conditioner_LOW_count':int(bc.conditioner_LOW.sum()),'conditioner_HIGH_count':int(bc.conditioner_HIGH.sum()),
                       'joint_factor_LOW_count':int(g.factor_LOW.sum()),'joint_factor_HIGH_count':int(g.factor_HIGH.sum()),
                       'joint_conditioner_LOW_count':int(g.conditioner_LOW.sum()),'joint_conditioner_HIGH_count':int(g.conditioner_HIGH.sum()),
                       'factor_low_boundary_ties':int(af.factor_low_boundary_tie.sum()),'factor_high_boundary_ties':int(af.factor_high_boundary_tie.sum()),
                       'conditioner_low_boundary_ties':int(bc.conditioner_low_boundary_tie.sum()),'conditioner_high_boundary_ties':int(bc.conditioner_high_boundary_tie.sum()),
                       'factor_overlap':int(af.factor_overlap.sum()),'conditioner_overlap':int(bc.conditioner_overlap.sum()),
                       'factor_excess_boundary_ties':max(int(af.factor_low_boundary_tie.sum())-1,0)+max(int(af.factor_high_boundary_tie.sum())-1,0),
                       'conditioner_excess_boundary_ties':max(int(bc.conditioner_low_boundary_tie.sum())-1,0)+max(int(bc.conditioner_high_boundary_tie.sum())-1,0),
                       **{cell+'_count':n for cell,n in counts.items()},
                       'all_four_cells_nonsparse':all(n>=SPARSE_BELOW for n in counts.values())}
                local_dates.append(row)
            dr = pd.DataFrame(local_dates)
            ed = dr[dr.joint_eligible_observations > 0]
            block_rates = []
            for i in range(1,5):
                bd = ed[ed.interaction_eligible_block == i]
                rate = float(bd.all_four_cells_nonsparse.mean()) if len(bd) else 0.
                block_rates.append(bool(len(bd)>=MIN_BLOCK_DATES and rate>=BLOCK_RATE))
                for cell in CELLS:
                    x = bd[cell+'_count']
                    temporal.append({'scheme':scheme,'interaction':label,'cell':cell,'block':i,
                                     'eligible_dates':len(bd),'date_start':str(bd.trade_date.min())[:10] if len(bd) else '',
                                     'date_end':str(bd.trade_date.max())[:10] if len(bd) else '',
                                     'cell_observations':int(x.sum()),'median_date_count':x.median(),'minimum_date_count':x.min(),
                                     'empty_dates':int((x==0).sum()),'sparse_dates':int((x<SPARSE_BELOW).sum()),
                                     'all_four_nonsparse_date_rate':rate,'block_adequate':block_rates[-1]})
            participation = {}
            for cell in CELLS:
                fstate,cstate=cell.split('_')
                mask=z['factor_'+fstate] & z['conditioner_'+cstate]
                counts = z.loc[mask].groupby('symbol').size()
                participation[cell]=len(counts)
                total=int(counts.sum())
                ordered=sorted(counts.index,key=lambda x:(-int(counts[x]),x))
                top={n:float(sum(counts[x] for x in ordered[:n])/total) if total else 0. for n in (1,5,10)}
                for symbol in sorted(frame.symbol.unique()):
                    n=int(counts.get(symbol,0))
                    symbols.append({'scheme':scheme,'interaction':label,'cell':cell,'symbol':symbol,
                                    'participating_symbol_dates':n,'share_of_cell_observations':n/total if total else 0.,
                                    'participation_rate_of_eligible_dates':n/len(ed) if len(ed) else 0.,
                                    'contribution_count_rank':ordered.index(symbol)+1 if symbol in ordered else None})
                x=ed[cell+'_count']
                cells.append({'scheme':scheme,'interaction':label,'cell':cell,'eligible_dates':len(ed),
                              'eligible_symbol_date_observations':int(ed.joint_eligible_observations.sum()),
                              'cell_symbol_date_observations':total,'median_date_count':x.median(),'minimum_date_count':x.min(),
                              'p05_date_count':x.quantile(.05),'p10_date_count':x.quantile(.10),'p25_date_count':x.quantile(.25),
                              'empty_dates':int((x==0).sum()),'empty_date_rate':float((x==0).mean()),
                              'sparse_dates':int((x<SPARSE_BELOW).sum()),'sparse_date_rate':float((x<SPARSE_BELOW).mean()),
                              'unique_symbols':len(counts),'top1_observation_share':top[1],'top5_observation_share':top[5],
                              'top10_observation_share':top[10], 'hhi_observation_share':float(((counts/total)**2).sum()) if total else 0.,
                              'factor_eligibility_loss':int(dr.factor_eligibility_loss.sum()),
                              'conditioner_eligibility_loss':int(dr.conditioner_eligibility_loss.sum()),
                              'factor_eligibility_loss_rate':float(dr.factor_eligibility_loss.sum()/dr.panel_observations.sum()),
                              'conditioner_eligibility_loss_rate':float(dr.conditioner_eligibility_loss.sum()/dr.panel_observations.sum()),
                              'factor_boundary_tie_rate':float((dr.factor_low_boundary_ties.sum()+dr.factor_high_boundary_ties.sum())/dr.factor_eligible_observations.sum()) if dr.factor_eligible_observations.sum() else 0.,
                              'conditioner_boundary_tie_rate':float((dr.conditioner_low_boundary_ties.sum()+dr.conditioner_high_boundary_ties.sum())/dr.conditioner_eligible_observations.sum()) if dr.conditioner_eligible_observations.sum() else 0.,
                              'factor_excess_boundary_tie_rate':float(dr.factor_excess_boundary_ties.sum()/dr.factor_eligible_observations.sum()) if dr.factor_eligible_observations.sum() else 0.,
                              'conditioner_excess_boundary_tie_rate':float(dr.conditioner_excess_boundary_ties.sum()/dr.conditioner_eligible_observations.sum()) if dr.conditioner_eligible_observations.sum() else 0.,
                              'factor_overlap_observations':int(dr.factor_overlap.sum()),
                              'factor_overlap_rate':float(dr.factor_overlap.sum()/dr.factor_eligible_observations.sum()) if dr.factor_eligible_observations.sum() else 0.,
                              'conditioner_overlap_rate':float(dr.conditioner_overlap.sum()/dr.conditioner_eligible_observations.sum()) if dr.conditioner_eligible_observations.sum() else 0.,
                              'conditioner_overlap_observations':int(dr.conditioner_overlap.sum())})
            rate=float(ed.all_four_cells_nonsparse.mean()) if len(ed) else 0.
            overlap=int(dr.factor_overlap.sum()+dr.conditioner_overlap.sum())
            feasible=bool(len(ed)>=MIN_DATES and rate>=ALL_CELL_RATE and all(block_rates) and
                          all(n>=MIN_SYMBOLS for n in participation.values()) and overlap==0)
            feasible_interactions+=int(feasible)
            for row in cells[-4:]:
                row.update(all_four_nonsparse_date_rate=rate,all_four_blocks_adequate=all(block_rates),
                           interaction_feasible=feasible)
            date_rows.extend(local_dates)
        schemes.append({'scheme':scheme,'audited_interactions':len(INTERACTIONS),'feasible_interactions':feasible_interactions,
                        'all_interactions_feasible':feasible_interactions==len(INTERACTIONS),
                        'sparse_cell_below':SPARSE_BELOW,'min_eligible_dates':MIN_DATES,'min_all_four_nonsparse_date_rate':ALL_CELL_RATE,
                        'min_block_dates':MIN_BLOCK_DATES,'min_block_nonsparse_rate':BLOCK_RATE,'min_symbols_per_cell':MIN_SYMBOLS})
    selected=recommendation({r['scheme']:r['all_interactions_feasible'] for r in schemes})
    for r in schemes:r['recommendation']=selected
    return {FILES[0]:pd.DataFrame(schemes),FILES[1]:pd.DataFrame(cells),FILES[2]:pd.DataFrame(date_rows),
            FILES[3]:pd.DataFrame(symbols),FILES[4]:pd.DataFrame(temporal)}, {'recommendation':selected,'blocks':block_definitions}


def audit_panel(panel: pd.DataFrame) -> tuple[dict,dict]:
    reject_columns(panel,PANEL_COLUMNS)
    values=causal_factors(panel)
    return audit_factor_frame(values[['symbol','trade_date']+list(FACTORS)])


def verify_input(path:Path):
    blob=path.read_bytes()
    if len(blob)!=INPUT_BYTES or hashlib.sha256(blob).hexdigest()!=INPUT_SHA:
        raise ValueError('immutable input SHA/bytes mismatch')
    panel=pd.read_csv(path,parse_dates=['trade_date'])
    reject_columns(panel,PANEL_COLUMNS)
    if len(panel)!=44128 or panel.symbol.nunique()!=112 or panel.trade_date.nunique()!=394 or not panel.groupby('symbol').size().eq(394).all():
        raise ValueError('immutable input universe/coverage mismatch')
    if panel.trade_date.min()!=pd.Timestamp('2025-02-03') or panel.trade_date.max()!=pd.Timestamp('2026-08-27'):
        raise ValueError('date coverage mismatch')
    if panel.duplicated(['symbol','trade_date']).any() or panel.isna().any().any() or not np.isfinite(panel[['open','high','low','close','volume']]).all().all():
        raise ValueError('duplicate/null/nonfinite immutable input')
    if ((panel.low>panel.high)|(panel.low>panel[['open','close']].min(axis=1))|(panel.high<panel[['open','close']].max(axis=1))|(panel[['open','high','low','close']]<=0).any(axis=1)|(panel.volume<0)).any():
        raise ValueError('invalid OHLCV')
    return panel


def run(work_root:Path)->dict:
    for name in ('swing10_s2_b3_preflight.py','swing10_causal_inputs.py'):
        guard_source((Path(__file__).parent/name).read_text())
    context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text())
    if len(context['materialized_inputs'])!=1 or context['materialized_inputs'][0]['sha256']!=INPUT_SHA:
        raise ValueError('preflight must materialize ONLY the certified daily panel')
    panel=verify_input(work_root/'job_inputs/swing10/market_daily_history.csv')
    tables,evidence=audit_panel(panel)
    out=work_root/'research_outputs/swing10/s2_b3_preflight'
    out.mkdir(parents=True,exist_ok=True)
    ids={name:str(uuid.uuid4()) for name in FILES}
    declarations=[]
    for name,frame in tables.items():
        path=out/name
        frame.to_csv(path,index=False,float_format='%.17g',lineterminator='\n')
        blob=path.read_bytes()
        declarations.append({'artifact_id':ids[name],'name':name,'size_bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),
                             'object_path':f"artifacts/{context['job_id']}/{context['attempt_id']}/{name}"})
    manifest={'protocol':PROTOCOL,'decision_id':'3a4231dc-647e-40bc-8315-65efd2b30c13',
              'mwe_id':'MWE-SW10-S2B3P-001','execution':context,
              'parent':{'mwe_id':'MWE-SW10-S2B2-001','job_id':'4cff26c3-e2b7-4938-9575-27739e885111',
                        'research_sha':'b912f0c78d9593f2b8d866856217a389ce9baf68','infrastructure_sha':'e038e415eeee315d6e6cd7a4594fdc9bf5f4a01b','run_id':36959940632},
              'input':{'identity':'market_daily_history_2025-02-03_2026-08-27','sha256':INPUT_SHA,'size_bytes':INPUT_BYTES,
                       'rows':44128,'symbols':112,'dates':394,'date_start':'2025-02-03','date_end':'2026-08-27','regenerated':False},
              'conditioning_schemes':SCHEMES,'primary_factor_tails':[.2,.8],
              'interactions':[f+' x '+c for f,c in INTERACTIONS],
              'membership_rule':'independent per-date factor-eligible quantiles, linear interpolation, inclusive; then joint eligibility intersection',
              'operational_screen':{'sparse_below':SPARSE_BELOW,'min_dates':MIN_DATES,'min_all_four_nonsparse_rate':ALL_CELL_RATE,
                                    'min_block_dates':MIN_BLOCK_DATES,'min_each_block_nonsparse_rate':BLOCK_RATE,'min_symbols_per_cell':MIN_SYMBOLS,'overlap_allowed':0},
              'block_definitions':evidence['blocks'],'global_panel_blocks':'four approximately equal chronological input-date blocks, recorded per date',
              'recommendation':evidence['recommendation'],'recommendation_rule':'prefer tail if all eight interactions pass; else tercile if all eight pass; else neither',
              'forward_outcomes_read':False,'forward_outcomes_computed':False,'protected_data_access':False,
              'b2_outcome_artifacts_accessed':False,'source_guard_passed':True,'strict_input_schema':list(PANEL_COLUMNS),
              'factor_source_revision':'b912f0c78d9593f2b8d866856217a389ce9baf68',
              'source_file_hashes':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ('swing10_s2_b3_preflight.py','swing10_causal_inputs.py')},
              'artifacts':declarations,'manifest_identity':{'artifact_id':ids[FILES[-1]],'name':FILES[-1],'sha_size_verification':'external registration/readback; no recursive self-hash'},
              'cost':{'executor':'github_actions','runner':'ubuntu-latest','paid_compute_selected':False,'incremental_billing_verified':False},
              'limitations':['operational coverage screen, not power assurance','no outcome-based inference or final B3 protocol freeze']}
    (out/FILES[-1]).write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    paths=[str((out/n).relative_to(work_root)) for n in FILES]
    return {'status':'PASS','artifact':paths[0],'output_paths':paths,'output_artifact_ids':{p:ids[n] for p,n in zip(paths,FILES)}}
