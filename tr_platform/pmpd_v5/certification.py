from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
import json
from typing import Iterable

import pandas as pd

from tr_platform.historical.certified_dataset import load_certified_partition
from tr_platform.universe.pmpd_universe import load_validated_universe
from .alpha import run_symbol_alpha


DEFAULT_YEAR = 2025
DEFAULT_SYMBOL_COUNT = 5
DEFAULT_DATES_PER_SYMBOL = 10
DEFAULT_SEED = "PMPD_V5_ALPHA_0_1_CERT_V1"


def _stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint_rows(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return sha256(b"[]").hexdigest()
    use = [c for c in columns if c in df.columns]
    x = df[use].copy()
    for c in x.columns:
        if pd.api.types.is_datetime64_any_dtype(x[c]):
            x[c] = x[c].astype(str)
    rows = x.fillna("<NA>").astype(str).to_dict("records")
    return sha256(_stable_json(rows).encode("utf-8")).hexdigest()


def deterministic_symbols(repo_root: Path, count: int = DEFAULT_SYMBOL_COUNT) -> list[str]:
    """Select symbols deterministically without consulting outcomes."""
    members = load_validated_universe(repo_root)
    ranked = sorted(
        (sha256(f"{DEFAULT_SEED}|{m.symbol}".encode()).hexdigest(), m.symbol)
        for m in members
    )
    return [symbol for _, symbol in ranked[:count]]


def eligible_dates(bars: pd.DataFrame, dates_per_symbol: int = DEFAULT_DATES_PER_SYMBOL) -> list[pd.Timestamp]:
    """Select the earliest dates with complete PM/AH/PD context.

    Date eligibility is structural only. No outcome fields are consulted.
    """
    from .session_levels import build_session_levels
    levels = build_session_levels(bars)
    ok = levels.loc[levels["has_complete_six_levels"].astype(bool), "trade_date"]
    dates = sorted(pd.to_datetime(ok).dt.tz_localize(None).dt.normalize().unique())
    return [pd.Timestamp(d) for d in dates[:dates_per_symbol]]


def _slice_with_context(bars: pd.DataFrame, selected_dates: list[pd.Timestamp]) -> pd.DataFrame:
    if not selected_dates:
        return bars.iloc[0:0].copy()
    x = bars.copy()
    td = pd.to_datetime(x["trade_date"]).dt.tz_localize(None).dt.normalize()
    # Keep all source bars through the final selected day. This preserves the
    # prior-day RTH/AH context required to construct levels for selected dates.
    end = max(selected_dates)
    return x.loc[td.le(end)].copy()


def _filter_outputs(outputs: dict[str, pd.DataFrame], selected_dates: list[pd.Timestamp]) -> dict[str, pd.DataFrame]:
    selected = {pd.Timestamp(d).normalize() for d in selected_dates}
    result = {}
    for name, df in outputs.items():
        if df.empty or "trade_date" not in df.columns:
            result[name] = df.copy()
            continue
        td = pd.to_datetime(df["trade_date"]).dt.tz_localize(None).dt.normalize()
        result[name] = df.loc[td.isin(selected)].copy().reset_index(drop=True)
    return result


@dataclass(frozen=True)
class SymbolCertificationSummary:
    symbol: str
    year: int
    selected_dates: int
    bull_events: int
    bear_events: int
    transitions: int
    decision_points: int
    full_stack_events: int
    session_levels_fp: str
    geometry_fp: str
    events_fp: str
    transitions_fp: str
    decisions_fp: str
    aggregate_fp: str


FP_COLUMNS = {
    "session_levels": ["trade_date", "pmh", "pml", "ahh", "ahl", "pdh", "pdl", "has_complete_six_levels"],
    "geometry": ["trade_date", "direction", "pm_level", "ah_level", "pd_level",
                 "identity_order_inner_to_outer", "outer_level_name", "stack_width", "stack_width_pct"],
    "events": ["event_id", "trade_date", "direction", "event_start_time",
               "first_full_stack_trade_time", "first_full_stack_close_time",
               "max_levels_cleared", "attempt_count"],
    "transitions": ["event_id", "sequence", "timestamp_utc", "prior_close_vector",
                    "new_close_vector", "traded_vector", "attempt_number", "close"],
    "decision_points": ["event_id", "decision_sequence", "decision_type", "timestamp_utc",
                        "direction", "attempt_number", "close_vector", "traded_vector",
                        "reference_price", "reference_price_source"],
}


def run_certification(
    *,
    repo_root: Path,
    year: int = DEFAULT_YEAR,
    symbol_count: int = DEFAULT_SYMBOL_COUNT,
    dates_per_symbol: int = DEFAULT_DATES_PER_SYMBOL,
    verify_hash: bool = True,
    include_outcomes: bool = False,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict]:
    """Run the structural Alpha certification sample.

    Structural reports are the primary output. Outcomes are suppressed by default
    to avoid contaminating engine certification with profitability information.
    """
    repo_root = Path(repo_root).resolve()
    symbols = deterministic_symbols(repo_root, symbol_count)
    all_outputs: dict[str, list[pd.DataFrame]] = {
        "session_levels": [], "geometry": [], "events": [],
        "transitions": [], "decision_points": [], "outcomes": [],
    }
    summaries = []
    selection_rows = []

    for symbol in symbols:
        partition = load_certified_partition(
            symbol=symbol, year=year, repo_root=repo_root, verify_hash=verify_hash
        )
        bars = partition.dataframe.copy()
        dates = eligible_dates(bars, dates_per_symbol)
        if len(dates) < dates_per_symbol:
            raise RuntimeError(
                f"{symbol}: only {len(dates)} structurally eligible dates; "
                f"required {dates_per_symbol}."
            )

        for seq, d in enumerate(dates, start=1):
            selection_rows.append({
                "symbol": symbol, "year": year, "date_sequence": seq,
                "trade_date": d.strftime("%Y-%m-%d"),
                "selection_rule": "EARLIEST_COMPLETE_SIX_LEVEL_DATES",
            })

        sliced = _slice_with_context(bars, dates)
        outputs = _filter_outputs(run_symbol_alpha(sliced, symbol=symbol), dates)

        fps = {name: _fingerprint_rows(outputs[name], FP_COLUMNS[name]) for name in FP_COLUMNS}
        agg = sha256(_stable_json(fps).encode()).hexdigest()

        events = outputs["events"]
        summaries.append(SymbolCertificationSummary(
            symbol=symbol,
            year=year,
            selected_dates=len(dates),
            bull_events=int((events.get("direction", pd.Series(dtype=str)) == "BULL").sum()) if not events.empty else 0,
            bear_events=int((events.get("direction", pd.Series(dtype=str)) == "BEAR").sum()) if not events.empty else 0,
            transitions=len(outputs["transitions"]),
            decision_points=len(outputs["decision_points"]),
            full_stack_events=int((events.get("max_levels_cleared", pd.Series(dtype=int)) == 3).sum()) if not events.empty else 0,
            session_levels_fp=fps["session_levels"],
            geometry_fp=fps["geometry"],
            events_fp=fps["events"],
            transitions_fp=fps["transitions"],
            decisions_fp=fps["decision_points"],
            aggregate_fp=agg,
        ))

        for name, df in outputs.items():
            if name == "outcomes" and not include_outcomes:
                continue
            if not df.empty:
                y = df.copy()
                if "symbol" not in y.columns:
                    y.insert(0, "symbol", symbol)
                all_outputs[name].append(y)

    combined = {
        name: (pd.concat(parts, ignore_index=True) if parts else pd.DataFrame())
        for name, parts in all_outputs.items()
    }
    summary_df = pd.DataFrame(asdict(s) for s in summaries)
    selection_df = pd.DataFrame(selection_rows)

    run_payload = {
        "protocol": DEFAULT_SEED,
        "year": year,
        "symbol_count": symbol_count,
        "dates_per_symbol": dates_per_symbol,
        "symbols": symbols,
        "selection_fingerprint": _fingerprint_rows(
            selection_df, ["symbol", "year", "date_sequence", "trade_date", "selection_rule"]
        ),
        "symbol_aggregate_fingerprints": summary_df[["symbol", "aggregate_fp"]].to_dict("records"),
    }
    run_payload["run_fingerprint"] = sha256(_stable_json(run_payload).encode()).hexdigest()
    combined["selection"] = selection_df
    return summary_df, combined, run_payload


def write_certification_package(
    *,
    repo_root: Path,
    output_dir: Path,
    year: int = DEFAULT_YEAR,
    symbol_count: int = DEFAULT_SYMBOL_COUNT,
    dates_per_symbol: int = DEFAULT_DATES_PER_SYMBOL,
    verify_hash: bool = True,
) -> Path:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    summary, outputs, payload = run_certification(
        repo_root=repo_root,
        year=year,
        symbol_count=symbol_count,
        dates_per_symbol=dates_per_symbol,
        verify_hash=verify_hash,
        include_outcomes=False,
    )

    summary.to_csv(output_dir / "symbol_summary.csv", index=False)
    for name in ["selection", "session_levels", "geometry", "events", "transitions", "decision_points"]:
        outputs[name].to_csv(output_dir / f"{name}.csv", index=False)
    (output_dir / "run_fingerprint.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    readme = f"""PMPD V5 Alpha 0.1 Structural Certification
Protocol: {DEFAULT_SEED}
Year: {year}
Symbols: {symbol_count}
Eligible dates per symbol: {dates_per_symbol}

This package intentionally excludes profitability/outcome distributions.
It is for structural certification only.

Run fingerprint:
{payload['run_fingerprint']}
"""
    (output_dir / "README.txt").write_text(readme, encoding="utf-8")
    return output_dir


def compare_package_fingerprints(first_json: Path, second_json: Path) -> list[str]:
    a = json.loads(Path(first_json).read_text(encoding="utf-8"))
    b = json.loads(Path(second_json).read_text(encoding="utf-8"))
    issues = []
    if a.get("selection_fingerprint") != b.get("selection_fingerprint"):
        issues.append("selection_fingerprint_mismatch")
    if a.get("run_fingerprint") != b.get("run_fingerprint"):
        issues.append("run_fingerprint_mismatch")
    if a.get("symbol_aggregate_fingerprints") != b.get("symbol_aggregate_fingerprints"):
        issues.append("symbol_aggregate_fingerprints_mismatch")
    return issues


def _normalize_vector_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Preserve 3-bit vectors as zero-padded strings and explicit booleans."""
    if df.empty:
        return df.copy()
    out = df.copy()
    for col in ["prior_close_vector", "new_close_vector", "traded_vector", "close_vector"]:
        if col in out.columns:
            def norm(v):
                if pd.isna(v):
                    return pd.NA
                s = str(v)
                if s.endswith(".0"):
                    s = s[:-2]
                return s.zfill(3)
            out[col] = out[col].map(norm).astype("string")
            out[f"{col}_code"] = out[col].map(
                lambda v: pd.NA if pd.isna(v) else f"V{v}"
            ).astype("string")
    # Add explicit identity bits where a close-retention vector exists.
    source_col = "new_close_vector" if "new_close_vector" in out.columns else (
        "close_vector" if "close_vector" in out.columns else None
    )
    if source_col:
        out["pm_retained"] = out[source_col].str[0].eq("1")
        out["ah_retained"] = out[source_col].str[1].eq("1")
        out["pd_retained"] = out[source_col].str[2].eq("1")
    return out


def run_full_universe_structural_baseline(
    *,
    repo_root: Path,
    year: int = DEFAULT_YEAR,
    verify_hash: bool = True,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict]:
    """Run structural baseline across the entire frozen PMPD universe.

    This remains outcome-blind. It characterizes natural event frequency and
    structural path distributions before any profitability research.
    """
    repo_root = Path(repo_root).resolve()
    members = load_validated_universe(repo_root)
    symbols = [m.symbol for m in members]

    all_outputs = {k: [] for k in [
        "session_levels", "geometry", "events", "transitions", "decision_points"
    ]}
    summaries = []
    coverage_rows = []

    for symbol in symbols:
        partition = load_certified_partition(
            symbol=symbol, year=year, repo_root=repo_root, verify_hash=verify_hash
        )
        bars = partition.dataframe.copy()
        outputs = run_symbol_alpha(bars, symbol=symbol)

        for name in ["transitions", "decision_points"]:
            outputs[name] = _normalize_vector_columns(outputs[name])

        levels = outputs["session_levels"].copy()
        if not levels.empty:
            levels["symbol"] = symbol

            # Continuous observability / discontinuity metadata. These are audit
            # fields, not eligibility filters.
            if "pm_last_close" in levels.columns and "prior_rth_close" in levels.columns:
                denom = pd.to_numeric(levels["prior_rth_close"], errors="coerce")
                numer = pd.to_numeric(levels["pm_last_close"], errors="coerce")
                levels["overnight_gap_pct"] = (numer / denom - 1.0) * 100.0
                levels["price_scale_ratio"] = numer / denom

            outputs["session_levels"] = levels

            ah_count_col = (
                "prior_ah_bar_count" if "prior_ah_bar_count" in levels.columns
                else "ah_bar_count" if "ah_bar_count" in levels.columns
                else None
            )
            coverage_rows.append({
                "symbol": symbol,
                "trade_days": int(len(levels)),
                "six_level_days": int(levels["has_complete_six_levels"].astype(bool).sum())
                    if "has_complete_six_levels" in levels.columns else 0,
                "median_pm_bars": float(pd.to_numeric(levels["pm_bar_count"], errors="coerce").median())
                    if "pm_bar_count" in levels.columns else float("nan"),
                "median_ah_bars": float(pd.to_numeric(levels[ah_count_col], errors="coerce").median())
                    if ah_count_col else float("nan"),
                "median_rth_bars": float(pd.to_numeric(levels["prior_rth_bar_count"], errors="coerce").median())
                    if "prior_rth_bar_count" in levels.columns else float("nan"),
            })

        events = outputs["events"]
        summaries.append({
            "symbol": symbol,
            "events": len(events),
            "bull_events": int((events["direction"] == "BULL").sum()) if not events.empty else 0,
            "bear_events": int((events["direction"] == "BEAR").sum()) if not events.empty else 0,
            "full_stack_events": int((events["max_levels_cleared"] == 3).sum())
                if (not events.empty and "max_levels_cleared" in events.columns) else 0,
            "transitions": len(outputs["transitions"]),
            "decision_points": len(outputs["decision_points"]),
        })

        for name in all_outputs:
            df = outputs[name]
            if not df.empty:
                all_outputs[name].append(df)

    combined = {
        name: (pd.concat(parts, ignore_index=True) if parts else pd.DataFrame())
        for name, parts in all_outputs.items()
    }
    summary_df = pd.DataFrame(summaries)
    coverage_df = pd.DataFrame(coverage_rows)

    payload = {
        "protocol": "PMPD_V5_ALPHA_0_2_FULL_UNIVERSE_STRUCTURAL_V1",
        "year": year,
        "symbols": symbols,
        "symbol_count": len(symbols),
        "total_events": int(summary_df["events"].sum()) if not summary_df.empty else 0,
        "total_transitions": int(summary_df["transitions"].sum()) if not summary_df.empty else 0,
        "total_decision_points": int(summary_df["decision_points"].sum()) if not summary_df.empty else 0,
    }
    payload["run_fingerprint"] = sha256(_stable_json(payload).encode()).hexdigest()
    combined["coverage"] = coverage_df
    return summary_df, combined, payload
