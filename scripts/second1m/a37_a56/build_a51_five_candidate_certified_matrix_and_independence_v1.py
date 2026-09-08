from pathlib import Path
import pandas as pd
import numpy as np
from itertools import combinations

ROOT=Path("data/second1m_alt_entry_research_v1")
D=ROOT/"ae2_v2_evidence_consolidation_v1"; D.mkdir(parents=True,exist_ok=True)
A37D=ROOT/"ae2_session_level_geometry_v1"
A38D=ROOT/"ae2_preferred_level_timing_v1"
A42D=ROOT/"ae2_opening_location_geometry_v1"
TIM=A38D/"a38_preferred_level_timing_events_v1.parquet"
GEO=A37D/"a37_session_level_geometry_events_v1.parquet"
A37TH=A37D/"a37_geometry_discovery_quintile_thresholds_v1.csv"
A42=A42D/"a42_opening_location_features_v1.parquet"
A42TH=A42D/"a42_discovery_quintile_thresholds_v1.csv"

CANDS=[
"A37_G_N1_PM_PD_SPACING_Q4",
"A37_G_P2_PD_AH_PM_ORDERING",
"A38_T_P1_PM_REMAINS_FOR_C2",
"A38_T_N1_PD_REMAINS_FOR_C2",
"A42_N2_OPEN_CONSUMED_RATIO_Q2",
]
EXP={
CANDS[0]:(73,85), CANDS[1]:(47,62), CANDS[2]:(61,68),
CANDS[3]:(59,43), CANDS[4]:(73,55)
}

def edges37(f):
    x=pd.read_csv(A37TH); fc="feature" if "feature" in x.columns else "metric"
    z=x[x[fc].astype(str).eq(f)]
    cp=dict(zip(z.cutpoint.astype(str).str.lower(),z.value.astype(float)))
    return [-np.inf,cp["q20"],cp["q40"],cp["q60"],cp["q80"],np.inf]
def edges42(f):
    x=pd.read_csv(A42TH); fc="feature" if "feature" in x.columns else "metric"
    r=x[x[fc].astype(str).eq(f)].iloc[0]
    return [-np.inf,float(r.edge_1),float(r.edge_2),float(r.edge_3),float(r.edge_4),np.inf]
def qb(s,e): return pd.cut(s,e,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)
def phi(a,b):
    a=a.astype(bool); b=b.astype(bool)
    n11=int((a&b).sum()); n10=int((a&~b).sum()); n01=int((~a&b).sum()); n00=int((~a&~b).sum())
    den=((n11+n10)*(n01+n00)*(n11+n01)*(n10+n00))**0.5
    return (n11*n00-n10*n01)/den if den else np.nan
def jacc(a,b):
    inter=int((a&b).sum()); union=int((a|b).sum())
    return inter/union if union else np.nan

