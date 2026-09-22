from cloud_compute.queue_watcher import eligible_jobs

class Dummy:
    pass

def test_filters_only_zero_cost_github_jobs(monkeypatch):
    rows = [
        {"job_id":"a"*36,"git_sha":"1"*40,"preferred_executor":"github_actions","cloud_run_spend_approved":False},
        {"job_id":"b"*36,"git_sha":"2"*40,"preferred_executor":"cloud_run","cloud_run_spend_approved":True},
        {"job_id":"c"*36,"git_sha":"3"*40,"preferred_executor":"github_actions","cloud_run_spend_approved":True},
    ]
    monkeypatch.setattr("cloud_compute.queue_watcher.fetch_queued_jobs", lambda config, limit: rows)
    got = eligible_jobs(Dummy(), limit=10)
    assert got == [{"job_id":"a"*36,"git_sha":"1"*40,"target_ref":"1"*40}]
