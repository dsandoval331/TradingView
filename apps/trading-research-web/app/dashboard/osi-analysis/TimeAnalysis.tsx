import {summarize, timeBucket, sessionSections, type Signal} from './model';
import styles from './analysis.module.css';

const pct = (v: number | null) => v === null ? '—' : `${v.toFixed(2)}%`;
const clock = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2,'0')}:${String(minutes % 60).padStart(2,'0')}`;
export const intervals = Array.from({length:78},(_,i) => `${clock(510+i*5)}–${clock(515+i*5)}`);
export function timeRows(signals: Signal[]) {
  return intervals.map(label => {
    const entries = signals.filter(s => timeBucket(s.time,'America/Chicago') === label);
    return {label, entries, long:summarize(entries.filter(s=>s.side==='Long')), short:summarize(entries.filter(s=>s.side==='Short'))};
  });
}
export function rankedTimes(rows: ReturnType<typeof timeRows>, side: 'long' | 'short', bottom = false) {
  return rows.filter(r=>r[side].favorableRate !== null).sort((a,b)=> (bottom ? 1 : -1)*((a[side].favorableRate ?? 0)-(b[side].favorableRate ?? 0)) || a.label.localeCompare(b.label)).slice(0,4);
}

function SessionStats({entries}: {entries: Signal[]}) {
  return <div className={styles.scroll}><table><thead><tr>{['Direction','Signals','Processed Outcomes','Favorable','Adverse','Both','Unresolved','No Accepted Outcome','Failed Events','Favorable Rate','Avg MFE','Avg MAE'].map(h=><th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{['All','Long','Short'].map(side=>{
    const s=summarize(side==='All'?entries:entries.filter(e=>e.side===side));
    return <tr key={side}><th scope="row">{side}</th>{[s.signals,s.accepted,s.favorable,s.adverse,s.both,s.unresolved,s.noAccepted,s.failed,pct(s.favorableRate),pct(s.mfe),pct(s.mae)].map((v,i)=><td key={i}>{v}</td>)}</tr>;
  })}</tbody></table></div>;
}

export default function TimeAnalysis({signals}: {signals:Signal[]}) {
  const rows = timeRows(signals);
  return <section className={styles.panel} aria-labelledby="time-analysis-title">
    <h2 id="time-analysis-title">5 Minute Window Analysis</h2>
    <p>5-Minute Entry Time Analysis · Central Time. Each alert is assigned to the closest five-minute increment at or before its signal timestamp (8:35:40 → 8:35; 8:40:00 → 8:40). All 78 regular-session intervals are shown, from 8:30 AM to 3:00 PM CT, with exclusive end times. Current analysis filters apply.</p>
    <p>Ranked by favorable rate, using the existing processed-outcome definition. Ties sort by earliest interval. Empty or unresolved-only intervals are unranked. With fewer than eight ranked intervals, top and bottom lists can overlap. These synthetic test results do not establish trading performance.</p>
    <div className={styles.timeCards}>{(['long','short'] as const).flatMap(side => [false,true].map(bottom => {
      const ranked=rankedTimes(rows,side,bottom);
      return <article key={`${side}-${bottom}`}><h3>{bottom?'Bottom':'Top'} 4 {side==='long'?'Long':'Short'} Times</h3>
        {ranked.length ? <ol>{ranked.map(r=><li key={r.label}><strong>{r.label} CT · {pct(r[side].favorableRate)}</strong><small>{r[side].favorable+r[side].adverse+r[side].both} resolved · {r[side].signals} signals · Avg MFE {pct(r[side].mfe)} · Avg MAE {pct(r[side].mae)}</small></li>)}</ol> : <p>No resolved outcomes available.</p>}
        {ranked.length>0 && ranked.length<4 && <small>Only {ranked.length} eligible interval{ranked.length===1?'':'s'} available.</small>}
      </article>;
    }))}</div>
    {sessionSections.map(section => {
      const sectionRows = rows.filter(r => r.label.slice(0,5) >= section.start && r.label.slice(0,5) < section.end);
      const entries = sectionRows.flatMap(r => r.entries);
      const total = summarize(entries);
      return <details className={styles.event} key={section.name}>
        <summary><strong>{section.name}</strong><span>{section.description}</span><span>{total.signals} signals · {pct(total.favorableRate)} favorable rate</span></summary>
        <p>{sectionRows.length} Five-Minute Intervals</p>
        <SessionStats entries={entries}/>
        <p>Statistics combine distinct signals across this section using the current analysis filters. Start times are inclusive and end times exclusive; session rates and excursion averages are calculated from underlying observations, not averages of interval rates.</p>
        {sectionRows.map(r=><details className={styles.event} key={r.label}><summary><strong>{r.label} CT</strong><span>{r.long.signals} Long · {r.short.signals} Short</span><span>Favorable Rate: Long {pct(r.long.favorableRate)} · Short {pct(r.short.favorableRate)}</span></summary>
      <div className={styles.scroll}><table><thead><tr>{['Direction','Signals','Processed Outcomes','Favorable','Adverse','Both','Unresolved','No Accepted Outcome','Failed Events','Favorable Rate','Avg MFE','Avg MAE'].map(h=><th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{(['long','short'] as const).map(side=>{const s=r[side];return <tr key={side}><th scope="row">{side==='long'?'Long':'Short'}</th>{[s.signals,s.accepted,s.favorable,s.adverse,s.both,s.unresolved,s.noAccepted,s.failed,pct(s.favorableRate),pct(s.mfe),pct(s.mae)].map((v,i)=><td key={i}>{v}</td>)}</tr>;})}</tbody></table></div>
      {r.entries.length ? <ul className={styles.timeSignals}>{r.entries.map(s=><li key={s.key}>{s.key} · {s.side} · {s.grade} · {String(s.outcome?.primary_outcome ?? 'No Accepted Outcome')}</li>)}</ul> : <p>No signals in this interval.</p>}
    </details>)}
      </details>;
    })}
  </section>;
}
