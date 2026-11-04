export const RULE_VERSION = 'tfm-bearish-v2';
export type SourceBar = {symbol:string;trade_date:string;open:number;high:number;low:number;close:number;run_id:string;response_sha256:string;source_view:string};
export type SetupPayload = {asset_class:'SECTOR_ETF'|'ETF'|'STOCK';market_condition:string;thursday_high:number;friday_high:number;friday_low:number;friday_close:number;reference_bars:SourceBar[]};
export type OutcomePayload = {hit:boolean;gap_through:boolean;mfe_pct:number;mae_pct:number;close_return_pct:number;target_bar:SourceBar};
export type Setup = {setup_key:string;symbol:string;friday:string;target_date:string;cohort:'MONDAY'|'TUESDAY_HOLIDAY';qualifies:boolean;origin:'HISTORICAL'|'PROSPECTIVE';recorded_at:string;payload:SetupPayload;outcome:OutcomePayload|null};
export type Coverage = {source_first?:string;source_last?:string;requested_start?:string;five_year_complete?:boolean;invalid_bars?:number;missing_setup_pairs?:number;missing_matured_outcomes?:number;history_label?:string;symbols?:Record<string,{bars:number;first:string|null;last:string|null}>};
export type Scan = {run_id:string;started_at:string;completed_at:string|null;status:string;coverage:Coverage;diagnostics:Record<string,number|string|boolean>};
export function summarize(rows:Setup[]) {
 const completed=rows.filter(r=>r.outcome!==null);
 const qualified=completed.filter(r=>r.qualifies);
 const control=completed.filter(r=>!r.qualifies);
 const rate=(a:Setup[])=>a.length?a.filter(r=>r.outcome!.hit).length/a.length*100:null;
 const mean=(key:'mfe_pct'|'mae_pct')=>qualified.length?qualified.reduce((s,r)=>s+r.outcome![key],0)/qualified.length:null;
 const hitRate=rate(qualified),baseline=rate(completed);
 return {n:qualified.length,hits:qualified.filter(r=>r.outcome!.hit).length,hitRate,baseline,baselineN:completed.length,controlRate:rate(control),controlN:control.length,lift:hitRate!==null&&baseline!==null?hitRate-baseline:null,mfe:mean('mfe_pct'),mae:mean('mae_pct'),gaps:qualified.filter(r=>r.outcome!.gap_through).length,pending:rows.filter(r=>r.qualifies&&!r.outcome).length};
}
export function partitions(rows:Setup[],asOf:string) {
 const candidates=rows.filter(r=>r.qualifies);
 const previousDate=candidates.filter(r=>r.target_date<asOf).map(r=>r.friday).sort().at(-1);
 return {current:candidates.filter(r=>r.target_date>=asOf),previous:candidates.filter(r=>r.friday===previousDate),archive:candidates.filter(r=>r.target_date<asOf&&r.friday!==previousDate)};
}

// Monthly tracking begins with the user-requested October 29–30 / November 2 week.
export const MONTHLY_TRACKING_START='2026-11-02';
export function mondayDate(row:Pick<Setup,'friday'>){
 const d=new Date(row.friday+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+3);
 return d.toISOString().slice(0,10);
}
export function trackingMonth(row:Pick<Setup,'friday'>){return mondayDate(row).slice(0,7);}
export function trackingSections(rows:Setup[],asOf:string){
 const live=rows.filter(r=>r.origin==='PROSPECTIVE');
 const tracked=rows.filter(r=>r.origin==='PROSPECTIVE'||mondayDate(r)>=MONTHLY_TRACKING_START);
 const month=asOf.slice(0,7);
 return {live,historical:rows.filter(r=>r.origin==='HISTORICAL'),current:tracked.filter(r=>r.qualifies&&trackingMonth(r)===month),older:tracked.filter(r=>trackingMonth(r)<month)};
}
export function monthGroups(rows:Setup[]){
 return [...new Set(rows.map(trackingMonth))].sort().reverse().map(month=>({month,rows:rows.filter(r=>trackingMonth(r)===month)}));
}
