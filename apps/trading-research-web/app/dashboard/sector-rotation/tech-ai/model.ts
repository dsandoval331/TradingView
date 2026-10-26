import type { Bar, Group } from '../model';
import definition from './groups.json' with { type: 'json' };
export const TECH_GROUPS: readonly Group[] = definition.groups as Group[];
/** Current fixed constituents, equal daily weights. Not a point-in-time index.
 * An incomplete member/session interrupts the index rather than being filled.
 */
export function buildTechBars(raw: Bar[]): Bar[] {
  const prices = new Map<string,Map<string,number>>();
  for (const row of raw) {
    const series=prices.get(row.symbol)??new Map<string,number>();
    const c=Number(row.close);
    if (!Number.isFinite(c)||c<=0) continue;
    if(series.has(row.trade_date)) throw new Error('Duplicate tech constituent/date');
    series.set(row.trade_date,c); prices.set(row.symbol,series);
  }
  const dates=[...(prices.get('SPY')?.keys()??[])].sort();
  const result:Bar[]=raw.filter(r=>r.symbol==='SPY'||r.symbol==='IGV');
  for (const group of TECH_GROUPS.filter(g=>g.kind==='basket')) {
    let index:number|null=null;
    for (let i=0;i<dates.length;i++) {
      const today=dates[i], previous=dates[i-1];
      const available=group.members!.every(s=>prices.get(s)?.has(today));
      if (!available) {index=null;continue;}
      if(index===null) index=100;
      else {
        const complete=previous&&group.members!.every(s=>prices.get(s)?.has(previous));
        if(!complete){index=null;continue;}
        const daily=group.members!.reduce((sum,s)=>sum+prices.get(s)!.get(today)!/prices.get(s)!.get(previous)!-1,0)/group.members!.length;
        index*=1+daily;
      }
      result.push({symbol:group.symbol,trade_date:today,close:index,volume:0});
    }
  }
  return result;
}
