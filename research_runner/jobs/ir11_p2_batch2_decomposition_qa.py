from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

P1_REL=Path('research_outputs/ir11/p1/ir11_p1_dense_clock_observations_2025_v1.parquet')
PATH_REL=Path('research_outputs/ir11/p2/ir11_p2_forward_paths_2025_v1.parquet')
PAIR_REL=Path('research_outputs/ir11/p2/ir11_p2_pairwise_outcomes_2025_v1.parquet')
OUT_REL=Path('research_outputs/ir11/p2/batch2')
PRIMARY={(0.50,0.25),(0.50,0.50),(0.75,0.50),(1.00,0.50)}
WARN={'MNDY','NOW','KLAC','BKNG','BLK','AXON','URI','REGN'}
EXPECTED=(149546,3738650,104,250)

def population(df):
    pos=df['displacement_pct']>0
    top=df['relative_top5_trailing60'].fillna(False)
    return np.select([top,pos],['REL_TOP5','POSITIVE_NON_TOP5'],default='NON_POSITIVE')

def summarize_pairs(df,groups):
    w=df.copy(); w['favorable_first']=w.first_passage_outcome.eq('FAVORABLE_FIRST'); w['adverse_first']=w.first_passage_outcome.eq('ADVERSE_FIRST'); w['ambiguous']=w.first_passage_outcome.eq('AMBIGUOUS_SAME_BAR'); w['neither']=w.first_passage_outcome.eq('NEITHER'); w['resolved']=w.favorable_first|w.adverse_first
    keys=groups+['favorable_threshold_pct','adverse_threshold_pct']
    o=w.groupby(keys,dropna=False).agg(n=('symbol','size'),symbols=('symbol','nunique'),dates=('trade_date','nunique'),favorable_first=('favorable_first','sum'),adverse_first=('adverse_first','sum'),ambiguous_same_bar=('ambiguous','sum'),neither=('neither','sum'),resolved=('resolved','sum')).reset_index()
    o['favorable_first_pct_all']=100*o.favorable_first/o.n; o['favorable_first_pct_resolved']=100*o.favorable_first/o.resolved.replace(0,np.nan); o['ambiguous_pct']=100*o.ambiguous_same_bar/o.n
    return o

def run(work_root:Path)->dict:
    root=Path(work_root).resolve(); out=root/OUT_REL; out.mkdir(parents=True,exist_ok=True)
    p1=pd.read_parquet(root/P1_REL); paths=pd.read_parquet(root/PATH_REL); pairs=pd.read_parquet(root/PAIR_REL)
    gate=(len(paths),len(pairs),paths.symbol.nunique(),pd.to_datetime(paths.trade_date).dt.date.nunique())
    if gate!=EXPECTED: raise RuntimeError(f'P2B parity gate failed {gate} != {EXPECTED}')
    if set(paths.symbol.unique()) & WARN: raise RuntimeError('WARN symbols leaked into certified 104-symbol population')
    pairs=pairs[[ (float(f),float(a)) in PRIMARY for f,a in zip(pairs.favorable_threshold_pct,pairs.adverse_threshold_pct)]].copy()
    pairs['population']=population(pairs); pairs['trade_date']=pd.to_datetime(pairs.trade_date).dt.date; pairs['month']=pd.to_datetime(pairs.trade_date).astype('datetime64[ns]').dt.to_period('M').astype(str)
    pairs['first_hit_session']=np.where(pairs.first_passage_outcome.eq('FAVORABLE_FIRST'),pairs.favorable_hit_session,np.where(pairs.first_passage_outcome.eq('ADVERSE_FIRST'),pairs.adverse_hit_session,np.where(pairs.first_passage_outcome.eq('AMBIGUOUS_SAME_BAR'),pairs.favorable_hit_session,None)))
    pairs['staleness_bucket']=pd.cut(pairs.staleness_minutes,[-np.inf,1,5,15,30,np.inf],labels=['<=1','>1-5','>5-15','>15-30','>30'])
    outputs=[]
    def save(df,name):
        p=out/name; df.to_csv(p,index=False); outputs.append(str(p)); return p
    save(summarize_pairs(pairs,['clock','population']),'ir11_p2_b2_primary_controls.csv')
    save(summarize_pairs(pairs,['clock','raw_displacement_bin']),'ir11_p2_b2_primary_rawbin.csv')
    save(summarize_pairs(pairs,['clock','population','first_hit_session']),'ir11_p2_b2_primary_session_decomposition.csv')
    save(summarize_pairs(pairs,['clock','population','staleness_bucket']),'ir11_p2_b2_staleness.csv')
    rel=pairs[pairs.population.eq('REL_TOP5') & pairs.first_passage_outcome.eq('FAVORABLE_FIRST')]
    save(rel.groupby(['clock','symbol']).size().rename('favorable_first_events').reset_index(),'ir11_p2_b2_top5_symbol_concentration.csv')
    save(rel.groupby(['clock','trade_date']).size().rename('favorable_first_events').reset_index(),'ir11_p2_b2_top5_date_concentration.csv')
    target=[]
    for t in (0.50,0.75,1.00):
        tag=f'{t:.2f}'.replace('.','p'); col=f'fav_{tag}_session'
        x=paths.copy(); x['population']=population(x)
        z=x.groupby(['clock','population',col],dropna=False).size().rename('n').reset_index(); z['target_pct']=t; target.append(z)
    save(pd.concat(target,ignore_index=True),'ir11_p2_b2_target_completion_session.csv')
    qa=p1.copy(); qa['abs_displacement_pct']=qa.displacement_pct.abs(); qa['extreme_ge_10']=qa.abs_displacement_pct.ge(10); qa['extreme_ge_15']=qa.abs_displacement_pct.ge(15); qa['extreme_ge_25']=qa.abs_displacement_pct.ge(25); qa['extreme_ge_50']=qa.abs_displacement_pct.ge(50)
    save(qa.nlargest(500,'abs_displacement_pct'),'ir11_p2_b2_top500_abs_displacement_outliers.csv')
    save(pd.DataFrame([{'p1_rows':len(p1),'p2_paths':len(paths),'pair_rows':3738650,'symbols':paths.symbol.nunique(),'dates':pd.to_datetime(paths.trade_date).dt.date.nunique(),'warn_symbols_expected':','.join(sorted(WARN)),'warn_symbols_in_analyzed_population':','.join(sorted(set(paths.symbol.unique())&WARN)),'abs_ge_10':int(qa.extreme_ge_10.sum()),'abs_ge_15':int(qa.extreme_ge_15.sum()),'abs_ge_25':int(qa.extreme_ge_25.sum()),'abs_ge_50':int(qa.extreme_ge_50.sum())}]),'ir11_p2_b2_qa.csv')
    return {'artifact':outputs[0],'output_paths':outputs,'research_phase':'IR11-P2','batch':'P2-B2','research_logic_modified':False,'warn_symbols':sorted(WARN)}
