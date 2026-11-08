// SSR contract check with synthetic fixtures only; no database or live claims.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const app=path.resolve(__dirname,'../../apps/trading-research-web');
const ts=require(path.join(app,'node_modules/typescript'));
require.extensions['.tsx']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,f);
require.extensions['.ts']=require.extensions['.tsx'];
require.extensions['.css']=(m)=>m.exports={__esModule:true,default:new Proxy({},{get:(_,p)=>p})};
const React=require(path.join(app,'node_modules/react'));
const {renderToStaticMarkup}=require(path.join(app,'node_modules/react-dom/server'));
const Dashboard=require(path.join(app,'app/dashboard/sector-rotation/tfm/TFMDashboard.tsx')).default;
const fixture=(symbol,origin,target)=>({setup_key:symbol,symbol,origin,friday:'2026-10-30',target_date:target,cohort:'MONDAY',qualifies:true,recorded_at:'2026-10-30T22:00:00Z',payload:{asset_class:'STOCK',thursday_high:112,friday_high:110,friday_low:95,friday_close:100,market_condition:'UNKNOWN',reference_bars:[]},outcome:null});
const rows=[fixture('LIVE_CURRENT','PROSPECTIVE','2026-11-02'),{...fixture('LIVE_OLD','PROSPECTIVE','2026-10-26'),friday:'2026-10-23'},fixture('RECENT_HISTORICAL','HISTORICAL','2026-11-02'),{...fixture('OLDER_BACKTEST','HISTORICAL','2026-10-26'),friday:'2026-10-23'}];
const outcome=hit=>({hit,gap_through:false,mfe_pct:hit?10:4,mae_pct:10,close_return_pct:0,target_bar:{symbol:'FIXTURE',trade_date:'2026-11-02',open:100,high:110,low:hit?90:96,close:100,run_id:'fixture',source_view:'fixture',response_sha256:'a'.repeat(64)}});
rows[0].outcome=outcome(true);rows[2].outcome=outcome(false);
for(const scopeLabel of ['Sector ETFs','Tech & AI','S&P 500 Top 50']){
 const html=renderToStaticMarkup(React.createElement(Dashboard,{rows,scans:[],asOf:'2026-11-03',error:null,scopeLabel}));
 assert.ok(html.includes('LIVE_CURRENT'));
 const summary=html.slice(0,html.indexOf('Current month')).replace(/<[^>]*>/g,'');
 assert.ok(summary.includes('1 hits / 2 completed qualifying instances'),'Live totals must include the completed imported instance');
 assert.ok(html.includes('RECENT_HISTORICAL'),'Requested November 2 historical instances must be visible');
 assert.ok(!html.includes('OLDER_BACKTEST'),'Older backtest occurrences stay aggregate-only');
 assert.ok(!html.includes('LIVE_OLD'),'Previous-month instance rows stay unmounted until archive is expanded');
 assert.match(html,/<details[^>]*><summary>Previous months/);
 assert.ok(html.indexOf('Live results')<html.indexOf('Historical results'));
 assert.ok(!html.includes('Current candidates'));
 assert.ok(!html.includes('Symbol search')&&!html.includes('<select'),'Symbol search and target-session controls must remain absent');
 assert.ok(html.includes('<span>Combined Success</span><strong>1</strong>'));
 assert.ok(html.includes('<span>Combined Success Rate</span><strong>50.00%</strong>'));
 assert.ok(html.includes('Alternate success')&&html.includes('Prospective alternate success'));
}
console.log('TFM SSR: three scopes, current-month live rows, collapsed prior months, aggregate-only history PASS');

