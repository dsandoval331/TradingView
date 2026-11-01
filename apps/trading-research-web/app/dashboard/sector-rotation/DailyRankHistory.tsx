import type {RefObject,UIEventHandler} from 'react';
import type {Session} from './model';
import {chartLayout} from './chart-layout';
import styles from './tracker.module.css';

export default function DailyRankHistory({timeline,symbol,name,universeSize,selectedDate,onSelect,scrollRef,onScroll}:{timeline:readonly Session[];symbol:string;name:string;universeSize:number;selectedDate:string|undefined;onSelect:(date:string)=>void;scrollRef?:RefObject<HTMLDivElement|null>;onScroll?:UIEventHandler<HTMLDivElement>}){
 const layout=chartLayout(timeline.length),height=220,padding=14;
 const rankOf=(day:Session)=>{const rank=day.cells[symbol]?.rank;return rank!=null&&Number.isFinite(rank)&&rank>=1&&rank<=universeSize?rank:null;};
 const y=(rank:number)=>padding+(rank-1)/Math.max(1,universeSize-1)*(height-padding*2);
 const ranks=timeline.map(rankOf),valid=ranks.filter((r):r is number=>r!==null);
 const current=timeline.find(day=>day.date===selectedDate);
 const format=(rank:number|null)=>rank===null?'—':`#${rank}`;
 // Separate path segments preserve gaps instead of implying ranks across missing comparisons.
 const path=ranks.map((rank,i)=>rank===null?'':`${i===0||ranks[i-1]===null?'M':'L'} ${(i+.5)*layout.slot} ${y(rank)}`).join(' ');
 const ticks=Array.from({length:universeSize},(_,i)=>i+1);
 return <section className={styles.performancePanel} aria-label="Daily Rank History">
  <h2>Daily Rank History</h2><h3>{symbol} · {name}</h3>
  <p className={styles.relativeMeta}>{timeline.length} selected sessions · Oldest to newest → · #1 is strongest · Independent of the Measure setting</p>
  <div className={styles.chartValues}><div><span>Selected · {selectedDate??'—'}</span><strong>{format(current?rankOf(current):null)}</strong></div><div><span>Best Visible Rank</span><strong>{format(valid.length?Math.min(...valid):null)}</strong></div><div><span>Worst Visible Rank</span><strong>{format(valid.length?Math.max(...valid):null)}</strong></div></div>
  {!timeline.length?<p>No sessions match these dates.</p>:<>
   {!valid.length&&<p>No complete rank comparisons are available in this range.</p>}
   <div className={styles.chartScroll} ref={scrollRef} onScroll={onScroll} tabIndex={0} role="region" aria-label="Scrollable daily rank history"><div data-chart-width={layout.width} style={{width:layout.width,paddingLeft:layout.left,paddingRight:layout.right}}>
    <div className={`${styles.relativePlot} ${styles.alignedPlot}`} style={{background:'none'}}>
     {ticks.map(rank=><span key={rank} aria-hidden="true" style={{position:'absolute',left:0,right:0,top:y(rank),borderTop:'1px solid #354254',pointerEvents:'none'}}><span style={{position:'absolute',right:'100%',paddingRight:12,transform:'translateY(-50%)',fontSize:11,color:'#9aabbc'}}>#{rank}</span></span>)}
     <svg aria-hidden="true" viewBox={`0 0 ${layout.plotWidth} ${height}`} style={{position:'absolute',width:'100%',height:'100%',pointerEvents:'none'}}><path data-rank-line d={path} fill="none" stroke="#f2b84b" strokeWidth="2"/>{ranks.map((rank,i)=>rank!==null&&<circle key={timeline[i].date} cx={(i+.5)*layout.slot} cy={y(rank)} r={timeline[i].date===selectedDate?5:3} fill={timeline[i].date===selectedDate?'#eef3f8':'#f2b84b'}/>)}</svg>
     {timeline.map((day,i)=><button key={day.date} aria-label={`${day.date}: ${symbol} daily rank ${format(ranks[i])}`} title={`${day.date}: ${format(ranks[i])} of ${universeSize}`} aria-pressed={day.date===selectedDate} onClick={()=>onSelect(day.date)}><span className={styles.srOnly}>{ranks[i]===null?'Missing rank':format(ranks[i])}</span></button>)}
    </div>
    <div className={`${styles.chartSessionDates} ${styles.alignedDates}`}>{timeline.map((day,i)=><time key={day.date} dateTime={day.date} aria-label={day.date}>{(i%layout.labelEvery===0||i===timeline.length-1)&&<>{day.date.slice(5)}<span>{day.date.slice(0,4)}</span></>}</time>)}</div>
   </div></div>
  </>}
  <p className={styles.relativeMeta}>Daily close-to-close return rank among all {universeSize} symbols in this view. Lower numbers appear higher on the chart. Tied returns share a rank; incomplete comparisons remain gaps. Select a date to update the other charts. Horizontal scrolling is linked to the price and performance charts.</p>
 </section>;
}
