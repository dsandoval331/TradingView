from pathlib import Path
import pandas as pd

root = Path(".").resolve()

def pick(*candidates):
    for rel in candidates:
        p = root / rel
        if p.exists():
            return p
    raise FileNotFoundError("None found: " + ", ".join(candidates))

v2_path = pick(
    "pmpd_v5_9j_vwap_event_path_v2/decision_vwap_event_path_v2.csv",
    "pmpd_v5_9j_vwap_event_path_v2_full/decision_vwap_event_path_v2.csv",
)
struct_path = pick(
    "pmpd_v5_alpha_0_2_full_universe/decision_points.csv",
    "pmpd_v5_alpha_certification/run_1/decision_points.csv",
)
outcome_path = pick("pmpd_v5_9h_research_dataset_v1/decision_research.csv")
v1_path = pick(
    "pmpd_v5_9j_vwap_enrichment_v1/decision_vwap_enrichment.csv",
    "pmpd_v5_9j_vwap_enrichment_v1/decision_enrichment.csv",
)

v2 = pd.read_csv(v2_path)
struct = pd.read_csv(struct_path)
outcome = pd.read_csv(outcome_path)
v1 = pd.read_csv(v1_path)

for df, cols in [
    (v2, ["timestamp_utc","dp1_timestamp_utc","source_max_timestamp_utc"]),
    (struct, ["timestamp_utc"]),
]:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, errors="raise")

def true_count(series):
    return int(series.astype(str).str.lower().eq("true").sum())

print("=== FILES ===")
print("V2=", v2_path)
print("STRUCTURAL_PARENT=", struct_path)
print("OUTCOME_PARENT=", outcome_path)
print("V1=", v1_path)

print("\n=== POPULATION ===")
print("V2_ROWS=", len(v2))
print("V2_UNIQUE_DECISIONS=", v2["decision_id"].nunique())
print("V2_EVENTS=", v2["event_id"].nunique())
print("V2_SYMBOLS=", v2["symbol"].nunique())
print("V2_PRIMARY_ROWS=", true_count(v2["primary_decision_unit"]))
print("STRUCT_ROWS=", len(struct))
print("STRUCT_UNIQUE_DECISIONS=", struct["decision_id"].nunique())
print("STRUCT_EVENTS=", struct["event_id"].nunique())
print("OUTCOME_ROWS=", len(outcome))
print("OUTCOME_UNIQUE_DECISIONS=", outcome["decision_id"].nunique())
print("OUTCOME_EVENTS=", outcome["event_id"].nunique())

print("\n=== ID / PARENT PARITY ===")
ids_v2 = set(v2["decision_id"].astype(str))
ids_struct = set(struct["decision_id"].astype(str))
ids_out = set(outcome["decision_id"].astype(str))
print("V2_EQUALS_STRUCT_ID_SET=", ids_v2 == ids_struct)
print("V2_EQUALS_OUTCOME_ID_SET=", ids_v2 == ids_out)

# Structural identity parity on stable fields.
stable = ["decision_id","event_id","decision_type","direction"]
if "timestamp_utc" in struct.columns and "timestamp_utc" in v2.columns:
    stable.append("timestamp_utc")
a = struct[stable].copy()
b = v2[stable].copy()
if "timestamp_utc" in stable:
    a["timestamp_utc"] = pd.to_datetime(a["timestamp_utc"], utc=True)
    b["timestamp_utc"] = pd.to_datetime(b["timestamp_utc"], utc=True)
m = a.merge(b, on="decision_id", suffixes=("_parent","_v2"), validate="one_to_one")
identity_mismatches = {}
for c in [x for x in stable if x != "decision_id"]:
    left = m[f"{c}_parent"]
    right = m[f"{c}_v2"]
    identity_mismatches[c] = int((left != right).sum())
    print(f"IDENTITY_MISMATCH_{c.upper()}=", identity_mismatches[c])

print("\n=== LEAKAGE / AGE ===")
dp1_after = int((v2["dp1_timestamp_utc"] > v2["timestamp_utc"]).sum())
src_after = int((v2["source_max_timestamp_utc"] > v2["timestamp_utc"]).sum())
neg_age = int((pd.to_numeric(v2["event_minutes_from_dp1"], errors="coerce") < 0).sum())
print("DP1_AFTER_DECISION=", dp1_after)
print("SOURCE_AFTER_DECISION=", src_after)
print("NEGATIVE_EVENT_AGE=", neg_age)

age_cols = [
    "event_minutes_since_last_touch",
    "event_minutes_since_last_cross",
    "event_minutes_since_last_reclaim",
    "event_minutes_since_last_loss",
    "event_minutes_since_last_rejection",
]
negative_age_counts = {}
for c in age_cols:
    s = pd.to_numeric(v2[c], errors="coerce")
    negative_age_counts[c] = int((s.dropna() < 0).sum())
    print(c.upper()+"_NEGATIVE=", negative_age_counts[c])

