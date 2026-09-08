from pathlib import Path
import subprocess, sys

V1_UPDATER=Path("update_altc2_prospective_v1.py")
V2_SCORER=Path("score_a53_v2_prospective_events_v1.py")
V2_REPORTER=Path("report_a53_v2_prospective_checkpoint_v1.py")

def run(cmd):
    print("\n>>>"," ".join(map(str,cmd)),flush=True)
    r=subprocess.run(cmd)
    if r.returncode:
        raise SystemExit(r.returncode)

def main():
    for p in [V1_UPDATER,V2_SCORER,V2_REPORTER]:
        if not p.exists():
            raise FileNotFoundError(f"Required script not found: {p.resolve()}")

    # V1 remains authoritative for market-data acquisition and Candidate-V1 scoring.
    # Its existing updater/report behavior is preserved.
    run([sys.executable,str(V1_UPDATER),"--report-only-if-current"])

    # V2 is a read-only nested refinement of the resulting V1 PREFERRED cohort.
    run([sys.executable,str(V2_SCORER)])
    run([sys.executable,str(V2_REPORTER)])

    print("\n"+"="*120)
    print("V1 + V2 PROSPECTIVE UPDATE COMPLETE")
    print("V1 ledger remains authoritative and is not modified by V2.")
    print("V2 ledger/report refreshed from frozen V1 PREFERRED events.")
    print("="*120)

if __name__=="__main__": main()
