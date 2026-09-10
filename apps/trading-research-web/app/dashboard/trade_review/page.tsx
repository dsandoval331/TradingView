import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "../../lib/supabase/server";
import styles from "./trade-review.module.css";

export const dynamic = "force-dynamic";

type Trade = { trade_review_id:string; trade_number:number|null; trade_date:string; symbol:string; strategy_version:string; direction:string; signal_grade:string|null; entry_time:string|null; exit_time:string|null; entry_price:number|null; exit_price:number|null; realized_pnl_pct:number|null; strategy_outcome:string|null; trader_outcome:string|null; holding_seconds:number|null; review_status:string; key_lesson:string|null; executive_summary:string|null; metadata_json:Record<string,unknown> };
type Finding = { finding_id:string; trade_review_id:string; category:string; title:string; finding:string; evidence_state:string; polarity:string|null; research_status:string; tags:string[] };
type Profile = { profile_item_id:string; name:string; category:string; polarity:string; evidence_state:string; established:boolean; active:boolean; description:string|null; corrective_principle:string|null; supporting_trade_count:number; first_observed_at:string; last_updated_at:string; metadata_json:Record<string,unknown> };
type Evidence = { profile_evidence_id:string; profile_item_id:string; trade_review_id:string|null; evidence_direction:string; evidence_note:string; evidence_weight:number|null };

const pct=(v:number|null|undefined,d=3)=>v==null?"—":`${v>0?"+":""}${Number(v).toFixed(d)}%`;
const pretty=(v:string|null|undefined)=>v?String(v).replaceAll("_"," ").toLowerCase().replace(/\b\w/g,c=>c.toUpperCase()):"—";
const duration=(s:number|null)=>s==null?"—":s<3600?`${Math.round(s/60)}m`:`${Math.floor(s/3600)}h ${Math.round((s%3600)/60)}m`;
const ct=(v:string|null)=>v?new Intl.DateTimeFormat("en-US",{hour:"numeric",minute:"2-digit",timeZone:"America/Chicago",timeZoneName:"short"}).format(new Date(v)):"—";
const numMeta=(t:Trade,key:string)=>typeof t.metadata_json?.[key]==="number"?Number(t.metadata_json[key]):null;

