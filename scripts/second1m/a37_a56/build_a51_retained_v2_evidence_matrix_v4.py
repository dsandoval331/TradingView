from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
A37D=ROOT/"ae2_session_level_geometry_v1"
A38D=ROOT/"ae2_preferred_level_timing_v1"
A42D=ROOT/"ae2_opening_location_geometry_v1"
PRED=ROOT/"ae2_c2_predictors_v1"/"ae2_c2_predictor_features_v1.parquet"
GEO=A37D/"a37_session_level_geometry_events_v1.parquet"
TIM=A38D/"a38_preferred_level_timing_events_v1.parquet"
A37TH=A37D/"a37_geometry_discovery_quintile_thresholds_v1.csv"
A42=A42D/"a42_opening_location_features_v1.parquet"
A42TH=A42D/"a42_discovery_quintile_thresholds_v1.csv"
OUTD=ROOT/"ae2_v2_evidence_consolidation_v1"; OUTD.mkdir(parents=True,exist_ok=True)

def q_edges_a37(feature):
    x=pd.read_csv(A37TH); fc="feature" if "feature" in x.columns else "metric"
    z=x[x[fc].astype(str).eq(feature)]
    cp=dict(zip(z.cutpoint.astype(str).str.lower(),z.value.astype(float)))
    return [-np.inf,cp["q20"],cp["q40"],cp["q60"],cp["q80"],np.inf]

def q_edges_a42(feature):
    x=pd.read_csv(A42TH); fc="feature" if "feature" in x.columns else "metric"
    r=x[x[fc].astype(str).eq(feature)].iloc[0]
    return [-np.inf,float(r.edge_1),float(r.edge_2),float(r.edge_3),float(r.edge_4),np.inf]

def q(s,e):
    return pd.cut(s,e,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)

def main():
    print("="*132)
    print("A51.3 V4 - SIX-CANDIDATE EXACT RECONSTRUCTION / PARITY CERTIFICATION")
    print("="*132)

    t=pd.read_parquet(TIM)
    assert len(t)==753, f"Expected 753 Preferred binary events, got {len(t)}"
    keys=["symbol","trade_date","direction"]
    u=t[keys+["research_period","quarter","c1_cleared_pattern"]].copy()

    # A37
    g=pd.read_parquet(GEO)
    u=u.merge(g[keys+["pm_pd_spacing_pct","directional_level_order_inner_to_outer"]].drop_duplicates(keys),
              on=keys,how="left",validate="one_to_one")
    e37=q_edges_a37("pm_pd_spacing_pct")
    u["A37_G_N1_PM_PD_SPACING_Q4"]=q(u.pm_pd_spacing_pct,e37).eq("Q4")
    u["A37_G_P2_PD_AH_PM_ORDERING"]=u.directional_level_order_inner_to_outer.eq("PD>AH>PM")

    # A38
    u["A38_T_P1_PM_REMAINS_FOR_C2"]=u.c1_cleared_pattern.eq("AH+PD")
    u["A38_T_N1_PD_REMAINS_FOR_C2"]=u.c1_cleared_pattern.eq("PM+AH")

    # A39: reproduce ORIGINAL upstream operation exactly.
    # Original C2 predictor code qcut the complete AE2 dataframe (8,307 events),
    # then A39 later filtered to Preferred. We recreate that categorical assignment
    # on the complete predictor population BEFORE joining to the 753 Preferred rows.
    p=pd.read_parquet(PRED)
    assert len(p)==8307, f"Expected original AE2 predictor population 8,307, got {len(p)}"
    raw=pd.to_numeric(p["vwap_distance_change_pp"],errors="coerce")
    a39_bucket=pd.qcut(raw,q=5,duplicates="drop")
    cats=sorted(list(a39_bucket.dropna().unique()),key=lambda v:v.left)
    rank={c:i+1 for i,c in enumerate(cats)}
    pp=p[keys].copy()
    pp["a39_vwap_frozen_q"]=a39_bucket.map(rank).astype("Int64")
    u=u.merge(pp.drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    u["A39_T_V1_VWAP_EXPANSION_Q3"]=u.a39_vwap_frozen_q.eq(3)

    # A42
    a=pd.read_parquet(A42)
    u=u.merge(a[keys+["a42_priorclose_to_outer_consumed_ratio"]].drop_duplicates(keys),
              on=keys,how="left",validate="one_to_one")
    e42=q_edges_a42("a42_priorclose_to_outer_consumed_ratio")
    u["A42_N2_OPEN_CONSUMED_RATIO_Q2"]=q(u.a42_priorclose_to_outer_consumed_ratio,e42).eq("Q2")

    expected={
      "A37_G_N1_PM_PD_SPACING_Q4":(73,85),
      "A37_G_P2_PD_AH_PM_ORDERING":(47,62),
      "A38_T_P1_PM_REMAINS_FOR_C2":(61,68),
      "A38_T_N1_PD_REMAINS_FOR_C2":(59,43),
      "A39_T_V1_VWAP_EXPANSION_Q3":(48,50),
      "A42_N2_OPEN_CONSUMED_RATIO_Q2":(73,55),
    }
    print(f"\nPopulation: {len(u)} | DISCOVERY={(u.research_period=='DISCOVERY').sum()} | VALIDATION={(u.research_period=='VALIDATION').sum()}")
    print("\nPARITY CERTIFICATION")
    ok=True
    for c,e in expected.items():
        got=(int(u.loc[u.research_period.eq("DISCOVERY"),c].sum()),
             int(u.loc[u.research_period.eq("VALIDATION"),c].sum()))
        passed=got==e; ok &= passed
        print(f"{c:42s} discovery={got[0]:3d} validation={got[1]:3d}  {'PASS' if passed else 'FAIL expected='+str(e)}")

    print("\nA39 reconstructed full-AE2 qcut categories:")
    for i,c in enumerate(cats,1):
        print(f"Q{i}: {c}  n={int((pp.a39_vwap_frozen_q==i).sum())}")

    assert "outcome" not in u.columns
    if not ok:
        print("\nRESULT: A51.3 PARITY FAILURE - CERTIFIED MATRIX NOT WRITTEN")
        raise SystemExit(2)

    out=OUTD/"a51_retained_v2_evidence_matrix_CERTIFIED_v1.parquet"
    csv=OUTD/"a51_retained_v2_evidence_matrix_CERTIFIED_v1.csv"
    u.to_parquet(out,index=False); u.to_csv(csv,index=False)
    print(f"\nParquet: {out}\nCSV: {csv}")
    print("RESULT: A51.3 SIX-FACTOR RECONSTRUCTION PARITY PASS - CERTIFIED")
    print("No outcomes analyzed. No prospective data used. Candidate Model V1 unchanged.")

if __name__=="__main__":
    main()
