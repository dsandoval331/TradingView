'use client';
import { useMemo } from 'react';
import type { Bar, Group, Session } from './model';
import { candleSeries } from './candles';
import styles from './tracker.module.css';
const price=(n:number)=>n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
export default function DailyCandles({bars,sessions,group,selectedDate,onSelect}:{bars:readonly Bar[];sessions:readonly Session[];group:Group;selectedDate?:string;onSelect:(date:string)=>void}) {
 const candles=useMemo(()=>candleSeries(bars,sessions,group.symbol),[bars,sessions,group.symbol]);
 const basket=group.kind==='basket';
 const closes=sessions.map(s=>s.cells[group.symbol]?.close??null);
 const valid=candles.filter(c=>c!==null);
 const values=basket?closes.filter((c):c is number=>c!==null&&Number.isFinite(c)&&c>0):valid.flatMap(c=>[c.low,c.high]);
 const lo=values.length?Math.min(...values):0,hi=values.length?Math.max(...values):1;
 const padding=Math.max((hi-lo)*.08,hi*.001,.01),bottom=lo-padding,top=hi+padding;
 const left=72,plotHeight=280,plotTop=20,width=Math.max(720,left+sessions.length*24+20);
 const slot=(width-left-20)/Math.max(1,sessions.length);
 const x=(i:number)=>left+(i+.5)*slot;
 const y=(v:number)=>plotTop+(top-v)/(top-bottom)*plotHeight;
 const selectedIndex=sessions.findIndex(s=>s.date===selectedDate),selected=candles[selectedIndex],selectedClose=closes[selectedIndex];
 const labelEvery=Math.max(1,Math.ceil(70/slot)),available=basket?values.length:valid.length;
 let path='';let connected=false;
 if(basket)closes.forEach((c,i)=>{if(c===null||!Number.isFinite(c)||c<=0){connected=false;return;}path+=`${connected?'L':'M'}${x(i).toFixed(2)},${y(c).toFixed(2)} `;connected=true;});
 return <section className={styles.candleSection} aria-label="Daily price chart">
  <p className={styles.eyebrow}>DAILY PRICE HISTORY</p><h2>{group.symbol} · {basket?'Basket closing index':'1-day candlestick chart'}</h2>
  <p className={styles.relativeMeta}>{sessions.length} sessions · Same session count and date filters as the heatmap · Oldest to newest →</p>
  <div className={styles.candleReadout} aria-live="polite"><strong>{selectedDate??'No session selected'}</strong>{basket?<span>Close {selectedClose==null?'—':price(selectedClose)} index points</span>:selected?<><span>Open ${price(selected.open)}</span><span>High ${price(selected.high)}</span><span>Low ${price(selected.low)}</span><span>Close ${price(selected.close)}</span></>:<span>OHLC unavailable for this session</span>}</div>
  {available===0?<p className={styles.notice}>{sessions.length?'Verified daily OHLC history is not available for this selection yet.':'No sessions match these dates.'}</p>:<div className={styles.chartScroll} tabIndex={0} role="region" aria-label="Scrollable daily price history">
   <svg className={styles.candleSvg} width={width} height={360} role="group" aria-label={`${group.symbol} daily ${basket?'closing index':'candles'} for ${sessions.length} heatmap sessions`}>
    {[0,1,2,3,4].map(i=>{const v=bottom+(top-bottom)*i/4;return <g key={i}><line x1={left} x2={width-10} y1={y(v)} y2={y(v)} stroke="#293647"/><text x={left-10} y={y(v)+4} textAnchor="end" fill="#9eacbe" fontSize="11">{basket?'':'$'}{price(v)}</text></g>;})}
    {basket&&<path d={path} fill="none" stroke="#f2b84b" strokeWidth="2"/>}
    {sessions.map((session,i)=>{
     const c=candles[i],close=closes[i],color=c?(c.close>c.open?'#52d9aa':c.close<c.open?'#ff8496':'#cad5e2'):'#f2b84b';
     const description=basket?`${session.date}: closing index ${close==null?'unavailable':price(close)}`:c?`${session.date}: open $${price(c.open)}, high $${price(c.high)}, low $${price(c.low)}, close $${price(c.close)}`:`${session.date}: OHLC unavailable`;
     return <g key={session.date} role="button" tabIndex={0} aria-label={description} aria-pressed={session.date===selectedDate} onClick={()=>onSelect(session.date)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(session.date);}}} className={styles.candleTarget} data-candle-date={session.date}>
      <title>{description}</title><rect x={x(i)-slot/2} y={plotTop} width={slot} height={plotHeight} fill={session.date===selectedDate?'#f2b84b12':'transparent'} stroke={session.date===selectedDate?'#f2b84b':'none'}/>
      {!basket&&c&&<><line x1={x(i)} x2={x(i)} y1={y(c.high)} y2={y(c.low)} stroke={color} strokeWidth="1.5"/><rect x={x(i)-Math.min(7,slot*.3)} y={Math.min(y(c.open),y(c.close))} width={Math.min(14,slot*.6)} height={Math.max(1,Math.abs(y(c.open)-y(c.close)))} fill={color}/></>}
      {basket&&close!==null&&Number.isFinite(close)&&close>0&&<circle cx={x(i)} cy={y(close)} r="3" fill={color}/>}
      {((!basket&&!c)||(basket&&close===null))&&<text x={x(i)} y={plotTop+plotHeight/2} textAnchor="middle" fill="#9eacbe" fontSize="11">—</text>}
      {(i%labelEvery===0||i===sessions.length-1)&&<text x={x(i)} y={plotTop+plotHeight+24} textAnchor="middle" fill="#9eacbe" fontSize="10">{session.date.slice(5)}<tspan x={x(i)} dy="14">{session.date.slice(0,4)}</tspan></text>}
     </g>;
    })}
   </svg>
  </div>}
  <p className={styles.relativeMeta}>{basket?'Close-only index: member daily highs/lows do not establish the basket’s intraday range.':'Each candle represents one completed provider daily OHLC bar. Green: close above open; red: close below open; gray: unchanged. Split-adjusted prices, excluding dividends.'} Select a {basket?'point':'candle'} to update the selected session. {available} of {sessions.length} sessions available; missing sessions stay blank.</p>
 </section>;
}
