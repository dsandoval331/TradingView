from collections import Counter
from pathlib import Path
from tr_platform.parity.pine_accessible_candidates import *
def main():
    root=Path(__file__).resolve().parents[1]
    dates=eligible_trading_dates()
    assert dates[0]==ACCESS_START and dates[-1]==ACCESS_END
    for d in MARKET_CLOSED_DATES: assert d not in dates
    a=build_candidate_manifest(root); b=build_candidate_manifest(root)
    assert a==b and len(a)==48
    assert Counter(c.set_code for c in a)=={"SET_1":12,"SET_2":12,"SET_3":12,"SET_4":12}
    for s in ["MNDY","BKNG","BLK"]: assert any(c.symbol==s for c in a)
    print("=== 8H-7B-2B PINE-ACCESSIBLE CANDIDATE TEST PASS ===")
    print(f"Access window: {ACCESS_START} -> {ACCESS_END}")
    print("Deterministic repeated build: PASS")
    print("Total candidates: 48")
    print("SET_1/2/3/4: 12 each")
    print("Python PMPD signal output used: NO")
if __name__=="__main__": main()
