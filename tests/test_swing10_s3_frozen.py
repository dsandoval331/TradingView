import copy
import json
import math
from pathlib import Path
import statistics
import unittest
from tr_platform.research import swing10_s3_preparation as p
from tr_platform.research import swing10_s3_preflight as audit
from tr_platform.research import swing10_s3_engine as e

def bar(o=100,h=100.5,l=99.5,c=100,v=100):return dict(open=o,high=h,low=l,close=c,volume=v)

def data(n=20):
    return {f'{i:03}':{h:{f'S{s:02}':(.01+s*.001+i*.0001)/h for s in range(12)} for h in p.CAPS} for i in range(n)}

class FrozenEngine(unittest.TestCase):
    def test_time_every_cap_side(self):
        for side in p.SIDES:
            for cap in p.CAPS:
                r=e.event(side,'TIME',cap,[bar()]*5,[bar(c=100.2)]*10)
                self.assertEqual(r['held_sessions'],cap);self.assertEqual(r['exit_reason'],'TIME')
    def test_stop_first_double_hit(self):
        r=e.event('LONG_LOW','BRACKET_1_1',5,[bar()]*5,[bar(h=102,l=98)]+[bar()]*9)
        self.assertEqual(r['exit_price'],99);self.assertTrue(r['ambiguous_bar'])
    def test_target_first_diagnostic(self):
        r=e.event('LONG_LOW','BRACKET_1_1',5,[bar()]*5,[bar(h=102,l=98)]+[bar()]*9,ordering='TARGET_FIRST')
        self.assertEqual(r['exit_price'],101)
    def test_adverse_gap_worse_open(self):
        r=e.event('LONG_LOW','BRACKET_1_1',5,[bar()]*5,[bar(),bar(o=97,h=98,l=96,c=97)]+[bar()]*8)
        self.assertEqual(r['exit_price'],97);self.assertEqual(r['exit_reason'],'STOP_GAP')
    def test_favorable_gap_target_fill(self):
        r=e.event('SHORT_HIGH','BRACKET_1_1',5,[bar()]*5,[bar(),bar(o=97,h=98,l=96,c=97)]+[bar()]*8)
        self.assertEqual(r['exit_price'],99);self.assertEqual(r['exit_reason'],'TARGET_GAP')
    def test_short_sign(self):
        r=e.event('SHORT_HIGH','TIME',5,[bar()]*5,[bar(h=101,l=97,c=98)]*10)
        self.assertAlmostEqual(r['gross_return'],.02)
    def test_cost_once_duration(self):
        for cost in (0,10,25,50):
            r=e.event('LONG_LOW','TIME',5,[bar()]*5,[bar()]*10,cost)
            self.assertAlmostEqual(r['net_return'],-cost/10000);self.assertAlmostEqual(r['dailyized_net_return'],-cost/50000)
    def test_trail_not_same_bar_high(self):
        r=e.event('LONG_LOW','TRAIL_2',5,[bar()]*5,[bar(h=110,l=99,c=100)]+[bar()]*9)
        self.assertEqual(r['exit_reason'],'TIME')
    def test_trail_completed_close_next_session(self):
        r=e.event('LONG_LOW','TRAIL_2',5,[bar()]*5,[bar(h=105,l=99,c=104),bar(o=100,h=101,l=99,c=100)]+[bar()]*8)
        self.assertEqual(r['held_sessions'],2);self.assertEqual(r['exit_reason'],'STOP_GAP')
    def test_structure_prior5(self):
        prior=[bar(l=99)]*5
        r=e.event('LONG_LOW','STRUCTURE_5',5,prior,[bar(l=98.5)]+[bar()]*9)
        self.assertEqual(r['exit_price'],99)
    def test_structure_short_prior5(self):
        r=e.event('SHORT_HIGH','STRUCTURE_5',5,[bar(h=101)]*5,[bar(h=101.5)]+[bar()]*9)
        self.assertEqual(r['exit_price'],101)
    def test_invalid_bar_fail_closed(self):
        for b in (bar(v=-1),bar(l=101),bar(c=math.nan),bar(o=0)):
            with self.assertRaises(ValueError):e.event('LONG_LOW','TIME',5,[bar()]*5,[b]+[bar()]*9)
    def test_common_full10_required(self):
        with self.assertRaises(ValueError):e.event('LONG_LOW','TIME',5,[bar()]*5,[bar()]*5)
    def test_prior5_required(self):
        with self.assertRaises(ValueError):e.event('LONG_LOW','TIME',5,[bar()]*4,[bar()]*10)
    def test_grid_no_extra(self):
        for a in ('NEW','BRACKET_3_1'):
            with self.assertRaises(ValueError):e.event('LONG_LOW',a,5,[bar()]*5,[bar()]*10)
        with self.assertRaises(ValueError):e.event('LONG_LOW','TIME',6,[bar()]*5,[bar()]*10)
    def test_barrier_precedes_force_close(self):
        r=e.event('LONG_LOW','BRACKET_1_1',5,[bar()]*5,[bar()]*4+[bar(l=98)]+[bar()]*5)
        self.assertEqual(r['exit_reason'],'STOP')
    def test_excursion_bounds(self):
        r=e.event('LONG_LOW','BRACKET_1_1',5,[bar()]*5,[bar(h=102,l=98)]+[bar()]*9)
        self.assertLessEqual(r['mfe_lower'],r['mfe_upper']);self.assertLessEqual(r['mae_lower'],r['mae_upper']);self.assertTrue(r['excursion_censored'])
    def test_unused_later_bars_invariant(self):
        bars=[bar()]*10;first=e.event('LONG_LOW','TIME',5,[bar()]*5,bars)
        bars=copy.deepcopy(bars);bars[7]=bar(h=105,l=90,c=92)
        self.assertEqual(first,e.event('LONG_LOW','TIME',5,[bar()]*5,bars))
    def test_hac_known_fixture(self):
        x=[.01,-.02,.03,-.01,.05,.02,-.03,.04,.01,-.02,.06,.02]
        mean=sum(x)/len(x);u=[v-mean for v in x];n=len(x)
        var=sum(v*v for v in u)+2*sum((1-k/10)*sum(u[i]*u[i-k] for i in range(k,n)) for k in range(1,10))
        r=e.hac_mean(x);self.assertAlmostEqual(r['hac_se'],math.sqrt(var)/n);self.assertAlmostEqual(r['standardized_effect'],mean/statistics.stdev(x))
        self.assertAlmostEqual(r['p_raw'],math.erfc(abs(mean/r['hac_se'])/math.sqrt(2)))
    def test_hac_lag_frozen(self):
        with self.assertRaises(ValueError):e.hac_mean([1,2,3],lag=4)
    def test_hac_constant_not_testable(self):
        with self.assertRaises(ValueError):e.hac_mean([1]*20)
    def test_bh_exact12(self):
        self.assertAlmostEqual(e.bh12([.001]+[1]*11)[0],.012)
        self.assertEqual(e.bh12([None]*12),[1.]*12)
        with self.assertRaises(ValueError):e.bh12([.01]*36)
    def test_blocks_fixed_balanced(self):
        dates=[f'{i:03}' for i in range(379)];b=e.blocks(dates)
        self.assertEqual(list(map(len,b)),[95,95,95,94]);self.assertEqual(sum(b,[]),dates)
    def test_date_cap_symbol_aggregation(self):
        d=data();v,c,caps=e.family(d)
        self.assertAlmostEqual(sum(c.values()),statistics.mean(v.values()))
        self.assertAlmostEqual(v['000'],sum(statistics.mean(d['000'][h].values()) for h in p.CAPS)/3)
        self.assertEqual(set(caps),set(p.CAPS))
    def test_missing_cap_reject(self):
        d=data();del d['000'][10]
        with self.assertRaises(ValueError):e.family(d)
    def test_noncommon_symbols_reject(self):
        d=data();del d['000'][5]['S00']
        with self.assertRaises(ValueError):e.family(d)
    def test_concentration_recompute_all_caps(self):
        d=data();v,c,_=e.family(d);r=e.concentration(d,c,statistics.mean(v.values()))
        self.assertEqual(len(r['removed']),5);self.assertFalse(r['sign_reversal']);self.assertTrue(r['pass']);self.assertAlmostEqual(sum(r['shares'].values()),1)
    def test_tie_symbol_order(self):
        d={f'{i:03}':{h:{f'S{s:02}':1. for s in range(12)} for h in p.CAPS} for i in range(4)}
        v,c,_=e.family(d);r=e.concentration(d,c,1)
        self.assertEqual(r['removed'],['S00','S01','S02','S03','S04'])
    def test_leave5_reversal(self):
        d={f'{i:03}':{h:{f'S{s:02}':1. if s<5 else -.1 for s in range(12)} for h in p.CAPS} for i in range(4)}
        v,c,_=e.family(d);r=e.concentration(d,c,statistics.mean(v.values()));self.assertTrue(r['sign_reversal']);self.assertFalse(r['pass'])
    def test_zero_not_reversal(self):
        d={f'{i:03}':{h:{f'S{s:02}':1. if s<5 else 0 for s in range(12)} for h in p.CAPS} for i in range(4)}
        v,c,_=e.family(d);r=e.concentration(d,c,statistics.mean(v.values()));self.assertEqual(r['leave5_effect'],0);self.assertTrue(r['pass'])
    def test_unavailable_leave5_fail_support(self):
        d={f'{i:03}':{h:{f'S{s:02}':1. for s in range(5)} for h in p.CAPS} for i in range(4)}
        v,c,_=e.family(d);self.assertFalse(e.concentration(d,c,1)['pass'])
    def test_temporal_positive(self):
        v={f'{i:03}':1. for i in range(20)};r,passed=e.temporal(v,e.blocks(sorted(v)));self.assertTrue(passed);self.assertEqual([x['effect_share'] for x in r],[.25]*4)
    def test_temporal_concentration_failure(self):
        v={f'{i:03}':10. if i<5 else 1. for i in range(20)};self.assertFalse(e.temporal(v,e.blocks(sorted(v)))[1])
    def test_temporal_direction_failure(self):
        v={f'{i:03}':1. if i<10 else -1. for i in range(20)};self.assertFalse(e.temporal(v,e.blocks(sorted(v)))[1])
    def test_all_dispositions(self):
        self.assertEqual(e.disposition(False,1,1,.01,[True]),'NOT_TESTABLE')
        self.assertEqual(e.disposition(True,0,1,.01,[True]),'NO_S4_SUPPORT')
        self.assertEqual(e.disposition(True,1,.199,.01,[True]),'NO_S4_SUPPORT')
        self.assertEqual(e.disposition(True,1,.2,.051,[True]),'NO_S4_SUPPORT')
        self.assertEqual(e.disposition(True,1,.2,.05,[None]),'DEVELOPMENT_ONLY_WEAK')
        self.assertEqual(e.disposition(True,1,.2,.05,[True]),'ELIGIBLE_FOR_CANONICAL_S4_REVIEW')
    def test_selection_per_side_ci_tie(self):
        rows=[dict(side='LONG_LOW',architecture_id=a,disposition='ELIGIBLE_FOR_CANONICAL_S4_REVIEW',ci95_low=1.) for a in ('TIME','BRACKET_1_1')]
        self.assertEqual(e.select_for_review(rows),{'LONG_LOW':'BRACKET_1_1'})
    def test_science_entry_disabled(self):
        with self.assertRaises(RuntimeError):e.execute_science()

