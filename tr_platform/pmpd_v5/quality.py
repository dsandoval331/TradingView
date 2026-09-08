from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

QUALITY_VERSION = "PMPD_V5_9H_QUALITY_V1"

LEVEL_COLUMNS = ["pmh", "pml", "ahh", "ahl", "pdh", "pdl"]
BULL_LEVEL_COLUMNS = ["pmh", "ahh", "pdh"]
BEAR_LEVEL_COLUMNS = ["pml", "ahl", "pdl"]


@dataclass(frozen=True)
class QualityThresholds:
    """Outcome-blind structural data-quality thresholds.

    These thresholds are *not* trading thresholds and are not selected from
    profitability. They exist only to isolate obvious data/price-scale breaks
    while retaining less-extreme observations for sensitivity analysis.
    """

    severe_six_scale_ratio: float = 1.50
    review_six_scale_ratio: float = 1.30
    severe_price_scale_low: float = 0.60
    severe_price_scale_high: float = 1.67
    review_price_scale_low: float = 0.75
    review_price_scale_high: float = 1.33
    severe_abs_overnight_gap_pct: float = 45.0
    review_abs_overnight_gap_pct: float = 20.0
    sparse_session_max_bars: int = 5
    thin_session_max_bars: int = 20
    moderate_session_max_bars: int = 60


DEFAULT_THRESHOLDS = QualityThresholds()


def _numeric(out: pd.DataFrame, columns: Iterable[str]) -> None:
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")


def _obs_tier(series: pd.Series, t: QualityThresholds) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    result = pd.Series(index=x.index, dtype="object")
    result.loc[x.isna()] = "MISSING"
    result.loc[x.notna() & (x <= t.sparse_session_max_bars)] = "SPARSE_1_5"
    result.loc[
        x.notna()
        & (x > t.sparse_session_max_bars)
        & (x <= t.thin_session_max_bars)
    ] = "THIN_6_20"
    result.loc[
        x.notna()
        & (x > t.thin_session_max_bars)
        & (x <= t.moderate_session_max_bars)
    ] = "MODERATE_21_60"
    result.loc[x.notna() & (x > t.moderate_session_max_bars)] = "DENSE_61_PLUS"
    return result


def _safe_ratio(max_values: pd.Series, min_values: pd.Series) -> pd.Series:
    denom = pd.to_numeric(min_values, errors="coerce")
    numer = pd.to_numeric(max_values, errors="coerce")
    return numer.where((denom > 0) & numer.notna()) / denom.where(denom > 0)


def build_session_quality_layer(
    session_levels: pd.DataFrame,
    thresholds: QualityThresholds = DEFAULT_THRESHOLDS,
) -> pd.DataFrame:
    """Create auditable, outcome-blind quality/eligibility metadata.

    Principles:
      * Preserve every raw session-level row.
      * Treat PM/AH observability as a continuous/context dimension, not a
        default exclusion.
      * Exclude only obvious severe price-scale discontinuities from primary
        inference; retain review-tier rows for sensitivity analysis.
      * Never use trade outcome to determine any quality flag.
    """
    out = session_levels.copy()

    required_identity = {"symbol", "trade_date"}
    missing_identity = sorted(required_identity - set(out.columns))
    if missing_identity:
        raise ValueError(f"Missing required identity columns: {missing_identity}")

    for col in LEVEL_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan

    _numeric(
        out,
        LEVEL_COLUMNS
        + [
            "pm_bar_count",
            "prior_ah_bar_count",
            "prior_rth_bar_count",
            "overnight_gap_pct",
            "price_scale_ratio",
        ],
    )

    if "has_complete_six_levels" in out.columns:
        complete = out["has_complete_six_levels"].fillna(False).astype(bool)
    else:
        complete = out[LEVEL_COLUMNS].notna().all(axis=1)
    out["has_complete_six_levels"] = complete

    six_max = out[LEVEL_COLUMNS].max(axis=1, skipna=False)
    six_min = out[LEVEL_COLUMNS].min(axis=1, skipna=False)
    bull_max = out[BULL_LEVEL_COLUMNS].max(axis=1, skipna=False)
    bull_min = out[BULL_LEVEL_COLUMNS].min(axis=1, skipna=False)
    bear_max = out[BEAR_LEVEL_COLUMNS].max(axis=1, skipna=False)
    bear_min = out[BEAR_LEVEL_COLUMNS].min(axis=1, skipna=False)

    out["six_level_scale_ratio"] = _safe_ratio(six_max, six_min)
    out["bull_stack_scale_ratio"] = _safe_ratio(bull_max, bull_min)
    out["bear_stack_scale_ratio"] = _safe_ratio(bear_max, bear_min)

    out["pm_observability_tier"] = _obs_tier(out.get("pm_bar_count"), thresholds)
    out["ah_observability_tier"] = _obs_tier(out.get("prior_ah_bar_count"), thresholds)
    out["rth_observability_tier"] = _obs_tier(out.get("prior_rth_bar_count"), thresholds)

    pm_sparse = pd.to_numeric(out.get("pm_bar_count"), errors="coerce") <= thresholds.sparse_session_max_bars
    ah_sparse = pd.to_numeric(out.get("prior_ah_bar_count"), errors="coerce") <= thresholds.sparse_session_max_bars
    out["sparse_extended_hours_flag"] = (pm_sparse.fillna(False) | ah_sparse.fillna(False)).astype(bool)

    scale_ratio = pd.to_numeric(out["six_level_scale_ratio"], errors="coerce")
    price_scale = pd.to_numeric(out.get("price_scale_ratio"), errors="coerce")
    gap = pd.to_numeric(out.get("overnight_gap_pct"), errors="coerce").abs()

    severe = (
        (scale_ratio >= thresholds.severe_six_scale_ratio)
        | (price_scale <= thresholds.severe_price_scale_low)
        | (price_scale >= thresholds.severe_price_scale_high)
        | (gap >= thresholds.severe_abs_overnight_gap_pct)
    )
    review = ~severe & (
        (scale_ratio >= thresholds.review_six_scale_ratio)
        | (price_scale <= thresholds.review_price_scale_low)
        | (price_scale >= thresholds.review_price_scale_high)
        | (gap >= thresholds.review_abs_overnight_gap_pct)
    )

    out["price_continuity_tier"] = np.select(
        [severe, review],
        ["SEVERE_DISCONTINUITY", "REVIEW_ANOMALY"],
        default="NORMAL",
    )
    out["price_scale_severe_flag"] = severe.astype(bool)
    out["price_scale_review_flag"] = review.astype(bool)

    out["raw_record_eligible"] = True
    out["structural_eligible"] = complete.astype(bool)
    out["primary_inference_eligible"] = (complete & ~severe).astype(bool)
    out["sensitivity_review_required"] = (review | out["sparse_extended_hours_flag"]).astype(bool)

    reasons = pd.Series("", index=out.index, dtype="object")
    reasons = reasons.mask(~complete, "INCOMPLETE_SIX_LEVELS")
    reasons = reasons.mask(
        complete & severe,
        "SEVERE_PRICE_SCALE_DISCONTINUITY",
    )
    reasons = reasons.mask(
        complete & ~severe & review,
        "PRICE_CONTINUITY_REVIEW",
    )
    reasons = reasons.mask(
        complete & ~severe & ~review & out["sparse_extended_hours_flag"],
        "SPARSE_EXTENDED_HOURS_SENSITIVITY",
    )
    reasons = reasons.mask(
        complete & ~severe & ~review & ~out["sparse_extended_hours_flag"],
        "PRIMARY_ELIGIBLE",
    )
    out["eligibility_reason"] = reasons
    out["quality_version"] = QUALITY_VERSION

    return out


