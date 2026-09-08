from pathlib import Path
p=Path("summarize_9j_validation_robustness.py")
s=p.read_text(encoding="utf-8")
start_marker='        # Spearman correlation without scipy: Pearson correlation of ranks.'
end_marker='        if corr < 0.5: corr_ok=False'
a=s.find(start_marker)
b=s.find(end_marker,a)
if a < 0 or b < 0:
    raise SystemExit("Expected correlation/qdiff block not found; no changes made.")
b = b + len(end_marker)
new = """        # Spearman correlation without scipy: Pearson correlation of ranks.
        dr=dvec.rank(method="average")
        vr=vvec.rank(method="average")
        corr=float(np.corrcoef(dr.to_numpy(dtype=float),vr.to_numpy(dtype=float))[0,1])
        qdiff=float(vvec.loc["Q4"]-vvec.loc["Q1"])
        rec[f"{part.lower()}_shape_corr"]=corr
        rec[f"{part.lower()}_q4_minus_q1"]=qdiff
        rec[f"{part.lower()}_best_bin"]=str(vvec.idxmax())
        rec[f"{part.lower()}_worst_bin"]=str(vvec.idxmin())
        if np.sign(qdiff)!=np.sign(d_q4q1): same_q4q1=False
        if corr < 0.5: corr_ok=False"""
s=s[:a]+new+s[b:]
p.write_text(s,encoding="utf-8")
print("VALIDATION_ROBUSTNESS_BLOCK_REPAIR_V3=PASS")
