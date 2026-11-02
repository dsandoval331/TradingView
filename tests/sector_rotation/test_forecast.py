import importlib.util
import sys
import unittest
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0,'scripts/sector_rotation')
import forecast

class ForecastTests(unittest.TestCase):
    def bars(self):
        dates=[];day=datetime(2026,1,1)
        while len(dates)<210:
            if day.weekday()<5:dates.append(day.date().isoformat())
            day+=timedelta(days=1)
        rows=[]
        for i,date in enumerate(dates):
            for j,symbol in enumerate(('SPY',)+forecast.SECTORS):
                close=100 if symbol=='SPY' else 100+(i*(j+1)/20)
                rows.append({'symbol':symbol,'trade_date':date,'close':close,'open':close-.2,'high':close+1,'low':close-1,'volume':100+i if symbol=='XLY' else 100})
        return rows
    def test_prefix_invariance_and_support(self):
        bars=self.bars();h=forecast.series(bars);a=forecast.choose_forecast(h[:-1]);b=forecast.choose_forecast(forecast.series([r for r in bars if r['trade_date']<=h[-2]['date']]))
        self.assertEqual(a,b);self.assertIsNotNone(a['symbol']);self.assertGreaterEqual(a['pattern']['observations'],20);self.assertGreaterEqual(a['pattern']['dates'],5);self.assertEqual(a['training_last'],h[-2]['date'])
        self.assertEqual(forecast.choose_forecast(h[:20])['symbol'],None)
        with self.assertRaises(ValueError):forecast.series(bars+[bars[0]])
    def test_window(self):
        et=ZoneInfo('America/New_York')
        self.assertTrue(forecast.eligible_creation('2026-10-26',datetime(2026,10,27,2,tzinfo=et)))
        self.assertTrue(forecast.eligible_creation('2026-10-26',datetime(2026,10,27,9,24,59,tzinfo=et)))
        self.assertFalse(forecast.eligible_creation('2026-10-26',datetime(2026,10,27,9,25,tzinfo=et)))
        self.assertFalse(forecast.eligible_creation('2026-10-26',datetime(2026,10,26,2,tzinfo=et)))
        self.assertFalse(forecast.eligible_creation('2026-10-20',datetime(2026,10,27,2,tzinfo=et)))
    def test_outcome_uses_first_next_session_and_preopen_record(self):
        h=forecast.series(self.bars());source=h[-2]['date'];target=h[-1]['date']
        f={'source_date':source,'recorded_at':source+'T23:00:00+00:00','payload':{'symbol':'XLY'}}
        self.assertIsNone(forecast.settle(f,h[:-1]));result=forecast.settle(f,h);self.assertEqual(result['target_date'],target);self.assertGreater(result['payload']['mfe_pct'],0)
        f['recorded_at']=target+'T20:00:00+00:00';self.assertIsNone(forecast.settle(f,h))
        f['recorded_at']=source+'T23:00:00+00:00';h[-1]['complete']=False;self.assertIsNone(forecast.settle(f,h))
    def test_result_waits_for_complete_ohlc_and_retries_same_session(self):
        import copy
        h=forecast.series(self.bars());source=h[-2]['date'];target=h[-1]['date']
        f={'source_date':source,'recorded_at':source+'T23:00:00+00:00','payload':{'symbol':'XLY'}}
        expected=forecast.settle(f,h)
        for field,value in [('open',None),('high',None),('low',None),('open',0),('high',1),('low',99999)]:
            incomplete=copy.deepcopy(h);incomplete[-1]['cells']['XLY']['bar'][field]=value
            self.assertIsNone(forecast.settle(f,incomplete),(field,value))
        actual=forecast.settle(f,h)
        self.assertEqual(actual,expected);self.assertEqual(actual['target_date'],target)
        self.assertTrue(all(actual['payload'][key] is not None for key in ('rank','daily','relative','open','close','open_close_pct','mfe_pct','mae_pct')))
        no_pick={**f,'payload':{'symbol':None}}
        self.assertTrue(forecast.settle(no_pick,h)['payload']['no_pick'])
    def test_features_missing_and_lagged(self):
        h=forecast.series(self.bars());c=h[-1]['cells']['XLY'];self.assertTrue(c['features'][0]);self.assertTrue(c['features'][3]);self.assertTrue(c['features'][5]);self.assertEqual(c['daily_streak'],209)
        bars=self.bars();last=h[-1]['date']
        for b in bars:
            if b['symbol']=='XLY' and b['trade_date']==last:b['volume']=None
        self.assertIsNone(forecast.series(bars)[-1]['cells']['XLY']['features'][0])

if __name__=='__main__':unittest.main()

class ForecastJobTests(unittest.TestCase):
    bars=ForecastTests.bars
    def test_job_records_once_then_appends_results_without_rewriting_pick(self):
        import contextlib,io,json,copy,os
        from unittest.mock import patch
        import collect
        bars=self.bars();source=max(b['trade_date'] for b in bars);clock=[datetime.fromisoformat(source).replace(tzinfo=forecast.ET)+timedelta(days=1,hours=2)]
        backend={'sector_winner_forecasts':[],'sector_winner_forecast_results':[]}
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return clock[0].astimezone(tz)
        def request(url,headers,method='GET',data=None):
            table=url.split('/rest/v1/')[1].split('?')[0]
            if table=='sector_tracker_runs':answer=[{'status':'COMPLETE','latest_session':max(b['trade_date'] for b in bars)}]
            elif table=='v_sector_daily_latest':
                from urllib.parse import parse_qs,urlsplit
                q=parse_qs(urlsplit(url).query);offset=int(q['offset'][0]);answer=bars[offset:offset+1000]
            elif method=='POST':
                if table=='sector_winner_forecasts':self.assertFalse(any(f['id']==data['id'] for f in backend[table]))
                backend[table].append({**copy.deepcopy(data),'recorded_at':clock[0].isoformat()});answer=None
            else:answer=copy.deepcopy(backend[table])
            return answer,'fixture-hash'
        with patch.dict(os.environ,{'SUPABASE_URL':'https://synthetic.invalid','SUPABASE_SECRET_KEY':'synthetic','GITHUB_SHA':'0'*40}),patch.object(collect,'request_json',request),patch.object(forecast,'datetime',Clock),contextlib.redirect_stdout(io.StringIO()):
            forecast.main();self.assertEqual(len(backend['sector_winner_forecasts']),1);original=copy.deepcopy(backend['sector_winner_forecasts'][0]);forecast.main();self.assertEqual(len(backend['sector_winner_forecasts']),1)
            target=clock[0].date().isoformat()
            last=[b for b in bars if b['trade_date']==source]
            bars.extend([{**b,'trade_date':target,'close':float(b['close'])+1,'open':float(b['close']),'high':float(b['close'])+2,'low':float(b['close'])-1} for b in last]);clock[0]+=timedelta(days=1)
            forecast.main();self.assertEqual(len(backend['sector_winner_forecast_results']),1);self.assertEqual(backend['sector_winner_forecasts'][0],original);forecast.main();self.assertEqual(len(backend['sector_winner_forecast_results']),1)
    def test_missing_next_benchmark_does_not_skip_to_later_result(self):
        bars=self.bars();history=forecast.series(bars);source=history[-3]['date'];target=history[-2]['date'];bars=[b for b in bars if not (b['symbol']=='SPY' and b['trade_date']==target)]
        f={'source_date':source,'recorded_at':source+'T23:00:00+00:00','payload':{'symbol':'XLY'}}
        self.assertIsNone(forecast.settle(f,forecast.series(bars)))
