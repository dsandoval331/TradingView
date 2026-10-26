import type { Session } from './model';
import { streakStats } from './streaks';
import styles from './tracker.module.css';
export default function StreakSummary({sessions,symbol,date,measure}:{sessions:readonly Session[];symbol:string;date:string|undefined;measure:'daily'|'relative'}) {
  const stats=streakStats(sessions,symbol,date,measure);
  return <section className={styles.normalMove} aria-label="Consecutive day streaks">
    <h3>Consecutive day streaks</h3>
    <p className={styles.normalMeta}>Prior {stats.lookback} sessions · Selected day excluded · {measure==='relative'?'Relative to SPY':'Daily price return'}</p>
    <table><thead><tr><th scope="col">Direction</th><th scope="col">Average days in a row</th><th scope="col">Longest streak (days)</th><th scope="col">Completed streaks</th></tr></thead><tbody>
      <tr><th scope="row" className={styles.averageUp}>Green days</th><td>{stats.green.mean===null?'—':stats.green.mean.toFixed(2)}</td><td>{stats.green.longest??'—'}</td><td>{stats.green.count}</td></tr>
      <tr><th scope="row" className={styles.averageDown}>Red days</th><td>{stats.red.mean===null?'—':stats.red.mean.toFixed(2)}</td><td>{stats.red.longest??'—'}</td><td>{stats.red.count}</td></tr>
    </tbody></table>
    <p className={styles.normalNote}>{measure==='relative'?'Green = outperforming SPY; red = underperforming SPY.':'Green = positive daily price return; red = negative daily price return.'} Flat days break a streak. Only fully observed, completed streaks inside the window enter the average and longest streak; runs touching either boundary or a missing observation are excluded. — means no eligible streaks.</p>
    <p className={styles.normalMeta}>{stats.startDate?`${stats.startDate} through ${stats.endDate} · `:''}{stats.historySessions} sessions · {stats.missingSessions} missing{stats.historySessions<stats.lookback?' · Limited history':''}</p>
  </section>;
}
