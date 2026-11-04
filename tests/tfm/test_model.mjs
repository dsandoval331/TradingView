import assert from 'node:assert/strict';
import {summarize,partitions,trackingSections,monthGroups} from '../../apps/trading-research-web/app/dashboard/sector-rotation/tfm/model.ts';
const row=(symbol,friday,target,qualifies,hit)=>({symbol,friday,target_date:target,qualifies,outcome:hit===null?null:{hit,mfe_pct:2,mae_pct:1,gap_through:false}});
const rows=[row('XLK','2026-10-30','2026-11-02',true,true),row('NVDA','2026-10-30','2026-11-02',true,false),row('XLE','2026-10-30','2026-11-02',false,false),row('XLK','2026-11-06','2026-11-09',true,null),row('XLK','2026-10-23','2026-10-26',true,true)];
const s=summarize(rows);
assert.equal(s.n,3);assert.equal(s.hits,2);assert.equal(s.baseline,50);assert.equal(s.controlRate,0);assert.equal(s.pending,1);
const p=partitions(rows,'2026-11-03');
assert.equal(p.current.length,1);assert.equal(p.previous.length,2);assert.equal(p.archive.length,1);
assert.equal(summarize([]).hitRate,null);
console.log('TFM model: denominators, baseline, missing outcomes, and archive partitions PASS');

const prospective=(r)=>({...r,origin:'PROSPECTIVE'});
const historical=(r)=>({...r,origin:'HISTORICAL'});
const mixed=[prospective(rows[0]),prospective(rows[2]),prospective(rows[4]),historical(rows[1])];
const sections=trackingSections(mixed,'2026-11-03');
assert.equal(sections.live.length,3);
assert.equal(sections.historical.length,1);
assert.equal(sections.current.length,1); // October Friday, November target belongs to November.
assert.equal(sections.current[0].symbol,'XLK');
assert.equal(sections.older.length,1);
assert.equal(monthGroups(sections.older)[0].month,'2026-10');
assert.equal(summarize(sections.historical).hitRate,0);
assert.equal(summarize(sections.live).hitRate,100);
assert.equal(summarize(sections.live).baselineN,3); // nonqualifying prospective weeks retained for baseline.
assert.equal(trackingSections([historical(rows[0])],'2026-11-03').current.length,0);
console.log('TFM split: prospective/historical isolation, target-month boundaries and baseline preservation PASS');
