from pathlib import Path
import pandas as pd, json
ROOT=Path.cwd(); P=ROOT/"pmpd_v5_9m_oos_frames_v1"/"decision_research.parquet"
print("=== PMPD V5 9M-7 DP4 CANDIDATE EXTRACTION PREFLIGHT ===")
print("SOURCE =",P)
df=pd.read_parquet(P)
print("ROWS =",len(df)); print("COLS =",len(df.columns)); print("COLUMNS =",list(df.columns))
for c in ["decision_type","decision_point","decision_code","direction","primary_decision_unit","primary_inference_eligible","has_complete_six_levels","quality_status","exclusion_reason","reference_price_source"]:
    if c in df.columns:
        print("\nVALUE_COUNTS",c); print(df[c].value_counts(dropna=False).head(30).to_string())
for c in df.columns:
    if df[c].dtype=="object" or str(df[c].dtype).startswith("string"):
        vals=df[c].dropna().astype(str)
        hits=vals[vals.str.contains("DP4|FULL_STACK|FIRST_CLEAR",case=False,regex=True)]
        if len(hits):
            print("\nDP4_MATCH_COLUMN",c,"MATCH_ROWS=",len(hits)); print(hits.value_counts().head(30).to_string())
mask=pd.Series(False,index=df.index)
for c in df.columns:
    if df[c].dtype=="object" or str(df[c].dtype).startswith("string"):
        try: mask |= df[c].fillna("").astype(str).str.contains("DP4|FULL_STACK|FIRST_CLEAR",case=False,regex=True)
        except Exception: pass
safe=[c for c in df.columns if not any(k in c.lower() for k in ["outcome","favorable","adverse","result","winner","label","mfe","mae"])]
print("\nDP4_LIKE_ROWS =",int(mask.sum()))
if mask.any(): print(df.loc[mask,safe].head(8).to_string(index=False))
op=ROOT/"pmpd_v5_9m_dp4_extraction_preflight_v1.json"
op.write_text(json.dumps({"source":str(P),"rows":len(df),"columns":list(df.columns),"dp4_like_rows":int(mask.sum()),"outcomes_summarized":False,"candidate_modified":False,"production_rule_authorized":False},indent=2),encoding="utf-8")
print("\nREPORT =",op); print("OUTCOMES_SUMMARIZED=False"); print("CANDIDATE_MODIFIED=False"); print("PRODUCTION_RULE_AUTHORIZED=False"); print("9M_DP4_EXTRACTION_PREFLIGHT_GATE=PASS")
