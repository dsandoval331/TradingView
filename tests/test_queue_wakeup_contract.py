from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260923_add_research_queue_wakeup_outbox.sql"
EDGE = ROOT / "supabase/functions/tr-queue-wakeup-v1/index.ts"
WATCHER = ROOT / ".github/workflows/trading-research-queue-watcher.yml"


def test_outbox_is_idempotent_and_governed():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "unique (job_id, event_type)" in sql
    assert "on conflict (job_id, event_type) do nothing" in sql
    assert "new.status = 'queued'" in sql
    assert "new.preferred_executor = 'github_actions'" in sql
    assert "cloud_run_spend_approved" in sql
    assert "length(coalesce(new.git_sha, '')) = 40" in sql
    assert "enable row level security" in sql


def test_edge_function_is_wakeup_only_and_secret_backed():
    src = EDGE.read_text(encoding="utf-8")
    assert 'Deno.env.get("TR_GITHUB_DISPATCH_TOKEN")' in src
    assert 'Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")' in src
    assert "trading-research-queue-watcher.yml" in src
    assert 'JSON.stringify({ ref: "main" })' in src
    assert "git_sha" not in src
    assert "research_jobs" not in src


def test_edge_function_records_delivery_observability():
    src = EDGE.read_text(encoding="utf-8")
    assert 'const eventId = payload?.record?.event_id' in src
    assert 'dispatch_status: "requested"' in src
    assert 'dispatch_status: "acknowledged"' in src
    assert 'dispatch_status: "failed"' in src
    assert "dispatch_requested_at" in src
    assert "dispatch_acknowledged_at" in src
    assert "dispatch_request_id" in src
    assert "attempt_count" in src


def test_cron_reconciliation_remains_enabled():
    workflow = WATCHER.read_text(encoding="utf-8")
    assert "schedule:" in workflow
    assert "cron: '3,13,23,33,43,53 * * * *'" in workflow
    assert "workflow_dispatch:" in workflow
