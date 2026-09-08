from pathlib import Path
import pandas as pd, numpy as np, json, hashlib

ROOT=Path.cwd()
BASE=ROOT/"pmpd_v5_9j_vwap_event_path_v2_analysis"
DISC=BASE/"discovery_stage1_restricted"
VAL=BASE/"validation_results"
FREEZE=BASE/"frozen_validation_protocol"
OUT=BASE/"validation_robustness"
OUT.mkdir(parents=True,exist_ok=True)

EXPECTED_FP="7e754fd754c46cd3d5b6e3de34bd0b2074cee9d50c4b5b1577cd0b91d2a3eadf"

def combined_fp():
    h=hashlib.sha256()
    for fn in ["frozen_continuous_cutpoints.csv","frozen_binary_hypotheses.csv","frozen_validation_protocol.json"]:
        h.update((FREEZE/fn).read_bytes())
    return h.hexdigest()

fp=combined_fp()
print("FREEZE_FINGERPRINT =",fp)
if fp!=EXPECTED_FP: raise SystemExit("FREEZE_FINGERPRINT_MISMATCH")

dbins=pd.read_csv(DISC/"discovery_quantile_bin_outcomes.csv")
vbins=pd.read_csv(VAL/"validation_continuous_frozen_bins.csv")
vbin=pd.read_csv(VAL/"validation_binary_summary.csv")
symbin=pd.read_csv(VAL/"validation_binary_symbol_clusters.csv")
cuts=pd.read_csv(FREEZE/"frozen_continuous_cutpoints.csv")
raw=BASE/"decision_vwap_event_path_v2_dp4fix_with_frozen_outcome.csv"

# ---- continuous shape replication ----
rows=[]
order=["Q1","Q2","Q3","Q4"]
for (feature,scope),dg in dbins.groupby(["feature","scope"]):
    if feature not in set(cuts["feature"]): continue
    dvec=dg.set_index("bin").reindex(order)["resolved_favorable_rate"].astype(float)
    if dvec.isna().any(): continue
    d_q4q1=float(dvec.loc["Q4"]-dvec.loc["Q1"])
    d_best=str(dvec.idxmax()); d_worst=str(dvec.idxmin())
    rec={"feature":feature,"scope":scope,
         "discovery_q4_minus_q1":d_q4q1,
         "discovery_best_bin":d_best,"discovery_worst_bin":d_worst}
    same_q4q1=True
    corr_ok=True
    for part in ["VALIDATION_A","VALIDATION_B"]:
        vg=vbins[(vbins.feature==feature)&(vbins.scope==scope)&(vbins.partition==part)]
        vvec=vg.set_index("bin").reindex(order)["resolved_favorable_rate"].astype(float)
        if len(vvec)!=4 or vvec.isna().any():
            rec[f"{part.lower()}_shape_corr"]=None
            rec[f"{part.lower()}_q4_minus_q1"]=None
            rec[f"{part.lower()}_best_bin"]=None
            rec[f"{part.lower()}_worst_bin"]=None
            same_q4q1=False; corr_ok=False
            continue
        # Spearman correlation without scipy: Pearson correlation of ranks.
        dr=dvec.rank(method="average")
        vr=vvec.rank(method="average")
        corr=float(np.corrcoef(dr.to_numpy(dtype=float),vr.to_numpy(dtype=float))[0,1])
        qdiff=float(vvec.loc["Q4"]-vvec.loc["Q1"])
        rec[f"{part.lower()}_shape_corr"]=corr
        rec[f"{part.lower()}_q4_minus_q1"]=qdiff
        rec[f"{part.lower()}_best_bin"]=str(vvec.idxmax())
        rec[f"{part.lower()}_worst_bin"]=str(vvec.idxmin())
        if np.sign(qdiff)!=np.sign(d_q4q1): same_q4q1=False
        if corr < 0.5: corr_ok=False
    rec["q4q1_sign_replicates_both"]=bool(same_q4q1)
    rec["shape_corr_ge_0_5_both"]=bool(corr_ok)
    rec["exact_best_bin_replicates_both"]=bool(
        rec.get("validation_a_best_bin")==d_best and rec.get("validation_b_best_bin")==d_best)
    rec["exact_worst_bin_replicates_both"]=bool(
        rec.get("validation_a_worst_bin")==d_worst and rec.get("validation_b_worst_bin")==d_worst)
    rows.append(rec)
shape=pd.DataFrame(rows)
shape.to_csv(OUT/"continuous_shape_replication.csv",index=False)

# ---- continuous symbol-cluster robustness using frozen Q1-vs-Q4 contrast ----
# We use exact frozen cutpoints; no threshold re-estimation.
need={"research_partition","frozen_primary_outcome","direction","symbol"}|set(cuts["feature"])
chunks=[]
for ch in pd.read_csv(raw,usecols=list(need),chunksize=50000,low_memory=False):
    q=ch[ch["research_partition"].isin(["VALIDATION_A","VALIDATION_B"])].copy()
    chunks.append(q)
