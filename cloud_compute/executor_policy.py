from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Executor(str, Enum):
    GITHUB_ACTIONS = "github_actions"
    CLOUD_RUN = "cloud_run"
    LOCAL_WINDOWS = "local_windows"


@dataclass(frozen=True)
class ExecutorAvailability:
    github_actions_available: bool = True
    cloud_run_available: bool = False
    local_windows_available: bool = True
    cloud_run_spend_approved: bool = False


DEFAULT_PRIORITY: tuple[Executor, ...] = (
    Executor.GITHUB_ACTIONS,
    Executor.CLOUD_RUN,
    Executor.LOCAL_WINDOWS,
)


def choose_executor(
    availability: ExecutorAvailability,
    priority: Iterable[Executor] = DEFAULT_PRIORITY,
) -> Executor | None:
    """Choose the first eligible executor without bypassing cost guardrails.

    Cloud Run is eligible only when it is both technically available and explicitly
    approved under the project's spend policy. Local execution remains the final
    fallback so jobs can continue when remote free/included capacity is unavailable.
    """
    eligibility = {
        Executor.GITHUB_ACTIONS: availability.github_actions_available,
        Executor.CLOUD_RUN: (
            availability.cloud_run_available and availability.cloud_run_spend_approved
        ),
        Executor.LOCAL_WINDOWS: availability.local_windows_available,
    }
    for executor in priority:
        if eligibility.get(executor, False):
            return executor
    return None
