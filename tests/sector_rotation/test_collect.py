import importlib.util
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

spec=importlib.util.spec_from_file_location('collector','scripts/sector_rotation/collect.py')
collector=importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

class ProviderContract(unittest.TestCase):
    def payload(self):
        start=datetime(2025,1,1,tzinfo=ZoneInfo('America/New_York'))
        return {'ticker':'XLK','adjusted':True,'status':'OK','results':[{'t':int((start+timedelta(days=i)).timestamp()*1000),'c':100+i,'o':99+i,'h':101+i,'l':98+i,'v':1000} for i in range(30)]}
    def test_timestamp_is_exchange_date(self):
        rows=collector.normalize(self.payload(),'XLK','2025-01-01','2025-01-30')
        self.assertEqual(rows[0]['trade_date'],'2025-01-01')
        self.assertEqual(len(rows),30)
    def test_invalid_adjustment_rejected(self):
        p=self.payload();p['adjusted']=False
        with self.assertRaises(ValueError): collector.normalize(p,'XLK','2025-01-01','2025-01-30')
    def test_duplicate_bar_rejected(self):
        p=self.payload();p['results'].append(p['results'][0])
        with self.assertRaises(ValueError): collector.normalize(p,'XLK','2025-01-01','2025-01-30')
    def test_partial_page_rejected(self):
        p=self.payload();p['next_url']='https://example.invalid/page2'
        with self.assertRaises(ValueError): collector.normalize(p,'XLK','2025-01-01','2025-01-30')
    def test_nonfinite_and_zero_rejected(self):
        for bad in (0,-1,float('nan'),float('inf')):
            p=self.payload();p['results'][0]['c']=bad
            with self.assertRaises(ValueError): collector.normalize(p,'XLK','2025-01-01','2025-01-30')
    def test_wrong_symbol_rejected(self):
        with self.assertRaises(ValueError): collector.normalize(self.payload(),'SPY','2025-01-01','2025-01-30')
    def test_ohlc_rejects_impossible_and_missing_prices(self):
        for field,value in [('o',0),('h',90),('l',110),('h',float('inf')),('l',None)]:
            p=self.payload();p['results'][0][field]=value
            with self.assertRaises(ValueError):collector.normalize(p,'XLK','2025-01-01','2025-01-30')
        p=self.payload();del p['results'][0]['o']
        with self.assertRaises(ValueError):collector.normalize(p,'XLK','2025-01-01','2025-01-30')
        row=collector.normalize(self.payload(),'XLK','2025-01-01','2025-01-30')[0]
        self.assertEqual((row['open'],row['high'],row['low'],row['close']),(99,101,98,100))
