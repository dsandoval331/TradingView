from pathlib import Path
import json
import pandas as pd

ROOT = Path.cwd()

CANDIDATES = {
    "decision_research": ROOT / "pmpd_v5_9h_research_dataset_v1" / "decision_research.csv",
    "decision_enrichment": ROOT / "pmpd_v5_9h_enrichment_v1" / "decision_enrichment.csv",
    "vwap_dp4fix_outcomes": ROOT / "pmpd_v5_9j_vwap_event_path_v2_analysis" / "decision_vwap_event_path_v2_dp4fix_with_frozen_outcome.csv",
}

def find_col(cols, exact=(), contains=()):
    lower = {c.lower(): c for c in cols}
    for x in exact:
        if x.lower() in lower:
            return lower[x.lower()]
    for c in cols:
        lc = c.lower()
        if all(tok.lower() in lc for tok in contains):
            return c
    return None

report = {"protocol":"PMPD_V5_9K_DP4_MATRIX_PREFLIGHT_V1","files":{},"gates":{}}
frames = {}

print("=== 9K-2 DP4 CANDIDATE MATRIX PREFLIGHT ===")
for name, path in CANDIDATES.items():
    exists = path.exists()
    print(f"{name}: {path} exists={exists}")
    report["files"][name] = {"path":str(path),"exists":exists}
    if not exists:
        continue
    df = pd.read_csv(path, low_memory=False)
    frames[name] = df
    report["files"][name].update({"rows":int(len(df)),"columns":int(len(df.columns))})
    print(f"  rows={len(df)} columns={len(df.columns)}")

all_exist = len(frames) == len(CANDIDATES)
report["gates"]["all_inputs_exist"] = all_exist
if not all_exist:
    print("PREFLIGHT_GATE=FAIL_MISSING_INPUT")
    Path("pmpd_v5_9k_dp4_matrix_preflight.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    raise SystemExit(2)

# Identify key columns without using outcomes analytically.
key_info = {}
for name, df in frames.items():
    cols=list(df.columns)
    decision_id=find_col(cols, exact=("decision_id",))
    decision_type=find_col(cols, exact=("decision_type","decision_point_type"), contains=("decision","type"))
    direction=find_col(cols, exact=("direction",))
    symbol=find_col(cols, exact=("symbol","ticker"))
    partition=find_col(cols, exact=("research_partition","partition"))
    outcome=find_col(cols, exact=("frozen_primary_outcome","outcome"))
    key_info[name]={
        "decision_id":decision_id,"decision_type":decision_type,"direction":direction,
        "symbol":symbol,"partition":partition,"outcome":outcome
    }
    print(f"\n{name} key columns: {key_info[name]}")

report["key_columns"]=key_info

# Decision ID uniqueness / overlap only.
for name, df in frames.items():
    did=key_info[name]["decision_id"]
    if did:
        report["files"][name]["unique_decision_ids"]=int(df[did].nunique(dropna=True))
        report["files"][name]["duplicate_decision_ids"]=int(df[did].duplicated().sum())

base=frames["decision_research"]
base_did=key_info["decision_research"]["decision_id"]
base_dtype=key_info["decision_research"]["decision_type"]
if not base_did or not base_dtype:
    print("PREFLIGHT_GATE=FAIL_KEY_COLUMNS")
    report["gates"]["base_key_columns"]=False
    Path("pmpd_v5_9k_dp4_matrix_preflight.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    raise SystemExit(3)
report["gates"]["base_key_columns"]=True

dp4_mask=base[base_dtype].astype(str).str.upper().eq("DP4_FULL_STACK_FIRST_CLEAR")
dp4=base.loc[dp4_mask].copy()
report["dp4_rows_all_occurrences"]=int(len(dp4))
report["dp4_unique_decisions"]=int(dp4[base_did].nunique())
print(f"\nDP4_FULL_STACK_FIRST_CLEAR rows={len(dp4)} unique_decisions={dp4[base_did].nunique()}")

# Print possible primary/first-occurrence eligibility columns.
eligibility_candidates=[
    c for c in base.columns
    if any(tok in c.lower() for tok in ("primary","eligible","first_occurrence","first_occur","research_unit"))
]
print("\nPossible primary-inference / first-occurrence columns:")
for c in eligibility_candidates:
    vals=base[c].dropna().astype(str).value_counts().head(8).to_dict()
    print(f"  {c}: {vals}")
report["primary_eligibility_candidate_columns"]=eligibility_candidates

# Feature-name discovery only. No outcome stratification.
feature_tokens=("scale","gap","minute","time","vwap","touch","cross","rejection","distance")
feature_hits={}
for name, df in frames.items():
    hits=[c for c in df.columns if any(tok in c.lower() for tok in feature_tokens)]
    feature_hits[name]=hits
    print(f"\n{name} candidate feature columns:")
    for c in hits:
        print(" ",c)
report["candidate_feature_columns"]=feature_hits

# DP4 decision-ID overlap across certified sources.
base_dp4_ids=set(dp4[base_did].dropna().astype(str))
for name in ("decision_enrichment","vwap_dp4fix_outcomes"):
    df=frames[name]
    did=key_info[name]["decision_id"]
    if did:
        ids=set(df[did].dropna().astype(str))
        matched=len(base_dp4_ids & ids)
        report["files"][name]["dp4_id_overlap_with_base"]=matched
        report["files"][name]["dp4_id_missing_from_source"]=len(base_dp4_ids-ids)
        print(f"\n{name}: DP4 ID overlap={matched}, missing={len(base_dp4_ids-ids)}")

# Hard anti-peek declaration.
report["gates"]["outcome_relationships_characterized"]=False
report["gates"]["thresholds_fit"]=False
report["gates"]["model_fit"]=False
report["gates"]["production_rule_authorized"]=False

out_path=ROOT/"pmpd_v5_9k_dp4_matrix_preflight.json"
out_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
print(f"\nREPORT={out_path}")
print("OUTCOME_RELATIONSHIPS_CHARACTERIZED=False")
print("THRESHOLDS_FIT=False")
print("MODEL_FIT=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("PREFLIGHT_GATE=PASS")
