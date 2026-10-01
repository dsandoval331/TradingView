import type { ReactNode } from "react";
import { createClient } from "../../../lib/supabase/server";
import WorkEnvelopes from "./WorkEnvelopes";

type Props = {
  children: ReactNode;
  params: Promise<{ strategyCode: string }>;
};

export default async function StrategyLayout({ children, params }: Props) {
  const { strategyCode } = await params;
  const supabase = await createClient();
  const { data: strategy } = await supabase
    .from("strategies")
    .select("strategy_id")
    .eq("strategy_code", strategyCode.toUpperCase())
    .maybeSingle();

  return <>
    {children}
    {strategy?.strategy_id && <main><WorkEnvelopes strategyId={strategy.strategy_id} /></main>}
  </>;
}
