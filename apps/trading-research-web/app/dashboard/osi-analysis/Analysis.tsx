'use client';

import {useState} from 'react';
import {buildSignals, breakdown, summarize, type WebhookEvent} from './model';
import styles from './analysis.module.css';

const pct = (v: number | null) => v == null ? '—' : `${v.toFixed(2)}%`;
const timestamp = (v: unknown) => typeof v === 'string' && Number.isFinite(Date.parse(v)) ? new Intl.DateTimeFormat('en-US', {timeZone: 'America/New_York',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',timeZoneName:'short'}).format(new Date(v)) : '—';

function Breakdown({title, rows}: {title: string; rows: ReturnType<typeof breakdown>}) {
  return <section className={styles.panel}><h2>{title}</h2><div className={styles.scroll}><table><thead><tr>{['Group','Signals','Processed Outcomes','Favorable','Adverse','Both','Unresolved','No Accepted Outcome','Failed Events','Favorable Rate','Avg MFE','Avg MAE'].map(h => <th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{rows.map(r => <tr key={r.label}><th scope="row">{r.label}</th><td>{r.signals}</td><td>{r.accepted}</td><td>{r.favorable}</td><td>{r.adverse}</td><td>{r.both}</td><td>{r.unresolved}</td><td>{r.noAccepted}</td><td>{r.failed}</td><td>{pct(r.favorableRate)}</td><td>{pct(r.mfe)}</td><td>{pct(r.mae)}</td></tr>)}</tbody></table>{!rows.length && <p>No signals match these filters.</p>}</div></section>;
}

function Fields({value}: {value: Record<string, unknown>}) {
  return <dl className={styles.fields}>{Object.entries(value).map(([key,v]) => <div key={key}><dt>{key}</dt><dd>{v !== null && typeof v === 'object' && !Array.isArray(v) ? <Fields value={v as Record<string,unknown>}/> : v === null ? <span className={styles.muted}>null</span> : typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd></div>)}</dl>;
}

export default function Analysis({events}: {events: WebhookEvent[]}) {
  const [side,setSide] = useState('');
  const [grade,setGrade] = useState('');
  const [bucket,setBucket] = useState('');
  const [eventType,setEventType] = useState('');
  const [eventStatus,setEventStatus] = useState('');
  const all = buildSignals(events);
  const filtered = all.filter(s => (!side || s.side === side) && (!grade || s.grade === grade) && (!bucket || s.bucket === bucket));
  const selectedKeys = new Set(filtered.map(s => s.key));
  const filteredEvents = events.filter(e => selectedKeys.has(e.signal_key));
  const visibleEvents = filteredEvents.filter(e => (!eventType || e.event_type === eventType) && (!eventStatus || e.processing_status === eventStatus));
  const stats = summarize(filtered);
  function exportEvents() {const url = URL.createObjectURL(new Blob([JSON.stringify(filteredEvents,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='osi-analysis-events.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  return <div className={styles.analysis}>
    <header className={styles.header}><div><p className="eyebrow">MULtipLY · Signal Research</p><h1>OSI Analysis</h1><p>Explore signal quality, direction, entry timing, and outcome delivery.</p></div><button className="secondaryButton" onClick={exportEvents}>Export Filtered Events</button></header>
    <aside className={styles.notice}><strong>Synthetic Test Data · Six Webhook Events</strong><p>Database snapshot captured October 30, 2026. All records use TEST; no live performance is implied. This template does not automatically refresh from Supabase.</p></aside>
    <section className={styles.filters} aria-label="Analysis Filters">
      <label>Grade<select value={grade} onChange={e=>setGrade(e.target.value)}><option value="">All Grades</option>{[...new Set(all.map(s=>s.grade))].sort().map(v=><option key={v}>{v}</option>)}</select></label>
      <label>Direction<select value={side} onChange={e=>setSide(e.target.value)}><option value="">Long &amp; Short</option><option>Long</option><option>Short</option></select></label>
      <label>Entry Time · Eastern<select value={bucket} onChange={e=>setBucket(e.target.value)}><option value="">All 5-Minute Intervals</option>{[...new Set(all.map(s=>s.bucket))].sort().map(v=><option key={v}>{v}</option>)}</select></label>
      <button className="secondaryButton" onClick={()=>{setGrade('');setSide('');setBucket('');setEventType('');setEventStatus('');}}>Reset Filters</button><span>{filtered.length} of {all.length} signals</span>
    </section>
    <div className={styles.cards}>{[['Distinct Signals',stats.signals,'One count per signal key'],['Webhook Events',filteredEvents.length,'Signal, checkpoint, and outcome'],['Processed Outcomes',stats.accepted,'Failed deliveries excluded'],['Favorable Rate',pct(stats.favorableRate),'Favorable / (favorable + adverse + both)']].map(([label,value,note])=><article key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>)}</div>
    <section className={styles.method}><h2>How To Read These Results</h2><p>Breakdowns count distinct signals, not individual deliveries. Outcome statistics use only PROCESSED outcome events. “Both” stays its own category and is included in the resolved denominator; unresolved outcomes are excluded from that rate. MFE and MAE averages use processed outcomes with available values and are positive excursion magnitudes, not realized P&amp;L.</p><p>Grade is missing for all four signals in both the webhook payloads and saved entry context, so they appear as Ungraded. Signal quality STANDARD is a separate field and is not treated as a grade.</p><p>5-minute intervals use signal entry time in America/New_York, start inclusive and end exclusive. For outcome-only records, entry time comes from the signal key. Empty intervals have no observations and are omitted.</p></section>
    <Breakdown title="Analysis By Grade" rows={breakdown(filtered,'grade')}/>
    <Breakdown title="Long / Short Analysis" rows={breakdown(filtered,'side')}/>
    <Breakdown title="5-Minute Entry Time Analysis · Eastern" rows={breakdown(filtered,'bucket')}/>
    <section className={styles.panel}><h2>Signal Results</h2><div className={styles.scroll}><table><thead><tr>{['Signal Key','Direction','Grade','Entry Interval · ET','Events','Processed Outcome','Received Outcome','MFE','MAE'].map(h=><th scope="col" key={h}>{h}</th>)}</tr></thead><tbody>{filtered.map(s=>{const received=s.events.find(e=>e.event_type==='OSI_OUTCOME');return <tr key={s.key}><th scope="row">{s.key}</th><td>{s.side}</td><td>{s.grade}</td><td>{s.bucket}</td><td>{s.events.length}</td><td>{String(s.outcome?.primary_outcome??'None')}</td><td>{received?`${received.payload.primary_outcome} · ${received.processing_status}`:'None'}</td><td>{pct(typeof s.outcome?.final_mfe_pct==='number'?s.outcome.final_mfe_pct:null)}</td><td>{pct(typeof s.outcome?.final_mae_pct==='number'?s.outcome.final_mae_pct:null)}</td></tr>;})}</tbody></table></div></section>
    <section className={styles.panel}><h2>All Webhook Data</h2><p>Expand any event to inspect every payload and database metadata field. Delivery filters below affect this list only.</p><div className={styles.filters}><label>Event Type<select value={eventType} onChange={e=>setEventType(e.target.value)}><option value="">All Types</option>{['OSI_SIGNAL','OSI_CHECKPOINT','OSI_OUTCOME'].map(v=><option key={v}>{v}</option>)}</select></label><label>Delivery Status<select value={eventStatus} onChange={e=>setEventStatus(e.target.value)}><option value="">All Statuses</option><option>PROCESSED</option><option>FAILED</option></select></label><span>{visibleEvents.length} events shown</span></div>
      {visibleEvents.map(event=><details className={styles.event} key={event.id}><summary><strong>#{event.id} · {event.event_type}</strong><span>{String(event.payload.symbol)} · {event.payload.direction==='BEAR'?'Short':'Long'}</span><span className={event.processing_status==='FAILED'?styles.failed:styles.processed}>{event.processing_status}</span><time>{timestamp(event.received_at)}</time></summary><p className={styles.key}>{event.signal_key}</p>{event.error_message && <p className={styles.failed}>Recorded Error: {event.error_message}</p>}<h3>Payload</h3><Fields value={event.payload}/><details><summary>Database Metadata</summary><Fields value={Object.fromEntries(Object.entries(event).filter(([key])=>key!=='payload'))}/></details><details><summary>Full Original Row · JSON</summary><pre>{JSON.stringify(event,null,2)}</pre></details></details>)}
      {!visibleEvents.length && <p>No events match these filters.</p>}
    </section>
    <aside className={styles.notice}><strong>Data Observations</strong><p>Only one signal has signal, checkpoint, and outcome events in this snapshot. The first signal and checkpoint were received before their embedded market times; synthetic timestamps cannot establish delivery latency.</p><p>Event #11 failed with UNRESOLVED_WITH_RESOLUTION_TIMESTAMP, although its saved raw payload has null resolution timestamps. The raw record alone cannot explain the discrepancy. Its UNRESOLVED payload remains visible but is excluded from processed-outcome statistics.</p></aside>
  </div>;
}
