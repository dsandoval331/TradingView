from pathlib import Path
p=Path("summarize_9j_validation_robustness.py")
s=p.read_text(encoding="utf-8")
marker='        # Spearman correlation without scipy: Pearson correlation of ranks.'
use='        rec[f"{part.lower()}_shape_corr"]=corr'
a=s.find(marker)
b=s.find(use,a)
if a < 0 or b < 0:
    raise SystemExit("Expected patched correlation region not found; no changes made.")
new = marker + "\n" + '        dr=dvec.rank(method="average")' + "\n" + '        vr=vvec.rank(method="average")' + "\n" + '        corr=float(np.corrcoef(dr.to_numpy(dtype=float),vr.to_numpy(dtype=float))[0,1])' + "\n"
s=s[:a]+new+s[b:]
p.write_text(s,encoding="utf-8")
print("VALIDATION_ROBUSTNESS_CORR_SCOPE_PATCH_V2=PASS")
