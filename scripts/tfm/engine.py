"""TFM bearish v1. Pure deterministic analysis; never imports protected research data."""
from datetime import date, datetime, timedelta, time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
import hashlib
import json
from pathlib import Path

ET = ZoneInfo('America/New_York')
RULES = json.loads(Path(__file__).with_name('rules.json').read_text())
VERSION = RULES['version']
SECTORS = tuple(RULES['universe']['sector_etfs'])
STOCKS = tuple(RULES['universe']['stocks'])
SYMBOLS = SECTORS + STOCKS


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def nth_weekday(year, month, weekday, n):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday-first.weekday()) % 7 + 7*(n-1))


def easter(year):
    a=year%19; b=year//100; c=year%100; d=b//4; e=b%4; f=(b+8)//25
    g=(b-f+1)//3; h=(19*a+b-d-g+15)%30; i=c//4; k=c%4
    l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    return date(year,(h+l-7*m+114)//31,(h+l-7*m+114)%31+1)


def observed(day):
    return day + timedelta(days=-1 if day.weekday()==5 else 1 if day.weekday()==6 else 0)


def holidays(year):
    if not 2021 <= year <= 2027:
        raise ValueError('CALENDAR_OUT_OF_BOUNDS')
    memorial = date(year,5,31)
    memorial -= timedelta(days=memorial.weekday())
    result = {nth_weekday(year,1,0,3),nth_weekday(year,2,0,3),easter(year)-timedelta(days=2),
              memorial, observed(date(year,7,4)),nth_weekday(year,9,0,1),
              nth_weekday(year,11,3,4),observed(date(year,12,25))}
    # NYSE does not observe a Saturday New Year's Day on the preceding Friday.
    newyear=date(year,1,1)
    if newyear.weekday()!=5: result.add(observed(newyear))
    if year>=2022: result.add(observed(date(year,6,19)))
    if year==2025: result.add(date(2025,1,9))
    return result


def session(day):
    return day.weekday()<5 and day not in holidays(day.year)


def close_at(day):
    early = day == nth_weekday(day.year,11,3,4)+timedelta(days=1)
    early |= day.month==12 and day.day==24
    early |= day.month==7 and day.day==3
    return datetime.combine(day,time(13 if early else 16),ET)


def open_at(day):
    return datetime.combine(day,time(9,30),ET)


def target_for(friday):
    monday=friday+timedelta(days=3)
    if session(monday):return monday,'MONDAY'
    tuesday=monday+timedelta(days=1)
    if monday in holidays(monday.year) and session(tuesday):return tuesday,'TUESDAY_HOLIDAY'
    raise ValueError('UNSUPPORTED_TARGET_CALENDAR')


def valid_bar(row):
    try:
        values={k:Decimal(str(row[k])) for k in ('open','high','low','close')}
        if any(not v.is_finite() or v<=0 for v in values.values()):return False
        return values['low']<=min(values['open'],values['close'])<=max(values['open'],values['close'])<=values['high']
    except (KeyError,InvalidOperation,TypeError,ValueError):return False


def index_bars(rows, now):
    result={};bad=0
    for row in rows:
        day=date.fromisoformat(row['trade_date'])
        key=(row['symbol'],day)
        if key in result:raise ValueError('DUPLICATE_SYMBOL_DATE')
        if not session(day):raise ValueError('BAR_ON_CLOSED_SESSION')
        if close_at(day)>now:continue
        if not valid_bar(row):bad+=1;continue
        result[key]=row
    return result,bad


def regime(index, friday):
    days=[];day=friday
    while len(days)<20:
        if session(day):days.append(day)
        day-=timedelta(days=1)
    # Seed EMA at first available valid bar; require no gaps in last 20 sessions.
    if any(('SPY',d) not in index for d in days):return 'UNKNOWN'
    series=sorted((d,r) for (s,d),r in index.items() if s=='SPY' and d<=friday)
    ema=Decimal(str(series[0][1]['close']));alpha=Decimal(2)/Decimal(21)
    for _,row in series[1:]:ema=alpha*Decimal(str(row['close']))+(1-alpha)*ema
    return 'SPY_ABOVE_EMA20' if Decimal(str(index['SPY',friday]['close']))>=ema else 'SPY_BELOW_EMA20'


def observation(symbol, friday, target, cohort, thursday_bar, friday_bar, now, market):
    setup={
        'rule_version':VERSION,'symbol':symbol,'friday':friday.isoformat(),'target_date':target.isoformat(),
        'cohort':cohort,'asset_class':'SECTOR_ETF' if symbol in SECTORS else 'STOCK',
        'qualifies':Decimal(str(friday_bar['high']))<Decimal(str(thursday_bar['high'])),
        'market_condition':market,
        'thursday_high':float(thursday_bar['high']),'friday_high':float(friday_bar['high']),
        'friday_low':float(friday_bar['low']),'friday_close':float(friday_bar['close']),
        'reference_bars':[thursday_bar,friday_bar],
        'origin':'PROSPECTIVE' if now<open_at(target) else 'HISTORICAL',
    }
    setup['setup_key']=digest([VERSION,symbol,setup['friday']])
    setup['setup_sha256']=digest({k:v for k,v in setup.items() if k not in ('origin','setup_key')})
    return setup


def evaluate(rows, now, start=None):
    if now.tzinfo is None:raise ValueError('TIMEZONE_REQUIRED')
    start=start or date.fromisoformat(RULES['historical_start'])
    index,invalid=index_bars(rows,now)
    dates=[d for _,d in index]
    if not dates:raise ValueError('NO_COMPLETED_HISTORY')
    first=max(start,min(dates));last=min(now.astimezone(ET).date(),max(dates))
    # Includes the latest Friday even if target data is unavailable.
    day=first;setups=[];results=[];missing_setups=0;missing_outcomes=0
    while day<=last:
        if day.weekday()!=4 or not session(day) or not session(day-timedelta(days=1)) or close_at(day)>now:
            day+=timedelta(days=1);continue
        target,cohort=target_for(day);market=regime(index,day)
        for symbol in SYMBOLS:
            thursday=index.get((symbol,day-timedelta(days=1)));friday=index.get((symbol,day))
            if thursday is None or friday is None:
                missing_setups+=1;continue
            item=observation(symbol,day,target,cohort,thursday,friday,now,market);setups.append(item)
            bar=index.get((symbol,target))
            if close_at(target)>now:continue
            if bar is None:missing_outcomes+=1;continue
            opening=Decimal(str(bar['open']));high=Decimal(str(bar['high']));low=Decimal(str(bar['low']))
            ref=Decimal(str(friday['low']))
            result={'setup_key':item['setup_key'],'setup_sha256':item['setup_sha256'],
                    'hit':low<ref,'gap_through':opening<ref,
                    'mfe_pct':float(max(Decimal(0),(opening-low)/opening*100)),
                    'mae_pct':float(max(Decimal(0),(high-opening)/opening*100)),
                    'close_return_pct':float((Decimal(str(bar['close']))/opening-1)*100),
                    'target_bar':bar}
            result['result_sha256']=digest(result);results.append(result)
        day+=timedelta(days=1)
    per_symbol={s:{'bars':sum(1 for key in index if key[0]==s),
                   'first':min((d.isoformat() for sym,d in index if sym==s),default=None),
                   'last':max((d.isoformat() for sym,d in index if sym==s),default=None)} for s in SYMBOLS}
    coverage={'source_first':min(dates).isoformat(),'source_last':max(dates).isoformat(),
              'requested_start':start.isoformat(),'requested_end':now.astimezone(ET).date().isoformat(),
              'five_year_complete':False,'invalid_bars':invalid,'missing_setup_pairs':missing_setups,
              'missing_matured_outcomes':missing_outcomes,'symbols':per_symbol,
              'history_label':'PRELIMINARY — five-year coverage not certified'}
    return setups,results,coverage
