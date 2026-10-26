import type { RefObject, UIEventHandler } from 'react';
import { chartLayout } from './chart-layout';
import type { Metric, Session } from './model';
import { formatValue } from './model';
import { directionalMoveStats } from './normal-move';
import styles from './tracker.module.css';
const titles:Record<Metric,string>={relative:'Relative daily performance',daily:'Daily return',rank:'Daily rank',rankChange:'Rank change'};
const units:Record<Metric,string>={relative:'Sector return minus SPY · percentage points',daily:'Close-to-close price return · %',rank:'Rank within this view · #1 is strongest',rankChange:'Change in rank · positive means improvement · places'};
export default function RelativePerformance({sessions,timeline,symbol,selectedDate,metric='relative',onSelect,scrollRef,onScroll}:{sessions:readonly Session[];timeline:readonly Session[];symbol:string;selectedDate:string|undefined;metric?:Metric;onSelect:(date:string)=>void;scrollRef?:RefObject<HTMLDivElement|null>;onScroll?:UIEventHandler<HTMLDivElement>}) {
  const layout=chartLayout(timeline.length);
  const returns=metric==='relative'||metric==='daily';
  const stats=directionalMoveStats(sessions,symbol,selectedDate,60,5,metric==='relative'?'relative':'daily');
  const complete=stats.historySessions===stats.lookback&&stats.missingSessions===0;
  const up=returns&&complete&&stats.up.count>=stats.minDirectionDays?stats.up.mean:null;
  const down=returns&&complete&&stats.down.count>=stats.minDirectionDays?stats.down.mean:null;
  const format=(n:number|null)=>formatValue(n,metric)+(n!==null?(metric==='relative'?' pp':metric==='rankChange'?' places':''):'');
  const current=sessions.find(d=>d.date===selectedDate)?.cells[symbol]?.[metric]??null;
  const values=timeline.map(d=>d.cells[symbol]?.[metric]??null).filter((v):v is number=>v!==null);
  const high=values.length?Math.max(...values):null;
  const low=values.length?Math.min(...values):null;
  // Every bar and reference line uses the same linear scale, without clipping.
  const extent=Math.max(.1,...values.map(Math.abs),Math.abs(up??0),Math.abs(down??0))*1.15;
  const position=(value:number)=>50-value/extent*50;
  return <section className={styles.relativeChart} aria-label={titles[metric]}>
    <div className={styles.miniTitle}>{titles[metric]}<span>{timeline.length} heatmap sessions · Oldest to newest → · {units[metric]} · Follows heatmap Measure</span></div>
    <div className={styles.chartValues}>
      <div><span>Selected · {selectedDate??'—'}</span><strong>{format(current)}</strong></div>
      <div><span>{metric==='rank'?'Best visible rank':'Highest visible value'}</span><strong>{format(metric==='rank'?low:high)}</strong></div>
      <div><span>{metric==='rank'?'Worst visible rank':'Lowest visible value'}</span><strong>{format(metric==='rank'?high:low)}</strong></div>
    </div>
    {returns?<div className={styles.relativeLegend}>
      <span className={styles.averageUp}><i/>Average up: {up===null?'unavailable':format(up)} · {stats.up.count} days</span>
      <span className={styles.averageDown}><i/>Average down: {down===null?'unavailable':format(down)} · {stats.down.count} days</span>
    </div>:<p className={styles.relativeMeta}>{metric==='rank'?'#1 is the strongest rank; lower numbers are better.':'↑ means improvement toward #1; ↓ means a loss of places.'} Average up/down return lines apply to the two return measures.</p>}
    <div className={styles.chartScroll} ref={scrollRef} onScroll={onScroll} tabIndex={0} role="region" aria-label="Scrollable performance history"><div data-chart-width={layout.width} style={{width:layout.width,paddingLeft:layout.left,paddingRight:layout.right}}>
    <div className={`${styles.relativePlot} ${styles.alignedPlot} ${metric==='rank'?styles.rankPlot:''}`} aria-label={`${titles[metric]} history`}>
      {timeline.map(day=>{const value=day.cells[symbol]?.[metric]??null;return <button key={day.date} title={`${day.date}: ${format(value)}`} aria-label={`${day.date}: ${format(value)}`} aria-pressed={day.date===selectedDate} onClick={()=>onSelect(day.date)}>
        {value!==null&&<span className={styles.relativeBar} style={{width:layout.bodyWidth,left:`calc(50% - ${layout.bodyWidth/2}px)`,right:'auto',background:metric==='rank'?'#f2b84b':value>=0?'#35b995':'#e77687',height:`${Math.abs(value)/extent*(metric==='rank'?100:50)}%`,...(metric==='rank'?{bottom:0}:{top:`${value>=0?position(value):50}%`})}}/>}
        {value===null&&<span className={styles.srOnly}>Missing value</span>}
      </button>})}
      {up!==null&&<span className={`${styles.averageLine} ${styles.averageUp}`} style={{top:`${position(up)}%`}} aria-hidden="true"/>}
      {down!==null&&<span className={`${styles.averageLine} ${styles.averageDown}`} style={{top:`${position(down)}%`}} aria-hidden="true"/>}
    </div>
    <div className={`${styles.chartSessionDates} ${styles.alignedDates}`}>{timeline.map((day,i)=><time key={day.date} dateTime={day.date} aria-label={day.date}>{(i%layout.labelEvery===0||i===timeline.length-1)&&<>{day.date.slice(5)}<span>{day.date.slice(0,4)}</span></>}</time>)}</div>
    </div></div>
    <p className={styles.relativeMeta}>Same sessions as the heatmap, oldest to newest. Horizontal scrolling is linked to the daily price chart. {metric==='rank'?'Ranks start at zero at the bottom; #1 is strongest.':`Zero ${metric==='relative'?'pp':metric==='daily'?'%':'places'} at center.`}</p>
    {returns&&<p className={styles.relativeMeta}>Lines average positive and negative {metric==='relative'?'relative-to-SPY moves':'daily price returns'} separately over the 60 sessions before {selectedDate??'the selected day'}; the selected day is excluded. {stats.startDate&&`${stats.startDate} through ${stats.endDate}.`} {(!complete||up===null||down===null)&&'Each line requires 60 complete prior returns and at least five days in that direction.'}</p>}
  </section>;
}
