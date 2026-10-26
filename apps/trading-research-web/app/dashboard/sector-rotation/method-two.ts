import {rsiSeries,type Bar} from './model';
import {weekdaysSince,type SwingSuggestion} from './swing-trades';
export const METHOD_TWO_VERSION='rsi2-sma200-v1';
export function methodTwoSide(close:number,average:number,rsi:number):'long'|'short'|null{
 return close>average&&rsi<5?'long':close<average&&rsi>95?'short':null;
}
/** Bounded retrospective screen. Every matching day is separate; no exit or fill simulation. */
export function backfillMethodTwo(bars:readonly Bar[],symbols:readonly string[],asOfDate:string):SwingSuggestion[]{
 weekdaysSince(asOfDate,asOfDate);
 const wanted=new Set(symbols.filter(s=>s!=='SPY'));
 const prices=new Map<string,Map<string,number|null>>();
 for(const bar of bars){
  if((bar.symbol!=='SPY'&&!wanted.has(bar.symbol))||bar.trade_date>asOfDate)continue;
  weekdaysSince(bar.trade_date,bar.trade_date);
  const map=prices.get(bar.symbol)??new Map<string,number|null>();
  if(map.has(bar.trade_date))throw new Error('Duplicate Method 2 symbol/date');
  const close=Number(bar.close);map.set(bar.trade_date,Number.isFinite(close)&&close>0?close:null);prices.set(bar.symbol,map);
 }
 const dates=[...(prices.get('SPY')??new Map()).keys()].sort();
 const output:SwingSuggestion[]=[];
 for(const symbol of wanted){
  const closes=dates.map(date=>prices.get(symbol)?.get(date)??null),rsi=rsiSeries(closes,2);
  let window:number[]=[],sum=0;
  for(let i=0;i<dates.length;i++){
   const close=closes[i];
   if(close===null){window=[];sum=0;continue;}
   window.push(close);sum+=close;if(window.length>200)sum-=window.shift()!;
   const age=weekdaysSince(dates[i],asOfDate),momentum=rsi[i];
   if(window.length<200||momentum===null||age<0||age>=15)continue;
   const average=sum/200;
   const side=methodTwoSide(close,average,momentum);
   if(!side)continue;
   output.push({id:`m2:${METHOD_TWO_VERSION}:${symbol}:${dates[i]}:${side}`,methodId:2,methodVersion:METHOD_TWO_VERSION,signalMetrics:{rsi2:momentum,sma200:average},origin:'retrospective',symbol,suggestedDate:dates[i],side,entryPrice:close,
    reason:`Retrospective Method #2 ${side==='long'?'Long':'Short'} match: close $${close.toFixed(2)} ${side==='long'?'above':'below'} the 200-session SMA ($${average.toFixed(2)}), with Wilder RSI(2) ${momentum.toFixed(4)} ${side==='long'?'below 5':'above 95'}. Signal-day closing reference; reconstructed from available price history.`});
  }
 }
 return output.sort((a,b)=>b.suggestedDate.localeCompare(a.suggestedDate)||a.symbol.localeCompare(b.symbol)||a.id.localeCompare(b.id));
}
