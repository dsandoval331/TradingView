from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json

import pandas as pd

from tr_platform.historical.certified_dataset import load_certified_partition
from tr_platform.universe.pmpd_universe import load_validated_universe

from .alpha import run_symbol_alpha
from .certification import _normalize_vector_columns
from .quality import build_session_quality_layer, enrich_by_session_quality, QUALITY_VERSION

PROTOCOL_ID = "PMPD_V5_9H_FACTOR_PROTOCOL_V1"
DATASET_VERSION = "PMPD_V5_9H_RESEARCH_DATASET_V1"

DISCOVERY_END = pd.Timestamp("2025-04-30")
VALIDATION_A_START = pd.Timestamp("2025-05-01")
VALIDATION_A_END = pd.Timestamp("2025-08-29")
VALIDATION_B_START = pd.Timestamp("2025-09-02")


def _split_for_date(value) -> str:
    d = pd.Timestamp(value).normalize()
    if d <= DISCOVERY_END:
        return "DISCOVERY"
    if VALIDATION_A_START <= d <= VALIDATION_A_END:
        return "VALIDATION_A"
    if d >= VALIDATION_B_START:
        return "VALIDATION_B"
    return "BOUNDARY_NONTRADING"


def _stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _frame_fingerprint(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return sha256(b"[]").hexdigest()
    use = [c for c in cols if c in df.columns]
    x = df[use].copy().fillna("<NA>").astype(str)
    rows = x.to_dict("records")
    return sha256(_stable_json(rows).encode("utf-8")).hexdigest()


def _parse_trade_date_from_event_id(event_id: str) -> str:
    parts = str(event_id).split("_")
    if len(parts) < 4:
        raise ValueError(f"Cannot parse trade_date from event_id={event_id!r}")
    return parts[1]


def build_symbol_research_dataset(
    bars: pd.DataFrame,
    *,
    symbol: str,
) -> dict[str, pd.DataFrame]:
    outputs = run_symbol_alpha(bars, symbol=symbol)

    levels = outputs["session_levels"].copy()
    if not levels.empty:
        levels["symbol"] = symbol
        if "pm_last_close" in levels.columns and "prior_rth_close" in levels.columns:
            denom = pd.to_numeric(levels["prior_rth_close"], errors="coerce")
            numer = pd.to_numeric(levels["pm_last_close"], errors="coerce")
            levels["overnight_gap_pct"] = (numer / denom - 1.0) * 100.0
            levels["price_scale_ratio"] = numer / denom
    quality = build_session_quality_layer(levels)

    geometry = outputs["geometry"].copy()
    if not geometry.empty:
        geometry["symbol"] = symbol
        geometry = enrich_by_session_quality(geometry, quality)

    events = outputs["events"].copy()
    if not events.empty:
        events["symbol"] = symbol
        events = enrich_by_session_quality(events, quality)

    decisions = _normalize_vector_columns(outputs["decision_points"])
    outcomes = outputs["outcomes"].copy()
    if decisions.empty:
        return {
            "session_quality": quality,
            "geometry": geometry,
            "events": events,
            "decision_research": pd.DataFrame(),
        }

    decisions["symbol"] = symbol
    decisions["trade_date"] = decisions["event_id"].map(_parse_trade_date_from_event_id)
    decisions["trade_date"] = pd.to_datetime(decisions["trade_date"], errors="raise").dt.strftime("%Y-%m-%d")

    # Primary 9H unit: first occurrence of each decision type within parent event.
    decisions = decisions.sort_values(["event_id", "decision_type", "decision_sequence"])
    decisions["decision_occurrence"] = decisions.groupby(["event_id", "decision_type"]).cumcount() + 1
    decisions["primary_decision_unit"] = decisions["decision_occurrence"].eq(1)

    # Outcomes are keyed by decision_id; Alpha evaluates strictly after the completed DP bar.
    merged = decisions.merge(
        outcomes,
        on=["decision_id", "event_id", "decision_sequence"],
        how="left",
        validate="one_to_one",
        suffixes=("", "_outcome"),
    )

    # Attach event and geometry context that is structurally known for the day/event.
    if not events.empty:
        event_cols = [
            "event_id", "stack_width_pct", "identity_order_inner_to_outer",
            "pm_level", "ah_level", "pd_level",
        ]
        merged = merged.merge(
            events[[c for c in event_cols if c in events.columns]],
            on="event_id",
            how="left",
            validate="many_to_one",
            suffixes=("", "_event"),
        )

    if not geometry.empty:
        geom_cols = [
            "symbol", "trade_date", "direction",
            "inner_level_name", "middle_level_name", "outer_level_name",
            "pm_ah_abs_pct", "pm_pd_abs_pct", "ah_pd_abs_pct",
            "stack_width_abs", "stack_width_pct",
            "pm_bar_count", "prior_ah_bar_count", "prior_rth_bar_count",
            "pm_observability_tier", "ah_observability_tier", "rth_observability_tier",
            "sparse_extended_hours_flag", "six_level_scale_ratio",
            "overnight_gap_pct", "price_scale_ratio", "price_continuity_tier",
            "price_scale_severe_flag", "price_scale_review_flag",
            "structural_eligible", "primary_inference_eligible",
            "sensitivity_review_required", "eligibility_reason", "quality_version",
        ]
        g = geometry[[c for c in geom_cols if c in geometry.columns]].copy()
        g["trade_date"] = pd.to_datetime(g["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        merged = merged.merge(
            g,
            on=["symbol", "trade_date", "direction"],
            how="left",
            validate="many_to_one",
            suffixes=("", "_geometry"),
        )

    merged["split"] = merged["trade_date"].map(_split_for_date)
    merged["resolved_primary"] = merged["outcome"].isin(["FAVORABLE_FIRST", "ADVERSE_FIRST"])
    merged["favorable_first"] = merged["outcome"].eq("FAVORABLE_FIRST").where(merged["resolved_primary"])
    merged["protocol_id"] = PROTOCOL_ID
    merged["dataset_version"] = DATASET_VERSION
    if "quality_version" not in merged.columns:
        merged["quality_version"] = QUALITY_VERSION

    # No future-event summary fields such as final max_levels_cleared or final attempt_count
    # are injected into the predictor table. Those would leak information at early DPs.
    return {
        "session_quality": quality,
        "geometry": geometry,
        "events": events,
        "decision_research": merged,
    }


def run_full_universe_research_dataset(
    *,
    repo_root: Path,
    year: int = 2025,
    verify_hash: bool = True,
) -> tuple[dict[str, pd.DataFrame], dict]:
    repo_root = Path(repo_root).resolve()
    members = load_validated_universe(repo_root)

    parts = {"session_quality": [], "geometry": [], "events": [], "decision_research": []}
    symbol_rows = []

    for i, member in enumerate(members, start=1):
        symbol = member.symbol
        print(f"[{i:03d}/{len(members):03d}] {symbol}", flush=True)
        partition = load_certified_partition(
            symbol=symbol,
            year=year,
            repo_root=repo_root,
            verify_hash=verify_hash,
        )
        result = build_symbol_research_dataset(partition.dataframe.copy(), symbol=symbol)
        for name, df in result.items():
            if not df.empty:
                parts[name].append(df)
        dr = result["decision_research"]
        symbol_rows.append({
            "symbol": symbol,
            "decision_rows": int(len(dr)),
            "primary_decision_rows": int(dr.get("primary_decision_unit", pd.Series(dtype=bool)).fillna(False).sum()) if not dr.empty else 0,
            "primary_eligible_rows": int((dr.get("primary_decision_unit", False) & dr.get("primary_inference_eligible", False)).sum()) if not dr.empty else 0,
            "resolved_primary_rows": int((dr.get("primary_decision_unit", False) & dr.get("primary_inference_eligible", False) & dr.get("resolved_primary", False)).sum()) if not dr.empty else 0,
        })

    combined = {
        name: (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame())
        for name, frames in parts.items()
    }
    combined["symbol_summary"] = pd.DataFrame(symbol_rows)

    dr = combined["decision_research"]
    payload = {
        "protocol_id": PROTOCOL_ID,
        "dataset_version": DATASET_VERSION,
        "quality_version": QUALITY_VERSION,
        "year": year,
        "symbol_count": len(members),
        "decision_rows": int(len(dr)),
        "primary_decision_rows": int(dr["primary_decision_unit"].sum()) if not dr.empty else 0,
        "primary_inference_eligible_rows": int((dr["primary_decision_unit"] & dr["primary_inference_eligible"]).sum()) if not dr.empty else 0,
        "resolved_primary_rows": int((dr["primary_decision_unit"] & dr["primary_inference_eligible"] & dr["resolved_primary"]).sum()) if not dr.empty else 0,
        "split_counts": dr.loc[dr["primary_decision_unit"], "split"].value_counts().to_dict() if not dr.empty else {},
    }
    payload["decision_fingerprint"] = _frame_fingerprint(
        dr,
        [
            "decision_id", "event_id", "decision_type", "timestamp_utc", "direction",
            "reference_price", "outcome", "mfe_pct", "mae_pct",
            "primary_decision_unit", "primary_inference_eligible", "split",
        ],
    )
    payload["run_fingerprint"] = sha256(_stable_json(payload).encode("utf-8")).hexdigest()
    return combined, payload
