import 'server-only';
import {createClient} from '../../../lib/supabase/server';
import type {SectorForecast} from './sector-forecast-types';
export async function loadSectorForecasts():Promise<{rows:SectorForecast[];error:string|null}>{
 const client=await createClient();
 const {data,error}=await client.auth.getClaims();
 if(error||!data?.claims)return {rows:[],error:'Sign in to view recorded sector suggestions.'};
 const access=await client.rpc('is_trading_research_web_user');
 if(access.error||access.data!==true)return {rows:[],error:'Sector suggestion access unavailable.'};
 async function load(table:string,fields:string,order:string){const rows=[];for(let offset=0;;offset+=1000){const result=await client.from(table).select(fields).order(order,{ascending:false}).range(offset,offset+999);if(result.error)throw new Error('Forecast read failed');rows.push(...(result.data??[]));if((result.data?.length??0)<1000)break;}return rows;}
 try{
  const [plans,outcomes]=await Promise.all([load('sector_winner_forecasts','id,version,source_date,recorded_at,payload','source_date'),load('sector_winner_forecast_results','forecast_id,target_date,recorded_at,payload','target_date')]);
  const byId=new Map(outcomes.map(row=>{const r=row as unknown as {forecast_id:string}&NonNullable<SectorForecast['result']>;return [r.forecast_id,r];}));
  return {rows:plans.map(row=>{const p=row as unknown as SectorForecast;return {...p,result:byId.get(p.id)};}),error:null};
 }catch{return {rows:[],error:'Recorded sector suggestions could not be loaded. Refresh to retry; this is not an empty result.'};}
}
