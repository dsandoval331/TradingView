"""Supplement-1 scientific-contract certification. SYNTHETIC ONLY, no input I/O.

Real S2-B execution is deliberately absent. These pure functions certify the
future contract on explicitly tagged fixtures and cannot consume market files.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import numpy as np

SUPPLEMENT = "a040e9fa-4fdf-4dc8-8ab7-5d8db622c779"
SUPPLEMENT_2 = "4f7cf8cf-3738-4b3c-8345-68722cf77644"
FINAL_FILES = ("sw11_s2a_final_binding_certification.json", "sw11_s2_final_sample_registry.json", "sw11_s2_final_scientific_schemas.json", "sw11_s2a_final_binding_manifest.json")
MWE = "eabd2257-bb59-4f32-af71-ad4b87bda4f5"
MECHANISMS = ("ACT20", "DOLLARVOL20", "ILLIQ20", "RV20", "REV5", "MOM20")
HORIZONS = (1, 2, 3, 5, 7, 10, 15, 20)
EPS = 1e-12
CERT_FILES = ("sw11_s2a_supplement_certification.json", "sw11_s2_scientific_schemas.json", "sw11_s2a_supplement_manifest.json")
SCIENTIFIC_SCHEMAS = {
 "sw11_s2_primary_summary.csv": ["test_id","family","mechanism","horizon","estimand","direction","testable","unavailable_reason","N_dates","mean","median","sd_ddof1","standardized_effect","hac_lag","hac_se","t_statistic","raw_p","bh_p","bh_slot_p","bh_family_size","ci_low","ci_high","direction_share","baseline_mean_matched","adjusted_mean_matched","descriptive_attenuation","direction_gate","fdr_gate","materiality_gate","temporal_gate","concentration_gate","adjacency_gate","required_robustness_available"],
 "sw11_s2_date_effects.csv": ["test_id","family","mechanism","horizon","trade_date","N_symbols","baseline_coefficient","adjusted_coefficient","interaction_coefficient","baseline_family_sign","paired_attenuation_difference","identified","unavailable_reason","block"],
 "sw11_s2_temporal_stability.csv": ["test_id","block","start_date","end_date","eligible_dates","finite_dates","mean","median","sign","baseline_mean_matched","adjusted_mean_matched","descriptive_attenuation","direction_pass","absolute_contribution","absolute_contribution_share","available"],
 "sw11_s2_symbol_concentration.csv": ["test_id","symbol","additive_contribution","absolute_contribution_share","absolute_rank","top_five_removed","top1_share","top5_share","top10_share","hhi","contribution_reconciled","full_effect","leave5_effect","full_standardized_effect","leave5_standardized_effect","standardized_effect_attenuation","leave5_sign_reversal","leave5_descriptive_attenuation","available","concentration_gate"],
 "sw11_s2_predictor_semantic_audit.csv": ["check","scope","passed","detail","source_input_id","source_sha256","source_bytes","protected_access","scientific_execution_authorized"],
 "sw11_s2_mechanism_dispositions.csv": ["mechanism","disposition","reason","qualifying_evidence_type","qualifying_horizons","secondary_supported_aspects","failed_aspects_denied_to_S3","testable_horizons","protocol_ids"],
 "sw11_s2_manifest.json": ["protocol_ids","complete_decision_snapshots","research_sha","infrastructure_sha","job_id","attempt_id","github_run_id","github_job_id","immutable_inputs","sample_role","rank_scope","matched_sample_rule","baseline_family_case_registry","endpoint_rule","coefficient_registry","bh_families","unavailable_slot_policy","hac","standardized_effect","attenuation","temporal_blocks","symbol_rules","adjacency","disposition_mapping","schemas","artifacts_excluding_manifest_self_hash","protected_data_access","outcome_authorization","compute_cost_provenance","failures_recovery"],
}

def fixture_only(symbols):
    if not symbols or any(not str(s).startswith("SYNTHETIC_") for s in symbols):
        raise ValueError("S2-A synthetic fixtures only; real outcomes denied")

def ranks(values):
    x=np.asarray(values,float); result=np.full(len(x),np.nan);finite=np.flatnonzero(np.isfinite(x))
    for i in finite:
        rank=1+sum(x[finite]<x[i])+(sum(x[finite]==x[i])-1)/2
        result[i]=2*rank/len(finite)-1
    return result

def matched_designs(price_raw, mechanism_raw, close_t, close_endpoint, symbols):
    fixture_only(symbols)
    p,m=ranks(price_raw),ranks(mechanism_raw)
    a,z=np.asarray(close_t,float),np.asarray(close_endpoint,float)
    mask=np.isfinite(p)&np.isfinite(m)&np.isfinite(a)&np.isfinite(z)&(a>0)&(z>0)
    p,m=p[mask],m[mask]
    designs=[np.column_stack([np.ones(len(p)),p]),np.column_stack([np.ones(len(p)),p,m]),np.column_stack([np.ones(len(p)),p,m,p*m])]
    for x in designs: identify(x)
    return mask,designs

def endpoint_return(calendar_closes, t, horizon, symbols):
    fixture_only(symbols)
    if horizon not in HORIZONS or t<0 or t+horizon>=len(calendar_closes):raise ValueError("registered calendar endpoint unavailable")
    a,z=np.asarray(calendar_closes[t],float),np.asarray(calendar_closes[t+horizon],float)
    mask=np.isfinite(a)&np.isfinite(z)&(a>0)&(z>0)
    result=np.full(a.shape,np.nan);result[mask]=z[mask]/a[mask]-1
    return result

def identify(x):
    x=np.asarray(x,float)
    if x.ndim!=2 or len(x)<4 or len(x)<x.shape[1] or not np.isfinite(x).all():raise ValueError("unavailable finite N>=4 design")
    s=np.linalg.svd(x,compute_uv=False)
    if len(s)!=x.shape[1] or sum(s>np.finfo(float).eps*max(x.shape)*s[0])!=x.shape[1]:raise ValueError("unidentified; no pseudoinverse")
    return x

def ols_contributions(x,y,symbols,index):
    fixture_only(symbols);x=identify(x);y=np.asarray(y,float)
    if len(y)!=len(x) or not np.isfinite(y).all():raise ValueError("nonfinite fixture response")
    # QR, not normal-equation pseudoinverse; projection row gives additive units.
    q,r=np.linalg.qr(x,mode="reduced")
    row=np.linalg.solve(r.T,np.eye(x.shape[1])[:,index])@q.T
    contribution=row*y
    coefficient=np.linalg.solve(r,q.T@y)[index]
    if not np.isclose(contribution.sum(),coefficient,rtol=1e-10,atol=1e-12):raise ValueError("additive reconciliation failed")
    return float(coefficient),contribution

def paired_difference(b0,b1,baseline_family_series):
    b0,b1=np.asarray(b0,float),np.asarray(b1,float)
    if b0.shape!=b1.shape:raise ValueError("identical paired dates required")
    base=np.asarray(baseline_family_series,float);base=base[np.isfinite(base)]
    base_mean=float(base.mean()) if len(base) else np.nan
    if not np.isfinite(base_mean) or base_mean==0:raise ValueError("baseline-family sign unavailable")
    mask=np.isfinite(b0)&np.isfinite(b1)
    b0,b1=b0[mask],b1[mask]
    denominator=float(b0.mean()) if len(b0) else np.nan
    if not np.isfinite(denominator) or abs(denominator)<=EPS:raise ValueError("near-zero matched baseline unavailable")
    return np.sign(base_mean)*(b0-b1),1-abs(float(b1.mean()))/abs(denominator)

def hac(series,horizon,kind):
    if horizon not in HORIZONS or kind not in ("BASELINE","ATTENUATION","INTERACTION"):raise ValueError("unregistered test")
    z=np.asarray(series,float);z=z[np.isfinite(z)];n=len(z)
    if n<max(20,horizon+2):return {"testable":False,"reason":"DATE_COUNT","raw_p":None,"bh_slot_p":1.0}
    mean=float(z.mean());sd=float(z.std(ddof=1));u=z-mean;lag=horizon-1
    long_variance=float(u@u)/n
    for k in range(1,lag+1):long_variance+=2*(1-k/(lag+1))*float(u[k:]@u[:-k])/n
    se=math.sqrt(max(0,long_variance)/n)
    limit=EPS if kind=="ATTENUATION" else 0
    if not np.isfinite(se) or se<=limit or (kind=="ATTENUATION" and (not np.isfinite(sd) or sd<=EPS)):
        return {"testable":False,"reason":"VARIANCE","raw_p":None,"bh_slot_p":1.0}
    es=mean/sd if np.isfinite(sd) and sd>0 else None
    p=math.erfc(abs(mean/se)/math.sqrt(2));delta=1.959963984540054*se
    return {"testable":True,"N":n,"mean":mean,"median":float(np.median(z)),"sd":sd,"ES":es,"hac_lag":lag,"hac_se":se,"t":mean/se,"raw_p":p,"bh_slot_p":p,"ci_low":mean-delta,"ci_high":mean+delta}

def bh(p_values,size):
    if size not in (8,48) or len(p_values)!=size:raise ValueError("fixed BH family cannot shrink")
    p=np.asarray([1 if v is None else v for v in p_values],float)
    if not np.isfinite(p).all() or (p<0).any() or (p>1).any():raise ValueError("invalid bookkeeping p")
    order=np.argsort(p,kind="stable");ranked=p[order]*size/np.arange(1,size+1)
    adjusted=np.minimum.accumulate(ranked[::-1])[::-1];out=np.empty(size);out[order]=np.minimum(1,adjusted)
    return out

def primary_gate(kind,mean,es,q,atten=None):
    if any(v is None or not np.isfinite(v) for v in (mean,es,q)):return False
    direction=mean<0 if kind=="BASELINE" else mean>0 if kind=="ATTENUATION" else mean!=0
    material=(es>=.20 and atten is not None and np.isfinite(atten) and atten>=.25) if kind=="ATTENUATION" else abs(es)>=.20
    return bool(direction and material and q<=.05)

def temporal_gate(kind,full_mean,blocks):
    # Blocks are supplied from the predictor-only registry, never selected by y.
    if len(blocks)!=4 or not np.isfinite(full_mean) or full_mean==0:return False
    if any(not b.get("available",False) or not np.isfinite(b.get("mean",np.nan)) or b.get("N",0)<=0 for b in blocks):return False
    if kind=="BASELINE":signs=[b["mean"]<0 for b in blocks]
    elif kind=="ATTENUATION":signs=[b["mean"]>0 and np.isfinite(b.get("ATTEN",np.nan)) and b["ATTEN"]>0 for b in blocks]
    else:signs=[b["mean"]*full_mean>0 for b in blocks]
    masses=np.asarray([abs(b["mean"]*b["N"]) for b in blocks])
    return bool(sum(signs)>=3 and masses.sum()>0 and masses.max()/masses.sum()<=.50)

def concentration_gate(kind,full_mean,leave_mean,full_es,leave_es,leave_atten=None):
    if any(v is None or not np.isfinite(v) for v in (full_mean,leave_mean,full_es,leave_es)) or full_mean==0 or full_es==0:return False
    if kind=="BASELINE":direction=full_mean<0 and leave_mean<0
    elif kind=="ATTENUATION":direction=full_mean>0 and leave_mean>0 and leave_atten is not None and np.isfinite(leave_atten) and leave_atten>0
    else:direction=leave_mean*full_mean>=0 # zero is not an interaction reversal
    return bool(direction and 1-abs(leave_es)/abs(full_es)<=.75)

def aggregate_contributions(date_contributions,symbols):
    fixture_only(symbols);matrix=np.asarray(date_contributions,float)
    if not np.isfinite(matrix).all() or matrix.ndim!=2 or matrix.shape[1]!=len(symbols):raise ValueError("contributions unavailable")
    c=matrix.mean(axis=0);absolute=abs(c);total=absolute.sum()
    if total<=0:raise ValueError("zero concentration denominator")
    order=sorted(range(len(c)),key=lambda i:(-absolute[i],symbols[i]));share=absolute/total
    return {"contributions":c,"top5":order[:5],"top1_share":float(share[order[:1]].sum()),"top5_share":float(share[order[:5]].sum()),"top10_share":float(share[order[:10]].sum()),"hhi":float((share**2).sum())}

def leave_five_refit(designs,responses,symbols,index,contributions):
    fixture_only(symbols);diagnostic=aggregate_contributions(contributions,symbols);removed=set(diagnostic["top5"])
    keep=[i for i in range(len(symbols)) if i not in removed];ids=[symbols[i] for i in keep]
    # Preserve original ranks; slice designs rather than re-rank remaining stocks.
    return [ols_contributions(np.asarray(x)[keep],np.asarray(y)[keep],ids,index)[0] for x,y in zip(designs,responses)],diagnostic

def adjacency(primary_by_horizon):
    if set(primary_by_horizon)!=set(HORIZONS):raise ValueError("all eight registered slots required")
    return {h:bool(primary_by_horizon[h] and any(primary_by_horizon[HORIZONS[j]] for j in (i-1,i+1) if 0<=j<len(HORIZONS))) for i,h in enumerate(HORIZONS)}

def disposition(rows):
    if set(rows)!=set(HORIZONS):raise ValueError("eight registered horizon records required")
    testable=[h for h in HORIZONS if rows[h].get("testable",False)]
    if not testable:return "NOT_TESTABLE","NO_TESTABLE_PATH",[]
    conditioning=[];explanatory=[];weaker=[];opposite=[]
    for a,b in zip(HORIZONS,HORIZONS[1:]):
        if a not in testable or b not in testable:continue
        pair=[rows[a],rows[b]]
        strong_c=all(x.get("interaction_primary",False) and x.get("interaction_temporal",False) and x.get("interaction_concentration",False) for x in pair) and pair[0].get("interaction_mean",0)*pair[1].get("interaction_mean",0)>0
        strong_e=all(x.get("attenuation_primary",False) and x.get("attenuation_temporal",False) and x.get("attenuation_concentration",False) and x.get("baseline_primary",False) for x in pair)
        weak_a=all(x.get("attenuation_fdr",False) and x.get("d_mean",0)>0 and x.get("d_ES",-np.inf)>=.20 and .10<=x.get("ATTEN",-np.inf)<.25 for x in pair)
        weak_c=all(x.get("interaction_primary",False) for x in pair) and pair[0].get("interaction_mean",0)*pair[1].get("interaction_mean",0)>0 and any(not x.get("interaction_temporal",False) or not x.get("interaction_concentration",False) for x in pair)
        if strong_c:conditioning.extend([a,b])
        if strong_e:explanatory.extend([a,b])
        if weak_a or weak_c:weaker.extend([a,b])
        if all(x.get("ATTEN",0)<0 and x.get("d_mean",1)<=0 for x in pair):opposite.extend([a,b])
    # COUNTEREVIDENCE is conditional on no qualifying support per section F;
    # the written precedence does not discard qualifying supported categories.
    if conditioning:return "CONDITIONING_SUPPORTED","QUALIFIED_ADJACENT_INTERACTION",sorted(set(conditioning))
    if explanatory:return "EXPLANATORY_EVIDENCE","QUALIFIED_ADJACENT_ATTENUATION",sorted(set(explanatory))
    if weaker:return "MECHANISM_SUPPORTED","WEAKER_REPRODUCIBLE_ASPECT_ONLY",sorted(set(weaker))
    return "COUNTEREVIDENCE",("NEGATIVE_ATTENUATION" if opposite else "ALL_FDR_FAILED" if all(not rows[h].get("attenuation_fdr",False) and not rows[h].get("interaction_fdr",False) for h in testable) else "INSUFFICIENT_REGISTERED_SUPPORT"),[]

def certify():
    # Deterministic small fixtures; no filesystem/network/market-data reads.
    ids=[f"SYNTHETIC_{i:03}" for i in range(30)];p=np.linspace(-1,1,30);m=np.sin(np.arange(30))
    x=np.column_stack([np.ones(30),p,m,p*m]);y=x@np.array([.1,-.3,.2,.4])
    coefficient,c=ols_contributions(x,y,ids,3)
    z=-.2+.1*np.sin(np.arange(80));d,atten=paired_difference(z,z*.6,z)
    stats=hac(d,5,"ATTENUATION")
    assert abs(coefficient-.4)<1e-12 and abs(c.sum()-.4)<1e-12 and stats["testable"] and abs(atten-.4)<1e-12
    assert sum(len(bh([None]*n,n)) for n in (8,48,48))==104
    return {"status":"PASS_INDEPENDENT_SYNTHETIC_RULES","synthetic_only":True,"real_outcomes_computed":False,"protected_data_access":False,"fixture_known_interaction":coefficient,"fixture_attenuation":atten,"fixture_hac_lag":stats["hac_lag"],"bh_family_sizes":[8,48,48],"scientific_execution_enabled":False,"supplement_id":SUPPLEMENT,"baseline_family_sample_binding":"CANONICAL_REQUIRED_BEFORE_S2B","limitation":"Eight baseline PRICE tests need one exact per-horizon case/date-series binding; matched baselines for six mechanisms are not automatically identical eligible-date series."}

def run(work_root):
    root=Path(work_root)
    context_path=root/"job_inputs/swing10/execution_context.json"
    if context_path.exists() and json.loads(context_path.read_text()).get("final_binding_certification") is True:
        return run_final(root)
    if os.environ.get("GITHUB_ACTIONS")!="true":raise ValueError("governed certification only")
    context=json.loads((root/"job_inputs/swing10/execution_context.json").read_text())
    if context.get("mwe_uuid")!=MWE or context.get("synthetic_only") is not True or context.get("scientific_outcomes_authorized") is not False or context.get("materialized_inputs"):
        raise ValueError("zero-source synthetic certification envelope required")
    if set(x["decision_id"] for x in context.get("contract_snapshot",[]))!={SUPPLEMENT,"7c6279c1-a86d-4336-a08d-244bb5e005b4","11407ad3-97cd-459e-b78e-9162a115b8e4","f240f40d-65a0-40dd-91dc-bdf722431e2b"}:raise ValueError("complete four-decision authority required")
    out=root/"research_outputs/swing11/s2a_supplement";out.mkdir(parents=True,exist_ok=True)
    (out/CERT_FILES[0]).write_text(json.dumps(certify(),sort_keys=True,indent=2)+"\n")
    (out/CERT_FILES[1]).write_text(json.dumps(SCIENTIFIC_SCHEMAS,sort_keys=True,indent=2)+"\n")
    artifacts=[{"name":name,"sha256":hashlib.sha256((out/name).read_bytes()).hexdigest(),"bytes":(out/name).stat().st_size} for name in CERT_FILES[:2]]
    manifest={"authority":context,"artifacts":artifacts,"schemas":SCIENTIFIC_SCHEMAS,"synthetic_only":True,"scientific_execution_enabled":False,"real_forward_outcomes_computed":False,"protected_data_access":False,"paid_fallback":False,"billing_evidence_available":False}
    (out/CERT_FILES[2]).write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    paths=[str((out/name).relative_to(root)) for name in CERT_FILES]
    return {"status":"PASS","artifact":paths[0],"output_paths":paths}

def price_only_design(price_raw, close_t, endpoint, symbols):
    """Synthetic binding fixture; rank the finite date cross section first."""
    fixture_only(symbols)
    p=ranks(price_raw);a,z=np.asarray(close_t,float),np.asarray(endpoint,float)
    if p.shape!=a.shape or p.shape!=z.shape or len(symbols)!=len(p):
        raise ValueError("same registered symbol cross section required")
    mask=np.isfinite(p)&np.isfinite(a)&np.isfinite(z)&(a>0)&(z>0)
    x=np.column_stack([np.ones(int(mask.sum())),p[mask]])
    identify(x)
    return mask,x

def baseline_anchor(horizon, baseline_registry):
    """Only a complete, unique PRICE-only family record may supply s_H."""
    if set(baseline_registry)!=set(HORIZONS):raise ValueError("eight baseline records required")
    case=baseline_registry[horizon]
    if case.get("test_id")!=f"BASELINE_PRICE_H{horizon}" or case.get("sample_binding")!="PRICE_ONLY" or case.get("complete_series") is not True:
        raise ValueError("complete PRICE-only sign source required")
    z=np.asarray(case["coefficient_series"],float);z=z[np.isfinite(z)]
    mean=float(z.mean()) if len(z) else np.nan
    if not np.isfinite(mean) or mean==0:raise ValueError("baseline sign unavailable")
    return float(np.sign(mean))

def bound_paired_difference(b0,b1,horizon,baseline_registry):
    s=baseline_anchor(horizon,baseline_registry)
    # Keep the matched comparison, never substitute the PRICE-only series.
    return paired_difference(b0,b1,[s])

def baseline_blocks(eligible_dates):
    dates=list(eligible_dates)
    if dates!=sorted(set(dates)):raise ValueError("unique chronological eligibility dates required")
    return [list(block) for block in np.array_split(np.asarray(dates),4)]

def final_registry():
    rows=[]
    for h in HORIZONS:
        rows.append({"test_id":f"BASELINE_PRICE_H{h}","family":"BASELINE","horizon":h,"mechanism":None,"sample_binding":"PRICE_ONLY","sign_source":f"BASELINE_PRICE_H{h}","rank_scope":"finite same-date PRICE before endpoint mask","blocks":"four chronological PRICE-only eligible-date blocks","leave5":"fixed sample and original ranks; complete PRICE-only refit","bh_family_size":8})
    for family in ("ATTENUATION","INTERACTION"):
        for m in MECHANISMS:
            for h in HORIZONS:
                rows.append({"test_id":f"{family}_{m}_H{h}","family":family,"horizon":h,"mechanism":m,"sample_binding":"MECHANISM_MATCHED","sign_source":f"BASELINE_PRICE_H{h}" if family=="ATTENUATION" else None,"rank_scope":"separately finite same-date PRICE and mechanism before endpoint mask","blocks":"four chronological matched eligible-date blocks","leave5":"fixed matched sample and original ranks; complete matched estimator refit","bh_family_size":48})
    return rows

def final_schemas():
    schemas={k:list(v) for k,v in SCIENTIFIC_SCHEMAS.items()}
    for name in ("sw11_s2_primary_summary.csv","sw11_s2_date_effects.csv"):
        schemas[name]+=["sample_binding","baseline_family_test_id","baseline_family_sign_source"]
    schemas["sw11_s2_manifest.json"]+=["baseline_family_sample_rule","baseline_sign_anchor_rule","baseline_blocks_rule","baseline_leave5_rule","matched_comparison_separation"]
    return schemas

def certify_binding():
    ids=[f"SYNTHETIC_{i:03}" for i in range(12)]
    prices=np.arange(1.,13.);mask,x=price_only_design(prices,prices,prices+1,ids)
    y=.2-.4*x[:,1]
    beta,contribution=ols_contributions(x,y,ids,1)
    remaining,diag=leave_five_refit([x],[y],ids,1,[contribution])
    registry={h:{"test_id":f"BASELINE_PRICE_H{h}","sample_binding":"PRICE_ONLY","complete_series":True,"coefficient_series":[beta,beta-.1]} for h in HORIZONS}
    d,atten=bound_paired_difference([.4,.6],[.2,.3],5,registry)
    assert mask.sum()==12 and abs(beta+.4)<1e-12 and abs(remaining[0]+.4)<1e-12
    assert np.allclose(d,[-.2,-.3]) and abs(atten-.5)<1e-12
    assert len(final_registry())==104
    return {"status":"PASS_FINAL_SAMPLE_BINDING","synthetic_only":True,"price_only_baseline":"CERTIFIED","global_s_H_source":"COMPLETE_PRICE_ONLY_BASELINE_H","matched_attenuation_separation":"CERTIFIED","baseline_blocks":"CERTIFIED","baseline_leave5_full_refit":"CERTIFIED","bh_family_sizes":[8,48,48],"real_outcomes_computed":False,"protected_data_access":False,"scientific_execution_enabled":False,"S2B_readiness":"READY_FOR_CANONICAL_AUTHORIZATION","supplement_2_id":SUPPLEMENT_2}

def run_final(root):
    if os.environ.get("GITHUB_ACTIONS")!="true":raise ValueError("governed certification only")
    context=json.loads((root/"job_inputs/swing10/execution_context.json").read_text())
    required={SUPPLEMENT,SUPPLEMENT_2,"7c6279c1-a86d-4336-a08d-244bb5e005b4","11407ad3-97cd-459e-b78e-9162a115b8e4","f240f40d-65a0-40dd-91dc-bdf722431e2b"}
    snapshots=context.get("contract_snapshot",[])
    if context.get("mwe_uuid")!=MWE or context.get("synthetic_only") is not True or context.get("scientific_outcomes_authorized") is not False or context.get("materialized_inputs") or len(snapshots)!=5 or {x["decision_id"] for x in snapshots}!=required:
        raise ValueError("five frozen decisions and zero-source synthetic envelope required")
    if any(x.get("metadata_json",{}).get("status")!="FROZEN" for x in snapshots):raise ValueError("frozen authority required")
    out=root/"research_outputs/swing11/s2a_final_binding";out.mkdir(parents=True,exist_ok=True)
    values=[certify_binding(),final_registry(),final_schemas()]
    for name,value in zip(FINAL_FILES,values):(out/name).write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")
    declarations=[{"name":name,"sha256":hashlib.sha256((out/name).read_bytes()).hexdigest(),"bytes":(out/name).stat().st_size} for name in FINAL_FILES[:-1]]
    manifest={"authority":context,"artifacts":declarations,"schemas":final_schemas(),"registry":final_registry(),"synthetic_only":True,"real_forward_outcomes_computed":False,"protected_data_access":False,"scientific_execution_enabled":False,"paid_fallback":False,"billing_evidence_available":False,"preserved_parent_jobs":["42204772-60f1-4ac2-b005-f103e97f14b2","0f54aa61-5c01-4290-af9a-3805d2f2a320"]}
    (out/FINAL_FILES[-1]).write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    paths=[str((out/name).relative_to(root)) for name in FINAL_FILES]
    return {"status":"PASS","artifact":paths[0],"output_paths":paths}
