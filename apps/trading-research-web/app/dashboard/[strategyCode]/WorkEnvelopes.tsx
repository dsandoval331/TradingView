import { createClient } from "../../../lib/supabase/server";

function prettyStatus(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "Not tracked";
  return String(value).replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" }).format(new Date(value));
}

type Props = { strategyId: string };

export default async function WorkEnvelopes({ strategyId }: Props) {
  const supabase = await createClient();
  const { data: envelopes, error: envelopeError } = await supabase
    .from("work_envelopes")
    .select("work_envelope_id,mwe_id,project_code,phase_code,workstream,objective,status,authority_ceiling,escalation_class,user_action_required,user_action_summary,cost_policy_code,record_origin,started_at,completed_at,updated_at")
    .eq("strategy_id", strategyId)
    .order("created_at", { ascending: false });

  if (envelopeError) {
    return <section className="alertPanel" id="work-envelopes"><strong>Work Envelope query failed.</strong><span>{envelopeError.message}</span></section>;
  }

  const envelopeRows = envelopes ?? [];
  const envelopeIds = envelopeRows.map((row) => row.work_envelope_id);
  const { data: links, error: linkError } = envelopeIds.length
    ? await supabase.from("work_envelope_research_jobs").select("work_envelope_id,job_id,relationship_role").in("work_envelope_id", envelopeIds)
    : { data: [], error: null };
  const jobIds = [...new Set((links ?? []).map((row) => row.job_id))];
  const { data: jobs, error: jobError } = jobIds.length
    ? await supabase.from("research_jobs").select("job_id,runner_job_id,project_code,phase_code,status,git_sha,assigned_executor,preferred_executor,cloud_run_spend_approved,started_at,completed_at").in("job_id", jobIds)
    : { data: [], error: null };
  const { data: providers, error: providerError } = await supabase.from("compute_provider_status").select("*").order("routing_priority", { ascending: true });

  const relatedError = linkError || jobError || providerError;
  const jobsById = new Map((jobs ?? []).map((job) => [job.job_id, job]));
  const linksByEnvelope = new Map<string, typeof links>();
  for (const link of links ?? []) {
    const existing = linksByEnvelope.get(link.work_envelope_id) ?? [];
    existing.push(link);
    linksByEnvelope.set(link.work_envelope_id, existing);
  }

  return <section className="projectSection" id="work-envelopes">
    <div className="sectionHeader"><div><p className="eyebrow">CHATGPT WORK</p><h2>MULtipLY Work Envelopes</h2></div><span>Read-only orchestration state</span></div>
    <p className="sectionDescription">MWE means MULtipLY Work Envelope. Research methodology remains owned by the canonical research thread; these records expose bounded Work orchestration, governed execution links, escalation state, and handoff status.</p>
    {relatedError && <div className="alertPanel"><strong>Related control-plane data is incomplete.</strong><span>{relatedError.message}</span></div>}
    {envelopeRows.some((row) => row.user_action_required) && <div className="alertPanel"><strong>USER ACTION REQUIRED</strong><span>At least one Work Envelope has reached an escalation boundary. Review the highlighted envelope below before execution continues.</span></div>}
    <div className="stackList">
      {envelopeRows.length ? envelopeRows.map((envelope) => {
        const envelopeLinks = linksByEnvelope.get(envelope.work_envelope_id) ?? [];
        const envelopeJobs = envelopeLinks.map((link) => jobsById.get(link.job_id)).filter(Boolean);
        return <article className={`detailPanel${envelope.user_action_required ? " blockingPanel" : ""}`} key={envelope.work_envelope_id}>
          <div className="listTop"><strong>{envelope.mwe_id}</strong><div className="timelineBadges"><span className="statusPill">{prettyStatus(envelope.status)}</span><span className="statusPill">{envelope.authority_ceiling}</span></div></div>
          <p>{envelope.objective}</p>
          {envelope.user_action_required && <p><strong>USER ACTION REQUIRED — {envelope.escalation_class ?? envelope.authority_ceiling}</strong>{envelope.user_action_summary ? ` · ${envelope.user_action_summary}` : ""}</p>}
          <dl className="detailGrid">
            <div><dt>Phase / workstream</dt><dd>{envelope.phase_code ?? envelope.workstream ?? "Not set"}</dd></div>
            <div><dt>Authority ceiling</dt><dd>{envelope.authority_ceiling}</dd></div>
            <div><dt>Cost policy</dt><dd>{envelope.cost_policy_code}</dd></div>
            <div><dt>Origin</dt><dd>{prettyStatus(envelope.record_origin)}</dd></div>
            <div><dt>Started</dt><dd>{formatDateTime(envelope.started_at)}</dd></div>
            <div><dt>Completed</dt><dd>{formatDateTime(envelope.completed_at)}</dd></div>
          </dl>
          <span className="fieldLabel spacedLabel">Governed execution</span>
          {envelopeJobs.length ? envelopeJobs.map((job: any) => <div key={job.job_id}>
            <p><strong>{job.runner_job_id ?? job.job_id}</strong> · {prettyStatus(job.status)} · {job.assigned_executor ?? job.preferred_executor ?? "Executor not assigned"}</p>
            <small>Job {job.job_id} · {job.project_code ?? "project not recorded"} / {job.phase_code ?? "phase not recorded"} · SHA {job.git_sha ?? "not recorded"} · Cloud Run spend approved: {job.cloud_run_spend_approved ? "YES" : "NO"}</small>
          </div>) : <p className="emptyState">No governed research job linked to this envelope.</p>}
          <small>Envelope updated: {formatDateTime(envelope.updated_at)}</small>
        </article>;
      }) : <p className="emptyState">No Work Envelopes are registered for this project.</p>}
    </div>
    <article className="detailPanel" style={{ marginTop: 18 }}>
      <span className="fieldLabel">Compute routing</span>
      {(providers ?? []).length ? (providers ?? []).map((provider: any) => <p key={provider.provider_code}><strong>{provider.provider_code}</strong> · priority {provider.routing_priority} · {prettyStatus(provider.provider_class)} · {prettyStatus(provider.free_compute_status ?? provider.status)}{provider.approval_required ? " · approval required" : ""}</p>) : <p className="emptyState">No compute-provider status is available.</p>}
      <small>Compute-provider state is authoritative here; MWE does not maintain a competing quota or spend model.</small>
    </article>
  </section>;
}
