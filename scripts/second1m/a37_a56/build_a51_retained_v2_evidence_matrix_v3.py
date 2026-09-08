from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
A37D=ROOT/"ae2_session_level_geometry_v1"
A38D=ROOT/"ae2_preferred_level_timing_v1"
A39D=ROOT/"ae2_c1_c2_transition_v1"
A42D=ROOT/"ae2_opening_location_geometry_v1"
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
GEO=A37D/"a37_session_level_geometry_events_v1.parquet"
TIM=A38D/"a38_preferred_level_timing_events_v1.parquet"
A37TH=A37D/"a37_geometry_discovery_quintile_thresholds_v1.csv"
A39INV=A39D/"a39_frozen_transition_bucket_inventory_v1.csv"
A42=A42D/"a42_opening_location_features_v1.parquet"
A42TH=A42D/"a42_discovery_quintile_thresholds_v1.csv"
OUTD=ROOT/"ae2_v2_evidence_consolidation_v1"; OUTD.mkdir(parents=True,exist_ok=True)

def edges_a37(feature):
    x=pd.read_csv(A37TH); fc="feature" if "feature" in x else "metric"
    z=x[x[fc].astype(str).eq(feature)]
    cp=dict(zip(z.cutpoint.astype(str).str.lower(),z.value.astype(float)))
    return [-np.inf,cp["q20"],cp["q40"],cp["q60"],cp["q80"],np.inf]

def edges_a42(feature):
    x=pd.read_csv(A42TH); fc="feature" if "feature" in x else "metric"
    r=x[x[fc].astype(str).eq(feature)].iloc[0]
    return [-np.inf,float(r.edge_1),float(r.edge_2),float(r.edge_3),float(r.edge_4),np.inf]

def edges_a39(feature):
    x=pd.read_csv(A39INV)
    z=x[x.feature.astype(str).eq(feature)].copy()
    if len(z)!=5: raise ValueError(f"A39 {feature}: expected 5 frozen buckets, got {len(z)}")
    # Use persisted observed bucket boundaries. Adjacent max/min have tiny gaps because
    # pandas interval labels were rounded; midpoint is deterministic and outcome-free.
    z=z.sort_values("min_value")
    cuts=[]
    for i in range(4):
        cuts.append((float(z.iloc[i].max_value)+float(z.iloc[i+1].min_value))/2.0)
    return [-np.inf,*cuts,np.inf]

def q(s,e): return pd.cut(s,e,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)

def main():
    print("="*132); print("A51.3 - SIX-CANDIDATE RECONSTRUCTION PARITY CERTIFICATION"); print("="*132)
    t=pd.read_parquet(TIM); assert len(t)==753
    keys=["symbol","trade_date","direction"]
    u=t[keys+["research_period","quarter","c1_cleared_pattern"]].copy()
    print(f"Authoritative Preferred binary population: {len(u)} (DISCOVERY={(u.research_period=='DISCOVERY').sum()}, VALIDATION={(u.research_period=='VALIDATION').sum()})")

    g=pd.read_parquet(GEO)
    u=u.merge(g[keys+["pm_pd_spacing_pct","directional_level_order_inner_to_outer"]].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    e37=edges_a37("pm_pd_spacing_pct")
    u["A37_G_N1_PM_PD_SPACING_Q4"]=q(u.pm_pd_spacing_pct,e37).eq("Q4")
    u["A37_G_P2_PD_AH_PM_ORDERING"]=u.directional_level_order_inner_to_outer.eq("PD>AH>PM")
    u["A38_T_P1_PM_REMAINS_FOR_C2"]=u.c1_cleared_pattern.eq("AH+PD")
    u["A38_T_N1_PD_REMAINS_FOR_C2"]=u.c1_cleared_pattern.eq("PM+AH")

    b=pd.read_parquet(BASE)
    if "vwap_distance_change_pp" not in b.columns:
        raise KeyError("Raw frozen-source vwap_distance_change_pp not found in baseline artifact")
    u=u.merge(b[keys+["vwap_distance_change_pp"]].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    e39=edges_a39("vwap_distance_change_pp")
    u["A39_T_V1_VWAP_EXPANSION_Q3"]=q(u.vwap_distance_change_pp,e39).eq("Q3")

    a=pd.read_parquet(A42)
    u=u.merge(a[keys+["a42_priorclose_to_outer_consumed_ratio"]].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    e42=edges_a42("a42_priorclose_to_outer_consumed_ratio")
    u["A42_N2_OPEN_CONSUMED_RATIO_Q2"]=q(u.a42_priorclose_to_outer_consumed_ratio,e42).eq("Q2")

    exp={
      "A37_G_N1_PM_PD_SPACING_Q4":(73,85),
      "A37_G_P2_PD_AH_PM_ORDERING":(47,62),
      "A38_T_P1_PM_REMAINS_FOR_C2":(61,68),
      "A38_T_N1_PD_REMAINS_FOR_C2":(59,43),
      "A39_T_V1_VWAP_EXPANSION_Q3":(48,50),
      "A42_N2_OPEN_CONSUMED_RATIO_Q2":(73,55),
    }
    ok=True
    print("\nEXACT PARITY")
    for c,e in exp.items():
        got=(int(u.loc[u.research_period.eq("DISCOVERY"),c].sum()),int(u.loc[u.research_period.eq("VALIDATION"),c].sum()))
        st="PASS" if got==e else f"FAIL expected={e}"
        ok &= got==e
        print(f"{c:42s} discovery={got[0]:3d} validation={got[1]:3d}  {st}")

    print("\nPersisted/reconstructed edges:")
    print("A37 PM-PD:",e37)
    print("A39 VWAP change:",e39)
    print("A42 consumed ratio:",e42)
    assert "outcome" not in u.columns
    if not ok:
        print("\nRESULT: A51.3 PARITY FAILURE - NO CERTIFIED MATRIX WRITTEN")
        raise SystemExit(2)
    out=OUTD/"a51_retained_v2_evidence_matrix_CERTIFIED_v1.parquet"
    csv=OUTD/"a51_retained_v2_evidence_matrix_CERTIFIED_v1.csv"
    u.to_parquet(out,index=False); u.to_csv(csv,index=False)
    print(f"\nParquet: {out}\nCSV: {csv}")
    print("RESULT: A51.3 SIX-FACTOR RECONSTRUCTION PARITY PASS — CERTIFIED")
    print("No outcomes analyzed. No thresholds optimized. No prospective data touched.")
if __name__=="__main__": main()
