import { redirect } from "next/navigation";
import { createClient } from "../../lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const supabase = await createClient();
  const { data: claimsData, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claimsData?.claims) redirect("/login");

  const { data: allowed, error: accessError } = await supabase.rpc("is_trading_research_web_user");
  if (accessError || allowed !== true) redirect("/unauthorized");

  const { data: strategies, error } = await supabase
    .from("strategies")
    .select("strategy_id,strategy_code,strategy_name,strategy_type,status,baseline_model,description,created_at,updated_at")
    .order("strategy_code", { ascending: true })
    .limit(25);

  return (
    <main>
      <section className="hero compactHero">
        <p className="eyebrow">TRADING RESEARCH PLATFORM</p>
        <h1>Research dashboard</h1>
        <p className="lede">Authenticated, allowlisted, read-only access to the research database.</p>
        <form action="/auth/signout" method="post"><button className="secondaryButton" type="submit">Sign out</button></form>
      </section>
      <section className="next">
        <p className="eyebrow">DATABASE HEALTH CHECK</p>
        <h2>Strategies</h2>
        {error ? <p>Protected query failed: {error.message}</p> : <p>Protected query succeeded. Rows returned: {strategies?.length ?? 0}.</p>}
        {strategies && strategies.length > 0 && <pre className="dataPreview">{JSON.stringify(strategies, null, 2)}</pre>}
      </section>
    </main>
  );
}
