const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createRequire}=require('node:module');
const app=path.resolve(__dirname,'../../apps/trading-research-web');
const appRequire=createRequire(path.join(app,'package.json'));
const ts=appRequire('typescript');
require.extensions['.tsx']=require.extensions['.ts']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true,target:ts.ScriptTarget.ES2022}}).outputText,f);
require.extensions['.css']=(m)=>{m.exports=new Proxy({},{get:(_,k)=>String(k)});};
const React=appRequire('react');
const {renderToStaticMarkup}=appRequire('react-dom/server');
const Chart=require(path.join(app,'app/dashboard/sector-rotation/RelativePerformance.tsx')).default;
const sessions=Array.from({length:70},(_,i)=>({date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),cells:{XLK:{daily:i%2?2:-1,relative:i%2?.75:-.25,rank:i%2?1:3,rankChange:i%2?2:-2}}}));
const props={sessions,timeline:sessions.slice(42,62),symbol:'XLK',selectedDate:sessions[61].date,onSelect:()=>{}};
const render=(metric)=>renderToStaticMarkup(React.createElement(Chart,{...props,...(metric?{metric}:{})}));
test('default relative chart and daily chart show values and averages in their own units',()=>{
 const relative=render();assert.match(relative,/Selected/);assert.match(relative,/Highest visible value/);assert.match(relative,/Average up: \+0.75 pp/);assert.match(relative,/Average down: -0.25 pp/);
 assert.ok(relative.indexOf('Highest visible value')<relative.indexOf('Average up:'));
 const daily=render('daily');assert.match(daily,/Average up: \+2.00%/);assert.match(daily,/Average down: -1.00%/);assert.doesNotMatch(daily,/0 pp at center/);
 for(const html of [relative,daily]){assert.equal((html.match(/aria-hidden="true"/g)||[]).length,2);assert.equal((html.match(/<button/g)||[]).length,20);}
});
test('rank and rank-change charts use rank values, labels and no return-average lines',()=>{
 const rank=render('rank');assert.match(rank,/Best visible rank/);assert.match(rank,/#1/);assert.match(rank,/Worst visible rank/);assert.match(rank,/#3/);
 const change=render('rankChange');assert.match(change,/↑2 places/);assert.match(change,/↓2 places/);
 for(const html of [rank,change]){assert.doesNotMatch(html,/Average up:/);assert.equal((html.match(/aria-hidden="true"/g)||[]).length,0);}
});
test('missing and early-history views show unavailable values and withhold reference lines',()=>{
 const html=renderToStaticMarkup(React.createElement(Chart,{...props,timeline:[],selectedDate:sessions[10].date}));
 assert.match(html,/Average up: unavailable/);assert.match(html,/Highest visible value<\/span><strong>—/);assert.equal((html.match(/aria-hidden="true"/g)||[]).length,0);
});
test('tracker chart uses every heatmap session in the same newest-first order',()=>{
 const {SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));
 const Tracker=require(path.join(app,'app/dashboard/sector-rotation/Tracker.tsx')).default;
 const bars=Array.from({length:130},(_,i)=>['SPY',...SECTORS.map(s=>s.symbol)].map((symbol,j)=>({symbol,trade_date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),close:100+i+j,volume:1}))).flat();
 const html=renderToStaticMarkup(React.createElement(Tracker,{bars,updatedAt:null,latestSession:bars.at(-1).trade_date,runStatus:'SUCCESS',error:null}));
 const heatmap=html.split('<thead>')[1].split('</thead>')[0];
 const dates=[...heatmap.matchAll(/<small>(\d{4}-\d{2}-\d{2})<\/small>/g)].map(m=>m[1]);
 const chartDates=[...html.matchAll(/<time dateTime="(\d{4}-\d{2}-\d{2})"/g)].map(m=>m[1]);
 assert.equal(dates.length,60);assert.deepEqual(chartDates,dates);
 const large=renderToStaticMarkup(React.createElement(Chart,{...props,timeline:Array.from({length:120},(_,i)=>({...sessions[0],date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10)})).reverse()}));
 assert.equal((large.match(/<button/g)||[]).length,120);assert.equal((large.match(/<time dateTime=/g)||[]).length,120);
});
test('streak panel renders two-decimal means, counts and the selected measure',()=>{
 const StreakSummary=require(path.join(app,'app/dashboard/sector-rotation/StreakSummary.tsx')).default;
 const days=[0,1,1,-1,-1,1,-1,0,9].map((daily,i)=>({date:String(i),cells:{XLK:{daily,relative:-daily}}}));
 const html=renderToStaticMarkup(React.createElement(StreakSummary,{sessions:days,symbol:'XLK',date:'8',measure:'daily'}));
 assert.match(html,/Green days/);assert.match(html,/Red days/);assert.match(html,/>1.50<\/td><td>2/);assert.match(html,/Daily price return/);
 const relative=renderToStaticMarkup(React.createElement(StreakSummary,{sessions:days,symbol:'XLK',date:'8',measure:'relative'}));
 assert.match(relative,/Relative to SPY/);assert.match(relative,/outperforming SPY/);
});
