from pathlib import Path
from datetime import datetime
import json, zipfile
import pandas as pd

from tr_platform.pmpd_v5.vwap_event_path_v2 import build_symbol
from tr_platform.market_data.partition_loader import load_certified_partition

root=Path(".").resolve()
out=root/"pmpd_v5_9j_vwap_event_path_v2"
csv=out/"decision_vwap_event_path_v2.csv"
zip_path=root/"pmpd_v5_9j_vwap_event_path_v2.zip"
fp=out/"run_fingerprint.json"

def fmt_mtime(p):
    return datetime.fromtimestamp(p.stat().st_mtime).isoformat(sep=" ", timespec="seconds") if p.exists() else "MISSING"

print("=== ARTIFACT TIMESTAMPS / SIZES ===")
for x in [csv, fp, zip_path]:
    print(x.name, "exists=",x.exists(),"mtime=",fmt_mtime(x),"size=",x.stat().st_size if x.exists() else None)

print("\n=== DISK CSV SCHEMA ===")
if csv.exists():
    d=pd.read_csv(csv,nrows=1)
    print("column_count=",len(d.columns))
    print("has_source_max_timestamp_utc=","source_max_timestamp_utc" in d.columns)
    print("columns=",list(d.columns))

print("\n=== RUN FINGERPRINT FILE ===")
if fp.exists():
    print(fp.read_text(encoding="utf-8"))

print("\n=== ZIP CSV SCHEMA ===")
if zip_path.exists():
    with zipfile.ZipFile(zip_path,"r") as z:
        names=z.namelist()
        print("zip_members=",names)
        target=next((n for n in names if n.endswith("decision_vwap_event_path_v2.csv")),None)
        if target:
            with z.open(target) as f:
                zd=pd.read_csv(f,nrows=1)
            print("zip_column_count=",len(zd.columns))
            print("zip_has_source_max_timestamp_utc=","source_max_timestamp_utc" in zd.columns)
            print("zip_columns=",list(zd.columns))

print("\n=== LIVE MSFT BUILD USING CURRENT CORE ===")
part=load_certified_partition(symbol="MSFT",year=2025,repo_root=root,verify_hash=True)
live=build_symbol(part.dataframe.copy(),symbol="MSFT")
print("live_rows=",len(live))
print("live_column_count=",len(live.columns))
print("live_has_source_max_timestamp_utc=","source_max_timestamp_utc" in live.columns)
print("live_has_directional_vwap_distance_pct=","directional_vwap_distance_pct" in live.columns)
print("live_has_event_reclaim_count=","event_reclaim_count" in live.columns)
print("live_has_event_vwap_loss_after_structural_clearance=","event_vwap_loss_after_structural_clearance" in live.columns)
print("live_columns=",list(live.columns))

print("\n=== LIVE REQUIRED FIELD NULL COUNTS ===")
for c in [
    "source_max_timestamp_utc",
    "directional_vwap_distance_pct",
    "event_vwap_touch_count_from_dp1",
    "event_reclaim_count",
    "event_loss_count",
    "event_directional_rejection_count",
]:
    print(c, "missing=", int(live[c].isna().sum()) if c in live.columns else "COLUMN_ABSENT")

print("\n=== WRITE/READ ROUNDTRIP TEST (TEMP FILE ONLY) ===")
tmp=root/"_tmp_msft_v2_roundtrip.csv"
live.to_csv(tmp,index=False)
rr=pd.read_csv(tmp,nrows=1)
print("roundtrip_column_count=",len(rr.columns))
print("roundtrip_has_source_max_timestamp_utc=","source_max_timestamp_utc" in rr.columns)
tmp.unlink(missing_ok=True)

print("\nDIAGNOSTIC_COMPLETE")
