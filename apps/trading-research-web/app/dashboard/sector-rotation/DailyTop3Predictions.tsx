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
const finishGroups=['Top 3','Middle','Bottom 3'] as const;
type FinishGroup=typeof finishGroups[number];
type AccuracyCount={completed:number;correct:number;incorrect:number;pending:number;tied:number};
export function predictionAccuracy(predictions:readonly DailyTop3Prediction[],results:readonly DailyTop3Result[],asOfDate:string){
 const empty=():AccuracyCount=>({completed:0,correct:0,incorrect:0,pending:0,tied:0});
 const overall=empty(),byStage:Record<PredictionStage,AccuracyCount>={overnight:empty(),premarket:empty(),open30:empty()};
 const emptyGroups=():Record<FinishGroup,AccuracyCount>=>({'Top 3':empty(),Middle:empty(),'Bottom 3':empty()});
 const byGroup=emptyGroups(),byStageGroup:Record<PredictionStage,Record<FinishGroup,AccuracyCount>>={overnight:emptyGroups(),premarket:emptyGroups(),open30:emptyGroups()};
 const resultsByDate=new Map(results.map(result=>[result.target_date,result]));
 const recorded=predictions.filter(p=>p.target_date<=asOfDate);
 const completedDates=new Set<string>();
 for(const p of recorded){
  const actual=resultsByDate.get(p.target_date)?.payload.ranks.find(row=>row.symbol===p.symbol);
  const completed=actual!==undefined&&Number.isInteger(actual.rank)&&actual.rank>=1&&actual.rank<=11;
  const likely=mostLikely(p);
  const bucket=completed?(actual.rank<=3?'Top 3':actual.rank<=8?'Middle':'Bottom 3'):null;
  for(const count of [overall,byStage[p.stage]]){
   if(!completed){count.pending++;continue;}
   count.completed++;
   if(likely.includes(bucket!))count.correct++;else count.incorrect++;
   if(likely.length>1)count.tied++;
  }
  for(const group of finishGroups.filter(group=>likely.includes(group))){
   for(const count of [byGroup[group],byStageGroup[p.stage][group]]){
    if(!completed){count.pending++;continue;}
    count.completed++;
    if(bucket===group)count.correct++;else count.incorrect++;
    if(likely.length>1)count.tied++;
   }
  }
  if(completed)completedDates.add(p.target_date);
 }
 const dates=recorded.map(p=>p.target_date).sort();
 return {overall,byStage,byGroup,byStageGroup,firstDate:dates[0]??null,lastDate:dates.at(-1)??null,completedDates:completedDates.size};
}
function AccuracyTable({rows,heading,caption}:{rows:readonly {label:string;count:AccuracyCount}[];heading:string;caption:string}){
 return <div className={styles.eventTableScroll}><table><caption>{caption}</caption><thead><tr><th scope="col">{heading}</th><th scope="col">Completed</th><th scope="col">Correct</th><th scope="col">Incorrect</th><th scope="col">Pending</th><th scope="col">Success Rate</th></tr></thead><tbody>{rows.map(({label,count})=><tr key={label}><th scope="row">{label}</th><td>{count.completed}</td><td>{count.correct}</td><td>{count.incorrect}</td><td>{count.pending}</td><td>{count.completed?`${(100*count.correct/count.completed).toFixed(1)}%`:'—'}</td></tr>)}</tbody></table></div>;
}
function PredictionStatistics({predictions,results,asOfDate,error}:{predictions:readonly DailyTop3Prediction[];results:readonly DailyTop3Result[];asOfDate:string;error?:string|null}){
 const stats=predictionAccuracy(predictions,results,asOfDate);
 const rows=[{label:'Overall',count:stats.overall},...(['overnight','premarket','open30'] as const).map(stage=>({label:{overnight:'Overnight Outlook',premarket:'Before Market Open',open30:'30 Minutes After Open'}[stage],count:stats.byStage[stage]}))];
 return <section className={`${styles.eventLog} ${styles.top3Section}`} aria-label="Prediction Statistics"><p className={styles.eyebrow}>ALL-HISTORY FORECAST SCORECARD</p><h2>Prediction Statistics</h2>
 {error?<p>Statistics are unavailable while prediction data cannot be loaded.</p>:<>
 <p className={styles.relativeMeta}>{stats.firstDate?`${stats.firstDate} through ${stats.lastDate} · ${stats.completedDates} ${stats.completedDates===1?'date':'dates'} with scored forecasts`:'No forecasts recorded yet.'} · Independent of Sessions and date filters.</p>
 <details className={styles.predictionStage}><summary className={styles.predictionStageTitle}><h3>Success By Prediction Time</h3></summary><AccuracyTable rows={rows} heading="Prediction Time" caption="Success = actual finishing group matches a highest-probability group"/></details>
 <details className={styles.predictionStage}><summary className={styles.predictionStageTitle}><h3>Success By Predicted Group</h3></summary>
 <AccuracyTable rows={finishGroups.map(group=>({label:group,count:stats.byGroup[group]}))} heading="Predicted Group" caption="Top 3, Middle, and Bottom 3 forecast accuracy"/>
 <p className={styles.relativeMeta}>Each group includes forecasts assigning it the highest probability. Success requires finishing in that exact group. Tied forecasts appear in each tied group, so group totals can exceed the overall total.</p></details>
 <details className={styles.predictionStage}><summary className={styles.predictionStageTitle}><h3>Group Success By Prediction Time</h3></summary><div className={styles.eventRules}>{(['overnight','premarket','open30'] as const).map(stage=><div key={stage}><h4>{STAGE_LABELS[stage]}</h4><AccuracyTable rows={finishGroups.map(group=>({label:group,count:stats.byStageGroup[stage][group]}))} heading="Predicted Group" caption={`${STAGE_LABELS[stage]} · Group accuracy`}/></div>)}</div></details>
 <details className={`${styles.eventRules} ${styles.notation}`}><summary>How Success Is Counted</summary><div className={styles.eventRules}><p>Each ETF, target date and forecast time is one prediction. Overall pools all three times; it counts correct forecasts divided by completed forecasts, rather than averaging their percentages. Overnight, before-open and after-open forecasts for the same ETF/day are scored separately.</p><p>Top 3 means ranks 1–3; Middle means ranks 4–8; Bottom 3 means ranks 9–11. A forecast is correct when the actual group matches a group with the highest recorded probability. Tied highest estimates accept any tied group; {stats.overall.tied} completed {stats.overall.tied===1?'forecast had':'forecasts had'} a tie. Missing closing ranks remain pending and do not reduce accuracy.</p><p>Includes all saved forecasts, including baseline-only estimates. This measures finishing-group accuracy, not trade profitability or probability calibration. Results update when verified closing data arrives; original forecasts stay fixed.</p></div></details>
 </>}
 </section>;
}
function Snapshot({rows,result}:{rows:readonly DailyTop3Prediction[];result?:DailyTop3Result}){
 const shared=sharedResearchPrefix(rows);
 const sameMetadata=rows.every(p=>p.recorded_at===rows[0].recorded_at&&p.data_as_of===rows[0].data_as_of&&p.methodology===rows[0].methodology);
 const metadata=(p:DailyTop3Prediction)=>`Recorded ${timestamp(p.recorded_at)} · Data through ${timestamp(p.data_as_of)} · ${p.methodology}`;
 return <>{sameMetadata&&<p className={styles.predictionMeta}>{metadata(rows[0])}</p>}<div className={styles.eventTableScroll}><table><caption>{STAGE_LABELS[rows[0].stage]} · Each ETF evaluated independently against all 11 sectors</caption><thead><tr><th scope="col">ETF</th><th scope="col">Top 3 chance</th><th scope="col">Middle chance</th><th scope="col">Bottom 3 chance</th><th scope="col">Confidence in estimate</th><th scope="col">Actual Rank</th><th scope="col">Return</th><th scope="col">Group Finish</th><th scope="col">Top 3 Finish</th></tr></thead><tbody>{TOP3_SYMBOLS.map(symbol=>{const p=rows.find(r=>r.symbol===symbol),actual=result?.payload.ranks.find(r=>r.symbol===symbol);return <tr key={symbol}><th scope="row">{symbol}</th>{!p?<td colSpan={4}>No forecast recorded for this ETF</td>:<><td>{p.top3}%</td><td>{p.middle}%</td><td>{p.bottom3}%</td><td>{p.confidence}{p.availability==='baseline_only'?' · Baseline only':''}</td></>}<td>{actual?`#${actual.rank}`:'Pending'}</td><td>{actual?`${actual.daily>0?'+':''}${actual.daily.toFixed(2)}%`:'Pending'}</td><td>{actual?actual.bucket:'Pending'}</td><td>{actual?(actual.rank<=3?'Yes':'No'):'Pending'}</td></tr>;})}</tbody></table></div>
 {rows.every(p=>p.availability==='baseline_only')&&<p className={styles.predictionMeta}>Historical baseline only: live inputs did not support a verified probability adjustment.</p>}
 {shared&&<details className={`${styles.eventRules} ${styles.predictionShared}`}><summary>Shared Research Context · All ETFs In This Forecast</summary><p className={styles.predictionReason}>{shared}</p></details>}
 {rows.map(p=>{const likely=mostLikely(p);return <article key={p.symbol} className={styles.winnerCard}><h5>{p.symbol} · {likely.join(' / ')}{likely.length>1?' (tied highest estimates)':' is the most likely finish'}</h5><ResearchNote text={p.reason.slice(shared.length).trim()}/>{!sameMetadata&&<p className={styles.predictionMeta}>{metadata(p)}</p>}<details className={styles.eventRules}><summary>Original Research &amp; Sources For {p.symbol}</summary><p className={styles.predictionReason}>{p.reason}</p><p className={styles.relativeMeta}>{metadata(p)} · Original forecast preserved</p>{p.sources.length>0&&<details className={styles.eventRules}><summary>Research sources for {p.symbol}</summary><ul>{p.sources.map((source,i)=><li key={`${source.url}-${i}`}>{safeUrl(source.url)?<a href={safeUrl(source.url)} target="_blank" rel="noreferrer">{source.label}</a>:source.label}{source.as_of?` · ${source.as_of}`:''}</li>)}</ul></details>}</details></article>;})}</>;
}
export default function DailyTop3Predictions({predictions,results,asOfDate,error}:{predictions:readonly DailyTop3Prediction[];results:readonly DailyTop3Result[];asOfDate:string;error?:string|null}){
 const currentDates=new Set(weekDisplayDates(asOfDate));
 const dates=[...new Set([...currentDates,...predictions.map(p=>p.target_date).filter(d=>d<=asOfDate)])].sort().reverse();
 const renderDay=(date:string,i:number)=>{const rows=predictions.filter(p=>p.target_date===date),result=results.find(r=>r.target_date===date),available=stages.filter(stage=>rows.some(p=>p.stage===stage));return <details key={date} className={`${styles.eventDay} ${i%2?styles.eventDayAlternate:''}`}><summary className={styles.winnerDaySummary}>{date} · {rows.length?result?'Results available':'Awaiting results':'No forecast recorded'}</summary>{!rows.length?<p>No forecast was recorded for this date. Historical predictions are not backfilled.</p>:<>{!result&&<p role="status">Awaiting this session’s verified closing results.</p>}{result&&<p className={styles.relativeMeta}>Closing results recorded {timestamp(result.recorded_at)}. {result.payload.ranking_rule}</p>}{available.map((stage,index)=><details key={stage} className={styles.predictionStage}><summary className={styles.predictionStageTitle}><h3>{index===0?'Current Prediction · ':''}{STAGE_LABELS[stage]}</h3></summary><Snapshot rows={rows.filter(p=>p.stage===stage)} result={result}/></details>)}</>}</details>;};
 return <><PredictionStatistics predictions={predictions} results={results} asOfDate={asOfDate} error={error}/><section id="predicting-daily-top-3-sectors" className={`${styles.eventLog} ${styles.top3Section}`} aria-label="Predicting Daily Top 3 Sectors"><p className={styles.eyebrow}>RECORDED FORECASTS &amp; CLOSING RESULTS</p><h2>Predicting Daily Top 3 Sectors <span className={styles.swingBeta}>(Beta)</span></h2><p>XLE, XLV and XLK each compete against all 11 sector ETFs. Top 3 = ranks 1–3; Middle = 4–8; Bottom 3 = 9–11, ranked by close versus the previous session’s close. Negative returns can still finish Top 3.</p><p className={styles.relativeMeta}>Research checks: 8:25 AM CT before open and 9:00 AM CT after 30 minutes, on market weekdays. Each snapshot remains separate. Results and analysis append after the verified overnight price refresh, rather than live at the closing bell. Independent of heatmap filters. Current week listed first; Monday also includes the previous Friday. All dates start collapsed and remain available to expand.</p><p className={styles.relativeMeta}>Probabilities are uncalibrated analyst judgments, not measured model accuracy. Confidence describes evidence quality. One day cannot validate a probability; a Top 3 finish does not establish a profitable trade.</p>
 {error?<p role="alert">{error}</p>:<>{dates.filter(date=>currentDates.has(date)).map(renderDay)}{dates.some(date=>!currentDates.has(date))&&<details className={styles.eventRules}><summary>Older daily predictions ({dates.filter(date=>!currentDates.has(date)).length})</summary>{dates.filter(date=>!currentDates.has(date)).map((date,i)=>renderDay(date,i+currentDates.size))}</details>}</>}
 </section></>;
}
