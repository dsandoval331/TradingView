import {redirect} from 'next/navigation';
import {createClient} from '../../../../lib/supabase/server';
import type {Bar} from '../model';
export async function stockClient(){
 const client=await createClient();
 const {data:claims,error}=await client.auth.getClaims();
 if(error||!claims?.claims)redirect('/login');
 const {data:allowed,error:accessError}=await client.rpc('is_trading_research_web_user');
 if(accessError||allowed!==true)redirect('/unauthorized');
 return client;
}
export async function loadStockHistory(symbols:readonly string[]){
 const client=await stockClient();
 let bars:Bar[]=[],error:string|null=null;
 for(let offset=0;;offset+=1000){
  const result=await client.from('v_stock_daily_latest').select('symbol,trade_date,close,volume,collected_at,open,high,low').in('symbol',[...new Set(['SPY',...symbols])]).order('trade_date').order('symbol').range(offset,offset+999);
  if(result.error){bars=[];error='Stock history could not be loaded. Please try again.';break;}
  bars.push(...(result.data??[]) as Bar[]);if((result.data?.length??0)<1000)break;
 }
 const {data:requests,error:requestError}=await client.from('stock_tracker_symbols').select('symbol,last_success_at,last_error').in('symbol',[...symbols]);
 if(requestError)error='Collection status could not be loaded. Please try again.';
 const dates=bars.filter(b=>b.symbol==='SPY').map(b=>b.trade_date).sort();
 const updated=bars.map(b=>b.collected_at).filter((d):d is string=>!!d).sort().at(-1)??null;
 return {bars,error,requests:requests??[],latestSession:dates.at(-1)??null,updatedAt:updated};
}
