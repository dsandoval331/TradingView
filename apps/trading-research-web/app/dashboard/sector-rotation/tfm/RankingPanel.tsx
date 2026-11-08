'use client';
import {useState} from 'react';
import {createClient} from '../../../../lib/supabase/client';
import type {League, LeagueMatch} from './LeaguePanel';
import styles from './tfm.module.css';
export type RankCandidate={setup_key:string;symbol:string;rank:number|null;score:number|null;close_points:number|null;red_points:number|null;below_points:number|null;distance_pct:number|null;lower_third:boolean|null;status:string;reason:string|null;reference_bars:{trade_date:string;response_sha256:string}[]};
export type RankInstance=RankCandidate&{classification:string;outcome:{hit:boolean;gap_through:boolean;mfe_pct:number;mae_pct:number;close_return_pct:number}|null};
export type RankReview={n:number;k:number;complete:boolean;top_rate:number|null;top_hit_rate:number|null;pool_rate:number|null;lift:number|null;ndcg:number|null;median_mfe:number|null;median_mae:number|null;gaps:number;instances:RankInstance[];groups:Record<string,{n:number;wins:number;rate:number|null}>};
export type RankSnapshot={snapshot_id:string;model_version:string;scope:string;monday:string;target_date:string;frozen_at:string;payload:{n:number;k:number;complete:boolean;model_sha256:string;source_sha256:string;universe_sha256:string;candidates:RankCandidate[]};review:RankReview|null};
export type RankGame={snapshots:RankSnapshot[];xp:{monday:string;kind:string;points:number}[];reflections:{monday:string;note:string}[];error:string|null};
const num=(v:number|null|undefined,suffix='')=>v==null?'—':`${v.toFixed(2)}${suffix}`;
const ct=(s:string)=>new Intl.DateTimeFormat('en-US',{timeZone:'America/Chicago',dateStyle:'medium',timeStyle:'short'}).format(new Date(s))+' CT';
function FrozenWeek({snapshot:s, match}:{snapshot:RankSnapshot; match?:LeagueMatch}){
 const [selected,setSelected]=useState<'champion'|'challenger'>('champion');
 const challenger = match !== undefined && selected==='challenger';
 const paired = new Map(match?.picks.map(pick=>[pick.setup_key,pick]));
 const candidates = challenger
  ? [...s.payload.candidates].sort((a,b)=>(paired.get(a.setup_key)?.challenger_rank??Infinity)-(paired.get(b.setup_key)?.challenger_rank??Infinity))
  : s.payload.candidates;
 const outcomes = new Map(s.review?.instances.map(instance=>[instance.setup_key,instance]));
 const [reveal,setReveal]=useState(false);const r=s.review;
 return <section><h3>Monday {s.monday}{s.target_date!==s.monday?' · holiday-Tuesday target '+s.target_date:''}</h3><p>Frozen {ct(s.frozen_at)} · {s.model_version} · {s.payload.n} qualifying instances · Top {s.payload.k}. {s.payload.complete?'Complete frozen pool.':'Incomplete ranking: unrankable candidates retained; no final score or XP.'}</p>
 <div className={styles.metrics}><div><span>Top-{s.payload.k} Combined Success Rate</span><strong>{num(r?.top_rate,'%')}</strong><small>Pattern hit rate: {num(r?.top_hit_rate,'%')}</small></div><div><span>Qualifying-pool baseline</span><strong>{num(r?.pool_rate,'%')}</strong><small>All {s.payload.n} frozen qualifiers</small></div><div><span>Selection lift</span><strong>{num(r?.lift,' pp')}</strong><small>Top group minus full pool</small></div><div><span>Ranking quality</span><strong>{num(r?.ndcg,' / 100')}</strong><small>NDCG@{s.payload.k} · no successful ideal = N/A</small></div></div>
 <p>{r?`Verified full-pool review · median MFE ${num(r.median_mfe,'%')} / MAE ${num(r.median_mae,'%')} · ${r.gaps} gap-through hits.`:'Review pending verified target-session data. No missing result is treated as a loss.'}</p>
 {r&&<><button type="button" aria-pressed={reveal} onClick={()=>setReveal(!reveal)}>{reveal?'Hide instance outcomes':'Reveal instance outcomes'}</button><p className={styles.footnote}>Top / middle / bottom: {Object.entries(r.groups).map(([g,v])=>`${g} ${v.wins}/${v.n} (${num(v.rate,'%')})`).join(' · ')}. Top and bottom use up to five nonoverlapping ranks.</p></>}
 <div className={styles.rankingTabs} role="group" aria-label="Ranking system">
  <button type="button" aria-pressed={!challenger} onClick={()=>setSelected('champion')}>Champion</button>
  <button type="button" aria-pressed={challenger} disabled={!match} onClick={()=>setSelected('challenger')}>Room to Target</button>
 </div>
 {!match&&<p className={styles.footnote}>Room to Target ranks are unavailable for this snapshot.</p>}
 <div className={styles.scroll}><table>
  <caption className={styles.srOnly}>{challenger?'Room to Target':'Champion'} frozen rankings</caption>
  <thead><tr><th>Rank</th><th>Symbol</th><th>{challenger?'Champion rank':'Room to Target rank'}</th>
   <th>{challenger?'Room to stop':'Candidate score'}</th>{!challenger&&<th>Why this score</th>}
   <th>Friday close to low</th><th>Outcome</th><th>MFE / MAE</th><th>MFE/MAE ratio</th></tr></thead>
  <tbody>{candidates.map(c=>{
   const pick=paired.get(c.setup_key);
   const outcome=outcomes.get(c.setup_key);
   return <tr key={c.setup_key}>
    <td>{(challenger?pick?.challenger_rank:c.rank)??'—'}</td><th scope="row">{c.symbol}</th>
    <td>{(challenger?c.rank:pick?.challenger_rank)??'—'}</td>
    <td>{challenger?num(pick?.room_to_stop,'×'):num(c.score,' / 100')}</td>
    {!challenger&&<td>{c.status==='RANKED'?`${num(c.close_points)} close position + ${c.red_points} red candle + ${c.below_points} below Thursday`:c.reason}<small>{c.lower_third?'Lower-third Friday close':''}</small></td>}
    <td>{num(c.distance_pct,'%')}</td>
    <td>{reveal&&outcome?`${outcome.classification}${outcome.outcome?.gap_through?' · gap through':''}`:r?'Hidden until revealed':'Pending review'}</td>
    <td>{reveal&&outcome?`${num(outcome.outcome?.mfe_pct,'%')} / ${num(outcome.outcome?.mae_pct,'%')}`:'—'}</td>
    <td>{reveal&&outcome?.outcome?(outcome.outcome.mae_pct>0?num(outcome.outcome.mfe_pct/outcome.outcome.mae_pct,':1'):outcome.outcome.mfe_pct>0?'∞':'—'):'—'}</td>
   </tr>;
  })}</tbody>
 </table></div>
 <details><summary>Frozen audit record</summary><p className={styles.source}>Model SHA-256 {s.payload.model_sha256}<br/>Universe SHA-256 {s.payload.universe_sha256}<br/>Source SHA-256 {s.payload.source_sha256}<br/>Snapshot {s.snapshot_id}</p><p>Scores are priorities, not win probabilities. Review uses the approved 0.5% / 2:1 alternate rules regardless of temporary display settings below. Excursions do not prove executable profit.</p></details></section>;
}
export default function RankingPanel({game,league}:{game?:RankGame;league?:League}){
 const [note,setNote]=useState(''),[message,setMessage]=useState(''),[saving,setSaving]=useState(false);
 const xp=game?.xp??[],snaps=game?.snapshots??[];
 const matches=new Map(league?.matches.map(match=>[match.champion_id,match]));
 const total=xp.reduce((s,x)=>s+x.points,0),level=total>=500?'Strategist':total>=250?'Researcher':total>=100?'Analyst':'Apprentice';
 const latest=snaps[0],week=latest?.monday,events=xp.filter(x=>x.monday===week),weekXP=events.reduce((s,x)=>s+x.points,0);
 const reflection=game?.reflections.find(x=>x.monday===week);
 const reviews=xp.filter(x=>x.kind==='review').length,clean=xp.filter(x=>x.kind==='integrity').length;
 const reviewed=snaps.filter(x=>x.review),monday=reviewed.filter(x=>x.target_date===x.monday),holiday=reviewed.filter(x=>x.target_date!==x.monday);
 const season=(list:RankSnapshot[])=>{const lift=list.filter(x=>x.review?.lift!=null);return `${list.length} verified weeks · mean weekly selection lift ${lift.length?num(lift.reduce((sum,x)=>sum+x.review!.lift!,0)/lift.length,' pp'):'—'} · ${list.reduce((sum,x)=>sum+x.payload.n,0)} qualifying instances`;};
 async function save(){if(!week)return;setSaving(true);setMessage('');try{const {error}=await createClient().rpc('tfm_save_reflection',{p_monday:week,p_note:note});if(error){setMessage('Could not save. A verified review is required; use 20–4,000 characters.');return;}setMessage('Reflection saved. Refresh to see your verified XP.');setNote('');}catch{setMessage('Could not save. Please retry.');}finally{setSaving(false);}}
 return <section className={styles.panel} aria-label="Friday rankings and research rewards"><h2>Friday rankings &amp; Research XP</h2><p>Approved v1 · 70 close-position points + 20 red-Friday points + 10 below-Thursday-close points. Separate frozen ranking pools for each page; Research XP is shared across all three pools.</p>
 {game?.error&&<p role="alert" className={styles.warning}>{game.error}</p>}
 <div className={styles.metrics}><div><span>Research XP</span><strong>{total}</strong><small>{level} · process rewards, separate from ranking quality</small></div><div><span>{week?'Week of '+week:'Weekly mission'}</span><strong>{weekXP} / 30 XP</strong><small>Freeze 10 · verified review 10 · integrity 5 · saved reflection 5</small></div><div><span>Milestones</span><strong>{reviews} reviews</strong><small>{xp.some(x=>x.kind==='freeze')?'🏅 First Frozen Week':'First Frozen Week · locked'}{reviews>=4?' · 🏅 Four Complete Reviews':''}{clean>=4?' · 🏅 Data Integrity':''}</small></div><div><span>Level progress</span><strong>{total>=500?'Strategist':`${total} / ${total>=250?500:total>=100?250:100}`}</strong><small>Apprentice 0 · Analyst 100 · Researcher 250 · Strategist 500</small></div></div>
 <p className={styles.footnote}>No historical XP or loss penalties. Awards require complete evidence across all three scopes; retries cannot duplicate rewards. Outages and holidays do not consume a streak. Consistency evaluation begins after at least 12 prospective weeks.</p>
 <p>Monday season: {season(monday)}.</p>{holiday.length>0&&<p>Holiday-Tuesday season, separate: {season(holiday)}.</p>}
 {latest?<FrozenWeek key={latest.snapshot_id} snapshot={latest} match={matches.get(latest.snapshot_id)}/>:<p className={styles.empty}>Rankings not available yet. First eligible target: Monday, November 9, 2026. Verified Thursday/Friday data must be frozen before the target session opens. Past results are not assigned retrospective live ranks.</p>}
 {latest&&<div><h3>Weekly mission</h3><p>{['freeze','review','integrity','reflection'].map(k=>`${events.some(e=>e.kind===k)?'✓':'○'} ${k}`).join(' · ')}</p>{reflection?<p>Saved reflection: {reflection.note}</p>:<><label htmlFor="tfm-reflection">What worked, what failed, and what will you test next?</label><textarea id="tfm-reflection" value={note} minLength={20} maxLength={4000} rows={3} onChange={e=>setNote(e.target.value)} disabled={!events.some(e=>e.kind==='review')||saving}/><button type="button" onClick={save} disabled={!events.some(e=>e.kind==='review')||saving||note.trim().length<20}>{saving?'Saving…':'Save reflection · 5 XP'}</button></>}<p role="status">{message}</p></div>}
 {snaps.length>1&&<details><summary>Previous frozen weeks · {snaps.length-1}</summary>{snaps.slice(1).map(s=><details key={s.snapshot_id}><summary>Monday {s.monday}</summary><FrozenWeek snapshot={s} match={matches.get(s.snapshot_id)}/></details>)}</details>}
 <details><summary>Strategy documentation &amp; change policy</summary><p><a href="https://chatgpt.com/library?file_id=libfile_7757730a1c908191a4b5838df1510418&amp;account_id=personal" target="_blank" rel="noreferrer">Strategy specification and change log</a>. Rule changes require approval, a new version and a future effective week. Existing scores and reviews remain frozen. Challenger models and additional badges are future extensions.</p></details></section>;
}
