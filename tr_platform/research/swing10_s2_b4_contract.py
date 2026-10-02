"""Outcome-free B4 contract preparation; no scientific execution entry point.

The frozen market interaction model cannot identify beta_I within one date.
Reject that design before any outcome is accepted. Canonical clarification is
required before implementing a replacement estimator or standardization rule.
"""
import numpy as np
import pandas as pd

HORIZONS=(1,2,3,5,7,10)
LIQUIDITY=('LIQ_CLOSE_DOLLAR_VOLUME','LIQ_ADJUSTED_PRICE',
           'LIQ_REPORTED_VOLUME','LIQ_RANGE_SPREAD_PROXY')
INTERACTIONS=tuple(f'{p} x {m}' for m in
    ('MARKET_SPY_TREND10','MARKET_PANEL_BREADTH10','MARKET_PANEL_DISPERSION10')
    for p in ('RET_MOM','SHORT_REV'))
PRIMARY=LIQUIDITY+INTERACTIONS
FAMILY=tuple((p,h) for p in PRIMARY for h in HORIZONS)
DIAGNOSTIC_ONLY=('REL_MARKET_10','LIQ_PRIOR20_ACTIVITY','MARKET_SPY_VOL14')
EXCLUDED=('REL_SECTOR_10','REL_INDUSTRY_10','LIQ_TRUE_BID_ASK',
          'LIQ_SHARES_TURNOVER','LIQ_TRANSACTION_COUNT','LIQ_VWAP_DOLLAR_VOLUME')
FILES=('b4_scientific_summary.csv','b4_date_primary_quantities.csv',
       'b4_temporal_stability.csv','b4_symbol_concentration.csv',
       'b4_model_diagnostics.csv','b4_dispositions.csv','sw10_s2_b4_manifest.json')

def centered_rank(values):
    """Single eligible date cross section, average ties, rank/N exactly."""
    z=pd.Series(values,dtype=float)
    return z.where(np.isfinite(z)).rank(method='average',pct=True)*2-1

def liquidity_membership(values):
    """Same-date inclusive p20/p80 membership; exclude nonfinite values."""
    z=pd.Series(values,dtype=float).where(lambda x:np.isfinite(x))
    return pd.DataFrame({'low':z.le(z.quantile(.2)),
                         'high':z.ge(z.quantile(.8))})

def market_design(primary_rank,market_state):
    """Construct the literal predictor-only frozen model and fail closed."""
    x=np.asarray(primary_rank,dtype=float)
    if x.ndim!=1 or not np.isfinite(x).all() or not np.isfinite(market_state):
        raise ValueError('finite one-date predictors required')
    design=np.column_stack([np.ones(len(x)),x,
                            np.full(len(x),market_state),x*market_state])
    if np.linalg.matrix_rank(design)<4:
        raise ValueError('unidentifiable frozen date-level market interaction: rank < 4')
    return design

def validate_family(keys):
    if len(keys)!=60 or len(set(keys))!=60 or set(keys)!=set(FAMILY):
        raise ValueError('exact joint 60-test family required')

def disposition(valid,fdr,material,robust):
    if not valid:return 'INVALID_SEMANTICS_NOT_TESTABLE'
    if robust and fdr and material:return 'SEED_INDEPENDENT_VALIDATION_HYPOTHESIS'
    if robust and bool(fdr)!=bool(material):return 'RETAIN_AS_WEAK_EVIDENCE'
    return 'RETAIN_AS_COUNTEREVIDENCE'
