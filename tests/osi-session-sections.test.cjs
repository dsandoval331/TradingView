const {test}=require('node:test');
const assert=require('node:assert/strict');
const {sessionForTime}=require('../apps/trading-research-web/app/dashboard/osi-analysis/model.ts');
test('sessions partition all 78 reporting slots and exclusive boundaries',()=>{
 for(const [time,expected] of [['08:29:59',null],['08:30:00','Open'],['09:59:59','Open'],['10:00:00','Mid-Day'],['13:29:59','Mid-Day'],['13:30:00','Close'],['14:59:59','Close'],['15:00:00',null]])assert.equal(sessionForTime('2026-10-30T'+time+'-05:00'),expected);
 const counts={};for(let i=0;i<78;i++){const m=510+i*5;const t=String(Math.floor(m/60)).padStart(2,'0')+':'+String(m%60).padStart(2,'0');const name=sessionForTime('2026-10-30T'+t+':40-05:00');assert.ok(name);counts[name]=(counts[name]||0)+1;}
 assert.deepEqual(counts,{Open:18,'Mid-Day':42,Close:18});
 assert.equal(sessionForTime('2026-12-01T16:00:00Z'),'Mid-Day');assert.equal(sessionForTime(null),null);
});
