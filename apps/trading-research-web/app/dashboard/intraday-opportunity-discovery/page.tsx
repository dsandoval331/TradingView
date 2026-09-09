import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "../../../lib/supabase/server";

export const dynamic = "force-dynamic";
const MASTER = "INTRADAY_OPP_MASTER";

function pretty(value: string | null | undefined) {
  if (!value) return "Not tracked";
  return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}
function stamp(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month:"short", day:"numeric", year:"numeric", hour:"numeric", minute:"2-digit", timeZone:"America/Chicago", timeZoneName:"short" }).format(new Date(value));
}
function laneCode(title: string) { return title.match(/IR-\d{2}/)?.[0] ?? "—"; }
function family(title: string) { return title.replace(/^IR-\d{2}\s+/, ""); }

export default async function IntradayOpportunityMaster() {
  const supabase = await createClient();
  const { data: claimsData, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claimsData?.claims) redirect("/login");
  const { data: allowed, error: accessError } = await supabase.rpc("is_trading_research_web_user");
  if (accessError || allowed !== true) redirect("/unauthorized");

  const { data: strategy, error: strategyError } = await supabase.from("strategies").select("strategy_id,strategy_code,strategy_name,status,description,metadata_json,updated_at").eq("strategy_code", MASTER).maybeSingle();
  if (strategyError) throw strategyError;
  if (!strategy) return <main><Link className="backLink" href="/dashboard">← Research control center</Link><section className="alertPanel"><strong>Master program not registered.</strong></section></main>;

  const [stateR, phasesR, backlogR, decisionsR] = await Promise.all([
    supabase.from("project_state").select("*").eq("strategy_id", strategy.strategy_id).maybeSingle(),
    supabase.from("program_phases").select("phase_id,phase_code,phase_name,objective,status,sequence_order,entry_criteria,exit_criteria,started_at,completed_at,next_phase_code,notes,updated_at").eq("strategy_id", strategy.strategy_id).order("sequence_order"),
    supabase.from("project_backlog").select("backlog_id,title,description,category,priority,status,origin_phase,blocking_current_phase,why_it_matters,promoted_to_phase,created_at,resolved_at,updated_at").eq("strategy_id", strategy.strategy_id).order("priority"),
    supabase.from("project_decisions").select("decision_id,decision_date,title,decision,rationale,evidence,status,metadata_json").eq("strategy_id", strategy.strategy_id).order("decision_date", { ascending:false }),
  ]);
  const queryError = stateR.error || phasesR.error || backlogR.error || decisionsR.error;
  const state = stateR.data;
  const phases = phasesR.data ?? [];
  const backlog = backlogR.data ?? [];
  const decisions = decisionsR.data ?? [];
  const lanes = backlog.filter(x => x.category === "child_research_lane" || x.category === "candidate_lane").sort((a,b) => (a.priority ?? 99) - (b.priority ?? 99));
  const activeResearch = lanes.filter(x => ["active","research_active"].includes(x.status)).length;
  const awaiting = lanes.filter(x => ["awaiting_final_results","awaiting_results"].includes(x.status)).length;
  const completed = lanes.filter(x => ["complete","results_received"].includes(x.status)).length;
  const validationQualified = lanes.filter(x => x.promoted_to_phase === "M6").length;
  const rejected = lanes.filter(x => ["rejected","cancelled"].includes(x.status)).length;
  const implementationCandidates = lanes.filter(x => x.promoted_to_phase === "M8").length;
  const graveyard = backlog.filter(x => ["rejected","cancelled"].includes(x.status));

  return <main>
    <section className="projectHero masterHero"><div><Link className="backLink" href="/dashboard">← Research control center</Link><p className="eyebrow">MASTER RESEARCH COORDINATION PROGRAM</p><h1>Intraday 0.5%–1.0% Opportunity Discovery</h1><p className="masterSubtitle">Master Research Coordination</p><p className="lede">{strategy.description}</p></div><span className="securityBadge">Authenticated · Allowlisted · Read-only</span></section>
    {queryError ? <section className="alertPanel"><strong>Master query failed.</strong><span>{queryError.message}</span></section> : <>
      <nav className="projectNav"><a href="#overview">Master Overview</a><a href="#lanes">Research Lanes</a><a href="#roadmap">Roadmap</a><a href="#comparison">Results Comparison</a><a href="#evidence">Evidence</a><a href="#graveyard">Hypothesis Graveyard</a><a href="#decisions">Decisions / Activity</a></nav>
      <section id="overview" className="masterProgramPanel"><div><span className="fieldLabel">Program phase</span><h2>{state?.active_phase_code ?? "—"} · {state?.active_phase_name ?? "Not tracked"}</h2><p>Roadmap: {state?.roadmap_version ?? "Not tracked"} · Next: {state?.next_phase_code ?? "—"} · {state?.next_phase_name ?? "Not tracked"}</p></div><time>Updated: {stamp(state?.updated_at)}</time></section>
      <section className="masterMetricGrid"><article className="metricCard"><span>Research lanes</span><strong>{lanes.length}</strong><small>Registered candidate phenomena</small></article><article className="metricCard"><span>Active research</span><strong>{activeResearch}</strong><small>Currently conducting research</small></article><article className="metricCard"><span>Awaiting results</span><strong>{awaiting}</strong><small>Issued and awaiting final return</small></article><article className="metricCard"><span>Completed research</span><strong>{completed}</strong><small>Final packages returned</small></article><article className="metricCard"><span>Validation qualified</span><strong>{validationQualified}</strong><small>Advanced to stronger validation</small></article><article className="metricCard"><span>Rejected</span><strong>{rejected}</strong><small>Preserved negative findings</small></article><article className="metricCard"><span>Implementation candidates</span><strong>{implementationCandidates}</strong><small>Qualified for implementation review</small></article></section>

      <section className="projectSection" id="lanes"><div className="sectionHeader"><div><p className="eyebrow">RESEARCH LANES</p><h2>Independent opportunity-family board</h2><p className="sectionDescription">Lifecycle is shown from live program records. Research lanes are hypotheses, not trading systems or automatic implementation candidates.</p></div><span>{lanes.length} lanes</span></div><div className="laneTableWrap"><table className="laneTable"><thead><tr><th>Lane</th><th>Research family</th><th>Priority</th><th>Lifecycle</th><th>Prompt</th><th>Current phase</th><th>Evidence grade</th><th>Master disposition</th></tr></thead><tbody>{lanes.map(lane => { const code=laneCode(lane.title); const prompt = code === "IR-01" && state?.metadata_json?.IR01 === "ready_for_prompt" ? "Prepared" : ["ready","active"].includes(lane.status) ? "Ready" : "Pending"; return <tr key={lane.backlog_id}><td><strong>{code}</strong></td><td>{family(lane.title)}<small>{lane.why_it_matters}</small></td><td>{lane.priority ?? "—"}</td><td><span className="statusPill">{pretty(lane.status)}</span></td><td>{prompt}</td><td>{lane.origin_phase ?? "—"}</td><td>—</td><td>{lane.promoted_to_phase ? `Promoted → ${lane.promoted_to_phase}` : "—"}</td></tr>; })}</tbody></table></div></section>

      <section className="projectSection" id="roadmap"><div className="sectionHeader"><div><p className="eyebrow">MASTER ROADMAP</p><h2>Idea → evidence → validation → decision</h2></div><span>{state?.roadmap_version}</span></div><div className="timeline">{phases.map(p => <article className={`timelineItem timeline-${p.status}${p.phase_code===state?.active_phase_code ? " timeline-current" : ""}`} key={p.phase_id}><div className="timelineMarker"/><div><div className="timelineTop"><strong>{p.phase_code} · {p.phase_name}</strong><div className="timelineBadges">{p.phase_code===state?.active_phase_code && <span className="currentBadge">CURRENT</span>}<span className="statusPill">{pretty(p.status)}</span></div></div><p>{p.objective}</p><div className="timelineMeta"><span>Updated: {stamp(p.updated_at)}</span>{p.completed_at && <span>Completed: {stamp(p.completed_at)}</span>}</div></div></article>)}</div></section>

      <section className="projectSection" id="comparison"><div className="sectionHeader"><div><p className="eyebrow">RESULTS COMPARISON</p><h2>Cross-family research comparison</h2></div></div><article className="detailPanel masterEmpty"><strong>No comparable research returns yet.</strong><p>This area will compare standardized long/short first-passage outcomes, opportunity frequency, MFE/MAE, timing, regime stability and cost robustness only after audited lane results exist. No placeholder performance is shown.</p></article></section>

      <section className="projectSection" id="evidence"><div className="sectionHeader"><div><p className="eyebrow">EVIDENCE</p><h2>Shared research evidence</h2></div></div><article className="detailPanel masterEmpty"><strong>Evidence tables remain protected from this web role.</strong><p>The live schema contains shared research sources, findings and strategy links, but those research tables currently have RLS enabled with no authenticated read policy. This control plane will not weaken database security to display them. Evidence can be surfaced after a deliberate read-only policy/view is approved.</p></article></section>

      <section className="projectSection" id="graveyard"><div className="sectionHeader"><div><p className="eyebrow">HYPOTHESIS GRAVEYARD</p><h2>Preserved negative research</h2></div><span>{graveyard.length} rejected</span></div>{graveyard.length ? <div className="stackList">{graveyard.map(x => <article className="detailPanel" key={x.backlog_id}><div className="listTop"><strong>{x.title}</strong><span className="statusPill">{pretty(x.status)}</span></div><p>{x.description}</p><small>Resolved: {stamp(x.resolved_at)}</small></article>)}</div> : <article className="detailPanel masterEmpty"><strong>No rejected hypotheses recorded yet.</strong><p>Failed ideas will remain visible here rather than being deleted, protecting the program from repeatedly rediscovering or mutating rejected hypotheses.</p></article>}</section>

      <section className="projectSection" id="decisions"><div className="sectionHeader"><div><p className="eyebrow">DECISIONS / ACTIVITY</p><h2>Auditable master decisions</h2></div></div><div className="stackList">{decisions.map(d => <article className="detailPanel" key={d.decision_id}><div className="listTop"><strong>{d.title}</strong><time>{stamp(d.decision_date)}</time></div><p>{d.decision}</p>{d.rationale && <small>{d.rationale}</small>}</article>)}</div></section>
    </>}
  </main>;
}
