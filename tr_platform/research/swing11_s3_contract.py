"""Prospectively frozen S3 constants/schemas and SYNTHETIC-only estimators.

No data readers or real research execution exist in this module.
"""
from functools import cmp_to_key
import numpy as np
from tr_platform.research import swing11_s2a_supplement as stats

HORIZONS=(5,7,10,15)
CANDIDATES=('S3-C0','S3-C1','S3-C2')
TESTS=tuple([f'ABS_{c}' for c in CANDIDATES]+[f'REL_{c}_vs_S3-C0' for c in CANDIDATES[1:]])
SENSITIVITIES=('boundary_ties_input_order','capacity_5_vs_4','next_open_H_indexing','sleeve_cash_conservation')
FUTURE_SCHEMAS={
 'sw11_s3_candidate_primary_summary.csv':('test_id','candidate','evidence','N_dates','mean','median','sample_sd','ES','hac_lag','hac_se','t','raw_p','bh_p','ci_low','ci_high','positive_share','cohort_mean','cohort_median','cohort_sd','cohort_hit_rate','cumulative_development_return','maximum_drawdown_diagnostic','testable','reason','direction_gate','material_gate','fdr_gate','horizon_gate','temporal_gate','concentration_gate','capacity_gate','sensitivity_gate'),
 'sw11_s3_candidate_cohort_returns.csv':('candidate','decision_date','horizon','entry_date','exit_date','long_N','short_N','no_trade','long_return','short_return','cohort_return','dailyized_return','family_return','sample_role'),
 'sw11_s3_temporal_stability.csv':('test_id','block','start','end','N','mean','median','positive','absolute_contribution','absolute_share','available'),
 'sw11_s3_symbol_concentration.csv':('test_id','symbol','contribution','absolute_share','absolute_rank','top5_removed','top1_share','top5_share','top10_share','hhi','reconciled','full_effect','leave5_effect','full_ES','leave5_ES','ES_loss','sign_reversal','available','gate'),
 'sw11_s3_turnover_exposure.csv':('candidate','horizon','date','active_cohorts','cash_sleeves','gross','net','entry_turnover','exit_turnover','daily_fixed_capital_pnl','cumulative_fixed_capital_pnl','drawdown_from_peak_diagnostic','initial_capital','conservation_verified'),
 'sw11_s3_implementation_sensitivity.csv':('case_id','synthetic_only','passed','fixture_identity','detail'),
 'sw11_s3_candidate_dispositions.csv':('candidate','disposition','testable','absolute_pass','relative_pass','failed_gates','passing_horizons','minimum_positive_blocks','maximum_block_share','maximum_top5_share','active_rate','paired_improvement','selected','selection_reason'),
 'sw11_s3_semantic_audit.csv':('check','passed','detail','input_id','input_sha','input_bytes','protected_access','outcome_authorization','sample_role'),
 'sw11_s3_manifest.json':('complete_authority','candidate_registry','test_registry','horizons','schemas','sample_rule','comparison_calendar','blocks','input','execution','cost','protection','artifact_declarations','outcome_exposure')}

def synthetic_only(symbols):
 if not symbols or any(not str(s).startswith('SYNTHETIC_') for s in symbols):
  raise ValueError('real S3 outcomes denied in S3P')

def synthetic_cohort(symbols,entry,exit,long,short):
 synthetic_only(symbols)
 entry=np.asarray(entry,float);exit=np.asarray(exit,float)
 if not np.isfinite(entry).all() or not np.isfinite(exit).all() or (entry<=0).any() or (exit<=0).any():raise ValueError('invalid synthetic bars')
 if len(long)<5 or len(short)<5:return 0.,np.zeros(len(symbols))
 if set(long)&set(short):raise ValueError('overlapping sides')
 contributions=np.zeros(len(symbols));contributions[long]=.5*(exit[long]/entry[long]-1)/len(long);contributions[short]=.5*(1-exit[short]/entry[short])/len(short)
 return float(contributions.sum()),contributions

def synthetic_daily_sleeve(symbols,entry,previous,current,weights,horizon):
 synthetic_only(symbols)
 if horizon not in HORIZONS:raise ValueError('unregistered horizon')
 entry=np.asarray(entry,float);previous=np.asarray(previous,float);current=np.asarray(current,float);weights=np.asarray(weights,float)
 if np.sum(abs(weights))>1+1e-12 or abs(weights.sum())>1e-12 or not (entry>0).all():raise ValueError('invalid inception exposure')
 pnl=float((weights*(current-previous)/entry).sum()/horizon)
 marked=weights*current/entry/horizon
 return {'pnl':pnl,'gross':float(abs(marked).sum()),'net':float(marked.sum()),'turnover':float(abs(marked).sum())}

def indices(t,h,n):
 if h not in (*HORIZONS,20) or t<0 or t+h>=n:raise ValueError('calendar capacity')
 return t+1,t+h

