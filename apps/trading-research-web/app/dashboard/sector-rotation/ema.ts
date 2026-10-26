import type {Session} from './model';
/** SMA-seeded close EMA. Missing closes reset warmup; no future or filled values. */
export function closeEma(sessions:readonly Session[],symbol:string,period=20):Map<string,number|null> {
 if(!Number.isInteger(period)||period<1)throw new Error('Invalid EMA period');
 const result=new Map<string,number|null>();
 const alpha=2/(period+1);
 let mean:number|null=null,sum=0,count=0;
 for(const session of sessions){
  const close=session.cells[symbol]?.close??null;
  if(close===null||!Number.isFinite(close)||close<=0){mean=null;sum=0;count=0;}
  else if(mean===null){sum+=close;count++;if(count===period)mean=sum/period;}
  else mean=alpha*close+(1-alpha)*mean;
  result.set(session.date,mean);
 }
 return result;
}
