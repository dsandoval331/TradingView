import {test} from 'node:test';
import assert from 'node:assert/strict';
import {closeEma} from '../../apps/trading-research-web/app/dashboard/sector-rotation/ema.ts';
const fixture=values=>values.map((close,i)=>({date:String(i).padStart(3,'0'),cells:{XLK:{close}}}));
test('20 EMA seeds at the twentieth close and follows alpha 2/21 without lookahead',()=>{
 const days=fixture(Array.from({length:23},(_,i)=>100+i));
 const result=closeEma(days,'XLK');
 assert.equal(result.get('018'),null);assert.equal(result.get('019'),109.5);
 assert.ok(Math.abs(result.get('020')-110.5)<1e-12);assert.ok(Math.abs(result.get('021')-111.5)<1e-12);
 days[22].cells.XLK.close=99999;assert.equal(closeEma(days,'XLK').get('021'),result.get('021'));
});
test('full history EMA values stay fixed when the display is sliced to 20 or 60 sessions',()=>{
 const days=fixture(Array.from({length:90},(_,i)=>100+Math.sin(i)*5+i));
 const full=closeEma(days,'XLK');
 for(const count of [20,60])for(const day of days.slice(-count))assert.equal(full.get(day.date),closeEma(days.slice(0,+day.date+1),'XLK').get(day.date));
});
test('missing and invalid closes restart the full warmup without bridging a gap',()=>{
 for(const invalid of [null,0,NaN,Infinity]){
  const days=fixture([...Array(20).fill(100),invalid,...Array(20).fill(200)]);
  const result=closeEma(days,'XLK');assert.equal(result.get('020'),null);assert.equal(result.get('039'),null);assert.equal(result.get('040'),200);
 }
 assert.equal([...closeEma(fixture([100,101]),'IGV').values()].every(v=>v===null),true);
 assert.throws(()=>closeEma([], 'XLK',0),/Invalid/);
});