def synthetic_family(symbols,cohorts):
 synthetic_only(symbols)
 a=np.asarray(cohorts,float)
 if a.ndim!=2 or a.shape[1]!=4 or not np.isfinite(a).all():raise ValueError('four complete caps required')
 return (a/np.asarray(HORIZONS)).mean(axis=1)

def synthetic_hac(symbols,series):
 synthetic_only(symbols)
 # Certified H-1 implementation with H15 => exactly Bartlett lag14.
 return stats.hac(np.asarray(series,float),15,'INTERACTION')

def bh_five(raw):
 if len(raw)!=5:raise ValueError('five fixed BH slots')
 p=np.asarray([1. if x is None or not np.isfinite(x) else x for x in raw],float)
 if (p<0).any() or (p>1).any():raise ValueError('invalid p value')
 order=np.argsort(p,kind='stable');adjusted=np.minimum.accumulate((p[order]*5/np.arange(1,6))[::-1])[::-1]
 result=np.empty(5);result[order]=np.minimum(adjusted,1)
 return result

def temporal(blocks):
 if len(blocks)!=4 or any(b.get('N',0)<20 or not np.isfinite(b.get('mean',np.nan)) for b in blocks):return False
 effects=np.array([abs(b['N']*b['mean']) for b in blocks]);total=effects.sum()
 return bool(sum(b['mean']>0 for b in blocks)>=3 and total>0 and effects.max()/total<=.5)

def concentration(symbols,contributions,full_effect,full_ES,leave_effect,leave_ES):
 symbols=list(symbols);v=np.asarray(contributions,float)
 if len(v)!=len(symbols) or not np.isfinite(v).all() or not np.isclose(v.sum(),full_effect,rtol=1e-9,atol=1e-12):raise ValueError('additive reconciliation')
 order=sorted(range(len(v)),key=lambda i:(-abs(v[i]),symbols[i]));total=abs(v).sum()
 if total<=0:return {'available':False,'gate':False,'removed':[]}
 shares=abs(v)/total;top5=float(shares[order[:5]].sum());hhi=float(shares@shares)
 available=all(np.isfinite(x) for x in (full_effect,full_ES,leave_effect,leave_ES)) and full_ES!=0
 loss=1-abs(leave_ES)/abs(full_ES) if available else np.nan
 return {'available':available,'gate':bool(available and full_effect>0 and leave_effect>0 and top5<=.5 and hhi<=.1 and loss<=.75),'top1':float(shares[order[:1]].sum()),'top5':top5,'top10':float(shares[order[:10]].sum()),'hhi':hhi,'removed':[symbols[i] for i in order[:5]],'loss':loss,'sign_reversal':bool(full_effect*leave_effect<0)}

def evidence_gate(row):
 # Missing robustness fails support but doesn't invent an invalid primary.
 return bool(row.get('testable') and row.get('mean',0)>0 and row.get('ES',0)>=.2 and row.get('q',1)<=.05 and row.get('positive_horizons',0)>=3 and row.get('adjacent_pair',False) and row.get('temporal',False) and row.get('concentration',False) and row.get('capacity',False) and row.get('sensitivity',False))

def capacity_gate(N,active_rate,block_counts,minimum_side,reconciled):
 return bool(N>=100 and np.isfinite(active_rate) and active_rate>=.8 and len(block_counts)==4 and min(block_counts)>=20 and minimum_side>=5 and reconciled is True)

def horizon_gate(means):
 if set(means)!=set(HORIZONS) or not np.isfinite(list(means.values())).all():return False
 positive=[means[h]>0 for h in HORIZONS]
 return bool(sum(positive)>=3 and any(a and b for a,b in zip(positive,positive[1:])))

def select(rows):
 if set(rows)!=set(CANDIDATES):raise ValueError('exact three architecture registry')
 labels={};qual=[]
 for c,row in rows.items():
  primary=row.get('absolute',{}).get('testable',False) and (c=='S3-C0' or row.get('relative',{}).get('testable',False))
  passes=primary and evidence_gate(row['absolute']) and (c=='S3-C0' or evidence_gate(row.get('relative',{})))
  labels[c]='NOT_TESTABLE' if not primary else 'QUALIFIED' if passes else 'NO_ADVANCE'
  if passes:qual.append(c)
 rv=[c for c in qual if c!='S3-C0']
 if not rv:return ('S3-C0' if 'S3-C0' in qual else 'NO_ADVANCE'),labels
 fields=(('passing_horizons',-1),('minimum_positive_blocks',-1),('maximum_block_share',1),('maximum_top5_share',1),('active_rate',-1),('paired_improvement',-1))
 def cmp(a,b):
  for name,direction in fields:
   x=rows[a].get(name);y=rows[b].get(name)
   if x is None or y is None or not np.isfinite([x,y]).all():raise ValueError('selection diagnostic unavailable')
   if abs(x-y)>1e-12:return direction*(1 if x>y else -1)
  return (a>b)-(a<b)
 return sorted(rv,key=cmp_to_key(cmp))[0],labels
