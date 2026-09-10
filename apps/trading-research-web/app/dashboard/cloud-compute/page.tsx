import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "../../../lib/supabase/server";
import { createAdminClient } from "../../../lib/supabase/admin";
import { submitCloudJob } from "./actions";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ submitted?: string; error?: string; job?: string }> };
type Job = {
  job_id: string; runner_job_id: string; phase_code: string | null; status: string; git_sha: string;
  dataset_version: string | null; assigned_executor: string | null; queued_at: string; started_at: string | null;
  completed_at: string | null; last_error: string | null; parameters_json: Record<string, unknown> | null;
};

function fmt(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" }).format(new Date(value));
}
function pretty(value: string) { return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()); }

export default async function CloudComputePage({ searchParams }: Props) {
  const query = await searchParams;
  const supabase = await createClient();
  const { data: claimsData, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claimsData?.claims) redirect("/login");
  const { data: allowed, error: accessError } = await supabase.rpc("is_trading_research_web_user");
  if (accessError || allowed !== true) redirect("/unauthorized");

  const admin = createAdminClient();
  const [{ data: jobsData, error: jobsError }, { data: stateData, error: stateError }] = await Promise.all([
    admin.from("research_jobs").select("job_id,runner_job_id,phase_code,status,git_sha,dataset_version,assigned_executor,queued_at,started_at,completed_at,last_error,parameters_json").eq("project_code", "CLOUD_COMPUTE").order("queued_at", { ascending: false }).limit(20),
    admin.from("project_state").select("active_phase_code,active_phase_name,next_phase_code,next_phase_name,last_decision,updated_at").eq("strategy_id", "98f761bf-c6f1-4399-b10e-e299cb332141").maybeSingle(),
  ]);
  const jobs = (jobsData ?? []) as Job[];
  const queryError = jobsError || stateError;
  const queued = jobs.filter((j) => ["queued", "local_pending"].includes(j.status)).length;
  const running = jobs.filter((j) => j.status === "running").length;
  const failed = jobs.filter((j) => j.status === "failed").length;
  const succeeded = jobs.filter((j) => j.status === "succeeded").length;

  return <main>
    <section className="projectHero">
      <div>
        <Link className="backLink" href="/dashboard">← Research control center</Link>
        <p className="eyebrow">CLOUD COMPUTE · CCP-9</p>
        <h1>Cloud job control</h1>
        <p className="lede">Authenticated server-side submission and live execution status for the governed TradingResearch cloud control plane.</p>
      </div>
      <span className="securityBadge">Authenticated · Allowlisted · Server-side secrets only</span>
    </section>

    {query.submitted && <section className="trackingHealth trackingHealth-ok"><div><span className="fieldLabel">Job submitted</span><strong>{query.submitted}</strong></div><p>GitHub Actions dispatch was accepted. Refresh this page to follow execution state.</p></section>}
    {query.error && <section className="alertPanel"><strong>Submission failed: {pretty(query.error)}</strong><span>{query.job ? `Job ${query.job}` : "No job was dispatched."}</span></section>}
    {queryError && <section className="alertPanel"><strong>Cloud control-plane query failed.</strong><span>{queryError.message}</span></section>}

    <section className="metricGrid">
      <article className="metricCard"><span>Queued</span><strong>{queued}</strong><small>Recent 20 jobs</small></article>
      <article className="metricCard"><span>Running</span><strong>{running}</strong><small>Currently claimed</small></article>
      <article className="metricCard"><span>Succeeded</span><strong>{succeeded}</strong><small>Recent 20 jobs</small></article>
      <article className="metricCard"><span>Failed</span><strong>{failed}</strong><small>Recent 20 jobs</small></article>
    </section>

    <section className="statusPlanGrid">
      <article className="detailPanel">
        <span className="fieldLabel">Current platform phase</span>
        <h3>{stateData?.active_phase_code ?? "—"} · {stateData?.active_phase_name ?? "Not tracked"}</h3>
        <p>Next: {stateData?.next_phase_code ?? "—"} · {stateData?.next_phase_name ?? "Not tracked"}</p>
        <small>Updated {fmt(stateData?.updated_at ?? null)}</small>
      </article>
      <article className="detailPanel">
        <span className="fieldLabel">Zero-spend web certification</span>
        <h3>Submit a governed fixture</h3>
        <p>CCP-9 initially exposes only deterministic platform fixtures. Research-lane jobs are enabled in CCP-10 after migration certification.</p>
        <form action={submitCloudJob} className="authForm">
          <label htmlFor="runner_job_id">Runner job</label>
          <select id="runner_job_id" name="runner_job_id" defaultValue="CCP3-PARITY-FIXTURE">
            <option value="CCP3-PARITY-FIXTURE">CCP3-PARITY-FIXTURE</option>
            <option value="CCP4-REMOTE-FIXTURE">CCP4-REMOTE-FIXTURE</option>
          </select>
          <button type="submit">Submit to GitHub Actions</button>
        </form>
        <small>Cloud Run remains blocked unless separately and explicitly approved.</small>
      </article>
    </section>

    <section className="projectSection">
      <div className="sectionHeader"><div><p className="eyebrow">CONTROL PLANE</p><h2>Recent cloud jobs</h2></div><span>{jobs.length} shown</span></div>
      <div className="stackList">
        {jobs.length ? jobs.map((job) => <article className="detailPanel" key={job.job_id}>
          <div className="listTop"><strong>{job.runner_job_id}</strong><span className={`statusPill status-${job.status}`}>{pretty(job.status)}</span></div>
          <dl className="detailGrid">
            <div><dt>Job ID</dt><dd>{job.job_id}</dd></div><div><dt>Dataset</dt><dd>{job.dataset_version ?? "—"}</dd></div>
            <div><dt>Executor</dt><dd>{job.assigned_executor ?? "Waiting"}</dd></div><div><dt>Git SHA</dt><dd>{job.git_sha.slice(0, 12)}</dd></div>
            <div><dt>Queued</dt><dd>{fmt(job.queued_at)}</dd></div><div><dt>Completed</dt><dd>{fmt(job.completed_at)}</dd></div>
          </dl>
          {job.last_error && <p className="authError">{job.last_error}</p>}
        </article>) : <p className="emptyState">No cloud jobs recorded.</p>}
      </div>
    </section>
  </main>;
}
