import assert from 'node:assert/strict';
import {summarize,partitions,trackingSections,monthGroups,trackingMonth} from '../../apps/trading-research-web/app/dashboard/sector-rotation/tfm/model.ts';
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
assert.equal(sections.current.length,2); // October Friday, November target belongs to November.
assert.equal(sections.current[0].symbol,'XLK');
assert.equal(sections.older.length,0);
assert.equal(monthGroups(sections.historical)[0].month,'2026-10');
assert.equal(summarize(sections.historical).hitRate,100);
assert.equal(summarize(sections.live).hitRate,50);
assert.equal(summarize(sections.live).baselineN,3); // nonqualifying tracking-period weeks retained for baseline.
assert.equal(trackingSections([historical(rows[0])],'2026-11-03').current.length,1);
assert.equal(trackingSections([historical(rows[4])],'2026-11-03').current.length,0);
assert.equal(trackingSections([historical(rows[0])],'2026-12-01').older.length,1);
assert.equal(trackingMonth({friday:'2027-05-28',target_date:'2027-06-01'}),'2027-05'); // Monday May 31 holiday: month still May.
console.log('TFM split: prospective/historical isolation, target-month boundaries and baseline preservation PASS');

const liveKeys=new Set(sections.live);
assert.equal(sections.live.length+sections.historical.length,mixed.length);
assert.ok(sections.historical.every(r=>!liveKeys.has(r)),'Live and historical populations must be disjoint');
assert.equal(trackingSections([historical(rows[0])],'2026-11-04').live.length,1);
assert.equal(trackingSections([historical(rows[0])],'2026-11-04').historical.length,0);
console.log('TFM totals: imported tracking-period outcomes included; historical cutoff disjoint; no duplicated baseline rows PASS');
const {alternateSuccess,summarizeAlternate,excursionRatio}=await import('../../apps/trading-research-web/app/dashboard/sector-rotation/tfm/model.ts');
const alt=(mfe,mae,hit=false,origin='HISTORICAL')=>({...rows[0],qualifies:true,origin,outcome:{hit,mfe_pct:mfe,mae_pct:mae}});
assert.equal(alternateSuccess(alt(.5,.25)),true);
assert.equal(alternateSuccess(alt(.49,.1)),false);
assert.equal(alternateSuccess(alt(.5,.251)),false);
assert.equal(alternateSuccess(alt(1,.1,true)),false);
assert.equal(alternateSuccess(alt(.5,0)),true);
assert.equal(excursionRatio(alt(0,0).outcome),null);
assert.equal(alternateSuccess({...alt(1,.1),qualifies:false}),false);
assert.equal(alternateSuccess({...alt(1,.1),outcome:null}),false);
assert.equal(alternateSuccess(alt(1,.1),{minMfePct:NaN,minRatio:2}),false);
assert.equal(alternateSuccess(alt(1,-1)),false);
const combined=summarizeAlternate([alt(1,.1,true),alt(.5,.25),alt(.2,.2),alt(.8,.2,false,'PROSPECTIVE')]);
assert.equal(combined.alternate,2);assert.equal(combined.combined,3);assert.equal(combined.combinedRate,75);assert.equal(combined.prospectiveRate,100);
assert.equal(summarizeAlternate([]).alternateRate,null);
console.log('Alternate success: exact thresholds, primary exclusion, zero MAE, pending/invalid data, combined denominator and prospective split PASS');
