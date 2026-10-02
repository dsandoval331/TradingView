"""Frozen S2-B2 causal validation; mechanical dispositions, no promotion."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid

import numpy as np
import pandas as pd

from tr_platform.research.swing10_s2_b2_core import (
    PROTOCOL, HORIZONS, FACTOR_COLUMNS, causal_factors, date_tails,
    forward_returns, chronological_blocks, date_spreads, hac_mean, bh_adjust, volume_turnover,
)

SUPPLEMENT = "SW10_S2_B2_PROTOCOL_V1_SUPPLEMENT_1"
PRIMARY = ("RET_MOM", "SHORT_REV", "VOL_TURN_V2_CAUSAL", "HIGH52", "VOL_REGIME", "GAP_OVN")
DIRECTIONS = {f: (1 if f == "RET_MOM" else -1 if f == "SHORT_REV" else 0) for f in FACTOR_COLUMNS}
INPUT_SHA = "ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2"
INPUT_BYTES = 2411604
INPUT_PATH = f"governed_inputs/swing10/s2_b1/market_daily_history_2025-02-03_2026-08-27/{INPUT_SHA}.csv"
FILES = ("factor_causal_summary.csv", "factor_date_spreads.csv", "factor_temporal_stability.csv",
         "factor_symbol_concentration.csv", "factor_semantic_audit.csv", "factor_b2_dispositions.csv",
         "sw10_s2_b2_manifest.json")


def disposition(rows: list[dict], *, semantic_valid: bool, testable: bool, direction: int) -> str:
    """Literal priority/mapping from supplemental frozen decision."""
    if not semantic_valid or not testable:
        return "INVALID_SEMANTICS_NOT_TESTABLE"
    strong = any(r["required_sign_pass"] and r["fdr_support"] and r["neighbor_coherence"]
                 and r["material_support"] and r["temporal_support"] and r["symbol_support"] for r in rows)
    if direction and strong:
        return "ADVANCE_TO_S2_ROBUSTNESS"
    weak = (any(r["required_sign_pass"] and (r["fdr_support"] or r["material_support"]) for r in rows)
            if direction else strong)
    return "RETAIN_AS_WEAK_EVIDENCE" if weak else "RETAIN_AS_COUNTEREVIDENCE"


def temporal_stats(spreads: pd.DataFrame, blocks: dict, sign: int) -> tuple[list[dict], dict]:
    rows = []
    for block in range(1, 5):
        x = spreads.loc[spreads.trade_date.map(blocks) == block, "spread"]
        rows.append({"block": block, "eligible_dates": len(x), "mean_spread": x.mean(),
                     "median_spread": x.median(), "aggregate_date_effect": x.sum(),
                     "required_sign_pass": bool(len(x) and sign and np.sign(x.mean()) == sign)})
    total_abs = sum(abs(r["aggregate_date_effect"]) for r in rows)
    for r in rows:
        r["absolute_aggregate_effect_share"] = abs(r["aggregate_date_effect"]) / total_abs if total_abs else np.nan
    max_share = max((r["absolute_aggregate_effect_share"] for r in rows), default=np.nan)
    count = sum(r["required_sign_pass"] for r in rows)
    return rows, {"directional_blocks": count, "max_block_abs_effect_share": max_share,
                  "temporal_support": bool(sign and count >= 3 and max_share <= .5)}


def concentration_stats(joined: pd.DataFrame, horizon: int, sign: int) -> tuple[list[dict], dict]:
    """Additive symbol contributions to mean date-spread; frozen original tails.

    Rank absolute contributions, deterministically break ties by symbol. The
    exclusion diagnostic recomputes tail means without reclassifying thresholds.
    """
    value = f"forward_{horizon}"
    z = joined[np.isfinite(joined[value])].copy()
    counts = z.groupby("trade_date")[["is_high", "is_low"]].sum()
    valid_dates = counts[(counts.is_high > 0) & (counts.is_low > 0)].index
    z = z[z.trade_date.isin(valid_dates)].copy()
    hn = z.trade_date.map(counts.is_high)
    ln = z.trade_date.map(counts.is_low)
    z["contribution"] = z[value] * (z.is_high.astype(int) / hn - z.is_low.astype(int) / ln)
    c = z.groupby("symbol").contribution.sum() / len(valid_dates)
    ranked = sorted(c.index, key=lambda s: (-abs(c[s]), s))
    denominator = c.abs().sum()
    top = {n: sum(abs(c[s]) for s in ranked[:n]) / denominator if denominator else np.nan for n in (1, 5, 10)}
    removed = set(ranked[:5])
    left = z[~z.symbol.isin(removed)]
    dates = []
    for _, g in left.groupby("trade_date"):
        hi, lo = g.loc[g.is_high, value], g.loc[g.is_low, value]
        if len(hi) and len(lo):
            dates.append(hi.mean() - lo.mean())
    mean = float(np.mean(dates)) if dates else np.nan
    # Zero is not a sign reversal; an unavailable diagnostic fails closed.
    support = bool(sign and np.isfinite(mean) and mean * sign >= 0)
    rows = [{"symbol": s, "absolute_contribution_rank": i + 1, "mean_spread_contribution": c[s],
             "absolute_contribution_share": abs(c[s]) / denominator if denominator else np.nan,
             "excluded_in_leave_top5": s in removed} for i, s in enumerate(ranked)]
    return rows, {**{f"top{n}_signed_mean_contribution": sum(c[x] for x in ranked[:n]) for n in (1, 5, 10)},
                  "top1_abs_contribution_share": top[1], "top5_abs_contribution_share": top[5],
                  "top10_abs_contribution_share": top[10], "leave_top5_out_mean_spread": mean,
                  "leave_top5_out_eligible_dates": len(dates), "symbol_support": support}


def tail_distribution(joined: pd.DataFrame, h: int) -> dict:
    value = f"forward_{h}"
    result = {}
    for label, mask in (("high", joined.is_high), ("low", joined.is_low)):
        x = joined.loc[mask, value].dropna()
        result.update({f"{label}_observations": len(x), f"{label}_raw_mean_return": x.mean(),
                       f"{label}_raw_median_return": x.median(), f"{label}_return_dispersion_sd": x.std(ddof=1),
                       f"{label}_positive_return_fraction": (x > 0).mean(),
                       f"{label}_downside_q05": x.quantile(.05), f"{label}_downside_q25": x.quantile(.25),
                       f"{label}_negative_return_fraction": (x < 0).mean(),
                       f"{label}_negative_return_mean": x[x < 0].mean()})
    result["high_low_dispersion_ratio"] = result["high_return_dispersion_sd"] / result["low_return_dispersion_sd"] if result["low_return_dispersion_sd"] > 0 else np.nan
    result["positive_return_differential"] = result["high_positive_return_fraction"] - result["low_positive_return_fraction"]
    result["eligible_observations"] = int(joined.loc[(joined.is_high | joined.is_low) & joined[value].notna()].shape[0])
    return result


def semantic_fixtures() -> dict:
    checks = {}
    for current, expected in ((100, 1), (200, 2), (50, .5)):
        value = volume_turnover(pd.Series([100.]*20 + [current, 999.]))
        checks[f"prior100_current{current}"] = bool(value.VOL_TURN_V2_CAUSAL.iloc[20] == expected)
    original = pd.Series([100.]*20 + [200., 999.])
    z = volume_turnover(original)
    future = original.copy(); future.iloc[21] = 999999.
    changed = original.copy(); changed.iloc[20] = 50.
    checks["future_invariance"] = bool(z.VOL_TURN_V2_CAUSAL.iloc[20] == volume_turnover(future).VOL_TURN_V2_CAUSAL.iloc[20])
    checks["current_excluded_denominator"] = bool(z.prior20_mean.iloc[20] == volume_turnover(changed).prior20_mean.iloc[20])
    checks["fewer20_ineligible"] = bool(volume_turnover(pd.Series([100.]*20)).VOL_TURN_V2_CAUSAL.iloc[-1:].isna().all())
    checks["zero_denominator_ineligible"] = bool(volume_turnover(pd.Series([0.]*20+[100.])).VOL_TURN_V2_CAUSAL.iloc[-1:].isna().all())
    if not all(checks.values()):
        raise RuntimeError("causal volume semantic fixture failed")
    return checks


def analyze(panel: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict]:
    fixture_results = semantic_fixtures()
    factors = causal_factors(panel)
    tails = {f: date_tails(factors, f) for f in FACTOR_COLUMNS}
    # Define all block memberships BEFORE forward outcomes are computed/read.
    blocks = {f: chronological_blocks(z.trade_date) for f, z in tails.items()}
    block_definitions = {f: [{"block": b, "start": str(min(d for d, n in mapping.items() if n == b).date()),
                              "end": str(max(d for d, n in mapping.items() if n == b).date()),
                              "input_eligible_dates": sum(n == b for n in mapping.values())}
                             for b in range(1, 5)] for f, mapping in blocks.items()}
    outcomes = forward_returns(factors)
    summaries, date_rows, temporal_rows, symbol_rows, semantic_rows = [], [], [], [], []
    for f, tail in tails.items():
        joined = tail.merge(outcomes, on=["symbol", "trade_date"], validate="one_to_one")
        legacy = f == "VOL_TURN_B1_LEGACY"
        semantic_valid = not legacy  # Legacy fails intended volume-ratio semantics; reproduce diagnostically.
        semantic_rows.append({"factor": f, "semantic_valid": semantic_valid, "testable": True,
                              "role": "PRIMARY" if f in PRIMARY else "DIAGNOSTIC_ONLY",
                              "definition": "volume_t / prior20_completed_mean" if f == "VOL_TURN_V2_CAUSAL" else
                                            "exact_B1_volume_expression_equals_prior20_mean_when_volume_nonzero" if legacy else "unchanged_B1_formula",
                              "no_future_factor_or_threshold_information": True,
                              "eligible_factor_observations": len(tail),
                              "tail_overlap_observations": int(tail.tail_overlap.sum()),
                              "causal_volume_fixture_results": json.dumps(fixture_results, sort_keys=True),
                              "semantic_note": "preserved B1 legacy; invalid as intended turnover ratio" if legacy else "causal construction; no imputation"})
        for h in HORIZONS:
            ds = date_spreads(tail, outcomes, h)
            if len(ds) <= h:
                raise ValueError(f"insufficient testable date series: {f}/{h}")
            stats = hac_mean(ds.spread, h)
            sd = ds.spread.std(ddof=1)
            effect = stats["mean_spread"] / sd if sd > 0 else np.nan
            observed_sign = int(np.sign(stats["mean_spread"]))
            sign = DIRECTIONS[f] or observed_sign
            tr, ts = temporal_stats(ds, blocks[f], sign)
            sr, ss = concentration_stats(joined, h, sign)
            ds = ds.assign(factor=f, horizon_days=h, temporal_block=ds.trade_date.map(blocks[f]))
            date_rows.extend(ds.to_dict("records"))
            temporal_rows.extend({**r, "factor": f, "horizon_days": h} for r in tr)
            symbol_rows.extend({**r, "factor": f, "horizon_days": h} for r in sr)
            summaries.append({"factor": f, "horizon_days": h, **stats, **tail_distribution(joined, h), **ts, **ss,
                              "standardized_effect": effect, "spread_sample_sd": sd,
                              "direction": "POSITIVE_HIGH_MINUS_LOW" if DIRECTIONS[f] == 1 else
                                           "NEGATIVE_HIGH_MINUS_LOW" if DIRECTIONS[f] == -1 else "NON_DIRECTIONAL",
                              "observed_sign_descriptive": observed_sign,
                              "fraction_dates_hypothesized_direction": (ds.spread * DIRECTIONS[f] > 0).mean() if DIRECTIONS[f] else np.nan,
                              "fraction_dates_observed_direction_descriptive": (ds.spread * observed_sign > 0).mean(),
                              "required_sign_pass": bool(sign and observed_sign == sign),
                              "material_support": bool(abs(effect) >= .20),
                              "semantic_valid": semantic_valid, "testable": True,
                              "primary_bh_member": f in PRIMARY, "long_short_independent_evidence": False})
    family = [(f, h) for f in PRIMARY for h in HORIZONS]
    raw = {(r["factor"], r["horizon_days"]): r["p_raw"] for r in summaries if r["primary_bh_member"]}
    adjusted = bh_adjust(raw, family)
    for r in summaries:
        r["p_fdr"] = adjusted.get((r["factor"], r["horizon_days"]), np.nan)
        r["fdr_support"] = bool(r["p_fdr"] <= .05)
        idx = HORIZONS.index(r["horizon_days"])
        neighbors = [HORIZONS[i] for i in (idx-1, idx+1) if 0 <= i < len(HORIZONS)]
        neighbor_means = [z["mean_spread"] for z in summaries if z["factor"] == r["factor"] and z["horizon_days"] in neighbors]
        sign = DIRECTIONS[r["factor"]] or r["observed_sign_descriptive"]
        r["neighbor_coherence"] = bool(r["required_sign_pass"] and any(x * sign > 0 for x in neighbor_means))
    dispositions = []
    for f in FACTOR_COLUMNS:
        rows = [r for r in summaries if r["factor"] == f]
        d = disposition(rows, semantic_valid=rows[0]["semantic_valid"], testable=all(r["testable"] for r in rows), direction=DIRECTIONS[f])
        dispositions.append({"factor": f, "mechanical_disposition": d,
                             "canonical_promotion_decision": False, "direction": rows[0]["direction"],
                             "primary_bh_member": f in PRIMARY, "semantic_valid": rows[0]["semantic_valid"],
                             "qualifying_horizons": ";".join(str(r["horizon_days"]) for r in rows if all(r[k] for k in
                                 ("required_sign_pass", "fdr_support", "neighbor_coherence", "material_support", "temporal_support", "symbol_support")))})
        for r in rows:
            r["mechanical_disposition"] = d
    return {FILES[0]: pd.DataFrame(summaries), FILES[1]: pd.DataFrame(date_rows),
            FILES[2]: pd.DataFrame(temporal_rows), FILES[3]: pd.DataFrame(symbol_rows),
            FILES[4]: pd.DataFrame(semantic_rows), FILES[5]: pd.DataFrame(dispositions)}, block_definitions


def verify_input(path: Path) -> tuple[pd.DataFrame, dict]:
    b = path.read_bytes()
    if len(b) != INPUT_BYTES or hashlib.sha256(b).hexdigest() != INPUT_SHA:
        raise ValueError("frozen immutable panel bytes/SHA mismatch")
    panel = pd.read_csv(path, parse_dates=["trade_date"])
    coverage = {"rows": len(panel), "symbols": panel.symbol.nunique(), "dates": panel.trade_date.nunique(),
                "date_start": str(panel.trade_date.min().date()), "date_end": str(panel.trade_date.max().date())}
    if coverage != {"rows": 44128, "symbols": 112, "dates": 394, "date_start": "2025-02-03", "date_end": "2026-08-27"}:
        raise ValueError("frozen universe/date coverage mismatch")
    if not (panel.groupby("symbol").size() == 394).all() or panel.duplicated(["symbol", "trade_date"]).any():
        raise ValueError("unbalanced or duplicate panel")
    if panel.isna().any().any() or not np.isfinite(panel[["open", "high", "low", "close", "volume"]]).all().all():
        raise ValueError("null/nonfinite panel")
    invalid = (panel.low > panel.high) | (panel.high < panel[["open", "close"]].max(axis=1)) | (panel.low > panel[["open", "close"]].min(axis=1)) | (panel[["open", "high", "low", "close"]] <= 0).any(axis=1) | (panel.volume < 0)
    if invalid.any():
        raise ValueError("invalid OHLCV")
    return panel, coverage


def write_outputs(tables: dict, blocks: dict, out: Path, provenance: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    identities = {name: str(uuid.uuid4()) for name in FILES}
    artifacts = []
    for name, frame in tables.items():
        path = out / name
        frame.to_csv(path, index=False, float_format="%.17g", lineterminator="\n")
        b = path.read_bytes()
        artifacts.append({"artifact_id": identities[name], "name": name, "sha256": hashlib.sha256(b).hexdigest(),
                          "size_bytes": len(b), "object_path": f"artifacts/{provenance['job_id']}/{provenance['attempt_id']}/{name}"})
    manifest = {"protocol": PROTOCOL, "supplement": SUPPLEMENT,
                "protocol_decision_id": "d7b1e65f-28c6-4f13-b3fb-e77fbbd8afbe",
                "supplemental_decision_id": "cccfd976-1933-4d53-be9e-17b15377414e",
                "parent_b1": {"job_id": "b355eadf-8cd3-417b-9508-b0d952e858ab", "attempt_id": "20cc4057-1190-48c3-80a7-2c2ea12f9939", "run_id": "36944181647", "research_sha": "af73dad08c7edf4b5733a55d61aba0ea5d0cbf66", "infrastructure_sha": "dd3926a0033ccfd7b9134d7dcdcb2e9c581355bf"},
                "execution": provenance, "input": {"dataset_identity": "market_daily_history_2025-02-03_2026-08-27", "sha256": INPUT_SHA, "size_bytes": INPUT_BYTES, "object_path": INPUT_PATH, "adjusted": True, "source": "B1 certified immutable canonical daily snapshot"},
                "factor_version_registry": {f: {"direction": DIRECTIONS[f], "primary": f in PRIMARY} for f in FACTOR_COLUMNS},
                "tail_rule": {"high": ">=date_cross_sectional_q80", "low": "<=date_cross_sectional_q20", "quantile_interpolation": "linear", "ties": "inclusive; overlap reported", "classification_before_outcomes": True},
                "horizons": HORIZONS, "max_holding_days": 10,
                "hac": {"kernel": "Bartlett", "lag": "horizon-1", "two_sided": True, "ci": .95, "small_sample_correction": False, "reference_distribution": "asymptotic_normal"},
                "fdr": {"method": "Benjamini-Hochberg", "q": .05, "tests": 36, "members": PRIMARY, "horizons": HORIZONS},
                "standardized_effect": {"formula": "mean(date_spread)/sample_sd(date_spread)", "ddof": 1, "abs_support_threshold": .20},
                "temporal_blocks": blocks, "temporal_share_definition": "abs(block_sum)/sum(abs(each_block_sum)); blocks fixed using factor-input-eligible dates before outcomes",
                "concentration": {"ranking": "absolute additive symbol contribution to mean date spread", "ties": "symbol ascending", "top": [1, 5, 10], "leave_top5": "fixed original tails; recompute surviving tail means; no sign reversal"},
                "artifacts": artifacts, "manifest_identity": {"artifact_id": identities[FILES[6]], "name": FILES[6], "sha256_and_size": "external durable registration/readback; self-hash excluded to avoid recursive hash"},
                "protected_data_access": False, "canonical_promotion_decision": False,
                "compute_cost": {"executor": "github_actions", "runner": "ubuntu-latest", "policy": "ZERO_INCREMENTAL_COST_FIRST", "paid_compute_selected": False, "incremental_billing_verified": False}}
    (out / FILES[6]).write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return identities


def run(work_root: Path) -> dict:
    context = json.loads((work_root / "job_inputs" / "swing10" / "execution_context.json").read_text())
    panel, coverage = verify_input(work_root / "job_inputs" / "swing10" / "market_daily_history.csv")
    tables, blocks = analyze(panel)
    out = work_root / "research_outputs" / "swing10" / "s2_b2"
    identities = write_outputs(tables, blocks, out, {**context, "coverage": coverage})
    paths = [str((out / name).relative_to(work_root)) for name in FILES]
    return {"status": "PASS", "artifact": paths[0], "output_paths": paths,
            "output_artifact_ids": {path: identities[name] for path, name in zip(paths, FILES)}}
