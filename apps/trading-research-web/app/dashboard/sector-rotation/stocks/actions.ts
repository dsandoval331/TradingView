'use server';
import {redirect} from 'next/navigation';
import {stockClient} from './data';
import {normalizeStockSymbol,MAX_TRACKED_SYMBOLS} from './symbols';
export async function requestStock(form:FormData){
 const client=await stockClient();
 const symbol=normalizeStockSymbol(String(form.get('symbol')??''));
 if(!symbol)redirect('/dashboard/sector-rotation/stocks?message=invalid');
 const {data:existing,error}=await client.from('stock_tracker_symbols').select('symbol').eq('symbol',symbol).maybeSingle();
 if(error)redirect('/dashboard/sector-rotation/stocks?message=unavailable');
 if(!existing){
  const {count,error:countError}=await client.from('stock_tracker_symbols').select('symbol',{count:'exact',head:true});
  if(countError)redirect('/dashboard/sector-rotation/stocks?message=unavailable');
  if((count??MAX_TRACKED_SYMBOLS)>=MAX_TRACKED_SYMBOLS)redirect('/dashboard/sector-rotation/stocks?message=capacity');
  const {error:insertError}=await client.from('stock_tracker_symbols').insert({symbol});
  if(insertError&&insertError.code!=='23505')redirect('/dashboard/sector-rotation/stocks?message=unavailable');
 }
 redirect('/dashboard/sector-rotation/stocks?symbol='+encodeURIComponent(symbol));
}
