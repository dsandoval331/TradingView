import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "../../../lib/supabase/server";
import { createAdminClient } from "../../../lib/supabase/admin";
import { submitCloudJob } from "./actions";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ submitted?: string; error?: string; job?: string }> };
type Job = {
  job_id: string; runner_job_id: string; phase_code: string | null; status: string; git_sha: string;
  dataset_version: string | null; preferred_executor?: string | null; assigned_executor: string | null;
  cloud_run_spend_approved?: boolean; queued_at: string; started_at: string | null;
  completed_at: string | null; last_error: string | null; parameters_json: Record<string, unknown> | null;
};

function fmt(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" }).format(new Date(value));
}
function pretty(value: string) { return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()); }
function formatDuration(seconds: number) {
  if (seconds < 60) return `${seconds.toFixed(0)} sec`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} min`;
  return `${(seconds / 3600).toFixed(2)} hr`;
}

export default async function CloudComputePage({ searchParams }: Props) {
  const query = await searchParams;
  const supabase = await createClient();
  const { data: claimsData, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claimsData?.claims) redirect("/login");
  const { data: allowed, error: accessError } = await supabase.rpc("is_trading_research_web_user");
  if (accessError || allowed !== true) redirect("/unauthorized");

  const admin = createAdminClient();
  const now = new Date();
  const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1)).toISOString();
  const [{ data: jobsData, error: jobsError }, { data: stateData, error: stateError }, { data: monthJobsData, error: monthJobsError }] = await Promise.all([
    admin.from("research_jobs").select("job_id,runner_job_id,phase_code,status,git_sha,dataset_version,preferred_executor,assigned_executor,cloud_run_spend_approved,queued_at,started_at,completed_at,last_error,parameters_json").eq("project_code", "CLOUD_COMPUTE").order("queued_at", { ascending: false }).limit(20),
    admin.from("project_state").select("active_phase_code,active_phase_name,next_phase_code,next_phase_name,last_decision,updated_at").eq("strategy_id", "98f761bf-c6f1-4399-b10e-e299cb332141").maybeSingle(),
    admin.from("research_jobs").select("job_id,status,preferred_executor,assigned_executor,cloud_run_spend_approved,started_at,completed_at").eq("project_code", "CLOUD_COMPUTE").gte("queued_at", monthStart).limit(1000),
  ]);
  const jobs = (jobsData ?? []) as Job[];
  const monthJobs = (monthJobsData ?? []) as Pick<Job, "job_id" | "status" | "preferred_executor" | "assigned_executor" | "cloud_run_spend_approved" | "started_at" | "completed_at">[];
  const queryError = jobsError || stateError || monthJobsError;
  const queued = jobs.filter((j) => ["queued", "local_pending"].includes(j.status)).length;
  const running = jobs.filter((j) => j.status === "running").length;
  const failed = jobs.filter((j) => j.status === "failed").length;
  const succeeded = jobs.filter((j) => j.status === "succeeded").length;

  const githubMonthJobs = monthJobs.filter((j) => (j.assigned_executor ?? j.preferred_executor) === "github_actions");
  const cloudRunApproved = monthJobs.filter((j) => j.cloud_run_spend_approved === true).length;
  const governedRuntimeSeconds = githubMonthJobs.reduce((total, job) => {
    if (!job.started_at || !job.completed_at) return total;
    return total + Math.max(0, (new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000);
  }, 0);

  return <main>
    <section className="projectHero">
      <div>
        <Link className="backLink" href="/dashboard">← Research control center</Link>
        <p className="eyebrow">CLOUD COMPUTE · {stateData?.active_phase_code ?? "—"}</p>
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
        <span className="fieldLabel">Governed submission</span>
        <h3>Submit a certified fixture</h3>
        <p>Only allowlisted platform fixtures are exposed here while CCP-10 certifies real research-lane migration.</p>
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
      <div className="sectionHeader"><div><p className="eyebrow">COST & COMPUTE GUARDRAILS</p><h2>Zero-spend status</h2></div><span className="statusPill status-succeeded">Protected</span></div>
      <div className="metricGrid">
        <article className="metricCard"><span>GitHub compute billing</span><strong>$0</strong><small>Public repo · standard ubuntu runner</small></article>
        <article className="metricCard"><span>CCP jobs this month</span><strong>{githubMonthJobs.length}</strong><small>GitHub Actions governed jobs</small></article>
        <article className="metricCard"><span>Research runtime</span><strong>{formatDuration(governedRuntimeSeconds)}</strong><small>Job execution time observed this month</small></article>
        <article className="metricCard"><span>Cloud Run spend approvals</span><strong>{cloudRunApproved}</strong><small>Must remain 0 without explicit approval</small></article>
      </div>
      <article className="detailPanel">
        <div className="listTop"><strong>NO_INCREMENTAL_SPEND_WITHOUT_EXPLICIT_APPROVAL</strong><span className="statusPill status-succeeded">Enforced</span></div>
        <p>CCP dispatch is configured for standard GitHub-hosted runners in a public repository. GitHub does not bill Actions compute minutes for this configuration. Before Vercel creates a new cloud job, it now checks repository visibility and fails closed if the repository is no longer public. Larger runners and Cloud Run are not enabled by this control path.</p>
        <small>Runtime above is operational telemetry, not a billing quota. Public-repository standard GitHub Actions runner minutes currently have no monthly compute-minute allowance to exhaust.</small>
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
