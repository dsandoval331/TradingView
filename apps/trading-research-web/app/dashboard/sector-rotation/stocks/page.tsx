import Tracker from '../Tracker';
import TrackerNav from '../TrackerNav';
import {loadStockHistory,stockClient} from './data';
import {normalizeStockSymbol,FREQUENT_STOCKS} from './symbols';
import {requestStock} from './actions';
export const dynamic='force-dynamic';
export const metadata={title:'Stock Lookup | MULtipLY'};
export default async function StockPage({searchParams}:{searchParams:Promise<{symbol?:string;message?:string}>}){
 await stockClient();
 const params=await searchParams;
 const symbol=normalizeStockSymbol(params.symbol??'MSFT');
 const messages:Record<string,string>={invalid:'Enter a stock symbol such as MSFT or $MSFT (up to 10 letters, numbers, dots or hyphens).',unavailable:'The stock data service is unavailable. Please try again.',capacity:'The 30-symbol collection limit is reached. Existing symbols remain available.'};
 const data=symbol?await loadStockHistory([symbol]):null;
 const request=data?.requests.find(r=>r.symbol===symbol);
 const hasStock=!!data?.bars.some(b=>b.symbol===symbol);
 const name=FREQUENT_STOCKS.find(g=>g.symbol===symbol)?.name??symbol??'';
 return <main><TrackerNav/><h1>Stock Lookup</h1><form action={requestStock} style={{display:'flex',gap:12,alignItems:'end',flexWrap:'wrap',margin:'24px 0'}}><label htmlFor="stock-symbol">Stock symbol<input id="stock-symbol" name="symbol" type="text" maxLength={11} required defaultValue={symbol??''} placeholder="MSFT or $MSFT" autoCapitalize="characters" style={{display:'block',padding:10,marginTop:8}}/></label><button type="submit" style={{padding:12}}>View stock / request history</button></form>
 {params.message&&<p role="alert">{messages[params.message]??messages.unavailable}</p>}
 {!symbol&&<p role="alert">Enter a valid stock symbol.</p>}
 {data?.error&&<p role="alert">{data.error}</p>}
 {symbol&&!hasStock&&<p role="status">{request?.last_error?'Collection could not validate this symbol. Check the ticker; the overnight collector will retry.':request?'History requested. This symbol will be collected during the next overnight update. Refresh this page afterward.':'No history is loaded for this symbol. Submit the symbol above to request it.'}</p>}
 {hasStock&&request?.last_error&&<p role="alert">The latest collection failed for this symbol. Showing its last verified history.</p>}
 {data&&hasStock&&<Tracker key={symbol!} stocks singleStock groups={[{symbol:symbol!,name,short:name}]} title={`${symbol} stock history`} bars={data.bars} updatedAt={data.updatedAt} latestSession={data.latestSession} runStatus="COMPLETE" error={data.error}/>}
 </main>;
}
