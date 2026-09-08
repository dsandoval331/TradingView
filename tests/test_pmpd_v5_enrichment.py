import pandas as pd
from tr_platform.pmpd_v5.enrichment import _identity_from_vector, _rth_open_context, _transition_features

def test_identity_multi_is_not_fake_order():
    assert _identity_from_vector("100")=="PM"
    assert _identity_from_vector("110")=="MULTI_PM_AH"
    assert _identity_from_vector("111")=="MULTI_PM_AH_PD"

def test_rth_open_context_bull():
    day=pd.DataFrame([{"timestamp_utc":pd.Timestamp("2025-01-02T14:30:00Z"),"open":102.0}])
    x=_rth_open_context(day,"BULL",{"PM":100.0,"AH":101.0,"PD":103.0})
    assert x["levels_precleared_at_rth_open"]==2
    assert x["rth_open_location_relative_stack"]=="BETWEEN_MIDDLE_OUTER"

def test_recross_count():
    t=pd.DataFrame([
      {"sequence":1,"timestamp_utc":"2025-01-02T14:31:00Z","prior_close_vector":"000","new_close_vector":"100","traded_vector":"100","attempt_number":1,"close":1},
      {"sequence":2,"timestamp_utc":"2025-01-02T14:32:00Z","prior_close_vector":"100","new_close_vector":"000","traded_vector":"000","attempt_number":1,"close":1},
      {"sequence":3,"timestamp_utc":"2025-01-02T14:33:00Z","prior_close_vector":"000","new_close_vector":"100","traded_vector":"100","attempt_number":2,"close":1},
    ])
    x=_transition_features(t,pd.Timestamp("2025-01-02T14:33:00Z"))
    assert x["directional_recross_count_to_dp"]==2
    assert x["structural_path_signature_to_dp"]=="000>100>000>100"
