from pathlib import Path
import pandas as pd, json, hashlib

ROOT=Path.cwd()
SRC=ROOT/"pmpd_v5_9m_oos_frames_v1"/"decision_research.parquet"
OUT=ROOT/"pmpd_v5_9m_oos_candidate_dp4_v1.parquet"
MAN=ROOT/"pmpd_v5_9m_oos_candidate_dp4_v1_manifest.json"

print("=== PMPD V5 9M-8 DP4 CANDIDATE POPULATION FREEZE ===")
df=pd.read_parquet(SRC)

# Frozen structural candidate selection only.
m_dp4=df["decision_type"].eq("DP4_FULL_STACK_FIRST_CLEAR")
m_primary=df["primary_decision_unit"].eq(True)
m_eligible=df["primary_inference_eligible"].eq(True)

print("SOURCE_ROWS =",len(df))
print("DP4_ROWS_PRE_FILTER =",int(m_dp4.sum()))
print("DP4_PRIMARY_DECISION_UNIT_ROWS =",int((m_dp4&m_primary).sum()))
print("DP4_PRIMARY_INFERENCE_ELIGIBLE_ROWS =",int((m_dp4&m_eligible).sum()))
print("DP4_PRIMARY_AND_ELIGIBLE_ROWS =",int((m_dp4&m_primary&m_eligible).sum()))

cand=df.loc[m_dp4&m_primary&m_eligible].copy()

# Structural diagnostics only; do not summarize outcome fields.
print("CANDIDATE_ROWS =",len(cand))
print("DIRECTION_COUNTS =",cand["direction"].value_counts(dropna=False).to_dict())
print("SYMBOL_COUNT =",cand["symbol"].nunique())
print("TRADE_DATE_COUNT =",cand["trade_date"].nunique())
print("FIRST_TRADE_DATE =",str(cand["trade_date"].min()))
print("LAST_TRADE_DATE =",str(cand["trade_date"].max()))

for c in ["eligibility_reason","price_scale_severe_flag","sparse_extended_hours_flag"]:
    if c in cand.columns:
        print(f"{c.upper()}_COUNTS =",cand[c].value_counts(dropna=False).to_dict())

# Guard against post-DP4 selection logic being introduced here.
selection_definition={
    "decision_type":"DP4_FULL_STACK_FIRST_CLEAR",
    "primary_decision_unit":True,
    "primary_inference_eligible":True
}

cand.to_parquet(OUT,index=False)
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()

manifest={
    "candidate_code":"PMPD_V5_CANDIDATE_DP4_UNSCORED_V1",
    "oos_protocol_id":"PMPD_V5_9M_OOS_PROTOCOL_V1",
    "source":str(SRC),
    "output":str(OUT),
    "selection_definition":selection_definition,
    "candidate_rows":len(cand),
    "direction_counts":cand["direction"].value_counts(dropna=False).to_dict(),
    "symbol_count":int(cand["symbol"].nunique()),
    "trade_date_count":int(cand["trade_date"].nunique()),
    "first_trade_date":str(cand["trade_date"].min()),
    "last_trade_date":str(cand["trade_date"].max()),
    "sha256":digest,
    "outcomes_summarized":False,
    "candidate_modified":False,
    "threshold_tuning":False,
    "score_fitting":False,
    "production_rule_authorized":False
}
MAN.write_text(json.dumps(manifest,indent=2,default=str),encoding="utf-8")

print("OUTPUT =",OUT)
print("MANIFEST =",MAN)
print("SHA256 =",digest)
print("OUTCOMES_SUMMARIZED=False")
print("CANDIDATE_MODIFIED=False")
print("THRESHOLD_TUNING=False")
print("SCORE_FITTING=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("9M_DP4_CANDIDATE_FREEZE_GATE=PASS")
