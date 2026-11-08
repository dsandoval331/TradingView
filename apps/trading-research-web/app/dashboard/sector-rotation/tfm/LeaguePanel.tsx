import styles from './tfm.module.css';

type Pick = {symbol: string; rank: number; challenger_rank: number; room_to_stop: number};
type Result = {
  k: number;
  missing: number;
  ambiguous: number;
  champion_lo: number | null;
  champion_hi: number | null;
  challenger_lo: number | null;
  challenger_hi: number | null;
  champion_hits: number;
  challenger_hits: number;
  winner: 'CHAMPION' | 'CHALLENGER' | 'TIE' | 'PENDING' | 'NO_PICKS';
};
export type LeagueMatch = {
  champion_id: string;
  monday: string;
  target_date: string;
  picks: Pick[];
  result: Result | null;
};
export type League = {matches: LeagueMatch[]; error: boolean};

const labels = {
  CHAMPION: 'Champion wins', CHALLENGER: 'Room to Target wins',
  TIE: 'Tie · half a point each', PENDING: 'Point pending', NO_PICKS: 'No qualifying picks',
};
const pct = (value: number) => `${value.toFixed(2)}%`;
function range(low: number | null, high: number | null) {
  if (low === null || high === null) return '—';
  return low === high ? pct(low) : `${pct(low)} to ${pct(high)}`;
}

function Standings({matches, title}: {matches: LeagueMatch[]; title: string}) {
  const results = matches.flatMap(match => match.result ? [match.result] : []);
  const scored = results.filter(r => ['CHAMPION', 'CHALLENGER', 'TIE'].includes(r.winner));
  const complete = results.filter(r => r.k > 0 && r.missing === 0);
  const slots = complete.reduce((sum, r) => sum + r.k, 0);
  return <section>
    <h4>{title}</h4>
    <p>{scored.length} scored weeks · 12 required before promotion review</p>
    <div className={styles.scroll}><table>
      <thead><tr><th scope="col">Ranking</th><th scope="col">League points</th>
        <th scope="col">Sum of weekly paper returns</th><th scope="col">Pattern hit rate</th></tr></thead>
      <tbody>{(['CHAMPION', 'CHALLENGER'] as const).map(side => {
        const points = scored.reduce((sum, r) => sum + (r.winner === side ? 1 : r.winner === 'TIE' ? .5 : 0), 0);
        const champion = side === 'CHAMPION';
        const low = complete.reduce((sum, r) => sum + ((champion ? r.champion_lo : r.challenger_lo) ?? 0), 0);
        const high = complete.reduce((sum, r) => sum + ((champion ? r.champion_hi : r.challenger_hi) ?? 0), 0);
        const hits = complete.reduce((sum, r) => sum + (champion ? r.champion_hits : r.challenger_hits), 0);
        return <tr key={side}>
          <th scope="row">{champion ? 'TFM champion' : 'Room to Target'}</th>
          <td>{points}</td><td>{slots ? range(low, high) : '—'}</td>
          <td>{slots ? `${pct(hits / slots * 100)} · ${hits}/${slots}` : '—'}</td>
        </tr>;
      })}</tbody>
    </table></div>
  </section>;
}

export default function LeaguePanel({league}: {league: League}) {
  return <section className={styles.panel} aria-label="TFM Ranking League">
    <h3>TFM Ranking League</h3>
    <p>Same qualifying pool, two frozen top-five lists. Room to Target ranks by Friday close-to-low distance divided by the 0.75% stop.</p>
    <p>Paper short at the session open, exit at Friday’s low, the 0.75% stop, or the session close. An open at or below Friday’s low earns zero for that slot. Returns are before costs.</p>
    {league.error ? <p role="alert">League standings could not be loaded.</p> : <>
      <Standings matches={league.matches.filter(m => m.monday === m.target_date)} title="Monday standings"/>
      {league.matches.some(m => m.monday !== m.target_date) &&
        <Standings matches={league.matches.filter(m => m.monday !== m.target_date)} title="Holiday Tuesday standings"/>}
      {league.matches.length === 0 && <p>First eligible target is November 16, 2026. Picks appear after the first paired freeze.</p>}
      {league.matches.map(match => {
        const r = match.result;
        const champion = match.picks.filter(p => p.rank <= 5).sort((a,b) => a.rank-b.rank);
        const challenger = match.picks.filter(p => p.challenger_rank <= 5);
        return <details key={match.champion_id}>
          <summary>{match.target_date} · {r ? labels[r.winner] : 'Awaiting session review'}</summary>
          <p>Champion picks: {champion.map(p => p.symbol).join(', ') || 'None'}</p>
          <p>Room to Target picks: {challenger.map(p => p.symbol).join(', ') || 'None'}</p>
          {r && !r.missing && r.k > 0 && <p>Champion {range(r.champion_lo,r.champion_hi)} · Room to Target {range(r.challenger_lo,r.challenger_hi)}</p>}
          {r && r.ambiguous > 0 && <p>{r.ambiguous} unique picks touched both exit levels. Return ranges reflect the unknown order.</p>}
          {r && r.missing > 0 && <p>{r.missing} unique picks are missing price data.</p>}
        </details>;
      })}
    </>}
  </section>;
}
