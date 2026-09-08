import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { createClient } from "../../../lib/supabase/server";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ strategyCode: string }> };

function prettyStatus(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "Not tracked";
  return String(value).replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" }).format(new Date(value));
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
    supabase.from("program_phases").select("phase_id,phase_code,phase_name,objective,status,sequence_order,entry_criteria,exit_criteria,started_at,completed_at,next_phase_code,notes,updated_at").eq("strategy_id", strategy.strategy_id).order("sequence_order", { ascending: true }),
    supabase.from("project_decisions").select("decision_id,decision_date,title,decision,rationale,evidence,affects_model_version,status").eq("strategy_id", strategy.strategy_id).order("decision_date", { ascending: false }).limit(12),
    supabase.from("project_backlog").select("backlog_id,title,description,category,priority,status,origin_phase,blocking_current_phase,why_it_matters,promoted_to_phase,created_at,resolved_at,updated_at").eq("strategy_id", strategy.strategy_id).order("created_at", { ascending: false }),
    supabase.from("datasets").select("dataset_id,dataset_key,dataset_name,dataset_version,start_date,end_date,symbol_count,is_frozen,notes,updated_at").eq("strategy_id", strategy.strategy_id).order("created_at", { ascending: false }),
  ]);

  const queryError = stateResult.error || phasesResult.error || decisionsResult.error || backlogResult.error || datasetsResult.error;
  const state = stateResult.data;
  const phases = phasesResult.data ?? [];
  const decisions = decisionsResult.data ?? [];
  const backlog = backlogResult.data ?? [];
  const datasets = datasetsResult.data ?? [];
  const openBacklog = backlog.filter((item) => !["complete", "rejected", "cancelled"].includes(item.status));
  const openBlockingBacklog = openBacklog.filter((item) => item.blocking_current_phase);
  const currentPhase = phases.find((p) => p.phase_code === state?.active_phase_code);
  const nextPhase = phases.find((p) => p.phase_code === state?.next_phase_code);
  const activePhaseRows = phases.filter((p) => p.status === "active");
  const isPmpd = strategy.strategy_code === "PMPD";
  const metadata = (state?.metadata_json ?? {}) as Record<string, unknown>;
  const v4TrackStatus = typeof metadata.v4_track_status === "string" ? metadata.v4_track_status : "FROZEN_BENCHMARK";
  const v5TrackStatus = typeof metadata.v5_track_status === "string" ? metadata.v5_track_status : "ACTIVE_RESEARCH";
  const legacyRoadmapStatus = typeof metadata.legacy_8h_roadmap_status === "string" ? metadata.legacy_8h_roadmap_status : "SUPERSEDED_PRESERVED";
  const legacyRoadmapVersion = typeof metadata.legacy_roadmap_version === "string" ? metadata.legacy_roadmap_version : "PMPD-RM-1.0";

  const healthIssues: string[] = [];
  if (!state) healthIssues.push("No project_state record is present, so current status and next-step tracking are not yet configured.");
  if (phases.length === 0) healthIssues.push("No program_phases roadmap is registered for this project.");
  if (state?.active_phase_code && !currentPhase) healthIssues.push(`Current phase ${state.active_phase_code} is not present in program_phases.`);
  if (currentPhase && currentPhase.status !== "active") healthIssues.push(`project_state says ${currentPhase.phase_code} is current, but program_phases marks it ${prettyStatus(currentPhase.status)}.`);
  if (activePhaseRows.length > 1) healthIssues.push(`program_phases contains ${activePhaseRows.length} phases marked Active (${activePhaseRows.map((p) => p.phase_code).join(", ")}).`);
  if (activePhaseRows.length === 1 && state?.active_phase_code && activePhaseRows[0].phase_code !== state.active_phase_code) healthIssues.push(`program_phases marks ${activePhaseRows[0].phase_code} Active while project_state identifies ${state.active_phase_code} as current.`);
  if ((state?.blocker_count ?? 0) !== openBlockingBacklog.length) healthIssues.push(`Gate count differs: project_state reports ${state?.blocker_count ?? 0}, while the open backlog contains ${openBlockingBacklog.length} required phase-closing item${openBlockingBacklog.length === 1 ? "" : "s"}.`);
  if (state && !state.roadmap_version) healthIssues.push("No roadmap version is recorded in project_state.");

  return (
    <main>
      <section className="projectHero">
        <div>
          <Link className="backLink" href="/dashboard">← Research control center</Link>
          <p className="eyebrow">{strategy.strategy_code} · {prettyStatus(strategy.status)}</p>
          <h1>{strategy.strategy_name}</h1>
          <p className="lede">{strategy.description ?? "No project description recorded."}</p>
          <p className="sectionDescription">Project state updated: {formatDateTime(state?.updated_at)}</p>
        </div>
        <span className="securityBadge">Authenticated · Allowlisted · Read-only</span>
      </section>

      {queryError ? <section className="alertPanel"><strong>Project query failed.</strong><span>{queryError.message}</span></section> : <>
        <nav className="projectNav" aria-label="Project sections">
          {isPmpd && <a href="#model-tracks">Model Tracks</a>}
          <a href="#status-plan">Status & Plan</a>
          <a href="#roadmap">Roadmap</a>
          <a href="#decisions">Decisions</a>
          <a href="#backlog">Backlog</a>
          <a href="#datasets">Datasets</a>
        </nav>

        <section className="metricGrid">
          <article className="metricCard"><span>Current phase</span><strong className="metricText">{state?.active_phase_code ?? "—"}</strong><small>{state?.active_phase_name ?? "No active phase recorded"}</small></article>
          <article className="metricCard"><span>Next phase</span><strong className="metricText">{state?.next_phase_code ?? "—"}</strong><small>{state?.next_phase_name ?? "No next phase recorded"}</small></article>
          <article className="metricCard"><span>{isPmpd ? "Required gates" : "Open backlog"}</span><strong>{isPmpd ? openBlockingBacklog.length : openBacklog.length}</strong><small>{isPmpd ? "Unresolved phase-close requirements" : `${openBlockingBacklog.length} blocking current phase`}</small></article>
          <article className="metricCard"><span>Datasets</span><strong>{datasets.length}</strong><small>{datasets.filter((d) => d.is_frozen).length} frozen</small></article>
        </section>

        <section className={`trackingHealth ${healthIssues.length ? "trackingHealth-warning" : "trackingHealth-ok"}`}>
          <div>
            <span className="fieldLabel">Tracking health</span>
            <strong>{healthIssues.length ? `${healthIssues.length} data-quality issue${healthIssues.length === 1 ? "" : "s"} detected` : "Project tracking is aligned"}</strong>
          </div>
          {healthIssues.length ? <ul>{healthIssues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : <p>Current phase, roadmap state, and required-gate tracking are internally consistent.</p>}
        </section>

        {isPmpd && <section className="projectSection" id="model-tracks">
          <div className="sectionHeader"><div><p className="eyebrow">MODEL TRACKS</p><h2>One PM+PD program, two versions</h2></div><span>Shared governance · separate purposes</span></div>
          <div className="statusPlanGrid">
            <article className="detailPanel">
              <div className="listTop"><strong>V4 · Benchmark / Forward Validation</strong><span className="statusPill">{prettyStatus(v4TrackStatus)}</span></div>
              <p>Frozen reference implementation used for forward validation, live comparison, trade review, and benchmark performance.</p>
              <dl className="detailGrid"><div><dt>Role</dt><dd>Benchmark</dd></div><div><dt>Baseline</dt><dd>{state?.baseline_model ?? strategy.baseline_model ?? "V4"}</dd></div><div><dt>Validation</dt><dd>{prettyStatus(state?.forward_validation_status)}</dd></div><div><dt>Change policy</dt><dd>Frozen / controlled</dd></div></dl>
            </article>
            <article className="detailPanel">
              <div className="listTop"><strong>V5 · Active Research Successor</strong><span className="statusPill status-active">{prettyStatus(v5TrackStatus)}</span></div>
              <p>Active research track for the successor architecture. The main PM+PD project status follows this track.</p>
              <dl className="detailGrid"><div><dt>Current phase</dt><dd>{state?.active_phase_code ?? "—"} · {state?.active_phase_name ?? "Not tracked"}</dd></div><div><dt>Next phase</dt><dd>{state?.next_phase_code ?? "—"}</dd></div><div><dt>Active roadmap</dt><dd>{state?.roadmap_version ?? "Not tracked"}</dd></div><div><dt>Required gates</dt><dd>{openBlockingBacklog.length}</dd></div></dl>
            </article>
          </div>
          <article className="detailPanel" style={{ marginTop: 18 }}>
            <span className="fieldLabel">Roadmap governance</span>
            <p><strong>{state?.roadmap_version ?? "PMPD-V5-RM-2.0"}</strong> is the authoritative current V5 roadmap. <strong>{legacyRoadmapVersion}</strong> is preserved as {prettyStatus(legacyRoadmapStatus)} history rather than treated as a competing active track.</p>
          </article>
        </section>}

        <section className="projectSection" id="status-plan">
          <div className="sectionHeader"><div><p className="eyebrow">STATUS & PLAN</p><h2>Where the project stands</h2></div><span>Updated {formatDateTime(state?.updated_at)}</span></div>
          <div className="statusPlanGrid">
            <article className="detailPanel">
              <span className="fieldLabel">Current objective</span>
              <h3>{state?.active_phase_code ?? "No active phase"}{state?.active_phase_name ? ` · ${state.active_phase_name}` : ""}</h3>
              <p>{currentPhase?.objective ?? "No phase objective recorded."}</p>
              <dl className="detailGrid"><div><dt>Baseline</dt><dd>{state?.baseline_model ?? strategy.baseline_model ?? "Not set"}</dd></div><div><dt>Baseline status</dt><dd>{prettyStatus(state?.baseline_status)}</dd></div><div><dt>Forward validation</dt><dd>{prettyStatus(state?.forward_validation_status)}</dd></div><div><dt>{isPmpd ? "Required gates" : "Blockers"}</dt><dd>{state?.blocker_count ?? 0}</dd></div></dl>
              {currentPhase?.entry_criteria && <details><summary>Entry criteria</summary><p>{currentPhase.entry_criteria}</p></details>}
              {currentPhase?.exit_criteria && <details open><summary>Exit criteria / definition of done</summary><p>{currentPhase.exit_criteria}</p></details>}
            </article>
            <article className="detailPanel">
              <span className="fieldLabel">Next planned step</span>
              <h3>{state?.next_phase_code ?? "Not scheduled"}{state?.next_phase_name ? ` · ${state.next_phase_name}` : ""}</h3>
              <p>{nextPhase?.objective ?? "No next-phase objective recorded."}</p>
              {nextPhase?.entry_criteria && <details><summary>Next-phase entry criteria</summary><p>{nextPhase.entry_criteria}</p></details>}
              <span className="fieldLabel spacedLabel">Latest recorded decision</span>
              <p>{state?.last_decision ?? "No decision summary recorded."}</p>
              <small>Project state updated: {formatDateTime(state?.updated_at)}</small>
            </article>
          </div>
        </section>

        <section className="projectSection" id="roadmap">
          <div className="sectionHeader"><div><p className="eyebrow">ROADMAP</p><h2>Phase timeline</h2></div><span>{phases.length} tracked phases</span></div>
          <div className="timeline">
            {phases.map((phase) => {
              const isCurrent = phase.phase_code === state?.active_phase_code;
              return <article className={`timelineItem timeline-${phase.status}${isCurrent ? " timeline-current" : ""}`} key={phase.phase_id}><div className="timelineMarker"/><div><div className="timelineTop"><strong>{phase.phase_code} · {phase.phase_name}</strong><div className="timelineBadges">{isCurrent && <span className="currentBadge">CURRENT</span>}<span className="statusPill">{prettyStatus(phase.status)}</span></div></div><p>{phase.objective ?? "No objective recorded."}</p><div className="timelineMeta"><span>Started: {formatDateTime(phase.started_at)}</span><span>Completed: {formatDateTime(phase.completed_at)}</span><span>Updated: {formatDateTime(phase.updated_at)}</span>{phase.next_phase_code && <span>Next: {phase.next_phase_code}</span>}</div>{phase.exit_criteria && <details><summary>Exit criteria</summary><p>{phase.exit_criteria}</p></details>}</div></article>;
            })}
          </div>
        </section>

        <section className="projectSection twoColumnSection">
          <div id="decisions"><div className="sectionHeader"><div><p className="eyebrow">DECISIONS</p><h2>Recent decisions</h2></div></div><div className="stackList">{decisions.length ? decisions.map((item) => <article className="detailPanel" key={item.decision_id}><div className="listTop"><strong>{item.title}</strong><time>{formatDateTime(item.decision_date)}</time></div><p>{item.decision}</p>{item.rationale && <small>{item.rationale}</small>}</article>) : <p className="emptyState">No decisions recorded.</p>}</div></div>
          <div id="backlog"><div className="sectionHeader"><div><p className="eyebrow">BACKLOG</p><h2>Plan queue</h2></div></div><div className="stackList">{backlog.length ? backlog.map((item) => <article className={`detailPanel${item.blocking_current_phase && !["complete", "rejected", "cancelled"].includes(item.status) ? " blockingPanel" : ""}`} key={item.backlog_id}><div className="listTop"><strong>{item.title}</strong><span className="statusPill">{prettyStatus(item.status)}</span></div><p>{item.description ?? item.why_it_matters ?? "No description recorded."}</p><small>{item.priority ? `Priority: ${prettyStatus(item.priority)}` : "Priority not set"}{item.origin_phase ? ` · Origin: ${item.origin_phase}` : ""}{item.blocking_current_phase && !["complete", "rejected", "cancelled"].includes(item.status) ? ` · ${isPmpd ? "REQUIRED GATE" : "BLOCKING"}` : ""}</small><small>Updated: {formatDateTime(item.updated_at ?? item.created_at)}</small></article>) : <p className="emptyState">No backlog items recorded.</p>}</div></div>
        </section>

        <section className="projectSection" id="datasets"><div className="sectionHeader"><div><p className="eyebrow">DATASETS</p><h2>Research evidence</h2></div></div><div className="datasetList">{datasets.length ? datasets.map((dataset) => <article className="detailPanel" key={dataset.dataset_id}><div className="listTop"><strong>{dataset.dataset_name ?? dataset.dataset_key}</strong><span className="statusPill">{dataset.is_frozen ? "Frozen" : "Active"}</span></div><p>{dataset.dataset_version ?? "No version"}{dataset.symbol_count ? ` · ${dataset.symbol_count} symbols` : ""}</p><small>{dataset.start_date ?? "?"} → {dataset.end_date ?? "?"}</small><small>Updated: {formatDateTime(dataset.updated_at)}</small></article>) : <p className="emptyState">No datasets registered for this project.</p>}</div></section>
      </>}
    </main>
  );
}
