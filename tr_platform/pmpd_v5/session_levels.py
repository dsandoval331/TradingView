from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = {
    "trade_date", "timestamp_et", "session", "high", "low", "close",
}


def _normalize_trade_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.tz_localize(None).dt.normalize()


def build_session_levels(bars: pd.DataFrame) -> pd.DataFrame:
    """Build current-PM and strictly-prior RTH/AH levels for each RTH trade date.

    Session semantics are inherited from MARKET_CACHE_V1:
      PRE = 04:00-09:29 ET
      RTH = 09:30-15:59 ET
      AH  = 16:00-19:59 ET

    The previous session is mapped by the ordered set of observed RTH trade dates,
    which naturally handles weekends and market holidays without calendar guessing.
    """
    missing = sorted(REQUIRED_COLUMNS - set(bars.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    x = bars.copy()
    x["trade_date"] = _normalize_trade_date(x["trade_date"])
    x["timestamp_et"] = pd.to_datetime(x["timestamp_et"], errors="coerce", utc=True).dt.tz_convert(
        "America/New_York"
    )
    x = x.dropna(subset=["trade_date", "timestamp_et"]).sort_values("timestamp_et")

    pre = (
        x.loc[x["session"].eq("PRE")]
        .groupby("trade_date", as_index=False)
        .agg(
            pmh=("high", "max"),
            pml=("low", "min"),
            pm_last_close=("close", "last"),
            pm_bar_count=("close", "size"),
            pm_first_bar=("timestamp_et", "min"),
            pm_last_bar=("timestamp_et", "max"),
        )
    )

    rth = (
        x.loc[x["session"].eq("RTH")]
        .groupby("trade_date", as_index=False)
        .agg(
            pdh=("high", "max"),
            pdl=("low", "min"),
            prior_rth_close=("close", "last"),
            prior_rth_bar_count=("close", "size"),
            rth_first_bar=("timestamp_et", "min"),
            rth_last_bar=("timestamp_et", "max"),
        )
        .sort_values("trade_date")
        .reset_index(drop=True)
    )

    ah = (
        x.loc[x["session"].eq("AH")]
        .groupby("trade_date", as_index=False)
        .agg(
            ahh=("high", "max"),
            ahl=("low", "min"),
            prior_ah_close=("close", "last"),
            prior_ah_bar_count=("close", "size"),
            ah_first_bar=("timestamp_et", "min"),
            ah_last_bar=("timestamp_et", "max"),
        )
    )

    completed = rth.merge(ah, on="trade_date", how="left", validate="one_to_one")
    completed = completed.rename(columns={"trade_date": "prior_session_date"})

    # Research dates are days with an observed RTH session.
    dates = rth[["trade_date"]].copy()
    dates["prior_session_date"] = dates["trade_date"].shift(1)

    out = dates.merge(pre, on="trade_date", how="left", validate="one_to_one")
    out = out.merge(completed, on="prior_session_date", how="left", validate="many_to_one")

    level_cols = ["pmh", "pml", "ahh", "ahl", "pdh", "pdl"]
    out["level_count_available"] = out[level_cols].notna().sum(axis=1)
    out["has_complete_six_levels"] = out[level_cols].notna().all(axis=1)
    return out.sort_values("trade_date").reset_index(drop=True)


def add_session_quality_metadata(levels: pd.DataFrame) -> pd.DataFrame:
    """Add non-judgmental session quality metadata.

    This does not exclude sparse sessions. It records raw observability so later
    research can decide whether sparse PM/AH formation matters.
    """
    out = levels.copy()
    # These columns may already exist depending on upstream implementation.
    defaults = {
        "pm_bar_count": pd.NA,
        "ah_bar_count": pd.NA,
        "rth_bar_count": pd.NA,
        "pm_first_bar": pd.NaT,
        "pm_last_bar": pd.NaT,
        "ah_first_bar": pd.NaT,
        "ah_last_bar": pd.NaT,
    }
    for col, default in defaults.items():
        if col not in out.columns:
            out[col] = default
    out["level_available"] = out.get("has_complete_six_levels", False)
    return out