print("\n=== REQUIRED FIELD COMPLETENESS ===")
required_zero_missing = [
    "rth_vwap_at_decision",
    "directional_vwap_distance_pct",
    "directional_vwap_distance_min_from_dp1_pct",
    "directional_vwap_distance_max_from_dp1_pct",
    "event_vwap_touch_from_dp1",
    "event_vwap_touch_count_from_dp1",
    "event_vwap_cross_from_dp1",
    "event_vwap_cross_count_from_dp1",
    "event_favorable_close_fraction",
    "event_adverse_close_fraction",
    "event_directional_rejection_seen",
    "event_reclaim_seen",
    "event_loss_seen",
    "source_max_timestamp_utc",
]
missing_counts = {}
for c in required_zero_missing:
    missing_counts[c] = int(v2[c].isna().sum())
    print("MISSING_"+c.upper()+"=", missing_counts[c])

print("\n=== DP1 SANITY ===")
dp1 = v2[v2["decision_type"].astype(str).str.startswith("DP1_")].copy()
dp1_nonzero = int((pd.to_numeric(dp1["event_minutes_from_dp1"], errors="coerce") != 0).sum())
dp1_src_after = int((dp1["source_max_timestamp_utc"] > dp1["timestamp_utc"]).sum())
print("DP1_ROWS=", len(dp1))
print("DP1_NONZERO_EVENT_MINUTES=", dp1_nonzero)
print("DP1_SOURCE_AFTER_DECISION=", dp1_src_after)

print("\n=== V1/V2 DECISION VWAP PARITY ===")
j = v1[["decision_id","rth_vwap_at_decision"]].merge(
    v2[["decision_id","rth_vwap_at_decision"]],
    on="decision_id", suffixes=("_v1","_v2"), validate="one_to_one"
)
diff = (
    pd.to_numeric(j["rth_vwap_at_decision_v1"], errors="coerce")
    - pd.to_numeric(j["rth_vwap_at_decision_v2"], errors="coerce")
).abs()
vwap_gt_1e10 = int((diff > 1e-10).sum())
vwap_gt_1e8 = int((diff > 1e-8).sum())
print("VWAP_PARITY_ROWS=", len(j))
print("VWAP_PARITY_MAX_ABS_DIFF=", float(diff.max()))
print("VWAP_PARITY_GT_1E_10=", vwap_gt_1e10)
print("VWAP_PARITY_GT_1E_8=", vwap_gt_1e8)

print("\n=== SPLIT PARITY ===")
if "split" in outcome.columns:
    print(outcome["split"].value_counts(dropna=False).sort_index().to_string())

print("\n=== DECISION TYPES ===")
print(struct[["decision_type"]].drop_duplicates().sort_values("decision_type").to_string(index=False))

print("\n=== STRUCTURAL-CLEARANCE FLAG DIAGNOSTIC ===")
flag = v2["event_vwap_loss_after_structural_clearance"].astype(str).str.lower().eq("true")
print("LOSS_AFTER_CLEARANCE_TRUE_ROWS=", int(flag.sum()))
if flag.any():
    print("FLAGGED_DECISION_TYPES=")
    print(v2.loc[flag, "decision_type"].value_counts().sort_index().to_string())

population_pass = (
    len(v2) == 450491
    and v2["decision_id"].nunique() == 450491
    and v2["event_id"].nunique() == 44627
    and v2["symbol"].nunique() == 112
    and len(struct) == 450491
    and len(outcome) == 450491
)
id_pass = ids_v2 == ids_struct == ids_out
identity_pass = all(v == 0 for v in identity_mismatches.values())
temporal_pass = (
    dp1_after == 0 and src_after == 0 and neg_age == 0
    and all(v == 0 for v in negative_age_counts.values())
    and dp1_nonzero == 0 and dp1_src_after == 0
)
completeness_pass = all(v == 0 for v in missing_counts.values())
vwap_pass = len(j) == 450491 and vwap_gt_1e8 == 0

print("\n=== CERTIFICATION GATES ===")
print("POPULATION_GATE=", "PASS" if population_pass else "FAIL")
print("ID_SET_GATE=", "PASS" if id_pass else "FAIL")
print("STRUCTURAL_IDENTITY_GATE=", "PASS" if identity_pass else "FAIL")
print("TEMPORAL_LEAKAGE_GATE=", "PASS" if temporal_pass else "FAIL")
print("FIELD_COMPLETENESS_GATE=", "PASS" if completeness_pass else "FAIL")
print("V1_V2_VWAP_PARITY_GATE=", "PASS" if vwap_pass else "FAIL")

overall = population_pass and id_pass and identity_pass and temporal_pass and completeness_pass and vwap_pass
print("\nFULL_V2_INTEGRITY_CERTIFICATION=" + ("PASS" if overall else "FAIL"))
print("NOTE=Structural-clearance semantics remain a separate methodology review and do not invalidate the structural V2 certification unless the feature definition itself is used analytically.")
