from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

CACHE_VERSION = "MARKET_CACHE_V1"
SOURCE_NAME = "massive"
CANONICAL_TIMEFRAME = "1m"

NEW_YORK_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")


@dataclass(frozen=True)
class MarketCacheConfig:
    repo_root: Path
    cache_root: Path
    timeframe_root: Path
    manifests_root: Path

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "MarketCacheConfig":
        repo_root = repo_root.resolve()
        cache_root = repo_root / "market_cache" / CACHE_VERSION
        return cls(
            repo_root=repo_root,
            cache_root=cache_root,
            timeframe_root=cache_root / CANONICAL_TIMEFRAME,
            manifests_root=cache_root / "manifests",
        )

    def ensure_directories(self) -> None:
        self.timeframe_root.mkdir(parents=True, exist_ok=True)
        self.manifests_root.mkdir(parents=True, exist_ok=True)

    def symbol_year_path(self, symbol: str, year: int) -> Path:
        symbol = symbol.upper().strip()
        return self.timeframe_root / symbol / f"{year}.parquet"


def classify_session(hour: int, minute: int) -> str:
    mins = hour * 60 + minute

    if 4 * 60 <= mins <= 9 * 60 + 29:
        return "PRE"
    if 9 * 60 + 30 <= mins <= 15 * 60 + 59:
        return "RTH"
    if 16 * 60 <= mins <= 19 * 60 + 59:
        return "AH"
    return "OVERNIGHT"
