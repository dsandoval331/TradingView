const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createRequire}=require('node:module');
const app=path.resolve(__dirname,'../apps/trading-research-web');
const appRequire=createRequire(path.join(app,'package.json'));
const ts=appRequire('typescript');
require.extensions['.ts']=require.extensions['.tsx']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true,target:ts.ScriptTarget.ES2022}}).outputText,f);
require.extensions['.css']=m=>{m.exports=new Proxy({},{get:(_,k)=>k==='__esModule'?false:String(k)});};
const route=path.join(app,'app/dashboard/osi-analysis');
const {buildSignals,summarize,breakdown,timeBucket}=require(path.join(route,'model.ts'));
const events=require(path.join(route,'events.json'));
test('six deliveries become four signals and only three processed outcomes',()=>{
 const signals=buildSignals(events),s=summarize(signals);
 assert.equal(signals.length,4);assert.equal(s.accepted,3);assert.equal(s.failed,1);assert.equal(s.noAccepted,1);
 assert.equal(s.favorable,1);assert.equal(s.adverse,1);assert.equal(s.both,1);assert.equal(s.unresolved,0);
 assert.ok(Math.abs(s.mfe-(1.42+.31+1.2)/3)<1e-10);assert.ok(Math.abs(s.mae-(.27+1.14+1.05)/3)<1e-10);
 assert.ok(Math.abs(s.favorableRate-100/3)<1e-10);assert.equal(signals[0].events.length,3);
});
test('grade and direction breakdowns preserve missing grades and signal denominators',()=>{
 const signals=buildSignals(events);
 const grade=breakdown(signals,'grade');assert.equal(grade.length,1);assert.equal(grade[0].label,'Ungraded');assert.equal(grade[0].signals,4);
 const sides=breakdown(signals,'side');assert.equal(sides.find(s=>s.label==='Long').signals,3);assert.equal(sides.find(s=>s.label==='Short').signals,1);assert.equal(sides.find(s=>s.label==='Long').accepted,2);
 assert.equal(summarize([]).favorableRate,null);assert.equal(summarize([]).mfe,null);
});
test('five minute entry windows use Central time with exclusive end boundaries',()=>{
 assert.equal(timeBucket('2026-09-02T09:34:59-04:00'),'08:30–08:35');
 assert.equal(timeBucket('2026-09-02T09:35:00-04:00'),'08:35–08:40');
 assert.equal(timeBucket('2026-12-02T14:31:00Z'),'08:30–08:35');
 assert.equal(timeBucket(null),'Unknown Time');
 assert.deepEqual(breakdown(buildSignals(events),'bucket').map(s=>s.label),['08:30–08:35','09:00–09:05','09:10–09:15','09:20–09:25']);
});
test('render includes all six complete rows and the three requested breakdowns',()=>{
 const React=appRequire('react'),{renderToStaticMarkup}=appRequire('react-dom/server');
 const Analysis=require(path.join(route,'Analysis.tsx')).default;
 const html=renderToStaticMarkup(React.createElement(Analysis,{events}));
 for(const text of ['Analysis By Grade','Long / Short Analysis','5-Minute Entry Time Analysis','Ungraded','UNRESOLVED_WITH_RESOLUTION_TIMESTAMP','Database Metadata','Full Original Row'])assert.ok(html.includes(text),text);
 for(const event of events){assert.ok(html.includes('#'+event.id+' ·'));assert.ok(html.includes(event.webhook_event_key));}
 assert.ok(html.includes('0.98%'));assert.ok(html.includes('0.82%'));assert.ok(html.includes('33.33%'));
});
test('direction filter narrows signal rollups and full event details together',()=>{
 const React=appRequire('react'),{renderToStaticMarkup}=appRequire('react-dom/server');
 const Analysis=require(path.join(route,'Analysis.tsx')).default;
 const original=React.useState;let index=0;
 try {React.useState=initial=>{const state=original(initial);return index++===0?['Short',state[1]]:state;};
 const html=renderToStaticMarkup(React.createElement(Analysis,{events}));assert.ok(html.includes('#10 ·'));assert.ok(!html.includes('#11 ·'));assert.ok(!html.includes('#1 ·'));assert.ok(html.includes('1 of 4 signals'));
 }finally{React.useState=original;}
});
test('time analysis includes 78 closed intervals and honest sparse rankings',()=>{
 const React=appRequire('react'),{renderToStaticMarkup}=appRequire('react-dom/server');
 const {default:TimeAnalysis,timeRows,rankedTimes,intervals}=require(path.join(route,'TimeAnalysis.tsx'));
 assert.equal(intervals.length,78);assert.equal(intervals[0],'08:30–08:35');assert.equal(intervals.at(-1),'14:55–15:00');
 const signals=buildSignals(events),rows=timeRows(signals);
 assert.equal(rows[0].long.signals,1);assert.equal(rows[0].long.favorableRate,100);
 assert.equal(rankedTimes(rows,'long')[0].label,'08:30–08:35');assert.equal(rankedTimes(rows,'long',true)[0].label,'09:00–09:05');
 assert.equal(rankedTimes(rows,'long').length,2);assert.equal(rankedTimes(rows,'short').length,1);assert.equal(rankedTimes(timeRows([]),'long').length,0);
 const html=renderToStaticMarkup(React.createElement(TimeAnalysis,{signals}));
 assert.equal((html.match(/<details/g)||[]).length,81);assert.ok(!/<details[^>]*\bopen[=> ]/.test(html));
 for(const text of ['Top 4 Long Times','Bottom 4 Long Times','Top 4 Short Times','Bottom 4 Short Times','No signals in this interval.'])assert.ok(html.includes(text),text);
 assert.equal(timeBucket('2026-12-02T14:35:00Z','America/Chicago'),'08:35–08:40');
});
