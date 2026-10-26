import type {Bar,Session} from './model';
export type VolumePoint={volume:number|null;average:number|null};
/** Trailing volume SMA includes this session; missing values break the window. Zero is valid. */
export function volumeSeries(bars:readonly Bar[],sessions:readonly Session[],symbol:string,period:number|'all'=20):Map<string,VolumePoint>{
 if(period!=='all'&&(!Number.isInteger(period)||period<1))throw new Error('Invalid volume average period');
 const byDate=new Map<string,number|null>();
 for(const bar of bars)if(bar.symbol===symbol){
  if(byDate.has(bar.trade_date))throw new Error('Duplicate volume date');
  const n=bar.volume==null?NaN:Number(bar.volume);
  byDate.set(bar.trade_date,Number.isFinite(n)&&n>=0?n:null);
 }
 const result=new Map<string,VolumePoint>();let window:number[]=[];let sum=0;
 for(const session of sessions){
  const volume=byDate.get(session.date)??null;
  if(volume===null){window=[];sum=0;}
  else{window.push(volume);sum+=volume;if(period!=='all'&&window.length>period)sum-=window.shift()!;}
  result.set(session.date,{volume,average:period==='all'?(window.length?sum/window.length:null):window.length===period?sum/period:null});
 }
 return result;
}
