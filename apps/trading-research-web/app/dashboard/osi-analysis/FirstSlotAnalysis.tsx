import {slotGradeRows, reportingSlot, summarize, type Signal} from './model';
import styles from './analysis.module.css';

const pct = (v: number | null) => v === null ? '—' : `${v.toFixed(2)}%`;
export default function FirstSlotAnalysis({signals}: {signals:Signal[]}) {
  const selected = signals.filter(s => reportingSlot(s.time) === '08:35');
  const rows = slotGradeRows(signals);
  const stats = summarize(selected);
  return <section className={styles.panel} aria-labelledby="first-slot-title">
    <h2 id="first-slot-title">8:35 AM CT Analysis By Letter Grade</h2>
    <p>The first indicator reporting slot. Alerts from 08:35:00 up to, but not including, 08:40:00 CT belong to 8:35. For example, 8:35:40 belongs to 8:35; it is never rounded forward.</p>
    <p>Grouped by the originating signal alert time, floored to the preceding five-minute increment. Later checkpoints and outcomes remain linked to that signal so each signal is counted once. The Direction filter applies; Grade and Entry Time filters do not narrow this dedicated grade comparison.</p>
    <p><strong>{stats.signals} signals · {stats.accepted} processed outcomes · {pct(stats.favorableRate)} favorable rate</strong></p>
    {selected.length === 0 ? <p>No 8:35 AM CT signals are present in the current snapshot. Letter-grade statistics are unavailable.</p> : <>
      {selected.some(s=>s.grade==='Ungraded') && <p>Missing letter grades appear as Ungraded. Signal quality labels are not converted into letter grades.</p>}
      <div className={styles.scroll}><table><thead><tr>{['Letter Grade','Direction','Signals','Processed Outcomes','Favorable','Adverse','Both','Unresolved','No Accepted Outcome','Failed Events','Favorable Rate','Avg MFE','Avg MAE'].map(h=><th key={h} scope="col">{h}</th>)}</tr></thead>
      <tbody>{rows.map(r=><tr key={`${r.grade}-${r.side}`}><th scope="row">{r.grade}</th><td>{r.side}</td>{[r.signals,r.accepted,r.favorable,r.adverse,r.both,r.unresolved,r.noAccepted,r.failed,pct(r.favorableRate),pct(r.mfe),pct(r.mae)].map((v,i)=><td key={i}>{v}</td>)}</tr>)}</tbody></table></div>
    </>}
    <p>Favorable rate = Favorable / (Favorable + Adverse + Both). Failed outcome deliveries and unresolved outcomes are excluded from this rate. MFE/MAE use available processed outcomes and are not realized returns. The current snapshot is synthetic; no live statistical conclusion is implied.</p>
  </section>;
}
