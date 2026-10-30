import Link from 'next/link';
import {redirect} from 'next/navigation';
import {createClient} from '../../../lib/supabase/server';
import Analysis from './Analysis';
import events from './events.json';
import type {WebhookEvent} from './model';

export const dynamic = 'force-dynamic';
export const metadata = {title: 'OSI Analysis | MULtipLY'};

export default async function OSIAnalysisPage() {
  const client = await createClient();
  const {data, error} = await client.auth.getClaims();
  if (error || !data?.claims) redirect('/login');
  const {data: allowed, error: accessError} = await client.rpc('is_trading_research_web_user');
  if (accessError || allowed !== true) redirect('/unauthorized');
  return <main><nav className="projectNav" aria-label="OSI Navigation"><Link href="/dashboard">← MULtipLY Dashboard</Link></nav><Analysis events={events as WebhookEvent[]}/></main>;
}