def enrich_by_session_quality(
    frame: pd.DataFrame,
    quality: pd.DataFrame,
    *,
    date_column: str = "trade_date",
) -> pd.DataFrame:
    """Attach quality flags to event/geometry-style rows by symbol + trade_date."""
    required = {"symbol", date_column}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Frame missing join columns: {missing}")

    qcols = [
        "symbol",
        "trade_date",
        "pm_bar_count",
        "prior_ah_bar_count",
        "prior_rth_bar_count",
        "pm_observability_tier",
        "ah_observability_tier",
        "rth_observability_tier",
        "sparse_extended_hours_flag",
        "six_level_scale_ratio",
        "bull_stack_scale_ratio",
        "bear_stack_scale_ratio",
        "overnight_gap_pct",
        "price_scale_ratio",
        "price_continuity_tier",
        "price_scale_severe_flag",
        "price_scale_review_flag",
        "structural_eligible",
        "primary_inference_eligible",
        "sensitivity_review_required",
        "eligibility_reason",
        "quality_version",
    ]
    q = quality[[c for c in qcols if c in quality.columns]].copy()
    q["trade_date"] = pd.to_datetime(q["trade_date"], errors="coerce").dt.date.astype("string")

    x = frame.copy()
    x[date_column] = pd.to_datetime(x[date_column], errors="coerce").dt.date.astype("string")
    if date_column != "trade_date":
        q = q.rename(columns={"trade_date": date_column})

    return x.merge(q, on=["symbol", date_column], how="left", validate="many_to_one")


def quality_summary(quality: pd.DataFrame) -> dict:
    q = quality.copy()
    complete = q["has_complete_six_levels"].fillna(False).astype(bool)
    primary = q["primary_inference_eligible"].fillna(False).astype(bool)
    severe = q["price_scale_severe_flag"].fillna(False).astype(bool)
    review = q["price_scale_review_flag"].fillna(False).astype(bool)
    sparse = q["sparse_extended_hours_flag"].fillna(False).astype(bool)

    return {
        "quality_version": QUALITY_VERSION,
        "rows": int(len(q)),
        "complete_six_level_rows": int(complete.sum()),
        "primary_inference_eligible_rows": int(primary.sum()),
        "severe_price_scale_rows": int(severe.sum()),
        "review_price_continuity_rows": int(review.sum()),
        "sparse_extended_hours_rows": int(sparse.sum()),
        "pm_observability_tiers": {str(k): int(v) for k, v in q.loc[complete, "pm_observability_tier"].value_counts().items()},
        "ah_observability_tiers": {str(k): int(v) for k, v in q.loc[complete, "ah_observability_tier"].value_counts().items()},
    }
