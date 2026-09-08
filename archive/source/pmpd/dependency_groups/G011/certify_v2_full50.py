from pathlib import Path
import json, sys
import numpy as np
import pandas as pd

ROOT = Path(".").resolve()
V2_DIR = ROOT / "pmpd_v5_9j_vwap_event_path_v2_full50"
V2_CSV = V2_DIR / "decision_vwap_event_path_v2.csv"
FP_JSON = V2_DIR / "run_fingerprint.json"

EXPECTED = {
    "rows": 450491,
    "unique_decisions": 450491,
    "events": 44627,
    "symbols": 112,
    "primary_rows": 266076,
    "columns": 50,
    "fingerprint": "1f3e0d2bec2c6257bb6b372d324e9b0bc6948d6f02c5713b5ae10091573f0b56",
}

REQ = [
    "decision_id","event_id","decision_type","timestamp_utc","symbol","trade_date","direction",
    "primary_decision_unit","dp1_timestamp_utc","rth_vwap_at_decision",
    "directional_vwap_distance_pct","directional_vwap_distance_min_from_dp1_pct",
    "directional_vwap_distance_max_from_dp1_pct","event_minutes_from_dp1",
    "event_vwap_touch_count_from_dp1","event_vwap_cross_count_from_dp1",
    "event_favorable_close_count","event_adverse_close_count",
    "event_favorable_close_fraction","event_adverse_close_fraction",
    "event_consecutive_favorable_closes_at_decision","event_consecutive_adverse_closes_at_decision",
    "event_directional_rejection_count","event_reclaim_count","event_loss_count",
    "event_minutes_since_last_touch","event_minutes_since_last_cross",
    "event_minutes_since_last_reclaim","event_minutes_since_last_loss",
    "event_minutes_since_last_rejection","event_dp1_side_sign","event_decision_side_sign",
    "source_max_timestamp_utc","vwap_event_path_version","parent_dataset_version","protocol_id"
]

AGE_COLS = [
    "event_minutes_from_dp1","event_minutes_since_last_touch","event_minutes_since_last_cross",
    "event_minutes_since_last_reclaim","event_minutes_since_last_loss","event_minutes_since_last_rejection"
]

def find_first(paths):
    for p in paths:
        if p.exists():
            return p
    return None

PARENT = find_first([
    ROOT/"pmpd_v5_9h_research_dataset_v1"/"decision_research.csv",
    ROOT/"pmpd_v5_9h_research_dataset_v1"/"decision_points.csv",
    ROOT/"pmpd_v5_alpha_0_2_full_universe"/"decision_points.csv",
    ROOT/"pmpd_v5_alpha_certification"/"run_1"/"decision_points.csv",
])

V1 = find_first([
    ROOT/"pmpd_v5_9j_vwap_enrichment_v1"/"decision_vwap_enrichment.csv",
])

if not V2_CSV.exists():
    raise FileNotFoundError(f"Missing V2 CSV: {V2_CSV}")
if PARENT is None:
    raise FileNotFoundError("Could not locate structural parent decision dataset.")
if V1 is None:
    raise FileNotFoundError("Could not locate V1 VWAP enrichment dataset.")

print("=== INPUTS ===")
print("V2 =", V2_CSV)
print("PARENT =", PARENT)
print("V1 =", V1)

v2 = pd.read_csv(V2_CSV, low_memory=False)
checks = {}
checks["row_count"] = len(v2) == EXPECTED["rows"]
checks["unique_decisions"] = v2.decision_id.nunique() == EXPECTED["unique_decisions"]
checks["events"] = v2.event_id.nunique() == EXPECTED["events"]
checks["symbols"] = v2.symbol.nunique() == EXPECTED["symbols"]
checks["columns_50"] = len(v2.columns) == EXPECTED["columns"]
checks["required_columns_present"] = all(c in v2.columns for c in REQ)

prim = v2["primary_decision_unit"]
primary_rows = int(prim.sum()) if prim.dtype == bool else int(prim.astype(str).str.lower().eq("true").sum())
checks["primary_rows"] = primary_rows == EXPECTED["primary_rows"]

