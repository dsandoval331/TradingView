from pathlib import Path
import sys
try: sys.stdout.reconfigure(encoding="utf-8",errors="backslashreplace")
except Exception: pass

P=Path("research_second1m_ae2_c2_predictors_v1.py")
if not P.exists():
    raise FileNotFoundError(P)
lines=P.read_text(encoding="utf-8",errors="ignore").splitlines()

print("="*132)
print("A51.3H - EXTRACT ORIGINAL C2 PREDICTOR BUCKETING SCOPE")
print("="*132)

# Print all bucket_by_quantiles call sites with wide context.
idx=[i for i,l in enumerate(lines) if "bucket_by_quantiles(" in l and not l.lstrip().startswith("def ")]
print(f"bucket_by_quantiles call sites: {len(idx)}")
for i in idx:
    lo=max(0,i-70); hi=min(len(lines),i+71)
    print(f"\n--- CALL SITE around line {i+1}: lines {lo+1}-{hi} ---")
    for j in range(lo,hi): print(f"{j+1:5d}: {lines[j]}")

# Also print where ae2 is first formed/filtered and bucket_columns is defined.
tokens=["ae2 =", "ae2=", "bucket_columns", "continuous_features", "feature_columns"]
for tok in tokens:
    idx2=[i for i,l in enumerate(lines) if tok in l]
    for i in idx2[:8]:
        lo=max(0,i-35); hi=min(len(lines),i+56)
        print(f"\n--- TOKEN '{tok}' around line {i+1}: lines {lo+1}-{hi} ---")
        for j in range(lo,hi): print(f"{j+1:5d}: {lines[j]}")

print("\nRESULT: ORIGINAL BUCKETING SCOPE EXTRACTION COMPLETE.")
