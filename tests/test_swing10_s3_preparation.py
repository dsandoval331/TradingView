import copy,json,unittest
from datetime import date,timedelta
from pathlib import Path
from tr_platform.research import swing10_s3_preparation as p

ROOT=Path(__file__).resolve().parents[1]
class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.c=json.loads((ROOT/'research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.proposed.json').read_text())
        self.input={'sha256':p.DEVELOPMENT_SHA,'object_size_bytes':p.DEVELOPMENT_BYTES,'object_path':p.OBJECT,'role':'DEVELOPMENT_CANDIDATE','date_start':'2025-02-03','date_end':'2026-08-27'}
    def test_contract(self):self.assertTrue(p.validate_contract(self.c))
    def test_no_science(self):
        with self.assertRaises(RuntimeError):p.execute_science(self.c)
    def test_fake_freeze_still_no_science(self):
        c=copy.deepcopy(self.c);c['status']='FROZEN';c['outcome_execution_authorized']=True
        with self.assertRaises(RuntimeError):p.execute_science(c)
    def test_exact_input(self):self.assertTrue(p.validate_input_registration(self.input))
    def test_B5_deny(self):
        self.input['sha256']=p.CONSUMED_B5_SHA
        with self.assertRaises(ValueError):p.validate_input_registration(self.input)
    def test_S5_deny(self):
        self.input['object_path']='protected/S5.csv'
        with self.assertRaises(ValueError):p.validate_input_registration(self.input)
    def test_size_reject(self):
        self.input['object_size_bytes']+=1
        with self.assertRaises(ValueError):p.validate_input_registration(self.input)
    def test_date_reject(self):
        self.input['date_end']='2026-08-28'
        with self.assertRaises(ValueError):p.validate_input_registration(self.input)
    def test_role_reject(self):
        self.input['role']='VALIDATION'
        with self.assertRaises(ValueError):p.validate_input_registration(self.input)
    def test_blob_mismatch(self):
        with self.assertRaises(ValueError):p.opaque_bytes_verify(b'not certified')
    def test_base_fields(self):p.reject_outcome_columns(p.FIELDS)
    def test_forward_field(self):
        with self.assertRaises(ValueError):p.reject_outcome_columns(p.FIELDS|{'forward_return'})
    def test_effect_field(self):
        with self.assertRaises(ValueError):p.reject_outcome_columns(p.FIELDS|{'effect_size'})
    def test_p_field(self):
        with self.assertRaises(ValueError):p.reject_outcome_columns(p.FIELDS|{'p_value'})
    def test_path_field(self):
        with self.assertRaises(ValueError):p.reject_outcome_columns(p.FIELDS|{'mfe'})
    def test_unknown_field(self):
        with self.assertRaises(ValueError):p.reject_outcome_columns(p.FIELDS|{'unknown'})
    def test_average_rank_ties(self):self.assertEqual(p.same_date_ranks([('A',1),('B',1),('C',2)]),{'A':0.,'B':0.,'C':1.})
    def test_rank_finite_only(self):self.assertEqual(p.same_date_ranks([('A',1),('B',float('nan')),('C',None)]),{'A':1.})
    def test_rank_no_finite(self):
        with self.assertRaises(ValueError):p.same_date_ranks([('A',None)])
    def test_duplicate_symbol(self):
        with self.assertRaises(ValueError):p.same_date_ranks([('A',1),('A',2)])
    def test_quantile_linear(self):self.assertEqual(p.quantile([1,2,3,4,5],.2),1.8)
    def test_inclusive_tails(self):self.assertEqual(p.tail_membership([('A',1),('B',1),('C',3)]),({'A','B'},{'C'}))
    def test_tie_overlap_retained(self):self.assertEqual(p.tail_membership([('A',1),('B',1)]),({'A','B'},{'A','B'}))
    def test_future_invariance(self):
        panel={'2025-03-01':[('A',1),('B',2)],'2025-03-02':[('A',999),('B',1)]}
        a=p.signal_at_date(panel,'2025-03-01');panel['2025-03-02']=[('A',-500),('B',4000)]
        self.assertEqual(a,p.signal_at_date(panel,'2025-03-01'))
    def test_current_change(self):self.assertNotEqual(p.tail_membership([('A',1),('B',2)]),p.tail_membership([('A',3),('B',2)]))
    def test_registry36(self):self.assertEqual(len(p.registry()),36)
    def test_registry_unique(self):self.assertEqual(len({r['candidate_id'] for r in p.registry()}),36)
    def test_all3caps_every_arch_side(self):
        for s in p.SIDES:
            for a in p.ARCHITECTURES:self.assertEqual([r['cap_days'] for r in p.registry() if r['side']==s and r['architecture_id']==a],[5,7,10])
    def test_horizon_drift(self):
        self.c['horizons']['validated_caps']=[10]
        with self.assertRaises(ValueError):p.validate_contract(self.c)
    def test_factor_drift(self):
        self.c['factor']['name']='LIQ_REPORTED_VOLUME'
        with self.assertRaises(ValueError):p.validate_contract(self.c)
    def test_S5_unlock(self):
        self.c['S5']['future_validation_authorized']=True
        with self.assertRaises(ValueError):p.validate_contract(self.c)
    def calendar(self):return [(date(2025,2,3)+timedelta(days=i)).isoformat() for i in range(30)]
    def test_calendar_warmup(self):self.assertFalse(p.common_date_eligibility(self.calendar(),self.calendar()[4]))
    def test_calendar_endpoint(self):self.assertFalse(p.common_date_eligibility(self.calendar(),self.calendar()[-10]))
    def test_calendar_eligible(self):self.assertTrue(p.common_date_eligibility(self.calendar(),self.calendar()[5]))
    def test_calendar_protected_date(self):
        with self.assertRaises(ValueError):p.common_date_eligibility(['2026-08-28'],'2026-08-28')
    def test_source_guard(self):self.assertTrue(p.source_guard((ROOT/'tr_platform/research/swing10_s3_preparation.py').read_text()))
    def test_future_primitive_rejected(self):
        with self.assertRaises(ValueError):p.source_guard('x.shift(-1)')
    def test_outcome_import_rejected(self):
        with self.assertRaises(ValueError):p.source_guard('from tr_platform.research.swing10_s2_b5_validation import outcome')
    def test_B5_file_reader_rejected(self):
        with self.assertRaises(ValueError):p.source_guard("open('b5_validation_primary_summary.csv')")
    def test_network_import_rejected(self):
        with self.assertRaises(ValueError):p.source_guard('import requests')
    def test_dynamic_execution_rejected(self):
        with self.assertRaises(ValueError):p.source_guard("eval('future_data')")
if __name__=='__main__':unittest.main()
