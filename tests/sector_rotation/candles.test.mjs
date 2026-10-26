import {test} from 'node:test';
import assert from 'node:assert/strict';
import {candleSeries} from '../../apps/trading-research-web/app/dashboard/sector-rotation/candles.ts';
const sessions=['2025-01-02','2025-01-03','2025-01-06'].map(date=>({date}));
const row=(date)=>({symbol:'XLK',trade_date:date,open:'100',high:'105',low:'99',close:'103',volume:1});
test('candle windows exactly follow supplied sessions, preserving missing slots',()=>{
 const bars=[row('2025-01-02'),row('2025-01-06'),row('2024-12-31')];
 const result=candleSeries(bars,sessions,'XLK');
 assert.equal(result.length,3);assert.equal(result[1],null);assert.equal(result[2].date,'2025-01-06');
 assert.deepEqual(candleSeries(bars,sessions.slice(2),'XLK'),[result[2]]);
 assert.equal(candleSeries(bars,sessions,'IGV').every(c=>c===null),true);
});
test('invalid OHLC is withheld and never synthesized from closes',()=>{
 for(const change of [{open:null},{high:102},{low:101},{high:Infinity},{open:0},{low:NaN}])assert.equal(candleSeries([{...row('2025-01-02'),...change}],sessions,'XLK')[0],null);
 assert.throws(()=>candleSeries([row('2025-01-02'),row('2025-01-02')],sessions,'XLK'),/Duplicate/);
});
