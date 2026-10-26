'use client';
import {useMemo,useState} from 'react';
import type {Group,Metric,Session} from './model';
import {emaPeriod,type ChartLine} from './chart-lines';
import {dailyEvents} from './events';
import styles from './tracker.module.css';
const labels:Record<Metric,string>={relative:'Relative to SPY',daily:'Daily return',rank:'Daily rank',rankChange:'Rank change'};
const valueLabel=(value:number,metric:Metric)=>`${metric==='rank'?'#':value>0?'+':''}${value.toFixed(2)}${metric==='daily'?'%':metric==='relative'?' pp':metric==='rankChange'?' places':''}`;
export default function EventLog({sessions,visibleSessions,groups,metric,line,singleStock=false,onSelect}:{sessions:readonly Session[];visibleSessions:readonly Session[];groups:readonly Group[];metric:Metric;line:ChartLine;singleStock?:boolean;onSelect:(symbol:string,date:string)=>void}){
 const history=useMemo(()=>dailyEvents(sessions,groups,metric,line),[sessions,groups,metric,line]);
 const visible=new Set(visibleSessions.map(s=>s.date));
 const days=history.filter(d=>visible.has(d.date)).reverse();
 const [expanded,setExpanded]=useState<string|null|undefined>(undefined);
 const openDate=expanded===null?null:days.some(d=>d.date===expanded)?expanded:days[0]?.date;
 const period=emaPeriod(line);
 const pick=(symbol:string,date:string)=><button className={styles.eventSymbol} onClick={()=>onSelect(symbol,date)} title={`Show ${symbol} on ${date}`}>{symbol}</button>;
 return <section className={styles.eventLog} aria-label="Event Log"><p className={styles.eyebrow}>DAILY OBSERVATIONS</p><h2>Event Log</h2>
  <p className={styles.relativeMeta}>Newest day first · Same dates as the heatmap · {labels[metric]} · {period?`${period} EMA`:'EMA events off'}. Expand a day to review its closing observations; select a symbol to update the detail and charts.</p>
  <details className={styles.eventRules}><summary>Event definitions</summary><p>EMA events match visible superscripts and count consecutive trading sessions, including that day. The first available marker is labeled First day. A missing datapoint or a close at/above the EMA resets the count. None disables EMA events.</p><p>Long/Short are descriptive threshold labels. Daily return, relative return, and rank-change events compare against their same-direction arithmetic averages over the prior 60 sessions, excluding that day, with at least five matching-direction observations. A move must be strictly beyond its average. Daily rank uses the prior 60-session mean: a lower rank is Long context; a higher rank is Short context.</p><p>Current streaks include that day. Longest streaks are the longest observed in loaded history up to that day, including unfinished runs. Positive/negative values define green/red; rank uses better/worse than the universe midpoint. Flat or missing values break a run. Historical records never use later sessions. Rank movers require complete comparisons and include every tie.</p></details>
  {!days.length&&<p>No sessions match these dates.</p>}
  {days.map((day,i)=>{const open=day.date===openDate;return <article key={day.date} data-event-date={day.date} className={`${styles.eventDay} ${i%2?styles.eventDayAlternate:''}`}>
   <h3><button className={styles.eventDayToggle} aria-expanded={open} aria-controls={`events-${day.date}`} onClick={()=>setExpanded(open?null:day.date)}><time>{day.date}</time><span>{day.ema.length} EMA events · {day.averages.length} beyond average</span><span>{open?'−':'+'}</span></button></h3>
   {open&&<div id={`events-${day.date}`} className={styles.eventBody}>
    <div><h4>{period?`${period}E · Close below ${period} EMA`:'EMA events'}</h4>{!period?<p>Choose 20 EMA or 50 EMA in the heatmap to enable these events.</p>:day.ema.length?<ul>{day.ema.map(e=><li key={e.symbol}>{pick(e.symbol,day.date)} <strong>{e.days===1?'First day':`Day ${e.days} in a row`}</strong> · Close {e.close.toFixed(2)} &lt; EMA {e.ema.toFixed(2)}</li>)}</ul>:<p>No EMA superscripts for this day.</p>}</div>
    <div><h4>{labels[metric]} · Beyond average</h4>{day.averages.length?<ul>{day.averages.map(e=><li key={e.symbol}>{pick(e.symbol,day.date)} <strong className={e.side==='Long'?styles.averageUp:styles.averageDown}>{e.side} context</strong> · {valueLabel(e.value,metric)} {e.value>e.average?'above':'below'} prior average {valueLabel(e.average,metric)}</li>)}</ul>:<p>No qualifying average exceedances.</p>}{day.baselineUnavailable>0&&<p className={styles.relativeMeta}>{day.baselineUnavailable} {day.baselineUnavailable===1?'datapoint lacks':'datapoints lack'} sufficient valid history for the average comparison.</p>}</div>
    <div><h4>Green / red streaks at day end</h4><div className={styles.eventTableScroll}><table><caption>Consecutive sessions · Current run and longest observed through {day.date}</caption><thead><tr><th scope="col">Symbol</th><th scope="col">Current green</th><th scope="col">Current red</th><th scope="col">Longest green</th><th scope="col">Longest red</th></tr></thead><tbody>{day.streaks.map(s=><tr key={s.symbol}><th scope="row">{pick(s.symbol,day.date)}</th><td>{s.available?s.green:'—'}</td><td>{s.available?s.red:'—'}</td><td>{s.longestGreen||'—'}</td><td>{s.longestRed||'—'}</td></tr>)}</tbody></table></div></div>
    {!singleStock&&<div><h4>Biggest rank movers</h4><p><strong className={styles.averageUp}>Rank gain:</strong> {day.rankUp?<>{day.rankUp.symbols.map((s,i)=><span key={s}>{i?', ':''}{pick(s,day.date)}</span>)} · ↑{day.rankUp.change} places</>:'No positive rank change, or comparison unavailable.'}</p><p><strong className={styles.averageDown}>Rank drop:</strong> {day.rankDown?<>{day.rankDown.symbols.map((s,i)=><span key={s}>{i?', ':''}{pick(s,day.date)}</span>)} · ↓{Math.abs(day.rankDown.change)} places</>:'No negative rank change, or comparison unavailable.'}</p></div>}
   </div>}
  </article>;})}
 </section>;
}
