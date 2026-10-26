import Tracker from '../../Tracker';
import TrackerNav from '../../TrackerNav';
import {loadStockHistory} from '../data';
import {FREQUENT_STOCKS} from '../symbols';
export const dynamic='force-dynamic';
export const metadata={title:'Frequently Traded Stocks | MULtipLY'};
export default async function FrequentPage(){
 const data=await loadStockHistory(FREQUENT_STOCKS.map(g=>g.symbol));
 const missing=FREQUENT_STOCKS.filter(g=>!data.bars.some(b=>b.symbol===g.symbol)).map(g=>g.symbol);
 const failed=data.requests.filter(r=>r.last_error).map(r=>r.symbol);
 return <main><TrackerNav/>{missing.length>0&&<p role="status">Awaiting initial history for {missing.join(', ')}. No sample values are substituted.</p>}{failed.length>0&&<p role="alert">Latest collection failed for {failed.join(', ')}. Last verified history is retained.</p>}<Tracker stocks groups={FREQUENT_STOCKS} title="Frequently traded stocks" bars={data.bars} updatedAt={data.updatedAt} latestSession={data.latestSession} runStatus="COMPLETE" error={data.error}/></main>;
}
