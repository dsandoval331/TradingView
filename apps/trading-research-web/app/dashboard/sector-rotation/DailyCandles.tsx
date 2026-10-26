'use client';
import { useMemo } from 'react';
import { closeEma } from './ema';
import type { RefObject, UIEventHandler } from 'react';
import { chartLayout } from './chart-layout';
import type { Bar, Group, Session } from './model';
import { candleSeries } from './candles';
import styles from './tracker.module.css';
import { emaPeriod, type ChartLine } from './chart-lines';
import { volumeSeries } from './volume';
const price=(n:number)=>n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
export default function DailyCandles({bars,sessions,group,selectedDate,onSelect,scrollRef,onScroll,historySessions=sessions,line='ema20'}:{bars:readonly Bar[];sessions:readonly Session[];group:Group;selectedDate?:string;onSelect:(date:string)=>void;line?:ChartLine;historySessions?:readonly Session[];scrollRef?:RefObject<HTMLDivElement|null>;onScroll?:UIEventHandler<HTMLDivElement>}) {
 const period=emaPeriod(line);
 const ema=useMemo(()=>closeEma(historySessions,group.symbol,period??20),[historySessions,group.symbol,period]);
 const volumes=useMemo(()=>volumeSeries(bars,historySessions,group.symbol),[bars,historySessions,group.symbol]);
 const emaValues=sessions.map(s=>ema.get(s.date)??null);
 const selectedEma=selectedDate?ema.get(selectedDate)??null:null;
 const candles=useMemo(()=>candleSeries(bars,sessions,group.symbol),[bars,sessions,group.symbol]);
 const basket=group.kind==='basket';
 const closes=sessions.map(s=>s.cells[group.symbol]?.close??null);
 const valid=candles.filter(c=>c!==null);
 const priceValues=basket?closes.filter((c):c is number=>c!==null&&Number.isFinite(c)&&c>0):valid.flatMap(c=>[c.low,c.high]);
 const values=[...priceValues,...(period!==null?emaValues.filter((v):v is number=>v!==null):[])];
 const lo=values.length?Math.min(...values):0,hi=values.length?Math.max(...values):1;
 const padding=Math.max((hi-lo)*.08,hi*.001,.01),bottom=lo-padding,top=hi+padding;
 const {left,right,width,slot,bodyWidth,labelEvery}=chartLayout(sessions.length);
 const plotHeight=280,plotTop=20;
 const volumeTop=340,volumeHeight=100,axisBottom=basket?plotTop+plotHeight:volumeTop+volumeHeight;
 const volumeValues=sessions.flatMap(s=>{const v=volumes.get(s.date);return [v?.volume,v?.average].filter((n):n is number=>n!=null);});
 const volumeMax=Math.max(1,...volumeValues)*1.08;
 const vy=(v:number)=>volumeTop+volumeHeight-(v/volumeMax)*volumeHeight;
 const selectedVolume=selectedDate?volumes.get(selectedDate):null;
 const compact=(v:number)=>new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:1}).format(v);
 let volumePath='',volumeConnected=false;
 sessions.forEach((s,i)=>{const v=volumes.get(s.date)?.average;if(v==null){volumeConnected=false;return;}volumePath+=`${volumeConnected?'L':'M'}${(left+(i+.5)*slot).toFixed(2)},${vy(v).toFixed(2)} `;volumeConnected=true;});
 const x=(i:number)=>left+(i+.5)*slot;
 const y=(v:number)=>plotTop+(top-v)/(top-bottom)*plotHeight;
 const selectedIndex=sessions.findIndex(s=>s.date===selectedDate),selected=candles[selectedIndex],selectedClose=closes[selectedIndex];
 const available=basket?priceValues.length:valid.length;
 let emaPath='',emaConnected=false;
 if(period!==null)emaValues.forEach((value,i)=>{if(value===null){emaConnected=false;return;}emaPath+=`${emaConnected?'L':'M'}${x(i).toFixed(2)},${y(value).toFixed(2)} `;emaConnected=true;});
 let path='';let connected=false;
 if(basket)closes.forEach((c,i)=>{if(c===null||!Number.isFinite(c)||c<=0){connected=false;return;}path+=`${connected?'L':'M'}${x(i).toFixed(2)},${y(c).toFixed(2)} `;connected=true;});
 return <section className={styles.candleSection} aria-label="Daily price chart">
  <p className={styles.eyebrow}>DAILY PRICE HISTORY</p><h2>{group.symbol} · {basket?'Basket closing index':'1-day candlestick chart'}</h2>
  <p className={styles.relativeMeta}>{sessions.length} sessions · Same session count and date filters as the heatmap · Oldest to newest → · Scrolling linked to performance chart</p>
  <div className={styles.chartLineControl}>{period!==null&&<span className={styles.emaLegend}><i/>{period} EMA · {selectedEma===null?`Unavailable · needs ${period} consecutive closes`:`${basket?'':'$'}${price(selectedEma)}${basket?' index points':''}`}</span>}</div>
  <div className={styles.candleReadout} aria-live="polite"><strong>{selectedDate??'No session selected'}</strong>{basket?<span>Close {selectedClose==null?'—':price(selectedClose)} index points</span>:selected?<><span>Open ${price(selected.open)}</span><span>High ${price(selected.high)}</span><span>Low ${price(selected.low)}</span><span>Close ${price(selected.close)}</span></>:<span>OHLC unavailable for this session</span>}</div>
  {!basket&&<div className={styles.candleReadout}><span>Volume · {selectedVolume?.volume==null?'Unavailable':compact(selectedVolume.volume)+' shares'}</span><span>20-session average · {selectedVolume?.average==null?'Unavailable':compact(selectedVolume.average)+' shares'}</span></div>}
  {available===0?<p className={styles.notice}>{sessions.length?'Verified daily OHLC history is not available for this selection yet.':'No sessions match these dates.'}</p>:<div className={styles.chartScroll} ref={scrollRef} onScroll={onScroll} tabIndex={0} role="region" aria-label="Scrollable daily price history">
   <svg className={styles.candleSvg} data-chart-width={width} width={width} height={basket?360:500} role="group" aria-label={`${group.symbol} daily ${basket?'closing index':'candles'} for ${sessions.length} heatmap sessions`}>
    {[0,1,2,3,4].map(i=>{const v=bottom+(top-bottom)*i/4;return <g key={i}><line x1={left} x2={width-right} y1={y(v)} y2={y(v)} stroke="#293647"/><text x={left-10} y={y(v)+4} textAnchor="end" fill="#9eacbe" fontSize="11">{basket?'':'$'}{price(v)}</text></g>;})}
    {!basket&&<g aria-label="Volume axis"><line x1={left} x2={width-right} y1={volumeTop+volumeHeight} y2={volumeTop+volumeHeight} stroke="#293647"/><text x={left} y={volumeTop-12} fill="#9eacbe" fontSize="11">Volume · shares · 20-session average</text>{[0,1].map(i=><text key={i} x={left-10} y={vy(volumeMax*i)+4} textAnchor="end" fill="#9eacbe" fontSize="10">{compact(volumeMax*i)}</text>)}</g>}
    {basket&&<path d={path} fill="none" stroke="#f2b84b" strokeWidth="2"/>}
    {sessions.map((session,i)=>{
     const c=candles[i],close=closes[i],color=c?(c.close>c.open?'#52d9aa':c.close<c.open?'#ff8496':'#cad5e2'):'#f2b84b';
     const description=basket?`${session.date}: closing index ${close==null?'unavailable':price(close)}`:c?`${session.date}: open $${price(c.open)}, high $${price(c.high)}, low $${price(c.low)}, close $${price(c.close)}`:`${session.date}: OHLC unavailable`;
     return <g key={session.date} role="button" tabIndex={0} aria-label={description} aria-pressed={session.date===selectedDate} onClick={()=>onSelect(session.date)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(session.date);}}} className={styles.candleTarget} data-candle-date={session.date}>
      <title>{description}</title><rect x={x(i)-slot/2} y={plotTop} width={slot} height={axisBottom-plotTop} fill={session.date===selectedDate?'#f2b84b12':'transparent'} stroke={session.date===selectedDate?'#f2b84b':'none'}/>
      {!basket&&c&&<><line x1={x(i)} x2={x(i)} y1={y(c.high)} y2={y(c.low)} stroke={color} strokeWidth="1.5"/><rect x={x(i)-bodyWidth/2} y={Math.min(y(c.open),y(c.close))} width={bodyWidth} height={Math.max(1,Math.abs(y(c.open)-y(c.close)))} fill={color}/></>}
      {basket&&close!==null&&Number.isFinite(close)&&close>0&&<circle cx={x(i)} cy={y(close)} r="3" fill={color}/>}
      {((!basket&&!c)||(basket&&close===null))&&<text x={x(i)} y={plotTop+plotHeight/2} textAnchor="middle" fill="#9eacbe" fontSize="11">—</text>}
      {!basket&&volumes.get(session.date)?.volume!=null&&<rect data-volume-date={session.date} x={x(i)-bodyWidth/2} y={vy(volumes.get(session.date)!.volume!)} width={bodyWidth} height={volumeTop+volumeHeight-vy(volumes.get(session.date)!.volume!)} fill={color} opacity=".65"><title>{`${session.date}: volume ${volumes.get(session.date)!.volume!.toLocaleString('en-US')} shares`}</title></rect>}
      {(i%labelEvery===0||i===sessions.length-1)&&<text x={x(i)} y={axisBottom+24} textAnchor="middle" fill="#9eacbe" fontSize="10">{session.date.slice(5)}<tspan x={x(i)} dy="14">{session.date.slice(0,4)}</tspan></text>}
     </g>;
    })}
    {emaPath&&<path data-overlay={line} d={emaPath} fill="none" stroke="#69b7ff" strokeWidth="2" pointerEvents="none" aria-label={`${period}-session exponential moving average of closing prices`}/>}
    {!basket&&volumePath&&<path data-overlay="volume-average" d={volumePath} fill="none" stroke="#f2b84b" strokeWidth="2" pointerEvents="none" aria-label="20-session average volume"/>}
   </svg>
  </div>}
  <p className={styles.relativeMeta}>{basket?'Close-only index: member daily highs/lows do not establish the basket’s intraday range.':'Each candle represents one completed provider daily OHLC bar. Green: close above open; red: close below open; gray: unchanged. Split-adjusted prices, excluding dividends.'} Select a {basket?'point':'candle'} to update the selected session. {available} of {sessions.length} sessions available; missing sessions stay blank.</p>
  {period!==null&&<p className={styles.relativeMeta}>{period} EMA uses closing {basket?'index levels':'prices'} with a {period}-session simple-average seed and smoothing factor 2/{(period??20)+1}. Calculated from full loaded history before applying the visible date range. Missing closes restart the {period}-session warmup.</p>}
  <p className={styles.relativeMeta}>{basket?'Basket volume is unavailable; constituent share volumes are not combined into an artificial index volume.':'Volume bars use the same dates and widths as the candles. Amber line: trailing 20-session simple average including that day, computed from full loaded history. Missing volume resets the average warmup; zero volume is retained.'}</p>
 </section>;
}
