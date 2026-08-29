from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class MassiveClientConfig:
    api_key: str
    requests_per_minute: float = 4.0
    timeout_seconds: int = 30
    max_retries: int = 4
    base_url: str = "https://api.massive.com"


class MassiveClient:
    def __init__(self, config: MassiveClientConfig) -> None:
        if not config.api_key.strip():
            raise ValueError("Massive API key cannot be blank.")

        self.config = config
        self.session = requests.Session()
        self._min_interval = 60.0 / config.requests_per_minute
        self._last_request_at: Optional[float] = None

    def _rate_limit(self) -> None:
        if self._last_request_at is None:
            return

        elapsed = time.monotonic() - self._last_request_at
        remaining = self._min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            self._rate_limit()

            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.config.timeout_seconds,
                )
                self._last_request_at = time.monotonic()

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_seconds = float(retry_after) if retry_after else min(15 * (2 ** attempt), 120)
                    time.sleep(wait_seconds)
                    continue

                if 500 <= response.status_code <= 599:
                    time.sleep(min(5 * (2 ** attempt), 60))
                    continue

                response.raise_for_status()
                return response.json()

            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                time.sleep(min(5 * (2 ** attempt), 60))

            except requests.HTTPError:
                raise

        raise RuntimeError(f"Massive request failed after retries: {last_error}")

    def get_minute_aggs(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjusted: bool = False,
        limit: int = 50_000,
    ) -> List[Dict[str, Any]]:
        symbol = symbol.upper().strip()

        url = (
            f"{self.config.base_url}/v2/aggs/ticker/{symbol}"
            f"/range/1/minute/{start_date}/{end_date}"
        )

        params: Optional[Dict[str, Any]] = {
            "adjusted": str(adjusted).lower(),
            "sort": "asc",
            "limit": limit,
            "apiKey": self.config.api_key,
        }

        all_results: List[Dict[str, Any]] = []

        while url:
            payload = self._get_json(url, params=params)

            results = payload.get("results") or []
            all_results.extend(results)

            next_url = payload.get("next_url")
            if not next_url:
                break

            url = next_url
            params = {"apiKey": self.config.api_key}

        return all_results
