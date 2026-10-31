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
const ModuleForActions=require('node:module'),originalActionLoad=ModuleForActions._load;
ModuleForActions._load=function(request,parent,isMain){if(request==='./method-one-action')return {runMethodOne:async()=>{throw new Error('Server action must be explicitly mocked in render fixtures');}};return originalActionLoad.call(this,request,parent,isMain);};
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
 assert.deepEqual(candleDates,[...dates].reverse());assert.ok(html.indexOf('DAILY PRICE HISTORY')>html.indexOf('</aside>'));assert.ok(html.indexOf('class="relativeChart"')>html.indexOf('DAILY PRICE HISTORY'));assert.doesNotMatch(html.slice(html.indexOf('<aside'),html.indexOf('</aside>')),/class="relativeChart"/);
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
 const days=eventFixture(Array(65).fill(-1)).map((day,i)=>({...day,date:new Date(Date.UTC(2026,7,25+i)).toISOString().slice(0,10)}));
 const html=renderToStaticMarkup(React.createElement(EventLog,{asOfDate:'2026-10-28',sessions:days,visibleSessions:days.slice(-3),groups:eventGroup,metric:'daily',line:'ema50',onSelect:()=>{}}));
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
 const days=eventFixture(Array(65).fill(-1)).map((day,i)=>({...day,date:new Date(Date.UTC(2026,7,25+i)).toISOString().slice(0,10)}));
 const html=renderToStaticMarkup(React.createElement(EventLog,{asOfDate:'2026-10-28',sessions:days,visibleSessions:days.slice(-3),groups:eventGroup,metric:'daily',line:'ema50',sessionDuration:20,onSelect:()=>{}}));
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
const swingSuggestion={id:'test-only',methodId:1,symbol:'X',suggestedDate:'2026-10-23',side:'long',entryPrice:100,reason:'Synthetic test fixture; not a suggestion.'};
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
 const empty=renderToStaticMarkup(React.createElement(Swing,props));assert.match(empty,/Suggested Swing Trades/);assert.match(empty,/Beta/);assert.match(empty,/No active suggestions match the current rules and filters/);assert.match(empty,/Archive \(0\)/);assert.doesNotMatch(empty,/test-only|Synthetic test/);
 const active=renderToStaticMarkup(React.createElement(Swing,{...props,suggestions:[swingSuggestion]}));assert.ok(active.indexOf(swingSuggestion.reason)<active.indexOf('<table'));assert.match(active,/Day 2/);assert.match(active,/MFA/);assert.match(active,/MAE/);assert.match(active,/As of 2026-10-27/);
 const archive=renderToStaticMarkup(React.createElement(Swing,{...props,asOfDate:'2026-11-16',suggestions:[swingSuggestion]}));assert.match(archive,/Archive \(1\)/);assert.match(archive,/Final price/);assert.match(archive,/Day 16/);
 const excluded=renderToStaticMarkup(React.createElement(Swing,{...props,suggestions:[{...swingSuggestion,symbol:'HW'}]}));assert.match(excluded,/No active suggestions match these filters/);
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
 const html=renderToStaticMarkup(React.createElement(Tracker,{bars,asOfDate:bars.at(-1).trade_date,stocks:true,singleStock:true,groups:eventGroup,updatedAt:null,latestSession:bars.at(-1).trade_date,runStatus:'COMPLETE',error:null}));
 assert.match(html,/<option value="rsiRelative"/);assert.match(html,/<option value="mansfield"/);assert.doesNotMatch(html,/<option value="rank"/);
 const table=html.match(/<table[^>]*data-current-streaks[^>]*>([\s\S]*?)<\/table>/)[1];assert.equal((table.match(/<tr>/g)||[]).length,7);assert.match(table,/RSI vs SPY RSI/);assert.match(table,/Mansfield RS/);
});

test('numbered methods persist in Active and Archive and unidentified suggestions are rejected',()=>{
 const {trackSwingTrades,SWING_METHODS}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));
 const Swing=require(path.join(app,'app/dashboard/sector-rotation/SwingTrades.tsx')).default;
 assert.deepEqual(SWING_METHODS.map(m=>m.id),[1,2,3]);
 const suggestions=[swingSuggestion,{...swingSuggestion,id:'test-method-2',methodId:2}];
 for(const date of ['2026-10-27','2026-11-16']){
  assert.deepEqual(trackSwingTrades(suggestions,swingBars,date).map(row=>row.methodId),[1,2]);
  const html=renderToStaticMarkup(React.createElement(Swing,{bars:swingBars,groups:[{symbol:'X',name:'Fixture',short:'Fixture'}],asOfDate:date,suggestions}));
  assert.match(html,/#1 · Sector rotation/);assert.match(html,/#2 · RSI\(2\) trend pullback/);
  assert.match(html,/<th scope="col">Method<\/th>/);assert.match(html,/Retrospective screen/);assert.match(html,/Configurable screen/);
 }
 assert.throws(()=>trackSwingTrades([{...swingSuggestion,methodId:4}],[], '2026-10-27'),/Invalid swing suggestion/);
 const {methodId,...unidentified}=swingSuggestion;
 assert.throws(()=>trackSwingTrades([unidentified],[], '2026-10-27'),/Invalid swing suggestion/);
});

test('retrospective swing entries show provenance and retain newest-first order',()=>{
 const Swing=require(path.join(app,'app/dashboard/sector-rotation/SwingTrades.tsx')).default;
 const suggestions=[{...swingSuggestion,id:'older',methodId:2,origin:'retrospective',recordedAt:'2026-10-26T22:00:00Z',suggestedDate:'2026-10-20',reason:'Older retrospective row.'},{...swingSuggestion,id:'newer',methodId:2,origin:'retrospective',recordedAt:'2026-10-26T22:00:00Z',suggestedDate:'2026-10-23',reason:'Newest retrospective row.'}];
 const html=renderToStaticMarkup(React.createElement(Swing,{bars:swingBars,groups:[{symbol:'X',name:'Fixture',short:'Fixture'}],asOfDate:'2026-10-26',suggestions}));
 assert.ok(html.indexOf('Newest retrospective row.')<html.indexOf('Older retrospective row.'));
 assert.match(html,/Retrospective match/);assert.match(html,/Added 2026-10-26/);assert.match(html,/signal-day closing reference/);
});
test('Method 2 screen respects strict thresholds, warmup, gaps, date bounds and repeated matching days',()=>{
 const {backfillMethodTwo}=require(path.join(app,'app/dashboard/sector-rotation/method-two.ts'));
 const date=i=>new Date(Date.UTC(2026,0,1+i)).toISOString().slice(0,10);
 const prices=Array.from({length:220},(_,i)=>i<210?100+i:300-(i-210)*2);
 const bars=prices.flatMap((close,i)=>[{symbol:'X',trade_date:date(i),close,volume:1},{symbol:'SPY',trade_date:date(i),close:100,volume:1}]);
 const rows=backfillMethodTwo(bars,['X'],'2026-08-08');
 assert.ok(rows.length>1);assert.ok(rows.every(s=>s.side==='long'&&s.methodId===2&&s.origin==='retrospective'));
 assert.deepEqual(rows.map(s=>s.suggestedDate),rows.map(s=>s.suggestedDate).sort().reverse());
 const {weekdaysSince}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));
 assert.ok(rows.every(s=>weekdaysSince(s.suggestedDate,'2026-08-08')<15));
 assert.equal(new Set(rows.map(s=>s.id)).size,rows.length);
 const oldest=rows.at(-1);
 const {addWeekdays}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));
 assert.ok(backfillMethodTwo(bars,['X'],addWeekdays(oldest.suggestedDate,14)).some(s=>s.id===oldest.id));
 assert.ok(!backfillMethodTwo(bars,['X'],addWeekdays(oldest.suggestedDate,15)).some(s=>s.id===oldest.id));
 const {methodTwoSide}=require(path.join(app,'app/dashboard/sector-rotation/method-two.ts'));
 assert.equal(methodTwoSide(101,100,5),null);assert.equal(methodTwoSide(99,100,95),null);
 assert.equal(methodTwoSide(100,100,1),null);assert.equal(methodTwoSide(100,100,99),null);
 assert.equal(methodTwoSide(101,100,4.999),'long');assert.equal(methodTwoSide(99,100,95.001),'short');
 const earlier=backfillMethodTwo(bars,['X'],rows.at(-1).suggestedDate);
 assert.deepEqual(earlier.find(s=>s.id===rows.at(-1).id),rows.at(-1));
 assert.deepEqual(backfillMethodTwo(bars.slice(0,398),['X'],date(198)),[]);
 assert.deepEqual(backfillMethodTwo(bars.filter(b=>!(b.symbol==='X'&&b.trade_date===date(205))),['X'],'2026-08-08'),[]);
 assert.deepEqual(backfillMethodTwo(bars,['SPY'],'2026-08-08'),[]);
 assert.deepEqual(backfillMethodTwo(bars,['X'],'2026-09-08'),[]);
 assert.throws(()=>backfillMethodTwo([...bars,bars[0]],['X'],'2026-08-08'),/Duplicate/);
 const flat=bars.map(b=>({...b,close:100}));assert.deepEqual(backfillMethodTwo(flat,['X'],'2026-08-08'),[]);
 const short=prices.map(p=>400-p).flatMap((close,i)=>[{symbol:'X',trade_date:date(i),close,volume:1},{symbol:'SPY',trade_date:date(i),close:100,volume:1}]);
 assert.ok(backfillMethodTwo(short,['X'],'2026-08-08').some(s=>s.side==='short'));
});

