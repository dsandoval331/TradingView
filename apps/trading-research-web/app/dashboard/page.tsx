import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "../../lib/supabase/server";

export const dynamic = "force-dynamic";

type Strategy = { strategy_id: string; strategy_code: string; strategy_name: string; strategy_type: string; status: string; baseline_model: string | null; description: string | null; };
type ProjectState = { strategy_id: string; active_phase_code: string | null; active_phase_name: string | null; next_phase_code: string | null; next_phase_name: string | null; blocker_count: number | null; baseline_model: string | null; baseline_status: string | null; forward_validation_status: string | null; historical_dataset_status: string | null; active_tangent_count: number | null; last_decision: string | null; roadmap_version: string | null; updated_at: string | null; };
type Dataset = { strategy_id: string; is_frozen: boolean | null; };

function prettyStatus(value: string | null | undefined) { if (!value) return "Not tracked"; return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()); }
function formatUpdated(value: string | null | undefined) { if (!value) return "No state timestamp"; return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "America/Chicago" }).format(new Date(value)); }

export default async function DashboardPage() {
  const supabase = await createClient();
  const { data: claimsData, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claimsData?.claims) redirect("/login");
  const { data: allowed, error: accessError } = await supabase.rpc("is_trading_research_web_user");
  if (accessError || allowed !== true) redirect("/unauthorized");

  const [strategiesResult, statesResult, datasetsResult] = await Promise.all([
    supabase.from("strategies").select("strategy_id,strategy_code,strategy_name,strategy_type,status,baseline_model,description").order("strategy_name", { ascending: true }),
    supabase.from("project_state").select("strategy_id,active_phase_code,active_phase_name,next_phase_code,next_phase_name,blocker_count,baseline_model,baseline_status,forward_validation_status,historical_dataset_status,active_tangent_count,last_decision,roadmap_version,updated_at"),
    supabase.from("datasets").select("strategy_id,is_frozen"),
  ]);

  const queryError = strategiesResult.error || statesResult.error || datasetsResult.error;
  const strategies = (strategiesResult.data ?? []) as Strategy[];
  const states = (statesResult.data ?? []) as ProjectState[];
  const datasets = (datasetsResult.data ?? []) as Dataset[];
  const stateByStrategy = new Map(states.map((state) => [state.strategy_id, state]));
  const datasetStats = new Map<string, { total: number; frozen: number }>();
  for (const dataset of datasets) { const current = datasetStats.get(dataset.strategy_id) ?? { total: 0, frozen: 0 }; current.total += 1; if (dataset.is_frozen) current.frozen += 1; datasetStats.set(dataset.strategy_id, current); }

  const activeCount = strategies.filter((strategy) => strategy.status === "active").length;
  const researchCount = strategies.filter((strategy) => strategy.status === "research").length;
  const blockerCount = states.reduce((sum, state) => sum + (state.blocker_count ?? 0), 0);

  const tradeReviewCodes = new Set(["TRADE_REVIEW"]);
  const toolCodes = new Set(["PLATFORM", "REALTIME_ADVISOR", "TV_AUTOMATION"]);
  const tradeReviews = strategies.filter((strategy) => tradeReviewCodes.has(strategy.strategy_code));
  const tools = strategies.filter((strategy) => toolCodes.has(strategy.strategy_code));
  const indicatorStrategies = strategies.filter((strategy) => !tradeReviewCodes.has(strategy.strategy_code) && !toolCodes.has(strategy.strategy_code));

  const renderCard = (strategy: Strategy) => {
    const state = stateByStrategy.get(strategy.strategy_id);
    const stats = datasetStats.get(strategy.strategy_id) ?? { total: 0, frozen: 0 };
    return <article className="strategyCard" key={strategy.strategy_id}><div className="cardTopline"><span className="strategyCode">{strategy.strategy_code}</span><span className={`statusPill status-${strategy.status}`}>{prettyStatus(strategy.status)}</span></div><h3>{strategy.strategy_name}</h3><p className="strategyDescription">{strategy.description ?? "No description recorded."}</p><div className="phaseBlock"><span className="fieldLabel">Current phase</span><strong>{state?.active_phase_code ?? "—"}{state?.active_phase_name ? ` · ${state.active_phase_name}` : ""}</strong><span className="nextPhase">Next: {state?.next_phase_code ?? "Not scheduled"}{state?.next_phase_name ? ` · ${state.next_phase_name}` : ""}</span></div><dl className="detailGrid"><div><dt>Baseline</dt><dd>{state?.baseline_model ?? strategy.baseline_model ?? "Not set"}</dd></div><div><dt>Baseline status</dt><dd>{prettyStatus(state?.baseline_status)}</dd></div><div><dt>Forward validation</dt><dd>{prettyStatus(state?.forward_validation_status)}</dd></div><div><dt>Datasets</dt><dd>{stats.total}{stats.total ? ` (${stats.frozen} frozen)` : ""}</dd></div><div><dt>Roadmap</dt><dd>{state?.roadmap_version ?? "Not tracked"}</dd></div><div><dt>Blockers</dt><dd>{state?.blocker_count ?? 0}</dd></div></dl><div className="decisionBlock"><span className="fieldLabel">Latest recorded decision</span><p>{state?.last_decision ?? "No project-state decision summary recorded yet."}</p></div><footer className="cardFooter"><span>{state?.historical_dataset_status ? `Data: ${state.historical_dataset_status}` : "Historical data status not tracked"}</span><time>{formatUpdated(state?.updated_at)}</time></footer><Link className="projectLink" href={`/dashboard/${strategy.strategy_code.toLowerCase()}`}>View status, plan & roadmap →</Link></article>;
  };

  const renderGroup = (eyebrow: string, title: string, description: string, items: Strategy[], tone: string) => <section className={`portfolioSection ${tone}`}><div className="sectionHeader"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2><p className="sectionDescription">{description}</p></div><span>{items.length} project{items.length === 1 ? "" : "s"}</span></div><div className="strategyGrid">{items.map(renderCard)}</div></section>;

  return <main>
    <section className="dashboardHero"><div><p className="eyebrow">TRADING RESEARCH PLATFORM</p><h1>Research control center</h1><p className="lede">Live, protected research status across indicators, strategies, tools, trade review, datasets, validation work, and shared infrastructure.</p></div><form action="/auth/signout" method="post"><button className="secondaryButton" type="submit">Sign out</button></form></section>
    {queryError ? <section className="alertPanel"><strong>Dashboard query failed.</strong><span>{queryError.message}</span></section> : <>
      <section className="metricGrid" aria-label="Research summary"><article className="metricCard"><span>Registered projects</span><strong>{strategies.length}</strong><small>{states.length} with project-state tracking</small></article><article className="metricCard"><span>Active systems</span><strong>{activeCount}</strong><small>{researchCount} additional projects in research</small></article><article className="metricCard"><span>Current blockers</span><strong>{blockerCount}</strong><small>Across tracked project states</small></article><article className="metricCard"><span>Protected datasets</span><strong>{datasets.length}</strong><small>{datasets.filter((d) => d.is_frozen).length} frozen datasets</small></article></section>
      <section className="sectionHeader"><div><p className="eyebrow">PROJECT PORTFOLIO</p><h2>Research systems</h2></div><span className="securityBadge">Authenticated · Allowlisted · Read-only</span></section>
      {renderGroup("INDICATORS & STRATEGIES", "Indicators & strategies", "TradingView indicators, strategy research, validation, and model development.", indicatorStrategies, "portfolioIndicators")}
      {renderGroup("TOOLS", "Tools", "Shared research and execution-support systems that sit alongside the trading strategies.", tools, "portfolioTools")}
      {renderGroup("TRADE REVIEWS", "Trade reviews", "Executed-trade reconstruction, review, trade-health analysis, and trader-development research.", tradeReviews, "portfolioTradeReviews")}
    </>}
  </main>;
}
