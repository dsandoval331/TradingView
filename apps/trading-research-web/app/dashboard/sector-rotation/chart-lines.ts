export const CHART_LINES=[{value:'none',label:'None'},{value:'ema20',label:'20 EMA'},{value:'ema50',label:'50 EMA'}] as const;
export type ChartLine=typeof CHART_LINES[number]['value'];
export const emaPeriod=(line:ChartLine):20|50|null=>line==='ema20'?20:line==='ema50'?50:null;
