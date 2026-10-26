import 'server-only';
import {createClient} from '../../../lib/supabase/server';
import type {SwingSuggestion} from './swing-trades';
/** Recorded snapshots only. RLS enforces the existing MULtipLY allowlist. No generation on page load. */
export async function loadSwingSuggestions():Promise<readonly SwingSuggestion[]>{
 const client=await createClient();
 const rows:SwingSuggestion[]=[];
 for(let offset=0;;offset+=1000){
  const {data,error}=await client.from('sector_swing_suggestions').select('id,method_id,method_version,symbol,suggested_date,side,entry_price,reason,origin,recorded_at').order('suggested_date',{ascending:false}).order('symbol').order('id').range(offset,offset+999);
  if(error)throw new Error('Swing suggestions could not be loaded. Please refresh to retry.');
  for(const row of data??[])rows.push({id:row.id,methodId:row.method_id,methodVersion:row.method_version,symbol:row.symbol,suggestedDate:row.suggested_date,side:row.side,entryPrice:Number(row.entry_price),reason:row.reason,origin:row.origin,recordedAt:row.recorded_at});
  if((data?.length??0)<1000)break;
 }
 return rows;
}
