import {test} from 'node:test';
import assert from 'node:assert/strict';
import {normalizeStockSymbol,TOP_50_STOCKS} from '../../apps/trading-research-web/app/dashboard/sector-rotation/stocks/symbols.ts';
test('lookup normalizes dollar-prefixed symbols and rejects unsafe or ambiguous inputs',()=>{
 assert.equal(normalizeStockSymbol(' $msft '),'MSFT');assert.equal(normalizeStockSymbol('brk.b'),'BRK.B');
 for(const input of ['', '$$AAPL','MSFT,TSLA','../TSLA','AAPL&x=1','A'.repeat(11)])assert.equal(normalizeStockSymbol(input),null);
});
test('top 50 snapshot covers 50 companies with 51 valid share classes',()=>{
 assert.equal(TOP_50_STOCKS.length,51);assert.equal(new Set(TOP_50_STOCKS.map(g=>g.symbol)).size,51);
 for(const g of TOP_50_STOCKS)assert.equal(normalizeStockSymbol(g.symbol),g.symbol);
 for(const s of ['GOOG','GOOGL','BRK.B','SNDK','MCD'])assert.ok(TOP_50_STOCKS.some(g=>g.symbol===s));
 assert.ok(!TOP_50_STOCKS.some(g=>['AGPXX','USDPDV','SPY'].includes(g.symbol)));
});
