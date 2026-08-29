from tr_platform.validation.vendor_cache_parity import prompt_and_run

def main():
    results, csv_path = prompt_and_run()
    print("=== PMPD VENDOR -> CACHE PARITY ===")
    for r in results:
        print()
        print(f"{r.symbol} {r.trade_date}: {r.status}")
        print(f"  Vendor/cache RTH rows: {r.vendor_rth_rows}/{r.cache_rth_rows}")
        print(f"  Vendor-only timestamps: {r.vendor_only_timestamps}")
        print(f"  Cache-only timestamps:  {r.cache_only_timestamps}")
        print(f"  OHLCV mismatches:       {r.ohlcv_mismatches}")
        print(f"  Vendor/cache max gap:   {r.max_vendor_rth_gap_minutes}/{r.max_cache_rth_gap_minutes} min")
        print(f"  Notes: {r.notes}")
    passed = sum(r.status == "PASS" for r in results)
    failed = sum(r.status == "FAIL" for r in results)
    print()
    print("=== PARITY SUMMARY ===")
    print(f"Cases: {len(results)}")
    print(f"PASS:  {passed}")
    print(f"FAIL:  {failed}")
    print(f"CSV:   {csv_path}")
    if failed:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
