from pathlib import Path
import hashlib, json, zipfile
import numpy as np
import pandas as pd

ROOT = Path(".").resolve()
SRC_DIR = ROOT / "pmpd_v5_9j_vwap_event_path_v2_full50"
SRC = SRC_DIR / "decision_vwap_event_path_v2.csv"
PARENT = ROOT / "pmpd_v5_9h_research_dataset_v1" / "decision_research.csv"
OUT_DIR = ROOT / "pmpd_v5_9j_vwap_event_path_v2_dp4fix"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "decision_vwap_event_path_v2_dp4fix.csv"

EXPECTED_ROWS = 450491
EXPECTED_EVENTS = 44627
EXPECTED_SYMBOLS = 112
SOURCE_FINGERPRINT = "1f3e0d2bec2c6257bb6b372d324e9b0bc6948d6f02c5713b5ae10091573f0b56"

print("=== LOAD CERTIFIED V2 + STRUCTURAL PARENT ===")
v = pd.read_csv(SRC, low_memory=False)
p = pd.read_csv(PARENT, low_memory=False)

assert len(v) == EXPECTED_ROWS
assert v["decision_id"].nunique() == EXPECTED_ROWS
assert v["event_id"].nunique() == EXPECTED_EVENTS
assert v["symbol"].nunique() == EXPECTED_SYMBOLS

v["timestamp_utc"] = pd.to_datetime(v["timestamp_utc"], utc=True, errors="coerce")
p["timestamp_utc"] = pd.to_datetime(p["timestamp_utc"], utc=True, errors="coerce")

print("=== DERIVE FIRST DP4 PER EVENT ===")
dp4 = (
    p.loc[p["decision_type"].eq("DP4_FULL_STACK_FIRST_CLEAR"),
          ["event_id", "timestamp_utc"]]
    .sort_values(["event_id", "timestamp_utc"])
    .drop_duplicates("event_id", keep="first")
    .rename(columns={"timestamp_utc": "dp4_full_stack_first_clear_timestamp_utc"})
)
print("events_with_dp4 =", len(dp4))
assert len(dp4) == 22736

d = v.merge(dp4, on="event_id", how="left", validate="many_to_one")
assert len(d) == len(v)

print("=== RECONSTRUCT LAST VWAP-LOSS TIMESTAMP AT EACH DECISION ===")
loss_age = pd.to_numeric(d["event_minutes_since_last_loss"], errors="coerce")
loss_seen = d["event_loss_seen"]
if loss_seen.dtype != bool:
    loss_seen = loss_seen.astype(str).str.lower().eq("true")

d["event_last_vwap_loss_timestamp_utc"] = pd.Series(pd.NaT, index=d.index, dtype="datetime64[ns, UTC]")
mask_loss = loss_seen & loss_age.notna()
d.loc[mask_loss, "event_last_vwap_loss_timestamp_utc"] = (
    d.loc[mask_loss, "timestamp_utc"] -
    pd.to_timedelta(loss_age.loc[mask_loss], unit="m")
)

dp4_ts = d["dp4_full_stack_first_clear_timestamp_utc"]
last_loss_ts = pd.to_datetime(d["event_last_vwap_loss_timestamp_utc"], utc=True, errors="coerce")

corrected = (
    dp4_ts.notna()
    & last_loss_ts.notna()
    & (d["timestamp_utc"] >= dp4_ts)
    & (last_loss_ts >= dp4_ts)
    & (last_loss_ts <= d["timestamp_utc"])
)

# Preserve the original semantically-invalid field explicitly for provenance.
d = d.rename(columns={
    "event_vwap_loss_after_structural_clearance":
    "event_vwap_loss_after_first_dp345_legacy"
})
d["event_vwap_loss_after_dp4_full_stack_clearance"] = corrected.astype(bool)

# Derived-artifact metadata.
d["vwap_event_path_derivation_version"] = "PMPD_V5_9J_VWAP_EVENT_PATH_V2_DP4FIX"
d["source_v2_fingerprint"] = SOURCE_FINGERPRINT

print("=== DERIVATION INTEGRITY GATES ===")
checks = {}
checks["row_count"] = len(d) == EXPECTED_ROWS
checks["unique_decisions"] = d["decision_id"].nunique() == EXPECTED_ROWS
checks["events"] = d["event_id"].nunique() == EXPECTED_EVENTS
checks["symbols"] = d["symbol"].nunique() == EXPECTED_SYMBOLS
checks["decision_id_set_preserved"] = set(d["decision_id"]) == set(v["decision_id"])