class FrozenPreflight(unittest.TestCase):
    def test_authority_full_snapshot(self):
        root=Path(__file__).resolve().parents[1];f=json.loads((root/'research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.persisted.json').read_text());q=json.loads((root/'research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.proposed.json').read_text());self.assertTrue(audit.validate_freeze(f,q))
        f['metadata_json']['scientific_execution_authorized']=True
        with self.assertRaises(ValueError):audit.validate_freeze(f,q)
    def test_source_guard(self):
        self.assertTrue(audit.guard_source(Path(audit.__file__).read_text()))
        for src in ('from tr_platform.research import swing10_s3_engine','import requests','x.pct_change()','hac_mean(x)','event(x)','import swing10_s2_b5_validation','eval(x)'):
            with self.assertRaises(ValueError):audit.guard_source(src)
    def test_real_input_hash_rejection(self):
        with self.assertRaises(ValueError):audit.decode_verified(b'not immutable development')
    def test_outcome_columns_reject(self):
        for extra in ('forward_return','MFE','p_value','disposition','profitability'):
            with self.assertRaises(ValueError):p.reject_outcome_columns(p.FIELDS|{extra})
    def test_exact_preflight_artifacts(self):
        self.assertEqual(len(audit.FILES),7);self.assertEqual(set(audit.SCHEMAS),set(audit.FILES[:-1]));self.assertFalse(any('summary' in f for f in audit.FILES))
    def test_exact_future_artifacts(self):
        root=Path(__file__).resolve().parents[1];q=json.loads((root/'research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.proposed.json').read_text());self.assertEqual(len(q['artifact_schemas']),10);self.assertIn('s3_candidate_summary.csv',q['artifact_schemas'])
    def test_calendar_capacity(self):
        dates=[f'2025-{m:02}-{d:02}' for m in (2,3) for d in range(1,28) if f'2025-{m:02}-{d:02}'>='2025-02-03']
        eligible=[d for d in dates if p.common_date_eligibility(dates,d)];self.assertEqual(len(eligible),len(dates)-15)
    def test_tail_future_invariance(self):
        x={'2025-02-03':[(f'S{i}',i+1) for i in range(112)],'2025-02-04':[('X',999)]}
        first=p.signal_at_date(x,'2025-02-03');x['2025-02-04']=[('X',1)]
        self.assertEqual(first,p.signal_at_date(x,'2025-02-03'))
    def test_protected_calendar_denied(self):
        with self.assertRaises(ValueError):p.common_date_eligibility(['2026-08-28'],'2026-08-28')
    def test_b5_registration_denied(self):
        with self.assertRaises(ValueError):p.validate_input_registration(dict(sha256=p.CONSUMED_B5_SHA,object_size_bytes=792664,object_path='B5'))

