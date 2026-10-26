export type SessionWindow=20|60|120|'all';
export const sessionWindow=(value:string):SessionWindow=>value==='20'?20:value==='120'?120:value==='all'?'all':60;
export const windowLabel=(value:SessionWindow)=>value==='all'?'All available':`${value} sessions`;
