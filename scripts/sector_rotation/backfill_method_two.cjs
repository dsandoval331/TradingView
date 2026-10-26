// Offline, explicit one-time input. No credentials, database writes, API calls or scheduling.
const fs=require('node:fs'),path=require('node:path'),{createRequire}=require('node:module');
const app=path.resolve(__dirname,'../../apps/trading-research-web');
const ts=createRequire(path.join(app,'package.json'))('typescript');
require.extensions['.ts']=(module,file)=>module._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,file);
const {backfillMethodTwo,METHOD_TWO_VERSION}=require(path.join(app,'app/dashboard/sector-rotation/method-two.ts'));
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const bars=input.series.flatMap(s=>s.prices.map(([trade_date,close])=>({symbol:s.symbol,trade_date,close,volume:0})));
const symbols=input.series.map(s=>s.symbol).filter(s=>s!=='SPY');
const suggestions=backfillMethodTwo(bars,symbols,input.asOfDate);
process.stdout.write(JSON.stringify({asOfDate:input.asOfDate,methodVersion:METHOD_TWO_VERSION,symbolCount:symbols.length,barCount:bars.length,suggestions},null,2)+'\n');
