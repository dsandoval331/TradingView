import type { NormalMoveStats } from './normal-move';
import styles from './tracker.module.css';
const percent=(n:number|null)=>n===null?'—':`${n>0?'+':''}${n.toFixed(2)}%`;
export default function NormalMove({stats}:{stats:NormalMoveStats}) {
  const direction=stats.direction==='up'?'up':'down';
  const delta=stats.percentVsAverage;
  const assessment=stats.ratio===null?null:delta!==null&&Math.abs(delta)<0.05?'Approximately equal to its average move':`${Math.abs(delta!).toFixed(1)}% ${delta!>0?'larger':'smaller'} than the average ${direction} day`;
  return <section className={styles.normalMove} aria-label="Directional average daily move">
    <h3>Move vs directional average</h3>
    <p className={styles.normalMeta}>Prior {stats.lookback} trading sessions · Selected day excluded</p>
    <table><caption className={styles.srOnly}>Arithmetic average positive and negative daily price returns before the selected session.</caption><thead><tr><th scope="col">Direction</th><th scope="col">Average move</th><th scope="col">Days</th></tr></thead><tbody><tr><th scope="row">Up days</th><td>{percent(stats.up.mean)}</td><td>{stats.up.count}</td></tr><tr><th scope="row">Down days</th><td>{percent(stats.down.mean)}</td><td>{stats.down.count}</td></tr></tbody></table>
    {assessment?<div className={styles.normalAssessment}><strong>{stats.ratio!.toFixed(2)}× average {direction}-day move</strong><span>{assessment}</span></div>:<p className={styles.normalMessage}>{stats.reason==='no_session'?'Choose a session to compare its move.':stats.reason==='no_return'?'The selected session has no valid daily return.':stats.reason==='flat'?'Flat session — neither an up-day nor a down-day comparison applies.':stats.reason==='small_sample'?`Not enough ${direction} days for comparison: at least ${stats.minDirectionDays} are required.`:`Limited history — comparison requires ${stats.lookback} complete prior daily returns. ${stats.validSessions} of ${stats.historySessions} available sessions have valid returns.`}</p>}
    <p className={styles.normalMeta}>{stats.startDate&&stats.endDate?`${stats.startDate} through ${stats.endDate} · `:''}{stats.flatDays} flat · {stats.missingSessions} missing</p>
    <p className={styles.normalNote}>Uses daily close-to-close price returns, rather than returns relative to SPY. Down moves are compared by size: −2% is twice a −1% average down day. This is descriptive context, not a forecast.</p>
  </section>;
}
