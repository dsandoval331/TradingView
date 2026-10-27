// Explicit offline price snapshot in, calculated Method 1 screen out. No network or database writes.
const fs=require('node:fs'),path=require('node:path'),{createRequire}=require('node:module');
const app=path.resolve(__dirname,'../../apps/trading-research-web'),ts=createRequire(path.join(app,'package.json'))('typescript');
require.extensions['.ts']=(module,file)=>module._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true,target:ts.ScriptTarget.ES2022}}).outputText,file);
const {screenMethodOne,METHOD_ONE_DEFAULTS}=require(path.join(app,'app/dashboard/sector-rotation/method-one.ts'));
const {METHOD_ONE_SECTORS}=require(path.join(app,'app/dashboard/sector-rotation/method-one-sectors.ts'));
const {TOP_50_STOCKS}=require(path.join(app,'app/dashboard/sector-rotation/stocks/symbols.ts'));
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const bars=input.series.flatMap(s=>s.prices.map(([trade_date,close,open,high,low,volume])=>({symbol:s.symbol,trade_date,close,open,high,low,volume})));
process.stdout.write(JSON.stringify(screenMethodOne(bars,METHOD_ONE_SECTORS,TOP_50_STOCKS.map(s=>s.symbol),input.settings??METHOD_ONE_DEFAULTS,input.asOfDate),null,2)+'\n');
