import { redirect } from "next/navigation";
import { createClient } from "../lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function Home() {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims) redirect("/login");
  redirect("/dashboard/v2");
}
