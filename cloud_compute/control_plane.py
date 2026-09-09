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


def create_job(config: ControlPlaneConfig, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f'{config.rest_url}/research_jobs',
        headers=_request_headers(config.secret_key, prefer='return=representation'),
        json=payload,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f'create_job failed: HTTP {response.status_code} {response.text[:500]}')
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError('create_job expected exactly one returned row')
    return rows[0]


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
    response = requests.patch(
        f'{config.rest_url}/research_jobs',
        headers=_request_headers(config.secret_key, prefer='return=representation'),
        params={'job_id': f'eq.{job_id}'},
        json=patch,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f'update_job failed: HTTP {response.status_code} {response.text[:500]}')
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError('update_job expected exactly one returned row')
    return rows[0]


def create_attempt(config: ControlPlaneConfig, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f'{config.rest_url}/research_job_attempts',
        headers=_request_headers(config.secret_key, prefer='return=representation'),
        json=payload,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f'create_attempt failed: HTTP {response.status_code} {response.text[:500]}')
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError('create_attempt expected exactly one returned row')
    return rows[0]
