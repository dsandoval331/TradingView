import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const OWNER = "dsandoval331";
const REPO = "TradingView";
const WORKFLOW = "trading-research-queue-watcher.yml";
const OUTBOX = "research_queue_wakeup_events";
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

async function updateOutbox(eventId: string, values: Record<string, unknown>) {
  const url = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceKey) throw new Error("missing_supabase_runtime_secret");
  const response = await fetch(`${url}/rest/v1/${OUTBOX}?event_id=eq.${encodeURIComponent(eventId)}`, {
    method: "PATCH",
    headers: {
      "apikey": serviceKey,
      "authorization": `Bearer ${serviceKey}`,
      "content-type": "application/json",
      "prefer": "return=minimal"
    },
    body: JSON.stringify(values)
  });
  if (!response.ok) throw new Error(`outbox_update_failed_${response.status}`);
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return new Response("method not allowed", { status: 405 });

  const token = Deno.env.get("TR_GITHUB_DISPATCH_TOKEN");
  if (!token) return new Response(JSON.stringify({ ok: false, error: "missing_dispatch_secret" }), { status: 500, headers: { "content-type": "application/json" } });

  let payload: Record<string, any>;
  try {
    payload = await req.json();
  } catch {
    return new Response(JSON.stringify({ ok: false, error: "invalid_webhook_payload" }), { status: 400, headers: { "content-type": "application/json" } });
  }
  const eventId = payload?.record?.event_id;
  if (typeof eventId !== "string" || !UUID_RE.test(eventId)) {
    return new Response(JSON.stringify({ ok: false, error: "missing_event_id" }), { status: 400, headers: { "content-type": "application/json" } });
  }

  const now = new Date().toISOString();
  try {
    await updateOutbox(eventId, {
      dispatch_requested_at: now,
      dispatch_status: "dispatching",
      attempt_count: Number(payload?.record?.attempt_count ?? 0) + 1,
      last_error: null
    });
  } catch (error) {
    console.error("unable to mark wakeup dispatch requested", error);
    return new Response(JSON.stringify({ ok: false, error: "outbox_request_tracking_failed" }), { status: 500, headers: { "content-type": "application/json" } });
  }

  const gh = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      "authorization": `Bearer ${token}`,
      "accept": "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "trading-research-control-plane"
    },
    body: JSON.stringify({ ref: "main" })
  });
  const requestId = gh.headers.get("x-github-request-id");

  if (!gh.ok) {
    const detail = (await gh.text()).slice(0, 500);
    console.error("github workflow dispatch failed", gh.status, detail);
    try {
      await updateOutbox(eventId, {
        dispatch_status: "failed",
        dispatch_request_id: requestId,
        last_error: `github_dispatch_${gh.status}`
      });
    } catch (error) {
      console.error("unable to record github dispatch failure", error);
    }
    return new Response(JSON.stringify({ ok: false, github_status: gh.status }), { status: 502, headers: { "content-type": "application/json" } });
  }

  try {
    await updateOutbox(eventId, {
      dispatch_acknowledged_at: new Date().toISOString(),
      dispatch_request_id: requestId,
      dispatch_status: "acknowledged",
      last_error: null
    });
  } catch (error) {
    console.error("github dispatch succeeded but acknowledgement persistence failed", error);
    return new Response(JSON.stringify({ ok: false, error: "acknowledgement_persistence_failed", github_status: gh.status }), { status: 500, headers: { "content-type": "application/json" } });
  }

  return new Response(JSON.stringify({ ok: true, github_status: gh.status }), { status: 202, headers: { "content-type": "application/json" } });
});