test('recorded swing loader paginates snapshots, converts prices and surfaces database errors',async()=>{
 const Module=require('node:module'),original=Module._load;let fail=false;const calls=[];
 const sample={id:'fixture',method_id:2,method_version:'rsi2-sma200-v1',symbol:'X',suggested_date:'2026-10-23',side:'long',entry_price:'100.25',reason:'Fixture',origin:'retrospective',recorded_at:'2026-10-26T22:00:00Z'};
 const client={from(table){assert.equal(table,'sector_swing_suggestions');return {select(){return this;},order(){return this;},async range(start,end){calls.push([start,end]);return fail?{error:{message:'offline'},data:null}:{data:start===0?Array.from({length:1000},(_,i)=>({...sample,id:`fixture-${i}`})):[{...sample,id:'last'}],error:null};}};}};
 Module._load=function(request,parent,isMain){if(request==='server-only')return {};if(request==='../../../lib/supabase/server')return {createClient:async()=>client};return original.call(this,request,parent,isMain);};
 let load;
 try{const file=path.join(app,'app/dashboard/sector-rotation/swing-data.ts');delete require.cache[require.resolve(file)];load=require(file).loadSwingSuggestions;}finally{Module._load=original;}
 const rows=await load();assert.equal(rows.length,1001);assert.equal(rows[0].entryPrice,100.25);assert.equal(rows[0].origin,'retrospective');assert.deepEqual(calls,[[0,999],[1000,1999]]);
 fail=true;await assert.rejects(load(),/could not be loaded/);
});

test('next-session open comparison uses actual sessions and includes entry-day excursions for both sides',()=>{
 const {trackSwingTrades}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));
 const bars=[...swingBars.map(b=>({...b,open:102})),...swingBars.map(b=>({...b,symbol:'SPY',open:100}))];
 const close=trackSwingTrades([swingSuggestion],bars,'2026-10-26')[0];
 const open=trackSwingTrades([swingSuggestion],bars,'2026-10-26','next_open')[0];
 assert.equal(close.entryPrice,100);assert.equal(open.entryPrice,102);assert.equal(open.entryDate,'2026-10-26');
 assert.equal(open.mfa,8);assert.equal(open.mae,7);assert.equal(open.priceChange,3);assert.equal(open.percentChange,3/102*100);
 assert.equal(open.days,close.days);assert.equal(open.suggestedDate,close.suggestedDate);assert.equal(open.currentPrice,close.currentPrice);assert.notEqual(open.id,close.id);assert.equal(open.signalId,close.signalId);
 const short=trackSwingTrades([{...swingSuggestion,side:'short'}],bars,'2026-10-26','next_open')[0];assert.equal(short.mfa,7);assert.equal(short.mae,8);
 const pending=trackSwingTrades([swingSuggestion],bars,'2026-10-23','next_open')[0];assert.equal(pending.entryPrice,null);assert.equal(pending.priceChange,null);assert.equal(pending.mfa,null);
 // If the first actual session has no symbol open, never jump to a later one.
 const missing=bars.map(b=>b.symbol==='X'&&b.trade_date==='2026-10-26'?{...b,open:null}:b);
 const unavailable=trackSwingTrades([swingSuggestion],missing,'2026-10-27','next_open')[0];assert.equal(unavailable.entryPrice,null);assert.equal(unavailable.mae,null);
 const absent=trackSwingTrades([swingSuggestion],bars.filter(b=>!(b.symbol==='X'&&b.trade_date==='2026-10-26')),'2026-10-27','next_open')[0];assert.equal(absent.entryPrice,null);
 // A weekday holiday without a SPY session is skipped.
 const holiday={...swingSuggestion,suggestedDate:'2026-10-23'};
 const tuesday=bars.filter(b=>b.trade_date!=='2026-10-26');assert.equal(trackSwingTrades([holiday],tuesday,'2026-10-27','next_open')[0].entryDate,'2026-10-27');
 const archived=trackSwingTrades([swingSuggestion],bars,'2026-11-16','next_open')[0];
 assert.equal(archived.entryPrice,102);assert.equal(archived.currentPrice,107);assert.equal(archived.mfa,10);assert.equal(archived.days,16);
 assert.deepEqual(trackSwingTrades([swingSuggestion],bars,'2026-12-31','next_open')[0],archived);
});
test('swing table defaults to Longs and Open, shows Day count and keeps one reasoning card per signal',()=>{
 const Swing=require(path.join(app,'app/dashboard/sector-rotation/SwingTrades.tsx')).default;
 const html=renderToStaticMarkup(React.createElement(Swing,{bars:swingBars,groups:[{symbol:'X',name:'Fixture',short:'Fixture'}],asOfDate:'2026-10-26',suggestions:[swingSuggestion]}));
 assert.match(html,/<th scope="col">Strategy<\/th>/);assert.match(html,/<td>Long<\/td>/);assert.match(html,/Next session open/);assert.match(html,/Awaiting next-session open/);
 assert.equal(html.split(swingSuggestion.reason).length-1,1);
 const table=html.slice(html.indexOf('<tbody>'),html.indexOf('</tbody>'));assert.equal((table.match(/<tr>/g)||[]).length,1);
 assert.doesNotMatch(table,/Signal close/);assert.match(table,/Next session open/);assert.match(html,/>Day count<\/th>/);assert.match(html,/aria-pressed="true">Longs/);assert.match(html,/aria-pressed="true">Open/);
});

test('swing statistics weight individual plays and exclude missing or incomplete measurements',()=>{
 const {swingStatistics}=require(path.join(app,'app/dashboard/sector-rotation/swing-statistics.ts'));
 const base={side:'long',missingOHLC:0,mfa:4,mfaPercent:4,mae:2,maePercent:2,percentChange:10};
 const rows=[base,{...base,percentChange:-2},{...base,side:'short',percentChange:-6,mfa:8,mfaPercent:8},{...base,side:'short',percentChange:0},{...base,percentChange:null,mfa:null,mfaPercent:null,mae:null,maePercent:null},{...base,side:'short',percentChange:3,missingOHLC:1,mfa:999,mfaPercent:999}];
 const [long,short,both]=swingStatistics(rows);
 assert.equal(long.count,3);assert.equal(long.pricedCount,2);assert.equal(long.change.value,4);assert.equal(long.up.value,10);assert.equal(long.down.value,-2);
 assert.equal(short.change.value,-1);assert.equal(short.mfe.value,6);assert.equal(short.mfe.count,2);
 assert.equal(both.count,6);assert.equal(both.change.value,1);assert.equal(both.change.count,5);assert.equal(both.up.value,6.5);assert.equal(both.down.value,-4);assert.equal(both.mfe.value,5);assert.equal(both.mfe.count,4);
 for(const stat of swingStatistics([])){assert.equal(stat.count,0);assert.equal(stat.change.value,null);assert.equal(stat.mfe.value,null);}
});
test('stats appear before Archive with all groups and the selected entry basis',()=>{
 const Swing=require(path.join(app,'app/dashboard/sector-rotation/SwingTrades.tsx')).default;
 const html=renderToStaticMarkup(React.createElement(Swing,{bars:swingBars,groups:[{symbol:'X',name:'Fixture',short:'Fixture'}],asOfDate:'2026-10-26',suggestions:[swingSuggestion]}));
 assert.ok(html.indexOf('aria-label="Play statistics"')<html.indexOf('<summary>Archive'));
 assert.match(html,/Avg MFE/);assert.match(html,/Avg MAE/);assert.match(html,/Avg price up/);assert.match(html,/Avg price down/);
 const stats=html.slice(html.indexOf('aria-label="Play statistics"'),html.indexOf('<summary>Archive'));
 assert.match(stats,/>Longs<\/th>/);assert.match(stats,/>Shorts<\/th>/);assert.match(stats,/>Both<\/th>/);assert.match(stats,/Next session open/);
});

