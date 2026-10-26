import {test} from 'node:test';
import assert from 'node:assert/strict';
import {directionalMoveStats} from '../../apps/trading-research-web/app/dashboard/sector-rotation/normal-move.ts';
function fixture(){return Array.from({length:70},(_,i)=>({date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),cells:{XLK:{daily:i%2===0?1:-2}}}));}
function stats(days,index=61){return directionalMoveStats(days,'XLK',days[index].date);}
test('trailing 60 excludes the selected day, future days, and older outlier',()=>{
 const days=fixture();days[0].cells.XLK.daily=900;days[61].cells.XLK.daily=3;days[62].cells.XLK.daily=-500;
 const s=stats(days);assert.equal(s.historySessions,60);assert.equal(s.up.count,30);assert.equal(s.down.count,30);
 assert.equal(s.up.mean,1);assert.equal(s.down.mean,-2);assert.equal(s.ratio,3);assert.equal(s.percentVsAverage,200);
 assert.equal(s.endDate,days[60].date);assert.equal(s.startDate,days[1].date);
 days[62].cells.XLK.daily=999999;assert.deepEqual(stats(days),s);
});
test('down-day comparison uses magnitude with a signed negative directional mean',()=>{
 const days=fixture();days[61].cells.XLK.daily=-4;
 const s=stats(days);assert.equal(s.direction,'down');assert.equal(s.matchingMean,-2);assert.equal(s.ratio,2);assert.equal(s.percentVsAverage,100);
 days[61].cells.XLK.daily=-1;assert.equal(stats(days).ratio,.5);assert.equal(stats(days).percentVsAverage,-50);
});
test('flat days are excluded from up/down means; flat selected day has no ratio',()=>{
 const days=fixture();days[2].cells.XLK.daily=0;days[61].cells.XLK.daily=0;
 const s=stats(days);assert.equal(s.up.count,29);assert.equal(s.up.mean,1);assert.equal(s.flatDays,1);assert.equal(s.reason,'flat');assert.equal(s.ratio,null);
});
test('missing and nonfinite history are counted and do not fill or extend the window',()=>{
 const days=fixture();days[5].cells.XLK.daily=null;days[6].cells.XLK.daily=Infinity;
 const s=stats(days);assert.equal(s.historySessions,60);assert.equal(s.validSessions,58);assert.equal(s.missingSessions,2);assert.equal(s.reason,'incomplete_history');assert.equal(s.ratio,null);
 assert.equal(s.up.mean,1);assert.equal(s.down.mean,-2);
});
test('partial history keeps available means but withholds a normal-size comparison',()=>{
 const s=stats(fixture(),10);assert.equal(s.historySessions,10);assert.equal(s.up.count,5);assert.equal(s.down.count,5);assert.equal(s.up.mean,1);assert.equal(s.down.mean,-2);assert.equal(s.reason,'incomplete_history');assert.equal(s.ratio,null);
});
test('rare-direction comparison needs at least five matching days',()=>{
 const days=fixture();for(let i=1;i<=60;i++)days[i].cells.XLK.daily=1;days[5].cells.XLK.daily=-2;days[61].cells.XLK.daily=-3;
 const s=stats(days);assert.equal(s.down.mean,-2);assert.equal(s.down.count,1);assert.equal(s.reason,'small_sample');assert.equal(s.ratio,null);
});
test('no-direction history, missing selected return, and unknown selection remain unavailable',()=>{
 const days=fixture();for(let i=1;i<=60;i++)days[i].cells.XLK.daily=0;days[61].cells.XLK.daily=1;
 assert.equal(stats(days).reason,'small_sample');assert.equal(stats(days).matchingMean,null);
 days[61].cells.XLK.daily=null;assert.equal(stats(days).reason,'no_return');
 assert.equal(directionalMoveStats(days,'XLK','1900-01-01').reason,'no_session');
});
test('roundoff-flat returns do not create a directional sample or division by zero',()=>{
 const days=fixture();days[2].cells.XLK.daily=1e-12;days[61].cells.XLK.daily=1e-12;
 assert.equal(stats(days).reason,'flat');assert.equal(stats(days).flatDays,1);assert.equal(stats(days).ratio,null);
 assert.throws(()=>directionalMoveStats(days,'XLK',days[61].date,0),/Invalid/);
});
test('relative baseline classifies moves against SPY independently of price direction',()=>{
 const days=fixture();for(let i=0;i<days.length;i++)days[i].cells.XLK.relative=i%2===0?-.25:.75;
 days[61].cells.XLK.relative=1.5;days[62].cells.XLK.relative=999;
 const s=directionalMoveStats(days,'XLK',days[61].date,60,5,'relative');
 assert.equal(s.up.mean,.75);assert.equal(s.down.mean,-.25);assert.equal(s.up.count,30);assert.equal(s.down.count,30);assert.equal(s.ratio,2);
 assert.equal(stats(days).up.mean,1);assert.equal(stats(days).down.mean,-2);
 days[61].cells.XLK.relative=-30;days[62].cells.XLK.relative=-999;
 const historical=directionalMoveStats(days,'XLK',days[61].date,60,5,'relative');
 assert.deepEqual(historical.up,s.up);assert.deepEqual(historical.down,s.down);
});
test('a missing relative observation cannot borrow a valid price return',()=>{
 const days=fixture();for(const d of days)d.cells.XLK.relative=.5;
 days[10].cells.XLK.relative=null;
 const s=directionalMoveStats(days,'XLK',days[61].date,60,5,'relative');
 assert.equal(s.missingSessions,1);assert.equal(s.reason,'incomplete_history');assert.equal(s.ratio,null);
});
