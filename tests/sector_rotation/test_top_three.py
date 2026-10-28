import sys
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, 'scripts/sector_rotation')
import top_three
import forecast


class TopThreeTests(unittest.TestCase):
    def history(self):
        bars=[]
        for date in ['2026-10-26','2026-10-27','2026-10-28']:
            for i,s in enumerate(('SPY',)+forecast.SECTORS):
                # All returns negative on target: Top3 still populated. Exact ties deterministic.
                close=100 if date=='2026-10-26' else 99-i/10 if date=='2026-10-27' else 500+i
                bars.append({'symbol':s,'trade_date':date,'close':close})
        return forecast.series(bars)
    def test_exact_date_after_close_complete_ranks_and_negative_top3(self):
        h=self.history();et=ZoneInfo('America/New_York');now=datetime(2026,10,27,16,tzinfo=et)
        self.assertIsNone(top_three.outcome('2026-10-27',h,now.replace(hour=15,minute=59)))
        result=top_three.outcome('2026-10-27',h,now)
        self.assertEqual(len(result['ranks']),11)
        self.assertEqual([r['rank'] for r in result['ranks']],list(range(1,12)))
        self.assertEqual(sum(r['bucket']=='Top 3' for r in result['ranks']),3)
        self.assertEqual(sum(r['bucket']=='Bottom 3' for r in result['ranks']),3)
        self.assertTrue(all(r['daily']<0 for r in result['ranks']))
        self.assertEqual(result,top_three.outcome('2026-10-27',h[:-1],now))
        h[1]['complete']=False
        self.assertIsNone(top_three.outcome('2026-10-27',h,now.replace(day=29)))
        self.assertIsNone(top_three.outcome('2026-10-29',h,now.replace(day=30)))
    def test_exact_ties_use_ticker_and_retry_never_overwrites(self):
        h=self.history();now=datetime(2026,10,29,2,tzinfo=ZoneInfo('America/New_York'))
        for c in h[1]['cells'].values():c['daily']=0
        result=top_three.outcome('2026-10-27',h,now)
        self.assertEqual([r['symbol'] for r in result['ranks']],sorted(forecast.SECTORS))
        inserted=[];plans=[{'target_date':'2026-10-27'}]*9
        self.assertEqual(top_three.append_results(plans,set(),h,now,inserted.append),1)
        self.assertEqual(top_three.append_results(plans,{'2026-10-27'},h,now,inserted.append),0)
        self.assertEqual(len(inserted),1)
    def test_main_requires_verified_run_and_idempotent_rest_flow(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        inserted=[]
        def request(url,headers,method='GET',data=None):
            path=url.split('/rest/v1/')[1]
            if method=='POST':inserted.append(data);return ([],{})
            if path.startswith('sector_tracker_runs?'):return ([{'status':'COMPLETE','latest_session':'2026-10-27'}],{})
            if path.startswith('sector_top3_predictions?'):return ([{'target_date':'2026-10-27'}]*3,{})
            if path.startswith('sector_top3_results?'):return ([{'target_date':r['target_date']} for r in inserted],{})
            if path.startswith('v_sector_daily_latest?'):return ([],{})
            raise AssertionError(path)
        now=datetime(2026,10,28,2,tzinfo=ZoneInfo('America/New_York'))
        with patch.dict('os.environ',{'SUPABASE_URL':'https://fixture.invalid','SUPABASE_SECRET_KEY':'fixture'}),patch.dict(sys.modules,{'collect':SimpleNamespace(request_json=request)}),patch.object(top_three,'datetime') as clock,patch.object(top_three,'series',return_value=self.history()) as series:
            clock.now.return_value=now;clock.combine=datetime.combine;clock.fromisoformat=datetime.fromisoformat
            top_three.main();top_three.main()
            self.assertEqual(len(inserted),1);self.assertEqual(series.call_count,1)
