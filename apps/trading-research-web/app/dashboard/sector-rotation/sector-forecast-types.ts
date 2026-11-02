export type SectorForecast={id:string;source_date:string;recorded_at:string;version:string;payload:{missed_target_date?:string;symbol?:string|null;side?:string;reason:string;training_sessions?:number;pattern?:{traits:string[];wins:number;observations:number;dates:number;score:number};features?:{rvol:number|null;daily:number|null;relative:number|null;ema20:number|null;ema50:number|null;daily_streak:number}};result?:{target_date:string;recorded_at:string;payload:{no_pick?:boolean;rank?:number;winner?:string|null;top1_green?:boolean;daily?:number|null;relative?:number|null;open?:number|null;close?:number|null;open_close_pct?:number|null;mfe_pct?:number|null;mae_pct?:number|null}}};

/** Missing records are coverage notices, never reconstructed predictions. Only verified trading dates qualify. */
export function withMissedForecasts(plans:SectorForecast[],dates:readonly string[],now=new Date()):SectorForecast[]{
 if(!plans.length)return plans;
 const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(now);
 const part=(key:string)=>parts.find(p=>p.type===key)!.value;
 const today=`${part('year')}-${part('month')}-${part('day')}`,clock=`${part('hour')}:${part('minute')}`;
 const first=plans.map(p=>p.source_date).sort()[0],sources=new Set(plans.map(p=>p.source_date));
 const ordered=[...new Set(dates)].sort(),missed:SectorForecast[]=[];
 for(let i=1;i<ordered.length;i++){
  const source=ordered[i-1],target=ordered[i];
  if(source<first||sources.has(source)||target>today||(target===today&&clock<'09:25'))continue;
  missed.push({id:`missed:${source}`,source_date:source,recorded_at:'',version:'coverage-notice',payload:{missed_target_date:target,reason:'No suggestion was recorded before the creation cutoff. This is a missed entry, not a no-pick or a retrospective prediction.'}});
 }
 return [...plans,...missed].sort((a,b)=>b.source_date.localeCompare(a.source_date));
}
