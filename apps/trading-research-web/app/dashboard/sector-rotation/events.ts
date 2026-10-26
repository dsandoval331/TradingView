import type {Group,Metric,Session} from './model';
import {closeEma} from './ema';
import {emaPeriod,type ChartLine} from './chart-lines';
const EPS=1e-10;
export type EventStreak={symbol:string;green:number;red:number;longestGreen:number;longestRed:number;available:boolean};
export type AverageEvent={symbol:string;side:'Long'|'Short';value:number;average:number};
export type DailyEvents={date:string;ema:{symbol:string;days:number;close:number;ema:number}[];averages:AverageEvent[];streaks:EventStreak[];rankUp:{symbols:string[];change:number}|null;rankDown:{symbols:string[];change:number}|null;baselineUnavailable:number};
/** End-of-day observations only. Future rows never enter baselines, runs, or records. */
export function dailyEvents(sessions:readonly Session[],groups:readonly Group[],metric:Metric,line:ChartLine):DailyEvents[]{
 const period=emaPeriod(line);
 const emas=Object.fromEntries(groups.map(g=>[g.symbol,period?closeEma(sessions,g.symbol,period):null]));
 const runs=new Map<string,{ema:number;green:number;red:number;longestGreen:number;longestRed:number}>();
 return sessions.map((day,index)=>{
  const event:DailyEvents={date:day.date,ema:[],averages:[],streaks:[],rankUp:null,rankDown:null,baselineUnavailable:0};
  for(const group of groups){
   const symbol=group.symbol,c=day.cells[symbol];
   const state=runs.get(symbol)??{ema:0,green:0,red:0,longestGreen:0,longestRed:0};runs.set(symbol,state);
   const raw=c?.[metric];
   const value=raw!=null&&Number.isFinite(raw)?raw:null,average=emas[symbol]?.get(day.date)??null;
   // Match exactly when the selected metric's heatmap cell can display a superscript.
   const below=value!==null&&c?.close!=null&&average!==null&&c.close<average;
   state.ema=below?state.ema+1:0;
   if(below)event.ema.push({symbol,days:state.ema,close:c.close!,ema:average!});
   // Rank colors mean better/worse than the universe midpoint; other metrics use sign.
   const signal=value===null?null:metric==='rank'?(groups.length+1)/2-value:value;
   state.green=signal!==null&&signal>EPS?state.green+1:0;
   state.red=signal!==null&&signal< -EPS?state.red+1:0;
   state.longestGreen=Math.max(state.longestGreen,state.green);state.longestRed=Math.max(state.longestRed,state.red);
   event.streaks.push({symbol,green:state.green,red:state.red,longestGreen:state.longestGreen,longestRed:state.longestRed,available:value!==null});
   const baseline=sessions.slice(Math.max(0,index-60),index).map(s=>s.cells[symbol]?.[metric]??null);
   if(value===null||baseline.length<60||baseline.some(v=>v===null||!Number.isFinite(v))){event.baselineUnavailable++;continue;}
   const values=baseline as number[];
   if(metric==='rank'){
    const mean=values.reduce((a,b)=>a+b,0)/60;
    if(Math.abs(value-mean)>EPS)event.averages.push({symbol,side:value<mean?'Long':'Short',value,average:mean});
   }else{
    const direction=value>EPS?1:value< -EPS?-1:0;
    const matching=values.filter(v=>direction>0?v>EPS:direction<0?v< -EPS:false);
    if(!direction)continue;
    if(matching.length<5){event.baselineUnavailable++;continue;}
    const mean=matching.reduce((a,b)=>a+b,0)/matching.length;
    if(direction>0?value>mean+EPS:value<mean-EPS)event.averages.push({symbol,side:direction>0?'Long':'Short',value,average:mean});
   }
  }
  if(day.complete){
   const changes=groups.map(g=>({symbol:g.symbol,value:day.cells[g.symbol]?.rankChange??null}));
   if(changes.every(c=>c.value!==null)){
    const up=Math.max(...changes.map(c=>c.value!)),down=Math.min(...changes.map(c=>c.value!));
    if(up>0)event.rankUp={change:up,symbols:changes.filter(c=>c.value===up).map(c=>c.symbol)};
    if(down<0)event.rankDown={change:down,symbols:changes.filter(c=>c.value===down).map(c=>c.symbol)};
   }
  }
  return event;
 });
}
