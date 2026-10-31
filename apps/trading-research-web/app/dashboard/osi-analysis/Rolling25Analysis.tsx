'use client';

import {useState} from 'react';
import {rolling25Rows, rankRolling25, type WindowOverlapMode, type Signal} from './model';
import styles from './analysis.module.css';

const pct=(value:number|null)=>value===null?'—':`${value.toFixed(2)}%`;
export default function Rolling25Analysis({signals}:{signals:Signal[]}) {
  const [overlap,setOverlap]=useState<WindowOverlapMode>('exclude-3');
  const rows=rolling25Rows(signals);
  return <section className={styles.panel} aria-labelledby="rolling25-title">
    <h2 id="rolling25-title">25 Minute Window Analysis</h2>
    <p>Every rolling set of five consecutive five-minute reporting slots is compared: 74 possible windows across the regular session. Times are Central Time. For example, 10:20 / 10:25 / 10:30 / 10:35 / 10:40 covers alerts from 10:20 up to, but not including, 10:45. Current analysis filters apply.</p>
    <p>Ranked by pooled favorable rate, using Favorable / (Favorable + Adverse + Both). Each signal counts once within a window. Neighboring windows overlap and can share signals; top and bottom lists can overlap when few windows have data. Windows without resolved outcomes are unranked. Small samples and the current synthetic data do not establish successful trading times.</p>
    <div className={styles.filters}><label>Window Overlap<select value={overlap} onChange={e=>setOverlap(e.target.value as WindowOverlapMode)}>
      <option value="allow-all">Allow All</option><option value="exclude-3">Exclude +3</option><option value="exclude-any">Exclude Any Shared</option>
    </select></label></div>
    <p>{overlap==='allow-all'?'Allow All: overlapping windows are permitted.':overlap==='exclude-3'?'Exclude +3: skip a candidate if it shares three or more slots with any window already selected in that list.':'Exclude Any Shared: skip a candidate if it shares any slot with a window already selected in that list.'} Each list is selected independently in rank order; fewer than four results may qualify.</p>
    <div className={styles.timeCards}>{(['long','short'] as const).flatMap(side=>[false,true].map(bottom=>{
      const ranked=rankRolling25(rows,side,bottom,overlap);
      return <article key={`${side}-${bottom}`}><h3>{bottom?'Bottom':'Top'} 4 {side==='long'?'Long':'Short'} Windows</h3>
        {ranked.length ? <ol>{ranked.map(r=>{const s=r[side];return <li key={r.start}><strong>{r.start}–{r.end} CT · {pct(s.favorableRate)}</strong><small>Slots: {r.slots.join(' / ')}</small><small>{s.favorable+s.adverse+s.both} resolved · {s.signals} signals · {s.favorable} favorable · {s.adverse} adverse · {s.both} both</small><small>Avg MFE {pct(s.mfe)} · Avg MAE {pct(s.mae)}</small></li>;})}</ol>:<p>No resolved outcomes available.</p>}
        {ranked.length>0 && ranked.length<4 && <small>Only {ranked.length} window{ranked.length===1?'':'s'} qualify under the selected overlap rule.</small>}
      </article>;
    }))}</div>
  </section>;
}
