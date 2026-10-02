"""Synthetic/predictor-only preparation. Never reads the research input."""
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from tr_platform.research import swing10_s2_b4_contract as b

def test_snapshot_contract():
    d=json.loads(Path('research_protocols/swing10/SW10_S2_B4_PROTOCOL_V1.persisted.json').read_text())
    m=d['metadata_json']
    assert d['decision_id']=='d573293a-1a84-42ee-b5ec-9a3173c7bed7'
    assert b.PRIMARY==tuple(m['primary_tests'])
    assert b.HORIZONS==tuple(m['horizons_days'])
    assert b.FILES==tuple(m['artifact_contract'])
    assert b.DIAGNOSTIC_ONLY==tuple(m['diagnostic_only'])
    assert b.EXCLUDED==tuple(m['excluded_unavailable'])

def test_average_ties_and_nonfinite():
    np.testing.assert_allclose(b.centered_rank([1,1,3,np.inf]),[0,0,1,np.nan],equal_nan=True)

def test_single_eligible_rank():
    assert b.centered_rank([2]).tolist()==[1.]

def test_inclusive_tails():
    z=b.liquidity_membership([0,1,2,3,4,5])
    assert z.low.tolist()==[True,True,False,False,False,False]
    assert z.high.tolist()==[False,False,False,False,True,True]

def test_ties_are_inclusive_no_silent_exclusion():
    z=b.liquidity_membership([1,1,1,1,1])
    assert z.low.all() and z.high.all()

def test_membership_same_date_invariance():
    today=pd.Series([4,1,7,1,9])
    original=b.liquidity_membership(today)
    later=pd.Series([1000,2000,5000])
    later*=10
    pd.testing.assert_frame_equal(original,b.liquidity_membership(today))

@pytest.mark.parametrize('state',[-7.,-1.,0.,.5,2.,100.])
def test_market_model_fails_closed_without_outcomes(state):
    ranks=b.centered_rank(range(112)).to_numpy()
    with pytest.raises(ValueError,match='unidentifiable'):
        b.market_design(ranks,state)

@pytest.mark.parametrize('state',[-2.,0.,.75])
def test_exact_nullspace_identity(state):
    x=np.linspace(-1,1,112)
    design=np.column_stack([np.ones(len(x)),x,np.full(len(x),state),x*state])
    assert np.linalg.matrix_rank(design)==2
    # Intercept+state and rank+interaction each supply an exact null direction.
    np.testing.assert_allclose(design@[-state,0,1,0],0,atol=1e-14)
    np.testing.assert_allclose(design@[0,-state,0,1],0,atol=1e-14)

def test_family_exact_and_diagnostics_excluded():
    b.validate_family(b.FAMILY)
    assert not set(b.PRIMARY)&set(b.DIAGNOSTIC_ONLY+b.EXCLUDED)
    for bad in (b.FAMILY[:-1],b.FAMILY+(('REL_MARKET_10',1),),b.FAMILY[:-1]+(b.FAMILY[0],)):
        with pytest.raises(ValueError):b.validate_family(bad)

@pytest.mark.parametrize('valid,fdr,material,robust',itertools.product([False,True],repeat=4))
def test_every_disposition_branch(valid,fdr,material,robust):
    expected=('INVALID_SEMANTICS_NOT_TESTABLE' if not valid else
              'SEED_INDEPENDENT_VALIDATION_HYPOTHESIS' if robust and fdr and material else
              'RETAIN_AS_WEAK_EVIDENCE' if robust and fdr!=material else
              'RETAIN_AS_COUNTEREVIDENCE')
    assert b.disposition(valid,fdr,material,robust)==expected