function methodOneFixture(short=false){
 const dates=[];let date=new Date('2026-01-01T00:00:00Z');while(dates.length<60){if(date.getUTCDay()!==0&&date.getUTCDay()!==6)dates.push(date.toISOString().slice(0,10));date.setUTCDate(date.getUTCDate()+1);}
 const bars=dates.flatMap((trade_date,i)=>['SPY','XLK','A','B','C','D','UNKNOWN'].map((symbol,j)=>{const sector=100*Math.exp((short?-1:1)*i*i*.0005),close=symbol==='SPY'?100:symbol==='XLK'?sector:sector*Math.exp((short?-1:1)*i*(.014-j*.002));return {symbol,trade_date,close,open:close,high:close+.01,low:close-.01,volume:1};}));
 const config={...require(path.join(app,'app/dashboard/sector-rotation/method-one.ts')).METHOD_ONE_DEFAULTS,instruments:'stocks',direction:short?'short':'long',setups:'breakout',relativePeriod:3,momentumPeriod:1,mansfieldPeriod:3,fastEma:2,slowEma:3,breakoutPeriod:2,marketFilter:'none',rankPeriod:3,tiePeriod:1,startDate:dates[55]};
 return {dates,bars,config,map:{A:'XLK',B:'XLK',C:'XLK',D:'XLK'}};
}
test('Method 1 ranks globally after qualification, emits top 3 and computes repeat history before the display start',()=>{
 const {screenMethodOne}=require(path.join(app,'app/dashboard/sector-rotation/method-one.ts'));
 const {dates,bars,config,map}=methodOneFixture();const result=screenMethodOne(bars,map,[],config,dates.at(-1));
 assert.equal(result.suggestions.length,15);assert.deepEqual(result.unmapped,['UNKNOWN']);
 assert.deepEqual(result.suggestions.filter(s=>s.suggestedDate===dates.at(-1)).map(s=>[s.symbol,s.sectorRank]),[['A',1],['B',2],['C',3]]);
 assert.ok(result.suggestions.every(s=>s.consecutiveDays>1&&s.methodId===1&&s.calculated&&s.setup==='breakout'));
 const prefix=screenMethodOne(bars,map,[],config,dates[55]);assert.deepEqual(prefix.suggestions,result.suggestions.filter(s=>s.suggestedDate===dates[55]));
 const shorts=methodOneFixture(true);const down=screenMethodOne(shorts.bars,shorts.map,[],shorts.config,shorts.dates.at(-1));assert.equal(down.suggestions.length,15);assert.ok(down.suggestions.every(s=>s.side==='short'));
 assert.equal(screenMethodOne(bars,map,[],{...config,marketFilter:'stack'},dates.at(-1)).suggestions.length,0);
 assert.equal(screenMethodOne(bars,map,['B'],{...config,universe:'top50'},dates.at(-1)).suggestions.length,5);
 assert.equal(screenMethodOne(bars,map,[],{...config,repeats:'first'},dates.at(-1)).suggestions.length,0);
 const first=screenMethodOne(bars,map,[],{...config,repeats:'first',startDate:dates[0]},dates.at(-1));assert.equal(first.suggestions.length,3);assert.ok(first.suggestions.every(s=>s.consecutiveDays===1));
});
test('Method 1 missing sessions break repeats; pullback is a new closing cross and breakout excludes today',()=>{
 const {screenMethodOne}=require(path.join(app,'app/dashboard/sector-rotation/method-one.ts'));
 const {dates,bars,config,map}=methodOneFixture();
 const missing=bars.filter(b=>!(b.symbol==='A'&&b.trade_date===dates[55]));
 const result=screenMethodOne(missing,map,[],config,dates.at(-1));assert.equal(result.suggestions.find(s=>s.symbol==='A'&&s.suggestedDate===dates[59]).consecutiveDays,1);
 const huge=bars.map(b=>b.symbol==='A'&&b.trade_date===dates[55]?{...b,high:999999}:b);
 assert.ok(screenMethodOne(huge,map,[],config,dates[55]).suggestions.some(s=>s.symbol==='A'));
 const reclaim=bars.map(b=>{if(b.symbol!=='A')return b;const value=b.trade_date===dates[55]?100:b.trade_date===dates[56]?1000:b.trade_date===dates[57]?1005:b.close;return {...b,close:value,high:value+1,low:value-1};});
 const signals=screenMethodOne(reclaim,map,[],{...config,setups:'pullback'},dates[57]).suggestions.filter(s=>s.symbol==='A');assert.deepEqual(signals.map(s=>s.suggestedDate),[dates[56]]);assert.equal(signals[0].consecutiveDays,1);
 assert.throws(()=>screenMethodOne([...bars,bars[0]],map,[],config,dates.at(-1)),/Duplicate/);
});
test('Method 1 configuration validates bounds and changes identity; repeat metadata survives entry comparisons',()=>{
 const {validateMethodOne,methodOneKey,METHOD_ONE_DEFAULTS}=require(path.join(app,'app/dashboard/sector-rotation/method-one.ts'));
 assert.deepEqual(validateMethodOne(METHOD_ONE_DEFAULTS),METHOD_ONE_DEFAULTS);
 for(const update of [{topN:0},{rankPeriod:261},{fastEma:50},{leadership:'rrg'},{startDate:'2026-02-30'},{unexpected:1}])assert.throws(()=>validateMethodOne({...METHOD_ONE_DEFAULTS,...update}));
 assert.notEqual(methodOneKey(METHOD_ONE_DEFAULTS),methodOneKey({...METHOD_ONE_DEFAULTS,topN:2}));
 const {trackSwingTrades}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));
 for(const basis of ['signal_close','next_open']){const row=trackSwingTrades([{...swingSuggestion,methodId:1,consecutiveDays:3,setup:'breakout',calculated:true}],swingBars,'2026-10-26',basis)[0];assert.equal(row.consecutiveDays,3);assert.equal(row.setup,'breakout');}
});

test('Method 1 server action rejects unauthenticated and non-allowlisted requests before price reads',async()=>{
 const Module=require('node:module'),original=Module._load;let signedIn=false,allowed=false,reads=0,created=0;
 const client={auth:{getClaims:async()=>({data:{claims:signedIn?{claims:{sub:'fixture'}}:null},error:null})},rpc:async()=>({data:allowed,error:null}),from(){reads++;throw new Error('Price reads not expected');}};
 Module._load=function(request,parent,isMain){if(request==='../../../lib/supabase/server')return {createClient:async()=>{created++;return client;}};return original.call(this,request,parent,isMain);};
 let action;try{action=require(path.join(app,'app/dashboard/sector-rotation/method-one-action.ts')).runMethodOne;}finally{Module._load=original;}
 const {METHOD_ONE_DEFAULTS}=require(path.join(app,'app/dashboard/sector-rotation/method-one.ts'));
 await assert.rejects(action({}),/settings/);assert.equal(created,0);
 await assert.rejects(action(METHOD_ONE_DEFAULTS),/Sign in/);signedIn=true;
 await assert.rejects(action(METHOD_ONE_DEFAULTS),/access unavailable/);assert.equal(reads,0);
});

test('Method 1 server action reads the complete stock and sector views and returns a global calculation',async()=>{
 const Module=require('node:module'),original=Module._load,{dates,bars,config}=methodOneFixture();
 const names={A:'NVDA',B:'AMD',C:'MSFT',D:'QCOM'};
 const renamed=bars.filter(b=>b.symbol!=='UNKNOWN').map(b=>({...b,symbol:names[b.symbol]??b.symbol}));
 const views=[];let fail=false;
 const client={auth:{getClaims:async()=>({data:{claims:{claims:{sub:'fixture'}}},error:null})},rpc:async()=>({data:true,error:null}),from(view){views.push(view);return {select(){return this;},lte(){return this;},order(){return this;},async range(){return fail?{error:{message:'fixture error'},data:null}:{error:null,data:renamed.filter(b=>view==='v_stock_daily_latest'?b.symbol!=='XLK':b.symbol==='XLK'||b.symbol==='SPY')};}};}};
 Module._load=function(request,parent,isMain){if(request==='../../../lib/supabase/server')return {createClient:async()=>client};return original.call(this,request,parent,isMain);};
 let action;try{const file=path.join(app,'app/dashboard/sector-rotation/method-one-action.ts');delete require.cache[require.resolve(file)];action=require(file).runMethodOne;}finally{Module._load=original;}
 const result=await action(config);assert.equal(result.stockCount,4);assert.deepEqual(result.unmapped,[]);assert.deepEqual(new Set(views),new Set(['v_stock_daily_latest','v_sector_daily_latest']));assert.ok(result.suggestions.some(s=>s.symbol==='NVDA'&&s.sectorRank===1));
 fail=true;await assert.rejects(action(config),/could not be loaded/);
});

