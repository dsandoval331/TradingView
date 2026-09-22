from pathlib import Path

import pandas as pd
import pytest

from research_runner.jobs.pmod_p2_b2_certification import _audit, _read


def test_read_accepts_canonical_market_cache_timestamp_utc(tmp_path: Path) -> None:
    path = tmp_path / "canonical.parquet"
    expected = pd.to_datetime(["2025-01-02T14:00:00Z", "2025-01-02T14:29:00Z"], utc=True)
    pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "timestamp_utc": expected,
        "open": [100.0, 101.0], "high": [101.0, 102.0],
        "low": [99.0, 100.0], "close": [100.5, 101.5], "volume": [10, 20],
    }).to_parquet(path, index=False)

    got = _read(path)
    assert "timestamp" in got.columns
    assert got["timestamp"].tolist() == expected.tolist()


def test_read_rejects_missing_timestamp_without_synthesis(tmp_path: Path) -> None:
    path = tmp_path / "bad.parquet"
    pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]}).to_parquet(path, index=False)
    with pytest.raises(RuntimeError, match="timestamp column"):
        _read(path)


def test_read_rejects_unparseable_timestamp_without_synthesis(tmp_path: Path) -> None:
    path = tmp_path / "bad_timestamp.parquet"
    pd.DataFrame({"timestamp_utc": ["not-a-time"], "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]}).to_parquet(path, index=False)
    with pytest.raises(RuntimeError, match="unparseable timestamp"):
        _read(path)


def test_audit_canonical_timestamp_with_duplicate_rows(tmp_path: Path) -> None:
    path = tmp_path / "canonical_duplicates.parquet"
    ts = pd.to_datetime([
        "2025-01-02T14:00:00Z",
        "2025-01-02T14:00:00Z",
        "2025-01-02T14:29:00Z",
    ], utc=True)
    pd.DataFrame({
        "symbol": ["AAPL"] * 3,
        "timestamp_utc": ts,
        "open": [100.0, 100.0, 101.0],
        "high": [101.0, 101.0, 102.0],
        "low": [99.0, 99.0, 100.0],
        "close": [100.5, 100.5, 101.5],
        "volume": [10, 10, 20],
    }).to_parquet(path, index=False)

    got = _audit(path, "AAPL", 2025)
    assert got["duplicate_rows"] == 2
    assert got["conflicting_duplicate_timestamps"] == 0
    assert got["status"] == "PASS"
