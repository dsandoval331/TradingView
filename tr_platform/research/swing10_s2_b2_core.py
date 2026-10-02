"""Outcome-independent building blocks for SW10_S2_B2_PROTOCOL_V1.

This module deliberately provides no research runner or promotion defaults.
Directional hypotheses and disposition rules must come from canonical authority.
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

PROTOCOL = "SW10_S2_B2_PROTOCOL_V1"
HORIZONS = (1, 2, 3, 5, 7, 10)
FACTOR_COLUMNS = (
    "RET_MOM", "SHORT_REV", "VOL_TURN_B1_LEGACY", "VOL_TURN_V2_CAUSAL",
    "HIGH52", "VOL_REGIME", "GAP_OVN",
)


def volume_turnover(volume: pd.Series) -> pd.DataFrame:
    """Use exactly 20 immediately preceding valid completed observations."""
    values = pd.to_numeric(volume, errors="coerce").astype(float)
    valid = values.where(np.isfinite(values) & (values >= 0))
    denominator = valid.shift(1).rolling(20, min_periods=20).mean()
    denominator = denominator.where(denominator > 0)
    causal = valid / denominator
    # Preserve the original B1 expression, including its zero-volume behavior.
    legacy_ratio = values / values.shift(1).rolling(20, min_periods=20).mean()
    legacy = values / legacy_ratio
    return pd.DataFrame({"prior20_mean": denominator,
                         "VOL_TURN_V2_CAUSAL": causal,
                         "VOL_TURN_B1_LEGACY": legacy})


def causal_factors(panel: pd.DataFrame) -> pd.DataFrame:
    """Reproduce B1's other factor definitions; split legacy/V2 volume versions."""
    required = ["symbol", "trade_date", "open", "high", "low", "close", "volume"]
    if not set(required).issubset(panel.columns):
        raise ValueError("missing daily panel columns")
    if panel.duplicated(["symbol", "trade_date"]).any():
        raise ValueError("duplicate symbol/date")
    d = panel[required].copy().sort_values(["symbol", "trade_date"], kind="stable").reset_index(drop=True)
    d["trade_date"] = pd.to_datetime(d.trade_date)
    if d[required].isna().any().any():
        raise ValueError("null daily panel values; no imputation permitted")
    chunks = []
    for _, z in d.groupby("symbol", sort=True):
        z = z.copy()
        prior = z.close.shift(1)
        z["RET_MOM"] = z.close / z.close.shift(10) - 1
        z["SHORT_REV"] = z.close / prior - 1
        z["GAP_OVN"] = z.open / prior - 1
        tr = pd.concat([z.high - z.low, (z.high - prior).abs(), (z.low - prior).abs()], axis=1).max(axis=1)
        z["VOL_REGIME"] = tr.shift(1).rolling(14, min_periods=14).mean() / prior
        z["HIGH52"] = z.close / z.close.shift(1).rolling(252, min_periods=120).max() - 1
        v = volume_turnover(z.volume)
        z["VOL_TURN_B1_LEGACY"] = v.VOL_TURN_B1_LEGACY
        z["VOL_TURN_V2_CAUSAL"] = v.VOL_TURN_V2_CAUSAL
        chunks.append(z)
    return pd.concat(chunks, ignore_index=True)


def date_tails(factors: pd.DataFrame, factor: str) -> pd.DataFrame:
    """Inclusive 80/20 masks, with ties/overlap explicitly visible."""
    if factor not in FACTOR_COLUMNS:
        raise ValueError("unknown factor version")
    z = factors[["symbol", "trade_date", factor]].copy()
    z = z[np.isfinite(z[factor])].copy()
    g = z.groupby("trade_date")[factor]
    z["threshold_high"] = g.transform(lambda x: x.quantile(.8, interpolation="linear"))
    z["threshold_low"] = g.transform(lambda x: x.quantile(.2, interpolation="linear"))
    z["is_high"] = z[factor] >= z.threshold_high
    z["is_low"] = z[factor] <= z.threshold_low
    z["tail_overlap"] = z.is_high & z.is_low
    return z


