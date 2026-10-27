'use server';
import {createClient} from '../../../lib/supabase/server';
import {screenMethodOne,validateMethodOne} from './method-one';
import {METHOD_ONE_SECTORS} from './method-one-sectors';
import {TOP_50_STOCKS} from './stocks/symbols';
import {marketDate} from './swing-trades';
import type {Bar} from './model';
/** Read-only calculation with per-call authentication and existing RLS; no privileged credentials. */
export async function runMethodOne(settings:unknown){
 const config=validateMethodOne(settings),client=await createClient();
 const {data:claims,error}=await client.auth.getClaims();
 if(error||!claims?.claims)throw new Error('Sign in to run Method 1');
 const {data:allowed,error:accessError}=await client.rpc('is_trading_research_web_user');
 if(accessError||allowed!==true)throw new Error('Method 1 access unavailable');
 const asOfDate=marketDate();
 async function load(view:string){const bars:Bar[]=[];for(let offset=0;;offset+=1000){
  const {data,error}=await client.from(view).select('symbol,trade_date,close,open,high,low,volume').lte('trade_date',asOfDate).order('trade_date').order('symbol').range(offset,offset+999);
  if(error)throw new Error('Method 1 price history could not be loaded');
  bars.push(...(data??[]) as Bar[]);if((data?.length??0)<1000)break;
 }return bars;}
 const [stockBars,sectorBars]=await Promise.all([load('v_stock_daily_latest'),load('v_sector_daily_latest')]);
 // Sector ETF observations are authoritative for sector symbols; stock view supplies SPY calendar and stocks.
 const sectors=new Set(sectorBars.filter(b=>b.symbol!=='SPY').map(b=>b.symbol));
 return screenMethodOne([...stockBars.filter(b=>!sectors.has(b.symbol)),...sectorBars.filter(b=>b.symbol!=='SPY')],METHOD_ONE_SECTORS,TOP_50_STOCKS.map(s=>s.symbol),config,asOfDate);
}
