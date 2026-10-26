import type { Session } from './model';
type MeanStreak={mean:number|null;count:number};
export type StreakStats={green:MeanStreak;red:MeanStreak;historySessions:number;missingSessions:number;lookback:number;startDate:string|null;endDate:string|null};
export function streakStats(sessions:readonly Session[],symbol:string,date:string|undefined,measure:'daily'|'relative'='daily',lookback=60):StreakStats {
  if(!Number.isInteger(lookback)||lookback<1)throw new Error('Invalid streak window');
  const index=date?sessions.findIndex(s=>s.date===date):-1;
  const baseline=index<0?[]:sessions.slice(Math.max(0,index-lookback),index);
  const lengths:{green:number[];red:number[]}={green:[],red:[]};
  let sign=0,length=0,leftKnown=false,missingSessions=0;
  // A run is counted only when both its start and end are observed inside the window.
  for(const day of baseline){
    const value=day.cells[symbol]?.[measure];
    if(value==null||!Number.isFinite(value)){missingSessions++;sign=0;length=0;leftKnown=false;continue;}
    const next=Math.abs(value)<=1e-10?0:value>0?1:-1;
    if(length&&next===sign){length++;continue;}
    if(length&&leftKnown)lengths[sign>0?'green':'red'].push(length);
    const precedingKnown:boolean=length>0||leftKnown;
    sign=next;length=next===0?0:1;
    leftKnown=next===0?true:precedingKnown;
  }
  // The trailing run is still unfinished at the window end and is excluded.
  const average=(runs:number[]):MeanStreak=>({mean:runs.length?runs.reduce((a,b)=>a+b,0)/runs.length:null,count:runs.length});
  return {green:average(lengths.green),red:average(lengths.red),historySessions:baseline.length,missingSessions,lookback,startDate:baseline[0]?.date??null,endDate:baseline.at(-1)?.date??null};
}
