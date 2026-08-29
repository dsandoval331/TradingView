from __future__ import annotations

import argparse

from tr_platform.universe.acquire_set import execute_set_year


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PMPD frozen-universe set/year acquisition."
    )
    parser.add_argument("--set", type=int, required=True, dest="set_number")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually acquire missing partitions. Without this flag, dry-run only.",
    )
    args = parser.parse_args()

    execute_set_year(
        set_number=args.set_number,
        year=args.year,
        confirm_execute=args.execute,
    )


if __name__ == "__main__":
    main()
