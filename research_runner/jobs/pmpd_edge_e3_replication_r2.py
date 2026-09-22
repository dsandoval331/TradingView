from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from tr_platform.pmpd_v5.alpha import run_symbol_alpha
from tr_platform.pmpd_v5.certification import _normalize_vector_columns
from tr_platform.pmpd_v5.quality import build_session_quality_layer, enrich_by_session_quality, QUALITY_VERSION
from tr_platform.universe.pmpd_universe import load_validated_universe

DATASET = "PMPD-EDGE-E3-REPLICATION-2025-HOLDOUT-V1"
PROTOCOL = "PMPD_EDGE_E3_TRADE_HEALTH_PROTOCOL_V1"
V5_PROTOCOL = "PMPD_V5_9H_FACTOR_PROTOCOL_V1"
CANDIDATE = "PMPD_V5_CANDIDATE_DP4_UNSCORED_V1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _trade_date(event_id: str) -> str:
    parts = str(event_id).split("_")
    if len(parts) < 4:
        raise ValueError(f"cannot parse trade_date from event_id={event_id!r}")
    return pd.to_datetime(parts[1], errors="raise").strftime("%Y-%m-%d")


def run(root: Path) -> dict:
    """Outcome-blind reconciliation of E3-R1 DP4 rows to frozen V5 9H eligibility semantics."""
    r1 = root / "research_outputs" / "pmpd" / "edge" / "e3_2025_replication" / "r1" / "dp4_structural_population.parquet"
    if not r1.is_file():
        raise FileNotFoundError(r1)
    r1_df = pd.read_parquet(r1).copy()
    r1_df["timestamp_utc"] = pd.to_datetime(r1_df["timestamp_utc"], utc=True)

    out = root / "research_outputs" / "pmpd" / "edge" / "e3_2025_replication" / "r2"
    out.mkdir(parents=True, exist_ok=True)

    members = load_validated_universe(root)
    symbols = [m.symbol for m in members]
    if len(symbols) != 112:
        raise RuntimeError(f"expected 112 symbols, got {len(symbols)}")

    parts = []
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/112] E3_R2_ELIGIBILITY {symbol}")
        p = root / "market_cache" / "MARKET_CACHE_V1" / "1m" / symbol / "2025.parquet"
        bars = pd.read_parquet(p)
        alpha = run_symbol_alpha(bars, symbol=symbol)

        levels = alpha["session_levels"].copy()
        levels["symbol"] = symbol
        if "pm_last_close" in levels.columns and "prior_rth_close" in levels.columns:
            denom = pd.to_numeric(levels["prior_rth_close"], errors="coerce")
            numer = pd.to_numeric(levels["pm_last_close"], errors="coerce")
            levels["overnight_gap_pct"] = (numer / denom - 1.0) * 100.0
            levels["price_scale_ratio"] = numer / denom
        quality = build_session_quality_layer(levels)

        geometry = alpha["geometry"].copy()
        geometry["symbol"] = symbol
        geometry = enrich_by_session_quality(geometry, quality)

        decisions = _normalize_vector_columns(alpha["decision_points"])
        if decisions.empty:
            continue
        decisions["symbol"] = symbol
        decisions["trade_date"] = decisions["event_id"].map(_trade_date)
        decisions = decisions.sort_values(["event_id", "decision_type", "decision_sequence"])
        decisions["decision_occurrence"] = decisions.groupby(["event_id", "decision_type"]).cumcount() + 1
        decisions["primary_decision_unit"] = decisions["decision_occurrence"].eq(1)

        geom_cols = [
            "symbol","trade_date","direction","structural_eligible","primary_inference_eligible",
            "sensitivity_review_required","eligibility_reason","price_scale_severe_flag",
            "price_scale_review_flag","sparse_extended_hours_flag","quality_version",
        ]
        g = geometry[[c for c in geom_cols if c in geometry.columns]].copy()
        g["trade_date"] = pd.to_datetime(g["trade_date"], errors="raise").dt.strftime("%Y-%m-%d")
        decisions = decisions.merge(g, on=["symbol","trade_date","direction"], how="left", validate="many_to_one")
        parts.append(decisions.loc[decisions["decision_type"].eq("DP4_FULL_STACK_FIRST_CLEAR")].copy())

    v5 = pd.concat(parts, ignore_index=True)
    v5["timestamp_utc"] = pd.to_datetime(v5["timestamp_utc"], utc=True)

    # Exact structural parity to E3-R1 before eligibility is applied.
    key = ["symbol","event_id","decision_id","timestamp_utc","direction"]
    if any(c not in r1_df.columns for c in key):
        key = ["symbol","event_id","timestamp_utc","direction"]
    a = r1_df[key].drop_duplicates()
    b = v5[key].drop_duplicates()
    merged = a.merge(b, on=key, how="outer", indicator=True)
    r1_only = int((merged["_merge"] == "left_only").sum())
    v5_only = int((merged["_merge"] == "right_only").sum())

    primary = v5["primary_decision_unit"].fillna(False).astype(bool)
    eligible = v5["primary_inference_eligible"].fillna(False).astype(bool)
    frozen = v5.loc[primary & eligible].copy()

    # Frozen V5 semantics are structural/outcome-blind: first decision-type occurrence
    # per parent event + complete six levels + no severe price-scale discontinuity.
    if v5["primary_inference_eligible"].isna().any():
        raise RuntimeError("missing frozen V5 eligibility metadata on DP4 rows")
    if r1_only or v5_only or len(v5) != len(r1_df):
        raise RuntimeError(f"structural parity failed: r1_only={r1_only} v5_only={v5_only} r1={len(r1_df)} v5={len(v5)}")

    excluded = v5.loc[~(primary & eligible)].copy()
    reason_counts = {str(k): int(v) for k, v in excluded["eligibility_reason"].fillna("<NA>").value_counts().items()}
    manifest = {
        "step":"PMPD-EDGE-E3-R2",
        "purpose":"Outcome-blind reconciliation and freeze of 2025 DP4 population under frozen V5 primary-decision-unit / primary-inference-eligibility semantics.",
        "dataset_version":DATASET,
        "e3_protocol":PROTOCOL,
        "v5_protocol":V5_PROTOCOL,
        "candidate_reference":CANDIDATE,
        "quality_version":QUALITY_VERSION,
        "r1_structural_rows":int(len(r1_df)),
        "reconstructed_dp4_rows":int(len(v5)),
        "structural_parity":True,
        "r1_only_rows":r1_only,
        "v5_only_rows":v5_only,
        "primary_decision_rows":int(primary.sum()),
        "primary_inference_eligible_rows":int((primary & eligible).sum()),
        "excluded_rows":int((~(primary & eligible)).sum()),
        "excluded_reason_counts":reason_counts,
        "frozen_rows":int(len(frozen)),
        "frozen_symbols":int(frozen["symbol"].nunique()),
        "frozen_trade_dates":int(frozen["trade_date"].nunique()),
        "direction_counts":{str(k):int(v) for k,v in frozen["direction"].value_counts().items()},
        "primary_decision_semantics":"first occurrence of each decision_type within parent event, ordered by event_id/decision_type/decision_sequence",
        "primary_inference_semantics":"complete six session levels AND no severe price-scale discontinuity; review/sparse flags retained for sensitivity and are not primary exclusions",
        "outcomes_inspected":False,
        "trade_health_events_computed":False,
        "threshold_search_performed":False,
        "event_taxonomy_retuned":False,
        "v4_modified":False,
        "v5_modified":False,
        "production_rule_authorized":False,
    }

    frozen.to_parquet(out / "dp4_primary_inference_population.parquet", index=False)
    excluded.to_parquet(out / "dp4_excluded_population.parquet", index=False)
    pd.DataFrame([{"eligibility_reason":k,"rows":v} for k,v in reason_counts.items()]).to_csv(out / "exclusion_summary.csv", index=False)
    (out / "summary.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    paths=[out/"dp4_primary_inference_population.parquet",out/"dp4_excluded_population.parquet",out/"exclusion_summary.csv",out/"summary.json"]
    artifact_manifest={"dataset_version":DATASET,"artifacts":[{"path":str(p.relative_to(root)).replace("\\","/"),"size_bytes":p.stat().st_size,"sha256":_sha(p)} for p in paths]}
    (out/"artifact_manifest.json").write_text(json.dumps(artifact_manifest,indent=2),encoding="utf-8")
    paths.append(out/"artifact_manifest.json")

    print("PMPD_EDGE_E3_R2_SUMMARY="+json.dumps(manifest,sort_keys=True,default=str))
    return {"status":"PASS","output_paths":[str(p.relative_to(root)).replace("\\","/") for p in paths],"outcomes_inspected":False,"research_only":True}
