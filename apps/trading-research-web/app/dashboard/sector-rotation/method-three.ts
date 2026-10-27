import {buildSessions,HEAT_NEUTRAL_THRESHOLD,type Bar,type Group} from './model';
import {volumeSeries} from './volume';
import type {SessionWindow} from './session-window';
import {windowLabel} from './session-window';
import type {SwingSuggestion} from './swing-trades';
export const METHOD_THREE_START_DATE='2026-10-06';
export const METHOD_THREE_RVOL_OPTIONS=[{value:'baseline',label:'>1.0× (original)'},...Array.from({length:10},(_,i)=>({value:((11+i)/10).toFixed(1),label:`≥${((11+i)/10).toFixed(1)}×`})),{value:'over2',label:'>2.0×'}] as const;
export const relativeVolumeLabel=(value:string)=>METHOD_THREE_RVOL_OPTIONS.find(option=>option.value===value)?.label??'Invalid';
export function qualifiesRelativeVolume(volume:number,average:number,setting:string){
 if(!METHOD_THREE_RVOL_OPTIONS.some(option=>option.value===setting))throw new Error('Invalid relative volume setting');
 return average>0&&(setting==='baseline'?volume>average:setting==='over2'?volume>2*average:volume*10>=Math.round(Number(setting)*10)*average);
}
/** Read-only retrospective screen. Reuse heatmap returns and chart volume definitions. */
export function screenMethodThree(bars:readonly Bar[],groups:readonly Group[],period:SessionWindow,asOfDate:string,startDate=METHOD_THREE_START_DATE,relativeVolume='baseline'):SwingSuggestion[]{
 if(!METHOD_THREE_RVOL_OPTIONS.some(option=>option.value===relativeVolume))throw new Error('Invalid relative volume setting');
 const instruments=groups.filter(group=>group.kind!=='basket');
 if(!instruments.length)return [];
 const history=bars.filter(bar=>bar.trade_date<=asOfDate);
 const sessions=buildSessions(history,instruments);
 const suggestions:SwingSuggestion[]=[];
 const version=`m3-v1-volume-${period}${relativeVolume==='baseline'?'':`-rvol-${relativeVolume}`}`;
 for(const group of instruments){
  const volumes=volumeSeries(history,sessions,group.symbol,period);
  let previousSide:'long'|'short'|null=null,consecutiveDays=0;
  for(const session of sessions){
   const cell=session.cells[group.symbol],volume=volumes.get(session.date);
   const side=cell.daily!==null&&cell.relative!==null&&Math.abs(cell.relative)>=HEAT_NEUTRAL_THRESHOLD&&volume?.volume!=null&&volume.average!==null&&qualifiesRelativeVolume(volume.volume,volume.average,relativeVolume)
    ?cell.daily>0&&cell.relative>0?'long':cell.daily<0&&cell.relative<0?'short':null:null;
   consecutiveDays=side?(side===previousSide?consecutiveDays+1:1):0;previousSide=side;
   if(!side||cell.close===null||session.date<startDate)continue;
   const repeat=consecutiveDays===1?'First occurrence':`Repeat: ${consecutiveDays} consecutive sessions`;
   suggestions.push({id:`${version}:${group.symbol}:${session.date}:${side}`,methodId:3,methodVersion:version,symbol:group.symbol,suggestedDate:session.date,side,entryPrice:cell.close,origin:'retrospective',calculated:true,consecutiveDays,
    reason:`${side==='long'?'Long':'Short'}: volume ${volume!.volume!.toLocaleString('en-US')} > ${windowLabel(period)} average ${volume!.average!.toLocaleString('en-US',{maximumFractionDigits:2})} (includes signal day); relative volume ${(volume!.volume!/volume!.average!).toFixed(2)}×, required ${relativeVolumeLabel(relativeVolume)}; close-to-close change ${cell.daily!.toFixed(2)}%; relative to SPY ${cell.relative!>0?'+':''}${cell.relative!.toFixed(2)} pp. ${repeat}.`});
  }
 }
 return suggestions.sort((a,b)=>b.suggestedDate.localeCompare(a.suggestedDate)||a.symbol.localeCompare(b.symbol));
}
