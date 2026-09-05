import { createClient } from "../../lib/supabase/server";

export async function loadStrategies() {
  const supabase = await createClient();
  return supabase
    .from("strategies")
    .select("strategy_id,strategy_code,strategy_name,strategy_type,status,baseline_model,description,created_at,updated_at")
    .order("strategy_code", { ascending: true })
    .limit(25);
}
