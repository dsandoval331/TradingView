import type {SupabaseClient} from '@supabase/supabase-js';
import {RULE_VERSION,type Setup,type OutcomePayload,type Scan} from './model';
export async function loadTFM(client:SupabaseClient,symbols:readonly string[]){
 const {data:runs,error:runError}=await client.from('tfm_runs').select('run_id,started_at,completed_at,status,coverage,diagnostics').eq('rule_version',RULE_VERSION).order('started_at',{ascending:false}).limit(5);
 let error=runError?'TFM scan status could not be loaded.':null;
 const setups:Setup[]=[];
 const outcomes=new Map<string,OutcomePayload>();
 if(!error){
  for(let offset=0;offset<200000;offset+=1000){
   const result=await client.from('tfm_outcomes').select('setup_key,payload').order('setup_key').range(offset,offset+999);
   if(result.error){error='TFM outcomes could not be loaded. No sample results are substituted.';break;}
   for(const row of result.data??[])outcomes.set(row.setup_key,row.payload as OutcomePayload);
   if((result.data?.length??0)<1000)break;
   if(offset===199000)error='TFM history exceeds the supported page limit.';
  }
  if(!error)for(let offset=0;offset<200000;offset+=1000){
   const result=await client.from('tfm_setups').select('setup_key,symbol,friday,target_date,cohort,qualifies,origin,recorded_at,payload').eq('rule_version',RULE_VERSION).in('symbol',[...symbols]).order('friday',{ascending:false}).order('symbol').range(offset,offset+999);
   if(result.error){error='TFM candidates could not be loaded. Please try again.';break;}
   for(const row of result.data??[])setups.push({...row,payload:row.payload,outcome:outcomes.get(row.setup_key)??null} as Setup);
   if((result.data?.length??0)<1000)break;
   if(offset===199000)error='TFM history exceeds the supported page limit.';
  }
 }
 return {rows:error?[]:setups,scans:(runs??[]) as Scan[],error};
}
