"""Append-only, pre-open sector forecast and later outcome recording. No new provider calls."""
import hashlib
import itertools
import json
import math
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ET=ZoneInfo('America/New_York')
SECTORS=('XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY')
VERSION='sector-next-v1'
LABELS=('Volume >60-session average','Positive daily return','Outperformance vs SPY','Close above EMA20','Close above EMA50','Positive daily streak ≥2')

def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):
        return None

def series(bars):
    by={}
    for b in bars:
        key=(b['symbol'],b['trade_date'])
        if key in by: raise ValueError('DUPLICATE_PRICE')
        by[key]=b
    dates=sorted({d for s,d in by if s=='SPY' or s in SECTORS})
    histories={s:[] for s in SECTORS}
    ema={s:{p:None for p in (20,50)} for s in SECTORS}
    closes={s:[] for s in SECTORS}
    volumes={s:[] for s in SECTORS}
    runs={s:0 for s in SECTORS}
    output=[]
    for i,date in enumerate(dates):
        def change(symbol):
            a=number(by.get((symbol,date),{}).get('close'))
            b=number(by.get((symbol,dates[i-1]),{}).get('close')) if i else None
            return (a/b-1)*100 if a is not None and b is not None and a>0 and b>0 else None
        spy=change('SPY'); cells={}
        for symbol in SECTORS:
            b=by.get((symbol,date),{}); close=number(b.get('close')); volume=number(b.get('volume')); daily=change(symbol)
            if close is None or close<=0:
                closes[symbol]=[];ema[symbol]={20:None,50:None}
            else:
                closes[symbol].append(close)
                for p in (20,50):
                    previous=ema[symbol][p]
                    ema[symbol][p]=(previous+2/(p+1)*(close-previous)) if previous is not None else sum(closes[symbol][-p:])/p if len(closes[symbol])>=p else None
            if volume is None or volume<0: volumes[symbol]=[]
            else: volumes[symbol]=(volumes[symbol]+[volume])[-60:]
            average=sum(volumes[symbol])/60 if len(volumes[symbol])==60 else None
            rvol=volume/average if volume is not None and average is not None and average>0 else None
            relative=daily-spy if daily is not None and spy is not None else None
            runs[symbol]=runs[symbol]+1 if daily is not None and daily>1e-10 else 0
            features=[None if rvol is None else rvol>1,None if daily is None else daily>0,None if relative is None else relative>0,*[None if ema[symbol][p] is None or close is None else close>ema[symbol][p] for p in (20,50)],None if daily is None else runs[symbol]>=2]
            cells[symbol]={'features':features,'close':close,'rvol':rvol,'daily':daily,'relative':relative,'ema20':ema[symbol][20],'ema50':ema[symbol][50],'daily_streak':runs[symbol],'bar':b}
        complete=spy is not None and all(c['daily'] is not None for c in cells.values())
        winner=min(SECTORS,key=lambda s:(-cells[s]['daily'],s)) if complete else None
        if winner is not None and cells[winner]['daily']<.05:winner=None
        output.append({'date':date,'complete':complete,'winner':winner,'cells':cells})
    return output

def eligible_creation(source,now):
    local=now.astimezone(ET); age=(local.date()-datetime.fromisoformat(source).date()).days
    return 1<=age<=4 and local.time()<time(8)

def choose_forecast(history):
    current=history[-1] if history else None
    if not current or not current['complete']:return None
    training=[]
    for i,day in enumerate(history):
        if i and day['complete']:
            training.append((day,history[i-1]))
    training=training[-120:]
    data=[(day['date'],symbol,prev['cells'][symbol]['features'],day['winner']==symbol) for day,prev in training for symbol in SECTORS]
    if len(training)<60:return {'symbol':None,'reason':'Insufficient history: need 60 complete labeled sessions.'}
    baseline=(sum(row[3] for row in data)+1)/(len(data)+2)
    candidates=[]
    for symbol in SECTORS:
        active=current['cells'][symbol]['features']; patterns=[]
        for size in (1,2,3):
            for keys in itertools.combinations(range(6),size):
                if not all(active[k] is True for k in keys):continue
                matched=[row for row in data if all(row[2][k] is True for k in keys)]
                wins=sum(row[3] for row in matched)
                if len(matched)<20 or len({row[0] for row in matched})<5 or wins<3:continue
                rate=(wins+1)/(len(matched)+2)
                if rate<=baseline:continue
                patterns.append({'keys':list(keys),'traits':[LABELS[k] for k in keys],'wins':wins,'observations':len(matched),'dates':len({row[0] for row in matched}),'score':rate,'baseline':baseline})
        if patterns:
            pattern=sorted(patterns,key=lambda p:(-p['score'],-p['observations'],len(p['keys']),p['keys']))[0]
            candidates.append({'symbol':symbol,'pattern':pattern,'features':{k:v for k,v in current['cells'][symbol].items() if k!='bar'}})
    if not candidates:return {'symbol':None,'reason':'No sector matched a pattern meeting the predeclared support and above-baseline requirements.','training_sessions':len(training)}
    candidates.sort(key=lambda c:(-c['pattern']['score'],-c['pattern']['observations'],len(c['pattern']['keys']),c['symbol']))
    pick=candidates[0]
    return {**pick,'side':'long','reason':' + '.join(pick['pattern']['traits']),'training_sessions':len(training),'training_first':training[0][0]['date'],'training_last':training[-1][0]['date'],'candidates':candidates,'rules':{'volume_sessions':60,'target_top_n':1,'lookback':120,'min_training_sessions':60,'min_pattern_observations':20,'min_pattern_dates':5,'min_pattern_wins':3}}

