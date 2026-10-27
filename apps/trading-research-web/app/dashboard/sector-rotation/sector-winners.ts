import {buildSessions,SECTORS,HEAT_NEUTRAL_THRESHOLD,type Bar,type Metric,type Cell} from './model';
import {volumeSeries} from './volume';
import {closeEma} from './ema';
import type {SessionWindow} from './session-window';
export const WINNER_MEASURES:readonly Metric[]=['daily','relative','rank','rankChange','rsiRelative','mansfield'];
export type WinnerFeature={key:string;label:string;timing:'Before session'|'During session'};
export const WINNER_FEATURES:readonly WinnerFeature[]=[
 {key:'priorVolume',label:'Prior relative volume >1×',timing:'Before session'},
 {key:'priorDaily',label:'Prior daily return positive',timing:'Before session'},
 {key:'priorRelative',label:'Prior outperformance vs SPY',timing:'Before session'},
 {key:'priorEma20',label:'Prior close above EMA20',timing:'Before session'},
 {key:'priorEma50',label:'Prior close above EMA50',timing:'Before session'},
 {key:'priorStreak',label:'Prior green streak ≥2 (any measure)',timing:'Before session'},
 {key:'volume',label:'Winning-day relative volume >1×',timing:'During session'},
 {key:'relative',label:'Winning-day outperformance vs SPY',timing:'During session'},
 {key:'gap',label:'Positive opening gap',timing:'During session'},
 {key:'aboveAverage',label:'Daily return above prior positive average',timing:'During session'},
 {key:'closeHigh',label:'Close in upper half of daily range',timing:'During session'},
];
type Streak={green:number;red:number};
export type WinnerObservation={symbol:string;date:string;weekday:string;rank:number;selected:boolean;cell:Cell;prior:Cell|null;spy:number|null;priorGap:number|null;gap:number|null;rvol:number|null;priorRvol:number|null;ema20:number|null;ema50:number|null;positiveAverage:number|null;closePosition:number|null;streaks:Record<Metric,Streak>;priorStreaks:Record<Metric,Streak>;features:Record<string,boolean|null>};
const weekdayFormat=new Intl.DateTimeFormat('en-US',{weekday:'long',timeZone:'UTC'});
const positive=(value:number|null|undefined)=>value==null?null:value>0;
const numeric=(value:unknown)=>value==null||!Number.isFinite(Number(value))?null:Number(value);
const pct=(a:number|null,b:number|null)=>a!==null&&b!==null&&a>0&&b>0?(a/b-1)*100:null;
/** Exact 11-sector daily comparison. Historical inputs never use a later session. */
export function sectorWinnerHistory(bars:readonly Bar[],period:SessionWindow,topN:number,asOfDate:string){
 if(![1,2,3].includes(topN))throw new Error('Choose 1, 2 or 3 winners');
 const history=bars.filter(b=>b.trade_date<=asOfDate),sessions=buildSessions(history,SECTORS);
 const byBar=new Map(history.map(b=>[`${b.symbol}:${b.trade_date}`,b]));
 const volumes=Object.fromEntries(SECTORS.map(g=>[g.symbol,volumeSeries(history,sessions,g.symbol,period)]));
 const emas=Object.fromEntries(SECTORS.map(g=>[g.symbol,{fast:closeEma(sessions,g.symbol,20),slow:closeEma(sessions,g.symbol,50)}]));
 const runs=new Map<string,Record<Metric,Streak>>();const observations:WinnerObservation[]=[];
 const days=sessions.map((day,i)=>{
  const complete=day.complete;
  const candidates=complete?SECTORS.filter(g=>(day.cells[g.symbol].daily??-Infinity)>=HEAT_NEUTRAL_THRESHOLD).sort((a,b)=>day.cells[b.symbol].daily!-day.cells[a.symbol].daily!||a.symbol.localeCompare(b.symbol)).slice(0,topN):[];
  const selected=new Set(candidates.map(g=>g.symbol));const entries:WinnerObservation[]=[];
  for(const group of SECTORS){
   const symbol=group.symbol,cell=day.cells[symbol],prior=i?sessions[i-1].cells[symbol]:null;
   const priorStreaks=structuredClone(runs.get(symbol)??Object.fromEntries(WINNER_MEASURES.map(m=>[m,{green:0,red:0}])) as Record<Metric,Streak>);
   const streaks=Object.fromEntries(WINNER_MEASURES.map(m=>{const v=cell[m],signal=v===null?null:m==='rank'?6-v:v;return [m,{green:signal!==null&&signal>1e-10?priorStreaks[m].green+1:0,red:signal!==null&&signal< -1e-10?priorStreaks[m].red+1:0}];})) as Record<Metric,Streak>;runs.set(symbol,streaks);
   if(!complete)continue;
   const bar=byBar.get(`${symbol}:${day.date}`),previousBar=i?byBar.get(`${symbol}:${sessions[i-1].date}`):null;
   const gap=pct(numeric(bar?.open),prior?.close??null),priorGap=pct(numeric(previousBar?.open),i>1?sessions[i-2].cells[symbol].close:null);
   const ratio=(date:string)=>{const v=volumes[symbol].get(date);return v?.volume!=null&&v.average!=null&&v.average>0?v.volume/v.average:null;};
   const rvol=ratio(day.date),priorRvol=i?ratio(sessions[i-1].date):null;
   const ema20=emas[symbol].fast.get(day.date)??null,ema50=emas[symbol].slow.get(day.date)??null;
   const before=sessions.slice(Math.max(0,i-60),i).map(d=>d.cells[symbol].daily);
   const positives=before.filter((v):v is number=>v!==null&&v>0);
   const positiveAverage=before.length===60&&before.every(v=>v!==null)&&positives.length>=5?positives.reduce((a,b)=>a+b,0)/positives.length:null;
   const high=numeric(bar?.high),low=numeric(bar?.low),close=cell.close;
   const closePosition=high!==null&&low!==null&&close!==null&&low>0&&high>low&&close>=low&&close<=high?(close-low)/(high-low):null;
   const prevEma20=i?emas[symbol].fast.get(sessions[i-1].date):null,prevEma50=i?emas[symbol].slow.get(sessions[i-1].date):null;
   const entry:WinnerObservation={symbol,date:day.date,weekday:weekdayFormat.format(new Date(day.date+'T12:00:00Z')),rank:cell.rank!,selected:selected.has(symbol),cell,prior,spy:day.spy,gap,priorGap,rvol,priorRvol,ema20,ema50,positiveAverage,closePosition,streaks,priorStreaks,features:{
    priorVolume:priorRvol===null?null:priorRvol>1,priorDaily:positive(prior?.daily),priorRelative:positive(prior?.relative),priorEma20:prevEma20==null||prior?.close==null?null:prior.close>prevEma20,priorEma50:prevEma50==null||prior?.close==null?null:prior.close>prevEma50,priorStreak:prior===null||!WINNER_MEASURES.some(m=>prior[m]!==null)?null:WINNER_MEASURES.some(m=>priorStreaks[m].green>=2),volume:rvol===null?null:rvol>1,relative:positive(cell.relative),gap:positive(gap),aboveAverage:positiveAverage===null?null:cell.daily!>positiveAverage,closeHigh:closePosition===null?null:closePosition>.5}};
   observations.push(entry);if(entry.selected)entries.push(entry);
  }
  entries.sort((a,b)=>b.cell.daily!-a.cell.daily!||a.symbol.localeCompare(b.symbol));
  return {date:day.date,complete,winners:entries};
 });
 return {days,observations};
}
export function winnerFeatureFrequency(observations:readonly WinnerObservation[]){
 return WINNER_FEATURES.map(feature=>{const count=(selected:boolean)=>{const values=observations.filter(o=>o.selected===selected&&o.features[feature.key]!==null);const yes=values.filter(o=>o.features[feature.key]).length;return {yes,total:values.length,percent:values.length?100*yes/values.length:null};};return {...feature,winners:count(true),others:count(false)};});
}
export function winnerCsv(rows:readonly WinnerObservation[]){
 const headers=['date','weekday','symbol','rank','daily_pct','relative_pp','spy_pct','rvol','prior_rvol','opening_gap_pct','prior_opening_gap_pct','prior_daily_pct','prior_relative_pp','ema20','ema50','rsi14','rsi_vs_spy','mansfield','rank_change','return5_pct','return20_pct','prior_positive_average_pct','close_range_position',...WINNER_MEASURES.flatMap(m=>[`${m}_prior_green_streak`,`${m}_prior_red_streak`,`${m}_ending_green_streak`,`${m}_ending_red_streak`])];
 const escape=(v:unknown)=>'"'+String(v??'').replaceAll('"','""')+'"';
 return [headers,...rows.map(o=>[o.date,o.weekday,o.symbol,o.rank,o.cell.daily,o.cell.relative,o.spy,o.rvol,o.priorRvol,o.gap,o.priorGap,o.prior?.daily,o.prior?.relative,o.ema20,o.ema50,o.cell.rsi,o.cell.rsiRelative,o.cell.mansfield,o.cell.rankChange,o.cell.five,o.cell.twenty,o.positiveAverage,o.closePosition,...WINNER_MEASURES.flatMap(m=>[o.priorStreaks[m].green,o.priorStreaks[m].red,o.streaks[m].green,o.streaks[m].red])])].map(row=>row.map(escape).join(',')).join('\n');
}

