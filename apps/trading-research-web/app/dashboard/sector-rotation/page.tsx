import Link from 'next/link';
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
      const result=await supabase.from('v_sector_daily_latest').select('symbol,trade_date,close,volume,collected_at').gte('trade_date',latest.requested_start).order('trade_date').order('symbol').range(offset,offset+999);
      if (result.error) { error='Sector history could not be loaded. Please try again.'; bars=[]; break; }
      bars.push(...(result.data??[]) as Bar[]);
      if ((result.data?.length??0)<1000) break;
    }
  }
  return <main><Link href="/dashboard" style={{color:'#f2b84b'}}>← MULtipLY control center</Link><Link href="/dashboard/sector-rotation/tech-ai" style={{color:"#f2b84b",marginLeft:24}}>Tech &amp; AI detail →</Link><Tracker bars={bars} updatedAt={latest?.completed_at??null} latestSession={latest?.latest_session??null} runStatus={runs?.[0]?.status??'NOT_STARTED'} error={error}/></main>;
}