test('Method 1 tie ranking is deterministic, ETF-only scope excludes stocks and dual setups share stock slots',()=>{
 const {screenMethodOne}=require(path.join(app,'app/dashboard/sector-rotation/method-one.ts'));
 const {dates,bars,config,map}=methodOneFixture();
 const a=new Map(bars.filter(b=>b.symbol==='A').map(b=>[b.trade_date,b]));
 const equal=bars.map(b=>map[b.symbol]?{...a.get(b.trade_date),symbol:b.symbol}:b);
 const tied=screenMethodOne(equal,map,[],{...config,ranking:'mansfield'},dates.at(-1));
 assert.deepEqual(tied.suggestions.filter(s=>s.suggestedDate===dates.at(-1)).map(s=>[s.symbol,s.sectorRank]),[['A',1],['B',2],['C',3]]);
 const etfs=screenMethodOne(bars,map,[],{...config,instruments:'etfs'},dates.at(-1));assert.equal(etfs.stockCount,0);assert.deepEqual(etfs.unmapped,[]);assert.equal(etfs.suggestions.length,5);assert.ok(etfs.suggestions.every(s=>s.symbol==='XLK'));
 const dual=bars.map(b=>{if(b.symbol!=='A')return b;const close=b.trade_date===dates[55]?100:b.trade_date===dates[56]?1000:b.close;return {...b,close,high:close+.01,low:close-.01};});
 const day=screenMethodOne(dual,map,[],{...config,setups:'both'},dates[56]).suggestions.filter(s=>s.suggestedDate===dates[56]);
 assert.deepEqual(day.filter(s=>s.symbol==='A').map(s=>s.setup).sort(),['breakout','pullback']);assert.equal(new Set(day.map(s=>s.symbol)).size,3);
});

test('method filters compose with direction and preserve separate active/archive signals',()=>{
 const {filterSwingMethods}=require(path.join(app,'app/dashboard/sector-rotation/swing-statistics.ts'));
 const rows=[{id:'a',methodId:1,side:'long',status:'active'},{id:'b',methodId:2,side:'long',status:'archive'},{id:'c',methodId:1,side:'short',status:'archive'},{id:'d',methodId:2,side:'short',status:'active'}];
 assert.deepEqual(filterSwingMethods(rows,1).map(r=>r.id),['a','c']);
 assert.deepEqual(filterSwingMethods(rows,2).map(r=>r.id),['b','d']);
 assert.deepEqual(filterSwingMethods(rows,'both'),rows);
 assert.deepEqual(filterSwingMethods(rows,2).filter(r=>r.side==='long').map(r=>r.id),['b']);
 const Swing=require(path.join(app,'app/dashboard/sector-rotation/SwingTrades.tsx')).default;
 const html=renderToStaticMarkup(React.createElement(Swing,{bars:[],groups:[],asOfDate:'2026-10-26'}));
 assert.match(html,/aria-label="Method filter"><button[^>]*aria-pressed="false">Method 1<\/button><button[^>]*aria-pressed="false">Method 2<\/button><button[^>]*aria-pressed="false">Method 3<\/button><button[^>]*aria-pressed="true">All methods<\/button>/);
});
test('method statistics isolate both methods, pool individual signals and render empty populations',()=>{
 const {swingStatisticsByMethod}=require(path.join(app,'app/dashboard/sector-rotation/swing-statistics.ts'));
 const base={methodId:1,side:'long',missingOHLC:0,mfa:4,mfaPercent:4,mae:2,maePercent:2,percentChange:10};
 const [one,two,three,both]=swingStatisticsByMethod([base,{...base,percentChange:20},{...base,methodId:2,side:'short',percentChange:-6,mfa:10}]);
 assert.deepEqual([one.method,two.method,three.method,both.method],[1,2,3,'both']);
 assert.equal(one.groups[2].count,2);assert.equal(one.groups[2].change.value,15);
 assert.equal(two.groups[2].count,1);assert.equal(two.groups[2].change.value,-6);
 assert.equal(both.groups[2].count,3);assert.equal(both.groups[2].change.value,8);assert.equal(both.groups[2].mfe.value,6);
 assert.equal(two.groups[0].change.value,null);assert.equal(one.groups[1].count,0);
 const Stats=require(path.join(app,'app/dashboard/sector-rotation/SwingStats.tsx')).default;
 for(const entryBasis of ['signal_close','next_open']){
  const html=renderToStaticMarkup(React.createElement(Stats,{rows:[],entryBasis}));
  assert.match(html,/<h4>Method 1<\/h4>/);assert.match(html,/<h4>Method 2<\/h4>/);assert.match(html,/<h4>All methods<\/h4>/);
  assert.equal((html.match(/>Longs<\/th>/g)||[]).length,4);assert.match(html,/Independent of suggestion filters/);
  assert.match(html,entryBasis==='next_open'?/Next session open/:/Signal close/);
 }
});

test('calendar display opens current week, Monday includes Friday, and weekends retain the week',()=>{
 const {weekDisplayDates}=require(path.join(app,'app/dashboard/sector-rotation/week-display.ts'));
 assert.deepEqual(weekDisplayDates('2026-10-26'),['2026-10-23','2026-10-26']);
 assert.deepEqual(weekDisplayDates('2026-10-27'),['2026-10-26','2026-10-27']);
 const full=['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30'];
 for(const day of ['2026-10-30','2026-10-31','2026-11-01'])assert.deepEqual(weekDisplayDates(day),full);
 assert.deepEqual(weekDisplayDates('2027-01-04'),['2027-01-01','2027-01-04']);
 assert.throws(()=>weekDisplayDates('2026-02-30'),/Invalid/);
});
test('Event Log opens calendar dates without substituting unavailable days',()=>{
 const EventLog=require(path.join(app,'app/dashboard/sector-rotation/EventLog.tsx')).default;
 const sessions=eventFixture(Array(65).fill(-1)).map((day,i)=>({...day,date:new Date(Date.UTC(2026,7,25+i)).toISOString().slice(0,10)}));
 const render=(asOfDate,visibleSessions=sessions.slice(-8))=>renderToStaticMarkup(React.createElement(EventLog,{asOfDate,sessions,visibleSessions,groups:eventGroup,metric:'daily',line:'ema50',onSelect:()=>{}}));
 const opened=html=>[...html.matchAll(/data-event-date="([^"]+)"[\s\S]*?aria-expanded="(true|false)"/g)].filter(m=>m[2]==='true').map(m=>m[1]);
 assert.deepEqual(opened(render('2026-10-26')),['2026-10-26','2026-10-23']);
 assert.deepEqual(opened(render('2026-10-27')),['2026-10-27','2026-10-26']);
 assert.deepEqual(opened(render('2026-10-28')),['2026-10-28','2026-10-27','2026-10-26']);
 assert.deepEqual(opened(render('2026-11-03')),[]);
 assert.match(render('2026-11-03'),/No current-week sessions/);
 assert.match(render('2026-10-28'),/Older Event Log days \(5\)/);
 assert.equal((render('2026-10-28').match(/data-event-date=/g)||[]).length,8);
 assert.doesNotMatch(render('2026-10-28',[]),/Older Event Log days/);
});
test('active reasoning shows today only and keeps prior reasoning in a closed disclosure',()=>{
 const Swing=require(path.join(app,'app/dashboard/sector-rotation/SwingTrades.tsx')).default;
 const props={bars:swingBars,groups:[{symbol:'X',name:'Fixture',short:'Fixture'}],asOfDate:'2026-10-26'};
 const suggestions=[{...swingSuggestion,id:'today',suggestedDate:'2026-10-26',reason:'TODAY REASON'},{...swingSuggestion,id:'earlier',suggestedDate:'2026-10-23',reason:'EARLIER REASON'}];
 const html=renderToStaticMarkup(React.createElement(Swing,{...props,suggestions}));
 const reasoning=html.slice(html.indexOf('aria-label="Active suggestion reasoning"'),html.indexOf('<caption>Active suggestions'));
 const disclosure=reasoning.indexOf('<details');
 assert.ok(reasoning.indexOf('TODAY REASON')<disclosure);assert.ok(reasoning.indexOf('EARLIER REASON')>disclosure);
 assert.match(reasoning,/<details class="eventRules"><summary>Earlier active suggestion reasoning \(1\)<\/summary>/);
 assert.equal((html.match(/TODAY REASON/g)||[]).length,1);assert.equal((html.match(/EARLIER REASON/g)||[]).length,1);
 const none=renderToStaticMarkup(React.createElement(Swing,{...props,suggestions:suggestions.slice(1)}));
 assert.match(none,/No suggestions dated today match these filters/);assert.match(none,/Earlier active suggestion reasoning \(1\)/);
 const current=renderToStaticMarkup(React.createElement(Swing,{...props,suggestions:suggestions.slice(0,1)}));assert.doesNotMatch(current,/Earlier active suggestion reasoning/);
});

