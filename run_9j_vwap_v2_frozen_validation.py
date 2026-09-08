from pathlib import Path
import pandas as pd, numpy as np, json, hashlib

ROOT=Path.cwd()
BASE=ROOT/"pmpd_v5_9j_vwap_event_path_v2_analysis"
INFILE=BASE/"decision_vwap_event_path_v2_dp4fix_with_frozen_outcome.csv"
FREEZE=BASE/"frozen_validation_protocol"
OUT=BASE/"validation_results"
OUT.mkdir(parents=True,exist_ok=True)

EXPECTED_FREEZE_FP="7e754fd754c46cd3d5b6e3de34bd0b2074cee9d50c4b5b1577cd0b91d2a3eadf"

def combined_fp():
    h=hashlib.sha256()
    for fn in ["frozen_continuous_cutpoints.csv","frozen_binary_hypotheses.csv","frozen_validation_protocol.json"]:
        h.update((FREEZE/fn).read_bytes())
    return h.hexdigest()

fp=combined_fp()
print("FREEZE_FINGERPRINT =",fp)
if fp!=EXPECTED_FREEZE_FP: raise SystemExit("FREEZE_FINGERPRINT_MISMATCH")

cuts=pd.read_csv(FREEZE/"frozen_continuous_cutpoints.csv")
binary=pd.read_csv(FREEZE/"frozen_binary_hypotheses.csv")
protocol=json.loads((FREEZE/"frozen_validation_protocol.json").read_text())

hdr=pd.read_csv(INFILE,nrows=0)
cols=list(hdr.columns)
outcome_col="frozen_primary_outcome"
needed={"research_partition",outcome_col,"direction","symbol"}
features=sorted(set(cuts["feature"]).union(binary["feature"]))
needed.update(features)
missing=needed-set(cols)
if missing: raise SystemExit(f"MISSING_COLUMNS={sorted(missing)}")

# Now, and only now after fingerprint verification, open validation partitions.
chunks=[]
for ch in pd.read_csv(INFILE,usecols=list(needed),chunksize=50000,low_memory=False):
    d=ch[ch["research_partition"].isin(["VALIDATION_A","VALIDATION_B"])].copy()
    chunks.append(d)
df=pd.concat(chunks,ignore_index=True)
print("validation_rows =",len(df))
print(df["research_partition"].value_counts().to_string())
if len(df)!=147486+157313: raise SystemExit("VALIDATION_ROW_COUNT_FAIL")

allowed={"FAVORABLE_FIRST","ADVERSE_FIRST","UNRESOLVED","AMBIGUOUS_SAME_BAR"}
if not set(df[outcome_col].dropna().astype(str).unique()).issubset(allowed):
    raise SystemExit("OUTCOME_LABEL_FAIL")
df["_resolved"]=df[outcome_col].isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])
df["_win"]=np.where(df[outcome_col].eq("FAVORABLE_FIRST"),1.0,
                    np.where(df[outcome_col].eq("ADVERSE_FIRST"),0.0,np.nan))
z=df["direction"].astype(str).str.upper()
df["_direction"]=np.where(z.str.contains("BULL|LONG|UP",regex=True),"BULL",
                          np.where(z.str.contains("BEAR|SHORT|DOWN",regex=True),"BEAR","UNKNOWN"))

# Population baselines.
pop=[]
for part in ["VALIDATION_A","VALIDATION_B"]:
  for scope in ["ALL","BULL","BEAR"]:
    m=df["research_partition"].eq(part)
    if scope!="ALL": m &= df["_direction"].eq(scope)
    g=df[m]; r=g[g["_resolved"]]
    pop.append({"partition":part,"scope":scope,"rows":len(g),"resolved_rows":len(r),
                "favorable_first":int((g[outcome_col]=="FAVORABLE_FIRST").sum()),
                "adverse_first":int((g[outcome_col]=="ADVERSE_FIRST").sum()),
                "unresolved":int((g[outcome_col]=="UNRESOLVED").sum()),
                "ambiguous_same_bar":int((g[outcome_col]=="AMBIGUOUS_SAME_BAR").sum()),
                "resolved_favorable_rate":float(r["_win"].mean()) if len(r) else None})
pd.DataFrame(pop).to_csv(OUT/"validation_population_summary.csv",index=False)

# Continuous frozen quartile bins. Use exact Discovery cuts, never recompute.
cres=[]
for _,row in cuts.iterrows():
    f=row["feature"]; scope=row["scope"]
    q25,q50,q75=float(row["q25"]),float(row["q50"]),float(row["q75"])
    x=pd.to_numeric(df[f],errors="coerce")
    bins=pd.cut(x,[-np.inf,q25,q50,q75,np.inf],labels=["Q1","Q2","Q3","Q4"],include_lowest=True)
    for part in ["VALIDATION_A","VALIDATION_B"]:
        base=df["research_partition"].eq(part)
        if scope!="ALL": base &= df["_direction"].eq(scope)
        rates=[]
        for lab in ["Q1","Q2","Q3","Q4"]:
            m=base & df["_resolved"] & bins.eq(lab)
            n=int(m.sum()); rate=float(df.loc[m,"_win"].mean()) if n else None
            rates.append(rate if rate is not None else np.nan)
            cres.append({"feature":f,"scope":scope,"partition":part,"bin":lab,
                         "resolved_n":n,"resolved_favorable_rate":rate,
                         "q25":q25,"q50":q50,"q75":q75})
        finite=[r for r in rates if not np.isnan(r)]
        spread=max(finite)-min(finite) if len(finite)>=2 else np.nan
        for rr in cres[-4:]:
            rr["quartile_rate_spread"]=float(spread) if not np.isnan(spread) else None
