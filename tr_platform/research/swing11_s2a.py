"""SWING11 predictor-only preflight. Scientific outcomes/dispositions are disabled."""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd

MWE = "eabd2257-bb59-4f32-af71-ad4b87bda4f5"
DECISIONS = ("7c6279c1-a86d-4336-a08d-244bb5e005b4", "11407ad3-97cd-459e-b78e-9162a115b8e4", "f240f40d-65a0-40dd-91dc-bdf722431e2b")
SHA = "ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2"
SIZE = 2411604
MECHANISMS = ("ACT20", "DOLLARVOL20", "ILLIQ20", "RV20", "REV5", "MOM20")
HORIZONS = (1, 2, 3, 5, 7, 10, 15, 20)
CORE = ("symbol", "trade_date", "open", "high", "low", "close", "volume")
FILES = ("sw11_s2a_predictor_values.csv", "sw11_s2a_coverage.csv", "sw11_s2a_design_geometry.csv",
         "sw11_s2a_temporal_blocks.csv", "sw11_s2a_inference_registry.csv",
         "sw11_s2a_semantic_source_audit.csv", "sw11_s2a_manifest.json")
SCHEMAS = {
 FILES[0]: ("symbol","trade_date","PRICE_raw","PRICE","ACT20_raw","ACT20","DOLLARVOL20_raw","DOLLARVOL20","ILLIQ20_raw","ILLIQ20","RV20_raw","RV20","REV5_raw","REV5","MOM20_raw","MOM20"),
 FILES[1]: ("mechanism","horizon","predictor_dates","endpoint_eligible_dates","symbol_dates","distinct_symbols","first_date","last_date","median_symbols"),
 FILES[2]: ("mechanism","trade_date","design","N","columns","rank","identified","condition_number","smallest_singular_value"),
 FILES[3]: ("mechanism","horizon","block","start","end","dates","median_symbols"),
 FILES[4]: ("family","mechanism","horizon","test_id","hac_lag","bh_family_size","bh_q","scientific_estimand_status"),
 FILES[5]: ("check","passed","detail"),
}

def reject_schema(columns):
    if tuple(columns) != CORE:
        raise ValueError("exact predictor-only OHLCV source schema required; outcomes denied")

def source_guard(source):
    tree=ast.parse(source)
    allowed={"ast","hashlib","io","json","os","pathlib","numpy","pandas"}
    banned={"forward_return","forward_returns","profitability","win_rate","p_value","read_sql","read_parquet","bfill","interpolate","eval","exec","__import__","pct_change"}
    for n in ast.walk(tree):
        if isinstance(n,(ast.Import,ast.ImportFrom)):
            names=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module]
            if any(x not in allowed for x in names): raise ValueError("unapproved source/outcome import")
        if isinstance(n,ast.Call):
            name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ""
            if name in banned: raise ValueError("scientific outcome primitive denied")
            if name=="shift":
                if not n.args or not isinstance(n.args[0],ast.Constant) or not isinstance(n.args[0].value,int) or n.args[0].value<=0:
                    raise ValueError("only fixed positive historical shifts allowed")
    return True

def verified_input(blob):
    if len(blob)!=SIZE or hashlib.sha256(blob).hexdigest()!=SHA:raise ValueError("immutable input mismatch")
    frame=pd.read_csv(io.BytesIO(blob));reject_schema(frame.columns)
    if frame.duplicated(["symbol","trade_date"]).any():raise ValueError("duplicate source")
    v=frame[list(CORE[2:])].to_numpy(dtype=float)
    if not np.isfinite(v).all() or (v[:,:4]<=0).any() or (v[:,4]<0).any():raise ValueError("invalid source numeric")
    if ((frame.low>frame[["open","close"]].min(axis=1))|(frame.high<frame[["open","close"]].max(axis=1))).any():raise ValueError("OHLC violation")
    dates=sorted(frame.trade_date.unique())
    if (len(frame),frame.symbol.nunique(),len(dates),dates[0],dates[-1])!=(44128,112,394,"2025-02-03","2026-08-27"):raise ValueError("protected or incompatible source")
    if not (frame.groupby("trade_date").symbol.nunique()==112).all():raise ValueError("incomplete panel")
    return frame

def centered_rank(values):
    x=pd.Series(values,dtype=float);x=x.where(np.isfinite(x))
    return 2*x.rank(method="average")/x.notna().sum()-1

