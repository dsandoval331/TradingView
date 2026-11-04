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
const rows=[fixture('LIVE_CURRENT','PROSPECTIVE','2026-11-02'),fixture('LIVE_OLD','PROSPECTIVE','2026-10-26'),fixture('HISTORICAL_SENTINEL','HISTORICAL','2026-11-02')];
for(const scopeLabel of ['Sector ETFs','Tech & AI','S&P 500 Top 50']){
 const html=renderToStaticMarkup(React.createElement(Dashboard,{rows,scans:[],asOf:'2026-11-03',error:null,scopeLabel}));
 assert.ok(html.includes('LIVE_CURRENT'));
 assert.ok(!html.includes('HISTORICAL_SENTINEL'),'Historical instances must never be rendered');
 assert.ok(!html.includes('LIVE_OLD'),'Previous-month instance rows stay unmounted until archive is expanded');
 assert.match(html,/<details[^>]*><summary>Previous months/);
 assert.ok(html.indexOf('Live results')<html.indexOf('Historical results'));
 assert.ok(!html.includes('Current candidates'));
}
console.log('TFM SSR: three scopes, current-month live rows, collapsed prior months, aggregate-only history PASS');
