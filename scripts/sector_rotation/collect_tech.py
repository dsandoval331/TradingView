"""Bounded, append-only sector price collector. No research dataset reads/writes.

Secrets remain in environment/headers. Errors never include URLs, bodies, or keys.
Re-fetch the available two-year window to detect split restatements/corrections;
only changed observations are archived, with response hashes and run provenance.
"""
import hashlib
import json
import math
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SYMBOLS = ('SPY', 'AAPL', 'AMD', 'AMZN', 'ANET', 'AVGO', 'CSCO', 'DELL', 'GOOGL', 'HPE', 'HPQ', 'IGV', 'META', 'MRVL', 'MSFT', 'MU', 'NVDA', 'ORCL', 'PLTR', 'STX', 'TSM', 'VRT', 'WDC')
MWE_ID = 'MWE-SECTOR-TECH-001'
ET = ZoneInfo('America/New_York')


def request_json(url, headers, method='GET', data=None):
    body = None if data is None else json.dumps(data, allow_nan=False).encode()
    request = Request(url, data=body, headers={**headers, 'Content-Type':'application/json'}, method=method)
    for attempt in range(3):
        try:
            with urlopen(request, timeout=60) as response:
                raw = response.read()
            return json.loads(raw) if raw else None, hashlib.sha256(raw).hexdigest()
        except HTTPError as error:
            if error.code in (429,500,502,503,504) and attempt < 2:
                time.sleep(30 * (attempt + 1))
                continue
            raise RuntimeError(f'HTTP_{error.code}') from None
        except (URLError, TimeoutError):
            if attempt < 2:
                time.sleep(15)
                continue
            raise RuntimeError('NETWORK_ERROR') from None
    raise RuntimeError('RETRIES_EXHAUSTED')


def normalize(payload, symbol, start, end):
    if payload.get('ticker') != symbol or payload.get('adjusted') is not True:
        raise ValueError('SYMBOL_OR_ADJUSTMENT_MISMATCH')
    if payload.get('status') not in ('OK','DELAYED') or payload.get('next_url'):
        raise ValueError('INCOMPLETE_PROVIDER_RESPONSE')
    result = []
    seen = set()
    for bar in payload.get('results', []):
        day = datetime.fromtimestamp(bar['t']/1000, ET).date().isoformat()
        close, volume = float(bar['c']), float(bar['v'])
        if not start <= day <= end or day in seen or not math.isfinite(close) or close <= 0 or not math.isfinite(volume) or volume < 0:
            raise ValueError('INVALID_BAR')
        seen.add(day)
        result.append({'symbol':symbol,'trade_date':day,'close':close,'volume':volume})
    if len(result) < 25:
        raise ValueError('INSUFFICIENT_HISTORY')
    return sorted(result, key=lambda row: row['trade_date'])