def forward_returns(panel: pd.DataFrame) -> pd.DataFrame:
    """Outcome construction is separate from classification."""
    d = panel.sort_values(["symbol", "trade_date"], kind="stable").copy()
    g = d.groupby("symbol").close
    for h in HORIZONS:
        d[f"forward_{h}"] = g.shift(-h) / d.close - 1
    return d[["symbol", "trade_date"] + [f"forward_{h}" for h in HORIZONS]]


def chronological_blocks(eligible_dates: Iterable) -> dict:
    """Partition input-eligible dates before examining forward outcomes."""
    dates = sorted(set(pd.to_datetime(list(eligible_dates))))
    if len(dates) < 4:
        raise ValueError("four temporal blocks require at least four eligible dates")
    return {date: number for number, block in enumerate(np.array_split(np.array(dates, dtype=object), 4), 1)
            for date in block}


def date_spreads(tails: pd.DataFrame, outcomes: pd.DataFrame, horizon: int) -> pd.DataFrame:
    if horizon not in HORIZONS:
        raise ValueError("unfrozen horizon")
    value = f"forward_{horizon}"
    d = tails.merge(outcomes[["symbol", "trade_date", value]], on=["symbol", "trade_date"],
                    how="left", validate="one_to_one")
    rows = []
    for date, z in d.groupby("trade_date", sort=True):
        high = z.loc[z.is_high, value].dropna()
        low = z.loc[z.is_low, value].dropna()
        if len(high) and len(low):
            rows.append({"trade_date": date, "high_n": len(high), "low_n": len(low),
                         "high_mean": high.mean(), "low_mean": low.mean(),
                         "spread": high.mean() - low.mean(),
                         "tail_overlap_n": int(z.tail_overlap.sum())})
    return pd.DataFrame(rows)


def hac_mean(spreads: Iterable[float], horizon: int) -> dict:
    """Bartlett Newey-West intercept covariance; asymptotic normal inference.

    No small-sample multiplier. This explicit convention is reviewable and is
    not a directional/disposition gate or a canonical scientific decision.
    """
    if horizon not in HORIZONS:
        raise ValueError("unfrozen horizon")
    x = np.asarray(list(spreads), dtype=float)
    lag = horizon - 1
    if not np.isfinite(x).all() or len(x) <= lag + 1:
        raise ValueError("insufficient or nonfinite date observations")
    n = len(x)
    mean = float(x.mean())
    u = x - mean
    meat = float(u @ u)
    for k in range(1, lag + 1):
        meat += 2 * (1 - k / (lag + 1)) * float(u[k:] @ u[:-k])
    variance = max(meat / (n * n), 0.0)
    se = math.sqrt(variance)
    t = mean / se if se else float("nan")
    p = math.erfc(abs(t) / math.sqrt(2)) if se else float("nan")
    z95 = 1.959963984540054
    return {"eligible_dates": n, "mean_spread": mean, "median_spread": float(np.median(x)),
            "hac_lag": lag, "hac_se": se, "hac_t": t, "p_raw": p,
            "ci95_low": mean - z95 * se, "ci95_high": mean + z95 * se}


def bh_adjust(pvalues: Mapping, primary_family: Iterable) -> dict:
    """Require an explicit family; retain unavailable tests in its denominator."""
    family = tuple(primary_family)
    if not family or len(family) != len(set(family)) or set(pvalues) != set(family):
        raise ValueError("explicit primary family must match tests exactly")
    for p in pvalues.values():
        if np.isfinite(p) and not 0 <= p <= 1:
            raise ValueError("invalid p-value")
    ordered = sorted(family, key=lambda key: pvalues[key] if np.isfinite(pvalues[key]) else 1.0)
    adjusted = {}
    running = 1.0
    for rank in range(len(ordered), 0, -1):
        key = ordered[rank - 1]
        p = pvalues[key] if np.isfinite(pvalues[key]) else 1.0
        running = min(running, p * len(ordered) / rank)
        adjusted[key] = running if np.isfinite(pvalues[key]) else float("nan")
    return adjusted


def require_scientific_contract(contract: Mapping) -> None:
    """Fail closed rather than derive hypotheses from B1/B2 outcomes."""
    missing = [key for key in ("primary_hypothesis_family", "hypothesized_directions", "disposition_rules")
               if not contract.get(key)]
    if missing:
        raise ValueError("canonical scientific contract required: " + ", ".join(missing))
