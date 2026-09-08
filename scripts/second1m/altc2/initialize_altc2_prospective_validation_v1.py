from __future__ import annotations
from pathlib import Path
import json
import shutil
from datetime import datetime

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")
VALIDATION_ROOT = ROOT / "data" / "second1m_alt_entry_prospective_v1"
PROTOCOL_DIR = VALIDATION_ROOT / "protocol"
EVENT_DIR = VALIDATION_ROOT / "events"
REPORT_DIR = VALIDATION_ROOT / "reports"
MANIFEST_PATH = PROTOCOL_DIR / "ALT_C2_PROSPECTIVE_VALIDATION_V1.json"

SOURCE_PROTOCOL = Path(__file__).with_name("ALT_C2_PROSPECTIVE_VALIDATION_V1.json")

def main():
    for p in [PROTOCOL_DIR, EVENT_DIR, REPORT_DIR]:
        p.mkdir(parents=True, exist_ok=True)

    if not SOURCE_PROTOCOL.exists():
        raise FileNotFoundError(
            f"Place ALT_C2_PROSPECTIVE_VALIDATION_V1.json beside this script. Missing: {SOURCE_PROTOCOL}"
        )

    protocol = json.loads(SOURCE_PROTOCOL.read_text(encoding="utf-8"))

    # Hard freeze: never silently overwrite an existing manifest.
    if MANIFEST_PATH.exists():
        existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if existing != protocol:
            raise RuntimeError(
                "A frozen prospective manifest already exists and differs from the supplied protocol. "
                "Do not overwrite V1. Create a V2 protocol instead."
            )
        print("Manifest already exists and matches exactly.")
    else:
        shutil.copy2(SOURCE_PROTOCOL, MANIFEST_PATH)
        print(f"Frozen manifest created: {MANIFEST_PATH}")

    readme = VALIDATION_ROOT / "README_VALIDATION_FREEZE.txt"
    if not readme.exists():
        readme.write_text(
            "\n".join([
                "ALT_C2_PROSPECTIVE_VALIDATION_V1",
                "",
                "Historical research end date: 2026-08-27",
                "Prospective start date: 2026-08-28",
                "",
                "DO NOT MODIFY MODEL V1 DURING THIS VALIDATION CYCLE.",
                "Any logic change requires a new model/version and a new validation cycle.",
                "",
                f"Initialized: {datetime.now().isoformat(timespec='seconds')}",
            ]),
            encoding="utf-8",
        )

    print(f"Validation root: {VALIDATION_ROOT}")
    print(f"Events folder:   {EVENT_DIR}")
    print(f"Reports folder:  {REPORT_DIR}")
    print("RESULT: PROTOCOL FROZEN")

if __name__ == "__main__":
    main()