# All original fields except the renamed legacy field must be unchanged exactly.
base_cols = [c for c in v.columns if c not in {"decision_id", "event_vwap_loss_after_structural_clearance"}]
left = v[["decision_id"] + base_cols].copy()
right = d[["decision_id"] + base_cols].copy()

# Compare via hashes after normalizing datetime source representation where necessary.
for frame in (left, right):
    for c in frame.columns:
        if c.endswith("_utc") or c.endswith("_timestamp") or "timestamp" in c:
            frame[c] = frame[c].astype(str)

base_equal = left.sort_values("decision_id").reset_index(drop=True).equals(
    right.sort_values("decision_id").reset_index(drop=True)
)
checks["all_nonlegacy_source_fields_preserved"] = base_equal

# DP4 must be absent before an event reaches DP4 and corrected flag cannot be true without DP4.
checks["corrected_never_true_without_dp4"] = not bool(
    (d["event_vwap_loss_after_dp4_full_stack_clearance"] & dp4_ts.isna()).any()
)
checks["corrected_never_true_before_dp4"] = not bool(
    (d["event_vwap_loss_after_dp4_full_stack_clearance"] & (d["timestamp_utc"] < dp4_ts)).fillna(False).any()
)

# If corrected flag is true, reconstructed last loss must lie within [DP4, decision].
true_rows = d["event_vwap_loss_after_dp4_full_stack_clearance"]
checks["true_rows_have_valid_loss_interval"] = bool((
    (last_loss_ts[true_rows] >= dp4_ts[true_rows]) &
    (last_loss_ts[true_rows] <= d.loc[true_rows, "timestamp_utc"])
).all())

print("true_rows_corrected =", int(true_rows.sum()))
print("true_events_corrected =", int(d.loc[true_rows, "event_id"].nunique()))
print("legacy_true_rows =", int(
    d["event_vwap_loss_after_first_dp345_legacy"].astype(str).str.lower().eq("true").sum()
))
print("legacy_true_events =", int(
    d.loc[
        d["event_vwap_loss_after_first_dp345_legacy"].astype(str).str.lower().eq("true"),
        "event_id"
    ].nunique()
))

for k, val in checks.items():
    print(k, "=", "PASS" if val else "FAIL")

failed = [k for k, val in checks.items() if not val]
if failed:
    raise SystemExit(f"DP4_DERIVATION_GATE=FAIL failed={failed}")

print("DP4_DERIVATION_GATE=PASS")

print("=== WRITE DERIVED ARTIFACT ===")
d.to_csv(OUT, index=False)

# Fingerprint the decision identity + corrected semantic fields.
finger_cols = [
    "decision_id",
    "dp4_full_stack_first_clear_timestamp_utc",
    "event_last_vwap_loss_timestamp_utc",
    "event_vwap_loss_after_dp4_full_stack_clearance",
    "source_v2_fingerprint",
]
finger_frame = d[finger_cols].copy()
for c in finger_frame.columns:
    finger_frame[c] = finger_frame[c].astype(str)
fingerprint = hashlib.sha256(
    finger_frame.sort_values("decision_id").to_csv(index=False).encode("utf-8")
).hexdigest()

meta = {
    "version": "PMPD_V5_9J_VWAP_EVENT_PATH_V2_DP4FIX",
    "source_version": "PMPD_V5_9J_VWAP_EVENT_PATH_V2",
    "source_fingerprint": SOURCE_FINGERPRINT,
    "fingerprint": fingerprint,
    "rows": int(len(d)),
    "unique_decisions": int(d["decision_id"].nunique()),
    "events": int(d["event_id"].nunique()),
    "symbols": int(d["symbol"].nunique()),
    "columns": int(len(d.columns)),
    "events_with_dp4": int(dp4["event_id"].nunique()),
    "corrected_true_rows": int(true_rows.sum()),
    "corrected_true_events": int(d.loc[true_rows, "event_id"].nunique()),
    "legacy_field_status": "PRESERVED_RENAMED_NOT_FOR_ANALYSIS",
    "structural_clearance_semantics": "DP4_FULL_STACK_FIRST_CLEAR",
}
(OUT_DIR / "run_fingerprint.json").write_text(
    json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8"
)

zip_path = ROOT / "pmpd_v5_9j_vwap_event_path_v2_dp4fix.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for f in OUT_DIR.rglob("*"):
        if f.is_file():
            z.write(f, f.relative_to(OUT_DIR))

print("DERIVED_ROWS =", len(d))
print("DERIVED_COLUMNS =", len(d.columns))
print("DERIVED_FINGERPRINT =", fingerprint)
print("OUTPUT =", OUT)
print("PACKAGE =", zip_path)
print("DP4_FIX_COMPLETE")