function methodThreeFixture(){
 const dates=[];let date=new Date('2026-09-15T00:00:00Z');while(dates.length<24){if(date.getUTCDay()!==0&&date.getUTCDay()!==6)dates.push(date.toISOString().slice(0,10));date.setUTCDate(date.getUTCDate()+1);}
 const closes=[...Array(20).fill(100),105,110,90,91],volumes=[...Array(20).fill(100),200,300,400,100];
 const bars=dates.flatMap((trade_date,i)=>['X','SPY'].map(symbol=>({symbol,trade_date,close:symbol==='SPY'?100:closes[i],open:150,high:160,low:80,volume:symbol==='SPY'?100:volumes[i]})));
 return {dates,bars,groups:[{symbol:'X',name:'Fixture',short:'Fixture'}]};
}
test('Method 3 requires above-average volume and aligned daily/SPY-relative signs for both directions',()=>{
 const {screenMethodThree}=require(path.join(app,'app/dashboard/sector-rotation/method-three.ts'));
 const {dates,bars,groups}=methodThreeFixture();const signals=screenMethodThree(bars,groups,20,dates.at(-1),'2026-01-01');
 assert.deepEqual(signals.map(s=>[s.suggestedDate,s.side,s.consecutiveDays]),[[dates[22],'short',1],[dates[21],'long',2],[dates[20],'long',1]]);
 assert.ok(signals.every(s=>s.methodId===3&&s.origin==='retrospective'&&s.calculated));
 assert.match(signals.find(s=>s.suggestedDate===dates[20]).reason,/20 sessions average 105/); // (19*100+200)/20
 assert.match(signals[1].reason,/Repeat: 2 consecutive sessions/);
 // Open is deliberately above every close: Long is defined close-to-close, not by candle body.
 assert.equal(signals.find(s=>s.side==='long').entryPrice,110);
 // Zero relative return, mismatched signs, and flat daily close must not qualify.
 for(const spyClose of [105,106]){const changed=bars.map(b=>b.symbol==='SPY'&&b.trade_date===dates[20]?{...b,close:spyClose}:b);assert.ok(!screenMethodThree(changed,groups,20,dates[20]).some(s=>s.suggestedDate===dates[20]));}
 const flat=bars.map(b=>b.symbol==='X'&&b.trade_date===dates[20]?{...b,close:100}:b);assert.equal(screenMethodThree(flat,groups,20,dates[20]).length,0);
 const low=bars.map(b=>b.symbol==='X'?{...b,volume:100}:b);assert.equal(screenMethodThree(low,groups,20,dates.at(-1)).length,0);
});
test('Method 3 uses Sessions history, excludes missing/future data and baskets, and preserves repeats before start',()=>{
 const {screenMethodThree}=require(path.join(app,'app/dashboard/sector-rotation/method-three.ts'));
 const {dates,bars,groups}=methodThreeFixture();
 assert.equal(screenMethodThree(bars,groups,60,dates.at(-1)).length,0);assert.equal(screenMethodThree(bars,groups,120,dates.at(-1)).length,0);
 assert.equal(screenMethodThree(bars,groups,'all',dates.at(-1)).length,3);
 const full=screenMethodThree(bars,groups,20,dates.at(-1));const prefix=screenMethodThree(bars,groups,20,dates[20]);assert.deepEqual(prefix,full.filter(s=>s.suggestedDate<=dates[20]));
 const range=screenMethodThree(bars,groups,20,dates.at(-1),dates[21]);assert.equal(range.find(s=>s.side==='long').consecutiveDays,2);
 for(const bad of [null,-1,NaN]){const missing=bars.map(b=>b.symbol==='X'&&b.trade_date===dates[19]?{...b,volume:bad}:b);assert.equal(screenMethodThree(missing,groups,20,dates.at(-1)).length,0);}
 const missingClose=bars.filter(b=>!(b.symbol==='X'&&b.trade_date===dates[21]));assert.deepEqual(screenMethodThree(missingClose,groups,'all',dates.at(-1)).map(s=>s.suggestedDate),[dates[20]]);
 assert.equal(screenMethodThree(bars,groups.map(g=>({...g,kind:'basket'})),20,dates.at(-1)).length,0);
 assert.throws(()=>screenMethodThree([...bars,bars[0]],groups,20,dates.at(-1)),/Duplicate/);
});
test('Method 3 participates in filters, independent method statistics, both entry bases and Archive',()=>{
 const {screenMethodThree}=require(path.join(app,'app/dashboard/sector-rotation/method-three.ts'));
 const {filterSwingMethods,swingStatisticsByMethod}=require(path.join(app,'app/dashboard/sector-rotation/swing-statistics.ts'));
 const {trackSwingTrades}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));
 const {dates,bars,groups}=methodThreeFixture();const signals=screenMethodThree(bars,groups,20,dates.at(-1));
 for(const basis of ['signal_close','next_open']){
  const rows=trackSwingTrades(signals,bars,dates.at(-1),basis);assert.equal(filterSwingMethods(rows,3).length,3);assert.equal(filterSwingMethods(rows,1).length,0);
  const stats=swingStatisticsByMethod(rows);assert.equal(stats[2].groups[2].count,3);assert.equal(stats[3].groups[2].count,3);
  assert.ok(trackSwingTrades(signals,bars,'2026-12-31',basis).every(r=>r.status==='archive'&&r.days===16));
 }
 const Swing=require(path.join(app,'app/dashboard/sector-rotation/SwingTrades.tsx')).default;
 const html=renderToStaticMarkup(React.createElement(Swing,{bars,groups,sessionDuration:20,asOfDate:dates.at(-1)}));assert.match(html,/#3 · Volume and SPY-relative confirmation/);assert.match(html,/<h4>Method 3 baseline · &gt;1.0×<\/h4>/);assert.match(html,/Method 3 selected/);assert.match(html,/Method #3: 3 calculated matches/);
});

test('Method 3 rejects opposite relative strength for either direction and accepts zero-volume history',()=>{
 const {screenMethodThree}=require(path.join(app,'app/dashboard/sector-rotation/method-three.ts'));
 const {dates,bars,groups}=methodThreeFixture();
 for(const [close,spy,qualifies] of [[102,103,false],[102,101.99,false],[98,98.01,false],[98,97,false],[98,98,false],[100,99,false],[102,101,true],[98,99,true]]){
  const changed=bars.map(b=>b.trade_date===dates[20]?{...b,close:b.symbol==='SPY'?spy:close}:b);
  assert.equal(screenMethodThree(changed,groups,20,dates[20]).length,qualifies?1:0);
 }
 const zero=bars.map(b=>b.symbol==='X'&&b.trade_date<dates[20]?{...b,volume:0}:b);assert.equal(screenMethodThree(zero,groups,20,dates[20]).length,1);
});

test('Method 3 relative volume choices enforce inclusive tenths and strict baseline/over2 bounds',()=>{
 const {METHOD_THREE_RVOL_OPTIONS,qualifiesRelativeVolume,screenMethodThree}=require(path.join(app,'app/dashboard/sector-rotation/method-three.ts'));
 assert.deepEqual(METHOD_THREE_RVOL_OPTIONS.map(o=>o.value),['baseline','1.1','1.2','1.3','1.4','1.5','1.6','1.7','1.8','1.9','2.0','over2']);
 for(let n=11;n<=20;n++){const setting=(n/10).toFixed(1);assert.equal(qualifiesRelativeVolume(n*10,100,setting),true);assert.equal(qualifiesRelativeVolume(n*10-.01,100,setting),false);}
 assert.equal(qualifiesRelativeVolume(100,100,'baseline'),false);assert.equal(qualifiesRelativeVolume(200,100,'over2'),false);assert.equal(qualifiesRelativeVolume(201,100,'over2'),true);assert.equal(qualifiesRelativeVolume(1,0,'1.1'),false);assert.throws(()=>qualifiesRelativeVolume(200,100,'2.1'));
 const {dates,bars,groups}=methodThreeFixture();const baseline=screenMethodThree(bars,groups,20,dates.at(-1));const selected=screenMethodThree(bars,groups,20,dates.at(-1),undefined,'2.0');assert.ok(selected.length<baseline.length);assert.ok(selected.every(s=>s.methodVersion.endsWith('rvol-2.0')));
 const Stats=require(path.join(app,'app/dashboard/sector-rotation/SwingStats.tsx')).default;
 const {trackSwingTrades}=require(path.join(app,'app/dashboard/sector-rotation/swing-trades.ts'));const props={entryBasis:'signal_close',rows:trackSwingTrades(selected,bars,dates.at(-1)),methodThreeBaseline:trackSwingTrades(baseline,bars,dates.at(-1)),relativeVolume:'≥2.0×'};
 const html=renderToStaticMarkup(React.createElement(Stats,props));assert.match(html,/Method 3 baseline/);assert.match(html,/Method 3 selected · ≥2.0×/);assert.match(html,/All methods/);
});