export default async function TradeReviewDashboard(){
 const supabase=await createClient();
 const {data:claimsData,error:claimsError}=await supabase.auth.getClaims();
 if(claimsError||!claimsData?.claims) redirect("/login");
 const {data:allowed,error:accessError}=await supabase.rpc("is_trading_research_web_user");
 if(accessError||allowed!==true) redirect("/unauthorized");
 const [tr,fr,pr,er]=await Promise.all([
  supabase.from("trade_reviews").select("trade_review_id,trade_number,trade_date,symbol,strategy_version,direction,signal_grade,entry_time,exit_time,entry_price,exit_price,realized_pnl_pct,strategy_outcome,trader_outcome,holding_seconds,review_status,key_lesson,executive_summary,metadata_json").order("trade_number",{ascending:true}),
  supabase.from("trade_review_findings").select("finding_id,trade_review_id,category,title,finding,evidence_state,polarity,research_status,tags").order("created_at",{ascending:false}),
  supabase.from("trader_profile_items").select("profile_item_id,name,category,polarity,evidence_state,established,active,description,corrective_principle,supporting_trade_count,first_observed_at,last_updated_at,metadata_json").eq("active",true).order("supporting_trade_count",{ascending:false}),
  supabase.from("trader_profile_evidence").select("profile_evidence_id,profile_item_id,trade_review_id,evidence_direction,evidence_note,evidence_weight")
 ]);
 const error=tr.error||fr.error||pr.error||er.error;
 const trades=(tr.data??[]) as Trade[], findings=(fr.data??[]) as Finding[], profiles=(pr.data??[]) as Profile[], evidence=(er.data??[]) as Evidence[];
 const complete=trades.filter(t=>t.review_status==="complete"), wins=complete.filter(t=>(t.realized_pnl_pct??0)>0), losses=complete.filter(t=>(t.realized_pnl_pct??0)<0);
 const pnls=complete.map(t=>Number(t.realized_pnl_pct??0)), total=pnls.reduce((a,b)=>a+b,0), avg=pnls.length?total/pnls.length:0;
 const avgWin=wins.length?wins.reduce((a,t)=>a+Number(t.realized_pnl_pct),0)/wins.length:null, avgLoss=losses.length?losses.reduce((a,t)=>a+Number(t.realized_pnl_pct),0)/losses.length:null;
 const grossWin=wins.reduce((a,t)=>a+Number(t.realized_pnl_pct),0), grossLoss=Math.abs(losses.reduce((a,t)=>a+Number(t.realized_pnl_pct),0));
 const profitFactor=grossLoss>0?grossWin/grossLoss:null;
 const held=complete.filter(t=>t.holding_seconds!=null), avgHold=held.length?held.reduce((a,t)=>a+(t.holding_seconds??0),0)/held.length:null;
 let cumulative=0; const curve=complete.map(t=>({t,value:(cumulative+=Number(t.realized_pnl_pct??0))}));
 const min=Math.min(0,...curve.map(x=>x.value)), max=Math.max(0,...curve.map(x=>x.value)), span=Math.max(.01,max-min);
 const sessions=Object.entries(complete.reduce((m,t)=>{(m[t.trade_date]??=[]).push(t);return m;},{} as Record<string,Trade[]>)).sort(([a],[b])=>b.localeCompare(a));
 const strengths=profiles.filter(p=>p.polarity==="strength"), priorities=profiles.filter(p=>p.polarity!=="strength");
 const tradeById=new Map(trades.map(t=>[t.trade_review_id,t]));
 const evidenceTrades=(p:Profile)=>evidence.filter(e=>e.profile_item_id===p.profile_item_id&&e.trade_review_id).map(e=>tradeById.get(e.trade_review_id!)).filter(Boolean) as Trade[];
 const gradeGroups=Object.entries(complete.filter(t=>t.signal_grade).reduce((m,t)=>{(m[t.signal_grade!]??=[]).push(t);return m;},{} as Record<string,Trade[]>));
 const winnerHold=wins.filter(t=>t.holding_seconds!=null), loserHold=losses.filter(t=>t.holding_seconds!=null);
 const avgSecs=(x:Trade[])=>x.length?x.reduce((a,t)=>a+(t.holding_seconds??0),0)/x.length:null;
 return <main className={styles.tradeTheme}>
  <section className={`projectHero ${styles.hero}`}><div><Link className="backLink" href="/dashboard">← Platform Control Center</Link><p className={`eyebrow ${styles.accent}`}>TRADE REVIEWS · TRADER DEVELOPMENT</p><h1>Trade Review & Trader Development</h1><p className="lede">Trade → Evidence → Finding → Pattern → Corrective Action → Measurement → Improvement</p><p className="sectionDescription">Read-only operational view · Percentage P&amp;L is canonical</p></div><span className="securityBadge">Authenticated · Allowlisted · Read-only</span></section>
  {error?<section className="alertPanel"><strong>Trade Review query failed.</strong><span>{error.message}</span></section>:<>
  <nav className={`projectNav ${styles.nav}`} aria-label="Trade Review sections"><a href="#overview">Overview</a><a href="#performance">Performance</a><a href="#log">Trade Log</a><a href="#profile">Trader Profile</a><a href="#sessions">Sessions</a><a href="#analytics">Analytics</a><a href="#findings">Findings</a></nav>
  <section id="overview" className="metricGrid">
   <article className="metricCard"><span>Reviewed Trades</span><strong>{complete.length}</strong><small>Completed sample size</small></article>
   <article className="metricCard"><span>Win Rate</span><strong>{complete.length?(wins.length/complete.length*100).toFixed(1):"—"}%</strong><small>{wins.length} wins · {losses.length} losses</small></article>
   <article className="metricCard"><span>Cumulative P&amp;L</span><strong className={total>=0?styles.positive:styles.negative}>{pct(total)}</strong><small>Reviewed trades · percentage return</small></article>
   <article className="metricCard"><span>Average P&amp;L</span><strong>{pct(avg)}</strong><small>Per completed review</small></article>
   <article className="metricCard"><span>Average Winner</span><strong className={styles.positive}>{pct(avgWin)}</strong><small>{wins.length} winning trades</small></article>
   <article className="metricCard"><span>Average Loser</span><strong className={styles.negative}>{pct(avgLoss)}</strong><small>{losses.length} losing trades</small></article>
   <article className="metricCard"><span>Best / Worst</span><strong className="metricText">{pnls.length?pct(Math.max(...pnls)):"—"} / {pnls.length?pct(Math.min(...pnls)):"—"}</strong><small>Observed sample range</small></article>
   <article className="metricCard"><span>Profit Factor</span><strong>{profitFactor==null?"—":profitFactor.toFixed(2)}</strong><small>{complete.length<20?"Small sample — descriptive only":"Gross wins ÷ gross losses"}</small></article>
  </section>
  <section className={styles.sampleNote}><strong>PRELIMINARY DATA · SAMPLE SIZE: {complete.length} REVIEWED TRADES</strong><span>Metrics and patterns are descriptive observations, not statistically established conclusions.</span></section>

  <section className="projectSection" id="performance"><div className="sectionHeader"><div><p className={`eyebrow ${styles.accent}`}>PERFORMANCE</p><h2>Cumulative reviewed-trade P&amp;L</h2></div><span>{pct(total)} total</span></div>
   <article className={`detailPanel ${styles.chartPanel}`}><div className={styles.chart} aria-label="Cumulative reviewed trade P&L chart">{curve.map((x,i)=>{const h=Math.max(4,Math.abs(x.value)/span*150); return <Link title={`#${x.t.trade_number} ${x.t.symbol}: ${pct(x.value)}`} href={`/dashboard/trade_review/${x.t.trade_review_id}`} className={`${styles.bar} ${x.value>=0?styles.barPositive:styles.barNegative}`} style={{height:h}} key={x.t.trade_review_id}><span>{x.t.symbol}</span><small>{pct(x.value,2)}</small></Link>})}</div><p className="sectionDescription">Each bar is cumulative realized percentage P&amp;L after that reviewed trade. Select a trade for its full review.</p></article>
  </section>

  <section className="projectSection" id="log"><div className="sectionHeader"><div><p className={`eyebrow ${styles.accent}`}>TRADE LOG</p><h2>Reviewed-trade ledger</h2></div><span>{complete.length} completed</span></div>
   <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>#</th><th>Date</th><th>Symbol</th><th>Setup</th><th>Direction</th><th>Entry</th><th>Hold</th><th>Strategy Outcome</th><th>Trader Outcome</th><th>P&amp;L</th><th>Lesson</th></tr></thead><tbody>{complete.map(t=><tr key={t.trade_review_id}><td><Link href={`/dashboard/trade_review/${t.trade_review_id}`}>#{String(t.trade_number??"").padStart(3,"0")}</Link></td><td>{t.trade_date}</td><td><Link href={`/dashboard/trade_review/${t.trade_review_id}`}><strong>{t.symbol}</strong></Link></td><td>{t.signal_grade??"—"}</td><td>{pretty(t.direction)}</td><td>{ct(t.entry_time)}</td><td>{duration(t.holding_seconds)}</td><td className={styles.longCell}>{t.strategy_outcome??"—"}</td><td className={styles.longCell}>{t.trader_outcome??"—"}</td><td className={(t.realized_pnl_pct??0)>=0?styles.positive:styles.negative}><strong>{pct(t.realized_pnl_pct)}</strong></td><td className={styles.longCell}>{t.key_lesson??"—"}</td></tr>)}</tbody></table></div>
  </section>

  <section className="projectSection" id="profile"><div className="sectionHeader"><div><p className={`eyebrow ${styles.accent}`}>PRELIMINARY TRADER PROFILE</p><h2>Evidence-backed development profile</h2></div><span>Sample Size: {complete.length} reviewed trades</span></div>
   <div className="statusPlanGrid"><div><h3>Top Strengths</h3><div className="stackList">{strengths.slice(0,3).map(p=><article className={`detailPanel ${styles.profileCard}`} key={p.profile_item_id}><div className="listTop"><strong>{p.name}</strong><span className="statusPill">{pretty(p.evidence_state)}</span></div><p>{p.description}</p><small>{p.supporting_trade_count} supporting trade{p.supporting_trade_count===1?"":"s"}: {evidenceTrades(p).map(t=>`#${t.trade_number} ${t.symbol}`).join(", ")||"Evidence not linked to a trade"}</small>{p.corrective_principle&&<p className={styles.principle}>{p.corrective_principle}</p>}</article>)}</div></div>
   <div><h3>Top Improvement Priorities</h3><div className="stackList">{priorities.slice(0,3).map(p=><article className={`detailPanel ${styles.profileCard}`} key={p.profile_item_id}><div className="listTop"><strong>{p.name}</strong><span className="statusPill">{pretty(p.evidence_state)}</span></div><p>{p.description}</p><small>{p.supporting_trade_count} supporting trade{p.supporting_trade_count===1?"":"s"}: {evidenceTrades(p).map(t=>`#${t.trade_number} ${t.symbol}`).join(", ")||"Evidence not linked to a trade"}</small>{p.corrective_principle&&<p className={styles.principle}>{p.corrective_principle}</p>}</article>)}</div></div></div>
   <details className={styles.allProfile}><summary>View all {profiles.length} active profile observations</summary><div className={styles.profileGrid}>{profiles.map(p=><article className="detailPanel" key={p.profile_item_id}><div className="listTop"><strong>{p.name}</strong><span className="statusPill">{pretty(p.evidence_state)}</span></div><small>{pretty(p.polarity)} · {p.supporting_trade_count} supporting trade{p.supporting_trade_count===1?"":"s"}</small><p>{p.description}</p>{p.corrective_principle&&<p className={styles.principle}>{p.corrective_principle}</p>}</article>)}</div></details>
  </section>

  <section className="projectSection" id="sessions"><div className="sectionHeader"><div><p className={`eyebrow ${styles.accent}`}>DAILY / SESSION REVIEW</p><h2>Trading-day outcomes</h2></div><span>{sessions.length} reviewed sessions</span></div><div className="stackList">{sessions.map(([date,ts])=>{let run=0,peak=-Infinity; ts.forEach(t=>{run+=Number(t.realized_pnl_pct??0);peak=Math.max(peak,run)}); const sw=ts.filter(t=>(t.realized_pnl_pct??0)>0).length; return <article className="detailPanel" key={date}><div className="listTop"><strong>{date}</strong><span className={(run>=0?styles.positive:styles.negative)}>{pct(run)}</span></div><div className={styles.sessionStats}><span>{ts.length} trades</span><span>{sw}W / {ts.length-sw}L</span><span>Peak: {pct(peak)}</span><span>Giveback: {pct(Math.min(0,run-peak))}</span><span>Grades: {ts.map(t=>t.signal_grade??"—").join(", ")}</span><span>Avg hold: {duration(Math.round(ts.filter(t=>t.holding_seconds!=null).reduce((a,t)=>a+(t.holding_seconds??0),0)/Math.max(1,ts.filter(t=>t.holding_seconds!=null).length)))}</span></div></article>})}</div></section>

  <section className="projectSection" id="analytics"><div className="sectionHeader"><div><p className={`eyebrow ${styles.accent}`}>TRADER DEVELOPMENT ANALYTICS</p><h2>Management & setup evidence</h2></div><span>Descriptive · small sample</span></div>
   <div className="statusPlanGrid"><article className="detailPanel"><span className="fieldLabel">Winner vs Loser Management</span><h3>Holding-time asymmetry</h3><dl className="detailGrid"><div><dt>Avg winner hold</dt><dd>{duration(avgSecs(winnerHold))}</dd></div><div><dt>Avg loser hold</dt><dd>{duration(avgSecs(loserHold))}</dd></div><div><dt>Avg winner</dt><dd>{pct(avgWin)}</dd></div><div><dt>Avg loser</dt><dd>{pct(avgLoss)}</dd></div></dl><p className="sectionDescription">Displayed as evidence for investigation; not declared a stable behavioral pattern.</p></article>
   <article className="detailPanel"><span className="fieldLabel">Setup Quality</span><h3>Performance by grade</h3>{gradeGroups.length?gradeGroups.map(([g,ts])=><div className={styles.gradeRow} key={g}><strong>{g}</strong><span>{ts.length} trade{ts.length===1?"":"s"}</span><span>{pct(ts.reduce((a,t)=>a+Number(t.realized_pnl_pct??0),0)/ts.length)}</span><span>{Math.round(ts.filter(t=>(t.realized_pnl_pct??0)>0).length/ts.length*100)}% win</span></div>):<p>No setup grades recorded.</p>}</article></div>
   <div className={styles.researchGrid}><article className="detailPanel"><strong>Profit Capture vs Extended Hold</strong><p>Research area prepared for MFE-at-time, +0.50% extension/retracement, VWAP, RSI, ADX, structure and Trade Health evidence as those measurements are persisted.</p></article><article className="detailPanel"><strong>Continuation vs Exhaustion</strong><p>Use findings to compare continued directional response against momentum retreat, failed continuation and VWAP recovery without promoting a small-sample hypothesis to a rule.</p></article><article className="detailPanel"><strong>RSI Extreme / Time of Day</strong><p>Prepared for opening-window buckets and RSI-extreme persistence versus retreat when those structured measurements become available.</p></article><article className="detailPanel"><strong>Small-Loss Acceptance / Recovery</strong><p>Profile evidence and trade findings surface risk expansion, recovery-exit opportunities and management migration as they are recorded.</p></article></div>
  </section>

  <section className="projectSection" id="findings"><div className="sectionHeader"><div><p className={`eyebrow ${styles.accent}`}>FINDINGS / LESSON LIBRARY</p><h2>Trade-generated evidence</h2></div><span>{findings.length} findings</span></div><div className={styles.findingsGrid}>{findings.map(f=>{const t=tradeById.get(f.trade_review_id); return <article className="detailPanel" key={f.finding_id}><div className="listTop"><strong>{f.title}</strong><span className="statusPill">{pretty(f.evidence_state)}</span></div><small>{pretty(f.category)}{t?` · #${t.trade_number} ${t.symbol}`:""}</small><p>{f.finding}</p>{t&&<Link className={styles.tradeLink} href={`/dashboard/trade_review/${t.trade_review_id}`}>Open trade review →</Link>}</article>})}</div></section>
  </>}
 </main>;
}