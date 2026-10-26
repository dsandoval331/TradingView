import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildSessions, SECTORS, leadershipNote, exportCsv } from '../../apps/trading-research-web/app/dashboard/sector-rotation/model.ts';
const fixture=()=>['SPY',...SECTORS.map(s=>s.symbol)].flatMap((symbol,j)=>Array.from({length:25},(_,i)=>({symbol,trade_date:`2025-01-${String(i+1).padStart(2,'0')}`,close:100*Math.pow(1+(j===0?.01:j*.002),i),volume:1000})));
test('returns, relative percentage points, and complete ranks',()=>{
 const days=buildSessions(fixture()), day=days[1];
 assert.ok(Math.abs(day.spy-1)<1e-9);
 assert.ok(Math.abs(day.cells.XLK.daily-.2)<1e-9);
 assert.ok(Math.abs(day.cells.XLK.relative-(-.8))<1e-9);
 assert.equal(day.cells.XLC.rank,1);assert.equal(day.cells.XLK.rank,11);
 assert.equal(day.cells.XLK.rankChange,null);
 assert.equal(days[2].cells.XLK.rankChange,0);
});
test('missing sector session is not bridged and does not manufacture rank',()=>{
 const bars=fixture().filter(b=>!(b.symbol==='XLK'&&b.trade_date==='2025-01-03'));
 const d=buildSessions(bars);
 assert.equal(d[2].cells.XLK.daily,null);assert.equal(d[3].cells.XLK.daily,null);
 assert.equal(d[3].cells.XLV.rank,null);assert.equal(d[3].leader,null);
 assert.equal(d[7].cells.XLK.five,null);
 assert.ok(d[8].cells.XLK.five!==null);
 assert.match(leadershipNote(d[2]),/Incomplete/);
});
test('5 and 20 session returns compound prices',()=>{
 const d=buildSessions(fixture());
 assert.ok(Math.abs(d[5].cells.XLK.five-(Math.pow(1.002,5)-1)*100)<1e-9);
 assert.ok(Math.abs(d[20].cells.XLK.twenty-(Math.pow(1.002,20)-1)*100)<1e-9);
 assert.equal(d[19].cells.XLK.twenty,null);
});
test('ties use shared competition ranks without a fabricated single leader',()=>{
 const bars=fixture().map(b=>({...b,close:100}));const d=buildSessions(bars);
 assert.equal(d[1].leader,null);assert.equal(d[1].laggard,null);
 assert.ok(Object.values(d[1].cells).every(c=>c.rank===1));
 assert.match(leadershipNote(d[1]),/Mixed/);
});
test('CSV preserves null as empty, and includes all 11 sectors',()=>{
 const csv=exportCsv(buildSessions(fixture()).slice(0,2));
 assert.equal(csv.split('\r\n').length,23);
 assert.match(csv,/relative_return_pp/);assert.doesNotMatch(csv,/null|undefined|NaN/);
});
test('duplicate observations rejected',()=>{
 const bars=fixture();bars.push(bars[0]);assert.throws(()=>buildSessions(bars),/Duplicate/);
});
test('leadership changes and daily vs relative sign remain distinct',()=>{
 const d=buildSessions(fixture());const current={...d[2],leader:'XLK'};
 assert.match(leadershipNote(current,d[1]),/Technology took the daily lead from Communication Services/);
 assert.ok(d[1].cells.XLK.daily>0&&d[1].cells.XLK.relative<0);
});
