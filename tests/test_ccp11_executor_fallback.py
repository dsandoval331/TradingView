from cloud_compute.executor_policy import Executor, ExecutorAvailability, choose_executor


def test_primary_executor_is_github_actions_when_available() -> None:
    assert choose_executor(ExecutorAvailability()) == Executor.GITHUB_ACTIONS


def test_unapproved_cloud_run_is_skipped_for_local_fallback() -> None:
    availability = ExecutorAvailability(
        github_actions_available=False,
        cloud_run_available=True,
        cloud_run_spend_approved=False,
        local_windows_available=True,
    )
    assert choose_executor(availability) == Executor.LOCAL_WINDOWS


def test_cloud_run_can_only_precede_local_after_explicit_approval() -> None:
    availability = ExecutorAvailability(
        github_actions_available=False,
        cloud_run_available=True,
        cloud_run_spend_approved=True,
        local_windows_available=True,
    )
    assert choose_executor(availability) == Executor.CLOUD_RUN


def test_no_eligible_executor_returns_none() -> None:
    availability = ExecutorAvailability(
        github_actions_available=False,
        cloud_run_available=False,
        cloud_run_spend_approved=False,
        local_windows_available=False,
    )
    assert choose_executor(availability) is None
