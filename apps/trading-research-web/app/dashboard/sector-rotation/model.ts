export type Group = {symbol:string;name:string;short:string;kind?:'etf'|'basket';members?:readonly string[];note?:string};
export const SECTORS = [
  { symbol: 'XLK', name: 'Technology', short: 'Technology' },
  { symbol: 'XLV', name: 'Healthcare', short: 'Healthcare' },
  { symbol: 'XLP', name: 'Consumer Staples', short: 'Staples' },
  { symbol: 'XLY', name: 'Consumer Discretionary', short: 'Discretionary' },
  { symbol: 'XLF', name: 'Financials', short: 'Financials' },
  { symbol: 'XLI', name: 'Industrials', short: 'Industrials' },
  { symbol: 'XLE', name: 'Energy', short: 'Energy' },
  { symbol: 'XLB', name: 'Materials', short: 'Materials' },
  { symbol: 'XLU', name: 'Utilities', short: 'Utilities' },
  { symbol: 'XLRE', name: 'Real Estate', short: 'Real Estate' },
  { symbol: 'XLC', name: 'Communication Services', short: 'Communication' },
] as const;
export type Bar = { symbol: string; trade_date: string; close: number | string; open?: number | string | null; high?: number | string | null; low?: number | string | null; volume: number | string; collected_at?: string };
export type Cell = { symbol: string; close: number | null; daily: number | null; relative: number | null; five: number | null; twenty: number | null; rank: number | null; rankChange: number | null; rsi:number|null;spyRsi:number|null;rsiRelative:number|null;mansfield:number|null };
export type Session = { date: string; spy: number | null; cells: Record<string, Cell>; complete: boolean; leader: string | null; laggard: string | null; spread: number | null };
export type Metric = 'relative' | 'daily' | 'rank' | 'rankChange' | 'rsiRelative' | 'mansfield';
const valid = (v: number) => Number.isFinite(v) && v > 0;
/** Wilder RSI: 14 price changes, SMA seed, then Wilder smoothing. Flat seed is neutral 50. */
export function rsiSeries(values:readonly (number|null)[],period=14):(number|null)[]{
 if(!Number.isInteger(period)||period<1)throw new Error('Invalid RSI period');
 let previous:number|null=null,gain=0,loss=0,count=0;
 return values.map(value=>{
  if(value===null||!valid(value)){previous=null;gain=0;loss=0;count=0;return null;}
  if(previous===null){previous=value;return null;}
  const delta=value-previous;previous=value;
  if(count<period){gain+=Math.max(0,delta);loss+=Math.max(0,-delta);count++;if(count<period)return null;gain/=period;loss/=period;}
  else{gain=(gain*(period-1)+Math.max(0,delta))/period;loss=(loss*(period-1)+Math.max(0,-delta))/period;}
  return loss===0?(gain===0?50:100):100-100/(1+gain/loss);
 });
}
/** Daily Mansfield variant: 100 * (close/SPY close / SMA200(close/SPY close) - 1). */
export function mansfieldSeries(values:readonly (number|null)[],benchmark:readonly (number|null)[],period=200):(number|null)[]{
 if(!Number.isInteger(period)||period<1)throw new Error('Invalid Mansfield period');
 let window:number[]=[],sum=0;
 return values.map((value,i)=>{
  const ref=benchmark[i];
  if(value==null||ref==null||!valid(value)||!valid(ref)){window=[];sum=0;return null;}
  const ratio=value/ref;window.push(ratio);sum+=ratio;if(window.length>period)sum-=window.shift()!;
  return window.length===period?(ratio/(sum/period)-1)*100:null;
 });
}
export function buildSessions(bars: Bar[], groups: readonly Group[] = SECTORS): Session[] {
  const prices = new Map<string, Map<string, number>>();
  for (const bar of bars) {
    const value = Number(bar.close);
    if (!valid(value)) continue;
    const dates = prices.get(bar.symbol) ?? new Map<string, number>();
    if (dates.has(bar.trade_date)) throw new Error('Duplicate sector/date in published observations');
    dates.set(bar.trade_date, value); prices.set(bar.symbol, dates);
  }
  // SPY provides the session reference. Never bridge a missing sector bar.
  const dates = [...(prices.get('SPY')?.keys() ?? [])].sort();
  const change = (symbol: string, i: number, h: number): number | null => {
    if (i < h) return null;
    const series = prices.get(symbol);
    for (let j = i - h; j <= i; j++) if (!series?.has(dates[j])) return null;
    return (series!.get(dates[i])! / series!.get(dates[i-h])! - 1) * 100;
  };
  const spyCloses=dates.map(date=>prices.get('SPY')?.get(date)??null);
  const spyRsi=rsiSeries(spyCloses);
  const indicators=new Map(groups.map(group=>{const closes=dates.map(date=>prices.get(group.symbol)?.get(date)??null);return [group.symbol,{rsi:rsiSeries(closes),mansfield:mansfieldSeries(closes,spyCloses)}] as const;}));
  const output: Session[] = [];
  for (let i = 0; i < dates.length; i++) {
    const spy = change('SPY', i, 1);
    const cells: Record<string, Cell> = {};
    for (const sector of groups) {
      const daily = change(sector.symbol, i, 1);
      const relative = daily === null || spy === null ? null : daily - spy;
      cells[sector.symbol] = { symbol: sector.symbol, close: prices.get(sector.symbol)?.get(dates[i]) ?? null, daily, relative, five: change(sector.symbol, i, 5), twenty: change(sector.symbol, i, 20), rank: null, rankChange: null,rsi:indicators.get(sector.symbol)!.rsi[i],spyRsi:spyRsi[i],rsiRelative:indicators.get(sector.symbol)!.rsi[i]===null||spyRsi[i]===null?null:indicators.get(sector.symbol)!.rsi[i]!-spyRsi[i]!,mansfield:indicators.get(sector.symbol)!.mansfield[i] };
    }
    const ordered = Object.values(cells).filter(c => c.daily !== null).sort((a,b) => b.daily! - a.daily! || a.symbol.localeCompare(b.symbol));
    const complete = ordered.length === groups.length;
    // Ranks require the complete universe; ties receive competition ranks.
    if (complete) for (const c of ordered) {
      c.rank = 1 + ordered.filter(other => other.daily! > c.daily! + 1e-10).length;
      const previous = output[i-1]?.cells[c.symbol]?.rank;
      c.rankChange = previous == null ? null : previous - c.rank;
    }
    const leaders = ordered.filter(c => c.rank === 1);
    const low = complete ? Math.min(...ordered.map(c => c.daily!)) : null;
    const laggards = complete ? ordered.filter(c => Math.abs(c.daily! - low!) < 1e-10) : [];
    output.push({ date: dates[i], spy, cells, complete, leader: complete && leaders.length === 1 ? leaders[0].symbol : null, laggard: laggards.length === 1 ? laggards[0].symbol : null, spread: complete ? ordered[0].daily! - ordered[ordered.length-1].daily! : null });
  }
  return output;
}
export function leadershipNote(session: Session, previous?: Session, groups: readonly Group[] = SECTORS): string {
  if (!session.complete) return 'Incomplete comparison — one or more sector returns are unavailable.';
  if (session.spread !== null && session.spread < 0.25) return 'Mixed leadership — sector returns were within 0.25 percentage points.';
  if (!session.leader) return 'Shared lead — multiple sectors tied for the strongest daily return.';
  const name = groups.find(s => s.symbol === session.leader)!.name;
  if (!previous?.complete || !previous.leader) return `${name} led the session.`;
  if (previous.leader === session.leader) return `${name} retained the daily lead.`;
  const before = groups.find(s => s.symbol === previous.leader)!.name;
  return `${name} took the daily lead from ${before}.`;
}
export function metricValue(cell: Cell, metric: Metric): number | null { return cell[metric]; }
export function formatValue(value: number | null, metric: Metric): string {
  if (value === null) return '—';
  if (metric === 'rank') return `#${value}`;
  if (metric === 'rankChange') return value > 0 ? `↑${value}` : value < 0 ? `↓${-value}` : '0';
  const rounded = Math.abs(value) < 0.005 ? 0 : value;
  return `${rounded > 0 ? '+' : ''}${rounded.toFixed(2)}${metric === 'relative'||metric==='rsiRelative' ? '' : '%'}`;
}
export const HEAT_NEUTRAL_THRESHOLD=0.05;
export function heat(value: number | null, metric: Metric, groupCount = 11): string {
  if (value === null) return 'rgba(148,163,184,.06)';
  const score = metric === 'rank' ? ((groupCount+1)/2-value)/Math.max(1,groupCount/4) : metric === 'rankChange' ? value/4 : metric==='rsiRelative'?value/10:metric==='mansfield'?value/5:value;
  const strength = Math.min(Math.abs(score)/1.5, 1);
  if (Math.abs(score) < HEAT_NEUTRAL_THRESHOLD) return 'rgba(148,163,184,.10)';
  return score > 0 ? `rgba(31,171,137,${.13+.48*strength})` : `rgba(222,84,104,${.13+.48*strength})`;
}
export function exportCsv(sessions: Session[], groups: readonly Group[] = SECTORS): string {
  const lines = ['date,symbol,sector,daily_return_pct,spy_return_pct,relative_return_pp,rank,rank_change,return_5_sessions_pct,return_20_sessions_pct,rsi_14,spy_rsi_14,rsi_difference_points,mansfield_rs_200_pct'];
  for (const day of sessions) for (const s of groups) {
    const c=day.cells[s.symbol];
    lines.push([day.date,s.symbol,s.name,c.daily,day.spy,c.relative,c.rank,c.rankChange,c.five,c.twenty,c.rsi,c.spyRsi,c.rsiRelative,c.mansfield].map(x=>x??'').join(','));
  }
  return lines.join('\r\n');
}
