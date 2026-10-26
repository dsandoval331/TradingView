import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildTechBars, TECH_GROUPS } from '../../apps/trading-research-web/app/dashboard/sector-rotation/tech-ai/model.ts';
import { buildSessions, exportCsv, SECTORS } from '../../apps/trading-research-web/app/dashboard/sector-rotation/model.ts';
const members=[...new Set(['SPY',...TECH_GROUPS.flatMap(g=>g.members)])];
function fixture(){return members.flatMap(symbol=>Array.from({length:25},(_,i)=>({symbol,trade_date:`2025-01-${String(i+1).padStart(2,'0')}`,close:symbol==='AAPL'?(i===0?100:i===1?110:99):100,volume:100})));}
test('four requested groups and no semiconductor overlap in the non-chip basket',()=>{
 assert.equal(TECH_GROUPS.length,4);assert.equal(members.length,23);
 const chips=TECH_GROUPS.find(g=>g.symbol==='AI-CHIP').members;
 const nonchips=TECH_GROUPS.find(g=>g.symbol==='AI-OTHER').members;
 assert.ok(chips.every(c=>!nonchips.includes(c)));
 assert.ok(nonchips.includes('ANET')&&nonchips.includes('VRT'));
});
test('custom basket is equal weighted each day, not a buy-and-hold constituent average',()=>{
 const bars=buildTechBars(fixture());const days=buildSessions(bars,TECH_GROUPS);
 assert.ok(Math.abs(days[1].cells.HW.daily-1.25)<1e-9);
 assert.ok(Math.abs(days[2].cells.HW.daily-(-1.25))<1e-9);
 assert.ok(Math.abs(days[5].cells.HW.five-((1.0125*.9875)-1)*100)<1e-9);
 assert.equal(days[1].cells.HW.rank,1);
});
test('IGV keeps the ETF price series and SPY remains the reference',()=>{
 const original=fixture();const bars=buildTechBars(original);
 assert.deepEqual(bars.filter(b=>b.symbol==='IGV'),original.filter(b=>b.symbol==='IGV'));
 assert.equal(buildSessions(bars,TECH_GROUPS).length,25);
});
test('missing constituent interrupts basket returns and rankings, never zero-fills',()=>{
 const raw=fixture().filter(b=>!(b.symbol==='AAPL'&&b.trade_date==='2025-01-03'));
 const days=buildSessions(buildTechBars(raw),TECH_GROUPS);
 assert.equal(days[2].cells.HW.daily,null);assert.equal(days[3].cells.HW.daily,null);
 assert.equal(days[3].cells['AI-CHIP'].rank,null);
 assert.equal(days[7].cells.HW.five,null);
 assert.ok(days[9].cells.HW.five!==null);
});
test('main-sector universe remains 11; theme CSV has four groups',()=>{
 assert.equal(SECTORS.length,11);
 const days=buildSessions(buildTechBars(fixture()),TECH_GROUPS);
 assert.equal(exportCsv(days.slice(1),TECH_GROUPS).split('\r\n').length,97);
});
