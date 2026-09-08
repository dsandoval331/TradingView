import inspect
import tr_platform.pmpd_v5.vwap_event_path_v2 as core

print("=== BUILD-LIKE FUNCTIONS ===")
for name,obj in inspect.getmembers(core):
    if inspect.isfunction(obj) and any(k in name.lower() for k in ["build","assemble","enrich","event_path","run"]):
        print(name)

print("\n=== SOURCE LINES 140-280 ===")
src=inspect.getsource(core).splitlines()
for i in range(139, min(280,len(src))):
    print(f"{i+1:04d}: {src[i]}")

print("\n=== FUNCTIONS CONTAINING LEGACY OUTPUT COLUMN NAMES ===")
needle="event_last_vwap_cross_direction"
for name,obj in inspect.getmembers(core):
    if inspect.isfunction(obj):
        try:
            s=inspect.getsource(obj)
        except Exception:
            continue
        if needle in s or "source_max_timestamp_utc" in s:
            print(f"\n--- {name} ---")
            print(s)

print("\nINSPECTION_COMPLETE")
