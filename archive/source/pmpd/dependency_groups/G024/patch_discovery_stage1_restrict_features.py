from pathlib import Path

p = Path("run_9j_vwap_v2_discovery_stage1.py")
s = p.read_text(encoding="utf-8")

old = 'exclude_exact = {\n    "decision_id","event_id","research_partition","partition",\n    "frozen_primary_outcome","primary_outcome","resolved_outcome","outcome",\n    "source_max_timestamp_utc","decision_timestamp_utc",\n    "dp4_full_stack_first_clear_timestamp_utc","event_last_vwap_loss_timestamp_utc",\n}'
new = 'exclude_exact = {\n    "decision_id","event_id","research_partition","partition",\n    "frozen_primary_outcome","primary_outcome","resolved_outcome","outcome",\n    "source_max_timestamp_utc","decision_timestamp_utc",\n    "dp4_full_stack_first_clear_timestamp_utc","event_last_vwap_loss_timestamp_utc",\n    "rth_vwap_at_decision",\n    "event_vwap_loss_after_first_dp345_legacy",\n    "vwap_event_path_version",\n    "vwap_event_path_derivation_version",\n}'
if old not in s:
    raise SystemExit("Expected exclude_exact block not found; no changes made.")
s = s.replace(old,new,1)

old2 = 'OUTDIR = ROOT / "pmpd_v5_9j_vwap_event_path_v2_analysis" / "discovery_stage1"'
new2 = 'OUTDIR = ROOT / "pmpd_v5_9j_vwap_event_path_v2_analysis" / "discovery_stage1_restricted"'
if old2 not in s:
    raise SystemExit("Expected OUTDIR line not found; no changes made.")
s = s.replace(old2,new2,1)

p.write_text(s,encoding="utf-8")
print("DISCOVERY_STAGE1_RESTRICTED_FEATURE_PATCH_APPLIED=PASS")
