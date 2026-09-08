from pathlib import Path
import inspect
import pandas as pd
import tr_platform.pmpd_v5.vwap_event_path_v2 as core
import tr_platform.pmpd_v5.vwap_event_path_v2_cli as cli

root=Path(".").resolve()
print("=== MODULE PATHS ===")
print("CORE=", Path(inspect.getfile(core)).resolve())
print("CLI =", Path(inspect.getfile(cli)).resolve())

core_src=inspect.getsource(core)
cli_src=inspect.getsource(cli)

terms=[
    "source_max_timestamp_utc",
    "directional_vwap_distance_pct",
    "event_vwap_touch_count_from_dp1",
    "event_reclaim_seen",
    "event_loss_after_structural_clearance",
]
print("\n=== CORE SOURCE TERM CHECK ===")
for t in terms:
    print(t, "=", t in core_src)

print("\n=== CLI SOURCE TERM CHECK ===")
for t in terms:
    print(t, "=", t in cli_src)

print("\n=== CLI LINES INVOLVING COLUMNS / EXPORT ===")
for i,line in enumerate(cli_src.splitlines(),1):
    low=line.lower()
    if any(k in low for k in ["column","to_csv","output","decision_vwap","reindex","select","fields"]):
        print(f"{i:04d}: {line}")

print("\n=== EXISTING V2 OUTPUT FILES ===")
files=sorted(root.rglob("decision_vwap_event_path_v2.csv"))
for f in files:
    try:
        d=pd.read_csv(f,nrows=1)
        print(f"\nFILE={f}")
        print("MTIME=", f.stat().st_mtime)
        print("COLUMN_COUNT=",len(d.columns))
        print("HAS_SOURCE_MAX=", "source_max_timestamp_utc" in d.columns)
        print("COLUMNS=", list(d.columns))
    except Exception as e:
        print("READ_ERROR",f,e)

print("\n=== CORE SOURCE LINES FOR PATCHED FIELDS ===")
for i,line in enumerate(core_src.splitlines(),1):
    if any(t in line for t in terms):
        print(f"{i:04d}: {line}")

print("\nDIAGNOSTIC_COMPLETE")
