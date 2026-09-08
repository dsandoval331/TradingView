from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
A37D=ROOT/"ae2_session_level_geometry_v1"
A38D=ROOT/"ae2_preferred_level_timing_v1"
A42D=ROOT/"ae2_opening_location_geometry_v1"
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
GEO=A37D/"a37_session_level_geometry_events_v1.parquet"
TIM=A38D/"a38_preferred_level_timing_events_v1.parquet"
A37TH=A37D/"a37_geometry_discovery_quintile_thresholds_v1.csv"
A42=A42D/"a42_opening_location_features_v1.parquet"
A42TH=A42D/"a42_discovery_quintile_thresholds_v1.csv"
OUTD=ROOT/"ae2_v2_evidence_consolidation_v1"; OUTD.mkdir(parents=True,exist_ok=True)
OUT=OUTD/"a51_retained_v2_evidence_matrix_v2.parquet"
OUTCSV=OUTD/"a51_retained_v2_evidence_matrix_v2.csv"

def q_edges_a37(feature):
    x=pd.read_csv(A37TH)
    # support either metric/feature naming
    fc="feature" if "feature" in x.columns else "metric"
    z=x[x[fc].astype(str).eq(feature)].copy()
    if len(z)!=4: raise ValueError(f"A37 thresholds for {feature}: expected 4 rows, got {len(z)}")
    cp=dict(zip(z["cutpoint"].astype(str).str.lower(),z["value"].astype(float)))
    return [-np.inf,cp["q20"],cp["q40"],cp["q60"],cp["q80"],np.inf]

def q_edges_a42(feature):
    x=pd.read_csv(A42TH)
    fc="feature" if "feature" in x.columns else "metric"
    z=x[x[fc].astype(str).eq(feature)]
    if len(z)!=1: raise ValueError(f"A42 thresholds for {feature}: expected 1 row, got {len(z)}")
    r=z.iloc[0]
    return [-np.inf,float(r.edge_1),float(r.edge_2),float(r.edge_3),float(r.edge_4),np.inf]

def bucket(s,e):
    return pd.cut(s,e,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)

def main():
    print("="*132); print("A51.2 V2 - RETAINED V2 EVIDENCE MATRIX USING PERSISTED FROZEN CUTPOINTS"); print("="*132)
    t=pd.read_parquet(TIM)
    assert len(t)==753, f"Expected authoritative Preferred binary population 753, got {len(t)}"
    keys=["symbol","trade_date","direction"]
    u=t[keys+["research_period","quarter","c1_cleared_pattern"]].copy()
    print(f"Authoritative Preferred binary population: {len(u)} (DISCOVERY={(u.research_period=='DISCOVERY').sum()}, VALIDATION={(u.research_period=='VALIDATION').sum()})")

    g=pd.read_parquet(GEO)
    u=u.merge(g[keys+["pm_pd_spacing_pct","directional_level_order_inner_to_outer"]].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    e37=q_edges_a37("pm_pd_spacing_pct")
    u["a37_pm_pd_spacing_q"]=bucket(u.pm_pd_spacing_pct,e37)
    u["A37_G_N1_PM_PD_SPACING_Q4"]=u.a37_pm_pd_spacing_q.eq("Q4")
    u["A37_G_P2_PD_AH_PM_ORDERING"]=u.directional_level_order_inner_to_outer.eq("PD>AH>PM")

    u["A38_T_P1_PM_REMAINS_FOR_C2"]=u.c1_cleared_pattern.eq("AH+PD")
    u["A38_T_N1_PD_REMAINS_FOR_C2"]=u.c1_cleared_pattern.eq("PM+AH")

    b=pd.read_parquet(BASE)
    if "vwap_distance_change_pp__bucket" not in b.columns:
        raise KeyError("Frozen vwap_distance_change_pp__bucket missing from baseline")
    u=u.merge(b[keys+["vwap_distance_change_pp__bucket"]].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    u["A39_T_V1_VWAP_EXPANSION_Q3"]=u.vwap_distance_change_pp__bucket.astype(str).str.upper().str.extract(r"(Q[1-5])",expand=False).eq("Q3")

    a=pd.read_parquet(A42)
    u=u.merge(a[keys+["a42_priorclose_to_outer_consumed_ratio"]].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    e42=q_edges_a42("a42_priorclose_to_outer_consumed_ratio")
    u["a42_consumed_ratio_q"]=bucket(u.a42_priorclose_to_outer_consumed_ratio,e42)
    u["A42_N2_OPEN_CONSUMED_RATIO_Q2"]=u.a42_consumed_ratio_q.eq("Q2")

    cs=["A37_G_N1_PM_PD_SPACING_Q4","A37_G_P2_PD_AH_PM_ORDERING","A38_T_P1_PM_REMAINS_FOR_C2","A38_T_N1_PD_REMAINS_FOR_C2","A39_T_V1_VWAP_EXPANSION_Q3","A42_N2_OPEN_CONSUMED_RATIO_Q2"]
    print("\nPARITY TARGETS (counts only; outcome-free matrix)")
    expected={
      "A37_G_N1_PM_PD_SPACING_Q4":(73,85),
      "A37_G_P2_PD_AH_PM_ORDERING":(47,62),
      "A38_T_P1_PM_REMAINS_FOR_C2":(61,68),
      "A38_T_N1_PD_REMAINS_FOR_C2":(59,43),
      "A42_N2_OPEN_CONSUMED_RATIO_Q2":(73,55),
    }
    ok=True
    for c in cs:
        dn=int(u.loc[u.research_period.eq("DISCOVERY"),c].sum())
        vn=int(u.loc[u.research_period.eq("VALIDATION"),c].sum())
        if c in expected:
            exp=expected[c]; status="PASS" if (dn,vn)==exp else f"FAIL expected={exp}"
            ok &= (dn,vn)==exp
        else: status="RECORDED (A39 parity target checked next)"
        print(f"{c:42s} discovery={dn:3d} validation={vn:3d}  {status}")

    # strict firewall: no outcome column.
    assert "outcome" not in u.columns
    u.to_parquet(OUT,index=False); u.to_csv(OUTCSV,index=False)
    print("\nPersisted cutpoints used:")
    print("A37:",A37TH); print("A37 PM-PD edges:",e37)
    print("A42:",A42TH); print("A42 consumed-ratio edges:",e42)
    print(f"\nParquet: {OUT}\nCSV: {OUTCSV}")
    print("RESULT:", "A51.2 CORE PARITY PASS" if ok else "A51.2 PARITY FAILURE - STOP BEFORE A51.3")
    print("No outcomes analyzed. No thresholds recomputed. No prospective data touched.")
if __name__=="__main__": main()
