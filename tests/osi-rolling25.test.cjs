const {test}=require('node:test');
const assert=require('node:assert/strict');
const {rolling25Rows,rankRolling25}=require('../apps/trading-research-web/app/dashboard/osi-analysis/model.ts');
test('all 74 five-slot windows stay inside regular hours',()=>{
 const rows=rolling25Rows([]);assert.equal(rows.length,74);assert.equal(rows[0].start,'08:30');assert.equal(rows[0].end,'08:55');assert.equal(rows.at(-1).start,'14:35');assert.equal(rows.at(-1).end,'15:00');assert.ok(rows.every(r=>r.slots.length===5));assert.deepEqual(rankRolling25(rows,'long'),[]);
});
test('rolling windows pool signal outcomes and honor exclusive boundaries',()=>{
 const signal=(time,side,result)=>({key:time,time:'2026-10-30T'+time+'-05:00',side,grade:'A',bucket:'',events:[],failed:0,outcome:result?{primary_outcome:result,final_mfe_pct:1,final_mae_pct:.5}:null});
 const signals=[signal('10:19:59','Long','ADVERSE'),signal('10:20:40','Long','FAVORABLE'),signal('10:25:00','Long','ADVERSE'),signal('10:30:00','Long','ADVERSE'),signal('10:40:40','Short','BOTH'),signal('10:44:59','Long',null),signal('10:45:00','Long','FAVORABLE')];
 const rows=rolling25Rows(signals),r=rows.find(r=>r.start==='10:20');
 assert.deepEqual(r.slots,['10:20','10:25','10:30','10:35','10:40']);assert.equal(r.long.signals,4);assert.equal(r.long.accepted,3);assert.ok(Math.abs(r.long.favorableRate-100/3)<1e-9);assert.equal(r.short.both,1);assert.equal(r.short.favorableRate,0);
 for(const side of ['long','short']){const top=rankRolling25(rows,side),bottom=rankRolling25(rows,side,true);assert.equal(top.length,4);assert.equal(bottom.length,4);assert.ok(top.every((v,i)=>i===0||top[i-1][side].favorableRate>=v[side].favorableRate));assert.ok(bottom.every((v,i)=>i===0||bottom[i-1][side].favorableRate<=v[side].favorableRate));}
 const tied=rankRolling25(rolling25Rows([signal('10:40:40','Long','FAVORABLE')]),'long');assert.deepEqual(tied.map(r=>r.start),['10:20','10:25','10:30','10:35']);
});
