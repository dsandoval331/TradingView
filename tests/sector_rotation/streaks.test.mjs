import {test} from 'node:test';
import assert from 'node:assert/strict';
import {streakStats} from '../../apps/trading-research-web/app/dashboard/sector-rotation/streaks.ts';
const fixture=values=>values.map((daily,i)=>({date:String(i),cells:{XLK:{daily,relative:daily===null?null:-daily}}}));
test('completed run means exclude both boundary runs and selected/future values',()=>{
 const days=fixture([1,1,-1,-1,1,1,1,-1,1,-1,1,1]);
 const s=streakStats(days,'XLK','10');
 assert.equal(s.green.mean,2);assert.equal(s.green.count,2);assert.equal(s.red.mean,1.5);assert.equal(s.red.count,2);
 days[10].cells.XLK.daily=999;days[11].cells.XLK.daily=-999;
 assert.deepEqual(streakStats(days,'XLK','10'),s);
});
test('flat terminates a completed streak; missing observations invalidate adjacent runs',()=>{
 const s=streakStats(fixture([0,1,1,0,-1,null,1,1,-1,0,9]),'XLK','10');
 assert.equal(s.green.mean,2);assert.equal(s.green.count,1);assert.equal(s.red.mean,1);assert.equal(s.red.count,1);assert.equal(s.missingSessions,1);
});
test('relative measure uses outperformance signs independently of price signs',()=>{
 const days=fixture([0,1,1,-1,0,1]);
 assert.equal(streakStats(days,'XLK','5').green.mean,2);
 const s=streakStats(days,'XLK','5','relative');assert.equal(s.red.mean,2);assert.equal(s.green.mean,1);
});
test('window does not extend for missing data or count truncated runs; no eligible runs stay null',()=>{
 const days=fixture([0,1,1,1,-1,-1,1,1,9]);
 const s=streakStats(days,'XLK','8','daily',5);assert.equal(s.green.mean,null);assert.equal(s.red.mean,2);assert.equal(s.historySessions,5);
 assert.equal(streakStats(fixture([1,1,1,9]),'XLK','3').green.mean,null);
 assert.equal(streakStats(days,'XLK','missing').historySessions,0);
 assert.throws(()=>streakStats(days,'XLK','8','daily',0),/Invalid/);
});
