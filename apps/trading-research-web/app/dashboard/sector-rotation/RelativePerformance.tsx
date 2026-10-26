import type { Session } from './model';
import { directionalMoveStats } from './normal-move';
import styles from './tracker.module.css';
const pp=(n:number)=>`${n>0?'+':''}${n.toFixed(2)} pp`;
export default function RelativePerformance({sessions,timeline,symbol,selectedDate,onSelect}:{sessions:readonly Session[];timeline:readonly Session[];symbol:string;selectedDate:string|undefined;onSelect:(date:string)=>void}) {
  const stats=directionalMoveStats(sessions,symbol,selectedDate,60,5,'relative');
  const complete=stats.historySessions===stats.lookback&&stats.missingSessions===0;
  const up=complete&&stats.up.count>=stats.minDirectionDays?stats.up.mean:null;
  const down=complete&&stats.down.count>=stats.minDirectionDays?stats.down.mean:null;
  // Bars and both means share one linear scale; no clipping of unusually large moves.
  const extent=Math.max(.1,...timeline.map(d=>Math.abs(d.cells[symbol]?.relative??0)),Math.abs(up??0),Math.abs(down??0))*1.15;
  const position=(value:number)=>50-value/extent*50;
  return <section className={styles.relativeChart} aria-label="Relative daily performance">
    <div className={styles.miniTitle}>Relative daily performance<span>Last {timeline.length} visible sessions · Sector return minus SPY · percentage points</span></div>
    <div className={styles.relativeLegend}>
      <span className={styles.averageUp}><i/>Average up: {up===null?'unavailable':pp(up)} · {stats.up.count} days</span>
      <span className={styles.averageDown}><i/>Average down: {down===null?'unavailable':pp(down)} · {stats.down.count} days</span>
    </div>
    <div className={styles.relativePlot} aria-label="Daily returns relative to SPY with directional average lines">
      {timeline.map(day=>{const value=day.cells[symbol]?.relative??null;return <button key={day.date} title={`${day.date}: ${value===null?'unavailable':pp(value)}`} aria-label={`${day.date}: ${value===null?'unavailable':pp(value)}`} aria-pressed={day.date===selectedDate} onClick={()=>onSelect(day.date)}>
        {value!==null&&<span className={styles.relativeBar} style={{background:value>=0?'#35b995':'#e77687',height:`${Math.abs(value)/extent*50}%`,top:`${value>=0?position(value):50}%`}}/>}
        {value===null&&<span className={styles.srOnly}>Missing return</span>}
      </button>})}
      {up!==null&&<span className={`${styles.averageLine} ${styles.averageUp}`} style={{top:`${position(up)}%`}} aria-hidden="true"/>}
      {down!==null&&<span className={`${styles.averageLine} ${styles.averageDown}`} style={{top:`${position(down)}%`}} aria-hidden="true"/>}
    </div>
    <div className={styles.chartDates}><span>{timeline[0]?.date}</span><span>0 pp at center</span><span>{timeline.at(-1)?.date}</span></div>
    <p className={styles.relativeMeta}>Lines average positive and negative relative moves separately over the 60 sessions before {selectedDate??'the selected day'}; the selected day is excluded. These are relative-to-SPY averages, separate from the price-move averages above. {stats.startDate&&`${stats.startDate} through ${stats.endDate}.`} {(!complete||up===null||down===null)&&'Each line requires 60 complete prior relative returns and at least five days in that direction.'}</p>
  </section>;
}
