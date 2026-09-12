from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

PROTOCOL = "PMPD_EDGE_E2_ACCEPTANCE_PROTOCOL_V1"
START = pd.Timestamp("2026-01-05").date()
END = pd.Timestamp("2026-09-02").date()
RTH_OPEN = pd.Timestamp("09:30").time()
RTH_LAST_MINUTE = pd.Timestamp("15:59").time()


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _find_col(columns, aliases):
    mapping = {_norm(c): c for c in columns}
    for a in aliases:
        if _norm(a) in mapping:
            return mapping[_norm(a)]
    return None


def _resolve_level_columns(df: pd.DataFrame) -> dict:
    cols = list(df.columns)
    aliases = {
        "pmh": ["pmh", "pm_high", "premarket_high", "pmh_price", "premarket_high_price"],
        "ahh": ["ahh", "ah_high", "afterhours_high", "after_hours_high", "ahh_price", "afterhours_high_price"],
        "pdh": ["pdh", "pd_high", "previous_day_high", "prior_day_high", "prev_day_high", "pdh_price"],
        "pml": ["pml", "pm_low", "premarket_low", "pml_price", "premarket_low_price"],
        "ahl": ["ahl", "ah_low", "afterhours_low", "after_hours_low", "ahl_price", "afterhours_low_price"],
        "pdl": ["pdl", "pd_low", "previous_day_low", "prior_day_low", "prev_day_low", "pdl_price"],
        "bull_boundary": ["bull_stack_boundary", "bull_full_stack_boundary", "full_stack_high", "stack_high", "final_high", "dp4_bull_boundary", "bull_boundary"],
        "bear_boundary": ["bear_stack_boundary", "bear_full_stack_boundary", "full_stack_low", "stack_low", "final_low", "dp4_bear_boundary", "bear_boundary"],
        "generic_boundary": ["full_stack_boundary", "stack_boundary", "breakout_boundary", "breakout_level", "dp4_boundary", "decision_boundary"],
    }
    out = {k: _find_col(cols, v) for k, v in aliases.items()}

    # Conservative heuristic fallback only for explicitly stack/boundary-labelled columns.
    normalized = {c: _norm(c) for c in cols}
    if out["bull_boundary"] is None:
        cand = [c for c, n in normalized.items() if "stack" in n and "high" in n and not any(x in n for x in ["width", "pct", "ratio"])]
        out["bull_boundary"] = cand[0] if len(cand) == 1 else None
    if out["bear_boundary"] is None:
        cand = [c for c, n in normalized.items() if "stack" in n and "low" in n and not any(x in n for x in ["width", "pct", "ratio"])]
        out["bear_boundary"] = cand[0] if len(cand) == 1 else None
    if out["generic_boundary"] is None:
        cand = [c for c, n in normalized.items() if "boundary" in n and not any(x in n for x in ["distance", "pct", "ratio"])]
        out["generic_boundary"] = cand[0] if len(cand) == 1 else None
    return out


def _boundary(row: pd.Series, mapping: dict) -> tuple[float, str]:
    direction = str(row["direction"]).upper()
    direct = mapping["bull_boundary"] if direction == "BULL" else mapping["bear_boundary"]
    if direct and pd.notna(row.get(direct)):
        return float(row[direct]), f"direct:{direct}"
    generic = mapping["generic_boundary"]
    if generic and pd.notna(row.get(generic)):
        return float(row[generic]), f"generic:{generic}"
    keys = ["pmh", "ahh", "pdh"] if direction == "BULL" else ["pml", "ahl", "pdl"]
    cols = [mapping[k] for k in keys]
    if all(cols) and all(pd.notna(row.get(c)) for c in cols):
        vals = [float(row[c]) for c in cols]
        return (max(vals), "derived:max(PMH,AHH,PDH)") if direction == "BULL" else (min(vals), "derived:min(PML,AHL,PDL)")
    return np.nan, "unresolved"


def _load_cache(cache: Path, sym: str) -> pd.DataFrame | None:
    p = cache / sym / f"{sym}_2026.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p).copy()
    ts_col = _find_col(d.columns, ["timestamp_utc", "timestamp", "datetime_utc", "ts_utc"])
    if ts_col is None:
        raise KeyError(f"{sym}: timestamp column not found")
    d["timestamp_utc"] = pd.to_datetime(d[ts_col], utc=True)
    d["timestamp_et"] = d["timestamp_utc"].dt.tz_convert("America/New_York")
    d["trade_date"] = d["timestamp_et"].dt.date
    return d