def main():
    base = os.environ['SUPABASE_URL'].rstrip('/') + '/rest/v1/'
    secret = os.environ['SUPABASE_SECRET_KEY']
    key = os.environ.get('MASSIVE_API_KEY') or os.environ.get('TR_MASSIVE_API_KEY')
    if not key:
        raise RuntimeError('MASSIVE_API_KEY_NOT_CONFIGURED')
    sha = os.environ['GITHUB_SHA']
    if len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('INVALID_GIT_SHA')
    headers = {'apikey':secret,'Authorization':'Bearer '+secret}
    def db(path, method='GET', data=None):
        return request_json(base+path, headers, method, data)[0]
    envelope = db('work_envelopes?mwe_id=eq.'+MWE_ID+'&select=work_envelope_id,authority_ceiling,cost_policy_code')
    if len(envelope) != 1 or envelope[0]['authority_ceiling'] != 'E1' or envelope[0]['cost_policy_code'] != 'ZERO_INCREMENTAL_COST_FIRST':
        raise RuntimeError('ENVELOPE_AUTHORITY_INVALID')
    now = datetime.now(ET)
    # Basic plan exposes completed days only after midnight Eastern.
    end = (now.date()-timedelta(days=1)).isoformat()
    start = (now.date()-timedelta(days=729)).isoformat()
    run_id = str(uuid.uuid4())
    db('tech_tracker_runs','POST',{'run_id':run_id,'work_envelope_id':envelope[0]['work_envelope_id'],'status':'RUNNING','git_sha':sha,'external_run_id':os.environ['GITHUB_RUN_ID'],'requested_start':start,'requested_end':end})
    meta = {'symbol_responses':{},'cost_policy':'ZERO_INCREMENTAL_COST_FIRST','billing_verified':False,'mwe_id':MWE_ID}
    count = 0
    try:
        collected = {}
        # 15 seconds between provider requests = at most four/minute locally.
        # Shared-account 429s receive bounded backoff.
        for index, symbol in enumerate(SYMBOLS):
            if index:
                time.sleep(15)
            url = f'https://api.massive.com/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}?adjusted=true&sort=asc&limit=50000'
            payload, digest = request_json(url, {'Authorization':'Bearer '+key})
            rows = normalize(payload, symbol, start, end)
            collected[symbol] = rows
            old = {}
            offset = 0
            while True:
                page = db(f'v_tech_daily_latest?symbol=eq.{symbol}&trade_date=gte.{start}&select=trade_date,close,volume&order=trade_date&limit=1000&offset={offset}')
                old.update({r['trade_date']:(float(r['close']),float(r['volume'])) for r in page})
                if len(page) < 1000:
                    break
                offset += 1000
            changed = [{**r,'run_id':run_id,'response_sha256':digest} for r in rows if old.get(r['trade_date']) != (r['close'],r['volume'])]
            for offset in range(0,len(changed),300):
                db('tech_daily_observations','POST',changed[offset:offset+300])
            count += len(changed)
            meta['symbol_responses'][symbol] = {'sha256':digest,'rows':len(rows),'changed':len(changed),'first':rows[0]['trade_date'],'last':rows[-1]['trade_date'],'request_id':payload.get('request_id')}
            print(f'{symbol}: validated {len(rows)} bars; archived {len(changed)} changes', flush=True)
        reference = {r['trade_date'] for r in collected['SPY']}
        # Every tracked symbol must align with SPY's returned session calendar.
        if any({r['trade_date'] for r in collected[s]} != reference for s in SYMBOLS):
            raise ValueError('SECTOR_CALENDAR_MISMATCH')
        latest = max(reference)
        # Catch an account/provider returning an old window, without inventing sessions.
        if (now.date()-datetime.fromisoformat(latest).date()).days > 5:
            raise ValueError('STALE_PROVIDER_HISTORY')
        meta['sessions'] = len(reference)
        meta['price_basis'] = 'split_adjusted_not_dividend_adjusted'
        db('tech_tracker_runs?run_id=eq.'+run_id,'PATCH',{'status':'COMPLETE','completed_at':datetime.now(timezone.utc).isoformat(),'latest_session':latest,'observation_count':count,'metadata_json':meta})
        readback = db('tech_tracker_runs?run_id=eq.'+run_id+'&select=status,latest_session,observation_count')
        if readback != [{'status':'COMPLETE','latest_session':latest,'observation_count':count}]:
            raise RuntimeError('RUN_READBACK_MISMATCH')
        print(json.dumps({'run_id':run_id,'latest_session':latest,'new_observations':count,'status':'COMPLETE'}))
    except Exception as error:
        meta['error_code'] = str(error) if isinstance(error,(RuntimeError,ValueError)) else type(error).__name__
        db('tech_tracker_runs?run_id=eq.'+run_id,'PATCH',{'status':'FAILED','completed_at':datetime.now(timezone.utc).isoformat(),'observation_count':count,'metadata_json':meta})
        raise RuntimeError(meta['error_code']) from None


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('SECTOR_COLLECTION_FAILED: '+(str(error) if isinstance(error,(RuntimeError,ValueError)) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
