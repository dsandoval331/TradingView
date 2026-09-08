from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import numpy as np
import pandas as pd

from tr_platform.historical.certified_dataset import load_certified_partition
from tr_platform.universe.pmpd_universe import load_validated_universe
from .alpha import run_symbol_alpha
from .certification import _normalize_vector_columns

VERSION = "PMPD_V5_9J_VWAP_EVENT_PATH_V2"
PARENT = "PMPD_V5_9H_RESEARCH_DATASET_V1"
PROTOCOL = "PMPD_V5_9J_ENTRY_ARCH_PROTOCOL_V1"

def _rth_vwap(day):
    x = day.sort_values("timestamp_utc").copy()
    tp = (pd.to_numeric(x.high) + pd.to_numeric(x.low) + pd.to_numeric(x.close)) / 3.0
    vol = pd.to_numeric(x.volume, errors="coerce").fillna(0.0)
    den = vol.cumsum()
    x["rth_vwap"] = (tp * vol).cumsum() / den.replace(0, np.nan)
    return x

def _dir_sign(direction):
    return 1 if str(direction).upper() == "BULL" else -1

def _age_minutes(end, ts):
    if ts is None or pd.isna(ts):
        return np.nan
    return (pd.Timestamp(end) - pd.Timestamp(ts)).total_seconds() / 60.0

def _streak(values, target):
    n = 0
    for v in reversed(list(values)):
        if int(v) == target:
            n += 1
        else:
            break
    return n

