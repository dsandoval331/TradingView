from pathlib import Path
p=Path("summarize_9j_validation_robustness.py")
s=p.read_text(encoding="utf-8")
old='corr=float(dvec.corr(vvec,method="spearman"))'
new='# Spearman correlation without scipy: Pearson correlation of ranks.\\n        dr=dvec.rank(method="average")\\n        vr=vvec.rank(method="average")\\n        corr=float(np.corrcoef(dr.to_numpy(dtype=float),vr.to_numpy(dtype=float))[0,1])'
if old not in s:
    raise SystemExit("Expected scipy-dependent line not found; no changes made.")
s=s.replace(old,new,1)
p.write_text(s,encoding="utf-8")
print("VALIDATION_ROBUSTNESS_NO_SCIPY_PATCH=PASS")
