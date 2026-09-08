from pathlib import Path
import json, hashlib, math
import pandas as pd
import numpy as np

ROOT = Path.cwd()
INFILE = ROOT / "pmpd_v5_9j_vwap_event_path_v2_analysis" / "decision_vwap_event_path_v2_dp4fix_with_frozen_outcome.csv"
OUTDIR = ROOT / "pmpd_v5_9j_vwap_event_path_v2_analysis" / "discovery_stage1_restricted"
OUTDIR.mkdir(parents=True, exist_ok=True)

EXPECTED_JOIN_FP = "e9dbb42aedd9293c7dde24574605f1fdf7049d3cad23fd3fd071e7d4aa2c0910"
MIN_SCOPE_N = 200

def sha256_file(p, chunk=1024*1024):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

print("=== 9J VWAP EVENT-PATH V2 — DISCOVERY STAGE 1 ===")
print("INPUT =", INFILE)
if not INFILE.exists():
    raise SystemExit("INPUT_MISSING")

hdr = pd.read_csv(INFILE, nrows=0)
cols = list(hdr.columns)
print("columns =", len(cols))

def first_present(names):
    for n in names:
        if n in cols:
            return n
    return None

partition_col = first_present(["research_partition","partition"])
outcome_col = first_present(["frozen_primary_outcome","primary_outcome","resolved_outcome","outcome"])
direction_col = first_present(["direction","event_direction","signal_direction","side"])
dp_col = first_present(["decision_type","decision_point_type","decision_point","decision_code","dp_type"])
symbol_col = first_present(["symbol","ticker"])

print("partition_col =", partition_col)
print("outcome_col =", outcome_col)
print("direction_col =", direction_col)
print("decision_type_col =", dp_col)
print("symbol_col =", symbol_col)

if partition_col is None or outcome_col is None:
    raise SystemExit("REQUIRED_COLUMN_RESOLUTION_FAIL")

# Feature whitelist is semantic, not outcome-driven. It selects only VWAP/path-state
# columns already frozen before outcome analysis.
exclude_exact = {
    "decision_id","event_id","research_partition","partition",
    "frozen_primary_outcome","primary_outcome","resolved_outcome","outcome",
    "source_max_timestamp_utc","decision_timestamp_utc",
    "dp4_full_stack_first_clear_timestamp_utc","event_last_vwap_loss_timestamp_utc",
    "rth_vwap_at_decision",
    "event_vwap_loss_after_first_dp345_legacy",
    "vwap_event_path_version",
    "vwap_event_path_derivation_version",
}
exclude_tokens = ("timestamp","price","target","mfe","mae","favorable_first")
feature_cols = []
for c in cols:
    lc = c.lower()
    if c in exclude_exact: 
        continue
    if any(tok in lc for tok in exclude_tokens):
        continue
    if (
        "vwap" in lc
        or lc.startswith("event_minutes_since_")
        or lc in {"side_changed"}
    ):
        feature_cols.append(c)

# Preserve identifiers/context only for grouping.
keep = [partition_col, outcome_col]
for c in [direction_col, dp_col, symbol_col]:
    if c and c not in keep:
        keep.append(c)
for c in feature_cols:
    if c not in keep:
        keep.append(c)

print("frozen_feature_columns_selected =", len(feature_cols))
for c in feature_cols:
    print(" FEATURE", c)

# Crucial anti-peek implementation: chunks are filtered to DISCOVERY before retained.
chunks = []
total_rows_seen = 0
discovery_rows_retained = 0
for ch in pd.read_csv(INFILE, usecols=keep, chunksize=50000, low_memory=False):
    total_rows_seen += len(ch)
    d = ch[ch[partition_col].astype(str).eq("DISCOVERY")].copy()
    discovery_rows_retained += len(d)
    chunks.append(d)
df = pd.concat(chunks, ignore_index=True)

print("total_rows_scanned_for_partition_filter =", total_rows_seen)
print("discovery_rows_retained =", len(df))
if len(df) != 145692:
    raise SystemExit(f"DISCOVERY_ROW_COUNT_FAIL expected=145692 actual={len(df)}")
if not df[partition_col].astype(str).eq("DISCOVERY").all():
    raise SystemExit("ANTI_PEEK_PARTITION_GATE_FAIL")
print("ANTI_PEEK_PARTITION_GATE=PASS")

# Canonical frozen outcomes.
allowed = {"FAVORABLE_FIRST","ADVERSE_FIRST","UNRESOLVED","AMBIGUOUS_SAME_BAR"}
observed = set(df[outcome_col].dropna().astype(str).unique())
if not observed.issubset(allowed):
    raise SystemExit(f"UNEXPECTED_OUTCOME_LABELS={sorted(observed-allowed)}")

outcome_counts = df[outcome_col].astype(str).value_counts(dropna=False).to_dict()
print("DISCOVERY_OUTCOME_COUNTS =", outcome_counts)