def predictors(frame):
    reject_schema(frame.columns)
    if frame.duplicated(["symbol","trade_date"]).any():raise ValueError("duplicate predictor source")
    chunks=[]
    for symbol,g in frame.groupby("symbol",sort=True):
        g=g.sort_values("trade_date").copy()
        c=pd.to_numeric(g.close,errors="coerce");v=pd.to_numeric(g.volume,errors="coerce")
        c=c.where(np.isfinite(c)&(c>0));v=v.where(np.isfinite(v)&(v>=0))
        historical_return=c/c.shift(1)-1
        dollar=c*v
        previous20=v.shift(1).rolling(20,min_periods=20).mean()
        g["PRICE_raw"]=c
        g["ACT20_raw"]=v/previous20.where(previous20>0)
        g["DOLLARVOL20_raw"]=dollar.rolling(20,min_periods=20).mean()
        g["ILLIQ20_raw"]=(historical_return.abs()/dollar.where(dollar>0)).rolling(20,min_periods=20).mean()
        g["RV20_raw"]=historical_return.rolling(20,min_periods=20).std(ddof=1)
        g["REV5_raw"]=c/c.shift(5)-1
        g["MOM20_raw"]=c/c.shift(20)-1
        chunks.append(g)
    out=pd.concat(chunks).sort_values(["trade_date","symbol"])
    for name in ("PRICE",*MECHANISMS):
        out[name+"_raw"]=out[name+"_raw"].where(np.isfinite(out[name+"_raw"]))
        out[name]=out.groupby("trade_date")[name+"_raw"].transform(centered_rank)
    return out[list(SCHEMAS[FILES[0]])]

def design(price,mechanism=None,conditioning=False):
    p=np.asarray(price,dtype=float)
    cols=[np.ones(len(p)),p]
    if mechanism is not None:
        m=np.asarray(mechanism,dtype=float);cols.append(m)
        if conditioning:cols.append(p*m)
    elif conditioning:raise ValueError("main effect required")
    x=np.column_stack(cols)
    if not np.isfinite(x).all() or len(x)<=x.shape[1]:raise ValueError("insufficient finite design")
    singular=np.linalg.svd(x,compute_uv=False)
    tol=np.finfo(float).eps*max(x.shape)*singular[0]
    rank=int(sum(singular>tol))
    if rank!=x.shape[1]:raise ValueError("numerically non-identifiable; no pseudoinverse")
    return x,rank,float(singular[0]/singular[-1]),float(singular[-1])

def synthetic_refit(x,y,symbols,index):
    # This estimator is exclusively for synthetic fixtures in S2-A.
    if any(not str(s).startswith("SYNTHETIC_") for s in symbols):raise ValueError("synthetic estimator only")
    if not np.isfinite(y).all() or np.linalg.matrix_rank(x)!=x.shape[1]:raise ValueError("unidentified synthetic estimator")
    inverse=np.linalg.solve(x.T@x,np.eye(x.shape[1]))
    contributions=(x@inverse[:,index])*np.asarray(y)
    coefficient=float(contributions.sum())
    top=sorted(range(len(symbols)),key=lambda i:(-abs(contributions[i]),symbols[i]))[:5]
    keep=[i for i in range(len(symbols)) if i not in top]
    if len(keep)<=x.shape[1] or np.linalg.matrix_rank(x[keep])!=x.shape[1]:raise ValueError("leave-five unavailable")
    leave=float(np.linalg.solve(x[keep].T@x[keep],x[keep].T@np.asarray(y)[keep])[index])
    absolute=abs(contributions);shares=absolute/absolute.sum() if absolute.sum()>0 else np.full(len(symbols),np.nan)
    return {"coefficient":coefficient,"contributions":contributions,"top5":top,"leave5":leave,
            "top1":float(np.sort(shares)[-1]),"top5_share":float(np.sort(shares)[-5:].sum()),
            "top10":float(np.sort(shares)[-10:].sum()),"hhi":float(np.square(shares).sum()),
            "sign_reversal":coefficient*leave<0,"absolute_attenuation":1-abs(leave)/abs(coefficient) if coefficient else None}

def inference_registry():
    rows=[]
    for family,size,names in (("A_BASELINE",8,("PRICE",)),("B_ATTENUATION",48,MECHANISMS),("C_INTERACTION",48,MECHANISMS)):
        for name in names:
            for h in HORIZONS:
                rows.append((family,name,h,f"{family}__{name}__H{h}",h-1,size,.05,
                             "CANONICAL_ATTENUATION_INFERENTIAL_ESTIMAND_REQUIRED" if family=="B_ATTENUATION" else "FROZEN_DATE_COEFFICIENT"))
    return rows

