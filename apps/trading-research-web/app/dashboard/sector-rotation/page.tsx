import {loadSwingSuggestions} from './swing-data';
import {marketDate} from './swing-trades';
import {loadSectorForecasts} from './sector-forecast-data';
import TrackerNav from './TrackerNav';
import { redirect } from 'next/navigation';
import { createClient } from '../../../lib/supabase/server';
import Tracker from './Tracker';
import { Bar } from './model';

export const dynamic = 'force-dynamic';
export const metadata = { title: 'Sector Rotation | MULtipLY' };
export default async function SectorRotationPage() {
  const supabase = await createClient();
  const {data:claims,error:authError} = await supabase.auth.getClaims();
  if (authError || !claims?.claims) redirect('/login');
  const {data:allowed,error:accessError} = await supabase.rpc('is_trading_research_web_user');
  if (accessError || allowed !== true) redirect('/unauthorized');
  const {data:runs,error:runError} = await supabase.from('sector_tracker_runs').select('run_id,status,started_at,completed_at,latest_session,requested_start,external_run_id').order('started_at',{ascending:false}).limit(10);
  const latest = runs?.find(r=>r.status==='COMPLETE');
  let bars: Bar[]=[];
  let error = runError ? 'The sector data service is unavailable. No sample values are substituted.' : null;
  if (latest) {
    for (let offset=0; ;offset+=1000) {
      const result=await supabase.from('v_sector_daily_latest').select('symbol,trade_date,close,volume,collected_at,open,high,low').gte('trade_date',latest.requested_start).order('trade_date').order('symbol').range(offset,offset+999);
      if (result.error) { error='Sector history could not be loaded. Please try again.'; bars=[]; break; }
      bars.push(...(result.data??[]) as Bar[]);
      if ((result.data?.length??0)<1000) break;
    }
  }
  const forecastData=await loadSectorForecasts();
  return <main><TrackerNav/><Tracker winnerForecasts={forecastData.rows} winnerForecastError={forecastData.error} swingSuggestions={await loadSwingSuggestions()} asOfDate={marketDate()} bars={bars} updatedAt={latest?.completed_at??null} latestSession={latest?.latest_session??null} runStatus={runs?.[0]?.status??'NOT_STARTED'} error={error}/></main>;
}
