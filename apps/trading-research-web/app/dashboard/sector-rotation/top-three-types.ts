export const TOP3_SYMBOLS=['XLE','XLV','XLK'] as const;
export type Top3Symbol=typeof TOP3_SYMBOLS[number];
export type PredictionStage='overnight'|'premarket'|'open30';
export type DailyTop3Prediction={target_date:string;stage:PredictionStage;symbol:Top3Symbol;recorded_at:string;data_as_of:string;top3:number;middle:number;bottom3:number;confidence:'Low'|'Medium'|'High';reason:string;sources:{label:string;url:string;as_of?:string}[];methodology:string;availability:'researched'|'baseline_only'};
export type DailyTop3Result={target_date:string;recorded_at:string;payload:{ranks:{symbol:string;rank:number;daily:number;bucket:'Top 3'|'Middle'|'Bottom 3'}[];ranking_rule:string;price_sha256:string}};
export const STAGE_LABELS:Record<PredictionStage,string>={overnight:'Overnight outlook',premarket:'Before market open',open30:'30 minutes after open'};
export function mostLikely(p:DailyTop3Prediction){const max=Math.max(p.top3,p.middle,p.bottom3);return [{label:'Top 3',p:p.top3},{label:'Middle',p:p.middle},{label:'Bottom 3',p:p.bottom3}].filter(v=>v.p===max).map(v=>v.label);}
export function priorCalendarDate(date:string){return new Date(Date.parse(date+'T12:00:00Z')-86400000).toISOString().slice(0,10);}
