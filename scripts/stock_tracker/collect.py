"""Isolated, bounded stock archive. Each symbol publishes independently.
Uses existing credential path and provider contract; no research datasets.
"""
import os,sys,time,uuid,re
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sector_rotation'))
from collect_tech import request_json,normalize,ET
MWE_ID='MWE-SECTOR-STOCKS-001'
FIELDS=('close','volume','open','high','low')
def validate_calendar(rows,reference):
    dates={r['trade_date'] for r in rows}
    if not dates or not dates.issubset(reference) or max(dates)!=max(reference):
        raise ValueError('STOCK_CALENDAR_OR_LATEST_MISMATCH')
def main():
    base=os.environ['SUPABASE_URL'].rstrip('/')+'/rest/v1/'
    secret=os.environ['SUPABASE_SECRET_KEY']
    key=os.environ.get('MASSIVE_API_KEY') or os.environ.get('TR_MASSIVE_API_KEY')
    if not key:raise RuntimeError('MASSIVE_KEY_NOT_CONFIGURED')
    headers={'apikey':secret,'Authorization':'Bearer '+secret}
    def db(path,method='GET',data=None):return request_json(base+path,headers,method,data)[0]
    envelope=db('work_envelopes?mwe_id=eq.'+MWE_ID+'&select=work_envelope_id,authority_ceiling,cost_policy_code')
    if len(envelope)!=1 or envelope[0]['authority_ceiling']!='E1' or envelope[0]['cost_policy_code']!='ZERO_INCREMENTAL_COST_FIRST':raise RuntimeError('INVALID_AUTHORITY')
    sha=os.environ['GITHUB_SHA']
    if not re.fullmatch('[0-9a-f]{40}',sha):raise ValueError('INVALID_SHA')
    requests=db('stock_tracker_symbols?select=symbol&order=requested_at,symbol&limit=30')
    symbols=['SPY']+[r['symbol'] for r in requests if r['symbol']!='SPY']
    if any(not re.fullmatch('[A-Z][A-Z0-9.-]{0,9}',s) for s in symbols):raise ValueError('INVALID_SYMBOL')
    now=datetime.now(ET);start=(now.date()-timedelta(days=729)).isoformat();end=(now.date()-timedelta(days=1)).isoformat()
    reference=None;failures=0
    for i,symbol in enumerate(symbols):
        if i:time.sleep(15)
        run_id=str(uuid.uuid4());meta={'symbol':symbol,'mwe_id':MWE_ID,'cost_policy':'ZERO_INCREMENTAL_COST_FIRST','billing_verified':False}
        db('stock_tracker_runs','POST',{'run_id':run_id,'work_envelope_id':envelope[0]['work_envelope_id'],'status':'RUNNING','git_sha':sha,'external_run_id':os.environ['GITHUB_RUN_ID'],'requested_start':start,'requested_end':end,'metadata_json':meta})
        count=0
        try:
            payload,digest=request_json(f'https://api.massive.com/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}?adjusted=true&sort=asc&limit=50000',{'Authorization':'Bearer '+key})
            rows=normalize(payload,symbol,start,end)
            if symbol=='SPY':
                reference={r['trade_date'] for r in rows}
                if (now.date()-datetime.fromisoformat(max(reference)).date()).days>5:raise ValueError('STALE_PROVIDER_HISTORY')
            elif reference is None:raise ValueError('BENCHMARK_UNAVAILABLE')
            else:validate_calendar(rows,reference)
            old=db(f'v_stock_daily_latest?symbol=eq.{symbol}&trade_date=gte.{start}&select=trade_date,close,volume,open,high,low&limit=1000')
            previous={r['trade_date']:tuple(float(r[k]) for k in FIELDS) for r in old}
            changed=[{**r,'run_id':run_id,'response_sha256':digest} for r in rows if previous.get(r['trade_date'])!=tuple(r[k] for k in FIELDS)]
            for offset in range(0,len(changed),300):db('stock_daily_observations','POST',changed[offset:offset+300])
            count=len(changed);meta.update({'sessions':len(rows),'response_sha256':digest,'request_id':payload.get('request_id')})
            db('stock_tracker_runs?run_id=eq.'+run_id,'PATCH',{'status':'COMPLETE','completed_at':datetime.now(timezone.utc).isoformat(),'latest_session':rows[-1]['trade_date'],'observation_count':count,'metadata_json':meta})
            db('stock_tracker_symbols?symbol=eq.'+symbol,'PATCH',{'last_success_at':datetime.now(timezone.utc).isoformat(),'last_error':None})
            print(f'{symbol}: COMPLETE, {len(rows)} sessions, {count} new observations',flush=True)
        except Exception as error:
            failures+=1;code=str(error) if isinstance(error,(RuntimeError,ValueError)) else type(error).__name__
            meta['error_code']=code
            db('stock_tracker_runs?run_id=eq.'+run_id,'PATCH',{'status':'FAILED','completed_at':datetime.now(timezone.utc).isoformat(),'observation_count':count,'metadata_json':meta})
            db('stock_tracker_symbols?symbol=eq.'+symbol,'PATCH',{'last_error':code})
            print(f'{symbol}: FAILED ({code})',flush=True)
            if symbol=='SPY':break
    if failures:raise RuntimeError('ONE_OR_MORE_SYMBOLS_FAILED')
if __name__=='__main__':
    try:main()
    except Exception as error:
        print('STOCK_COLLECTION_FAILED: '+(str(error) if isinstance(error,(RuntimeError,ValueError)) else type(error).__name__),file=sys.stderr);sys.exit(1)
