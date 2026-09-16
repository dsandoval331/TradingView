from cloud_compute.executor_policy import Executor, ExecutorAvailability, choose_executor


def test_github_actions_is_primary_when_available():
    selected = choose_executor(
        ExecutorAvailability(
            github_actions_available=True,
            cloud_run_available=True,
            cloud_run_spend_approved=True,
            local_windows_available=True,
        )
    )
    assert selected == Executor.GITHUB_ACTIONS


def test_cloud_run_is_second_when_github_unavailable_and_approved():
    selected = choose_executor(
        ExecutorAvailability(
            github_actions_available=False,
            cloud_run_available=True,
            cloud_run_spend_approved=True,
            local_windows_available=True,
        )
    )
    assert selected == Executor.CLOUD_RUN


def test_local_is_third_when_remote_execution_unavailable():
    selected = choose_executor(
        ExecutorAvailability(
            github_actions_available=False,
            cloud_run_available=False,
            cloud_run_spend_approved=False,
            local_windows_available=True,
        )
    )
    assert selected == Executor.LOCAL_WINDOWS


def test_cloud_run_cannot_bypass_spend_guardrail():
    selected = choose_executor(
        ExecutorAvailability(
            github_actions_available=False,
            cloud_run_available=True,
            cloud_run_spend_approved=False,
            local_windows_available=True,
        )
    )
    assert selected == Executor.LOCAL_WINDOWS


def test_none_when_no_executor_is_available():
    selected = choose_executor(
        ExecutorAvailability(
            github_actions_available=False,
            cloud_run_available=False,
            cloud_run_spend_approved=False,
            local_windows_available=False,
        )
    )
    assert selected is None
