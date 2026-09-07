import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { createClient } from "../../../lib/supabase/server";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ strategyCode: string }> };

function prettyStatus(value: string | null | undefined) {
  if (!value) return "Not tracked";
  return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "America/Chicago" }).format(new Date(value));
}

export default async function ProjectDetailPage({ params }: Props) {
  const { strategyCode } = await params;
  const supabase = await createClient();
  const { data: claimsData, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claimsData?.claims) redirect("/login");

  const { data: allowed, error: accessError } = await supabase.rpc("is_trading_research_web_user");
  if (accessError || allowed !== true) redirect("/unauthorized");

  const { data: strategy, error: strategyError } = await supabase
    .from("strategies")
    .select("strategy_id,strategy_code,strategy_name,strategy_type,status,baseline_model,description")
    .eq("strategy_code", strategyCode.toUpperCase())
    .maybeSingle();

  if (strategyError) throw strategyError;
  if (!strategy) notFound();

  const [stateResult, phasesResult, decisionsResult, backlogResult, datasetsResult] = await Promise.all([
    supabase.from("project_state").select("*").eq("strategy_id", strategy.strategy_id).maybeSingle(),
    supabase.from("program_phases").select("phase_id,phase_code,phase_name,objective,status,sequence_order,entry_criteria,exit_criteria,started_at,completed_at,next_phase_code,notes").eq("strategy_id", strategy.strategy_id).order("sequence_order", { ascending: true }),
    supabase.from("project_decisions").select("decision_id,decision_date,title,decision,rationale,evidence,affects_model_version,status").eq("strategy_id", strategy.strategy_id).order("decision_date", { ascending: false }).limit(12),
    supabase.from("project_backlog").select("backlog_id,title,description,category,priority,status,origin_phase,blocking_current_phase,why_it_matters,promoted_to_phase,created_at,resolved_at,updated_at").eq("strategy_id", strategy.strategy_id).order("created_at", { ascending: false }),
    supabase.from("datasets").select("dataset_id,dataset_key,dataset_name,dataset_version,start_date,end_date,symbol_count,is_frozen,notes").eq("strategy_id", strategy.strategy_id).order("created_at", { ascending: false }),
  ]);

  const queryError = stateResult.error || phasesResult.error || decisionsResult.error || backlogResult.error || datasetsResult.error;
  const state = stateResult.data;
  const phases = phasesResult.data ?? [];
  const decisions = decisionsResult.data ?? [];
  const backlog = backlogResult.data ?? [];
  const datasets = datasetsResult.data ?? [];
  const openBacklog = backlog.filter((item) => !["complete", "rejected", "cancelled"].includes(item.status));

  return (
    <main>
      <section className="projectHero">
        <div>
          <Link className="backLink" href="/dashboard">← Research control center</Link>
          <p className="eyebrow">{strategy.strategy_code} · {prettyStatus(strategy.status)}</p>
          <h1>{strategy.strategy_name}</h1>
          <p className="lede">{strategy.description ?? "No project description recorded."}</p>
        </div>
        <span className="securityBadge">Authenticated · Allowlisted · Read-only</span>
      </section>

      {queryError ? <section className="alertPanel"><strong>Project query failed.</strong><span>{queryError.message}</span></section> : <>
        <section className="metricGrid">
          <article className="metricCard"><span>Current phase</span><strong className="metricText">{state?.active_phase_code ?? "—"}</strong><small>{state?.active_phase_name ?? "No active phase recorded"}</small></article>
          <article className="metricCard"><span>Next phase</span><strong className="metricText">{state?.next_phase_code ?? "—"}</strong><small>{state?.next_phase_name ?? "No next phase recorded"}</small></article>
          <article className="metricCard"><span>Open backlog</span><strong>{openBacklog.length}</strong><small>{backlog.filter((item) => item.blocking_current_phase).length} blocking current phase</small></article>
          <article className="metricCard"><span>Datasets</span><strong>{datasets.length}</strong><small>{datasets.filter((d) => d.is_frozen).length} frozen</small></article>
        </section>

        <section className="projectSection">
          <div className="sectionHeader"><div><p className="eyebrow">STATUS & PLAN</p><h2>Where the project stands</h2></div><span>{state?.roadmap_version ?? "Roadmap not tracked"}</span></div>
          <div className="statusPlanGrid">
            <article className="detailPanel"><span className="fieldLabel">Current objective</span><h3>{state?.active_phase_code ?? "No active phase"}{state?.active_phase_name ? ` · ${state.active_phase_name}` : ""}</h3><p>{phases.find((p) => p.phase_code === state?.active_phase_code)?.objective ?? "No phase objective recorded."}</p><dl className="detailGrid"><div><dt>Baseline</dt><dd>{state?.baseline_model ?? strategy.baseline_model ?? "Not set"}</dd></div><div><dt>Baseline status</dt><dd>{prettyStatus(state?.baseline_status)}</dd></div><div><dt>Forward validation</dt><dd>{prettyStatus(state?.forward_validation_status)}</dd></div><div><dt>Blockers</dt><dd>{state?.blocker_count ?? 0}</dd></div></dl></article>
            <article className="detailPanel"><span className="fieldLabel">Next planned step</span><h3>{state?.next_phase_code ?? "Not scheduled"}{state?.next_phase_name ? ` · ${state.next_phase_name}` : ""}</h3><p>{phases.find((p) => p.phase_code === state?.next_phase_code)?.objective ?? "No next-phase objective recorded."}</p><span className="fieldLabel">Latest recorded decision</span><p>{state?.last_decision ?? "No decision summary recorded."}</p></article>
          </div>
        </section>

        <section className="projectSection">
          <div className="sectionHeader"><div><p className="eyebrow">ROADMAP</p><h2>Phase timeline</h2></div><span>{phases.length} tracked phases</span></div>
          <div className="timeline">
            {phases.map((phase) => <article className={`timelineItem timeline-${phase.status}`} key={phase.phase_id}><div className="timelineMarker"/><div><div className="timelineTop"><strong>{phase.phase_code} · {phase.phase_name}</strong><span className="statusPill">{prettyStatus(phase.status)}</span></div><p>{phase.objective ?? "No objective recorded."}</p><div className="timelineMeta"><span>Started: {formatDate(phase.started_at)}</span><span>Completed: {formatDate(phase.completed_at)}</span>{phase.next_phase_code && <span>Next: {phase.next_phase_code}</span>}</div>{phase.exit_criteria && <details><summary>Exit criteria</summary><p>{phase.exit_criteria}</p></details>}</div></article>)}
          </div>
        </section>

        <section className="projectSection twoColumnSection">
          <div><div className="sectionHeader"><div><p className="eyebrow">DECISIONS</p><h2>Recent decisions</h2></div></div><div className="stackList">{decisions.length ? decisions.map((item) => <article className="detailPanel" key={item.decision_id}><div className="listTop"><strong>{item.title}</strong><time>{formatDate(item.decision_date)}</time></div><p>{item.decision}</p>{item.rationale && <small>{item.rationale}</small>}</article>) : <p className="emptyState">No decisions recorded.</p>}</div></div>
          <div><div className="sectionHeader"><div><p className="eyebrow">BACKLOG</p><h2>Plan queue</h2></div></div><div className="stackList">{backlog.length ? backlog.map((item) => <article className="detailPanel" key={item.backlog_id}><div className="listTop"><strong>{item.title}</strong><span className="statusPill">{prettyStatus(item.status)}</span></div><p>{item.description ?? item.why_it_matters ?? "No description recorded."}</p><small>{item.priority ? `Priority: ${prettyStatus(item.priority)}` : "Priority not set"}{item.origin_phase ? ` · Origin: ${item.origin_phase}` : ""}{item.blocking_current_phase ? " · BLOCKING" : ""}</small></article>) : <p className="emptyState">No backlog items recorded.</p>}</div></div>
        </section>

        <section className="projectSection"><div className="sectionHeader"><div><p className="eyebrow">DATASETS</p><h2>Research evidence</h2></div></div><div className="datasetList">{datasets.length ? datasets.map((dataset) => <article className="detailPanel" key={dataset.dataset_id}><div className="listTop"><strong>{dataset.dataset_name ?? dataset.dataset_key}</strong><span className="statusPill">{dataset.is_frozen ? "Frozen" : "Active"}</span></div><p>{dataset.dataset_version ?? "No version"}{dataset.symbol_count ? ` · ${dataset.symbol_count} symbols` : ""}</p><small>{dataset.start_date ?? "?"} → {dataset.end_date ?? "?"}</small></article>) : <p className="emptyState">No datasets registered for this project.</p>}</div></section>
      </>}
    </main>
  );
}
