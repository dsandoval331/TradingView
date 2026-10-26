import {loadSwingSuggestions} from '../../swing-data';
import {marketDate} from '../../swing-trades';
import Tracker from '../../Tracker';
import TrackerNav from '../../TrackerNav';
import {loadStockHistory} from '../data';
import {TOP_50_STOCKS,TOP_50_AS_OF,TOP_50_SOURCE} from '../symbols';
export const dynamic='force-dynamic';
export const metadata={title:'S&P 500 Top 50 Index | MULtipLY'};
export default async function Top50Page(){
 const data=await loadStockHistory(TOP_50_STOCKS.map(g=>g.symbol));
 const loaded=new Set(data.bars.map(b=>b.symbol));
 const missing=TOP_50_STOCKS.filter(g=>!loaded.has(g.symbol)).map(g=>g.symbol);
 const failed=data.requests.filter(r=>r.last_error).map(r=>r.symbol);
 return <main><TrackerNav/>
  <p>Constituent tracker for 50 companies / 51 share classes, including both Alphabet classes. Membership snapshot: {TOP_50_AS_OF}, based on <a href={TOP_50_SOURCE} target="_blank" rel="noreferrer">Invesco XLG stock holdings</a>. Cash and fund positions are excluded. Historical returns follow these current constituents; this view does not reconstruct past index membership or calculate the official weighted index return.</p>
  {missing.length>0&&<p role="status">Awaiting initial history for {missing.join(', ')}. No sample values are substituted.</p>}
  {failed.length>0&&<p role="alert">Latest collection failed for {failed.join(', ')}. Last verified history is retained.</p>}
  <Tracker swingSuggestions={await loadSwingSuggestions()} asOfDate={marketDate()} stocks groups={TOP_50_STOCKS} title="S&P 500 Top 50 Index" bars={data.bars} updatedAt={data.updatedAt} latestSession={data.latestSession} runStatus="COMPLETE" error={data.error}/>
 </main>;
}
