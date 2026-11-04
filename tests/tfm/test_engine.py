import copy
import sys
import unittest
from datetime import date,datetime,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/tfm'))
from engine import evaluate,ET,session,target_for,close_at,valid_bar,digest,RULES
from scan import reconcile,scan


def bar(symbol,day,o=100,h=110,l=90,c=100):
    return {'symbol':symbol,'trade_date':day,'open':o,'high':h,'low':l,'close':c,'run_id':'fixture','response_sha256':'a'*64,'collected_at':'2026-10-30T22:00:00Z','source_view':'fixture'}


def sample():
    return [bar('XLK','2026-10-29',h=112),bar('XLK','2026-10-30',h=110,l=95),bar('XLK','2026-11-02',o=96,h=102,l=94,c=98)]

NOW=datetime(2026,11,3,12,tzinfo=ET)

class EngineTests(unittest.TestCase):
    def test_price_hash_survives_equivalent_json_numeric_types(self):
        self.assertEqual(digest({"prices":[100.0,100.25]}),digest({"prices":[100,100.25]}))

    def test_strict_hit_and_excursions(self):
        s,r,_=evaluate(sample(),NOW)
        self.assertTrue(s[0]['qualifies']);self.assertTrue(r[0]['hit'])
        self.assertAlmostEqual(r[0]['mfe_pct'],100*2/96)
        self.assertAlmostEqual(r[0]['mae_pct'],100*6/96)
        self.assertFalse(r[0]['gap_through'])
    def test_equal_high_not_qualifying_equal_low_not_hit(self):
        rows=sample();rows[0]['high']=110;rows[2]['low']=95
        s,r,_=evaluate(rows,NOW)
        self.assertFalse(s[0]['qualifies']);self.assertFalse(r[0]['hit'])
    def test_gap_hit_does_not_imply_intraday_profit(self):
        rows=sample();rows[2].update(open=94,low=94,high=102)
        _,r,_=evaluate(rows,NOW)
        self.assertTrue(r[0]['hit']);self.assertTrue(r[0]['gap_through']);self.assertEqual(r[0]['mfe_pct'],0)
    def test_holiday_tuesday_separate(self):
        self.assertEqual(target_for(date(2026,9,4)),(date(2026,9,8),'TUESDAY_HOLIDAY'))
        self.assertEqual(target_for(date(2026,10,30)),(date(2026,11,2),'MONDAY'))
    def test_missing_monday_is_not_a_holiday(self):
        rows=sample()[:2]+[bar('XLK','2026-11-03',l=80)]
        s,r,c=evaluate(rows,NOW)
        self.assertEqual(s[0]['target_date'],'2026-11-02');self.assertFalse(r)
        self.assertEqual(c['missing_matured_outcomes'],1)
    def test_missing_thursday_no_setup(self):
        self.assertEqual(evaluate(sample()[1:],NOW)[0],[])
    def test_no_future_outcome_or_signal(self):
        s,r,_=evaluate(sample(),datetime(2026,10,30,17,tzinfo=ET))
        self.assertEqual(s[0]['origin'],'PROSPECTIVE');self.assertFalse(r)
        self.assertFalse(evaluate(sample(),datetime(2026,10,30,15,tzinfo=ET))[0])
    def test_target_session_must_complete(self):
        s,r,_=evaluate(sample(),datetime(2026,11,2,12,tzinfo=ET))
        self.assertEqual(s[0]['origin'],'HISTORICAL');self.assertFalse(r)
    def test_holiday_and_calendar_boundaries(self):
        self.assertTrue(session(date(2021,12,31)))
        self.assertFalse(session(date(2025,1,9)))
        self.assertFalse(session(date(2026,6,19)))
        self.assertTrue(session(date(2021,6,18)))
        self.assertEqual(close_at(date(2026,11,27)).hour,13)
        with self.assertRaises(ValueError):session(date(2028,1,3))
    def test_invalid_or_duplicate_bars(self):
        self.assertFalse(valid_bar({'open':float('nan'),'high':110,'low':90,'close':100}))
        self.assertFalse(valid_bar({'open':100,'high':99,'low':90,'close':100}))
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):evaluate(sample()+sample()[:1],NOW)
    def test_no_target_day_regime_leak(self):
        rows=sample();d=date(2026,10,30)
        for _ in range(40):
            if session(d):rows.append(bar('SPY',d.isoformat(),o=100,h=110,l=90,c=100))
            d-=timedelta(days=1)
        s,_,_=evaluate(rows,NOW);rows.append(bar('SPY','2026-11-02',o=100,h=1100,l=1,c=1000))
        s2,_,_=evaluate(rows,NOW)
        self.assertEqual(s[-1]['market_condition'],s2[-1]['market_condition'])
    def test_idempotence_and_correction_gate(self):
        s,r,_=evaluate(sample(),NOW)
        self.assertEqual(reconcile(s,r,s,r),([],[],{'reference_corrections':0,'outcome_corrections':0}))
        changed=copy.deepcopy(s);changed[0]['setup_sha256']='b'*64
        new,results,diag=reconcile(changed,r,s,[])
        self.assertFalse(new);self.assertFalse(results);self.assertEqual(diag['reference_corrections'],1)
    def test_universe_does_not_include_unrequested_or_leveraged(self):
        from engine import SYMBOLS
        self.assertEqual(len(SYMBOLS),len(set(SYMBOLS)));self.assertIn('IGV',SYMBOLS);self.assertIn('VRT',SYMBOLS);self.assertNotIn('TQQQ',SYMBOLS);self.assertNotIn('SPY',SYMBOLS)

class ScannerIntegrationTests(unittest.TestCase):
    def test_atomic_publication_and_no_provider_calls(self):
        calls=[]
        def db(path,method='GET',data=None):
            calls.append((path,method,data))
            if path.startswith('work_envelopes?'):return [{'work_envelope_id':'19dd7129-0d19-4c1b-a65b-03480a925b8d','authority_ceiling':'E1','cost_policy_code':'ZERO_INCREMENTAL_COST_FIRST'}]
            if path.startswith('tfm_rules?'):return [{'rules_sha256':digest(RULES)}]
            if path.startswith('v_sector_daily_latest?'):return sample()
            if method=='GET':return []
            return None
        result=scan(db,'a'*40,now=NOW)
        publish=[c for c in calls if c[0]=='rpc/tfm_publish_scan']
        self.assertEqual(len(publish),1)
        self.assertEqual(len(publish[0][2]['p_setups']),1)
        self.assertEqual(len(publish[0][2]['p_outcomes']),1)
        self.assertEqual(result['diagnostics']['market_provider_calls'],0)
        self.assertFalse(any(c[0].startswith('tfm_setups') and c[1]=='POST' for c in calls))
    def test_contract_mismatch_blocks_execution(self):
        def db(path,method='GET',data=None):
            if path.startswith('work_envelopes?'):return [{'work_envelope_id':'19dd7129-0d19-4c1b-a65b-03480a925b8d','authority_ceiling':'E1','cost_policy_code':'ZERO_INCREMENTAL_COST_FIRST'}]
            return [{'rules_sha256':'wrong'}]
        with self.assertRaisesRegex(ValueError,'RULE_FREEZE'):scan(db,'a'*40,now=NOW)

if __name__=='__main__':unittest.main()
