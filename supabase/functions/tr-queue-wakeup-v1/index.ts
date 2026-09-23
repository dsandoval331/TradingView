import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const OWNER = "dsandoval331";
const REPO = "TradingView";
const WORKFLOW = "trading-research-queue-watcher.yml";

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return new Response("method not allowed", { status: 405 });

  const token = Deno.env.get("TR_GITHUB_DISPATCH_TOKEN");
  if (!token) return new Response(JSON.stringify({ ok: false, error: "missing_dispatch_secret" }), { status: 500, headers: { "content-type": "application/json" } });

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

  if (!gh.ok) {
    const detail = await gh.text();
    console.error("github workflow dispatch failed", gh.status, detail);
    return new Response(JSON.stringify({ ok: false, github_status: gh.status }), { status: 502, headers: { "content-type": "application/json" } });
  }

  return new Response(JSON.stringify({ ok: true, github_status: gh.status }), { status: 202, headers: { "content-type": "application/json" } });
});