# Primary resolved comparison = exact primary research question only.
df["_resolved"] = df[outcome_col].isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])
df["_win"] = np.where(
    df[outcome_col].eq("FAVORABLE_FIRST"), 1.0,
    np.where(df[outcome_col].eq("ADVERSE_FIRST"), 0.0, np.nan)
)

def norm_direction(s):
    z = s.astype(str).str.upper().str.strip()
    out = pd.Series("UNKNOWN", index=s.index, dtype="string")
    out[z.str.contains("BULL|LONG|UP", regex=True, na=False)] = "BULL"
    out[z.str.contains("BEAR|SHORT|DOWN", regex=True, na=False)] = "BEAR"
    return out

if direction_col:
    df["_direction"] = norm_direction(df[direction_col])
else:
    df["_direction"] = "UNKNOWN"

pop_rows = []
for scope, g in [("ALL", df)] + [(x, g) for x,g in df.groupby("_direction", dropna=False)]:
    resolved = g[g["_resolved"]]
    pop_rows.append({
        "scope": scope,
        "rows": len(g),
        "resolved_rows": len(resolved),
        "favorable_first": int((g[outcome_col]=="FAVORABLE_FIRST").sum()),
        "adverse_first": int((g[outcome_col]=="ADVERSE_FIRST").sum()),
        "unresolved": int((g[outcome_col]=="UNRESOLVED").sum()),
        "ambiguous_same_bar": int((g[outcome_col]=="AMBIGUOUS_SAME_BAR").sum()),
        "resolved_favorable_rate": float(resolved["_win"].mean()) if len(resolved) else None,
    })
pd.DataFrame(pop_rows).to_csv(OUTDIR/"discovery_population_summary.csv", index=False)

# Optional decision-point population summary.
if dp_col:
    dps = []
    for keys,g in df.groupby(["_direction", dp_col], dropna=False):
        r = g[g["_resolved"]]
        dps.append({
            "direction": keys[0], "decision_type": keys[1],
            "rows": len(g), "resolved_rows": len(r),
            "resolved_favorable_rate": float(r["_win"].mean()) if len(r) else None,
            "unresolved": int((g[outcome_col]=="UNRESOLVED").sum()),
            "ambiguous_same_bar": int((g[outcome_col]=="AMBIGUOUS_SAME_BAR").sum()),
        })
    pd.DataFrame(dps).sort_values(["direction","decision_type"]).to_csv(
        OUTDIR/"discovery_by_decision_type.csv", index=False
    )

# Coerce semantic feature columns and split numeric/bool-like.
numeric_features = []
bool_features = []
coerced = {}
for c in feature_cols:
    s = df[c]
    sl = s.astype(str).str.lower()
    vals = set(sl.dropna().unique())
    if vals and vals.issubset({"true","false","1","0","1.0","0.0","nan","<na>"}):
        mapped = sl.map({"true":1.0,"false":0.0,"1":1.0,"0":0.0,"1.0":1.0,"0.0":0.0})
        coerced[c] = mapped
        bool_features.append(c)
    else:
        n = pd.to_numeric(s, errors="coerce")
        if n.notna().sum() >= MIN_SCOPE_N:
            coerced[c] = n
            numeric_features.append(c)

print("numeric_features =", len(numeric_features))
print("bool_features =", len(bool_features))

# Descriptive feature summaries by ALL/BULL/BEAR.
summary_rows = []
for c in numeric_features + bool_features:
    x = coerced[c]
    for scope in ["ALL","BULL","BEAR"]:
        mask = pd.Series(True, index=df.index) if scope=="ALL" else df["_direction"].eq(scope)
        v = x[mask].dropna()
        rmask = mask & df["_resolved"] & x.notna()
        if len(v) < MIN_SCOPE_N:
            continue
        row = {
            "feature": c, "feature_kind": "boolean" if c in bool_features else "numeric",
            "scope": scope, "n": int(len(v)),
            "resolved_n": int(rmask.sum()),
            "mean": float(v.mean()), "std": float(v.std(ddof=1)) if len(v)>1 else None,
            "q25": float(v.quantile(.25)), "q50": float(v.quantile(.50)),
            "q75": float(v.quantile(.75)),
            "resolved_favorable_rate": float(df.loc[rmask,"_win"].mean()) if rmask.any() else None,
        }
        summary_rows.append(row)
pd.DataFrame(summary_rows).to_csv(OUTDIR/"discovery_feature_summary.csv", index=False)

