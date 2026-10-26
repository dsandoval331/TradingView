import {test} from 'node:test';
import assert from 'node:assert/strict';
import {normalizeStockSymbol,FREQUENT_STOCKS} from '../../apps/trading-research-web/app/dashboard/sector-rotation/stocks/symbols.ts';
test('lookup normalizes dollar-prefixed symbols and rejects unsafe or ambiguous inputs',()=>{
 assert.equal(normalizeStockSymbol(' $msft '),'MSFT');assert.equal(normalizeStockSymbol('brk.b'),'BRK.B');
 for(const input of ['', '$$AAPL','MSFT,TSLA','../TSLA','AAPL&x=1','A'.repeat(11)])assert.equal(normalizeStockSymbol(input),null);
});
test('frequent stocks match the requested starting list in order',()=>{assert.deepEqual(FREQUENT_STOCKS.map(g=>g.symbol),['MSFT','AAPL','NVDA','TSLA','AMD']);});