/** Most frequent positive conditions; typical values describe matching winners, not all winners. */
export function commonWinnerCharacteristics(observations:readonly WinnerObservation[],limit=3){
 const winners=observations.filter(o=>o.selected);
 const numericValue=(key:string,o:WinnerObservation):number|null=>{
  switch(key){
   case 'priorVolume':return o.priorRvol;
   case 'priorDaily':return o.prior?.daily??null;
   case 'priorRelative':return o.prior?.relative??null;
   case 'priorStreak':return Math.max(...WINNER_MEASURES.map(m=>o.priorStreaks[m].green));
   case 'volume':return o.rvol;
   case 'relative':return o.cell.relative;
   case 'gap':return o.gap;
   case 'aboveAverage':return o.positiveAverage!==null&&o.positiveAverage>0?o.cell.daily!/o.positiveAverage:null;
   case 'closeHigh':return o.closePosition===null?null:100*o.closePosition;
   default:return null;
  }
 };
 const summary=winnerFeatureFrequency(observations).filter(f=>f.winners.yes>0).map(f=>{
  const matches=winners.filter(o=>o.features[f.key]===true);
  const values=matches.map(o=>numericValue(f.key,o)).filter((v):v is number=>v!==null&&Number.isFinite(v)).sort((a,b)=>a-b);
  const median=values.length?(values[Math.floor((values.length-1)/2)]+values[Math.floor(values.length/2)])/2:null;
  const typical=f.key==='priorEma20'?'Above EMA20':f.key==='priorEma50'?'Above EMA50':median===null?'N/A':`${median.toFixed(2)}${['volume','priorVolume','aboveAverage'].includes(f.key)?'×':f.key==='priorStreak'?' sessions':f.key==='relative'||f.key==='priorRelative'?' pp':'%'}`;
  return {...f,typical,median,typicalCount:values.length,coverage:winners.length?100*f.winners.total/winners.length:0};
 });
 const groups=(['Before session','During session'] as const).map(timing=>({timing,items:summary.filter(f=>f.timing===timing).sort((a,b)=>b.winners.yes-a.winners.yes||b.winners.percent!-a.winners.percent!||a.key.localeCompare(b.key)).slice(0,limit)}));
 const counts=new Map<string,number>();for(const o of winners)counts.set(o.weekday,(counts.get(o.weekday)??0)+1);
 const weekdays=[...counts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));const max=weekdays[0]?.[1]??0;
 return {groups,winnerCount:winners.length,weekdays:weekdays.filter(([,n])=>n===max).map(([day,count])=>({day,count,percent:100*count/winners.length}))};
}
