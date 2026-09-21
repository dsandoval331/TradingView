from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

P1=Path("research_outputs/ir11/p1/ir11_p1_dense_clock_observations_2025_v1.parquet")
PAIR=Path("research_outputs/ir11/p2/ir11_p2_pairwise_outcomes_2025_v1.parquet")
OUT=Path("research_outputs/ir11/p2/final_qa")
PRIMARY={(0.50,0.25),(0.50,0.50),(0.75,0.50),(1.00,0.50)}
EXPECTED=(149546,3738650,104,250)
MECHANICAL={("NFLX","2025-11-17"),("TQQQ","2025-11-20")}

def pop(df):
    return np.select([df.relative_top5_trailing60.fillna(False),df.displacement_pct>0],
                     ["REL_TOP5","POSITIVE_NON_TOP5"],default="NON_POSITIVE")

def summary(df,label):
    w=df.copy(); w["population"]=pop(w)
    w["fav"]=w.first_passage_outcome.eq("FAVORABLE_FIRST")
    w["adv"]=w.first_passage_outcome.eq("ADVERSE_FIRST")
    w["amb"]=w.first_passage_outcome.eq("AMBIGUOUS_SAME_BAR")
    w["resolved"]=w.fav|w.adv
    g=w.groupby(["clock","population","favorable_threshold_pct","adverse_threshold_pct"],dropna=False).agg(
        n=("symbol","size"),symbols=("symbol","nunique"),dates=("trade_date","nunique"),
        favorable_first=("fav","sum"),adverse_first=("adv","sum"),ambiguous=("amb","sum"),resolved=("resolved","sum")).reset_index()
    g["scenario"]=label
    g["favorable_pct_all"]=100*g.favorable_first/g.n
    g["favorable_pct_resolved"]=100*g.favorable_first/g.resolved.replace(0,np.nan)
    g["ambiguous_pct"]=100*g.ambiguous/g.n
    return g

def run(work_root:Path)->dict:
    root=Path(work_root).resolve(); out=root/OUT; out.mkdir(parents=True,exist_ok=True)
    p1=pd.read_parquet(root/P1); pairs=pd.read_parquet(root/PAIR)
    gate=(len(p1),len(pairs),p1.symbol.nunique(),pd.to_datetime(p1.trade_date).dt.date.nunique())
    if gate!=EXPECTED: raise RuntimeError(f"parity gate failed {gate}")
    pairs=pairs[[ (float(f),float(a)) in PRIMARY for f,a in zip(pairs.favorable_threshold_pct,pairs.adverse_threshold_pct)]].copy()
    pairs["trade_date"]=pd.to_datetime(pairs.trade_date).dt.strftime("%Y-%m-%d")
    pairs["abs_disp"]=pairs.displacement_pct.abs()
    pairs["mechanical_known"]=[(s,d) in MECHANICAL for s,d in zip(pairs.symbol,pairs.trade_date)]
    scenarios={
      "ORIGINAL":np.ones(len(pairs),dtype=bool),
      "EX_KNOWN_MECHANICAL":~pairs.mechanical_known,
      "EX_ABS_GE_10":pairs.abs_disp<10,
      "EX_ABS_GE_15":pairs.abs_disp<15,
    }
    sens=pd.concat([summary(pairs[m],k) for k,m in scenarios.items()],ignore_index=True)
    p=out/"ir11_p2_finalqa_sensitivity.csv"; sens.to_csv(p,index=False)
    rel=sens[(sens.population=="REL_TOP5")&(sens.favorable_threshold_pct==0.5)&(sens.adverse_threshold_pct==0.5)]
    pivot=rel.pivot(index="clock",columns="scenario",values="favorable_pct_all").reset_index()
    p2=out/"ir11_p2_finalqa_rel_top5_050_050.csv"; pivot.to_csv(p2,index=False)
    qa=pd.DataFrame([{"p1_rows":len(p1),"pair_rows":3738650,"symbols":p1.symbol.nunique(),"dates":pd.to_datetime(p1.trade_date).dt.date.nunique(),
      "known_mechanical_symbol_days":"NFLX:2025-11-17;TQQQ:2025-11-20",
      "rows_abs_ge_10":int((p1.displacement_pct.abs()>=10).sum()),"rows_abs_ge_15":int((p1.displacement_pct.abs()>=15).sum()),
      "method":"Sensitivity only; original certified P2 remains unchanged."}])
    p3=out/"ir11_p2_finalqa_manifest.csv"; qa.to_csv(p3,index=False)
    return {"artifact":str(p),"output_paths":[str(p),str(p2),str(p3)],"research_phase":"IR11-P2","batch":"P2-FINAL-QA","research_logic_modified":False}
