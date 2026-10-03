"""B5 outcome-free preparation. No scientific runner is exposed.

Market estimand/ES and disposition/gate mapping require canonical clarification.
"""
import hashlib
import numpy as np
import pandas as pd

PROTOCOL = 'SW10_S2_B5_VALIDATION_PROTOCOL_V1'
DECISION = '880644f4-afcc-49d9-8641-27cc0bf5bcfd'
INPUT_ID = '86045cd0-8e49-4261-aed9-3f24bfb5ff07'
INPUT_SHA = 'b905affcb0843a4d313557fc59fc543a46413258f2c49a68f1eb87d338e55915'
INPUT_BYTES = 792664
CASES = tuple(
    [(name, h, direction, False) for name, horizons, direction in (
        ('LIQ_ADJUSTED_PRICE', (5, 7, 10), 'NEGATIVE'),
        ('LIQ_REPORTED_VOLUME', (3, 5, 7, 10), 'POSITIVE'))
     for h in horizons] +
    [('RET_MOM x MARKET_SPY_TREND10', h, 'POSITIVE', True) for h in (7, 10)]
)
KEYS = tuple((c[0], c[1]) for c in CASES)
FILES = ('b5_validation_primary_summary.csv', 'b5_validation_date_effects.csv',
         'b5_validation_temporal_stability.csv', 'b5_validation_symbol_concentration.csv',
         'b5_validation_dispositions.csv', 'b5_validation_semantic_audit.csv',
         'sw10_s2_b5_validation_manifest.json')
MATERIAL_ABS_THRESHOLD = .20
INHERITED_BASE = 'd573293a-1a84-42ee-b5ec-9a3173c7bed7'
INHERITED_SUPPLEMENT = 'f3e81d1f-83e0-4c8d-a5be-6d48d85b9700'
BLOCKERS = ('MARKET_ESTIMAND_AND_STANDARDIZED_EFFECT',
            'DISPOSITION_TRUTH_TABLE', 'CONFIRMATION_GATE_SET')

def validate_cases(keys):
    if len(keys) != 9 or len(set(keys)) != 9 or set(keys) != set(KEYS):
        raise ValueError('exact nine-test family required')

def verify_bytes(blob):
    if len(blob) != INPUT_BYTES or hashlib.sha256(blob).hexdigest() != INPUT_SHA:
        raise ValueError('immutable validation input mismatch')

def centered_rank(values):
    s = pd.Series(values, dtype=float)
    return s.where(np.isfinite(s)).rank(method='average', pct=True)*2-1

def trend10(close):
    s = pd.Series(close, dtype=float)
    return s/s.shift(10)-1

def normalize_state(values):
    s = pd.Series(values, dtype=float)
    finite = s.where(np.isfinite(s))
    prior = finite.shift(1)
    mean = prior.expanding(min_periods=20).mean()
    sd = prior.expanding(min_periods=20).std(ddof=1)
    return ((finite-mean)/sd).where(np.isfinite(mean) & np.isfinite(sd) & sd.gt(1e-12))

def eligible_calendar(dates, predictor_eligible, horizon):
    # Only endpoint DATE availability is examined here; no price/return access.
    ds = pd.DatetimeIndex(dates)
    if not ds.is_monotonic_increasing or ds.has_duplicates:
        raise ValueError('unique chronological dates required')
    if len(ds) != len(predictor_eligible) or horizon not in (1,2,3,5,7,10):
        raise ValueError('invalid causal calendar')
    return [d for i,d in enumerate(ds)
            if bool(predictor_eligible[i]) and i+horizon < len(ds)
            and ds[i+horizon] < pd.Timestamp('2025-02-03')]

def four_blocks(dates):
    dates = list(dates)
    if dates != sorted(set(dates)) or len(dates) < 4:
        raise ValueError('at least four unique chronological eligible dates required')
    return {date: block for block, chunk in enumerate(np.array_split(dates,4),1)
            for date in chunk}

def lag(horizon):
    if horizon not in {h for _,h in KEYS}:
        raise ValueError('unfrozen B5 horizon')
    return horizon-1

def guard_predictor_columns(columns):
    allowed = {'symbol','trade_date','open','high','low','close','volume','adjusted'}
    if not set(columns) <= allowed:
        raise ValueError('outcome/protected/unapproved field in preparation')

def scientific_entrypoint(*args, **kwargs):
    raise RuntimeError('BLOCKED_USER: canonical prospective supplement required; no B5 outcomes')
