from collections import Counter
from tr_platform.parity.pine_accessible_candidates import ACCESS_START,ACCESS_END,build_candidate_manifest,write_candidate_manifest
def main():
    cases=build_candidate_manifest()
    csv,js,digest=write_candidate_manifest(cases)
    print("=== PMPD 8H-7B-2B PINE-ACCESSIBLE CANDIDATE POOL ===")
    print(f"Access window: {ACCESS_START} -> {ACCESS_END}")
    print(f"Candidates: {len(cases)}")
    counts=Counter(c.set_code for c in cases)
    for s in sorted(counts): print(f"{s}: {counts[s]}")
    print(f"Sparse-source candidates: {sum(c.source_sparse_symbol for c in cases)}")
    print()
    for c in cases:
        sparse=" SPARSE" if c.source_sparse_symbol else ""
        print(f"{c.candidate_id} | {c.set_code} #{c.position_in_set} | {c.symbol} | {c.trade_date}{sparse}")
    print()
    print(f"CSV: {csv}")
    print(f"JSON: {js}")
    print(f"Manifest SHA-256: {digest}")
    print("Python PMPD signal output used: NO")
if __name__=="__main__": main()
