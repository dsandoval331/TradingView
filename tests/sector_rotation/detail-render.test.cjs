const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createRequire}=require('node:module');
const app=path.resolve(__dirname,'../../apps/trading-research-web');
const appRequire=createRequire(path.join(app,'package.json'));
const ts=appRequire('typescript');
require.extensions['.tsx']=require.extensions['.ts']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true,target:ts.ScriptTarget.ES2022}}).outputText,f);
require.extensions['.css']=(m)=>{m.exports=new Proxy({},{get:(_,k)=>k==='__esModule'?false:String(k)});};
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
test('tracker performance chart reverses heatmap chronology to match daily candles',()=>{
 const {SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));
 const Tracker=require(path.join(app,'app/dashboard/sector-rotation/Tracker.tsx')).default;
 const bars=Array.from({length:130},(_,i)=>['SPY',...SECTORS.map(s=>s.symbol)].map((symbol,j)=>({symbol,trade_date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),close:100+i+j,volume:1}))).flat();
 const html=renderToStaticMarkup(React.createElement(Tracker,{bars,updatedAt:null,latestSession:bars.at(-1).trade_date,runStatus:'SUCCESS',error:null}));
 const heatmap=html.split('<thead>')[1].split('</thead>')[0];
 const dates=[...heatmap.matchAll(/<small>(\d{4}-\d{2}-\d{2})<\/small>/g)].map(m=>m[1]);
 const chartDates=[...html.matchAll(/<time dateTime="(\d{4}-\d{2}-\d{2})"/g)].map(m=>m[1]);
 assert.equal(dates.length,60);assert.deepEqual(chartDates,[...dates].reverse());
 const large=renderToStaticMarkup(React.createElement(Chart,{...props,timeline:Array.from({length:120},(_,i)=>({...sessions[0],date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10)})).reverse()}));
 assert.equal((large.match(/<button/g)||[]).length,120);assert.equal((large.match(/<time dateTime=/g)||[]).length,120);
});
test('streak panel renders two-decimal means, counts and the selected measure',()=>{
 const StreakSummary=require(path.join(app,'app/dashboard/sector-rotation/StreakSummary.tsx')).default;
 const days=[0,1,1,-1,-1,1,-1,0,9].map((daily,i)=>({date:String(i),cells:{XLK:{daily,relative:-daily}}}));
 const html=renderToStaticMarkup(React.createElement(StreakSummary,{sessions:days,symbol:'XLK',date:'8',measure:'daily'}));
 assert.match(html,/Green days/);assert.match(html,/Red days/);assert.match(html,/Longest streak \(days\)/);assert.match(html,/>1.50<\/td><td>2/);assert.match(html,/Daily price return/);
 const relative=renderToStaticMarkup(React.createElement(StreakSummary,{sessions:days,symbol:'XLK',date:'8',measure:'relative'}));
 assert.match(relative,/Relative to SPY/);assert.match(relative,/outperforming SPY/);
});
test('daily candles sit after Sector Detail and use every filtered heatmap session',()=>{
 const {SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));
 const Tracker=require(path.join(app,'app/dashboard/sector-rotation/Tracker.tsx')).default;
 const bars=Array.from({length:130},(_,i)=>['SPY',...SECTORS.map(s=>s.symbol)].map((symbol,j)=>({symbol,trade_date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),open:100+i+j,high:104+i+j,low:99+i+j,close:102+i+j,volume:1}))).flat();
 const html=renderToStaticMarkup(React.createElement(Tracker,{bars,updatedAt:null,latestSession:bars.at(-1).trade_date,runStatus:'COMPLETE',error:null}));
 const dates=[...html.split('<thead>')[1].split('</thead>')[0].matchAll(/<small>(\d{4}-\d{2}-\d{2})<\/small>/g)].map(m=>m[1]);
 const candleDates=[...html.matchAll(/data-candle-date="([^"]+)"/g)].map(m=>m[1]);
 assert.deepEqual(candleDates,[...dates].reverse());assert.ok(html.indexOf('DAILY PRICE HISTORY')>html.indexOf('</aside>'));
 assert.match(html,/Open \$230.00/);assert.match(html,/60 of 60 sessions available/);
});
test('basket chart is close-only, keeps missing gaps, and custom windows have no extra sessions',()=>{
 const Daily=require(path.join(app,'app/dashboard/sector-rotation/DailyCandles.tsx')).default;
 const days=[100,null,102].map((close,i)=>({date:`2025-01-0${i+2}`,cells:{HW:{close}}}));
 const html=renderToStaticMarkup(React.createElement(Daily,{bars:[],sessions:days,group:{symbol:'HW',kind:'basket'},selectedDate:days[2].date,onSelect:()=>{}}));
 assert.match(html,/Basket closing index/);assert.match(html,/2 of 3 sessions available/);assert.doesNotMatch(html,/Open \$/);
 assert.match(html,/<path d="M[^L]+M/);assert.equal((html.match(/data-candle-date=/g)||[]).length,3);
});
test('price chart follows its supplied overlay and uses full pre-window history',()=>{
 const Daily=require(path.join(app,'app/dashboard/sector-rotation/DailyCandles.tsx')).default;
 const days=Array.from({length:80},(_,i)=>({date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),cells:{XLK:{close:100+i}}}));
 const bars=days.map((d,i)=>({symbol:'XLK',trade_date:d.date,open:99+i,low:98+i,high:102+i,close:100+i,volume:1}));
 const html=renderToStaticMarkup(React.createElement(Daily,{bars,sessions:days.slice(-20),historySessions:days,group:{symbol:'XLK'},selectedDate:days.at(-1).date,onSelect:()=>{}}));
 assert.doesNotMatch(html,/<select/);
 const hidden=renderToStaticMarkup(React.createElement(Daily,{bars,sessions:days.slice(-20),historySessions:days,group:{symbol:'XLK'},line:'none',selectedDate:days.at(-1).date,onSelect:()=>{}}));
 assert.doesNotMatch(hidden,/data-overlay="ema20"|20 EMA ·/);
 assert.match(html,/data-overlay="ema20"/);assert.match(html,/20 EMA · \$169.50/);assert.match(html,/20 of 20 sessions available/);
 assert.doesNotMatch(html,/Unavailable · needs 20 consecutive closes/);
});
test('heatmap has latest Price before historical dates and marks only closes below a warmed-up EMA',()=>{
 const {SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));
 const Tracker=require(path.join(app,'app/dashboard/sector-rotation/Tracker.tsx')).default;
 const fixture=(falling)=>Array.from({length:30},(_,i)=>['SPY',...SECTORS.map(s=>s.symbol)].map(symbol=>({symbol,trade_date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),close:falling?300-i:300,volume:1}))).flat();
 const render=(falling)=>renderToStaticMarkup(React.createElement(Tracker,{bars:fixture(falling),updatedAt:null,latestSession:'2025-01-30',runStatus:'COMPLETE',error:null}));
 const html=render(true);
 assert.equal((html.match(/aria-label="Chart line"/g)||[]).length,1);
 assert.ok(html.indexOf('aria-label="Chart line"')<html.indexOf('<table'));
 assert.match(html,/value="ema20" selected="">20 EMA/);
 const head=html.split('<thead>')[1].split('</thead>')[0];
 assert.ok(head.indexOf('ETF / Group')<head.indexOf('Price'));assert.ok(head.indexOf('Price')<head.indexOf('Thu, Jan 30'));
 assert.match(html,/<strong>\$271.00<\/strong>/);assert.match(html,/latest close on 2025-01-30: 271, daily return -0.37%/);
 assert.equal((html.match(/>20E<\/sup>/g)||[]).length,11*11);
 assert.match(html,/2025-01-20: close 281.00 below 20 EMA 290.50/);
 assert.doesNotMatch(render(false),/>20E<\/sup>/);
});
test('stock detail reuses candles and EMA controls without ETF holdings or single-stock ranks',()=>{
 const {SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));
 const Tracker=require(path.join(app,'app/dashboard/sector-rotation/Tracker.tsx')).default;
 const {TOP_50_STOCKS}=require(path.join(app,'app/dashboard/sector-rotation/stocks/symbols.ts'));
 const bars=Array.from({length:90},(_,i)=>['SPY',...TOP_50_STOCKS.map(g=>g.symbol)].map((symbol,j)=>({symbol,trade_date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),open:100+i+j,high:104+i+j,low:99+i+j,close:102+i+j,volume:1}))).flat();
 const props={bars,stocks:true,updatedAt:null,latestSession:'2025-03-31',runStatus:'COMPLETE',error:null};
 const single=renderToStaticMarkup(React.createElement(Tracker,{...props,singleStock:true,groups:[TOP_50_STOCKS[0]]}));
 assert.match(single,/STOCK DETAIL/);assert.match(single,/Move vs directional average/);assert.match(single,/Consecutive day streaks/);assert.match(single,/data-overlay="ema20"/);
 assert.doesNotMatch(single,/Top 5 stock holdings|Verified holdings are unavailable|<option value="rank"|<dt>Stock rank/);
 const frequent=renderToStaticMarkup(React.createElement(Tracker,{...props,groups:TOP_50_STOCKS}));
 assert.match(frequent,/<option value="rank"/);assert.match(frequent,/<dt>Stock rank/);for(const g of TOP_50_STOCKS)assert.match(frequent,new RegExp(g.symbol));
});
test('50 EMA and volume bars use full history and aligned candle slots',()=>{
 const Daily=require(path.join(app,'app/dashboard/sector-rotation/DailyCandles.tsx')).default;
 const days=Array.from({length:80},(_,i)=>({date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),cells:{XLK:{close:100+i}}}));
 const bars=days.map((d,i)=>({symbol:'XLK',trade_date:d.date,open:99+i,low:98+i,high:102+i,close:100+i,volume:1000+i*10}));
 const html=renderToStaticMarkup(React.createElement(Daily,{bars,sessions:days.slice(-20),historySessions:days,group:{symbol:'XLK'},line:'ema50',selectedDate:days.at(-1).date,onSelect:()=>{}}));
 assert.match(html,/data-overlay="ema50"/);assert.match(html,/50 EMA · \$154.50/);assert.match(html,/data-overlay="volume-average"/);
 assert.deepEqual([...html.matchAll(/data-volume-date="([^"]+)"/g)].map(m=>m[1]),days.slice(-20).map(d=>d.date));
 const basket=renderToStaticMarkup(React.createElement(Daily,{bars,sessions:days.slice(-20),historySessions:days,group:{symbol:'XLK',kind:'basket'},onSelect:()=>{}}));
 assert.doesNotMatch(basket,/data-volume-date|data-overlay="volume-average"/);assert.match(basket,/Basket volume is unavailable/);
});
test('volume average includes today, respects zeros, and restarts after missing data',()=>{
 const {volumeSeries}=require(path.join(app,'app/dashboard/sector-rotation/volume.ts'));
 const days=Array.from({length:7},(_,i)=>({date:String(i),cells:{}}));
 const bars=[0,3,6,null,6,9,12].flatMap((volume,i)=>volume===null?[]:[{symbol:'X',trade_date:String(i),volume}]);
 const v=volumeSeries(bars,days,'X',3);
 assert.equal(v.get('0').volume,0);assert.equal(v.get('1').average,null);assert.equal(v.get('2').average,3);
 assert.deepEqual(v.get('3'),{volume:null,average:null});assert.equal(v.get('5').average,null);assert.equal(v.get('6').average,9);
 assert.throws(()=>volumeSeries([...bars,bars[0]],days,'X',3),/Duplicate/);
});
const eventFixture=(values,overrides={})=>values.map((v,i)=>({date:String(i).padStart(3,'0'),complete:true,cells:{X:{close:200-i,daily:v,relative:-v,rank:1,rankChange:v,...overrides}}}));
const eventGroup=[{symbol:'X',name:'X',short:'X'}];
test('EMA events count first day, consecutive markers, and reset at equality or missing metric',()=>{
 const {dailyEvents}=require(path.join(app,'app/dashboard/sector-rotation/events.ts'));
 const days=eventFixture(Array(55).fill(1));
 let events=dailyEvents(days,eventGroup,'daily','ema50');
 assert.equal(events[48].ema.length,0);assert.equal(events[49].ema[0].days,1);assert.equal(events[54].ema[0].days,6);
 days[52].cells.X.daily=null;events=dailyEvents(days,eventGroup,'daily','ema50');assert.equal(events[52].ema.length,0);assert.equal(events[53].ema[0].days,1);
 assert.ok(dailyEvents(days,eventGroup,'daily','none').every(d=>!d.ema.length));
 const flat=days.map(d=>({...d,cells:{X:{...d.cells.X,close:100}}}));assert.ok(dailyEvents(flat,eventGroup,'daily','ema20').every(d=>!d.ema.length));
});
test('event averages exclude today and future, use the selected metric, and require valid warmup',()=>{
 const {dailyEvents}=require(path.join(app,'app/dashboard/sector-rotation/events.ts'));
 const days=eventFixture([...Array.from({length:60},(_,i)=>i%2?2:-1),3,-2,999]);
 const events=dailyEvents(days,eventGroup,'daily','none');
 assert.equal(events[59].averages.length,0);assert.deepEqual(events[60].averages,[{symbol:'X',side:'Long',value:3,average:2}]);
 assert.deepEqual(events[61].averages,[{symbol:'X',side:'Short',value:-2,average:-1}]);
 assert.equal(dailyEvents(days,eventGroup,'relative','none')[60].averages[0].side,'Short');
 assert.deepEqual(events.slice(0,62),dailyEvents(days.slice(0,62),eventGroup,'daily','none'));
 days[20].cells.X.daily=null;assert.equal(dailyEvents(days,eventGroup,'daily','none')[60].averages.length,0);
 const equal=eventFixture(Array(61).fill(2));assert.equal(dailyEvents(equal,eventGroup,'daily','none')[60].averages.length,0);
 const rank=eventFixture(Array(61).fill(1),{rank:2});rank[60].cells.X.rank=1;
 assert.deepEqual(dailyEvents(rank,eventGroup,'rank','none')[60].averages,[{symbol:'X',side:'Long',value:1,average:2}]);
});
test('event streaks include the ending day, retain historical records, and rank movers include ties',()=>{
 const {dailyEvents}=require(path.join(app,'app/dashboard/sector-rotation/events.ts'));
 const days=eventFixture([1,1,-1,-1,-1,0,1,null,1,1]);
 const events=dailyEvents(days,eventGroup,'daily','none');
 assert.equal(events[4].streaks[0].red,3);assert.equal(events[4].streaks[0].longestRed,3);assert.equal(events[5].streaks[0].red,0);
 assert.equal(events[7].streaks[0].green,0);assert.equal(events[9].streaks[0].green,2);assert.equal(events[9].streaks[0].longestGreen,2);
 const groups=['A','B','C'].map(symbol=>({symbol,name:symbol,short:symbol}));
 const row={date:'1',complete:true,cells:{A:{rankChange:2,daily:1},B:{rankChange:2,daily:1},C:{rankChange:-4,daily:-1}}};
 const e=dailyEvents([row],groups,'daily','none')[0];assert.deepEqual(e.rankUp,{symbols:['A','B'],change:2});assert.deepEqual(e.rankDown,{symbols:['C'],change:-4});
 assert.equal(dailyEvents([{...row,complete:false}],groups,'daily','none')[0].rankUp,null);
});
test('Event Log groups days with alternating shades and includes four day-end sections',()=>{
 const EventLog=require(path.join(app,'app/dashboard/sector-rotation/EventLog.tsx')).default;
 const days=eventFixture(Array(65).fill(-1));
 const html=renderToStaticMarkup(React.createElement(EventLog,{sessions:days,visibleSessions:days.slice(-3),groups:eventGroup,metric:'daily',line:'ema50',onSelect:()=>{}}));
 assert.equal((html.match(/data-event-date=/g)||[]).length,3);assert.match(html,/eventDayAlternate/);assert.match(html,/50E · Close below 50 EMA/);assert.match(html,/Day 16 in a row/);assert.match(html,/Beyond average/);assert.match(html,/Current Longest Streaks/);assert.match(html,/Biggest rank movers/);
});
test('volume average follows 20/60/120 Sessions and All expands without future data',()=>{
 const {volumeSeries}=require(path.join(app,'app/dashboard/sector-rotation/volume.ts'));
 const days=Array.from({length:130},(_,i)=>({date:String(i),cells:{}}));
 const bars=days.map((d,i)=>({symbol:'X',trade_date:d.date,volume:i+1}));
 for(const [period,expected] of [[20,120.5],[60,100.5],[120,70.5],['all',65.5]])assert.equal(volumeSeries(bars,days,'X',period).get('129').average,expected);
 const all=volumeSeries(bars,days,'X','all');assert.equal(all.get('9').average,5.5);
 assert.deepEqual(all.get('9'),volumeSeries(bars.slice(0,10),days.slice(0,10),'X','all').get('9'));
 const Daily=require(path.join(app,'app/dashboard/sector-rotation/DailyCandles.tsx')).default;
 const priceDays=days.map(d=>({...d,cells:{X:{close:100}}}));
 const fullBars=bars.map(b=>({...b,open:99,high:101,low:98,close:100}));
 for(const sessionDuration of [20,60,120,'all']){
  const html=renderToStaticMarkup(React.createElement(Daily,{bars:fullBars,sessions:priceDays.slice(-20),historySessions:priceDays,group:{symbol:'X'},sessionDuration,onSelect:()=>{}}));
  assert.match(html,new RegExp(sessionDuration==='all'?'Expanding average volume':`${sessionDuration}-session average volume`));
 }
});
test('EMA streak mean uses completed fully observed runs in the configured window',()=>{
 const {completedMarkerAverage}=require(path.join(app,'app/dashboard/sector-rotation/events.ts'));
 const markers=Array(30).fill(false);for(const i of [1,2,3,21,22,28,29])markers[i]=true;
 assert.deepEqual(completedMarkerAverage(markers,29,20),{averageStreak:2,completedStreaks:1});
 assert.deepEqual(completedMarkerAverage(markers,29,60),{averageStreak:2.5,completedStreaks:2});
 assert.deepEqual(completedMarkerAverage(markers,29,'all'),{averageStreak:2.5,completedStreaks:2});
 assert.deepEqual(completedMarkerAverage([null,true,true,false,false,true,false],6,20),{averageStreak:1,completedStreaks:1});
 assert.deepEqual(completedMarkerAverage([false,true,true,null,false],4,20),{averageStreak:null,completedStreaks:0});
 const clipped=Array(25).fill(false);for(let i=1;i<8;i++)clipped[i]=true;
 assert.equal(completedMarkerAverage(clipped,24,20).averageStreak,null);
 assert.deepEqual(completedMarkerAverage(markers,23,20),completedMarkerAverage([...markers.slice(0,24),true,true,true,true],23,20));
});
test('current longest winners cover all measures, include ties and ignore historical records',()=>{
 const {dailyEvents}=require(path.join(app,'app/dashboard/sector-rotation/events.ts'));
 const groups=['A','B','C','D'].map(symbol=>({symbol,name:symbol,short:symbol}));
 const days=Array.from({length:5},(_,i)=>({date:String(i),complete:true,cells:Object.fromEntries(groups.map(g=>[g.symbol,{close:100,daily:g.symbol==='D'?(i<4?1:-1):g.symbol==='C'?-1:1,relative:g.symbol==='A'||g.symbol==='B'?-1:1,rank:g.symbol==='A'||g.symbol==='B'?1:4,rankChange:g.symbol==='C'||g.symbol==='D'?-2:2}]))}));
 const result=dailyEvents(days,groups,'daily','none').at(-1).currentLongest;
 assert.equal(result.length,6);
 assert.deepEqual(result.find(m=>m.metric==='daily').green,{days:5,symbols:['A','B']});
 assert.deepEqual(result.find(m=>m.metric==='daily').red,{days:5,symbols:['C']});
 assert.deepEqual(result.find(m=>m.metric==='relative').red,{days:5,symbols:['A','B']});
 assert.deepEqual(result.find(m=>m.metric==='rank').green,{days:5,symbols:['A','B']});
 assert.deepEqual(result.find(m=>m.metric==='rankChange').red,{days:5,symbols:['C','D']});
 const first=dailyEvents(days.slice(0,1),groups,'relative','none')[0];assert.ok(first.currentLongest.every(m=>m.green===null&&m.red===null));
 assert.deepEqual(dailyEvents(days,groups,'relative','none').at(-1).currentLongest,result);
 days.at(-1).cells.C.daily=null;assert.equal(dailyEvents(days,groups,'daily','none').at(-1).currentLongest.find(m=>m.metric==='daily').red,null);
});
test('Event Log groups Long and Short and shows winners for every measure with N/A',()=>{
 const EventLog=require(path.join(app,'app/dashboard/sector-rotation/EventLog.tsx')).default;
 const days=eventFixture(Array(65).fill(-1));
 const html=renderToStaticMarkup(React.createElement(EventLog,{sessions:days,visibleSessions:days.slice(-3),groups:eventGroup,metric:'daily',line:'ema50',sessionDuration:20,onSelect:()=>{}}));
 assert.match(html,/Average streak \(20 sessions\):/);assert.match(html,/data-event-side="Long"/);assert.match(html,/data-event-side="Short"/);
 assert.ok(html.indexOf('data-event-side="Long"')<html.indexOf('data-event-side="Short"'));
 const table=html.match(/<table[^>]*data-current-streaks[^>]*>([\s\S]*?)<\/table>/)[1];
 for(const measure of ['Relative to SPY','Daily return','Daily rank','Rank change'])assert.match(table,new RegExp(measure));
 assert.match(table,/N\/A/);assert.doesNotMatch(table,/Longest green|Current green/);
});
test('swing trade age uses Day 0, weekdays only, and includes weekday holidays',()=>{
 const {weekdaysSince,addWeekdays}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));
 assert.equal(weekdaysSince('2026-10-23','2026-10-23'),0);
 assert.equal(weekdaysSince('2026-10-23','2026-10-25'),0);
 assert.equal(weekdaysSince('2026-10-23','2026-10-26'),1);
 assert.equal(weekdaysSince('2026-10-23','2026-11-13'),15);
 assert.equal(weekdaysSince('2026-10-23','2026-11-16'),16);
 assert.equal(weekdaysSince('2026-12-24','2026-12-25'),1);
 assert.equal(addWeekdays('2026-10-23',15),'2026-11-13');assert.equal(addWeekdays('2026-10-23',16),'2026-11-16');
 assert.throws(()=>weekdaysSince('2026-02-30','2026-03-01'),/Invalid/);
});
const swingSuggestion={id:'test-only',symbol:'X',suggestedDate:'2026-10-23',side:'long',entryPrice:100,reason:'Synthetic test fixture; not a suggestion.'};
const swingBars=[{symbol:'X',trade_date:'2026-10-23',close:100,high:999,low:1,volume:1},{symbol:'X',trade_date:'2026-10-26',close:105,high:110,low:95,volume:1},{symbol:'X',trade_date:'2026-10-27',close:90,high:108,low:85,volume:1},{symbol:'X',trade_date:'2026-11-13',close:107,high:112,low:99,volume:1},{symbol:'X',trade_date:'2026-11-16',close:1000,high:2000,low:.1,volume:1}];
test('swing trade tracking excludes pre-entry highs/lows and future bars; handles Long and Short',()=>{
 const {trackSwingTrades}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));
 const day0=trackSwingTrades([swingSuggestion],swingBars,'2026-10-23')[0];assert.equal(day0.days,0);assert.equal(day0.currentPrice,100);assert.equal(day0.mfa,0);assert.equal(day0.mae,0);
 const long=trackSwingTrades([swingSuggestion],swingBars,'2026-10-27')[0];assert.equal(long.mfa,10);assert.equal(long.mae,15);assert.equal(long.priceChange,-10);assert.equal(long.percentChange,-10);
 const short=trackSwingTrades([{...swingSuggestion,side:'short'}],swingBars,'2026-10-27')[0];assert.equal(short.mfa,15);assert.equal(short.mae,10);assert.equal(short.priceChange,-10);
 assert.equal(trackSwingTrades([{...swingSuggestion,suggestedDate:'2026-11-01'}],swingBars,'2026-10-27').length,0);
});
test('swing trades stay active through Day 15 and archive at Day 16 with a fixed price horizon',()=>{
 const {trackSwingTrades}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));
 assert.equal(trackSwingTrades([swingSuggestion],swingBars,'2026-11-13')[0].status,'active');
 const archived=trackSwingTrades([swingSuggestion],swingBars,'2026-11-16')[0];assert.equal(archived.status,'archive');assert.equal(archived.days,16);assert.equal(archived.archivedDate,'2026-11-16');assert.equal(archived.measurementEnd,'2026-11-13');assert.equal(archived.currentPrice,107);assert.equal(archived.mfa,12);assert.equal(archived.mae,15);
 assert.deepEqual(trackSwingTrades([swingSuggestion],swingBars,'2026-12-31')[0],archived);
 assert.deepEqual(trackSwingTrades([swingSuggestion],swingBars.filter(b=>b.trade_date<='2026-11-13'),'2026-12-31')[0],archived);
});
test('swing missing data remains unavailable and duplicate or invalid records are rejected',()=>{
 const {trackSwingTrades}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));
 const missing=trackSwingTrades([swingSuggestion],[],'2026-10-26')[0];assert.equal(missing.currentPrice,null);assert.equal(missing.mfa,null);assert.equal(missing.mae,null);
 const closeOnly=trackSwingTrades([swingSuggestion],[{symbol:'X',trade_date:'2026-10-26',close:105,volume:1}],'2026-10-26')[0];assert.equal(closeOnly.currentPrice,105);assert.equal(closeOnly.mfa,null);assert.equal(closeOnly.missingOHLC,1);
 assert.throws(()=>trackSwingTrades([{...swingSuggestion,entryPrice:0}],[],'2026-10-26'),/Invalid/);
 assert.throws(()=>trackSwingTrades([swingSuggestion,swingSuggestion],[],'2026-10-26'),/Invalid/);
 assert.throws(()=>trackSwingTrades([swingSuggestion],[swingBars[1],swingBars[1]],'2026-10-26'),/Duplicate/);
});
test('Swing Trades has empty Active/Archive without fabricated suggestions and renders reasoning before data',()=>{
 const Swing=require(path.join(app,'app/dashboard/sector-rotation/SwingTrades.tsx')).default;
 const groups=[{symbol:'X',name:'X',short:'X'},{symbol:'HW',name:'Basket',short:'Basket',kind:'basket'}];
 const props={bars:swingBars,groups,asOfDate:'2026-10-27'};
 const empty=renderToStaticMarkup(React.createElement(Swing,props));assert.match(empty,/Suggested Swing Trades/);assert.match(empty,/Beta/);assert.match(empty,/No active suggestions yet/);assert.match(empty,/Archive \(0\)/);assert.doesNotMatch(empty,/test-only|Synthetic test/);
 const active=renderToStaticMarkup(React.createElement(Swing,{...props,suggestions:[swingSuggestion]}));assert.ok(active.indexOf(swingSuggestion.reason)<active.indexOf('<table'));assert.match(active,/Day 2/);assert.match(active,/MFA/);assert.match(active,/MAE/);assert.match(active,/As of 2026-10-27/);
 const archive=renderToStaticMarkup(React.createElement(Swing,{...props,asOfDate:'2026-11-16',suggestions:[swingSuggestion]}));assert.match(archive,/Archive \(1\)/);assert.match(archive,/Final price/);assert.match(archive,/Day 16/);
 const excluded=renderToStaticMarkup(React.createElement(Swing,{...props,suggestions:[{...swingSuggestion,symbol:'HW'}]}));assert.match(excluded,/No active suggestions yet/);
});
test('rolling Event Log keeps at most 120 dates and each new date displaces the oldest',()=>{
 const {rollingEventDays,EVENT_LOG_MAX_DAYS}=require(path.join(app,'app/dashboard/sector-rotation/events.ts'));
 const history=Array.from({length:235},(_,i)=>({date:String(i).padStart(3,'0')}));
 const first=rollingEventDays(history,new Set(history.map(d=>d.date)));assert.equal(first.length,120);assert.equal(first[0].date,'234');assert.equal(first.at(-1).date,'115');
 const next=[...history,{date:'235'}];const second=rollingEventDays(next,new Set(next.map(d=>d.date)));assert.equal(second.length,EVENT_LOG_MAX_DAYS);assert.equal(second[0].date,'235');assert.equal(second.at(-1).date,'116');assert.ok(!second.some(d=>d.date==='115'));assert.equal(history.length,235);
 assert.equal(rollingEventDays(next,new Set(next.slice(-20).map(d=>d.date))).length,20);
});
test('new indicator chart modes show their units without return-average or rank-change labels',()=>{
 const days=sessions.map(d=>({...d,cells:{XLK:{...d.cells.XLK,rsiRelative:5,mansfield:-2}}}));
 for(const metric of ['rsiRelative','mansfield']){
  const html=renderToStaticMarkup(React.createElement(Chart,{...props,sessions:days,timeline:days.slice(-20),metric}));
  assert.match(html,metric==='rsiRelative'?/RSI pts/:/200-session SMA/);assert.doesNotMatch(html,/Average up:|↑ means improvement/);
 }
});
test('single-stock heatmap offers RSI and Mansfield and the Event Log renders six measure rows',()=>{
 const Tracker=require(path.join(app,'app/dashboard/sector-rotation/Tracker.tsx')).default;
 const bars=Array.from({length:220},(_,i)=>['SPY','X'].map(symbol=>({symbol,trade_date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),close:symbol==='SPY'?100:100+i,volume:1}))).flat();
 const html=renderToStaticMarkup(React.createElement(Tracker,{bars,stocks:true,singleStock:true,groups:eventGroup,updatedAt:null,latestSession:bars.at(-1).trade_date,runStatus:'COMPLETE',error:null}));
 assert.match(html,/<option value="rsiRelative"/);assert.match(html,/<option value="mansfield"/);assert.doesNotMatch(html,/<option value="rank"/);
 const table=html.match(/<table[^>]*data-current-streaks[^>]*>([\s\S]*?)<\/table>/)[1];assert.equal((table.match(/<tr>/g)||[]).length,7);assert.match(table,/RSI vs SPY RSI/);assert.match(table,/Mansfield RS/);
});