def settle(forecast,history):
    after=[d for d in history if d['date']>forecast['source_date']]
    if not after or not after[0]['complete']:return None
    day=after[0]
    recorded=datetime.fromisoformat(forecast['recorded_at'].replace('Z','+00:00'))
    opening=datetime.fromisoformat(day['date']).replace(hour=9,minute=30,tzinfo=ET)
    if recorded>=opening:return None
    symbol=forecast['payload'].get('symbol')
    if not symbol:return {'target_date':day['date'],'payload':{'no_pick':True,'winner':day['winner']}}
    cell=day['cells'][symbol];bar=cell['bar']; op=number(bar.get('open'));hi=number(bar.get('high'));lo=number(bar.get('low'));close=cell['close']
    op=op if op is not None and op>0 else None
    valid=op is not None and op>0 and hi is not None and lo is not None and lo>0 and hi>=max(op,close) and lo<=min(op,close)
    rank=1+sum(c['daily']>cell['daily']+1e-10 for c in day['cells'].values())
    return {'target_date':day['date'],'payload':{'symbol':symbol,'rank':rank,'winner':day['winner'],'top1_green':day['winner']==symbol,'daily':cell['daily'],'relative':cell['relative'],'open':op,'close':close,'open_close_pct':(close/op-1)*100 if op and op>0 else None,'mfe_pct':max(0,hi-op)/op*100 if valid else None,'mae_pct':max(0,op-lo)/op*100 if valid else None}}

def main():
    from collect import request_json
    base=os.environ['SUPABASE_URL'].rstrip('/')+'/rest/v1/';secret=os.environ['SUPABASE_SECRET_KEY'];headers={'apikey':secret,'Authorization':'Bearer '+secret}
    def db(path,method='GET',data=None):return request_json(base+path,headers,method,data)[0]
    def load(path):
        rows=[]
        for offset in range(0,100000,1000):
            page=db(path+f'&limit=1000&offset={offset}');rows.extend(page)
            if len(page)<1000:return rows
        raise RuntimeError('PRICE_HISTORY_LIMIT')
    runs=db('sector_tracker_runs?select=status,latest_session&order=started_at.desc&limit=1')
    if not runs or runs[0]['status']!='COMPLETE':raise RuntimeError('VERIFIED_COLLECTION_REQUIRED')
    bars=load('v_sector_daily_latest?select=symbol,trade_date,close,open,high,low,volume&order=trade_date,symbol')
    now=datetime.now(ET);bars=[b for b in bars if b['trade_date']<now.date().isoformat()];history=series(bars)
    forecasts=load('sector_winner_forecasts?select=id,source_date,recorded_at,payload&order=source_date')
    outcomes={row['forecast_id'] for row in load('sector_winner_forecast_results?select=forecast_id&order=forecast_id')}
    settled=0
    for forecast in forecasts:
        if forecast['id'] in outcomes:continue
        result=settle(forecast,history)
        if result:
            db('sector_winner_forecast_results','POST',{'forecast_id':forecast['id'],**result});settled+=1
    source=history[-1]['date'] if history else None
    created=False
    if source and source==runs[0]['latest_session'] and eligible_creation(source,now):
        identity=VERSION+':'+source
        if not any(f['id']==identity for f in forecasts):
            pick=choose_forecast(history)
            if pick is not None:
                payload={**pick,'source_sha256':hashlib.sha256(json.dumps(bars,sort_keys=True).encode()).hexdigest(),'git_sha':os.environ.get('GITHUB_SHA'),'source_session':source}
                db('sector_winner_forecasts','POST',{'id':identity,'version':VERSION,'source_date':source,'payload':payload});created=True
    print(json.dumps({'forecast_created':created,'results_appended':settled,'latest_source':source,'preopen_window':bool(source and eligible_creation(source,now))}))

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'FAILED','error_type':type(error).__name__}));raise SystemExit(1)
