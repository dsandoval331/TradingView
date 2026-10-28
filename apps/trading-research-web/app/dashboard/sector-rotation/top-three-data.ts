import 'server-only';
import {createClient} from '../../../lib/supabase/server';
import type {DailyTop3Prediction,DailyTop3Result} from './top-three-types';
export async function loadDailyTop3():Promise<{predictions:DailyTop3Prediction[];results:DailyTop3Result[];error:string|null}>{
 const client=await createClient();
 const {data,error}=await client.auth.getClaims();
 if(error||!data?.claims)return {predictions:[],results:[],error:'Sign in to view daily sector predictions.'};
 const access=await client.rpc('is_trading_research_web_user');
 if(access.error||access.data!==true)return {predictions:[],results:[],error:'Daily sector prediction access unavailable.'};
 async function load(table:string,fields:string,secondary:string){const rows=[];for(let offset=0;;offset+=1000){let query=client.from(table).select(fields).order('target_date',{ascending:false});if(secondary)query=query.order(secondary,{ascending:true}).order('symbol',{ascending:true});const result=await query.range(offset,offset+999);if(result.error)throw new Error('Prediction read failed');rows.push(...(result.data??[]));if((result.data?.length??0)<1000)break;}return rows;}
 try{
  const [predictions,results]=await Promise.all([load('sector_top3_predictions','target_date,stage,symbol,recorded_at,data_as_of,top3,middle,bottom3,confidence,reason,sources,methodology,availability','stage'),load('sector_top3_results','target_date,recorded_at,payload','')]);
  return {predictions:(predictions as unknown as DailyTop3Prediction[]).map(p=>({...p,top3:Number(p.top3),middle:Number(p.middle),bottom3:Number(p.bottom3)})),results:results as unknown as DailyTop3Result[],error:null};
 }catch{return {predictions:[],results:[],error:'Daily sector predictions could not be loaded. Refresh to retry; this is not an empty history.'};}
}
