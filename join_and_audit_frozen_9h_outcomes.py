from pathlib import Path
import json, re, hashlib
import numpy as np
import pandas as pd

ROOT = Path(".").resolve()
FEATURES = ROOT / "pmpd_v5_9j_vwap_event_path_v2_dp4fix" / "decision_vwap_event_path_v2_dp4fix.csv"
PARENT = ROOT / "pmpd_v5_9h_research_dataset_v1" / "decision_research.csv"
OUT_DIR = ROOT / "pmpd_v5_9j_vwap_event_path_v2_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "decision_vwap_event_path_v2_dp4fix_with_frozen_outcome.csv"
AUDIT = OUT_DIR / "frozen_outcome_join_audit.json"

EXPECTED_ROWS = 450491
EXPECTED_FEATURE_FP = "9db7404bbf69d9b31b5ad93edfce943bdc515b70146e0d07f0fdda331f9a3a57"

print("=== INPUTS ===")
print("FEATURES =", FEATURES, "exists=", FEATURES.exists())
print("PARENT =", PARENT, "exists=", PARENT.exists())
if not FEATURES.exists() or not PARENT.exists():
    raise SystemExit("MISSING_INPUT")

f = pd.read_csv(FEATURES, low_memory=False)
p = pd.read_csv(PARENT, low_memory=False)

print("\n=== POPULATION ===")
print("feature_rows =", len(f))
print("feature_unique_decisions =", f["decision_id"].nunique())
print("parent_rows =", len(p))
print("parent_unique_decisions =", p["decision_id"].nunique())

if len(f) != EXPECTED_ROWS or f["decision_id"].nunique() != EXPECTED_ROWS:
    raise SystemExit("FEATURE_POPULATION_GATE=FAIL")
if len(p) != EXPECTED_ROWS or p["decision_id"].nunique() != EXPECTED_ROWS:
    raise SystemExit("PARENT_POPULATION_GATE=FAIL")
if set(f["decision_id"]) != set(p["decision_id"]):
    raise SystemExit("DECISION_ID_SET_GATE=FAIL")

print("\n=== FROZEN 9H OUTCOME-SCHEMA DISCOVERY ===")
outcome_terms = re.compile(
    r"(outcome|favorable|adverse|target|stop|first|hit|mfe|mae|forward|success|failure|winner|loser)",
    re.I,
)
candidate_cols = [c for c in p.columns if outcome_terms.search(c)]
print("candidate_outcome_columns =", candidate_cols)

# Print compact diagnostics for candidate columns.
for c in candidate_cols:
    s = p[c]
    nonnull = int(s.notna().sum())
    nunique = int(s.nunique(dropna=True))
    vals = []
    if nunique <= 20:
        vals = [str(x) for x in s.dropna().value_counts().head(20).index.tolist()]
    print(f"{c}: dtype={s.dtype} nonnull={nonnull} nunique={nunique} values={vals}")

# Supported direct boolean representations.
fav_bool_names = [
    "favorable_first", "favorable_before_adverse", "favorable_first_0_5",
    "favorable_0_5_before_adverse_0_5", "primary_favorable_first",
    "target_before_stop", "win_0_5_before_loss_0_5"
]
adv_bool_names = [
    "adverse_first", "adverse_before_favorable", "adverse_first_0_5",
    "adverse_0_5_before_favorable_0_5", "primary_adverse_first",
    "stop_before_target"
]
label_names = [
    "outcome", "outcome_label", "primary_outcome", "first_reached",
    "first_reached_label", "primary_first_reached", "result", "result_label"
]

def as_bool(s):
    if pd.api.types.is_bool_dtype(s):
        return s.astype("boolean")
    if pd.api.types.is_numeric_dtype(s):
        vals = set(pd.to_numeric(s, errors="coerce").dropna().unique().tolist())
        if vals.issubset({0,1,0.0,1.0}):
            return pd.to_numeric(s, errors="coerce").astype("Int64").astype("boolean")
    z = s.astype(str).str.strip().str.lower()
    mapping = {
        "true": True, "false": False, "1": True, "0": False,
        "yes": True, "no": False, "y": True, "n": False
    }
    mapped = z.map(mapping)
    if mapped.notna().sum() == s.notna().sum():
        return mapped.astype("boolean")
    return None

resolved = None
resolution = None

# Case 1: skip the lossy direct favorable-first boolean when the canonical
# categorical first-reached outcome is available. FALSE cannot distinguish
# ADVERSE_FIRST from UNRESOLVED / AMBIGUOUS_SAME_BAR.
pass

# Case 2: paired booleans, preferred over a single negated boolean when available.
if resolution is None and "outcome" not in p.columns:
    fav_hits = []
    adv_hits = []
    for c in fav_bool_names:
        if c in p.columns:
            b = as_bool(p[c])
            if b is not None:
                fav_hits.append((c,b))
    for c in adv_bool_names:
        if c in p.columns:
            b = as_bool(p[c])
            if b is not None:
                adv_hits.append((c,b))
    if len(fav_hits) == 1 and len(adv_hits) == 1:
        fc, fb = fav_hits[0]
        ac, ab = adv_hits[0]
        resolved = pd.Series(pd.NA, index=p.index, dtype="string")
        resolved.loc[(fb == True) & (ab != True)] = "FAVORABLE_FIRST"
        resolved.loc[(ab == True) & (fb != True)] = "ADVERSE_FIRST"
        resolved.loc[(fb == False) & (ab == False)] = "NEITHER_OR_UNRESOLVED"
        resolved.loc[(fb == True) & (ab == True)] = "AMBIGUOUS_BOTH_TRUE"
        resolution = {"type":"paired_boolean","favorable_column":fc,"adverse_column":ac}

