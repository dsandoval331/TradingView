from __future__ import annotations

from dataclasses import dataclass
from math import erf, exp, log, sqrt
from pathlib import Path
import json

import numpy as np
import pandas as pd

PROTOCOL_ID = "PMPD_V5_9H_FACTOR_PROTOCOL_V1"
BATCH_ID = "PMPD_V5_9H_FACTOR_BATCH_1_GEOMETRY_QUALITY_V1"

PRIMARY_DECISION_TYPES = [
    "DP1_FIRST_CONTACT",
    "DP2_FIRST_LEVEL_CLEAR",
    "DP3_SECOND_LEVEL_CLEAR",
    "DP4_FULL_STACK_FIRST_CLEAR",
    "DP5_FIRST_COMPLETED_BAR_RETENTION",
]

CONTINUOUS_FACTORS = [
    "stack_width_pct",
    "pm_ah_abs_pct",
    "pm_pd_abs_pct",
    "ah_pd_abs_pct",
    "pm_bar_count",
    "prior_ah_bar_count",
    "prior_rth_bar_count",
    "six_level_scale_ratio",
    "attempt_number",
    "minutes_since_rth_open",
]

CATEGORICAL_FACTORS = [
    "inner_level_name",
    "middle_level_name",
    "outer_level_name",
    "identity_order_inner_to_outer",
    "pm_observability_tier",
    "ah_observability_tier",
    "sparse_extended_hours_flag",
    "price_scale_review_flag",
    "traded_vector_code",
    "close_vector_code",
]


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return center - half, center + half


def two_prop_pvalue(s1: int, n1: int, s2: int, n2: int) -> float:
    if min(n1, n2) <= 0:
        return float("nan")
    p = (s1 + s2) / (n1 + n2)
    se = sqrt(max(p * (1 - p) * (1 / n1 + 1 / n2), 0.0))
    if se == 0:
        return 1.0
    z = (s1 / n1 - s2 / n2) / se
    return 2.0 * (1.0 - _norm_cdf(abs(z)))


def bh_adjust(pvalues: pd.Series) -> pd.Series:
    x = pd.to_numeric(pvalues, errors="coerce")
    valid = x.dropna().sort_values()
    if valid.empty:
        return pd.Series(np.nan, index=x.index)
    m = len(valid)
    raw = pd.Series(index=valid.index, dtype=float)
    for rank, (idx, p) in enumerate(valid.items(), start=1):
        raw.loc[idx] = min(float(p) * m / rank, 1.0)
    # Enforce monotonicity from largest rank backward.
    ordered = raw.loc[valid.index].to_numpy()
    ordered = np.minimum.accumulate(ordered[::-1])[::-1]
    raw.loc[valid.index] = ordered
    out = pd.Series(np.nan, index=x.index, dtype=float)
    out.loc[raw.index] = raw
    return out


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    if "protocol_id" in x.columns:
        bad = x["protocol_id"].dropna().astype(str).ne(PROTOCOL_ID)
        if bad.any():
            raise ValueError("Input contains a protocol_id different from frozen 9H protocol")

    x = x.loc[
        x["primary_decision_unit"].fillna(False).astype(bool)
        & x["primary_inference_eligible"].fillna(False).astype(bool)
        & x["decision_type"].isin(PRIMARY_DECISION_TYPES)
    ].copy()

    x["resolved"] = x["outcome"].isin(["FAVORABLE_FIRST", "ADVERSE_FIRST"])
    x["y"] = np.where(x["outcome"].eq("FAVORABLE_FIRST"), 1,
                      np.where(x["outcome"].eq("ADVERSE_FIRST"), 0, np.nan))
    x["trade_date"] = pd.to_datetime(x["trade_date"], errors="coerce")
    ts = pd.to_datetime(x["timestamp_utc"], errors="coerce", utc=True).dt.tz_convert("America/New_York")
    x["minutes_since_rth_open"] = (ts.dt.hour * 60 + ts.dt.minute) - (9 * 60 + 30)
    return x


def _summary_row(g: pd.DataFrame) -> dict:
    resolved = g.loc[g["resolved"]].copy()
    n_resolved = len(resolved)
    successes = int((resolved["y"] == 1).sum())
    rate = successes / n_resolved if n_resolved else float("nan")
    lo, hi = wilson_interval(successes, n_resolved)
    return {
        "n_total": int(len(g)),
        "n_resolved": int(n_resolved),
        "n_favorable": successes,
        "favorable_first_rate": rate,
        "wilson95_low": lo,
        "wilson95_high": hi,
        "ambiguous_rate": float(g["outcome"].eq("AMBIGUOUS_SAME_BAR").mean()) if len(g) else float("nan"),
        "unresolved_rate": float(g["outcome"].eq("UNRESOLVED").mean()) if len(g) else float("nan"),
        "symbol_count": int(g["symbol"].nunique()),
        "trade_date_count": int(g["trade_date"].nunique()),
    }


