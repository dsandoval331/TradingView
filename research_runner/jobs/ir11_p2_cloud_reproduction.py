from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from research_runner.jobs import ir11_p2_unconditional_paths as historical_p2

YEAR = 2025
EXPECTED_OBSERVATIONS = 149_546
EXPECTED_PAIRWISE_ROWS = 3_738_650
EXPECTED_SYMBOLS = 104
EXPECTED_DATES = 250

P1_REL = Path("research_outputs/ir11/p1/ir11_p1_dense_clock_observations_2025_v1.parquet")
OUT_REL = Path("research_outputs/ir11/p2")

OUTPUT_NAMES = [
    "ir11_p2_forward_paths_2025_v1.parquet",
    "ir11_p2_forward_paths_2025_v1.csv",
    "ir11_p2_pairwise_outcomes_2025_v1.parquet",
    "ir11_p2_clock_path_summary_2025_v1.csv",
    "ir11_p2_pairwise_summary_by_clock_2025_v1.csv",
    "ir11_p2_pairwise_summary_by_clock_rawbin_2025_v1.csv",
    "ir11_p2_pairwise_summary_by_clock_relative_top5_2025_v1.csv",
]


def _assert_p1_gate(p1_path: Path) -> None:
    p1 = pd.read_parquet(p1_path, columns=["symbol", "trade_date"])
    observations = len(p1)
    symbols = p1["symbol"].nunique()
    dates = pd.to_datetime(p1["trade_date"]).dt.date.nunique()
    if (observations, symbols, dates) != (
        EXPECTED_OBSERVATIONS,
        EXPECTED_SYMBOLS,
        EXPECTED_DATES,
    ):
        raise RuntimeError(
            "IR-11 P1 parity gate failed: "
            f"observations={observations} symbols={symbols} dates={dates}; "
            f"expected={EXPECTED_OBSERVATIONS}/{EXPECTED_SYMBOLS}/{EXPECTED_DATES}"
        )


def _assert_p2_gate(out_root: Path) -> None:
    paths = pd.read_parquet(
        out_root / "ir11_p2_forward_paths_2025_v1.parquet",
        columns=["symbol", "trade_date"],
    )
    pairs = pd.read_parquet(
        out_root / "ir11_p2_pairwise_outcomes_2025_v1.parquet",
        columns=["symbol", "trade_date"],
    )
    observations = len(paths)
    pairwise_rows = len(pairs)
    symbols = paths["symbol"].nunique()
    dates = pd.to_datetime(paths["trade_date"]).dt.date.nunique()
    if (observations, pairwise_rows, symbols, dates) != (
        EXPECTED_OBSERVATIONS,
        EXPECTED_PAIRWISE_ROWS,
        EXPECTED_SYMBOLS,
        EXPECTED_DATES,
    ):
        raise RuntimeError(
            "IR-11 P2 parity gate failed: "
            f"observations={observations} pairwise_rows={pairwise_rows} "
            f"symbols={symbols} dates={dates}; expected="
            f"{EXPECTED_OBSERVATIONS}/{EXPECTED_PAIRWISE_ROWS}/"
            f"{EXPECTED_SYMBOLS}/{EXPECTED_DATES}"
        )


def run(work_root: Path) -> dict:
    work_root = Path(work_root).resolve()
    p1_path = work_root / P1_REL
    out_root = work_root / OUT_REL

    if not p1_path.is_file():
        raise FileNotFoundError(f"Missing governed P1 input: {p1_path}")

    _assert_p1_gate(p1_path)
    out_root.mkdir(parents=True, exist_ok=True)

    old_cache_root = historical_p2.CACHE_ROOT
    old_argv = sys.argv[:]
    try:
        historical_p2.CACHE_ROOT = work_root / "market_cache/MARKET_CACHE_V1/1m"
        sys.argv = [
            "ir11_p2_unconditional_paths",
            "--year",
            str(YEAR),
            "--p1-path",
            str(p1_path),
            "--out-root",
            str(out_root),
        ]
        historical_p2.main()
    finally:
        historical_p2.CACHE_ROOT = old_cache_root
        sys.argv = old_argv

    output_paths = [str(out_root / name) for name in OUTPUT_NAMES]
    missing = [p for p in output_paths if not Path(p).is_file()]
    if missing:
        raise RuntimeError(f"IR-11 P2 declared outputs missing: {missing}")

    _assert_p2_gate(out_root)

    return {
        "artifact": output_paths[0],
        "output_paths": output_paths,
        "parity": {
            "forward_path_rows": EXPECTED_OBSERVATIONS,
            "pairwise_rows": EXPECTED_PAIRWISE_ROWS,
            "symbols": EXPECTED_SYMBOLS,
            "dates": EXPECTED_DATES,
        },
        "historical_source_module": "research_runner.jobs.ir11_p2_unconditional_paths",
        "research_logic_modified": False,
    }
