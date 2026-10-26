import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chartLayout,syncChartScroll} from '../../apps/trading-research-web/app/dashboard/sector-rotation/chart-layout.ts';
test('shared geometry keeps session centers within identical plot gutters for short and long windows',()=>{
 for(const count of [0,1,20,60,120,499]){
  const p=chartLayout(count);
  assert.equal(p.left+p.plotWidth+p.right,p.width);
  if(count)assert.ok(Math.abs(count*p.slot-p.plotWidth)<1e-10);
  assert.ok(p.bodyWidth<p.slot);assert.ok(p.labelEvery*p.slot>=70||count===0);
 }
});
test('bidirectional scroll clamps common limits and does not write repeatedly at an equal position',()=>{
 let writes=0;
 const pane=(max)=>{let value=0;return {clientWidth:400,scrollWidth:400+max,get scrollLeft(){return value;},set scrollLeft(v){value=v;writes++;}};};
 const a=pane(800),b=pane(800);
 a.scrollLeft=237;syncChartScroll(a,[a,b]);assert.equal(b.scrollLeft,237);
 b.scrollLeft=400;syncChartScroll(b,[a,b]);assert.equal(a.scrollLeft,400);
 const before=writes;syncChartScroll(a,[a,b]);syncChartScroll(b,[a,b]);assert.equal(writes,before);
 b.clientWidth=1000;syncChartScroll(a,[a,b]);assert.equal(a.scrollLeft,200);assert.equal(b.scrollLeft,200);
 a.scrollLeft=-30;syncChartScroll(a,[b]);assert.equal(a.scrollLeft,0);assert.equal(b.scrollLeft,0);
 assert.equal(syncChartScroll(a,[null]),0);
});
