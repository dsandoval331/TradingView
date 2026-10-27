import type {Bar} from './model';
export const SWING_METHODS=[
 {id:1,name:'Sector rotation',status:'Configurable screen',description:'Use existing measures—relative performance versus SPY, Mansfield relative strength, ranks and EMAs—to define sector leadership. Screen sector ETFs and stocks for both pullback and breakout setups with broad-market alignment. Defaults: combined relative/Mansfield leadership, EMA20 reclaim, prior 20-session breakout, SPY EMA20/50 confirmation, and top 3 qualifying stocks per sector/direction. Daily repeats are labeled; exits remain outside this reference-price screen.'},
 {id:2,name:'RSI(2) trend pullback',status:'Retrospective screen',description:'Long screen: close above the 200-session SMA and RSI(2) below 5. Short screen: close below the 200-session SMA and RSI(2) above 95. Recent historical matches are recorded below. Closing prices are reference prices; strategy validation and executable entry/exit rules remain to be finalized.'},
 {id:3,name:'Volume and SPY-relative confirmation',status:'Calculated screen',description:'Long: volume strictly above its Sessions average, close above the prior session close, and relative-to-SPY heatmap green (at least +0.05 pp). Short: the same above-average volume, close below the prior session close, and relative-to-SPY heatmap red (at most −0.05 pp). The volume average includes the signal session and follows the heatmap Sessions setting. Every qualifying session is a separate signal; repeats are labeled. Calculated retrospective matches are reference-price observations, not a validated trading strategy.'},
] as const;
export type SwingMethodId=typeof SWING_METHODS[number]['id'];
export const swingMethodLabel=(id:SwingMethodId)=>{const method=SWING_METHODS.find(m=>m.id===id)!;return `#${method.id} · ${method.name}`;};
export type SwingSuggestion={id:string;methodId:SwingMethodId;methodVersion?:string;signalMetrics?:{rsi2:number;sma200:number};origin?:'retrospective'|'recorded';recordedAt?:string;calculated?:boolean;sector?:string;setup?:'pullback'|'breakout';sectorRank?:number;consecutiveDays?:number;symbol:string;suggestedDate:string;side:'long'|'short';entryPrice:number;reason:string};
const DAY=86400000;
function utcDay(date:string){
 const time=Date.parse(date+'T00:00:00Z');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(time)||new Date(time).toISOString().slice(0,10)!==date)throw new Error('Invalid suggestion date');
 return time;
}
export function marketDate(now=new Date()):string{const parts=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now).map(p=>[p.type,p.value]));return `${parts.year}-${parts.month}-${parts.day}`;}
/** Day 0 is the suggestion date. Count Mon–Fri strictly after it, including holidays. */
export function weekdaysSince(start:string,end:string):number{
 const from=utcDay(start),to=utcDay(end);if(to<from)return -1;
 const days=Math.round((to-from)/DAY),weeks=Math.floor(days/7);let count=weeks*5;
 for(let i=1;i<=days%7;i++){const day=new Date(from+i*DAY).getUTCDay();if(day!==0&&day!==6)count++;}
 return count;
}
export function addWeekdays(start:string,count:number):string{
 if(!Number.isInteger(count)||count<0)throw new Error('Invalid weekday count');
 let time=utcDay(start),remaining=count;
 while(remaining){time+=DAY;const day=new Date(time).getUTCDay();if(day!==0&&day!==6)remaining--;}
 return new Date(time).toISOString().slice(0,10);
}
export type SwingEntryBasis='signal_close'|'next_open';
export type SwingTradeRow=Omit<SwingSuggestion,'entryPrice'>&{entryPrice:number|null;entryBasis:SwingEntryBasis;entryDate:string|null;signalId:string;status:'active'|'archive';days:number;archivedDate:string|null;measurementEnd:string;priceDate:string|null;currentPrice:number|null;priceChange:number|null;percentChange:number|null;mfa:number|null;mae:number|null;mfaPercent:number|null;maePercent:number|null;excursionBars:number;missingOHLC:number};
export function trackSwingTrades(suggestions:readonly SwingSuggestion[],bars:readonly Bar[],asOfDate:string,entryBasis:SwingEntryBasis='signal_close'):SwingTradeRow[]{
 utcDay(asOfDate);const ids=new Set<string>();
 const calendar=[...new Set(bars.filter(b=>b.symbol==='SPY').map(b=>b.trade_date))].sort();
 return suggestions.flatMap(s=>{
  if(ids.has(s.id)||!s.id||!SWING_METHODS.some(m=>m.id===s.methodId)||!s.reason.trim()||!Number.isFinite(s.entryPrice)||s.entryPrice<=0||!['long','short'].includes(s.side)||!/^[A-Z][A-Z0-9.-]{0,9}$/.test(s.symbol))throw new Error('Invalid swing suggestion');
  ids.add(s.id);const age=weekdaysSince(s.suggestedDate,asOfDate);if(age<0)return [];
  const archived=age>15,end=archived?addWeekdays(s.suggestedDate,15):asOfDate;
  // Resolve against SPY's actual sessions, so weekends/holidays are skipped and missing opens are never bridged.
  const nextDate=entryBasis==='next_open'?calendar.find(date=>date>s.suggestedDate&&date<=end)??null:null;
  const opening=nextDate?bars.filter(b=>b.symbol===s.symbol&&b.trade_date===nextDate):[];
  if(opening.length>1)throw new Error('Duplicate swing price date');
  const rawOpen=opening[0]?.open;
  const entryPrice=entryBasis==='signal_close'?s.entryPrice:rawOpen!=null&&Number.isFinite(Number(rawOpen))&&Number(rawOpen)>0?Number(rawOpen):null;
  const entryDate=entryBasis==='signal_close'?s.suggestedDate:entryPrice===null?null:nextDate;
  const rows=bars.filter(b=>b.symbol===s.symbol&&b.trade_date>s.suggestedDate&&b.trade_date<=end).sort((a,b)=>a.trade_date.localeCompare(b.trade_date));
  const seen=new Set<string>();let mfa=0,mae=0,excursionBars=0,missingOHLC=0;
  let currentPrice:number|null=s.entryPrice,priceDate:string|null=s.suggestedDate;
  for(const b of rows){
   utcDay(b.trade_date);if(seen.has(b.trade_date))throw new Error('Duplicate swing price date');seen.add(b.trade_date);
   const close=Number(b.close);if(Number.isFinite(close)&&close>0){currentPrice=close;priceDate=b.trade_date;}
   if(b.high==null||b.low==null||!Number.isFinite(Number(b.high))||!Number.isFinite(Number(b.low))||Number(b.low)<=0||Number(b.high)<Number(b.low)||!Number.isFinite(close)||close<=0||Number(b.high)<close||Number(b.low)>close){missingOHLC++;continue;}
   const high=Number(b.high),low=Number(b.low);
   if(entryPrice!==null&&entryDate!==null&&b.trade_date>=entryDate){
    mfa=Math.max(mfa,s.side==='long'?high-entryPrice:entryPrice-low);
    mae=Math.max(mae,s.side==='long'?entryPrice-low:high-entryPrice);excursionBars++;
   }
  }
  // Day 0 has no post-entry excursion. Missing later bars are unavailable rather than fabricated zeros.
  const hasExcursion=entryPrice!==null&&((entryBasis==='signal_close'&&age===0)||excursionBars>0);
  if(age>0&&priceDate===s.suggestedDate){currentPrice=null;priceDate=null;}
  const change=currentPrice===null||entryPrice===null?null:currentPrice-entryPrice;
  return [{...s,id:entryBasis==='signal_close'?s.id:`${s.id}:next-open`,signalId:s.id,entryBasis,entryDate,entryPrice,status:archived?'archive' as const:'active' as const,days:archived?16:age,archivedDate:archived?addWeekdays(s.suggestedDate,16):null,measurementEnd:end,priceDate,currentPrice,priceChange:change,percentChange:change===null?null:change/entryPrice!*100,mfa:hasExcursion?mfa:null,mae:hasExcursion?mae:null,mfaPercent:hasExcursion?mfa/entryPrice!*100:null,maePercent:hasExcursion?mae/entryPrice!*100:null,excursionBars,missingOHLC}];
 });
}
