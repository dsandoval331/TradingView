import numpy as np
import pandas as pd
import pytest

from tr_platform.research import swing10_s2_b2_core as b2


@pytest.mark.parametrize("current,expected", [(100, 1), (200, 2), (50, .5)])
def test_volume_semantic_examples(current, expected):
    out = b2.volume_turnover(pd.Series([100.] * 20 + [current]))
    assert out.VOL_TURN_V2_CAUSAL.iloc[-1] == expected
    assert out.prior20_mean.iloc[-1] == 100


def test_volume_future_and_current_invariance():
    base = pd.Series([100.] * 20 + [200., 300., 400.])
    original = b2.volume_turnover(base)
    changed = base.copy(); changed.iloc[21:] = 999999
    assert b2.volume_turnover(changed).iloc[20].equals(original.iloc[20])
    changed = base.copy(); changed.iloc[20] = 50
    result = b2.volume_turnover(changed)
    assert result.prior20_mean.iloc[20] == original.prior20_mean.iloc[20]
    assert result.VOL_TURN_V2_CAUSAL.iloc[20] == .5
    assert original.VOL_TURN_B1_LEGACY.iloc[20] == 100


def test_volume_ineligible_preceding_window():
    assert b2.volume_turnover(pd.Series([100.] * 20)).VOL_TURN_V2_CAUSAL.isna().all()
    assert np.isnan(b2.volume_turnover(pd.Series([0.] * 20 + [100.])).VOL_TURN_V2_CAUSAL.iloc[-1])
    invalid = pd.Series([100.] * 20 + [200.]); invalid.iloc[4] = np.nan
    assert np.isnan(b2.volume_turnover(invalid).VOL_TURN_V2_CAUSAL.iloc[-1])
    invalid.iloc[4] = -1
    assert np.isnan(b2.volume_turnover(invalid).VOL_TURN_V2_CAUSAL.iloc[-1])


def fixture_panel():
    rows = []
    for symbol, phase in [("A", 0), ("B", 1), ("C", 2), ("D", 3), ("E", 4)]:
        for i, date in enumerate(pd.bdate_range("2025-01-02", periods=150)):
            close = 100 + i * .1 + np.sin(i / 7 + phase)
            rows.append([symbol, date, close, close + 1, close - 1, close, 100 + i + phase])
    return pd.DataFrame(rows, columns=["symbol", "trade_date", "open", "high", "low", "close", "volume"])


def test_all_factors_and_thresholds_ignore_future_observations():
    panel = fixture_panel(); cutoff = sorted(panel.trade_date.unique())[130]
    original = b2.causal_factors(panel)
    changed = panel.copy(); changed.loc[changed.trade_date > cutoff, ["open", "high", "low", "close", "volume"]] *= 10
    altered = b2.causal_factors(changed)
    pd.testing.assert_frame_equal(original[original.trade_date <= cutoff], altered[altered.trade_date <= cutoff])
    for factor in b2.FACTOR_COLUMNS:
        first, second = b2.date_tails(original, factor), b2.date_tails(altered, factor)
        pd.testing.assert_frame_equal(first[first.trade_date <= cutoff], second[second.trade_date <= cutoff])


def test_inclusive_tails_and_tie_overlap_are_visible():
    panel = pd.DataFrame({"symbol":list("ABCDE"), "trade_date": [pd.Timestamp("2025-01-02")] * 5,
                          "RET_MOM": [1., 2, 3, 4, 5]})
    out = b2.date_tails(panel, "RET_MOM")
    assert out.threshold_low.iloc[0] == 1.8
    assert out.threshold_high.iloc[0] == 4.2
    assert out.is_high.sum() == out.is_low.sum() == 1
    panel.RET_MOM = 1.
    assert b2.date_tails(panel, "RET_MOM").tail_overlap.all()


def test_date_is_estimator_unit():
    d = pd.Timestamp("2025-01-02")
    tails = pd.DataFrame({"symbol":list("ABCD"),"trade_date":[d]*4,
                          "is_high":[True,True,False,False],"is_low":[False,False,True,True],"tail_overlap":[False]*4})
    outcomes = pd.DataFrame({"symbol":list("ABCD"),"trade_date":[d]*4,"forward_1":[.1,.2,.0,.1]})
    out = b2.date_spreads(tails,outcomes,1)
    assert len(out) == 1
    assert out.spread.iloc[0] == pytest.approx(.1)
    assert out.high_n.iloc[0] == out.low_n.iloc[0] == 2


def test_hac_matches_independent_bartlett_calculation():
    x = np.array([.01, -.02, .03, .01, .02, -.01])
    u = x-x.mean(); n=len(x)
    for h in [1,2,3,5]:
        lag=h-1
        kernel = np.fromfunction(lambda i,j: np.maximum(1-np.abs(i-j)/(lag+1),0), (n,n))
        expected = float(u @ kernel @ u) / n**2
        got=b2.hac_mean(x,h)
        assert got["hac_se"]**2 == pytest.approx(expected)
        assert got["hac_lag"] == lag


def test_bh_uses_declared_family_and_preserves_raw_input():
    p={"a":.01,"b":.04,"c":.03,"d":.2}
    got=b2.bh_adjust(p,list(p))
    assert got == pytest.approx({"a":.04,"b":.05333333333333334,"c":.05333333333333334,"d":.2})
    assert p["a"] == .01
    with pytest.raises(ValueError,match="family"):
        b2.bh_adjust(p,["a"])


def test_temporal_blocks_are_chronological_and_outcome_independent():
    dates=pd.bdate_range("2025-01-02",periods=11)
    blocks=b2.chronological_blocks(dates)
    assert list(blocks.values()) == [1,1,1,2,2,2,3,3,3,4,4]
    assert b2.chronological_blocks(list(reversed(dates))) == blocks


def test_incomplete_scientific_contract_fails_closed():
    with pytest.raises(ValueError,match="hypothesized_directions"):
        b2.require_scientific_contract({"protocol":b2.PROTOCOL})
