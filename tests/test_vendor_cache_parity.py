from tr_platform.validation.vendor_cache_parity import DEFAULT_CASES
def main():
    assert ("BKNG", "2025-07-24") in DEFAULT_CASES
    assert ("SPY", "2025-07-24") in DEFAULT_CASES
    assert len(DEFAULT_CASES) == 4
    print("=== VENDOR CACHE PARITY STATIC TEST PASS ===")
    print(DEFAULT_CASES)
if __name__ == "__main__":
    main()
