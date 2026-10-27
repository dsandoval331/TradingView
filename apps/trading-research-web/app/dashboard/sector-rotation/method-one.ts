import {SECTORS,mansfieldSeries,type Bar} from './model';
import type {SwingSuggestion} from './swing-trades';
import {METHOD_ONE_MAPPING_VERSION} from './method-one-sectors';
export const METHOD_ONE_DEFAULTS={instruments:'both',universe:'all',direction:'both',setups:'both',leadership:'both',relativePeriod:20,momentumPeriod:5,mansfieldPeriod:200,pullback:'fast',fastEma:20,slowEma:50,breakoutPeriod:20,marketFilter:'stack',ranking:'relative',rankPeriod:20,tiePeriod:5,topN:3,repeats:'every',startDate:'2026-10-06'} as const;
export type MethodOneConfig={instruments:'both'|'etfs'|'stocks';universe:'all'|'top50';direction:'both'|'long'|'short';setups:'both'|'pullback'|'breakout';leadership:'both'|'relative'|'mansfield';relativePeriod:number;momentumPeriod:number;mansfieldPeriod:number;pullback:'fast'|'slow'|'either';fastEma:number;slowEma:number;breakoutPeriod:number;marketFilter:'stack'|'slow'|'none';ranking:'relative'|'mansfield'|'shortTerm';rankPeriod:number;tiePeriod:number;topN:number;repeats:'every'|'first';startDate:string};
const enums={instruments:['both','etfs','stocks'],universe:['all','top50'],direction:['both','long','short'],setups:['both','pullback','breakout'],leadership:['both','relative','mansfield'],pullback:['fast','slow','either'],marketFilter:['stack','slow','none'],ranking:['relative','mansfield','shortTerm'],repeats:['every','first']} as const;
export function validateMethodOne(input:unknown):MethodOneConfig{
 if(!input||typeof input!=='object'||Array.isArray(input))throw new Error('Invalid Method 1 settings');
 const c=input as Record<string,unknown>;
 if(Object.keys(c).sort().join()!==Object.keys(METHOD_ONE_DEFAULTS).sort().join())throw new Error('Unknown or missing Method 1 settings');
 for(const [key,values] of Object.entries(enums))if(!(values as readonly unknown[]).includes(c[key]))throw new Error(`Invalid ${key}`);
 for(const key of ['relativePeriod','momentumPeriod','mansfieldPeriod','fastEma','slowEma','breakoutPeriod','rankPeriod','tiePeriod','topN'])if(!Number.isInteger(c[key])||Number(c[key])<1||Number(c[key])>(key==='topN'?10:260))throw new Error(`Invalid ${key}`);
 if(Number(c.fastEma)>=Number(c.slowEma))throw new Error('Fast EMA must be shorter than slow EMA');
 if(typeof c.startDate!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(c.startDate)||!Number.isFinite(Date.parse(c.startDate))||new Date(c.startDate).toISOString().slice(0,10)!==c.startDate)throw new Error('Invalid screen start date');
 return {...c} as MethodOneConfig;
}
export function methodOneKey(config:MethodOneConfig){return 'm1-v1:'+METHOD_ONE_MAPPING_VERSION+':'+Object.keys(METHOD_ONE_DEFAULTS).map(key=>String(config[key as keyof MethodOneConfig])).join(':');}
function ema(values:readonly (number|null)[],period:number){let count=0,sum=0,last:number|null=null;return values.map(value=>{if(value===null){count=0;sum=0;last=null;return null;}if(last===null){sum+=value;if(++count===period)last=sum/period;}else last=value*2/(period+1)+last*(1-2/(period+1));return last;});}
export type MethodOneResult={suggestions:SwingSuggestion[];unmapped:string[];latestSession:string|null;asOfDate:string;config:MethodOneConfig;configKey:string;stockCount:number};
/** Fixed-rule, outcome-blind screen; current membership/mapping, never a point-in-time universe backtest. */
export function screenMethodOne(bars:readonly Bar[],sectorMap:Readonly<Record<string,string>>,top50:readonly string[],settings:unknown,asOfDate:string):MethodOneResult{
 const c=validateMethodOne(settings),key=methodOneKey(c);
 const leadershipLabel=c.leadership==='both'?'relative performance and Mansfield strength':c.leadership==='relative'?'relative performance':'Mansfield strength';
 const marketLabel=c.marketFilter==='stack'?`SPY close / EMA${c.fastEma} / EMA${c.slowEma} alignment`:c.marketFilter==='slow'?`SPY versus EMA${c.slowEma}`:'no additional SPY filter';
 if(!/^\d{4}-\d{2}-\d{2}$/.test(asOfDate)||!Number.isFinite(Date.parse(asOfDate)))throw new Error('Invalid as-of date');
 const sectorSymbols=new Set<string>(SECTORS.map(s=>s.symbol)),prices=new Map<string,Map<string,Bar>>();
 for(const bar of bars){if(bar.trade_date>asOfDate)continue;const map=prices.get(bar.symbol)??new Map<string,Bar>();if(map.has(bar.trade_date))throw new Error('Duplicate Method 1 symbol/date');map.set(bar.trade_date,bar);prices.set(bar.symbol,map);}
 const dates=[...(prices.get('SPY')?.keys()??[])].sort();
 const candidates=[...prices.keys()].filter(symbol=>symbol!=='SPY'&&!sectorSymbols.has(symbol)&&(c.universe==='all'||top50.includes(symbol))).sort();
 const unmapped=candidates.filter(symbol=>!sectorSymbols.has(sectorMap[symbol]));
 const stocks=candidates.filter(symbol=>sectorSymbols.has(sectorMap[symbol]));
 const close=(bar:Bar|undefined)=>{const n=Number(bar?.close);return Number.isFinite(n)&&n>0?n:null;};
 const series=new Map([...prices].map(([symbol,map])=>{const values=dates.map(date=>close(map.get(date)));return [symbol,{values,fast:ema(values,c.fastEma),slow:ema(values,c.slowEma)}] as const;}));
 const spy=series.get('SPY')?.values??[];
 const mansfield=new Map([...sectorSymbols,...stocks].map(symbol=>[symbol,mansfieldSeries(series.get(symbol)?.values??dates.map(()=>null),sectorSymbols.has(symbol)?spy:series.get(sectorMap[symbol])?.values??[],c.mansfieldPeriod)]));
 const ratioChange=(symbol:string,benchmark:string,i:number,period:number):number|null=>{
  if(i<period)return null;const a=series.get(symbol)?.values,b=series.get(benchmark)?.values;
  for(let j=i-period;j<=i;j++)if(a?.[j]==null||b?.[j]==null)return null;
  return (a![i]!/b![i]!/(a![i-period]!/b![i-period]!)-1)*100;
 };
 const setup=(symbol:string,i:number,side:'long'|'short')=>{
  const s=series.get(symbol);if(!s||i===0||s.values[i]===null||s.values[i-1]===null)return [] as ('pullback'|'breakout')[];
  const result:('pullback'|'breakout')[]=[],value=s.values[i]!,previous=s.values[i-1]!;
  if(c.setups!=='breakout'){
   const lines=c.pullback==='either'?[s.fast,s.slow]:[c.pullback==='fast'?s.fast:s.slow];
   if(lines.some(line=>line[i]!=null&&line[i-1]!=null&&(side==='long'?previous<=line[i-1]!&&value>line[i]!:previous>=line[i-1]!&&value<line[i]!)))result.push('pullback');
  }
  if(c.setups!=='pullback'&&i>=c.breakoutPeriod){
   const history=dates.slice(i-c.breakoutPeriod,i).map(date=>prices.get(symbol)?.get(date));
   const valid=history.every(bar=>bar&&close(bar)!==null&&bar.high!=null&&bar.low!=null&&Number.isFinite(Number(bar.high))&&Number.isFinite(Number(bar.low))&&Number(bar.low)>0&&Number(bar.high)>=Math.max(Number(bar.low),Number(bar.close))&&Number(bar.low)<=Number(bar.close));
   if(valid&&(side==='long'?value>Math.max(...history.map(bar=>Number(bar!.high))):value<Math.min(...history.map(bar=>Number(bar!.low)))))result.push('breakout');
  }
  return result;
 };
 const streaks=new Map<string,number>();const suggestions:SwingSuggestion[]=[];
 for(let i=0;i<dates.length;i++){
  const hits:{symbol:string;sector:string;side:'long'|'short';setup:'pullback'|'breakout';rank?:number;score?:number;tie?:number}[]=[];
  for(const side of ['long','short'] as const){
   if(c.direction!=='both'&&c.direction!==side)continue;
   const sign=side==='long'?1:-1,market=series.get('SPY');
   if(c.marketFilter!=='none'&&(!market||market.values[i]==null||market.slow[i]==null||sign*(market.values[i]!-market.slow[i]!)<=0))continue;
   if(c.marketFilter==='stack'&&(!market||market.fast[i]==null||market.slow[i]==null||market.values[i]==null||sign*(market.values[i]!-market.fast[i]!)<=0||sign*(market.fast[i]!-market.slow[i]!)<=0))continue;
   for(const sector of sectorSymbols){
    const relative=ratioChange(sector,'SPY',i,c.relativePeriod),momentum=ratioChange(sector,'SPY',i,c.momentumPeriod),m=mansfield.get(sector)?.[i],old=i>=c.momentumPeriod?mansfield.get(sector)?.[i-c.momentumPeriod]:null;
    const relOK=relative!==null&&momentum!==null&&sign*relative>0&&sign*momentum>0;
    const manOK=m!=null&&old!=null&&sign*m>0&&sign*(m-old)>0;
    if(c.leadership==='both'?!(relOK&&manOK):c.leadership==='relative'?!relOK:!manOK)continue;
    if(c.instruments!=='stocks')for(const kind of setup(sector,i,side))hits.push({symbol:sector,sector,side,setup:kind});
    if(c.instruments==='etfs')continue;
    const ranked=stocks.filter(symbol=>sectorMap[symbol]===sector).map(symbol=>{
     const kinds=setup(symbol,i,side);
     const score=c.ranking==='mansfield'?mansfield.get(symbol)?.[i]??null:ratioChange(symbol,sector,i,c.ranking==='shortTerm'?c.tiePeriod:c.rankPeriod);
     const tie=ratioChange(symbol,sector,i,c.tiePeriod);
     return {symbol,kinds,score,tie};
    }).filter((r):r is typeof r & {score:number;tie:number}=>r.kinds.length>0&&r.score!==null&&r.tie!==null).sort((a,b)=>sign*(b.score-a.score)||sign*(b.tie-a.tie)||a.symbol.localeCompare(b.symbol)).slice(0,c.topN);
    ranked.forEach((r,index)=>{for(const kind of r.kinds)hits.push({symbol:r.symbol,sector,side,setup:kind,rank:index+1,score:r.score,tie:r.tie});});
   }
  }
  const todayKeys=new Set<string>();
  for(const hit of hits){
   const streakKey=`${hit.symbol}:${hit.side}:${hit.setup}`,consecutive=(streaks.get(streakKey)??0)+1;todayKeys.add(streakKey);streaks.set(streakKey,consecutive);
   if(dates[i]<c.startDate||(c.repeats==='first'&&consecutive>1))continue;
   const entry=series.get(hit.symbol)?.values[i];if(entry==null)continue;
   suggestions.push({id:`${key}:${streakKey}:${dates[i]}`,methodId:1,methodVersion:key,origin:'retrospective',calculated:true,sector:hit.sector,setup:hit.setup,sectorRank:hit.rank,consecutiveDays:consecutive,symbol:hit.symbol,side:hit.side,suggestedDate:dates[i],entryPrice:entry,reason:`Calculated Method #1 ${hit.side} ${hit.setup}: ${hit.sector} meets ${leadershipLabel} leadership; market confirmation: ${marketLabel}. ${hit.rank?`Stock rank ${hit.rank} of up to ${c.topN} qualifying stocks in this sector/direction; ranking ${c.ranking==='mansfield'?`Mansfield(${c.mansfieldPeriod})`:`relative(${c.ranking==='shortTerm'?c.tiePeriod:c.rankPeriod})`} versus ${hit.sector}: ${hit.score!.toFixed(4)}%; ${c.tiePeriod}-session tie value ${hit.tie!.toFixed(4)}%. `:'Sector ETF setup. '}${consecutive===1?'First qualifying session.':`Repeat: ${consecutive} consecutive qualifying sessions.`} Signal-close reference; current universe and sector mapping, retrospective calculation.`});
  }
  if(suggestions.length>5000)throw new Error('More than 5000 Method 1 matches; choose a later screen start date');
  for(const key of streaks.keys())if(!todayKeys.has(key))streaks.delete(key);
 }
 return {suggestions:suggestions.sort((a,b)=>b.suggestedDate.localeCompare(a.suggestedDate)||a.symbol.localeCompare(b.symbol)||a.id.localeCompare(b.id)),unmapped:c.instruments==='etfs'?[]:unmapped,latestSession:dates.at(-1)??null,asOfDate,config:c,configKey:key,stockCount:c.instruments==='etfs'?0:stocks.length};
}
