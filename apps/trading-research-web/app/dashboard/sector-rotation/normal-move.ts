import type { Session } from './model';
export const NORMAL_LOOKBACK = 60;
export const MIN_DIRECTION_DAYS = 5;
const FLAT_EPSILON = 1e-10; // percentage points; ignore floating-point roundoff
export type DirectionalAverage = {mean:number|null;count:number};
export type NormalMoveStats = {
  lookback:number;minDirectionDays:number;historySessions:number;validSessions:number;missingSessions:number;flatDays:number;
  startDate:string|null;endDate:string|null;current:number|null;direction:'up'|'down'|'flat'|null;
  up:DirectionalAverage;down:DirectionalAverage;matchingMean:number|null;ratio:number|null;percentVsAverage:number|null;
  reason:'ready'|'no_session'|'no_return'|'flat'|'incomplete_history'|'small_sample';
};
export function directionalMoveStats(sessions:readonly Session[],symbol:string,date:string|undefined,lookback=NORMAL_LOOKBACK,minDirectionDays=MIN_DIRECTION_DAYS):NormalMoveStats {
  if(!Number.isInteger(lookback)||lookback<1||!Number.isInteger(minDirectionDays)||minDirectionDays<1) throw new Error('Invalid directional comparison window');
  const index=date?sessions.findIndex(d=>d.date===date):-1;
  const baseline=index<0?[]:sessions.slice(Math.max(0,index-lookback),index);
  let upSum=0,downSum=0,upCount=0,downCount=0,missing=0,flat=0;
  for(const session of baseline){
    const value=session.cells[symbol]?.daily;
    if(value==null||!Number.isFinite(value)){missing++;continue;}
    if(value>FLAT_EPSILON){upSum+=value;upCount++;}
    else if(value < -FLAT_EPSILON){downSum+=value;downCount++;}
    else flat++;
  }
  const value=index<0?null:sessions[index].cells[symbol]?.daily;
  const current=value==null||!Number.isFinite(value)?null:value;
  const direction=current===null?null:Math.abs(current)<=FLAT_EPSILON?'flat':current>0?'up':'down';
  const up={mean:upCount?upSum/upCount:null,count:upCount};
  const down={mean:downCount?downSum/downCount:null,count:downCount};
  const matching=direction==='up'?up:direction==='down'?down:null;
  let reason:NormalMoveStats['reason']='ready';
  if(index<0) reason='no_session';
  else if(current===null) reason='no_return';
  else if(direction==='flat') reason='flat';
  else if(baseline.length<lookback||missing>0) reason='incomplete_history';
  else if(!matching||matching.count<minDirectionDays||matching.mean===null) reason='small_sample';
  const ratio=reason==='ready'?Math.abs(current!)/Math.abs(matching!.mean!):null;
  return {lookback,minDirectionDays,historySessions:baseline.length,validSessions:baseline.length-missing,missingSessions:missing,flatDays:flat,startDate:baseline[0]?.date??null,endDate:baseline.at(-1)?.date??null,current,direction,up,down,matchingMean:matching?.mean??null,ratio,percentVsAverage:ratio===null?null:(ratio-1)*100,reason};
}
