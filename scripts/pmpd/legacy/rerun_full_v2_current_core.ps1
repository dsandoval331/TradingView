# PMPD V5 9J — Full 112-symbol rerun under current 50-column V2 core
# Preserves the stale 23-column artifact by writing to a NEW output directory.

$ErrorActionPreference = "Stop"

$OutputDir = "pmpd_v5_9j_vwap_event_path_v2_full50"

Write-Host "=== PRE-RUN CORE SELF-CHECK ==="
python -c "import inspect, hashlib, pathlib; import tr_platform.pmpd_v5.vwap_event_path_v2 as c; p=pathlib.Path(inspect.getfile(c)); print('CORE=',p.resolve()); print('CORE_SHA256=',hashlib.sha256(p.read_bytes()).hexdigest()); s=inspect.getsource(c); req=['source_max_timestamp_utc','directional_vwap_distance_pct','event_vwap_touch_count_from_dp1','event_reclaim_count','event_loss_count','event_directional_rejection_count','event_vwap_loss_after_structural_clearance']; print('ALL_REQUIRED_TERMS_PRESENT=',all(x in s for x in req)); print({x:(x in s) for x in req})"

Write-Host "`n=== FULL 112-SYMBOL BUILD ==="
python -m tr_platform.pmpd_v5.vwap_event_path_v2_cli --repo-root . --year 2025 --output-dir $OutputDir

Write-Host "`n=== POST-RUN SCHEMA / POPULATION CHECK ==="
python -c "import pandas as pd, json, pathlib; o=pathlib.Path(r'$OutputDir'); d=pd.read_csv(o/'decision_vwap_event_path_v2.csv'); f=json.loads((o/'run_fingerprint.json').read_text()); req=['source_max_timestamp_utc','directional_vwap_distance_pct','directional_vwap_distance_min_from_dp1_pct','directional_vwap_distance_max_from_dp1_pct','event_vwap_touch_count_from_dp1','event_reclaim_count','event_loss_count','event_directional_rejection_count','event_vwap_loss_after_structural_clearance']; print('ROWS=',len(d)); print('UNIQUE_DECISIONS=',d.decision_id.nunique()); print('EVENTS=',d.event_id.nunique()); print('SYMBOLS=',d.symbol.nunique()); print('PRIMARY_ROWS=',int(d.primary_decision_unit.astype(str).str.lower().eq('true').sum())); print('COLUMN_COUNT=',len(d.columns)); print('MISSING_REQUIRED_COLUMNS=',[c for c in req if c not in d.columns]); print('FINGERPRINT=',f.get('fingerprint')); print('FULL50_BUILD_SCHEMA_GATE=', 'PASS' if (len(d)==450491 and d.decision_id.nunique()==450491 and d.event_id.nunique()==44627 and d.symbol.nunique()==112 and len(d.columns)==50 and all(c in d.columns for c in req)) else 'FAIL')"

Write-Host "`nSTOP: Do not start Discovery or 9K. Run certification on this new output first."