def _rma(values: pd.Series, length: int = 14) -> pd.Series:
    x = values.astype(float).to_numpy()
    out = np.full(len(x), np.nan, dtype=float)
    if len(x) < length:
        return pd.Series(out, index=values.index)
    seed = np.nanmean(x[:length])
    if np.isfinite(seed):
        out[length - 1] = seed
        for i in range(length, len(x)):
            out[i] = (out[i - 1] * (length - 1) + x[i]) / length
    return pd.Series(out, index=values.index)


def _prepare_symbol(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    o = _find_col(d.columns, ["open", "o", "Open"])
    h = _find_col(d.columns, ["high", "h", "High"])
    l = _find_col(d.columns, ["low", "l", "Low"])
    c = _find_col(d.columns, ["close", "c", "Close"])
    v = _find_col(d.columns, ["volume", "v", "Volume"])
    if not all([o, h, l, c, v]):
        raise KeyError(f"OHLCV columns not found: open={o} high={h} low={l} close={c} volume={v}")

    r = d[(d["timestamp_et"].dt.time >= RTH_OPEN) & (d["timestamp_et"].dt.time <= RTH_LAST_MINUTE)].copy()
    r = r.sort_values("timestamp_et")
    r["minute_end_et"] = r["timestamp_et"] + pd.Timedelta(minutes=1)
    r["bar5_start"] = r["timestamp_et"].dt.floor("5min")
    r["typical"] = (r[h].astype(float) + r[l].astype(float) + r[c].astype(float)) / 3.0
    r["pv"] = r["typical"] * r[v].astype(float)
    r["cum_pv"] = r.groupby("trade_date")["pv"].cumsum()
    r["cum_vol"] = r.groupby("trade_date")[v].cumsum()
    r["vwap"] = r["cum_pv"] / r["cum_vol"].replace(0, np.nan)

    b = (
        r.groupby(["trade_date", "bar5_start"], as_index=False)
        .agg(open=(o, "first"), high=(h, "max"), low=(l, "min"), close=(c, "last"), volume=(v, "sum"))
        .sort_values(["trade_date", "bar5_start"])
    )
    b["decision_time_et"] = b["bar5_start"] + pd.Timedelta(minutes=5)
    parts = []
    for _, g in b.groupby("trade_date", sort=False):
        g = g.copy()
        prev_close = g["close"].astype(float).shift(1)
        tr = pd.concat([
            g["high"].astype(float) - g["low"].astype(float),
            (g["high"].astype(float) - prev_close).abs(),
            (g["low"].astype(float) - prev_close).abs(),
        ], axis=1).max(axis=1)
        g["atr14"] = _rma(tr, 14)
        g["prior_atr14"] = g["atr14"].shift(1)
        parts.append(g)
    b = pd.concat(parts, ignore_index=True) if parts else b
    return r, b, {"open": o, "high": h, "low": l, "close": c, "volume": v}


def _beyond(direction: str, x: float, boundary: float) -> bool:
    return bool(x > boundary) if direction == "BULL" else bool(x < boundary)


def _inside(direction: str, x: float, boundary: float) -> bool:
    return bool(x < boundary) if direction == "BULL" else bool(x > boundary)


def _touch(direction: str, high: float, low: float, boundary: float) -> bool:
    return bool(low <= boundary) if direction == "BULL" else bool(high >= boundary)


def _dir_distance(direction: str, price: float, boundary: float) -> tuple[float, float]:
    sign = 1.0 if direction == "BULL" else -1.0
    diff = sign * (price - boundary)
    pct = sign * (price / boundary - 1.0) if boundary else np.nan
    return diff, pct


def _sample_vwap(minutes: pd.DataFrame, decision_time: pd.Timestamp) -> float:
    x = minutes[minutes["minute_end_et"] <= decision_time]
    return float(x.iloc[-1]["vwap"]) if len(x) else np.nan


def _prior_atr(bars: pd.DataFrame, decision_time: pd.Timestamp) -> float:
    x = bars[bars["decision_time_et"] <= decision_time]
    return float(x.iloc[-1]["prior_atr14"]) if len(x) and pd.notna(x.iloc[-1]["prior_atr14"]) else np.nan


def _state_metrics(direction: str, boundary: float, price: float, decision_time: pd.Timestamp, dp4_time: pd.Timestamp, minutes: pd.DataFrame, bars: pd.DataFrame) -> dict:
    diff, pct = _dir_distance(direction, price, boundary)
    atr = _prior_atr(bars, decision_time)
    vwap = _sample_vwap(minutes, decision_time)
    vwap_diff, vwap_pct = _dir_distance(direction, price, vwap) if np.isfinite(vwap) and vwap != 0 else (np.nan, np.nan)
    return {
        "time": decision_time,
        "price": float(price),
        "minutes_from_dp4": float((decision_time - dp4_time).total_seconds() / 60.0),
        "distance_price": float(diff),
        "distance_pct": float(pct),
        "prior_atr14": float(atr) if np.isfinite(atr) else np.nan,
        "distance_atr": float(diff / atr) if np.isfinite(atr) and atr > 0 else np.nan,
        "vwap": float(vwap) if np.isfinite(vwap) else np.nan,
        "vwap_directional_distance_pct": float(vwap_pct) if np.isfinite(vwap_pct) else np.nan,
    }


def _event_path(row: pd.Series, minutes: pd.DataFrame, bars: pd.DataFrame, boundary: float) -> dict:
    direction = str(row["direction"]).upper()
    dp4 = row["timestamp_et"]
    day = row["trade_date"]
    m = minutes[(minutes["trade_date"] == day) & (minutes["minute_end_et"] > dp4)].copy()
    b = bars[(bars["trade_date"] == day) & (bars["decision_time_et"] > dp4)].copy().reset_index(drop=True)
    out: dict = {}

    # Penetration is known only at the end of the first 1m OHLC bar that proves it.
    pen_mask = m["high"].astype(float) > boundary if direction == "BULL" else m["low"].astype(float) < boundary
    if pen_mask.any():
        pr = m.loc[pen_mask].iloc[0]
        pprice = float(pr["high"] if direction == "BULL" else pr["low"])
        out["penetration"] = _state_metrics(direction, boundary, pprice, pr["minute_end_et"], dp4, minutes[minutes.trade_date == day], bars[bars.trade_date == day])

    close_idx = None
    for i, br in b.iterrows():
        if _beyond(direction, float(br["close"]), boundary):
            close_idx = i
            out["close_acceptance"] = _state_metrics(direction, boundary, float(br["close"]), br["decision_time_et"], dp4, minutes[minutes.trade_date == day], bars[bars.trade_date == day])
            break

    if close_idx is None:
        return out

    ca = b.loc[close_idx]
    subsequent = b.loc[close_idx + 1:].copy()

    # HOLD is deliberately the next completed 5m close only, per frozen B1 wording.
    if len(subsequent):
        nxt = subsequent.iloc[0]
        if (nxt["decision_time_et"] - ca["decision_time_et"]) <= pd.Timedelta(minutes=6) and _beyond(direction, float(nxt["close"]), boundary):
            out["hold_acceptance"] = _state_metrics(direction, boundary, float(nxt["close"]), nxt["decision_time_et"], dp4, minutes[minutes.trade_date == day], bars[bars.trade_date == day])

    # RETEST may occur after CLOSE even if HOLD has already occurred. FAILED is only
    # established if an inside close happens before either HOLD or RETEST is established.
    hold_time = out.get("hold_acceptance", {}).get("time")
    retest = None
    failure = None
    for _, br in subsequent.iterrows():
        close = float(br["close"])
        touched = _touch(direction, float(br["high"]), float(br["low"]), boundary)
        if touched and _beyond(direction, close, boundary) and retest is None:
            retest = _state_metrics(direction, boundary, close, br["decision_time_et"], dp4, minutes[minutes.trade_date == day], bars[bars.trade_date == day])
            out["retest_acceptance"] = retest
        established_time = min([t for t in [hold_time, retest["time"] if retest else None] if t is not None], default=None)
        if failure is None and _inside(direction, close, boundary) and (established_time is None or br["decision_time_et"] < established_time):
            failure = _state_metrics(direction, boundary, close, br["decision_time_et"], dp4, minutes[minutes.trade_date == day], bars[bars.trade_date == day])
            out["failed_acceptance"] = failure
            break

    if failure is not None:
        later = b[b["decision_time_et"] > failure["time"]]
        for _, br in later.iterrows():
            if _beyond(direction, float(br["close"]), boundary):
                out["reclaim_after_failure"] = _state_metrics(direction, boundary, float(br["close"]), br["decision_time_et"], dp4, minutes[minutes.trade_date == day], bars[bars.trade_date == day])
                break

    return out


def run(root: Path) -> dict:
    inp = root / "research_outputs" / "pmpd" / "post9n_batch1" / "context_enriched.parquet"
    protocol_path = root / "research_outputs" / "pmpd" / "edge" / "e2_batch1" / "acceptance_protocol.json"
    cache = root / "data" / "second1m_alt_entry_cache_v1" / "partitions"
    if not inp.exists():
        raise FileNotFoundError(inp)
    if not protocol_path.exists():
        raise FileNotFoundError(protocol_path)
    if not cache.exists():
        raise FileNotFoundError(cache)

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("protocol") != PROTOCOL:
        raise RuntimeError(f"Frozen protocol mismatch: {protocol.get('protocol')}")

    outdir = root / "research_outputs" / "pmpd" / "edge" / "e2_batch2"
    outdir.mkdir(parents=True, exist_ok=True)

    v = pd.read_parquet(inp).copy()
    v["trade_date"] = pd.to_datetime(v["trade_date"]).dt.date
    v = v[v["trade_date"].between(START, END)].copy()
    ts = pd.to_datetime(v["timestamp_et"])
    if getattr(ts.dt, "tz", None) is None:
        v["timestamp_et"] = ts.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
    else:
        v["timestamp_et"] = ts.dt.tz_convert("America/New_York")
    v = v[v["timestamp_et"].notna()].copy()
    v["direction"] = v["direction"].astype(str).str.upper().str.strip()

    required = {"symbol", "trade_date", "timestamp_et", "direction"}
    missing = sorted(required - set(v.columns))
    if missing:
        raise KeyError(f"Missing required context columns: {missing}")

    mapping = _resolve_level_columns(v)
    boundaries = v.apply(lambda r: _boundary(r, mapping), axis=1)
    v["acceptance_boundary"] = [x[0] for x in boundaries]
    v["boundary_source"] = [x[1] for x in boundaries]
    v["event_key"] = (
        v["symbol"].astype(str) + "|" + v["trade_date"].astype(str) + "|" +
        v["timestamp_et"].astype(str) + "|" + v["direction"].astype(str)
    )

    rows = []
    missing_cache = []
    symbol_errors = []
    symbols = sorted(v["symbol"].astype(str).unique())
    for n, sym in enumerate(symbols, 1):
        print(f"[{n}/{len(symbols)}] E2_ACCEPTANCE_PATH {sym}")
        d = _load_cache(cache, sym)
        if d is None:
            missing_cache.append(sym)
            continue
        try:
            minutes, bars, _ = _prepare_symbol(d)
        except Exception as exc:
            symbol_errors.append({"symbol": sym, "error": repr(exc)})
            continue

        for _, er in v[v["symbol"].astype(str).eq(sym)].iterrows():
            base = {
                "event_key": er["event_key"],
                "symbol": sym,
                "trade_date": er["trade_date"],
                "direction": er["direction"],
                "dp4_timestamp_et": er["timestamp_et"],
                "acceptance_boundary": er["acceptance_boundary"],
                "boundary_source": er["boundary_source"],
                "opening_rvol14_mean_5m": er.get("opening_rvol14_mean_5m", np.nan),
                "opening_rvol_ge_1_5": bool(er.get("opening_rvol14_mean_5m", np.nan) >= 1.5) if pd.notna(er.get("opening_rvol14_mean_5m", np.nan)) else False,
            }
            if not np.isfinite(er["acceptance_boundary"]):
                base["analyzable"] = False
                base["analysis_reason"] = "boundary_unresolved"
                rows.append(base)
                continue
            path = _event_path(er, minutes, bars, float(er["acceptance_boundary"]))
            base["analyzable"] = True
            base["analysis_reason"] = "ok"
            for state in ["penetration", "close_acceptance", "hold_acceptance", "retest_acceptance", "failed_acceptance", "reclaim_after_failure"]:
                m = path.get(state)
                base[f"{state}_seen"] = m is not None
                if m:
                    for k, val in m.items():
                        base[f"{state}_{k}"] = val
            rows.append(base)

    paths = pd.DataFrame(rows)
    for state in ["penetration", "close_acceptance", "hold_acceptance", "retest_acceptance", "failed_acceptance", "reclaim_after_failure"]:
        col = f"{state}_seen"
        if col not in paths.columns:
            paths[col] = False
        paths[col] = paths[col].fillna(False).astype(bool)

    paths.to_parquet(outdir / "acceptance_state_paths.parquet", index=False)

    analyzable = paths[paths["analyzable"].fillna(False)] if len(paths) else paths
    coverage_rows = []
    total_context = int(len(v))
    coverage_rows.append({"metric": "context_events", "count": total_context, "rate": 1.0})
    coverage_rows.append({"metric": "rows_emitted", "count": int(len(paths)), "rate": float(len(paths) / total_context) if total_context else np.nan})
    coverage_rows.append({"metric": "boundary_resolved", "count": int(np.isfinite(v["acceptance_boundary"]).sum()), "rate": float(np.isfinite(v["acceptance_boundary"]).mean()) if len(v) else np.nan})
    coverage_rows.append({"metric": "analyzable", "count": int(len(analyzable)), "rate": float(len(analyzable) / total_context) if total_context else np.nan})
    for state in ["penetration", "close_acceptance", "hold_acceptance", "retest_acceptance", "failed_acceptance", "reclaim_after_failure"]:
        seen = int(analyzable[f"{state}_seen"].sum()) if len(analyzable) else 0
        coverage_rows.append({"metric": state, "count": seen, "rate": float(seen / len(analyzable)) if len(analyzable) else np.nan})
    coverage = pd.DataFrame(coverage_rows)
    coverage.to_csv(outdir / "coverage.csv", index=False)

    delay_rows = []
    for state in ["penetration", "close_acceptance", "hold_acceptance", "retest_acceptance", "failed_acceptance", "reclaim_after_failure"]:
        c = f"{state}_minutes_from_dp4"
        vals = pd.to_numeric(analyzable[c], errors="coerce").dropna() if c in analyzable.columns else pd.Series(dtype=float)
        delay_rows.append({
            "state": state,
            "n": int(len(vals)),
            "median_minutes": float(vals.median()) if len(vals) else np.nan,
            "p25_minutes": float(vals.quantile(0.25)) if len(vals) else np.nan,
            "p75_minutes": float(vals.quantile(0.75)) if len(vals) else np.nan,
            "p90_minutes": float(vals.quantile(0.90)) if len(vals) else np.nan,
        })
    pd.DataFrame(delay_rows).to_csv(outdir / "decision_delay.csv", index=False)

    schema = {
        "protocol": PROTOCOL,
        "context_columns": list(v.columns),
        "resolved_level_mapping": mapping,
        "boundary_source_counts": v["boundary_source"].value_counts(dropna=False).to_dict(),
        "missing_cache_symbols": missing_cache,
        "symbol_errors": symbol_errors,
    }
    (outdir / "schema_audit.json").write_text(json.dumps(schema, indent=2, default=str), encoding="utf-8")

    def _count(state: str) -> int:
        return int(analyzable[f"{state}_seen"].sum()) if len(analyzable) else 0

    summary = {
        "step": "PMPD-EDGE-E2-B2",
        "protocol": PROTOCOL,
        "purpose": "Construct causal acceptance-state paths and certify availability/coverage before outcome comparison.",
        "outcome_comparison_performed": False,
        "context_events": total_context,
        "rows_emitted": int(len(paths)),
        "symbols_context": int(v["symbol"].nunique()),
        "symbols_missing_cache": missing_cache,
        "boundary_resolved_events": int(np.isfinite(v["acceptance_boundary"]).sum()),
        "analyzable_events": int(len(analyzable)),
        "state_counts": {
            "penetration": _count("penetration"),
            "close_acceptance": _count("close_acceptance"),
            "hold_acceptance": _count("hold_acceptance"),
            "retest_acceptance": _count("retest_acceptance"),
            "failed_acceptance": _count("failed_acceptance"),
            "reclaim_after_failure": _count("reclaim_after_failure"),
        },
        "guardrails": {
            "research_only": True,
            "2026_development_evidence": True,
            "v4_modified": False,
            "v5_modified": False,
            "production_rule_authorized": False,
            "trade_health_reserved_for_e3": True,
            "acceptance_definitions_retuned": False,
        },
        "next_batch_if_integrity_passes": "E2-B3 pre-specified state-anchored +/-0.50% outcome comparison from each state's first observable decision timestamp/price, including coverage-versus-delay tradeoff.",
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    return {
        "status": "PASS",
        "protocol": PROTOCOL,
        "context_events": total_context,
        "analyzable_events": int(len(analyzable)),
        "outcome_comparison_performed": False,
        "output_paths": [
            str((outdir / "acceptance_state_paths.parquet").relative_to(root)),
            str((outdir / "coverage.csv").relative_to(root)),
            str((outdir / "decision_delay.csv").relative_to(root)),
            str((outdir / "schema_audit.json").relative_to(root)),
            str((outdir / "summary.json").relative_to(root)),
        ],
        "research_only": True,
        "v4_modified": False,
        "v5_modified": False,
        "production_rule_authorized": False,
    }


if __name__ == "__main__":
    raise SystemExit(run(Path.cwd()))
