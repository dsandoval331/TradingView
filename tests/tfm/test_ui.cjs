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