print("\n=== POPULATION ===")
print("rows =", len(v2))
print("unique_decisions =", v2.decision_id.nunique())
print("events =", v2.event_id.nunique())
print("symbols =", v2.symbol.nunique())
print("primary_rows =", primary_rows)
print("columns =", len(v2.columns))
print("missing_required =", [c for c in REQ if c not in v2.columns])

print("\n=== FINGERPRINT METADATA ===")
if FP_JSON.exists():
    meta = json.loads(FP_JSON.read_text(encoding="utf-8"))
    print(json.dumps(meta, indent=2, sort_keys=True))
    checks["fingerprint_metadata"] = meta.get("fingerprint") == EXPECTED["fingerprint"]
    checks["fingerprint_meta_counts"] = (
        meta.get("rows") == EXPECTED["rows"]
        and meta.get("primary_rows") == EXPECTED["primary_rows"]
        and meta.get("symbol_count") == EXPECTED["symbols"]
    )
else:
    checks["fingerprint_metadata"] = False
    checks["fingerprint_meta_counts"] = False

print("\n=== TEMPORAL / LEAKAGE GATES ===")
for c in ["timestamp_utc","dp1_timestamp_utc","source_max_timestamp_utc"]:
    v2[c] = pd.to_datetime(v2[c], utc=True, errors="coerce")

checks["no_missing_decision_ts"] = v2.timestamp_utc.notna().all()
checks["no_missing_dp1_ts"] = v2.dp1_timestamp_utc.notna().all()
checks["no_missing_source_max_ts"] = v2.source_max_timestamp_utc.notna().all()
checks["dp1_not_after_decision"] = (v2.dp1_timestamp_utc <= v2.timestamp_utc).all()
checks["source_not_after_decision"] = (v2.source_max_timestamp_utc <= v2.timestamp_utc).all()
for c in AGE_COLS:
    x = pd.to_numeric(v2[c], errors="coerce")
    checks[f"nonnegative_{c}"] = bool((x.dropna() >= 0).all())
checks["no_missing_vwap"] = v2.rth_vwap_at_decision.notna().all()

print("dp1_after_decision_count =", int((v2.dp1_timestamp_utc > v2.timestamp_utc).sum()))
print("source_after_decision_count =", int((v2.source_max_timestamp_utc > v2.timestamp_utc).sum()))
for c in AGE_COLS:
    x = pd.to_numeric(v2[c], errors="coerce")
    print(f"negative_{c}_count =", int((x.dropna() < 0).sum()))
print("missing_vwap_count =", int(v2.rth_vwap_at_decision.isna().sum()))

print("\n=== STRUCTURAL PARENT IDENTITY ===")
parent = pd.read_csv(PARENT, low_memory=False)
need_parent = ["decision_id","event_id","decision_type","timestamp_utc","symbol","direction"]
missing_parent = [c for c in need_parent if c not in parent.columns]
if missing_parent:
    raise KeyError(f"Parent missing columns: {missing_parent}")

parent["timestamp_utc"] = pd.to_datetime(parent.timestamp_utc, utc=True, errors="coerce")
checks["parent_row_count"] = len(parent) == EXPECTED["rows"]
checks["parent_unique_decisions"] = parent.decision_id.nunique() == EXPECTED["unique_decisions"]
checks["decision_id_set_match_parent"] = set(v2.decision_id) == set(parent.decision_id)

m = v2[need_parent].merge(parent[need_parent], on="decision_id", how="outer", suffixes=("_v2","_parent"), indicator=True)
checks["identity_merge_both"] = bool(m["_merge"].eq("both").all())
for c in ["event_id","decision_type","symbol","direction"]:
    bad = (m[f"{c}_v2"].astype(str) != m[f"{c}_parent"].astype(str)) & m["_merge"].eq("both")
    print(f"identity_mismatch_{c} =", int(bad.sum()))
    checks[f"identity_{c}"] = int(bad.sum()) == 0
ts_bad = (m["timestamp_utc_v2"] != m["timestamp_utc_parent"]) & m["_merge"].eq("both")
print("identity_mismatch_timestamp_utc =", int(ts_bad.sum()))
checks["identity_timestamp_utc"] = int(ts_bad.sum()) == 0

