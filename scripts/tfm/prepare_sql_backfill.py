"""Verify Supabase-computed six-month outcomes and package atomic publication.
Primary pattern/metric computation is backfill_20261104_six_months.sql on Supabase.
This client-side step independently verifies it and canonicalizes provenance hashes.
Inputs are read-only operational exports; outputs contain no credentials.
"""
import argparse
import hashlib
import json
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from engine import RULES,VERSION,SYMBOLS,SECTORS,TECH_STOCKS,TECH_ETFS,digest,observation,regime,session,target_for,valid_bar


def prepare(triplets,spy):
    if VERSION!='tfm-bearish-v2':raise ValueError('UNEXPECTED_RULE_VERSION')
    start=date(2026,5,4);end=date(2026,11,3)
    days={date.fromisoformat(r['date']) for r in spy}
    d=min(days);expected=set()
    while d<=max(days):
        if session(d):expected.add(d)
        d+=timedelta(days=1)
    if days!=expected:raise ValueError('SPY_CALENDAR_GAPS')
    spy_index={('SPY',date.fromisoformat(r['date'])):{'close':r['close']} for r in spy}
    fridays=[];d=start-timedelta(days=7)
    while d<=end:
        if d.weekday()==4 and session(d) and session(d-timedelta(days=1)):
            t,c=target_for(d)
            if start<=t<=end:fridays.append((d,t,c))
        d+=timedelta(days=1)
    expected_keys={(s,f.isoformat()) for s in SYMBOLS for f,_,_ in fridays}
    keys={(r['symbol'],r['friday']) for r in triplets}
    if keys!=expected_keys or len(keys)!=len(triplets):raise ValueError('TRIPLET_COVERAGE_OR_DUPLICATES')
    now=datetime.now(timezone.utc);setups=[];outcomes=[];source_bars={}
    for row in triplets:
        f=date.fromisoformat(row['friday']);t,c=target_for(f)
        if row['target_date']!=t.isoformat() or row['cohort']!=c:raise ValueError('TARGET_CALENDAR_MISMATCH')
        th,fr,tg=(row[k] for k in ('thursday_bar','friday_bar','target_bar'))
        for bar,day in [(th,f-timedelta(days=1)),(fr,f),(tg,t)]:
            if not bar or not valid_bar(bar) or bar['symbol']!=row['symbol'] or bar['trade_date']!=day.isoformat():raise ValueError('INVALID_SOURCE_BAR')
            if not bar.get('run_id') or len(bar.get('response_sha256',''))!=64:raise ValueError('MISSING_PROVENANCE')
            key=(bar['symbol'],bar['trade_date'])
            if key in source_bars and source_bars[key]!=bar:raise ValueError('INCONSISTENT_SOURCE_SNAPSHOT')
            source_bars[key]=bar
        market=regime(spy_index,f)
        if market!=row['market_condition']:raise ValueError('SQL_EMA_VERIFICATION_FAILED')
        s=observation(row['symbol'],f,t,c,th,fr,now,market)
        if s['origin']!='HISTORICAL' or s['qualifies']!=row['qualifies']:raise ValueError('SQL_SETUP_VERIFICATION_FAILED')
        opening,high,low,close=(Decimal(str(tg[k])) for k in ('open','high','low','close'))
        ref=Decimal(str(fr['low']))
        result={'setup_key':s['setup_key'],'setup_sha256':s['setup_sha256'],'hit':low<ref,'gap_through':opening<ref,
                'mfe_pct':float(max(Decimal(0),(opening-low)/opening*100)),
                'mae_pct':float(max(Decimal(0),(high-opening)/opening*100)),
                'close_return_pct':float((close/opening-1)*100),'target_bar':tg}
        if any(result[k]!=row[k] for k in ('hit','gap_through')):raise ValueError('SQL_OUTCOME_VERIFICATION_FAILED')
        if any(abs(result[k]-float(row[k]))>1e-10 for k in ('mfe_pct','mae_pct','close_return_pct')):raise ValueError('SQL_METRIC_VERIFICATION_FAILED')
        result['result_sha256']=digest(result)
        setups.append({**{k:s[k] for k in ('setup_key','rule_version','symbol','friday','target_date','cohort','qualifies','origin','setup_sha256')},'payload':s})
        outcomes.append({'setup_key':result['setup_key'],'setup_sha256':result['setup_sha256'],'result_sha256':result['result_sha256'],'payload':result})
    per_symbol={symbol:{'bars':sum(s==symbol for s,_ in source_bars),
                        'first':min(d for s,d in source_bars if s==symbol),
                        'last':max(d for s,d in source_bars if s==symbol)} for symbol in SYMBOLS}
    coverage={'source_first':min(d for _,d in source_bars),'source_last':max(d for _,d in source_bars),
              'requested_start':start.isoformat(),'requested_end':end.isoformat(),
              'historical_target_start':start.isoformat(),'historical_target_end':end.isoformat(),
              'six_month_complete':True,'five_year_complete':False,'invalid_bars':0,
              'missing_setup_pairs':0,'missing_matured_outcomes':0,'symbols':per_symbol,
              'history_label':'Six-month historical load verified; five-year target remains open'}
    diagnostics={'compute_mechanism':'DIRECT_GOVERNED_EXECUTION_SUPABASE_SQL','sql_sha256':hashlib.sha256(Path(__file__).with_name('backfill_20261104_six_months.sql').read_bytes()).hexdigest(),
                 'rules_sha256':digest(RULES),'independent_verification':'PASS: calendar, source OHLC/provenance, EMA, pattern, gap and all excursions',
                 'setups_added':len(setups),'outcomes_added':len(outcomes),'qualified_setups':sum(s['qualifies'] for s in setups),
                 'reference_corrections':0,'outcome_corrections':0,'market_provider_calls':0,'cost_policy':'ZERO_INCREMENTAL_COST_FIRST','billing_verified':False}
    return {'p_setups':setups,'p_outcomes':outcomes,'p_coverage':coverage,'p_diagnostics':diagnostics}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('triplets');parser.add_argument('spy');parser.add_argument('output');a=parser.parse_args()
    payload=prepare(json.loads(Path(a.triplets).read_text()),json.loads(Path(a.spy).read_text()))
    Path(a.output).write_text(json.dumps(payload,separators=(',',':'),allow_nan=False))
    print(json.dumps({'coverage':payload['p_coverage'],'diagnostics':payload['p_diagnostics']}))
