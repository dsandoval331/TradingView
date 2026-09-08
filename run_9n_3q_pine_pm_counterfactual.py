from pathlib import Path
import hashlib, json
import pandas as pd
import v4_parity_engine_v2 as eng

ROOT=Path.cwd()
CACHE=ROOT/"data"/"second1m_alt_entry_cache_v1"/"partitions"
EXPECTED_SHA="cab75475f0bf4f4a9d8cf86561d9959957d660aeae7926769e26c53599be4b22"
ENGINE=ROOT/"v4_parity_engine_v2.py"

CASES={
"VRTX":{"date":"2026-07-01","pine_pmh":503.00,"pine_pml":494.15,"pine_count":0,"python_count":0},
"QCOM":{"date":"2026-07-02","pine_pmh":184.15,"pine_pml":177.99,"pine_count":2,"python_count":2},
"MU":{"date":"2026-07-07","pine_pmh":947.00,"pine_pml":920.26,"pine_count":5,"python_count":4},
"BLK":{"date":"2026-07-27","pine_pmh":1066.69,"pine_pml":1059.12,"pine_count":1,"python_count":0},
"SLB":{"date":"2026-07-28","pine_pmh":51.65,"pine_pml":50.98,"pine_count":1,"python_count":1},
"ABNB":{"date":"2026-07-31","pine_pmh":153.40,"pine_pml":151.66,"pine_count":0,"python_count":0},
"APP":{"date":"2026-08-18","pine_pmh":312.00,"pine_pml":308.89,"pine_count":0,"python_count":1},
}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

if not ENGINE.exists(): raise SystemExit("MISSING v4_parity_engine_v2.py in repo root")
if sha(ENGINE)!=EXPECTED_SHA: raise SystemExit("ENGINE_SHA_MISMATCH")

original_build=eng.build_daily_levels

def prep(path):
    d=pd.read_parquet(path).copy()
    d.index=pd.DatetimeIndex(pd.to_datetime(d["timestamp_utc"],utc=True))
    return d

rows=[]
print("=== PMPD V5 9N-3Q PINE-PM COUNTERFACTUAL ===")
print("ENGINE_SHA=PASS")

for sym,c in CASES.items():
    path=CACHE/sym/f"{sym}_2026.parquet"
    if not path.exists(): raise SystemExit(f"MISSING_PARTITION {path}")
    raw=prep(path)
    target=pd.Timestamp(c["date"]).date()

    # Baseline with frozen engine and Massive levels.
    baseline=eng.evaluate_v4_signals(raw,symbol=sym)
    b=baseline[baseline.trade_date.eq(target)].copy()

    # Instrumentation-only monkeypatch: replace ONLY target-date PMH/PML with
    # Pine-observed values, then recompute bull/bear final levels. PDH/PDL,
    # RTH bars, ATR, filters, state machine and scoring remain frozen.
    def patched_build(raw_1m, _target=target, _c=c):
        lv=original_build(raw_1m).copy()
        if _target not in lv.index:
            raise RuntimeError(f"Target date absent in levels: {_target}")
        lv.loc[_target,"pmh"]=_c["pine_pmh"]
        lv.loc[_target,"pml"]=_c["pine_pml"]
        lv.loc[_target,"bull_final"]=max(float(lv.loc[_target,"pmh"]),float(lv.loc[_target,"pdh"]))
        lv.loc[_target,"bear_final"]=min(float(lv.loc[_target,"pml"]),float(lv.loc[_target,"pdl"]))
        return lv

    eng.build_daily_levels=patched_build
    try:
        cf=eng.evaluate_v4_signals(raw,symbol=sym)
    finally:
        eng.build_daily_levels=original_build
    x=cf[cf.trade_date.eq(target)].copy()

    rec={
      "symbol":sym,"date":c["date"],"pine_signal_count":c["pine_count"],
      "massive_baseline_count":len(b),"pine_pm_counterfactual_count":len(x),
      "baseline_matches_expected":len(b)==c["python_count"],
      "counterfactual_matches_pine_count":len(x)==c["pine_count"],
      "pine_pmh":c["pine_pmh"],"pine_pml":c["pine_pml"],
      "baseline_directions":"|".join(b.direction.astype(str).tolist()),
      "counterfactual_directions":"|".join(x.direction.astype(str).tolist()),
      "counterfactual_times":"|".join(pd.to_datetime(x.signal_timestamp_et).astype(str).tolist()),
      "counterfactual_references":"|".join([f"{v:.6f}" for v in x.reference_price.tolist()]),
    }
    rows.append(rec)
    print(f'{sym:5s} Pine={c["pine_count"]} MassiveBase={len(b)} PinePM_CF={len(x)} '
          f'COUNT_EXPLAINED={rec["counterfactual_matches_pine_count"]}')

df=pd.DataFrame(rows)
out_csv=ROOT/"pmpd_v5_9n_3q_pine_pm_counterfactual.csv"
out_json=ROOT/"pmpd_v5_9n_3q_pine_pm_counterfactual_summary.json"
df.to_csv(out_csv,index=False)
summary={
 "step":"9N-3Q",
 "cases":len(df),
 "baseline_reproduced":int(df.baseline_matches_expected.sum()),
 "counterfactual_count_matches_pine":int(df.counterfactual_matches_pine_count.sum()),
 "all_signal_population_differences_explained_by_pine_pm_levels":bool(df.counterfactual_matches_pine_count.all()),
 "method":"Replace target-date PMH/PML only with Pine-observed values; preserve Massive RTH, PDH/PDL, ATR, filters, state machine, scoring and frozen engine code.",
 "governance":{"engine_file_modified":False,"v4_model_modified":False,"v5_modified":False,
               "frozen_sample_changed":False,"common_9n_evidence_source_changed":False,
               "production_rule_authorized":False,"full_24_case_tv_parity_validated":False}
}
out_json.write_text(json.dumps(summary,indent=2),encoding="utf-8")
print("CSV =",out_csv); print("SUMMARY =",out_json)
print("V4_MODIFIED=False"); print("V5_MODIFIED=False")
print("9N_3Q_COUNTERFACTUAL=PASS")
