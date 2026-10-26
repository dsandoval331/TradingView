export const CHART_LINES=[{value:'none',label:'None'},{value:'ema20',label:'20 EMA'}] as const;
export type ChartLine=typeof CHART_LINES[number]['value'];