print("\n=== TEMPORAL PARTITION GATE ===")
td = pd.to_datetime(v2.trade_date, errors="coerce")
disc = (td >= pd.Timestamp("2025-01-02")) & (td <= pd.Timestamp("2025-04-30"))
va = (td >= pd.Timestamp("2025-05-01")) & (td <= pd.Timestamp("2025-08-29"))
vb = (td >= pd.Timestamp("2025-09-02")) & (td <= pd.Timestamp("2025-12-31"))
assigned = disc.astype(int) + va.astype(int) + vb.astype(int)
checks["partition_exactly_one"] = bool((assigned == 1).all())
checks["partition_no_outside_dates"] = bool((assigned > 0).all())
checks["partition_no_overlap"] = bool((assigned <= 1).all())
print("DISCOVERY rows =", int(disc.sum()))
print("VALIDATION_A rows =", int(va.sum()))
print("VALIDATION_B rows =", int(vb.sum()))
print("unassigned rows =", int((assigned == 0).sum()))
print("overlap rows =", int((assigned > 1).sum()))

print("\n=== V1/V2 RTH VWAP PARITY ===")
v1 = pd.read_csv(V1, low_memory=False)
v1_vwap_col = next((c for c in ["rth_vwap_at_decision","vwap_at_decision","rth_vwap"] if c in v1.columns), None)
if v1_vwap_col is None:
    raise KeyError(f"Could not identify V1 VWAP column. Available: {list(v1.columns)}")

left = v2[["decision_id","rth_vwap_at_decision"]].rename(columns={"rth_vwap_at_decision":"rth_vwap_at_decision_v2"})
right = v1[["decision_id",v1_vwap_col]].rename(columns={v1_vwap_col:"rth_vwap_at_decision_v1"})
j = left.merge(right, on="decision_id", how="inner")
a = pd.to_numeric(j["rth_vwap_at_decision_v2"], errors="coerce")
b = pd.to_numeric(j["rth_vwap_at_decision_v1"], errors="coerce")
diff = (a-b).abs()
tol = 1e-10
checks["v1_v2_join_count"] = len(j) == EXPECTED["rows"]
checks["v1_v2_vwap_parity"] = bool((diff.fillna(np.inf) <= tol).all())
print("join_rows =", len(j))
print("max_abs_vwap_diff =", float(diff.max()))
print("nonparity_count_tol_1e-10 =", int((diff.fillna(np.inf) > tol).sum()))

print("\n=== VALUE SANITY ===")
for c in ["event_favorable_close_fraction","event_adverse_close_fraction"]:
    x = pd.to_numeric(v2[c], errors="coerce")
    checks[f"{c}_within_0_1"] = bool(((x >= 0) & (x <= 1)).all())
touch = pd.to_numeric(v2["event_vwap_touch_count_from_dp1"], errors="coerce")
cross = pd.to_numeric(v2["event_vwap_cross_count_from_dp1"], errors="coerce")
bars = pd.to_numeric(v2["event_bars_from_dp1_inclusive"], errors="coerce")
checks["touch_count_not_gt_bars"] = bool((touch <= bars).all())
checks["cross_count_not_gt_bars"] = bool((cross <= bars).all())

print("\n=== CERTIFICATION RESULT ===")
for k in sorted(checks):
    print(f"{k} = {'PASS' if bool(checks[k]) else 'FAIL'}")
failed = [k for k,v in checks.items() if not bool(v)]
overall = not failed
print("\nCERTIFICATION_OVERALL =", "PASS" if overall else "FAIL")
print("FAILED_CHECKS =", failed)

result = {
    "certification": "PASS" if overall else "FAIL",
    "failed_checks": failed,
    "expected": EXPECTED,
    "observed": {
        "rows": len(v2),
        "unique_decisions": int(v2.decision_id.nunique()),
        "events": int(v2.event_id.nunique()),
        "symbols": int(v2.symbol.nunique()),
        "primary_rows": primary_rows,
        "columns": len(v2.columns),
        "discovery_rows": int(disc.sum()),
        "validation_a_rows": int(va.sum()),
        "validation_b_rows": int(vb.sum()),
        "v1_v2_max_abs_vwap_diff": float(diff.max()),
    },
    "structural_clearance_field_analytical_status": "WITHHELD_PENDING_DP4_TAXONOMY_VERIFICATION"
}
cert_path = V2_DIR / "certification_v2.json"
cert_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
print("CERTIFICATION_FILE =", cert_path)
sys.exit(0 if overall else 2)
