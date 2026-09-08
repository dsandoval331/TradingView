from pathlib import Path
import pandas as pd, json, hashlib, numpy as np

ROOT=Path.cwd()
D=ROOT/"pmpd_v5_9j_vwap_event_path_v2_analysis"/"discovery_stage1_restricted"
OUT=D/"discovery_evidence_summary"
OUT.mkdir(parents=True,exist_ok=True)

files={
 "population":D/"discovery_population_summary.csv",
 "decision":D/"discovery_by_decision_type.csv",
 "features":D/"discovery_feature_summary.csv",
 "cutpoints":D/"discovery_unconditional_quantile_cutpoints.csv",
 "bins":D/"discovery_quantile_bin_outcomes.csv",
 "booleans":D/"discovery_boolean_state_outcomes.csv",
 "symbols":D/"discovery_symbol_cluster_summary.csv",
 "manifest":D/"discovery_stage1_manifest.json",
}
for k,p in files.items():
    print(k,p.exists(),p)
    if not p.exists(): raise SystemExit(f"MISSING_{k}")

pop=pd.read_csv(files["population"])
dec=pd.read_csv(files["decision"])
feat=pd.read_csv(files["features"])
cuts=pd.read_csv(files["cutpoints"])
bins=pd.read_csv(files["bins"])
boo=pd.read_csv(files["booleans"])
sym=pd.read_csv(files["symbols"])
manifest=json.loads(files["manifest"].read_text())

if manifest.get("validation_outcomes_characterized") is not False:
    raise SystemExit("ANTI_PEEK_MANIFEST_FAIL")
if manifest.get("discovery_rows_analyzed") != 145692:
    raise SystemExit("DISCOVERY_COUNT_FAIL")

# Rank continuous features by quartile outcome spread within Discovery.
rank=[]
for (f,s),g in bins.groupby(["feature","scope"]):
    if len(g)<2: continue
    rates=g["resolved_favorable_rate"].dropna()
    ns=g["resolved_n"].fillna(0)
    if len(rates)<2 or ns.min()<200: continue
    spread=float(rates.max()-rates.min())
    # monotonicity is descriptive only.
    gg=g.set_index("bin").reindex(["Q1","Q2","Q3","Q4"])
    rr=gg["resolved_favorable_rate"].to_numpy(float)
    mono_inc=bool(np.all(np.diff(rr[~np.isnan(rr)])>=0)) if np.sum(~np.isnan(rr))>=3 else False
    mono_dec=bool(np.all(np.diff(rr[~np.isnan(rr)])<=0)) if np.sum(~np.isnan(rr))>=3 else False
    rank.append({"feature":f,"scope":s,"quartile_rate_spread":spread,
                 "min_resolved_bin_n":int(ns.min()),
                 "monotonic_descriptive":mono_inc or mono_dec})
rank=pd.DataFrame(rank).sort_values("quartile_rate_spread",ascending=False)
rank.to_csv(OUT/"continuous_feature_discovery_ranking.csv",index=False)

# Boolean state deltas.
br=[]
for (f,s),g in boo.groupby(["feature","scope"]):
    x=g.set_index("value")
    if 0 not in x.index or 1 not in x.index: continue
    if min(x.loc[0,"resolved_n"],x.loc[1,"resolved_n"])<200: continue
    delta=float(x.loc[1,"resolved_favorable_rate"]-x.loc[0,"resolved_favorable_rate"])
    br.append({"feature":f,"scope":s,"true_minus_false_rate_delta":delta,
               "abs_delta":abs(delta),
               "false_resolved_n":int(x.loc[0,"resolved_n"]),
               "true_resolved_n":int(x.loc[1,"resolved_n"])})
br=pd.DataFrame(br).sort_values("abs_delta",ascending=False)
br.to_csv(OUT/"boolean_feature_discovery_ranking.csv",index=False)

# Directional concordance screen: same feature needs evidence in BULL and BEAR.
conc=[]
for f,g in rank[rank["scope"].isin(["BULL","BEAR"])].groupby("feature"):
    if set(g["scope"])=={"BULL","BEAR"}:
        b=g.set_index("scope")
        conc.append({"feature":f,
                     "bull_spread":float(b.loc["BULL","quartile_rate_spread"]),
                     "bear_spread":float(b.loc["BEAR","quartile_rate_spread"]),
                     "min_directional_spread":float(min(b.loc["BULL","quartile_rate_spread"],b.loc["BEAR","quartile_rate_spread"])),
                     "bull_monotonic":bool(b.loc["BULL","monotonic_descriptive"]),
                     "bear_monotonic":bool(b.loc["BEAR","monotonic_descriptive"])})
conc=pd.DataFrame(conc).sort_values("min_directional_spread",ascending=False)
conc.to_csv(OUT/"continuous_directional_concordance.csv",index=False)

# Candidate freeze sheet: pre-specified unconditional quartiles only.
# This is NOT an authorization to validate all candidates. It provides evidence
# for adjudicating a compact frozen set without optimizing threshold values.
top_features=set()
if len(conc):
    top_features.update(conc.head(6)["feature"])
if len(rank):
    top_features.update(rank[rank["scope"]=="ALL"].head(6)["feature"])
candidate=cuts[cuts["feature"].isin(top_features)].copy()
candidate.to_csv(OUT/"candidate_freeze_sheet.csv",index=False)

print("\n=== DISCOVERY POPULATION ===")
print(pop.to_string(index=False))
print("\n=== TOP CONTINUOUS DISCOVERY SEPARATION ===")
print(rank.head(20).to_string(index=False))
print("\n=== DIRECTIONAL CONCORDANCE ===")
print(conc.head(15).to_string(index=False))
print("\n=== BOOLEAN STATE DELTAS ===")
print(br.head(15).to_string(index=False))
print("\nCANDIDATE_FREEZE_FEATURES =",sorted(top_features))
print("CANDIDATE_FREEZE_ROWS =",len(candidate))
print("DISCOVERY_EVIDENCE_SUMMARY_GATE=PASS")
print("VALIDATION_OUTCOMES_CHARACTERIZED=False")
print("THRESHOLD_OPTIMIZATION_PERFORMED=False")
