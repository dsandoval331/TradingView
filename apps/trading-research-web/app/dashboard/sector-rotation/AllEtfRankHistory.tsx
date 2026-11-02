'use client';
import {useState} from 'react';
import type {Group,Session} from './model';
import {chartLayout} from './chart-layout';
import styles from './tracker.module.css';
import {sessionWindow} from './session-window';
const COLORS=['#5ee6b0','#ffb454','#73b7ff','#ff84b7','#c4a0ff','#f6ed78','#4edbe8','#ff8067','#b8df85','#d6bba3','#a5aaff'];
export default function AllEtfRankHistory({timeline:history,groups,selectedDate,onSelect}:{timeline:readonly Session[];groups:readonly Group[];selectedDate:string|undefined;onSelect:(date:string)=>void}){
 const [range,setRange]=useState('20');
 const duration=sessionWindow(range),timeline=duration==='all'?history:history.slice(-duration);
 const [hidden,setHidden]=useState<Record<string,boolean>>({});
 const layout=chartLayout(timeline.length),height=412.5,padding=14;
 const y=(rank:number)=>padding+(rank-1)/Math.max(1,groups.length-1)*(height-padding*2);
 const series=groups.map((g,i)=>{const ranks=timeline.map(day=>{const r=day.cells[g.symbol]?.rank;return r!=null&&Number.isFinite(r)&&r>=1&&r<=groups.length?r:null;});return {...g,color:COLORS[i%COLORS.length],ranks,path:ranks.map((r,j)=>r===null?'':`${j===0||ranks[j-1]===null?'M':'L'} ${(j+.5)*layout.slot} ${y(r)}`).join(' ')};});
 const visible=series.filter(g=>!hidden[g.symbol]);
 return <section className={styles.performancePanel} aria-label="All ETF Daily Rank History"><h2>All ETF Daily Rank History</h2>
  <div className={styles.methodOneGrid}><label>Rank History Range<select aria-label="All ETF rank history range" value={range} onChange={event=>setRange(event.target.value)}><option value="20">Last 20 Sessions</option><option value="60">Last 60 Sessions</option><option value="120">Last 120 Sessions</option><option value="all">All Available</option></select></label></div>
  <p className={styles.relativeMeta}>{timeline.length} trading sessions · Oldest to newest → · #1 is strongest · Independent of the page’s Sessions, date range, and Measure settings</p>
  <fieldset style={{border:'1px solid #354254',borderRadius:8,padding:14,margin:'14px 0'}}><legend>ETF Legend And Visibility</legend><div style={{display:'flex',flexWrap:'wrap',gap:'12px 24px'}}>{series.map(g=><label key={g.symbol} style={{display:'flex',alignItems:'center',gap:8,cursor:'pointer',fontSize:13}} title={g.name}><input type="checkbox" checked={!hidden[g.symbol]} aria-label={`Show ${g.symbol}`} onChange={()=>setHidden(previous=>({...previous,[g.symbol]:!previous[g.symbol]}))} style={{accentColor:g.color,width:16,height:16}}/><span aria-hidden="true" style={{width:24,borderTop:`3px solid ${g.color}`}}/><span style={{color:g.color}}>{g.symbol}</span><span className={styles.srOnly}>{g.name}</span></label>)}</div></fieldset>
  {!timeline.length?<p>No rank history is available.</p>:<>
   {!visible.length&&<p role="status">All ETFs are hidden. Enable an ETF above to display its rank history.</p>}
   {visible.length>0&&!visible.some(g=>g.ranks.some(r=>r!==null))&&<p>No complete rank comparisons are available in this range.</p>}
   <div className={styles.chartScroll} tabIndex={0} role="region" aria-label="Scrollable all ETF daily rank history"><div data-chart-width={layout.width} style={{width:layout.width,paddingLeft:layout.left,paddingRight:layout.right}}>
    <div className={`${styles.relativePlot} ${styles.alignedPlot}`} style={{height,background:'none'}}>
     {Array.from({length:groups.length},(_,i)=>i+1).map(rank=><span key={rank} aria-hidden="true" style={{position:'absolute',left:0,right:0,top:y(rank),borderTop:'1px solid #354254',pointerEvents:'none'}}><span style={{position:'absolute',right:'100%',paddingRight:12,transform:'translateY(-50%)',fontSize:11,color:'#9aabbc'}}>#{rank}</span></span>)}
     <svg aria-hidden="true" viewBox={`0 0 ${layout.plotWidth} ${height}`} style={{position:'absolute',width:'100%',height:'100%',pointerEvents:'none'}}>{visible.map(g=><g key={g.symbol} data-etf-series={g.symbol}><path d={g.path} fill="none" stroke={g.color} strokeWidth="2"/>{g.ranks.map((r,i)=>r!==null&&<circle key={timeline[i].date} cx={(i+.5)*layout.slot} cy={y(r)} r={timeline[i].date===selectedDate?4:2.5} fill={g.color}/>)}</g>)}</svg>
     {timeline.map((day,i)=>{const text=visible.map(g=>`${g.symbol}: ${g.ranks[i]===null?'unavailable':`#${g.ranks[i]}`}`).join(' · ');return <button key={day.date} title={`${day.date} · ${text}`} aria-label={`${day.date} ETF ranks · ${text}`} aria-pressed={day.date===selectedDate} onClick={()=>onSelect(day.date)}/>;})}
    </div>
    <div className={`${styles.chartSessionDates} ${styles.alignedDates}`}>{timeline.map((day,i)=><time key={day.date} dateTime={day.date}>{(i%layout.labelEvery===0||i===timeline.length-1)&&<>{day.date.slice(5)}<span>{day.date.slice(0,4)}</span></>}</time>)}</div>
   </div></div>
  </>}
  <p className={styles.relativeMeta}>Each line shows an ETF’s daily close-to-close return rank. Hiding ETFs changes visibility only; ranks remain calculated against all {groups.length} ETFs. Ties share a rank, and missing comparisons remain gaps. Hover a date for enabled ETF ranks or select it to update the other charts.</p>
 </section>;
}
