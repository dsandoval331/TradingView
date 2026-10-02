"""Outcome-free copies of certified B2 causal inputs; no research outcomes API.

Source research revision: b912f0c78d9593f2b8d866856217a389ce9baf68.
Only causal columns reach the preflight; legacy is reproduced internally solely
for source-function parity and is rejected from the candidate conditioning API.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

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
