# PMPD V5 9J — Full VWAP Event-Path V2 build + integrity certification
# Run from C:\Users\DirtySouth\TradingResearch with .venv active.
$ErrorActionPreference = "Stop"

Write-Host "=== 9J V2 FULL 112-SYMBOL BUILD ===" -ForegroundColor Cyan
python -m tr_platform.pmpd_v5.vwap_event_path_v2_cli --repo-root . --year 2025 --output-dir pmpd_v5_9j_vwap_event_path_v2_full

Write-Host "`n=== 9J V2 FULL INTEGRITY CERTIFICATION ===" -ForegroundColor Cyan
python -c @'
import json
from pathlib import Path
import pandas as pd
from tr_platform.pmpd_v5.vwap_event_path_v2 import audit

root = Path(".").resolve()
parent_path = root / "pmpd_v5_9h_research_dataset_v1" / "decision_research.csv"
v2_path = root / "pmpd_v5_9j_vwap_event_path_v2_full" / "decision_vwap_event_path_v2.csv"
summary_path = root / "pmpd_v5_9j_vwap_event_path_v2_full" / "symbol_summary.csv"
fp_path = root / "pmpd_v5_9j_vwap_event_path_v2_full" / "run_fingerprint.json"

parent = pd.read_csv(parent_path)
v2 = pd.read_csv(v2_path)
summary = pd.read_csv(summary_path)
meta = json.loads(fp_path.read_text(encoding="utf-8"))

checks = audit(parent, v2)

print("PARENT_ROWS=", len(parent))
print("PARENT_UNIQUE_DECISIONS=", parent["decision_id"].nunique())
print("PARENT_EVENTS=", parent["event_id"].nunique())
print("PARENT_SYMBOLS=", parent["symbol"].nunique())

print("V2_ROWS=", len(v2))
print("V2_UNIQUE_DECISIONS=", v2["decision_id"].nunique())
print("V2_EVENTS=", v2["event_id"].nunique())
print("V2_SYMBOLS=", v2["symbol"].nunique())
print("V2_PRIMARY_ROWS=", int(v2["primary_decision_unit"].astype(str).str.lower().eq("true").sum()))

print("SYMBOL_SUMMARY_ROWS=", len(summary))
print("SYMBOL_ROWS_MIN=", int(summary["rows"].min()))
print("SYMBOL_ROWS_MAX=", int(summary["rows"].max()))
print("SYMBOL_ZERO_ROW_COUNT=", int((summary["rows"] == 0).sum()))

print("TOUCH_MISSING=", int(v2["event_vwap_touch_from_dp1"].isna().sum()))
print("CROSS_COUNT_NEGATIVE=", int((pd.to_numeric(v2["event_vwap_cross_count_from_dp1"], errors="coerce") < 0).sum()))
print("TOUCH_COUNT_NEGATIVE=", int((pd.to_numeric(v2["event_vwap_touch_count_from_dp1"], errors="coerce") < 0).sum()))
print("RECLAIM_COUNT_NEGATIVE=", int((pd.to_numeric(v2["event_reclaim_count"], errors="coerce") < 0).sum()))
print("LOSS_COUNT_NEGATIVE=", int((pd.to_numeric(v2["event_loss_count"], errors="coerce") < 0).sum()))
print("REJECTION_COUNT_NEGATIVE=", int((pd.to_numeric(v2["event_directional_rejection_count"], errors="coerce") < 0).sum()))

for c in [
    "event_minutes_from_dp1",
    "event_minutes_since_last_touch",
    "event_minutes_since_last_cross",
    "event_minutes_since_last_reclaim",
    "event_minutes_since_last_loss",
    "event_minutes_since_last_rejection",
]:
    s = pd.to_numeric(v2[c], errors="coerce")
    print(f"{c.upper()}_NEGATIVE=", int((s.dropna() < 0).sum()))

p = parent[["decision_id","event_id","symbol","trade_date","direction","decision_type","split",
            "primary_inference_eligible","primary_decision_unit","resolved_primary","favorable_first"]].copy()
j = p.merge(v2[["decision_id","source_max_timestamp_utc","dp1_timestamp_utc","timestamp_utc"]],
            on="decision_id", how="left", validate="one_to_one")
print("JOIN_ROWS=", len(j))
print("JOIN_MISSING_V2=", int(j["source_max_timestamp_utc"].isna().sum()))

print("AUDIT=", checks)
print("RUN_FINGERPRINT=", meta.get("fingerprint"))
print("RUN_META=", json.dumps(meta, sort_keys=True))

# Frozen split counts: outcomes are not analyzed here.
print("SPLIT_COUNTS=", parent["split"].value_counts(dropna=False).sort_index().to_dict())

overall_pass = (
    checks.get("PASS", False)
    and len(parent) == 450491
    and parent["decision_id"].nunique() == 450491
    and parent["event_id"].nunique() == 44627
    and v2["decision_id"].nunique() == 450491
    and v2["event_id"].nunique() == 44627
    and v2["symbol"].nunique() == 112
    and int((summary["rows"] == 0).sum()) == 0
    and int(j["source_max_timestamp_utc"].isna().sum()) == 0
)
print("FULL_V2_INTEGRITY_CERTIFICATION=", "PASS" if overall_pass else "FAIL")
'@

Write-Host "`n=== OUTPUT FILES ===" -ForegroundColor Cyan
Get-ChildItem .\pmpd_v5_9j_vwap_event_path_v2_full | Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize

Write-Host "`nSTOP HERE. Do not begin 9K." -ForegroundColor Yellow
