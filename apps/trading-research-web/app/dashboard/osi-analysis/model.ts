export type Payload = Record<string, unknown>;
export type WebhookEvent = { id: number; signal_key: string; event_type: string; processing_status: string; received_at: string; error_message: string | null; payload: Payload; [key: string]: unknown };
export type Signal = { key: string; side: string; grade: string; time: string | null; bucket: string; events: WebhookEvent[]; outcome: Payload | null; failed: number };
export function timeBucket(time: string | null, zone = 'America/Chicago'): string {
  if (!time || !Number.isFinite(Date.parse(time))) return 'Unknown Time';
  const parts = new Intl.DateTimeFormat('en-US', {timeZone: zone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23'}).formatToParts(new Date(time));
  const h = Number(parts.find(p => p.type === 'hour')?.value);
  const m = Math.floor(Number(parts.find(p => p.type === 'minute')?.value) / 5) * 5;
  const label = (minutes: number) => `${String(Math.floor(minutes / 60) % 24).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
  return `${label(h * 60 + m)}–${label(h * 60 + m + 5)}`;
}
export function buildSignals(events: WebhookEvent[]): Signal[] {
  const grouped = new Map<string, WebhookEvent[]>();
  for (const event of events) grouped.set(event.signal_key, [...(grouped.get(event.signal_key) ?? []), event]);
  return [...grouped].map(([key, rows]) => {
    const entry = rows.find(e => e.event_type === 'OSI_SIGNAL')?.payload;
    const direction = String(entry?.direction ?? rows[0].payload.direction ?? '');
    const candidate = entry?.signal_timestamp ?? key.split('|')[1];
    const time = typeof candidate === 'string' && Number.isFinite(Date.parse(candidate)) ? candidate : null;
    const grade = entry?.entry_grade;
    return {key, side: direction === 'BULL' ? 'Long' : direction === 'BEAR' ? 'Short' : 'Unknown', grade: typeof grade === 'string' && grade.trim() ? grade : 'Ungraded', time, bucket: timeBucket(time), events: rows, outcome: rows.find(e => e.event_type === 'OSI_OUTCOME' && e.processing_status === 'PROCESSED')?.payload ?? null, failed: rows.filter(e => e.processing_status === 'FAILED').length};
  }).sort((a,b) => (a.time ?? '').localeCompare(b.time ?? ''));
}
export function summarize(signals: Signal[]) {
  const accepted = signals.flatMap(s => s.outcome ? [s.outcome] : []);
  const count = (name: string) => accepted.filter(o => o.primary_outcome === name).length;
  const favorable = count('FAVORABLE'), adverse = count('ADVERSE'), both = count('BOTH'), unresolved = count('UNRESOLVED');
  const resolved = favorable + adverse + both;
  const avg = (key: string) => {const values = accepted.map(o => o[key]).filter((v): v is number => typeof v === 'number' && Number.isFinite(v)); return values.length ? values.reduce((a,b) => a+b,0)/values.length : null;};
  return {signals: signals.length, accepted: accepted.length, favorable, adverse, both, unresolved, noAccepted: signals.length - accepted.length, failed: signals.reduce((n,s) => n+s.failed,0), favorableRate: resolved ? favorable/resolved*100 : null, mfe: avg('final_mfe_pct'), mae: avg('final_mae_pct')};
}
export function breakdown(signals: Signal[], field: 'grade' | 'side' | 'bucket') {
  return [...new Set(signals.map(s => s[field]))].sort().map(label => ({label, ...summarize(signals.filter(s => s[field] === label))}));
}

/** Floor alert time to the preceding five-minute reporting slot. */
export function reportingSlot(time: string | null, zone = 'America/Chicago') {
  const interval = timeBucket(time, zone);
  return interval === 'Unknown Time' ? interval : interval.split('–')[0];
}
export function slotGradeRows(signals: Signal[], slot = '08:35') {
  const selected = signals.filter(s => reportingSlot(s.time) === slot);
  const grades = [...new Set(selected.map(s => s.grade))].sort();
  return grades.flatMap(grade => ['Long', 'Short'].map(side => ({
    grade, side, ...summarize(selected.filter(s => s.grade === grade && s.side === side))
  })));
}

export const sessionSections = [
  {name: 'Open', start: '08:30', end: '10:00', description: '8:30–10:00 AM CT · First 90 Minutes'},
  {name: 'Mid-Day', start: '10:00', end: '13:30', description: '10:00 AM–1:30 PM CT'},
  {name: 'Close', start: '13:30', end: '15:00', description: '1:30–3:00 PM CT · Last 90 Minutes'}
] as const;
export function sessionForTime(time: string | null) {
  const slot = reportingSlot(time);
  return sessionSections.find(s => slot >= s.start && slot < s.end)?.name ?? null;
}

/** All rolling sets of five consecutive five-minute slots in the regular session. */
export function rolling25Rows(signals: Signal[]) {
  const clock = (m: number) => `${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;
  const timed = signals.map(signal => ({signal, slot: reportingSlot(signal.time)}));
  return Array.from({length:74}, (_,i) => {
    const startMinute=510+i*5, start=clock(startMinute), end=clock(startMinute+25);
    const slots=Array.from({length:5},(_,j)=>clock(startMinute+j*5));
    const entries=timed.filter(s=>s.slot>=start && s.slot<end).map(s=>s.signal);
    return {start, end, slots, long:summarize(entries.filter(s=>s.side==='Long')), short:summarize(entries.filter(s=>s.side==='Short'))};
  });
}
export function rankRolling25(rows: ReturnType<typeof rolling25Rows>, side:'long'|'short', bottom=false) {
  return rows.filter(r=>r[side].favorableRate!==null)
    .sort((a,b)=>(bottom?1:-1)*((a[side].favorableRate??0)-(b[side].favorableRate??0)) || a.start.localeCompare(b.start)).slice(0,4);
}