function sectorWinnerFixture(){
 const {SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));
 const dates=[];let date=new Date('2026-06-01T00:00:00Z');while(dates.length<80){if(date.getUTCDay()!==0&&date.getUTCDay()!==6)dates.push(date.toISOString().slice(0,10));date.setUTCDate(date.getUTCDate()+1);}
 const bars=dates.flatMap((trade_date,i)=>['SPY',...SECTORS.map(g=>g.symbol)].map((symbol,j)=>{const close=symbol==='SPY'?100:100+i*j;return {symbol,trade_date,close,open:close-1,high:close+2,low:close-2,volume:100+i};}));return {dates,bars};
}
test('sector winners cap Top 1/2/3, require green complete comparisons, and use deterministic ties',()=>{
 const {sectorWinnerHistory}=require(path.join(app,'app/dashboard/sector-rotation/sector-winners.ts'));const {dates,bars}=sectorWinnerFixture();
 for(const n of [1,2,3]){const h=sectorWinnerHistory(bars,20,n,dates.at(-1));assert.equal(h.days.at(-1).winners.length,n);assert.equal(h.observations.filter(o=>o.date===dates.at(-1)).length,11);assert.ok(h.days.at(-1).winners.every(o=>o.cell.daily>=.05));}
 const prior=new Map(bars.filter(b=>b.trade_date===dates.at(-2)).map(b=>[b.symbol,b.close]));
 const changed=bars.map(b=>b.trade_date===dates.at(-1)&&b.symbol!=='SPY'?{...b,close:prior.get(b.symbol)*(b.symbol==='XLK'?1.01:.99)}:b);
 assert.deepEqual(sectorWinnerHistory(changed,20,3,dates.at(-1)).days.at(-1).winners.map(o=>o.symbol),['XLK']);
 const tied=bars.map(b=>b.trade_date===dates.at(-1)&&b.symbol!=='SPY'?{...b,close:prior.get(b.symbol)*2}:b);assert.deepEqual(sectorWinnerHistory(tied,20,2,dates.at(-1)).days.at(-1).winners.map(o=>o.symbol),['XLB','XLC']);
 const missing=bars.filter(b=>!(b.symbol==='XLK'&&b.trade_date===dates.at(-1)));const day=sectorWinnerHistory(missing,20,3,dates.at(-1)).days.at(-1);assert.equal(day.complete,false);assert.equal(day.winners.length,0);
 const neutral=bars.map(b=>b.trade_date===dates.at(-1)&&b.symbol!=='SPY'?{...b,close:prior.get(b.symbol)*1.0001}:b);assert.equal(sectorWinnerHistory(neutral,20,3,dates.at(-1)).days.at(-1).winners.length,0);
 assert.throws(()=>sectorWinnerHistory(bars,20,4,dates.at(-1)));
});
test('winner characteristics preserve prior timing, full-history streaks, missing values and future exclusion',()=>{
 const {sectorWinnerHistory,winnerFeatureFrequency,winnerCsv}=require(path.join(app,'app/dashboard/sector-rotation/sector-winners.ts'));const {dates,bars}=sectorWinnerFixture();
 const full=sectorWinnerHistory(bars,20,3,dates.at(-1));const prefix=sectorWinnerHistory(bars,20,3,dates[65]);assert.deepEqual(prefix.days,full.days.slice(0,66));assert.deepEqual(prefix.observations,full.observations.filter(o=>o.date<=dates[65]));
 const o=full.days.at(-1).winners[0];assert.equal(o.priorStreaks.daily.green,78);assert.equal(o.streaks.daily.green,79);assert.ok(o.rvol>o.priorRvol-.01);assert.equal(o.cell.mansfield,null);assert.equal(o.positiveAverage!==null,true);
 const index=bars.find(b=>b.symbol===o.symbol&&b.trade_date===dates.at(-1)),prev=bars.find(b=>b.symbol===o.symbol&&b.trade_date===dates.at(-2));assert.ok(Math.abs(o.gap-(index.open/prev.close-1)*100)<1e-9);
 const oneDay=full.observations.filter(o=>o.date===dates.at(-1));const freq=winnerFeatureFrequency(oneDay);assert.equal(freq.find(f=>f.key==='volume').winners.total,3);assert.equal(freq.find(f=>f.key==='volume').others.total,8);
 const first=full.days[1].winners[0];assert.equal(first.rvol,null);assert.equal(first.ema20,null);assert.equal(first.positiveAverage,null);
 const csv=winnerCsv([o]);assert.match(csv,/daily_prior_green_streak/);assert.match(csv,/opening_gap_pct/);assert.equal(csv.split('\n').length,2);
});
test('Sector Winners renders history and comparator and is confined to the main sector tracker',()=>{
 const Winners=require(path.join(app,'app/dashboard/sector-rotation/SectorWinners.tsx')).default;const {buildSessions,SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));const {dates,bars}=sectorWinnerFixture();
 const sessions=buildSessions(bars,SECTORS);const html=renderToStaticMarkup(React.createElement(Winners,{bars,visibleSessions:sessions.slice(-7),sessionDuration:20,asOfDate:dates.at(-1),onSelect:()=>{}}));
 assert.match(html,/Reverse Engineering Sector Daily Leaders/);assert.match(html,/Top 1/);assert.match(html,/Top 2/);assert.match(html,/Top 3/);assert.match(html,/7 visible sessions \/ 7 leader observations/);assert.match(html,/leaders versus other sectors/);assert.match(html,/Before leading session/);assert.match(html,/Export leader characteristics CSV/);const {weekDisplayDates}=require(path.join(app,'app/dashboard/sector-rotation/week-display.ts'));assert.equal((html.match(/<details open=""/g)||[]).length,sessions.slice(-7).filter(day=>weekDisplayDates(dates.at(-1)).includes(day.date)).length);assert.match(html,/Older daily leader days/);assert.match(html,/Most common leader characteristics/);
 const Tracker=require(path.join(app,'app/dashboard/sector-rotation/Tracker.tsx')).default;const props={bars,groups:SECTORS,updatedAt:null,latestSession:dates.at(-1),runStatus:'COMPLETE',error:null,asOfDate:dates.at(-1)};
 assert.match(renderToStaticMarkup(React.createElement(Tracker,props)),/Reverse Engineering Sector Daily Leaders/);
 for(const flags of [{stocks:true},{tech:true}])assert.doesNotMatch(renderToStaticMarkup(React.createElement(Tracker,{...props,...flags})),/Reverse Engineering Sector Daily Leaders/);
});

test('common winner highlights rank observed counts, summarize matching values and preserve missing denominators',()=>{
 const {sectorWinnerHistory,commonWinnerCharacteristics,WINNER_FEATURES}=require(path.join(app,'app/dashboard/sector-rotation/sector-winners.ts'));const {dates,bars}=sectorWinnerFixture();const base=sectorWinnerHistory(bars,20,1,dates.at(-1)).observations[0];
 const rows=[0,1,2,3].map(i=>({...base,selected:true,weekday:i<2?'Monday':'Tuesday',priorRvol:[1.2,1.4,1.8,null][i],features:{...Object.fromEntries(WINNER_FEATURES.map(f=>[f.key,false])),priorVolume:i<3?true:null,priorDaily:i===0?true:null,volume:i<2}}));
 const result=commonWinnerCharacteristics(rows,1);assert.equal(result.groups[0].items.length,1);const top=result.groups[0].items[0];assert.equal(top.key,'priorVolume');assert.equal(top.typical,'1.40×');assert.equal(top.winners.yes,3);assert.equal(top.winners.total,3);assert.equal(top.coverage,75);assert.equal(top.others.percent,null);
 assert.deepEqual(result.weekdays.map(w=>[w.day,w.count]),[['Monday',2],['Tuesday',2]]);assert.equal(commonWinnerCharacteristics([]).groups[0].items.length,0);assert.equal(commonWinnerCharacteristics([]).weekdays.length,0);
 const nonwinner={...rows[0],selected:false,priorRvol:99};assert.equal(commonWinnerCharacteristics([...rows,nonwinner],1).groups[0].items[0].typical,'1.40×');
});

test('winner pairs and triples count same-observation conjunctions, missing data and joint medians',()=>{
 const {sectorWinnerHistory,commonWinnerCombinations,WINNER_FEATURES}=require(path.join(app,'app/dashboard/sector-rotation/sector-winners.ts'));const {dates,bars}=sectorWinnerFixture();const base=sectorWinnerHistory(bars,20,1,dates.at(-1)).observations[0];
 const patterns=[[true,true,true],[true,true,false],[true,false,true],[false,true,true],[null,true,true]];
 const rows=patterns.map((flags,i)=>({...base,selected:true,rvol:1.2+i*.2,gap:i+.1,cell:{...base.cell,relative:i+.1},features:{...Object.fromEntries(WINNER_FEATURES.map(f=>[f.key,false])),volume:flags[0],relative:flags[1],gap:flags[2]}}));
 const other={...rows[0],selected:false,rvol:99};const result=commonWinnerCombinations([...rows,other]);assert.equal(result.winnerCount,5);assert.equal(result.pairs.length,3);assert.equal(result.triples.length,1);
 const first=result.pairs[0];assert.deepEqual(first.features.map(f=>f.key),['relative','gap']);assert.deepEqual(first.winners,{yes:3,total:5,percent:60});assert.equal(first.others.percent,100);
 const pair=result.pairs.find(c=>c.features.some(f=>f.key==='volume')&&c.features.some(f=>f.key==='relative'));assert.equal(pair.values.find(v=>v.key==='volume').typical,'1.30×');assert.equal(pair.winners.total,4);
 assert.deepEqual(result.triples[0].winners,{yes:1,total:4,percent:25});assert.equal(result.triples[0].values.find(v=>v.key==='volume').typical,'1.20×');
 assert.equal(commonWinnerCombinations(rows,1).pairs.length,1);assert.deepEqual(commonWinnerCombinations([]),{winnerCount:0,pairs:[],triples:[]});
 for(const c of [...result.pairs,...result.triples])assert.equal(new Set(c.features.map(f=>f.key)).size,c.features.length);
 const Winners=require(path.join(app,'app/dashboard/sector-rotation/SectorWinners.tsx')).default;const {buildSessions,SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));const sessions=buildSessions(bars,SECTORS);const html=renderToStaticMarkup(React.createElement(Winners,{bars,visibleSessions:sessions.slice(-5),sessionDuration:20,asOfDate:dates.at(-1),onSelect:()=>{}}));assert.match(html,/Two-characteristic combinations/);assert.match(html,/Three-characteristic combinations/);assert.match(html,/Seen together in/);
});

