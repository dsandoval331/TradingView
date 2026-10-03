import pandas as pd
import pytest
from pathlib import Path
from cloud_compute import swing10_b5a_boundary_verify as v

def payload(date):return {'adjusted':True,'results':[{'t':int(pd.Timestamp(date).tz_localize('America/New_York').timestamp()*1000)}]}
def probes(older_status=403,older_payload=None):
 return [('earliest_available_day',payload('2024-10-02'),{'http_status':200},b'fixture'),('earlier_aapl_history',older_payload or {},{'http_status':older_status},b'fixture'),('earlier_spy_history',older_payload or {},{'http_status':older_status},b'fixture')]

def test_guard_self():v.guard_source(Path(v.__file__).read_text())
@pytest.mark.parametrize('code',["x['c']","x['forward_return']","x.shift(-1)","x.pct_change()","pd.read_parquet(path)"])
def test_prohibited_evaluation_rejected(code):
 with pytest.raises(ValueError):v.guard_source(code)
def test_403_predecessor_with_valid_earliest_confirms_exposed_coverage():assert v.classify('2024-10-02',probes())=='MAXIMUM_PROVIDER_EXPOSED_PRE_DISCOVERY_COVERAGE_VERIFIED'
def test_empty_200_earlier_ranges_are_data_unavailable():assert v.classify('2024-10-02',probes(200,{}))=='MAXIMUM_PROVIDER_EXPOSED_PRE_DISCOVERY_COVERAGE_VERIFIED'
def test_earlier_available_data_fails_closed():assert v.classify('2024-10-02',probes(200,payload('2024-10-01')))=='PRE_DISCOVERY_COVERAGE_REQUIRES_RECOVERY'
def test_protected_dates_fail_closed():
 with pytest.raises(ValueError):v.observed_dates(payload('2025-02-03'))
def test_outcome_column_names_fail_closed():
 p=payload('2024-10-02');p['results'][0]['forward_return']=0
 with pytest.raises(ValueError):v.observed_dates(p)
