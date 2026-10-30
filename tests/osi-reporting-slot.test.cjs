const {test}=require('node:test');
const assert=require('node:assert/strict');
const {reportingSlot,slotGradeRows,buildSignals}=require('../apps/trading-research-web/app/dashboard/osi-analysis/model.ts');
test('report slots floor seconds and respect exact boundaries and DST',()=>{
 for(const [time,slot] of [['2026-10-30T08:35:00-05:00','08:35'],['2026-10-30T08:35:40-05:00','08:35'],['2026-10-30T08:39:59-05:00','08:35'],['2026-10-30T08:40:00-05:00','08:40'],['2026-12-01T14:35:40Z','08:35']])assert.equal(reportingSlot(time),slot);
 assert.equal(reportingSlot(null),'Unknown Time');
});
test('grade comparison isolates 8:35 and separates side and missing grades',()=>{
 const signal=(key,time,grade,side,result,failed=0)=>({key,time,grade,side,events:[],bucket:'',failed,outcome:result?{primary_outcome:result,final_mfe_pct:1,final_mae_pct:.2}:null});
 const rows=slotGradeRows([signal('a','2026-10-30T08:35:40-05:00','A','Long','FAVORABLE'),signal('b','2026-10-30T08:36:00-05:00','A','Long','ADVERSE'),signal('c','2026-10-30T08:39:59-05:00','B','Short','BOTH'),signal('d','2026-10-30T08:40:00-05:00','A','Long','FAVORABLE'),signal('e','2026-10-30T08:35:30-05:00','Ungraded','Long',null,1)]);
 const a=rows.find(r=>r.grade==='A'&&r.side==='Long');assert.equal(a.signals,2);assert.equal(a.favorableRate,50);
 const b=rows.find(r=>r.grade==='B'&&r.side==='Short');assert.equal(b.both,1);assert.equal(b.favorableRate,0);
 const u=rows.find(r=>r.grade==='Ungraded'&&r.side==='Long');assert.equal(u.failed,1);assert.equal(u.favorableRate,null);
 assert.deepEqual(slotGradeRows([]),[]);
});
test('current snapshot has no 8:35 observations',()=>{assert.deepEqual(slotGradeRows(buildSignals(require('../apps/trading-research-web/app/dashboard/osi-analysis/events.json'))),[]);});