pd.DataFrame(cres).to_csv(OUT/"validation_continuous_frozen_bins.csv",index=False)

# Binary frozen hypotheses.
bres=[]
for _,h in binary.iterrows():
    f=h["feature"]; scope=h["scope"]
    s=df[f]
    if s.dtype==bool: xb=s
    else:
        sl=s.astype(str).str.lower()
        xb=sl.map({"true":True,"false":False,"1":True,"0":False,"1.0":True,"0.0":False})
    scopes=["ALL","BULL","BEAR"] if scope=="ALL_AND_DIRECTION_SEPARATE" else ["BULL","BEAR"]
    for part in ["VALIDATION_A","VALIDATION_B"]:
      for sc in scopes:
        base=df["research_partition"].eq(part)
        if sc!="ALL": base &= df["_direction"].eq(sc)
        vals={}
        for val in [False,True]:
            m=base & df["_resolved"] & xb.eq(val)
            n=int(m.sum()); rate=float(df.loc[m,"_win"].mean()) if n else None
            vals[val]=(n,rate)
            bres.append({"feature":f,"scope":sc,"partition":part,"value":val,
                         "resolved_n":n,"resolved_favorable_rate":rate})
        delta=(vals[True][1]-vals[False][1]) if vals[True][1] is not None and vals[False][1] is not None else None
        for rr in bres[-2:]: rr["true_minus_false_rate_delta"]=delta
pd.DataFrame(bres).to_csv(OUT/"validation_binary_hypotheses.csv",index=False)

# Symbol-cluster robustness for frozen binary hypotheses.
sres=[]
for _,h in binary.iterrows():
    f=h["feature"]; scope=h["scope"]
    sl=df[f].astype(str).str.lower()
    xb=sl.map({"true":True,"false":False,"1":True,"0":False,"1.0":True,"0.0":False})
    scopes=["ALL","BULL","BEAR"] if scope=="ALL_AND_DIRECTION_SEPARATE" else ["BULL","BEAR"]
    for part in ["VALIDATION_A","VALIDATION_B"]:
      for sc in scopes:
        base=df["research_partition"].eq(part)&df["_resolved"]
        if sc!="ALL": base &= df["_direction"].eq(sc)
        for sym,gidx in df[base].groupby("symbol").groups.items():
            idx=pd.Index(gidx)
            t=idx[xb.loc[idx].eq(True)]; fidx=idx[xb.loc[idx].eq(False)]
            if len(t)<20 or len(fidx)<20: continue
            delta=float(df.loc[t,"_win"].mean()-df.loc[fidx,"_win"].mean())
            sres.append({"feature":h["feature"],"scope":sc,"partition":part,
                         "symbol":sym,"true_n":len(t),"false_n":len(fidx),"delta":delta})
pd.DataFrame(sres).to_csv(OUT/"validation_binary_symbol_clusters.csv",index=False)

# Compact adjudication evidence summary. No post-validation threshold changes.
cont=pd.DataFrame(cres)
cs=[]
for (f,s),g in cont.groupby(["feature","scope"]):
    vals={}
    for part in ["VALIDATION_A","VALIDATION_B"]:
        q=g[g["partition"].eq(part)]
        vals[part]=float(q["quartile_rate_spread"].dropna().iloc[0]) if q["quartile_rate_spread"].notna().any() else None
    cs.append({"feature":f,"scope":s,"validation_a_spread":vals["VALIDATION_A"],
               "validation_b_spread":vals["VALIDATION_B"],
               "min_validation_spread":min(vals.values()) if all(v is not None for v in vals.values()) else None})
pd.DataFrame(cs).to_csv(OUT/"validation_continuous_summary.csv",index=False)

bb=pd.DataFrame(bres)
bs=[]
for (f,s),g in bb.groupby(["feature","scope"]):
    vals={}
    for part in ["VALIDATION_A","VALIDATION_B"]:
        q=g[g["partition"].eq(part)]
        vals[part]=float(q["true_minus_false_rate_delta"].dropna().iloc[0]) if q["true_minus_false_rate_delta"].notna().any() else None
    bs.append({"feature":f,"scope":s,"validation_a_delta":vals["VALIDATION_A"],
               "validation_b_delta":vals["VALIDATION_B"],
               "same_sign":bool(vals["VALIDATION_A"] is not None and vals["VALIDATION_B"] is not None and np.sign(vals["VALIDATION_A"])==np.sign(vals["VALIDATION_B"]))})
pd.DataFrame(bs).to_csv(OUT/"validation_binary_summary.csv",index=False)

manifest={
 "experiment":"PMPD_V5_9J_VWAP_EVENT_PATH_V2",
 "stage":"FROZEN_VALIDATION_A_B",
 "freeze_fingerprint":fp,
 "validation_a_rows":int((df["research_partition"]=="VALIDATION_A").sum()),
 "validation_b_rows":int((df["research_partition"]=="VALIDATION_B").sum()),
 "cutpoints_reestimated":False,
 "validation_opened_after_freeze":True,
 "production_rule_authorized":False,
 "9k_opened":False
}
(OUT/"validation_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

print("\n=== VALIDATION POPULATION ===")
print(pd.DataFrame(pop).to_string(index=False))
print("\n=== CONTINUOUS SUMMARY ===")
print(pd.DataFrame(cs).sort_values("min_validation_spread",ascending=False).to_string(index=False))
print("\n=== BINARY SUMMARY ===")
print(pd.DataFrame(bs).to_string(index=False))
print("\nFROZEN_VALIDATION_GATE=PASS")
print("CUTPOINTS_REESTIMATED=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9K_OPENED=False")
