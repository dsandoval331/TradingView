import type {League, LeagueMatch} from './LeaguePanel';
import type {RankGame,RankSnapshot} from './RankingPanel';
import type {SupabaseClient} from '@supabase/supabase-js';
import {RULE_VERSION,type Setup,type OutcomePayload,type Scan} from './model';
export async function loadTFM(client:SupabaseClient,symbols:readonly string[],scope='sectors'){
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
 const [game, league] = await Promise.all([loadRankGame(client,scope), loadLeague(client,scope)]);
 return {rows:error?[]:setups,scans:(runs??[]) as Scan[],error,game,league};
}

async function loadRankGame(client:SupabaseClient,scope:string):Promise<RankGame>{
 const empty:RankGame={snapshots:[],xp:[],reflections:[],error:null};
 // Read complete ledgers; do not truncate season totals at the API default row limit.
 const all=async(table:string,select:string)=>{const rows:Record<string,unknown>[]=[];for(let offset=0;offset<20000;offset+=1000){
 const q=client.from(table).select(select);const {data,error}=await (table==='tfm_rank_snapshots'?q.eq('scope',scope).order('monday',{ascending:false}):q.order(table==='tfm_rank_reviews'?'snapshot_id':'monday')).range(offset,offset+999);
 if(error)throw new Error('Rank data unavailable');rows.push(...((data??[]) as unknown as Record<string,unknown>[]));if((data?.length??0)<1000)return rows;
 }throw new Error('Rank history page limit');};
 try{
 const [snapshots,reviews,xp,reflections]=await Promise.all([all('tfm_rank_snapshots','snapshot_id,model_version,scope,monday,target_date,frozen_at,payload'),all('tfm_rank_reviews','snapshot_id,payload'),all('tfm_rank_xp','monday,kind,points'),all('tfm_rank_reflections','monday,note')]);
 return {snapshots:snapshots.map(s=>({...s,review:reviews.find(r=>r.snapshot_id===s.snapshot_id)?.payload??null})) as RankSnapshot[],xp:xp as RankGame['xp'],reflections:reflections as RankGame['reflections'],error:null};
 }catch{return {...empty,error:'Rankings and Research XP could not be loaded. No sample scores or awards are substituted.'};}
}

async function loadLeague(client: SupabaseClient, scope: string): Promise<League> {
 const matches: LeagueMatch[] = [];
 for (let offset = 0; offset < 20000; offset += 1000) {
  const {data, error} = await client.from('tfm_league_matches')
   .select('champion_id,monday,target_date,picks,tfm_league_results(payload)')
   .eq('scope',scope).order('monday',{ascending:false}).order('champion_id')
   .range(offset,offset+999);
  if (error) return {matches:[],error:true};
  for (const {tfm_league_results: review, ...match} of data ?? []) {
   const result = Array.isArray(review) ? review[0]?.payload : (review as {payload?: LeagueMatch['result']} | null)?.payload;
   matches.push({...match,result:result ?? null} as LeagueMatch);
  }
  if ((data?.length ?? 0) < 1000) return {matches,error:false};
 }
 return {matches:[],error:true};
}