def _path_features(day, start_ts, end_ts, direction):
    start = pd.Timestamp(start_ts)
    end = pd.Timestamp(end_ts)
    d = day[(day.timestamp_utc >= start) & (day.timestamp_utc <= end)].copy()
    if d.empty:
        return {}

    ds = _dir_sign(direction)
    for c in ["open", "high", "low", "close"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    # Direction-normalized distances: positive=favorable side, negative=adverse.
    d["signed_close_vwap_pct"] = ds * (d.close / d.rth_vwap - 1.0) * 100.0
    d["signed_open_vwap_pct"] = ds * (d.open / d.rth_vwap - 1.0) * 100.0
    d["dir_side"] = np.sign(d.signed_close_vwap_pct).fillna(0).astype(int)
    d["touch"] = (d.low <= d.rth_vwap) & (d.high >= d.rth_vwap)

    prev_side = d.dir_side.shift(1)
    close_flip = d.dir_side.ne(0) & prev_side.notna() & prev_side.ne(0) & d.dir_side.ne(prev_side)
    body_cross = (
        d.signed_open_vwap_pct.ne(0)
        & d.signed_close_vwap_pct.ne(0)
        & (np.sign(d.signed_open_vwap_pct) != np.sign(d.signed_close_vwap_pct))
    )
    d["cross"] = d.touch & (close_flip | body_cross)

    # Event definitions are fixed before outcome analysis:
    # rejection = prior completed bar interacted with VWAP (touch/cross), current close favorable.
    prev_interaction = (d.touch | d["cross"]).shift(1, fill_value=False)
    d["directional_rejection"] = prev_interaction & d.dir_side.eq(1)

    # reclaim/loss = completed-close transition across VWAP in direction-normalized space.
    d["reclaim"] = prev_side.eq(-1) & d.dir_side.eq(1)
    d["loss"] = prev_side.eq(1) & d.dir_side.eq(-1)

    cur = d.iloc[-1]
    side = "FAVORABLE_SIDE" if cur.dir_side > 0 else ("ADVERSE_SIDE" if cur.dir_side < 0 else "ON_VWAP")

    def first_ts(mask):
        z = d.loc[mask, "timestamp_utc"]
        return z.iloc[0] if len(z) else pd.NaT

    def last_ts(mask):
        z = d.loc[mask, "timestamp_utc"]
        return z.iloc[-1] if len(z) else pd.NaT

    first_touch = first_ts(d.touch)
    first_cross = first_ts(d["cross"])
    first_fav = first_ts(d.dir_side.eq(1))
    first_adv = first_ts(d.dir_side.eq(-1))
    last_touch = last_ts(d.touch)
    last_cross = last_ts(d["cross"])
    last_reclaim = last_ts(d.reclaim)
    last_loss = last_ts(d.loss)
    last_rejection = last_ts(d.directional_rejection)

    n = len(d)
    fav_n = int(d.dir_side.eq(1).sum())
    adv_n = int(d.dir_side.eq(-1).sum())

    return {
        "rth_vwap_at_decision": float(cur.rth_vwap),
        "reference_price_minus_vwap_pct": (float(cur.close) / float(cur.rth_vwap) - 1.0) * 100.0,
        "directional_vwap_distance_pct": float(cur.signed_close_vwap_pct),
        "directional_vwap_distance_min_from_dp1_pct": float(d.signed_close_vwap_pct.min()),
        "directional_vwap_distance_max_from_dp1_pct": float(d.signed_close_vwap_pct.max()),
        "directional_vwap_side": side,
        "event_minutes_from_dp1": (end - start).total_seconds() / 60.0,
        "event_bars_from_dp1_inclusive": n,
        "event_vwap_touch_from_dp1": bool(d.touch.any()),
        "event_vwap_touch_count_from_dp1": int(d.touch.sum()),
        "event_first_vwap_touch_timestamp": first_touch,
        "event_vwap_cross_from_dp1": bool(d["cross"].any()),
        "event_vwap_cross_count_from_dp1": int(d["cross"].sum()),
        "event_first_vwap_cross_timestamp": first_cross,
        "event_first_favorable_close_timestamp": first_fav,
        "event_first_adverse_close_timestamp": first_adv,
        "event_favorable_close_count": fav_n,
        "event_adverse_close_count": adv_n,
        "event_favorable_close_fraction": fav_n / n,
        "event_adverse_close_fraction": adv_n / n,
        "event_consecutive_favorable_closes_at_decision": _streak(d.dir_side, 1),
        "event_consecutive_adverse_closes_at_decision": _streak(d.dir_side, -1),
        "event_directional_rejection_seen": bool(d.directional_rejection.any()),
        "event_directional_rejection_count": int(d.directional_rejection.sum()),
        "event_reclaim_seen": bool(d.reclaim.any()),
        "event_reclaim_count": int(d.reclaim.sum()),
        "event_loss_seen": bool(d.loss.any()),
        "event_loss_count": int(d.loss.sum()),
        "event_minutes_since_last_touch": _age_minutes(end, last_touch),
        "event_minutes_since_last_cross": _age_minutes(end, last_cross),
        "event_minutes_since_last_reclaim": _age_minutes(end, last_reclaim),
        "event_minutes_since_last_loss": _age_minutes(end, last_loss),
        "event_minutes_since_last_rejection": _age_minutes(end, last_rejection),
        "event_dp1_side_sign": int(d.iloc[0].dir_side),
        "event_decision_side_sign": int(cur.dir_side),
        "event_vwap_side_changed_from_dp1": bool(int(d.iloc[0].dir_side) != int(cur.dir_side)),
        "source_max_timestamp_utc": d.timestamp_utc.max(),
    }

def build_symbol(bars, *, symbol):
    dec = _normalize_vector_columns(run_symbol_alpha(bars, symbol=symbol)["decision_points"])
    if dec.empty:
        return pd.DataFrame()

    dec["timestamp_utc"] = pd.to_datetime(dec.timestamp_utc, utc=True)
    dec["trade_date"] = dec.event_id.map(lambda s: str(s).split("_")[1])
    dec = dec.sort_values(["event_id", "decision_sequence"])
    dec["decision_occurrence"] = dec.groupby(["event_id", "decision_type"]).cumcount() + 1
    dec["primary_decision_unit"] = dec.decision_occurrence.eq(1)

    first = (
        dec[dec.decision_type.eq("DP1_FIRST_CONTACT")]
        .groupby("event_id").timestamp_utc.first()
    )

    x = bars.copy()
    x["timestamp_utc"] = pd.to_datetime(x.timestamp_utc, utc=True)
    x["trade_date"] = pd.to_datetime(x.trade_date).dt.strftime("%Y-%m-%d")

    rows = []
    for td, g in dec.groupby("trade_date", sort=False):
        day = x[(x.trade_date == td) & (x.session == "RTH")].copy()
        if day.empty:
            continue
        day = _rth_vwap(day)

        # Track whether structural clearance (DP3/DP4/DP5) occurred before each decision.
        structural_ts = {}
        for ev, eg in g.groupby("event_id", sort=False):
            stypes = eg[eg.decision_type.str.match(r"DP[345]_", na=False)]
            structural_ts[ev] = stypes.timestamp_utc.min() if not stypes.empty else pd.NaT

        for r in g.itertuples(index=False):
            if r.event_id not in first.index:
                continue
            st = pd.Timestamp(first.loc[r.event_id])
            en = pd.Timestamp(r.timestamp_utc)
            f = _path_features(day, st, en, r.direction)
            if not f:
                continue
            clear_ts = structural_ts.get(r.event_id, pd.NaT)
            loss_after_clear = False
            if pd.notna(clear_ts) and clear_ts <= en:
                dd = day[(day.timestamp_utc >= max(st, clear_ts)) & (day.timestamp_utc <= en)].copy()
                if not dd.empty:
                    ds = _dir_sign(r.direction)
                    side = np.sign(ds * (pd.to_numeric(dd.close) / dd.rth_vwap - 1.0)).fillna(0).astype(int)
                    loss_after_clear = bool((side.shift(1).eq(1) & side.eq(-1)).any())

            rows.append({
                "decision_id": r.decision_id,
                "event_id": r.event_id,
                "decision_type": r.decision_type,
                "timestamp_utc": r.timestamp_utc,
                "symbol": symbol,
                "trade_date": td,
                "direction": r.direction,
                "primary_decision_unit": bool(r.primary_decision_unit),
                "dp1_timestamp_utc": st,
                **f,
                "event_vwap_loss_after_structural_clearance": loss_after_clear,
                "vwap_event_path_version": VERSION,
                "parent_dataset_version": PARENT,
                "protocol_id": PROTOCOL,
            })
    return pd.DataFrame(rows)

def audit(parent, v2):
    p = parent.copy()
    q = v2.copy()
    p["timestamp_utc"] = pd.to_datetime(p.timestamp_utc, utc=True)
    q["timestamp_utc"] = pd.to_datetime(q.timestamp_utc, utc=True)
    q["dp1_timestamp_utc"] = pd.to_datetime(q.dp1_timestamp_utc, utc=True)
    q["source_max_timestamp_utc"] = pd.to_datetime(q.source_max_timestamp_utc, utc=True)

    checks = {
        "row_count_match": len(p) == len(q),
        "unique_decision_id": q.decision_id.nunique() == len(q),
        "decision_id_set_match": set(p.decision_id) == set(q.decision_id),
        "dp1_not_after_decision": bool((q.dp1_timestamp_utc <= q.timestamp_utc).all()),
        "source_not_after_decision": bool((q.source_max_timestamp_utc <= q.timestamp_utc).all()),
        "nonnegative_event_age": bool((q.event_minutes_from_dp1 >= 0).all()),
        "no_missing_dp1": bool(q.dp1_timestamp_utc.notna().all()),
        "no_missing_vwap": bool(q.rth_vwap_at_decision.notna().all()),
    }
    checks["PASS"] = all(checks.values())
    return checks

def run(*, repo_root: Path, year=2025, verify_hash=True):
    repo_root = Path(repo_root).resolve()
    members = load_validated_universe(repo_root)
    fs, ss = [], []
    for i, m in enumerate(members, 1):
        print(f"[{i:03d}/{len(members):03d}] {m.symbol}", flush=True)
        p = load_certified_partition(
            symbol=m.symbol, year=year, repo_root=repo_root, verify_hash=verify_hash
        )
        e = build_symbol(p.dataframe.copy(), symbol=m.symbol)
        fs.append(e)
        ss.append({
            "symbol": m.symbol,
            "rows": len(e),
            "primary_rows": int(e.primary_decision_unit.sum()) if len(e) else 0
        })

    a = pd.concat(fs, ignore_index=True)
    keycols = [
        "decision_id", "dp1_timestamp_utc", "directional_vwap_distance_pct",
        "event_vwap_touch_count_from_dp1", "event_vwap_cross_count_from_dp1",
        "event_reclaim_count", "event_loss_count",
        "event_directional_rejection_count", "source_max_timestamp_utc"
    ]
    h = sha256(a[keycols].fillna("<NA>").astype(str).to_csv(index=False).encode()).hexdigest()
    meta = {
        "version": VERSION, "parent_dataset_version": PARENT, "protocol_id": PROTOCOL,
        "year": year, "rows": len(a),
        "primary_rows": int(a.primary_decision_unit.sum()),
        "symbol_count": len(members), "fingerprint": h
    }
    return a, pd.DataFrame(ss), meta
