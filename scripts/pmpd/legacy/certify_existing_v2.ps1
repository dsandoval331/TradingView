# Certify existing PMPD V5 9J VWAP Event-Path V2 output.
# Does NOT rebuild the 112-symbol dataset.
# Run from C:\Users\DirtySouth\TradingResearch with .venv active.
$ErrorActionPreference = "Stop"

python -c @'
import json
from pathlib import Path
import numpy as np
import pandas as pd
from tr_platform.pmpd_v5.vwap_event_path_v2 import audit

root = Path(".").resolve()

def pick(*candidates):
    for p in candidates:
        p = root / p
        if p.exists():
            return p
    raise FileNotFoundError("None found: " + ", ".join(str(root/c) for c in candidates))

v2_path = pick(
    "pmpd_v5_9j_vwap_event_path_v2/decision_vwap_event_path_v2.csv",
    "pmpd_v5_9j_vwap_event_path_v2_full/decision_vwap_event_path_v2.csv",
)
parent_struct_path = pick(
    "pmpd_v5_alpha_0_2_full_universe/decision_points.csv",
    "pmpd_v5_alpha_certification/run_1/decision_points.csv",
)
parent_outcome_path = pick(
    "pmpd_v5_9h_research_dataset_v1/decision_research.csv",
)
v1_path = pick(
    "pmpd_v5_9j_vwap_enrichment_v1/decision_vwap_enrichment.csv",
)

v2 = pd.read_csv(v2_path)
struct = pd.read_csv(parent_struct_path)
outcome = pd.read_csv(parent_outcome_path)
v1 = pd.read_csv(v1_path)

# Normalize timestamps.
for df, cols in [
    (v2, ["timestamp_utc","dp1_timestamp_utc","source_max_timestamp_utc"]),
    (struct, ["timestamp_utc"]),
]:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, errors="raise")

print("=== FILES ===")
print("V2=", v2_path)
print("STRUCTURAL_PARENT=", parent_struct_path)
print("OUTCOME_PARENT=", parent_outcome_path)
print("V1=", v1_path)

print("\n=== POPULATION ===")
print("V2_ROWS=", len(v2))
print("V2_UNIQUE_DECISIONS=", v2["decision_id"].nunique())
print("V2_EVENTS=", v2["event_id"].nunique())
print("V2_SYMBOLS=", v2["symbol"].nunique())
print("V2_PRIMARY_ROWS=", int(v2["primary_decision_unit"].astype(str).str.lower().eq("true").sum()))

print("STRUCT_ROWS=", len(struct))
print("STRUCT_UNIQUE_DECISIONS=", struct["decision_id"].nunique())
print("STRUCT_EVENTS=", struct["event_id"].nunique())

print("OUTCOME_ROWS=", len(outcome))
print("OUTCOME_UNIQUE_DECISIONS=", outcome["decision_id"].nunique())
print("OUTCOME_EVENTS=", outcome["event_id"].nunique())

print("\n=== CORE AUDIT ===")
checks = audit(struct, v2)
print("AUDIT=", checks)

id_struct = set(struct["decision_id"].astype(str))
id_outcome = set(outcome["decision_id"].astype(str))
id_v2 = set(v2["decision_id"].astype(str))
print("V2_EQUALS_STRUCT_ID_SET=", id_v2 == id_struct)
print("V2_EQUALS_OUTCOME_ID_SET=", id_v2 == id_outcome)

print("\n=== LEAKAGE / AGE ===")
print("DP1_AFTER_DECISION=", int((v2["dp1_timestamp_utc"] > v2["timestamp_utc"]).sum()))
print("SOURCE_AFTER_DECISION=", int((v2["source_max_timestamp_utc"] > v2["timestamp_utc"]).sum()))
print("NEGATIVE_EVENT_AGE=", int((pd.to_numeric(v2["event_minutes_from_dp1"], errors="coerce") < 0).sum()))
for c in [
    "event_minutes_since_last_touch",
    "event_minutes_since_last_cross",
    "event_minutes_since_last_reclaim",
    "event_minutes_since_last_loss",
    "event_minutes_since_last_rejection",
]:
    s = pd.to_numeric(v2[c], errors="coerce")
    print(f"{c.upper()}_NEGATIVE=", int((s.dropna() < 0).sum()))

