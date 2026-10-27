import type {SwingTradeRow} from './swing-trades';
export type Mean={value:number|null;count:number};
function mean(values:readonly (number|null)[]):Mean{
 const valid=values.filter((v):v is number=>v!==null&&Number.isFinite(v));
 return {value:valid.length?valid.reduce((sum,value)=>sum+value,0)/valid.length:null,count:valid.length};
}
export type SwingMethodFilter=1|2|'both';
export function filterSwingMethods<T extends {methodId:1|2}>(rows:readonly T[],method:SwingMethodFilter):T[]{
 return rows.filter(row=>method==='both'||row.methodId===method);
}
/** Equal-weight per signal for one selected entry basis. Price returns retain their raw sign. */
export function swingStatistics(rows:readonly SwingTradeRow[]){
 return (['long','short','both'] as const).map(group=>{
  const plays=rows.filter(row=>group==='both'||row.side===group);
  const returns=plays.map(row=>row.percentChange).filter((n):n is number=>n!==null&&Number.isFinite(n));
  const complete=plays.filter(row=>row.missingOHLC===0);
  return {group,count:plays.length,pricedCount:returns.length,
   mfe:mean(complete.map(row=>row.mfa)),mfePercent:mean(complete.map(row=>row.mfaPercent)),
   mae:mean(complete.map(row=>row.mae)),maePercent:mean(complete.map(row=>row.maePercent)),
   change:mean(returns),up:mean(returns.filter(n=>n>0)),down:mean(returns.filter(n=>n<0))};
 });
}

/** Pool individual signals directly; a signal matching both methods contributes once per method. */
export function swingStatisticsByMethod(rows:readonly SwingTradeRow[]){
 return ([1,2,'both'] as const).map(method=>({method,groups:swingStatistics(filterSwingMethods(rows,method))}));
}
