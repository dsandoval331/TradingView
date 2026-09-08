import pandas as pd

from tr_platform.pmpd_v5.quality import build_session_quality_layer


def _base_row(symbol="TEST", trade_date="2025-01-02"):
    return dict(
        symbol=symbol,
        trade_date=trade_date,
        pmh=101.0,
        pml=99.0,
        ahh=100.5,
        ahl=98.5,
        pdh=100.8,
        pdl=98.8,
        has_complete_six_levels=True,
        pm_bar_count=30,
        prior_ah_bar_count=20,
        prior_rth_bar_count=390,
        overnight_gap_pct=0.5,
        price_scale_ratio=1.005,
    )


def test_normal_row_is_primary_eligible():
    q = build_session_quality_layer(pd.DataFrame([_base_row()]))
    r = q.iloc[0]
    assert bool(r.primary_inference_eligible)
    assert r.price_continuity_tier == "NORMAL"
    assert r.eligibility_reason == "PRIMARY_ELIGIBLE"


def test_sparse_extended_hours_is_flagged_not_excluded():
    row = _base_row()
    row["pm_bar_count"] = 3
    q = build_session_quality_layer(pd.DataFrame([row]))
    r = q.iloc[0]
    assert bool(r.sparse_extended_hours_flag)
    assert bool(r.primary_inference_eligible)
    assert bool(r.sensitivity_review_required)
    assert r.eligibility_reason == "SPARSE_EXTENDED_HOURS_SENSITIVITY"


def test_obvious_scale_break_is_excluded_from_primary_inference():
    row = _base_row()
    row.update(
        pmh=112.0, pml=110.0,
        ahh=1117.0, ahl=1112.0,
        pdh=1142.0, pdl=1107.0,
        overnight_gap_pct=-90.0,
        price_scale_ratio=0.10,
    )
    q = build_session_quality_layer(pd.DataFrame([row]))
    r = q.iloc[0]
    assert r.price_continuity_tier == "SEVERE_DISCONTINUITY"
    assert bool(r.price_scale_severe_flag)
    assert not bool(r.primary_inference_eligible)
    assert r.eligibility_reason == "SEVERE_PRICE_SCALE_DISCONTINUITY"


def test_incomplete_levels_are_structurally_ineligible():
    row = _base_row()
    row["ahh"] = None
    row["has_complete_six_levels"] = False
    q = build_session_quality_layer(pd.DataFrame([row]))
    r = q.iloc[0]
    assert not bool(r.structural_eligible)
    assert not bool(r.primary_inference_eligible)
    assert r.eligibility_reason == "INCOMPLETE_SIX_LEVELS"
