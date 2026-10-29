/** Calendar weekdays to open by default; never substitute older available sessions. */
export function weekDisplayDates(asOfDate:string):string[]{
 const time=Date.parse(asOfDate+'T12:00:00Z');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(asOfDate)||!Number.isFinite(time)||new Date(time).toISOString().slice(0,10)!==asOfDate)throw new Error('Invalid display date');
 const weekday=new Date(time).getUTCDay();
 const offset=(weekday+6)%7;
 const monday=time-offset*86400000;
 const date=(t:number)=>new Date(t).toISOString().slice(0,10);
 if(weekday===1)return [date(monday-3*86400000),asOfDate];
 return Array.from({length:Math.min(offset+1,5)},(_,i)=>date(monday+i*86400000));
}
export const WEEK_DISPLAY_NOTE='Current week expanded by default; Monday also includes the previous Friday. Older days remain collapsed and available to open.';
