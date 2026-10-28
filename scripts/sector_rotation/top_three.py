"""Append verified closing outcomes for recorded Top 3 probabilities; no market-provider calls."""
import hashlib
import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo
from forecast import series, SECTORS
ET = ZoneInfo('America/New_York')


def outcome(target, history, now):
    """Require the exact target date and all eleven returns; never skip missing dates."""
    cutoff = datetime.combine(datetime.fromisoformat(target).date(), time(16), ET)
    if now.astimezone(ET) < cutoff:
        return None
    day = next((d for d in history if d['date'] == target), None)
    if not day or not day['complete']:
        return None
    ordered = sorted(SECTORS, key=lambda s: (-day['cells'][s]['daily'], s))
    return {'ranks': [{'symbol': symbol, 'rank': i+1, 'daily': day['cells'][symbol]['daily'],
                       'bucket': 'Top 3' if i < 3 else 'Bottom 3' if i >= 8 else 'Middle'}
                      for i, symbol in enumerate(ordered)],
            'ranking_rule': 'Close-to-close return descending; exact ties by ticker ascending. No green-only filter.',
            'price_sha256': hashlib.sha256(json.dumps([{'symbol': s, 'daily': day['cells'][s]['daily'],
                'close': day['cells'][s]['close']} for s in sorted(SECTORS)], sort_keys=True).encode()).hexdigest()}


def append_results(predictions, existing, history, now, insert):
    count = 0
    for target in sorted({p['target_date'] for p in predictions} - set(existing)):
        payload = outcome(target, history, now)
        if payload:
            insert({'target_date': target, 'payload': payload})
            count += 1
    return count


def main():
    from collect import request_json
    base = os.environ['SUPABASE_URL'].rstrip('/')+'/rest/v1/'
    secret = os.environ['SUPABASE_SECRET_KEY']
    headers = {'apikey': secret, 'Authorization': 'Bearer '+secret}
    def db(path, method='GET', data=None):
        return request_json(base+path, headers, method, data)[0]
    def load(path):
        rows = []
        for offset in range(0, 100000, 1000):
            page = db(path+f'&limit=1000&offset={offset}')
            rows.extend(page)
            if len(page) < 1000:
                return rows
        raise RuntimeError('PAGINATION_LIMIT')
    runs = db('sector_tracker_runs?select=status,latest_session&order=started_at.desc&limit=1')
    if not runs or runs[0]['status'] != 'COMPLETE':
        raise RuntimeError('VERIFIED_COLLECTION_REQUIRED')
    predictions = load('sector_top3_predictions?select=target_date&order=target_date,stage,symbol')
    existing = {r['target_date'] for r in load('sector_top3_results?select=target_date&order=target_date')}
    if not {p['target_date'] for p in predictions}-existing:
        print(json.dumps({'top3_results_appended': 0}))
        return
    now = datetime.now(ET)
    bars = load('v_sector_daily_latest?select=symbol,trade_date,close&order=trade_date,symbol')
    # Never settle a date beyond the collector's verified published boundary.
    history = series([b for b in bars if b['trade_date'] <= runs[0]['latest_session']])
    count = append_results(predictions, existing, history, now, lambda row: db('sector_top3_results', 'POST', row))
    print(json.dumps({'top3_results_appended': count}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'FAILED', 'error_type': type(error).__name__}))
        raise SystemExit(1)