test('winner combinations rank before and during independently; any includes mixed timing',()=>{
 const {sectorWinnerHistory,commonWinnerCombinations,WINNER_FEATURES}=require(path.join(app,'app/dashboard/sector-rotation/sector-winners.ts'));const {dates,bars}=sectorWinnerFixture();const base=sectorWinnerHistory(bars,20,1,dates.at(-1)).observations[0];
 const rows=[0,1,2,3].map(i=>({...base,selected:true,features:{...Object.fromEntries(WINNER_FEATURES.map(f=>[f.key,false])),priorVolume:i===0?true:i===1?null:false,priorDaily:i===0,priorRelative:i===0,volume:true,relative:true,gap:true}}));
 const before=commonWinnerCombinations(rows,3,'Before session'),during=commonWinnerCombinations(rows,3,'During session'),any=commonWinnerCombinations(rows,1000,'Any session');
 assert.equal(before.pairs.length,3);assert.equal(before.triples.length,1);assert.equal(before.triples[0].winners.yes,1);assert.equal(before.triples[0].winners.total,3);
 for(const c of [...before.pairs,...before.triples])assert.ok(c.features.every(f=>f.timing==='Before session'));
 for(const c of [...during.pairs,...during.triples]){assert.ok(c.features.every(f=>f.timing==='During session'));assert.equal(c.winners.yes,4);}
 assert.ok([...any.pairs,...any.triples].some(c=>c.timing==='Mixed timing'));assert.deepEqual(commonWinnerCombinations(rows),commonWinnerCombinations(rows,3,'Any session'));
 assert.equal(commonWinnerCombinations(rows,1,'Before session').pairs.length,1);assert.equal(commonWinnerCombinations(rows.slice(2),3,'Before session').pairs.length,0);
 const Winners=require(path.join(app,'app/dashboard/sector-rotation/SectorWinners.tsx')).default;const {buildSessions,SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));const html=renderToStaticMarkup(React.createElement(Winners,{bars,visibleSessions:buildSessions(bars,SECTORS).slice(-5),sessionDuration:20,asOfDate:dates.at(-1),onSelect:()=>{}}));
 for(const timing of ['Before session','During session','Any session'])assert.ok(html.includes(`aria-label="${timing} combinations"`));assert.equal((html.match(/<h5>Two-characteristic combinations<\/h5>/g)||[]).length,3);assert.equal((html.match(/<h5>Three-characteristic combinations<\/h5>/g)||[]).length,3);
});

test('forward sector suggestion retains recorded reasoning beside appended results and explicit pending/error states',()=>{
 const Forecasts=require(path.join(app,'app/dashboard/sector-rotation/SectorForecasts.tsx')).default;
 const plan={id:'fixture',version:'sector-next-v1',source_date:'2026-10-26',recorded_at:'2026-10-27T06:15:00Z',payload:{symbol:'XLK',reason:'RECORDED REASON',pattern:{traits:['Volume >60-session average'],wins:5,observations:30,dates:12},training_sessions:120}};
 const render=props=>renderToStaticMarkup(React.createElement(Forecasts,props));
 assert.match(render({forecasts:[]}),/No forward suggestion recorded yet/);
 assert.match(render({forecasts:[],error:'Fixture unavailable'}),/role="alert"/);
 const pending=render({forecasts:[plan]});assert.match(pending,/RECORDED REASON/);assert.match(pending,/Awaiting the next trading session/);assert.match(pending,/XLK · Long/);
 const completed=render({forecasts:[{...plan,result:{target_date:'2026-10-27',recorded_at:'2026-10-28T06:15:00Z',payload:{symbol:'XLK',rank:2,top1_green:false,open:100,close:102,open_close_pct:2,mfe_pct:3,mae_pct:1,winner:'XLV'}}}]});
 assert.match(completed,/RECORDED REASON/);assert.match(completed,/Results for 2026-10-27/);assert.match(completed,/\+2.00%/);assert.match(completed,/Observed leader: XLV/);
});

test('recorded sector suggestion loader blocks unauthenticated reads and reports service failures',async()=>{
 const Module=require('node:module'),original=Module._load;let signedIn=false,allowed=false,reads=0,fail=false;
 const client={auth:{getClaims:async()=>({data:{claims:signedIn?{sub:'fixture'}:null},error:null})},rpc:async()=>({data:allowed,error:null}),from(table){reads++;return {select(){return this;},order(){return this;},async range(){return fail?{data:null,error:{message:'fixture'}}:{data:[],error:null};}};}};
 Module._load=function(request,parent,isMain){if(request==='server-only')return {};if(request==='../../../lib/supabase/server')return {createClient:async()=>client};return original.call(this,request,parent,isMain);};
 let load;try{load=require(path.join(app,'app/dashboard/sector-rotation/sector-forecast-data.ts')).loadSectorForecasts;}finally{Module._load=original;}
 assert.match((await load()).error,/Sign in/);signedIn=true;assert.match((await load()).error,/access unavailable/);assert.equal(reads,0);allowed=true;assert.deepEqual(await load(),{rows:[],error:null});fail=true;assert.match((await load()).error,/could not be loaded/);
});

