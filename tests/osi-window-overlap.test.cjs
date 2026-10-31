const {test}=require('node:test');
const assert=require('node:assert/strict');
const {rolling25Rows,rankRolling25}=require('../apps/trading-research-web/app/dashboard/osi-analysis/model.ts');
test('overlap modes enforce pairwise diversity independently in each ranking',()=>{
 const rows=rolling25Rows([]).map(r=>({...r,long:{...r.long,favorableRate:100},short:{...r.short,favorableRate:50}}));
 const starts=mode=>rankRolling25(rows,'long',false,mode).map(r=>r.start);
 assert.deepEqual(starts('allow-all'),['08:30','08:35','08:40','08:45']);
 assert.deepEqual(starts('exclude-3'),['08:30','08:45','09:00','09:15']);
 assert.deepEqual(starts('exclude-any'),['08:30','08:55','09:20','09:45']);
 for(const side of ['long','short'])for(const bottom of [false,true])for(const mode of ['allow-all','exclude-3','exclude-any']){
  const selected=rankRolling25(rows,side,bottom,mode);assert.equal(selected.length,4);
  for(let i=0;i<selected.length;i++)for(let j=0;j<i;j++){const shared=selected[i].slots.filter(s=>selected[j].slots.includes(s)).length;if(mode==='exclude-3')assert.ok(shared<3);if(mode==='exclude-any')assert.equal(shared,0);}
 }
 assert.equal(rankRolling25(rows.slice(0,5),'long',false,'exclude-any').length,1);
 assert.equal(rankRolling25(rows.slice(0,5),'long',false,'exclude-3').length,2);
 assert.deepEqual(rankRolling25(rolling25Rows([]),'long',false,'exclude-3'),[]);
});
