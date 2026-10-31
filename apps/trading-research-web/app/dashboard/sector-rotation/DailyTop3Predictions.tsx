import {TOP3_SYMBOLS,STAGE_LABELS,mostLikely,type DailyTop3Prediction,type DailyTop3Result,type PredictionStage} from './top-three-types';
import styles from './tracker.module.css';
import {weekDisplayDates} from './week-display';
const timestamp=(s:string)=>new Intl.DateTimeFormat('en-US',{dateStyle:'medium',timeStyle:'short',timeZone:'America/Chicago'}).format(new Date(s))+' CT';
const stages:PredictionStage[]=['open30','premarket','overnight'];
const safeUrl=(url:string)=>{try{const parsed=new URL(url);return parsed.protocol==='https:'?parsed.href:undefined;}catch{return undefined;}};
// Move only verbatim, complete shared sentences; never infer or rewrite research.
export function sharedResearchPrefix(rows:readonly DailyTop3Prediction[]):string {
 if(rows.length<2)return '';
 let prefix=rows[0].reason;
 for(const row of rows.slice(1)){
  let i=0;while(i<prefix.length&&i<row.reason.length&&prefix[i]===row.reason[i])i++;
  prefix=prefix.slice(0,i);
 }
 if(prefix.length<160)return '';
 if(rows.every(row=>row.reason===prefix))return prefix;
 const ends=[...prefix.matchAll(/[.!?](?=\s)/g)];
 const end=ends.at(-1)?.index;
 return end!==undefined&&end>=120?prefix.slice(0,end+1):'';
}
function ResearchNote({text}:{text:string}){
 if(!text)return null;
 if(text.length<=520)return <p className={styles.predictionReason}>{text}</p>;
 // Preview complete sentences when possible; the full text remains directly expandable.
 const boundary=[...text.slice(0,420).matchAll(/[.!?](?=\s)/g)].at(-1)?.index;
 const preview=boundary!==undefined?text.slice(0,boundary+1):text.slice(0,300).replace(/\s+\S*$/,'')+'…';
 return <><p className={styles.predictionReason}>{preview}</p><details className={styles.eventRules}><summary>More ETF Analysis</summary><p className={styles.predictionReason}>{text}</p></details></>;
}
function Snapshot({rows,result}:{rows:readonly DailyTop3Prediction[];result?:DailyTop3Result}){
 const shared=sharedResearchPrefix(rows);
 const sameMetadata=rows.every(p=>p.recorded_at===rows[0].recorded_at&&p.data_as_of===rows[0].data_as_of&&p.methodology===rows[0].methodology);
 const metadata=(p:DailyTop3Prediction)=>`Recorded ${timestamp(p.recorded_at)} · Data through ${timestamp(p.data_as_of)} · ${p.methodology}`;
 return <>{sameMetadata&&<p className={styles.predictionMeta}>{metadata(rows[0])}</p>}<div className={styles.eventTableScroll}><table><caption>{STAGE_LABELS[rows[0].stage]} · Each ETF evaluated independently against all 11 sectors</caption><thead><tr><th scope="col">ETF</th><th scope="col">Top 3 chance</th><th scope="col">Middle chance</th><th scope="col">Bottom 3 chance</th><th scope="col">Confidence in estimate</th><th scope="col">Actual rank / return</th><th scope="col">Actual finish</th></tr></thead><tbody>{TOP3_SYMBOLS.map(symbol=>{const p=rows.find(r=>r.symbol===symbol),actual=result?.payload.ranks.find(r=>r.symbol===symbol);return <tr key={symbol}><th scope="row">{symbol}</th>{!p?<td colSpan={4}>No forecast recorded for this ETF</td>:<><td>{p.top3}%</td><td>{p.middle}%</td><td>{p.bottom3}%</td><td>{p.confidence}{p.availability==='baseline_only'?' · Baseline only':''}</td></>}<td>{actual?`#${actual.rank} · ${actual.daily>0?'+':''}${actual.daily.toFixed(2)}%`:'Pending'}</td><td>{actual?`${actual.bucket} · Top 3: ${actual.rank<=3?'Yes':'No'}`:'Pending verified closing data'}</td></tr>;})}</tbody></table></div>
 {rows.every(p=>p.availability==='baseline_only')&&<p className={styles.predictionMeta}>Historical baseline only: live inputs did not support a verified probability adjustment.</p>}
 {shared&&<details className={`${styles.eventRules} ${styles.predictionShared}`}><summary>Shared Research Context · All ETFs In This Forecast</summary><p className={styles.predictionReason}>{shared}</p></details>}
 {rows.map(p=>{const likely=mostLikely(p);return <article key={p.symbol} className={styles.winnerCard}><h5>{p.symbol} · {likely.join(' / ')}{likely.length>1?' (tied highest estimates)':' is the most likely finish'}</h5><ResearchNote text={p.reason.slice(shared.length).trim()}/>{!sameMetadata&&<p className={styles.predictionMeta}>{metadata(p)}</p>}<details className={styles.eventRules}><summary>Original Research &amp; Sources For {p.symbol}</summary><p className={styles.predictionReason}>{p.reason}</p><p className={styles.relativeMeta}>{metadata(p)} · Original forecast preserved</p>{p.sources.length>0&&<details className={styles.eventRules}><summary>Research sources for {p.symbol}</summary><ul>{p.sources.map((source,i)=><li key={`${source.url}-${i}`}>{safeUrl(source.url)?<a href={safeUrl(source.url)} target="_blank" rel="noreferrer">{source.label}</a>:source.label}{source.as_of?` · ${source.as_of}`:''}</li>)}</ul></details>}</details></article>;})}</>;
}
export default function DailyTop3Predictions({predictions,results,asOfDate,error}:{predictions:readonly DailyTop3Prediction[];results:readonly DailyTop3Result[];asOfDate:string;error?:string|null}){
 const currentDates=new Set(weekDisplayDates(asOfDate));
 const dates=[...new Set([...currentDates,...predictions.map(p=>p.target_date).filter(d=>d<=asOfDate)])].sort().reverse();
 const renderDay=(date:string,i:number)=>{const rows=predictions.filter(p=>p.target_date===date),result=results.find(r=>r.target_date===date),available=stages.filter(stage=>rows.some(p=>p.stage===stage));return <details key={date} className={`${styles.eventDay} ${i%2?styles.eventDayAlternate:''}`}><summary className={styles.winnerDaySummary}>{date} · {rows.length?result?'Results available':'Awaiting results':'No forecast recorded'}</summary>{!rows.length?<p>No forecast was recorded for this date. Historical predictions are not backfilled.</p>:<>{!result&&<p role="status">Awaiting this session’s verified closing results.</p>}{result&&<p className={styles.relativeMeta}>Closing results recorded {timestamp(result.recorded_at)}. {result.payload.ranking_rule}</p>}{available.map((stage,index)=><details key={stage} className={styles.predictionStage} open={index===0}><summary className={styles.predictionStageTitle}><h3>{index===0?'Current Prediction · ':''}{STAGE_LABELS[stage]}</h3></summary><Snapshot rows={rows.filter(p=>p.stage===stage)} result={result}/></details>)}</>}</details>;};
 return <section id="predicting-daily-top-3-sectors" className={`${styles.eventLog} ${styles.top3Section}`} aria-label="Predicting Daily Top 3 Sectors"><p className={styles.eyebrow}>RECORDED FORECASTS &amp; CLOSING RESULTS</p><h2>Predicting Daily Top 3 Sectors <span className={styles.swingBeta}>(Beta)</span></h2><p>XLE, XLV and XLK each compete against all 11 sector ETFs. Top 3 = ranks 1–3; Middle = 4–8; Bottom 3 = 9–11, ranked by close versus the previous session’s close. Negative returns can still finish Top 3.</p><p className={styles.relativeMeta}>Research checks: 8:25 AM CT before open and 9:00 AM CT after 30 minutes, on market weekdays. Each snapshot remains separate. Results and analysis append after the verified overnight price refresh, rather than live at the closing bell. Independent of heatmap filters. Current week listed first; Monday also includes the previous Friday. All dates start collapsed and remain available to expand.</p><p className={styles.relativeMeta}>Probabilities are uncalibrated analyst judgments, not measured model accuracy. Confidence describes evidence quality. One day cannot validate a probability; a Top 3 finish does not establish a profitable trade.</p>
 {error?<p role="alert">{error}</p>:<>{dates.filter(date=>currentDates.has(date)).map(renderDay)}{dates.some(date=>!currentDates.has(date))&&<details className={styles.eventRules}><summary>Older daily predictions ({dates.filter(date=>!currentDates.has(date)).length})</summary>{dates.filter(date=>!currentDates.has(date)).map((date,i)=>renderDay(date,i+currentDates.size))}</details>}</>}
 </section>;
}