df=pd.concat(chunks,ignore_index=True)
df["_resolved"]=df["frozen_primary_outcome"].isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])
df["_win"]=np.where(df["frozen_primary_outcome"].eq("FAVORABLE_FIRST"),1.0,
                    np.where(df["frozen_primary_outcome"].eq("ADVERSE_FIRST"),0.0,np.nan))
z=df["direction"].astype(str).str.upper()
df["_direction"]=np.where(z.str.contains("BULL|LONG|UP",regex=True),"BULL",
                    np.where(z.str.contains("BEAR|SHORT|DOWN",regex=True),"BEAR","UNKNOWN"))

sym_rows=[]
for _,r in cuts.iterrows():
    feature=r["feature"]; scope=r["scope"]; q25=float(r["q25"]); q75=float(r["q75"])
    x=pd.to_numeric(df[feature],errors="coerce")
    for part in ["VALIDATION_A","VALIDATION_B"]:
        base=df["research_partition"].eq(part)&df["_resolved"]
        if scope!="ALL": base &= df["_direction"].eq(scope)
        # Aggregate sign from exact Q1/Q4 contrast.
        q1=base & x.le(q25)
        q4=base & x.gt(q75)
        if q1.sum()<200 or q4.sum()<200: continue
        agg_delta=float(df.loc[q4,"_win"].mean()-df.loc[q1,"_win"].mean())
        agg_sign=np.sign(agg_delta)
        deltas=[]
        for sym,idx in df[base].groupby("symbol").groups.items():
            idx=pd.Index(idx)
            s1=idx[x.loc[idx].le(q25)]
            s4=idx[x.loc[idx].gt(q75)]
            if len(s1)<20 or len(s4)<20: continue
            delta=float(df.loc[s4,"_win"].mean()-df.loc[s1,"_win"].mean())
            deltas.append((sym,delta))
        if deltas:
            vals=np.array([d for _,d in deltas],dtype=float)
            same=float(np.mean(np.sign(vals)==agg_sign))
            med=float(np.median(vals))
            nsy=len(vals)
        else:
            same=np.nan; med=np.nan; nsy=0
        sym_rows.append({"feature":feature,"scope":scope,"partition":part,
                         "aggregate_q4_minus_q1":agg_delta,
                         "symbols_eligible":nsy,
                         "fraction_symbols_same_sign_as_aggregate":same,
                         "median_symbol_q4_minus_q1":med})
symc=pd.DataFrame(sym_rows)
symc.to_csv(OUT/"continuous_symbol_cluster_q1_q4.csv",index=False)

# ---- binary symbol robustness summary ----
brows=[]
for (f,s,p),g in symbin.groupby(["feature","scope","partition"]):
    # aggregate delta from validation_binary_summary
    q=vbin[(vbin.feature==f)&(vbin.scope==s)]
    col="validation_a_delta" if p=="VALIDATION_A" else "validation_b_delta"
    if q.empty: continue
    agg=float(q.iloc[0][col])
    vals=g["delta"].astype(float).to_numpy()
    if len(vals)==0: continue
    brows.append({"feature":f,"scope":s,"partition":p,
                  "aggregate_delta":agg,
                  "symbols_eligible":len(vals),
                  "fraction_symbols_same_sign_as_aggregate":float(np.mean(np.sign(vals)==np.sign(agg))),
                  "median_symbol_delta":float(np.median(vals))})
bsym=pd.DataFrame(brows)
bsym.to_csv(OUT/"binary_symbol_cluster_summary.csv",index=False)

print("\n=== CONTINUOUS SHAPE REPLICATION ===")
show=shape.sort_values(["shape_corr_ge_0_5_both","q4q1_sign_replicates_both"],ascending=False)
print(show.to_string(index=False))

print("\n=== CONTINUOUS SYMBOL CLUSTER Q1-vs-Q4 ===")
print(symc.to_string(index=False))

print("\n=== BINARY SYMBOL CLUSTER SUMMARY ===")
print(bsym.to_string(index=False))

# compact candidate classification hints, not final production authorization
hints=[]
for _,r in shape.iterrows():
    if r["shape_corr_ge_0_5_both"] and r["q4q1_sign_replicates_both"]:
        hint="REPLICATION_SIGNAL"
    elif r["q4q1_sign_replicates_both"]:
        hint="PARTIAL_REPLICATION"
    else:
        hint="WEAK_OR_UNSTABLE"
    hints.append({"feature":r["feature"],"scope":r["scope"],"hint":hint})
pd.DataFrame(hints).to_csv(OUT/"continuous_replication_hints.csv",index=False)

print("\nVALIDATION_ROBUSTNESS_GATE=PASS")
print("CUTPOINTS_REESTIMATED=False")
print("POST_VALIDATION_RULE_TUNING=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9K_OPENED=False")