def _quantile_edges(discovery: pd.Series) -> list[float]:
    s = pd.to_numeric(discovery, errors="coerce").dropna()
    if s.nunique() < 5:
        return []
    qs = s.quantile([0, .2, .4, .6, .8, 1.0]).to_numpy(dtype=float)
    # Make strictly increasing edges. Duplicate quantiles are removed; factors
    # with <3 resulting bins are skipped rather than outcome-tuned.
    edges = sorted(set(float(v) for v in qs if np.isfinite(v)))
    if len(edges) < 4:
        return []
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def analyze_continuous(x: pd.DataFrame, factor: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, contrasts = [], []
    if factor not in x.columns:
        return pd.DataFrame(), pd.DataFrame()

    for decision_type in PRIMARY_DECISION_TYPES:
        for direction in ["ALL", "BULL", "BEAR"]:
            base = x.loc[x["decision_type"].eq(decision_type)].copy()
            if direction != "ALL":
                base = base.loc[base["direction"].eq(direction)].copy()
            disc = base.loc[base["split"].eq("DISCOVERY")].copy()
            edges = _quantile_edges(disc[factor])
            if not edges:
                continue
            labels = [f"Q{i+1}" for i in range(len(edges)-1)]
            for split in ["DISCOVERY", "VALIDATION_A", "VALIDATION_B"]:
                z = base.loc[base["split"].eq(split)].copy()
                z["factor_bin"] = pd.cut(
                    pd.to_numeric(z[factor], errors="coerce"),
                    bins=edges,
                    labels=labels,
                    include_lowest=True,
                    duplicates="drop",
                )
                for bin_name, g in z.dropna(subset=["factor_bin"]).groupby("factor_bin", observed=True):
                    r = _summary_row(g)
                    r.update({
                        "batch_id": BATCH_ID,
                        "factor": factor,
                        "factor_type": "continuous",
                        "decision_type": decision_type,
                        "direction": direction,
                        "split": split,
                        "category": str(bin_name),
                        "discovery_edges_json": json.dumps(edges),
                    })
                    rows.append(r)

                low = z.loc[z["factor_bin"].astype(str).eq(labels[0]) & z["resolved"]]
                high = z.loc[z["factor_bin"].astype(str).eq(labels[-1]) & z["resolved"]]
                if len(low) and len(high):
                    sl = int((low["y"] == 1).sum()); sh = int((high["y"] == 1).sum())
                    nl=len(low); nh=len(high)
                    contrasts.append({
                        "batch_id":BATCH_ID,"factor":factor,"decision_type":decision_type,
                        "direction":direction,"split":split,"contrast":f"{labels[-1]}-{labels[0]}",
                        "risk_difference":sh/nh-sl/nl,"p_value":two_prop_pvalue(sh,nh,sl,nl),
                        "n_high":nh,"n_low":nl,"discovery_edges_json":json.dumps(edges),
                    })
    return pd.DataFrame(rows), pd.DataFrame(contrasts)


def analyze_categorical(x: pd.DataFrame, factor: str) -> pd.DataFrame:
    rows=[]
    if factor not in x.columns:
        return pd.DataFrame()
    for decision_type in PRIMARY_DECISION_TYPES:
        for direction in ["ALL","BULL","BEAR"]:
            base=x.loc[x["decision_type"].eq(decision_type)].copy()
            if direction!="ALL": base=base.loc[base["direction"].eq(direction)]
            # Categories are frozen from discovery presence, not outcome ranking.
            cats=sorted(base.loc[base["split"].eq("DISCOVERY"),factor].dropna().astype(str).unique())
            for split in ["DISCOVERY","VALIDATION_A","VALIDATION_B"]:
                z=base.loc[base["split"].eq(split)].copy()
                for cat in cats:
                    g=z.loc[z[factor].astype(str).eq(cat)]
                    if g.empty: continue
                    r=_summary_row(g)
                    r.update({"batch_id":BATCH_ID,"factor":factor,"factor_type":"categorical",
                              "decision_type":decision_type,"direction":direction,"split":split,
                              "category":cat,"discovery_edges_json":None})
                    rows.append(r)
    return pd.DataFrame(rows)


def run_batch1(df: pd.DataFrame) -> dict[str,pd.DataFrame]:
    x=_prepare(df)
    summaries=[]; contrasts=[]
    for factor in CONTINUOUS_FACTORS:
        s,c=analyze_continuous(x,factor)
        if not s.empty: summaries.append(s)
        if not c.empty: contrasts.append(c)
    for factor in CATEGORICAL_FACTORS:
        s=analyze_categorical(x,factor)
        if not s.empty: summaries.append(s)

    summary=pd.concat(summaries,ignore_index=True) if summaries else pd.DataFrame()
    contrast=pd.concat(contrasts,ignore_index=True) if contrasts else pd.DataFrame()
    if not contrast.empty:
        disc=contrast["split"].eq("DISCOVERY")
        contrast.loc[disc,"bh_fdr_q"] = (
            contrast.loc[disc]
            .groupby(["decision_type","direction"])["p_value"]
            .transform(bh_adjust)
        )
    return {"factor_summary":summary,"continuous_contrasts":contrast}