# Case 3: categorical label.
if resolution is None:
    possible = [c for c in label_names if c in p.columns]
    if len(possible) == 1:
        c = possible[0]
        z = p[c].astype(str).str.strip().str.lower()
        resolved = pd.Series(pd.NA, index=p.index, dtype="string")
        fav_pat = z.str.contains(r"favor|target|win|positive", regex=True, na=False)
        adv_pat = z.str.contains(r"adverse|stop|loss|negative", regex=True, na=False)
        neither_pat = z.str.contains(r"neither|none|unresolved|censor|no_hit|no hit", regex=True, na=False)
        ambiguous_pat = z.eq("ambiguous_same_bar")
        resolved.loc[fav_pat & ~adv_pat] = "FAVORABLE_FIRST"
        resolved.loc[adv_pat & ~fav_pat] = "ADVERSE_FIRST"
        resolved.loc[neither_pat & ~fav_pat & ~adv_pat] = "UNRESOLVED"
        resolved.loc[ambiguous_pat] = "AMBIGUOUS_SAME_BAR"
        unknown = p[c].notna() & resolved.isna()
        if unknown.any():
            print("\nUNMAPPED_LABEL_VALUES =", p.loc[unknown,c].value_counts().head(30).to_dict())
            resolved = None
        else:
            resolution = {"type":"categorical_label","column":c}

if resolution is None:
    print("\nOUTCOME_RESOLUTION=AMBIGUOUS_OR_UNRECOGNIZED")
    print("No output file was written.")
    print("Please paste this complete schema-discovery output.")
    raise SystemExit(3)

print("\n=== OUTCOME RESOLUTION ===")
print(json.dumps(resolution, indent=2))
print(resolved.value_counts(dropna=False).to_string())

# Direct favorable bool can only safely identify FAVORABLE_FIRST vs NOT_FAVORABLE_FIRST.
# Primary research needs favorable-first BEFORE adverse-first, so reject if it cannot distinguish adverse/neither.
if resolution["type"] == "direct_favorable_bool":
    print("\nOUTCOME_RESOLUTION_GATE=FAIL")
    print("A favorable-first boolean was found, but FALSE may combine adverse-first and unresolved/neither.")
    print("Need an explicit adverse-first indicator or categorical first-reached outcome before analysis.")
    raise SystemExit(4)

if (resolved == "AMBIGUOUS_BOTH_TRUE").any():
    raise SystemExit("OUTCOME_MUTUAL_EXCLUSIVITY_GATE=FAIL")

print("\n=== JOIN ===")
outcome_frame = pd.DataFrame({
    "decision_id": p["decision_id"],
    "frozen_primary_outcome": resolved
})
j = f.merge(outcome_frame, on="decision_id", how="left", validate="one_to_one")
print("join_rows =", len(j))
print("missing_outcome_rows =", int(j["frozen_primary_outcome"].isna().sum()))
if len(j) != EXPECTED_ROWS:
    raise SystemExit("JOIN_ROW_COUNT_GATE=FAIL")
if j["frozen_primary_outcome"].isna().any():
    raise SystemExit("JOIN_MISSING_OUTCOME_GATE=FAIL")

print("\n=== PARTITION ASSIGNMENT ===")
ts = pd.to_datetime(j["timestamp_utc"], utc=True, errors="coerce")
trade_date = ts.dt.date
disc = (trade_date >= pd.Timestamp("2025-01-02").date()) & (trade_date <= pd.Timestamp("2025-04-30").date())
va = (trade_date >= pd.Timestamp("2025-05-01").date()) & (trade_date <= pd.Timestamp("2025-08-29").date())
vb = (trade_date >= pd.Timestamp("2025-09-02").date()) & (trade_date <= pd.Timestamp("2025-12-31").date())
j["research_partition"] = np.select([disc,va,vb],["DISCOVERY","VALIDATION_A","VALIDATION_B"],default="UNASSIGNED")
print(j["research_partition"].value_counts().to_string())
if (j["research_partition"] == "UNASSIGNED").any():
    raise SystemExit("PARTITION_GATE=FAIL")

# Guardrail: no outcome-based characterization is printed by partition here.
# This runner only establishes the audited join.
print("\n=== WRITE AUDITED JOIN ===")
j.to_csv(OUT, index=False)

finger_cols = ["decision_id","frozen_primary_outcome","research_partition","source_v2_fingerprint"]
ff = j[finger_cols].astype(str).sort_values("decision_id")
join_fp = hashlib.sha256(ff.to_csv(index=False).encode("utf-8")).hexdigest()

audit = {
    "status":"PASS",
    "feature_source":"PMPD_V5_9J_VWAP_EVENT_PATH_V2_DP4FIX",
    "feature_fingerprint":EXPECTED_FEATURE_FP,
    "rows":int(len(j)),
    "unique_decisions":int(j["decision_id"].nunique()),
    "outcome_resolution":resolution,
    "outcome_counts":{str(k):int(v) for k,v in resolved.value_counts(dropna=False).items()},
    "partition_counts":{str(k):int(v) for k,v in j["research_partition"].value_counts().items()},
    "join_fingerprint":join_fp,
    "validation_outcomes_not_characterized":True,
    "join_key":"decision_id",
}
AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")

print("FROZEN_OUTCOME_JOIN_GATE=PASS")
print("JOIN_FINGERPRINT =", join_fp)
print("OUTPUT =", OUT)
print("AUDIT =", AUDIT)
print("VALIDATION_OUTCOMES_CHARACTERIZED = False")