const Ranking=require(path.join(app,'app/dashboard/sector-rotation/tfm/RankingPanel.tsx')).default;
const candidate={setup_key:'frozen',symbol:'FROZEN_RANK',rank:1,score:86,close_points:56,red_points:20,below_points:10,distance_pct:0.61,lower_third:true,status:'RANKED',reference_bars:[]};
const snapshot={snapshot_id:'fixture',model_version:'tfm-rank-v1',scope:'tech',monday:'2026-11-09',target_date:'2026-11-09',frozen_at:'2026-11-07T13:15:00Z',payload:{n:1,k:1,complete:true,candidates:[candidate],model_sha256:'model',source_sha256:'source',universe_sha256:'universe'},review:{n:1,k:1,complete:true,top_rate:100,top_hit_rate:0,pool_rate:100,lift:0,ndcg:100,median_mfe:0.5,median_mae:0.25,gaps:0,instances:[{...candidate,classification:'ALTERNATE',outcome:{hit:false,mfe_pct:0.5,mae_pct:0.25}}],groups:{top:{n:1,wins:1,rate:100}}}};
const html=renderToStaticMarkup(React.createElement(Ranking,{game:{snapshots:[snapshot],xp:[{monday:'2026-11-09',kind:'freeze',points:10}],reflections:[],error:null}}));
assert.ok(html.includes('FROZEN_RANK')&&html.includes('86.00 / 100'));
assert.ok(html.includes('Hidden until revealed')&&!html.includes('ALTERNATE</td>'));
assert.ok(html.includes('10 / 30 XP')&&html.includes('First Frozen Week'));
assert.ok(html.includes('disabled=')&&html.includes('Save reflection'));
const empty=renderToStaticMarkup(React.createElement(Ranking,{game:{snapshots:[],xp:[],reflections:[],error:null}}));
assert.ok(empty.includes('Rankings not available yet')&&empty.includes('0 / 30 XP'));
console.log('TFM rankings SSR: frozen reasons, separate XP, blind review, locked reflection, truthful empty state PASS');
for(const scopeLabel of ['Sector ETFs','Tech & AI','S&P 500 Top 50']){
 const html=renderToStaticMarkup(React.createElement(Dashboard,{rows,scans:[],asOf:'2026-11-03',error:null,scopeLabel}));
 assert.ok(html.includes('All qualifying · mean MFE / MAE'));
 assert.ok(html.includes('MFE and MAE by qualifying outcome'));
 for(const label of ['Pattern hits','Did not hit Friday low','Alternate successes','All qualifying instances'])assert.ok(html.includes(label));
 assert.ok(html.includes('these groups overlap'));
 const live=html.slice(html.indexOf('Live results'),html.indexOf('Historical results'));
 assert.ok(live.includes('<th scope="row">Pattern hits</th><td>1</td><td>10.00%</td><td>10.00%</td>'));
 assert.ok(live.includes('<th scope="row">Did not hit Friday low</th><td>1</td><td>4.00%</td><td>10.00%</td>'));
 assert.ok(live.includes('<th scope="row">Alternate successes</th><td>0</td><td>—</td><td>—</td>'));
 assert.ok(live.includes('<th scope="row">All qualifying instances</th><td>2</td><td>7.00%</td><td>10.00%</td>'));
}
console.log('TFM excursion table SSR: three scopes, exact group counts/means, overlapping-group explanation and empty state PASS');

const League=require(path.join(app,'app/dashboard/sector-rotation/tfm/LeaguePanel.tsx')).default;
const leagueHtml=renderToStaticMarkup(React.createElement(League,{league:{error:false,matches:[
 {champion_id:'first',monday:'2026-11-16',target_date:'2026-11-16',picks:[
  {symbol:'AAA',rank:1,challenger_rank:2,room_to_stop:1},
  {symbol:'BBB',rank:2,challenger_rank:1,room_to_stop:2}],
  result:{k:2,missing:0,ambiguous:1,champion_lo:-.25,champion_hi:.75,
   challenger_lo:-.25,challenger_hi:.75,champion_hits:1,challenger_hits:1,winner:'TIE'}},
 {champion_id:'holiday',monday:'2027-01-18',target_date:'2027-01-19',picks:[],result:null}
]}}));
assert.ok(leagueHtml.includes('Tie · half a point each'));
assert.ok(leagueHtml.includes('-0.25% to 0.75%'));
assert.ok(leagueHtml.includes('Holiday Tuesday standings'));
assert.ok(leagueHtml.includes('Champion picks: AAA, BBB'));
console.log('TFM league SSR: paired picks, tied points, ambiguity bounds and holiday cohort PASS');

const pairedRanking=renderToStaticMarkup(React.createElement(Ranking,{
 game:{snapshots:[snapshot],xp:[],reflections:[],error:null},
 league:{error:false,matches:[{champion_id:snapshot.snapshot_id,picks:[
  {setup_key:candidate.setup_key,symbol:candidate.symbol,rank:1,challenger_rank:7,room_to_stop:.81}
 ]}]}
}));
assert.match(pairedRanking,/aria-pressed="false">Room to Target<\/button>/);
assert.match(pairedRanking,/<th>Room to Target rank<\/th>/);
assert.match(pairedRanking,/<td>1<\/td><th scope="row">FROZEN_RANK<\/th><td>7<\/td>/);
assert.ok(!pairedRanking.includes('Room to Target frozen rankings'));
console.log('TFM ranking tabs SSR: shared snapshot, alternate rank and single active table PASS');
