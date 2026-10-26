import type { Bar, Session } from './model';
export type Candle = {date:string;open:number;high:number;low:number;close:number};
/** One slot per heatmap session; never invent missing wicks. */
export function candleSeries(bars:readonly Bar[],sessions:readonly Session[],symbol:string):(Candle|null)[] {
 const byDate=new Map<string,Bar>();
 for(const bar of bars)if(bar.symbol===symbol){if(byDate.has(bar.trade_date))throw new Error('Duplicate candle date');byDate.set(bar.trade_date,bar);}
 return sessions.map(session=>{
  const row=byDate.get(session.date);
  if(!row||[row.open,row.high,row.low,row.close].some(v=>v==null))return null;
  const [open,high,low,close]=[row.open,row.high,row.low,row.close].map(Number);
  if(![open,high,low,close].every(v=>Number.isFinite(v)&&v>0)||low>Math.min(open,close)||high<Math.max(open,close))return null;
  return {date:session.date,open,high,low,close};
 });
}