test('daily Top3 shows all dates collapsed, older grouped closed, immutable stages and results',()=>{
 const View=require(path.join(app,'app/dashboard/sector-rotation/DailyTop3Predictions.tsx')).default;
 const p={target_date:'2026-10-28',stage:'overnight',symbol:'XLE',recorded_at:'2026-10-28T06:00:00Z',data_as_of:'2026-10-28T05:00:00Z',top3:25,middle:35,bottom3:40,confidence:'Low',reason:'ORIGINAL OVERNIGHT REASON',sources:[{label:'bad URL',url:'javascript:alert(1)'}],methodology:'judgment-v1',availability:'researched'};
 const predictions=[p,{...p,stage:'premarket',recorded_at:'2026-10-28T13:26:00Z',reason:'PREMARKET REASON'}, {...p,target_date:'2026-10-27'},{...p,target_date:'2026-10-26'},{...p,target_date:'2026-10-23'}];
 const render=results=>renderToStaticMarkup(React.createElement(View,{predictions,results,asOfDate:'2026-10-28'}));
 const pending=render([]);assert.equal((pending.match(/<details open="" class="eventDay/g)||[]).length,0);assert.match(pending,/Older daily predictions \(1\)/);assert.match(pending,/2026-10-26 ·/);assert.doesNotMatch(pending,/Yesterday|Earlier day/);assert.match(pending,/Before market open/);assert.match(pending,/ORIGINAL OVERNIGHT REASON/);assert.match(pending,/No forecast recorded for this ETF/);assert.doesNotMatch(pending,/href="javascript:/);
 const result={target_date:'2026-10-28',recorded_at:'2026-10-29T06:30:00Z',payload:{ranks:[{symbol:'XLE',rank:2,daily:-.2,bucket:'Top 3'}],ranking_rule:'Fixture ordinal ranks',price_sha256:'fixture'}};
 const completed=render([result]);assert.match(completed,/<td>#2<\/td><td>-0.20%<\/td><td>Top 3<\/td><td>Yes<\/td>/);assert.match(completed,/ORIGINAL OVERNIGHT REASON/);assert.match(completed,/<td>25%<\/td>/);
 const empty=renderToStaticMarkup(React.createElement(View,{predictions:[],results:[],asOfDate:'2026-10-28'}));assert.match(empty,/2026-10-27 ·/);assert.match(empty,/Historical predictions are not backfilled/);
 assert.match(renderToStaticMarkup(React.createElement(View,{predictions:[],results:[],asOfDate:'2026-10-28',error:'READ FAILED'})),/role="alert">READ FAILED/);
});

test('daily Top3 dates and most likely buckets preserve calendar boundaries and ties',()=>{
 const {priorCalendarDate,mostLikely}=require(path.join(app,'app/dashboard/sector-rotation/top-three-types.ts'));
 assert.equal(priorCalendarDate('2026-11-01'),'2026-10-31');assert.equal(priorCalendarDate('2027-01-01'),'2026-12-31');assert.deepEqual(mostLikely({top3:40,middle:40,bottom3:20}),['Top 3','Middle']);
});

test('daily Top3 loader authorizes before reads and preserves read failures',async()=>{
 const Module=require('node:module'),original=Module._load;let signedIn=false,allowed=false,reads=0,fail=false;
 const client={auth:{getClaims:async()=>({data:{claims:signedIn?{sub:'fixture'}:null},error:null})},rpc:async()=>({data:allowed,error:null}),from(){reads++;return {select(){return this;},order(){return this;},async range(){return fail?{data:null,error:{message:'fixture'}}:{data:[],error:null};}};}};
 Module._load=function(request,parent,isMain){if(request==='server-only')return {};if(request==='../../../lib/supabase/server')return {createClient:async()=>client};return original.call(this,request,parent,isMain);};
 let load;try{load=require(path.join(app,'app/dashboard/sector-rotation/top-three-data.ts')).loadDailyTop3;}finally{Module._load=original;}
 assert.match((await load()).error,/Sign in/);signedIn=true;assert.match((await load()).error,/access unavailable/);assert.equal(reads,0);allowed=true;assert.deepEqual(await load(),{predictions:[],results:[],error:null});fail=true;assert.match((await load()).error,/could not be loaded/);
});

test('symbol reference is first after tabs and before configuration on every secondary tab',()=>{
 const Tracker=require(path.join(app,'app/dashboard/sector-rotation/Tracker.tsx')).default;
 const {SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));
 const {bars,dates}=sectorWinnerFixture();
 const props={bars,updatedAt:null,latestSession:dates.at(-1),runStatus:'COMPLETE',error:null,asOfDate:dates.at(-1),dailyPredictions:React.createElement('p',null,'Forecast fixture')};
 const original=React.useState;
 try{
  for(const tab of ['overview','events','winners','swing','predictions']){
   React.useState=initial=>{const state=original(initial);return initial==='overview'?[tab,state[1]]:state;};
   const html=renderToStaticMarkup(React.createElement(Tracker,props));
   if(tab==='overview'){assert.doesNotMatch(html,/class="symbolReference"/);continue;}
   const tabsEnd=html.indexOf('</div>',html.indexOf('aria-label="Tracker sections"'));
   const referenceStart=html.indexOf('<section class="symbolReference"');
   assert.equal(referenceStart,tabsEnd+6);assert.ok(referenceStart<html.indexOf('aria-label="Shared tracker filters"'));
   assert.equal((html.match(/class="symbolReference"/g)||[]).length,1);
   const reference=html.slice(referenceStart).split('</section>')[0];
   const expected=tab==='predictions'?SECTORS.filter(g=>['XLE','XLV','XLK'].includes(g.symbol)):SECTORS;
   assert.equal((reference.match(/<dt>/g)||[]).length,expected.length);
   for(const group of expected){assert.ok(reference.includes(`<dt>${group.symbol}</dt>`));assert.ok(reference.includes(`<dd>${group.name}</dd>`));}
  }
 }finally{React.useState=original;}
});


test('all-history suggestion counts distinguish pending, no-pick and positive/negative/flat outcomes',()=>{
 const Forecasts=require(path.join(app,'app/dashboard/sector-rotation/SectorForecasts.tsx')).default;
 const base={version:'sector-next-v1',source_date:'2026-10-26',recorded_at:'2026-10-27T06:15:00Z',payload:{symbol:'XLB',reason:'Saved original reasoning'}};
 const forecasts=[{...base,id:'pending'},{...base,id:'no-pick',payload:{reason:'No supported pattern'}},...[2,-1,0,null].map((value,i)=>({...base,id:`done-${i}`,result:{target_date:'2026-10-27',recorded_at:'2026-10-28T06:15:00Z',payload:{rank:i+1,open_close_pct:value}}}))];
 const html=renderToStaticMarkup(React.createElement(Forecasts,{forecasts}));
 assert.match(html,/6 recorded entries · 5 Long picks · 1 no-pick entries · 4 completed picks · 1 pending picks/);
 assert.match(html,/1 positive · 1 negative · 1 unchanged · 1 unavailable/);
 assert.match(html,/Top 3 finishes: 3\/4 ranked results/);
 assert.equal((html.match(/Saved original reasoning/g)||[]).length,5);
 assert.match(html,/Earlier next-session suggestions \(5\)/);
});

test('prediction stages collapse independently and shared context preserves ETF-specific research',()=>{
 const {default:View,sharedResearchPrefix}=require(path.join(app,'app/dashboard/sector-rotation/DailyTop3Predictions.tsx'));
 const common='Forecasts rank all eleven sectors by closing return. '+'Shared verified history and source quality apply to all three ETFs. '.repeat(4);
 const p={target_date:'2026-10-30',symbol:'XLE',recorded_at:'2026-10-30T14:00:00Z',data_as_of:'2026-10-30T13:59:00Z',top3:45,middle:30,bottom3:25,confidence:'Low',sources:[],methodology:'judgment-v1',availability:'baseline_only'};
 const rows=['XLE','XLV','XLK'].map(symbol=>({...p,stage:'open30',symbol,reason:common+symbol+' specific catalyst. Unverified quotes did not change the baseline.'}));
 assert.equal(sharedResearchPrefix(rows),common.trim());
 assert.equal(sharedResearchPrefix([rows[0]]),'');
 assert.equal(sharedResearchPrefix([{...rows[0],reason:'Short shared. XLE'}, {...rows[1],reason:'Short shared. XLV'}]),'');
 assert.equal(sharedResearchPrefix(rows.map(r=>({...r,reason:common}))),common);
 const predictions=[...rows,...rows.map(r=>({...r,stage:'premarket'})),...rows.map(r=>({...r,stage:'overnight'}))];
 const html=renderToStaticMarkup(React.createElement(View,{predictions,results:[],asOfDate:'2026-10-30'}));
 assert.equal((html.match(/class="predictionStageTitle"/g)||[]).length,3);
 assert.equal((html.match(/<details class="predictionStage" open=""/g)||[]).length,0);
 assert.match(html,/Current Prediction · 30 minutes after open/);
 assert.match(html,/<h3>Before market open<\/h3>/);assert.match(html,/<h3>Overnight outlook<\/h3>/);
 assert.equal((html.match(/Shared Research Context · All ETFs In This Forecast/g)||[]).length,3);
 for(const r of rows){assert.ok(html.includes(r.reason));assert.match(html,new RegExp('<p class="predictionReason">'+r.symbol+' specific catalyst'));}
 assert.doesNotMatch(html,/Earlier forecasts for this day|Yesterday|Earlier day/);
 const different=rows.map((r,i)=>({...r,recorded_at:`2026-10-30T14:0${i}:00Z`}));
 const divergent=renderToStaticMarkup(React.createElement(View,{predictions:different,results:[],asOfDate:'2026-10-30'}));
 assert.equal((divergent.match(/class="predictionMeta">Recorded/g)||[]).length,3);
});

test('Event Log begins each day with the matching Leadership Log and full-history prior session',()=>{
 const EventLog=require(path.join(app,'app/dashboard/sector-rotation/EventLog.tsx')).default;
 const {buildSessions,leadershipNote}=require(path.join(app,'app/dashboard/sector-rotation/model.ts'));
 const groups=[{symbol:'A',name:'Alpha',short:'Alpha'},{symbol:'B',name:'Beta',short:'Beta'}];
 const dates=['2026-10-26','2026-10-27','2026-10-28'];
 const closes={SPY:[100,101,102],A:[100,103,104],B:[100,101,105]};
 const bars=dates.flatMap((trade_date,i)=>Object.entries(closes).map(([symbol,prices])=>({symbol,trade_date,close:prices[i]})));
 const sessions=buildSessions(bars,groups);
 const props={sessions,visibleSessions:sessions.slice(-1),groups,metric:'daily',line:'none',asOfDate:'2026-10-28',onSelect:()=>{}};
 const html=renderToStaticMarkup(React.createElement(EventLog,props));
 assert.match(html,/Beta took the daily lead from Alpha\./);
 assert.ok(html.includes(leadershipNote(sessions[2],sessions[1],groups)));
 assert.match(html,/SPY \+0.99%/);assert.match(html,/3.96%/);assert.match(html,/Laggard <button[^>]*>A<\/button>/);
 assert.ok(html.indexOf('<strong>Leadership Log:</strong>')<html.indexOf('<h4>EMA events</h4>'));
 assert.doesNotMatch(renderToStaticMarkup(React.createElement(EventLog,{...props,singleStock:true})),/<strong>Leadership Log:<\/strong>/);
 const incomplete=sessions.map((s,i)=>i===2?{...s,complete:false,leader:null,laggard:null}:s);
 assert.match(renderToStaticMarkup(React.createElement(EventLog,{...props,sessions:incomplete})),/Incomplete comparison/);
});
