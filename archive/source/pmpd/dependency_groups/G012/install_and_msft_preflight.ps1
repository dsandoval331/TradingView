# Run from C:\Users\DirtySouth\TradingResearch with .venv active
$ErrorActionPreference="Stop"
Copy-Item .\tr_platform\pmpd_v5\vwap_event_path_v2.py .\tr_platform\pmpd_v5\vwap_event_path_v2.pre_protocol_patch.bak.py -Force
Copy-Item .\vwap_event_path_v2.py .\tr_platform\pmpd_v5\vwap_event_path_v2.py -Force

python -m py_compile .\tr_platform\pmpd_v5\vwap_event_path_v2.py
python -c "import pandas as pd; from pathlib import Path; from tr_platform.pmpd_v5.vwap_event_path_v2 import build_symbol,audit; from tr_platform.historical.certified_dataset import load_certified_partition; p=load_certified_partition(symbol='MSFT',year=2025,repo_root=Path('.').resolve(),verify_hash=True); q=build_symbol(p.dataframe.copy(),symbol='MSFT'); parent=pd.read_csv('pmpd_v5_alpha_0_2_full_universe/decision_points.csv'); parent=parent[parent.event_id.str.startswith('MSFT_')].copy(); print('MSFT V2 rows=',len(q)); print('MSFT parent rows=',len(parent)); print('V2 unique=',q.decision_id.nunique()); print('AUDIT=',audit(parent,q)); print('columns=',list(q.columns)); print(q.head(3).to_string())"
