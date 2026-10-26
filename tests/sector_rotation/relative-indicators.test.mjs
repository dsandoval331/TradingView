import {test} from 'node:test';
import assert from 'node:assert/strict';
import {rsiSeries,mansfieldSeries,buildSessions,formatValue,exportCsv} from '../../apps/trading-research-web/app/dashboard/sector-rotation/model.ts';
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
test('Wilder RSI uses a simple seed, then smoothed gains/losses, with explicit flat/up/down limits',()=>{
 const v=rsiSeries([10,11,10,12,11],3);assert.deepEqual(v.slice(0,3),[null,null,null]);near(v[3],75);near(v[4],600/11);
 assert.equal(rsiSeries(Array.from({length:15},(_,i)=>100+i))[14],100);
 assert.equal(rsiSeries(Array.from({length:15},(_,i)=>100-i))[14],0);
 assert.equal(rsiSeries(Array(15).fill(100))[14],50);
});
test('RSI warmup resets across missing prices and later values cannot rewrite historical RSI',()=>{
 const prices=[10,11,12,13,null,20,19,18,17];const v=rsiSeries(prices,3);
 assert.equal(v[3],100);assert.equal(v[7],null);assert.equal(v[8],0);
 assert.deepEqual(rsiSeries([...prices,999,1],3).slice(0,prices.length),v);
 assert.throws(()=>rsiSeries(prices,0),/Invalid/);
});
test('Mansfield normalizes the paired price ratio against its trailing SMA, including today',()=>{
 const v=mansfieldSeries([10,20,30,60],[10,10,10,10],3);assert.equal(v[1],null);near(v[2],50);near(v[3],700/11);
 const scaled=mansfieldSeries([100,200,300,600],[10,10,10,10],3);near(scaled[3],v[3]);
 const flat=mansfieldSeries(Array(200).fill(200),Array(200).fill(100));near(flat[199],0);assert.equal(flat[198],null);
 const gap=mansfieldSeries([10,20,30,40,50,60,70],[10,10,10,null,10,10,10],3);assert.equal(gap[5],null);assert.ok(gap[6]!==null);
 assert.deepEqual(mansfieldSeries([10,20,30,60,999],[10,10,10,10,1],3).slice(0,4),v);
});
test('session indicators are benchmark-aware, keep full-history warmup and export their own units',()=>{
 const groups=[{symbol:'X',name:'X',short:'X'}];
 const bars=Array.from({length:220},(_,i)=>{const trade_date=new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10);return [{symbol:'SPY',trade_date,close:100,volume:1},{symbol:'X',trade_date,close:10+i,volume:1}];}).flat();
 const days=buildSessions(bars,groups);assert.equal(days[13].cells.X.rsiRelative,null);near(days[14].cells.X.rsi,100);near(days[14].cells.X.spyRsi,50);near(days[14].cells.X.rsiRelative,50);
 assert.equal(days[198].cells.X.mansfield,null);near(days[199].cells.X.mansfield,(209/109.5-1)*100);
 assert.deepEqual(days.slice(0,200),buildSessions(bars.filter(b=>b.trade_date<=days[199].date),groups));
 assert.equal(formatValue(4.5,'rsiRelative'),'+4.50');assert.equal(formatValue(4.5,'mansfield'),'+4.50%');
 const csv=exportCsv(days.slice(-1),groups);assert.match(csv,/rsi_14,spy_rsi_14,rsi_difference_points,mansfield_rs_200_pct/);assert.doesNotMatch(csv,/NaN|undefined/);
});