print("\n=== REQUIRED FIELD COMPLETENESS ===")
required = [
    "rth_vwap_at_decision","directional_vwap_distance_pct",
    "directional_vwap_distance_min_from_dp1_pct",
    "directional_vwap_distance_max_from_dp1_pct",
    "event_vwap_touch_from_dp1","event_vwap_touch_count_from_dp1",
    "event_vwap_cross_from_dp1","event_vwap_cross_count_from_dp1",
    "event_favorable_close_fraction","event_adverse_close_fraction",
    "event_directional_rejection_seen","event_reclaim_seen","event_loss_seen",
    "source_max_timestamp_utc"
]
for c in required:
    print(f"MISSING_{c.upper()}=", int(v2[c].isna().sum()))

print("\n=== DP1 SANITY ===")
dp1 = v2[v2["decision_type"].astype(str).str.startswith("DP1_")].copy()
print("DP1_ROWS=", len(dp1))
print("DP1_NONZERO_EVENT_MINUTES=", int((pd.to_numeric(dp1["event_minutes_from_dp1"],errors="coerce") != 0).sum()))
print("DP1_SOURCE_AFTER_DECISION=", int((dp1["source_max_timestamp_utc"] > dp1["timestamp_utc"]).sum()))

print("\n=== V1/V2 DECISION VWAP PARITY ===")
j = v1[["decision_id","rth_vwap_at_decision"]].merge(
    v2[["decision_id","rth_vwap_at_decision"]],
    on="decision_id", suffixes=("_v1","_v2"), validate="one_to_one"
)
diff = (pd.to_numeric(j["rth_vwap_at_decision_v1"],errors="coerce") -
        pd.to_numeric(j["rth_vwap_at_decision_v2"],errors="coerce")).abs()
print("VWAP_PARITY_ROWS=", len(j))
print("VWAP_PARITY_MAX_ABS_DIFF=", float(diff.max()))
print("VWAP_PARITY_GT_1E_10=", int((diff > 1e-10).sum()))
print("VWAP_PARITY_GT_1E_8=", int((diff > 1e-8).sum()))

print("\n=== DECISION TYPES ===")
types = struct[["decision_type"]].drop_duplicates().sort_values("decision_type")
print(types.to_string(index=False))

print("\n=== STRUCTURAL-CLEARANCE FLAG DIAGNOSTIC ===")
flag = v2["event_vwap_loss_after_structural_clearance"].astype(str).str.lower().eq("true")
print("LOSS_AFTER_CLEARANCE_TRUE_ROWS=", int(flag.sum()))
if flag.any():
    print("FLAGGED_DECISION_TYPES=")
    print(v2.loc[flag,"decision_type"].value_counts().sort_index().to_string())

overall = (
    checks.get("PASS", False)
    and len(v2) == 450491
    and v2["decision_id"].nunique() == 450491
    and v2["event_id"].nunique() == 44627
    and v2["symbol"].nunique() == 112
    and id_v2 == id_struct == id_outcome
    and int((v2["dp1_timestamp_utc"] > v2["timestamp_utc"]).sum()) == 0
    and int((v2["source_max_timestamp_utc"] > v2["timestamp_utc"]).sum()) == 0
    and int((pd.to_numeric(v2["event_minutes_from_dp1"], errors="coerce") < 0).sum()) == 0
    and int(v2["rth_vwap_at_decision"].isna().sum()) == 0
    and int((diff > 1e-8).sum()) == 0
)
print("\nFULL_V2_INTEGRITY_CERTIFICATION=", "PASS" if overall else "FAIL")
print("NOTE=Structural-clearance semantics are printed above for final protocol review before outcome analysis.")
'@