if __name__=='__main__':unittest.main()

class EndToEndSynthetic(unittest.TestCase):
    def test_full_frozen_grid_and_artifacts(self):
        root=Path(__file__).resolve().parents[1];contract=json.loads((root/'research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.proposed.json').read_text())
        cohorts={}
        for i in range(16):
            sides={}
            for side in p.SIDES:
                rows={}
                for j in range(8):
                    bs=[]
                    for k in range(10):
                        c=100+(k+1)*(.08+i*.005+j*.001)*(1 if side=='LONG_LOW' else -1)
                        b=bar(h=max(100,c)+.05,l=min(100,c)-.05,c=c);b['date']=f'FIXTURE_SESSION_{i}_{k}';bs.append(b)
                    rows[f'FIXTURE_S{j}']={'prior':[bar()]*5,'bars':bs}
                sides[side]=rows
            cohorts[f'{i:03}']=sides
        tables=e.build_synthetic_tables(cohorts,contract)
        self.assertEqual(set(tables),set(contract['artifact_schemas']));self.assertEqual(len(tables['s3_candidate_registry.csv']),36);self.assertEqual(len(tables['s3_candidate_summary.csv']),12)
        self.assertEqual(len(tables['s3_event_exits.csv']),36*16*8);self.assertEqual(len(tables['s3_event_paths.csv']),36*16*8*10)
        self.assertTrue(tables['sw10_s3_manifest.json']['synthetic_only'])
        self.assertFalse(tables['sw10_s3_manifest.json']['scientific_execution_authorized'])
    def test_real_symbol_orchestration_denied(self):
        with self.assertRaises(ValueError):e.build_synthetic_tables({'2025-02-03':{'LONG_LOW':{'AAPL':{}}}}, {})
