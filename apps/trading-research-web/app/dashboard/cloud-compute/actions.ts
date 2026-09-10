"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { createClient } from "../../../lib/supabase/server";
import { createAdminClient } from "../../../lib/supabase/admin";

const CLOUD_COMPUTE_STRATEGY_ID = "98f761bf-c6f1-4399-b10e-e299cb332141";
const ALLOWED_RUNNERS = new Set(["CCP3-PARITY-FIXTURE", "CCP4-REMOTE-FIXTURE"]);
const STABLE_DISPATCH_WORKFLOW = "trading-research-dispatch.yml";

async function requireAuthorizedUser() {
  const supabase = await createClient();
  const { data: claimsData, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claimsData?.claims) redirect("/login");
  const { data: allowed, error: accessError } = await supabase.rpc("is_trading_research_web_user");
  if (accessError || allowed !== true) redirect("/unauthorized");
}

export async function submitCloudJob(formData: FormData) {
  await requireAuthorizedUser();

  const runnerJobId = String(formData.get("runner_job_id") ?? "").trim();
  if (!ALLOWED_RUNNERS.has(runnerJobId)) redirect("/dashboard/cloud-compute?error=runner_not_allowed");

  const gitSha = process.env.VERCEL_GIT_COMMIT_SHA || process.env.TR_GIT_SHA;
  const gitRef = process.env.VERCEL_GIT_COMMIT_REF || process.env.TR_GIT_REF || "main";
  const githubToken = process.env.TR_GITHUB_ACTIONS_TOKEN;
  const repository = process.env.TR_GITHUB_REPOSITORY || "dsandoval331/TradingView";
  if (!gitSha || !githubToken) redirect("/dashboard/cloud-compute?error=server_execution_not_configured");

  const admin = createAdminClient();
  const datasetVersion = `CCP9-WEB-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
  const { data: job, error: jobError } = await admin.from("research_jobs").insert({
    strategy_id: CLOUD_COMPUTE_STRATEGY_ID,
    runner_job_id: runnerJobId,
    project_code: "CLOUD_COMPUTE",
    phase_code: "CCP-9",
    status: "queued",
    preferred_executor: "github_actions",
    cloud_run_spend_approved: false,
    priority: 20,
    git_sha: gitSha,
    dataset_version: datasetVersion,
    parameters_json: {
      submission_source: "vercel_web_app",
      purpose: "CCP-9 authenticated web submission",
      git_ref: gitRef,
      dispatch_workflow: STABLE_DISPATCH_WORKFLOW,
      retry_policy: { enabled: true, max_attempts: 2, retry_exit_codes: [1, 2] },
    },
  }).select("job_id").single();

  if (jobError || !job) redirect("/dashboard/cloud-compute?error=job_create_failed");

  const response = await fetch(`https://api.github.com/repos/${repository}/actions/workflows/${STABLE_DISPATCH_WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${githubToken}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ref: "main",
      inputs: { job_id: job.job_id, git_sha: gitSha, target_ref: gitRef },
    }),
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = (await response.text()).slice(0, 300);
    await admin.from("research_jobs").update({
      status: "failed",
      completed_at: new Date().toISOString(),
      last_error: `GitHub dispatch failed: HTTP ${response.status} ${detail}`,
    }).eq("job_id", job.job_id);
    redirect(`/dashboard/cloud-compute?error=dispatch_failed&job=${job.job_id}`);
  }

  revalidatePath("/dashboard/cloud-compute");
  redirect(`/dashboard/cloud-compute?submitted=${job.job_id}`);
}