# Non-optimized candidate cutpoints: unconditional Discovery Q25/Q50/Q75 only.
# Outcome is used only to DESCRIBE the pre-specified quantile bins after cutpoints exist.
cut_rows = []
bin_rows = []
for c in numeric_features:
    x = coerced[c]
    for scope in ["ALL","BULL","BEAR"]:
        smask = pd.Series(True, index=df.index) if scope=="ALL" else df["_direction"].eq(scope)
        base = x[smask].dropna()
        if len(base) < MIN_SCOPE_N or base.nunique() < 4:
            continue
        qs = base.quantile([.25,.50,.75]).to_dict()
        q25,q50,q75 = float(qs[.25]),float(qs[.50]),float(qs[.75])
        if len({q25,q50,q75}) < 3:
            continue
        cut_rows.append({
            "feature":c,"scope":scope,"n":int(len(base)),
            "cutpoint_method":"UNCONDITIONAL_DISCOVERY_QUARTILES",
            "q25":q25,"q50":q50,"q75":q75
        })
        edges = [-np.inf,q25,q50,q75,np.inf]
        labels = ["Q1","Q2","Q3","Q4"]
        bins = pd.cut(x, bins=edges, labels=labels, include_lowest=True, duplicates="drop")
        rates=[]
        for lab in labels:
            m = smask & df["_resolved"] & bins.eq(lab)
            n=int(m.sum())
            rate=float(df.loc[m,"_win"].mean()) if n else None
            rates.append(rate if rate is not None else np.nan)
            bin_rows.append({
                "feature":c,"scope":scope,"bin":lab,
                "resolved_n":n,"resolved_favorable_rate":rate
            })
        finite=[r for r in rates if not np.isnan(r)]
        spread=max(finite)-min(finite) if len(finite)>=2 else np.nan
        # Add spread to all four just for convenient screening, not threshold optimization.
        for row in bin_rows[-4:]:
            row["quartile_rate_spread"] = float(spread) if not np.isnan(spread) else None

pd.DataFrame(cut_rows).to_csv(OUTDIR/"discovery_unconditional_quantile_cutpoints.csv", index=False)
bins_df = pd.DataFrame(bin_rows)
bins_df.to_csv(OUTDIR/"discovery_quantile_bin_outcomes.csv", index=False)

# Boolean event/path states: prevalence + outcome description, no threshold search.
bool_rows=[]
for c in bool_features:
    x=coerced[c]
    for scope in ["ALL","BULL","BEAR"]:
        smask = pd.Series(True,index=df.index) if scope=="ALL" else df["_direction"].eq(scope)
        for val in [0.0,1.0]:
            m=smask & x.eq(val)
            rm=m & df["_resolved"]
            if m.sum() < MIN_SCOPE_N: continue
            bool_rows.append({
                "feature":c,"scope":scope,"value":int(val),
                "n":int(m.sum()),"resolved_n":int(rm.sum()),
                "resolved_favorable_rate":float(df.loc[rm,"_win"].mean()) if rm.any() else None
            })
pd.DataFrame(bool_rows).to_csv(OUTDIR/"discovery_boolean_state_outcomes.csv", index=False)

# Symbol-cluster descriptive table for later robustness design. Discovery only.
if symbol_col:
    sym=[]
    for keys,g in df.groupby(["_direction",symbol_col],dropna=False):
        r=g[g["_resolved"]]
        if len(r)==0: continue
        sym.append({
            "direction":keys[0],"symbol":keys[1],
            "rows":len(g),"resolved_rows":len(r),
            "resolved_favorable_rate":float(r["_win"].mean())
        })
    pd.DataFrame(sym).to_csv(OUTDIR/"discovery_symbol_cluster_summary.csv",index=False)

manifest = {
    "experiment":"PMPD_V5_9J_VWAP_EVENT_PATH_V2",
    "stage":"DISCOVERY_STAGE1",
    "input_file":str(INFILE),
    "input_sha256":sha256_file(INFILE),
    "expected_join_fingerprint_reference":EXPECTED_JOIN_FP,
    "rows_scanned":int(total_rows_seen),
    "discovery_rows_analyzed":int(len(df)),
    "validation_outcomes_characterized":False,
    "minimum_scope_n":MIN_SCOPE_N,
    "primary_outcome_definition":"FAVORABLE_FIRST vs ADVERSE_FIRST; UNRESOLVED and AMBIGUOUS_SAME_BAR preserved but excluded from resolved hit-rate denominator",
    "cutpoint_policy":"Only unconditional Discovery Q25/Q50/Q75. No outcome-optimized threshold search.",
    "feature_selection_policy":"Frozen VWAP/event-path semantic columns only; excludes target/MFE/MAE/raw outcome/timestamp/price fields.",
    "direction_column":direction_col,
    "decision_type_column":dp_col,
    "symbol_column":symbol_col,
    "numeric_features":numeric_features,
    "boolean_features":bool_features,
}
(OUTDIR/"discovery_stage1_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

print("OUTPUT_DIR =", OUTDIR)
print("DISCOVERY_STAGE1_GATE=PASS")
print("VALIDATION_OUTCOMES_CHARACTERIZED=False")
print("NO_OUTCOME_OPTIMIZED_THRESHOLDS=True")
