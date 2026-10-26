import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path('scripts/stock_tracker').resolve()))
import collect as stock
class StockContract(unittest.TestCase):
 def test_benchmark_alignment_allows_shorter_listed_history_but_not_stale_or_foreign_dates(self):
  stock.validate_calendar([{'trade_date':'2025-01-03'}],{'2025-01-02','2025-01-03'})
  for rows in [[],[{'trade_date':'2025-01-02'}],[{'trade_date':'2025-01-04'}]]:
   with self.assertRaises(ValueError):stock.validate_calendar(rows,{'2025-01-02','2025-01-03'})
 def test_stock_lane_is_isolated(self):self.assertEqual(stock.MWE_ID,'MWE-SECTOR-STOCKS-001')
