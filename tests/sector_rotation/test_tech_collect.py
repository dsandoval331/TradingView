import importlib.util
import unittest
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
spec=importlib.util.spec_from_file_location('tech_collector','scripts/sector_rotation/collect_tech.py')
tech=importlib.util.module_from_spec(spec);spec.loader.exec_module(tech)
class TechProviderContract(unittest.TestCase):
    def test_new_universe_and_scope(self):
        self.assertEqual(len(tech.SYMBOLS),23)
        self.assertEqual(len(set(tech.SYMBOLS)),23)
        self.assertEqual(tech.MWE_ID,'MWE-SECTOR-TECH-001')
        self.assertIn('IGV',tech.SYMBOLS);self.assertIn('VRT',tech.SYMBOLS)
    def test_new_collector_exchange_dates_and_no_duplicate_acceptance(self):
        start=datetime(2025,1,1,tzinfo=ZoneInfo('America/New_York'))
        p={'ticker':'VRT','adjusted':True,'status':'OK','results':[{'t':int((start+timedelta(days=i)).timestamp()*1000),'c':100+i,'o':99+i,'h':101+i,'l':98+i,'v':1000} for i in range(30)]}
        self.assertEqual(tech.normalize(p,'VRT','2025-01-01','2025-01-30')[0]['trade_date'],'2025-01-01')
        p['results'].append(p['results'][0])
        with self.assertRaises(ValueError):tech.normalize(p,'VRT','2025-01-01','2025-01-30')
    def test_insufficient_or_unadjusted_history_is_not_published(self):
        for p in ({'ticker':'VRT','status':'OK','adjusted':False,'results':[]},{'ticker':'VRT','status':'OK','adjusted':True,'results':[]}):
            with self.assertRaises(ValueError):tech.normalize(p,'VRT','2025-01-01','2025-01-30')