def main():
    print("="*136)
    print("A51.3L / A51.4 - FIVE-CANDIDATE CERTIFICATION + OUTCOME-FREE INDEPENDENCE AUDIT")
    print("="*136)
    t=pd.read_parquet(TIM); assert len(t)==753
    keys=["symbol","trade_date","direction"]
    u=t[keys+["research_period","quarter","c1_cleared_pattern"]].copy()

    g=pd.read_parquet(GEO)
    u=u.merge(g[keys+["pm_pd_spacing_pct","directional_level_order_inner_to_outer"]].drop_duplicates(keys),
              on=keys,how="left",validate="one_to_one")
    u[CANDS[0]]=qb(u.pm_pd_spacing_pct,edges37("pm_pd_spacing_pct")).eq("Q4")
    u[CANDS[1]]=u.directional_level_order_inner_to_outer.eq("PD>AH>PM")
    u[CANDS[2]]=u.c1_cleared_pattern.eq("AH+PD")
    u[CANDS[3]]=u.c1_cleared_pattern.eq("PM+AH")
    a=pd.read_parquet(A42)
    u=u.merge(a[keys+["a42_priorclose_to_outer_consumed_ratio"]].drop_duplicates(keys),
              on=keys,how="left",validate="one_to_one")
    u[CANDS[4]]=qb(u.a42_priorclose_to_outer_consumed_ratio,edges42("a42_priorclose_to_outer_consumed_ratio")).eq("Q2")

    print(f"\nPopulation={len(u)} DISCOVERY={(u.research_period=='DISCOVERY').sum()} VALIDATION={(u.research_period=='VALIDATION').sum()}")
    ok=True
    for c,e in EXP.items():
        got=(int(u.loc[u.research_period.eq("DISCOVERY"),c].sum()),int(u.loc[u.research_period.eq("VALIDATION"),c].sum()))
        good=got==e; ok &= good
        print(f"{c:42s} {got} {'PASS' if good else 'FAIL expected='+str(e)}")
    if not ok: raise SystemExit("Parity failure; no outputs written.")

    # certified outcome-free matrix
    assert "outcome" not in u.columns
    mp=D/"a51_retained_v2_evidence_matrix_5FACTOR_CERTIFIED_v1.parquet"
    mc=D/"a51_retained_v2_evidence_matrix_5FACTOR_CERTIFIED_v1.csv"
    u.to_parquet(mp,index=False); u.to_csv(mc,index=False)

    # prevalence
    prev=[]
    for c in CANDS:
        for period,z in [("ALL",u),("DISCOVERY",u[u.research_period.eq("DISCOVERY")]),("VALIDATION",u[u.research_period.eq("VALIDATION")])]:
            prev.append({"candidate":c,"period":period,"n":len(z),"fires":int(z[c].sum()),"prevalence_pct":100*z[c].mean()})
    pd.DataFrame(prev).to_csv(D/"a51_4_candidate_prevalence_v1.csv",index=False)

    # pairwise overlap/association
    rows=[]
    for a,b in combinations(CANDS,2):
        A=u[a].astype(bool); B=u[b].astype(bool)
        rows.append({"candidate_a":a,"candidate_b":b,"a_n":int(A.sum()),"b_n":int(B.sum()),
                     "intersection_n":int((A&B).sum()),"union_n":int((A|B).sum()),
                     "jaccard":jacc(A,B),"phi":phi(A,B),
                     "pct_a_covered_by_b":100*(A&B).sum()/A.sum() if A.sum() else np.nan,
                     "pct_b_covered_by_a":100*(A&B).sum()/B.sum() if B.sum() else np.nan})
    pair=pd.DataFrame(rows); pair.to_csv(D/"a51_4_pairwise_overlap_association_v1.csv",index=False)

    # incremental unique coverage
    inc=[]
    anyall=u[CANDS].any(axis=1)
    for c in CANDS:
        others=[x for x in CANDS if x!=c]
        unique=u[c] & ~u[others].any(axis=1)
        inc.append({"candidate":c,"fires":int(u[c].sum()),"unique_only_n":int(unique.sum()),
                    "unique_share_of_candidate_pct":100*unique.sum()/u[c].sum() if u[c].sum() else np.nan})
    pd.DataFrame(inc).to_csv(D/"a51_4_incremental_coverage_v1.csv",index=False)

    # direction and quarter distributions
    dist=[]
    for c in CANDS:
        for d,z in u.groupby("direction"):
            dist.append({"candidate":c,"dimension":"DIRECTION","value":str(d),"population_n":len(z),"fires":int(z[c].sum()),"prevalence_pct":100*z[c].mean()})
        for q,z in u.groupby("quarter"):
            dist.append({"candidate":c,"dimension":"QUARTER","value":str(q),"population_n":len(z),"fires":int(z[c].sum()),"prevalence_pct":100*z[c].mean()})
    pd.DataFrame(dist).to_csv(D/"a51_4_direction_quarter_distribution_v1.csv",index=False)

    print("\nPAIRWISE OVERLAP / ASSOCIATION")
    print(pair.to_string(index=False,float_format=lambda x:f"{x:.4f}"))
    print("\nINCREMENTAL UNIQUE COVERAGE")
    print(pd.DataFrame(inc).to_string(index=False,float_format=lambda x:f"{x:.2f}"))
    print("\nAny retained reproducible candidate fires:",int(anyall.sum()),f"({100*anyall.mean():.2f}%)")
    print("\nCertified matrix:",mp)
    print("RESULT: A51.3L FIVE-FACTOR PARITY PASS; A39 EXCLUDED AS PROVENANCE-CONFLICTED.")
    print("RESULT: A51.4 OUTCOME-FREE INDEPENDENCE AUDIT COMPLETE.")
    print("No outcome rates analyzed. No combinations optimized. No prospective data touched.")

if __name__=="__main__": main()
