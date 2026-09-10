from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from cloud_compute.storage_poc import _headers


@dataclass(frozen=True)
class ControlPlaneConfig:
    supabase_url: str
    secret_key: str

    @property
    def rest_url(self) -> str:
        return self.supabase_url.rstrip('/') + '/rest/v1'


def _request_headers(secret_key: str, *, prefer: str | None = None) -> dict[str, str]:
    headers = {**_headers(secret_key), 'Content-Type': 'application/json'}
    if prefer:
        headers['Prefer'] = prefer
    return headers


def _insert_one(config: ControlPlaneConfig, table: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f'{config.rest_url}/{table}',
        headers=_request_headers(config.secret_key, prefer='return=representation'),
        json=payload,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f'{table} insert failed: HTTP {response.status_code} {response.text[:500]}')
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError(f'{table} insert expected exactly one returned row')
    return rows[0]


def _update_one(config: ControlPlaneConfig, table: str, key: str, value: str, patch: dict[str, Any]) -> dict[str, Any]:
    response = requests.patch(
        f'{config.rest_url}/{table}',
        headers=_request_headers(config.secret_key, prefer='return=representation'),
        params={key: f'eq.{value}'},
        json=patch,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f'{table} update failed: HTTP {response.status_code} {response.text[:500]}')
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError(f'{table} update expected exactly one returned row')
    return rows[0]


def create_job(config: ControlPlaneConfig, payload: dict[str, Any]) -> dict[str, Any]:
    return _insert_one(config, 'research_jobs', payload)


def fetch_queued_jobs(config: ControlPlaneConfig, *, limit: int = 20) -> list[dict[str, Any]]:
    params = {
        'status': 'in.(queued,local_pending)',
        'order': 'priority.asc,queued_at.asc',
        'limit': str(limit),
    }
    response = requests.get(
        f'{config.rest_url}/research_jobs',
        headers=_request_headers(config.secret_key),
        params=params,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f'fetch_queued_jobs failed: HTTP {response.status_code} {response.text[:500]}')
    rows = response.json()
    if not isinstance(rows, list):
        raise RuntimeError('fetch_queued_jobs expected a list response')
    return rows


def update_job(config: ControlPlaneConfig, job_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return _update_one(config, 'research_jobs', 'job_id', job_id, patch)


def create_attempt(config: ControlPlaneConfig, payload: dict[str, Any]) -> dict[str, Any]:
    return _insert_one(config, 'research_job_attempts', payload)


def update_attempt(config: ControlPlaneConfig, attempt_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return _update_one(config, 'research_job_attempts', 'attempt_id', attempt_id, patch)


def create_log(config: ControlPlaneConfig, payload: dict[str, Any]) -> dict[str, Any]:
    return _insert_one(config, 'research_job_logs', payload)


def create_artifact(config: ControlPlaneConfig, payload: dict[str, Any]) -> dict[str, Any]:
    return _insert_one(config, 'research_job_artifacts', payload)