def four_blocks(dates):
    n,extra=divmod(len(dates),4);parts=[];i=0
    for b in range(4):
        part=list(dates[i:i+n+(b<extra)]);parts.append(part);i+=len(part)
    return parts

def require_scientific_contract():
    raise ValueError("BLOCKED_USER: attenuation inferential estimand and disposition truth table not frozen")

def audit(frame):
    values=predictors(frame);calendar=sorted(frame.trade_date.unique());positions={d:i for i,d in enumerate(calendar)}
    coverage=[];geometry=[];blocks=[]
    for name in MECHANISMS:
        valid=values.dropna(subset=["PRICE",name]);groups=list(valid.groupby("trade_date"))
        for date,g in groups:
            for kind in ("BASELINE","ADJUSTED","CONDITIONING"):
                try:
                    x,rank,cond,small=design(g.PRICE,None if kind=="BASELINE" else g[name],kind=="CONDITIONING");identified=True
                except ValueError:
                    x=np.empty((len(g),2 if kind=="BASELINE" else 3 if kind=="ADJUSTED" else 4));rank=cond=small=None;identified=False
                geometry.append((name,date,kind,len(g),x.shape[1],rank,identified,cond,small))
        for h in HORIZONS:
            eligible=[(d,g) for d,g in groups if positions[d]+h<len(calendar)]
            dates=[d for d,g in eligible];lookup=dict(eligible)
            coverage.append((name,h,len(groups),len(dates),sum(len(g) for d,g in eligible),len(set(valid.symbol)),
                             dates[0] if dates else None,dates[-1] if dates else None,float(np.median([len(g) for d,g in eligible])) if dates else None))
            for b,part in enumerate(four_blocks(dates),1):
                blocks.append((name,h,b,part[0] if part else None,part[-1] if part else None,len(part),float(np.median([len(lookup[d]) for d in part])) if part else None))
    return values,coverage,geometry,blocks

def run(work_root):
    root=Path(work_root)
    if os.environ.get("GITHUB_ACTIONS")!="true":raise ValueError("governed online real predictor compute required")
    context=json.loads((root/"job_inputs/swing10/execution_context.json").read_text())
    if context.get("mwe_uuid")!=MWE or context.get("preflight_only") is not True or context.get("scientific_outcomes_authorized") is not False:raise ValueError("exact outcome-blind envelope required")
    source_guard(Path(__file__).read_text())
    frame=verified_input((root/"job_inputs/swing11/development.csv").read_bytes())
    values,coverage,geometry,blocks=audit(frame)
    out=root/"research_outputs/swing11/s2a";out.mkdir(parents=True,exist_ok=True)
    rows={FILES[0]:values,FILES[1]:coverage,FILES[2]:geometry,FILES[3]:blocks,FILES[4]:inference_registry(),
          FILES[5]:[("IMMUTABLE_INPUT",True,SHA),("OUTCOME_BLIND",True,"no future price primitive or outcome import"),
                    ("PROTECTED_DENIAL",True,"B5 and all post2026-08-27 sources excluded"),
                    ("SCIENTIFIC_CONTRACT",False,"attenuation inference and disposition mapping require canonical clarification")]}
    declarations=[]
    for name,table in rows.items():
        df=table if isinstance(table,pd.DataFrame) else pd.DataFrame(table,columns=SCHEMAS[name])
        df.to_csv(out/name,index=False)
        blob=(out/name).read_bytes();declarations.append({"name":name,"sha256":hashlib.sha256(blob).hexdigest(),"bytes":len(blob)})
    manifest={"mwe_uuid":MWE,"decisions":DECISIONS,"outcome_blind":True,"scientific_outcomes_computed":False,
              "protected_data_access":False,"input_sha256":SHA,"input_bytes":SIZE,"execution":context,
              "files":FILES,"schemas":SCHEMAS,"artifacts":declarations,"horizons":HORIZONS,
              "rank_scope":"each predictor finite same-date cross-section; designs intersect eligible ranked observations",
              "block_scope":"per mechanism/horizon predictor eligibility plus calendar endpoint availability",
              "numeric_rank_tolerance":"machine epsilon * max(design dimensions) * largest singular value",
              "readiness":"BLOCKED_USER","billing_evidence_available":False,"paid_fallback":False,
              "limitations":["previously used S2/S3 development, not untouched validation","adjusted price/reported volume proxy coordinates","no actual attenuation/disposition scientific rule invented"]}
    (out/FILES[-1]).write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    return {"status":"PASS","artifact":str((out/FILES[1]).relative_to(root)),"output_paths":[str((out/n).relative_to(root)) for n in FILES]}
