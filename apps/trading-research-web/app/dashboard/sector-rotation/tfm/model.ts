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
 const live=rows.filter(r=>mondayDate(r)>=MONTHLY_TRACKING_START);
 const tracked=live;
 const month=asOf.slice(0,7);
 return {live,historical:rows.filter(r=>mondayDate(r)<MONTHLY_TRACKING_START),current:tracked.filter(r=>r.qualifies&&trackingMonth(r)===month),older:tracked.filter(r=>trackingMonth(r)<month)};
}
export function monthGroups(rows:Setup[]){
 return [...new Set(rows.map(trackingMonth))].sort().reverse().map(month=>({month,rows:rows.filter(r=>trackingMonth(r)===month)}));
}

export type AlternateRules={minMfePct:number;minRatio:number};
export const DEFAULT_ALTERNATE_RULES:AlternateRules={minMfePct:0.5,minRatio:2};
export const ALTERNATE_VERSION='tfm-alternate-v1-exploratory';
export function validAlternateRules(r:AlternateRules){return Number.isFinite(r.minMfePct)&&r.minMfePct>0&&Number.isFinite(r.minRatio)&&r.minRatio>0;}
export function excursionRatio(o:OutcomePayload|null){
 if(!o||!Number.isFinite(o.mfe_pct)||!Number.isFinite(o.mae_pct)||o.mfe_pct<0||o.mae_pct<0)return null;
 return o.mae_pct===0?(o.mfe_pct>0?Infinity:null):o.mfe_pct/o.mae_pct;
}
export function alternateSuccess(row:Setup,rules:AlternateRules=DEFAULT_ALTERNATE_RULES){
 const ratio=excursionRatio(row.outcome);
 return validAlternateRules(rules)&&row.qualifies&&!!row.outcome&&!row.outcome.hit&&row.outcome.mfe_pct>=rules.minMfePct&&ratio!==null&&ratio>=rules.minRatio;
}
export function summarizeAlternate(rows:Setup[],rules:AlternateRules=DEFAULT_ALTERNATE_RULES){
 const completed=rows.filter(r=>r.qualifies&&r.outcome!==null);
 const alternate=completed.filter(r=>alternateSuccess(r,rules)).length;
 const hits=completed.filter(r=>r.outcome!.hit).length;
 const prospective=completed.filter(r=>r.origin==='PROSPECTIVE');
 const prospectiveAlternate=prospective.filter(r=>alternateSuccess(r,rules)).length;
 const valid=validAlternateRules(rules);
 return {n:completed.length,alternate,combined:hits+alternate,alternateRate:valid&&completed.length?alternate/completed.length*100:null,combinedRate:valid&&completed.length?(hits+alternate)/completed.length*100:null,prospectiveN:prospective.length,prospectiveAlternate,prospectiveRate:valid&&prospective.length?prospectiveAlternate/prospective.length*100:null};
}

// Outcome groups overlap deliberately: alternate successes are a subset of primary misses.
export function summarizeExcursions(rows:Setup[],rules:AlternateRules=DEFAULT_ALTERNATE_RULES){
 const completed=rows.filter(r=>r.qualifies&&r.outcome!==null);
 const group=(items:Setup[])=>({n:items.length,
  mfe:items.length?items.reduce((sum,r)=>sum+r.outcome!.mfe_pct,0)/items.length:null,
  mae:items.length?items.reduce((sum,r)=>sum+r.outcome!.mae_pct,0)/items.length:null});
 return {hits:group(completed.filter(r=>r.outcome!.hit)),
  misses:group(completed.filter(r=>!r.outcome!.hit)),
  alternate:validAlternateRules(rules)?group(completed.filter(r=>alternateSuccess(r,rules))):null,
  all:group(completed)};
}
