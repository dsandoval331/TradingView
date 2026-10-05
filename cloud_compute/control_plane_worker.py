from __future__ import annotations

import argparse
import io
import json
import uuid
import mimetypes
import os
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cloud_compute.artifact_contract import primary_output_path, validate_declared_outputs
from cloud_compute.control_plane import (
    ControlPlaneConfig,
    claim_job,
    claim_job_by_id,
    create_artifact,
    create_log,
    update_attempt,
    update_job,
)
from cloud_compute.input_materializer import materialize_job_inputs
from cloud_compute.manifest import sha256_file
from cloud_compute.research_revision_adapter import GOVERNED_RESEARCH_TARGETS, run_governed_revision
from cloud_compute.storage_poc import _upload_object
from research_runner import runner

DEFAULT_ARTIFACT_BUCKET = "trading-research-market-data"


@dataclass(frozen=True)
class RunOutcome:
    exit_code: int
    job: dict[str, Any] | None = None
    attempt_id: str | None = None
    attempt_no: int = 0
    artifact_id: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_stream_logs(config: ControlPlaneConfig, *, job_id: str, attempt_id: str, stdout_text: str, stderr_text: str) -> None:
    sequence = 1
    for level, source, text in (("INFO", "runner_stdout", stdout_text), ("ERROR", "runner_stderr", stderr_text)):
        for line in text.splitlines():
            message = line.strip()
            if not message:
                continue
            create_log(config, {
                "job_id": job_id,
                "attempt_id": attempt_id,
                "sequence_no": sequence,
                "level": level,
                "source": source,
                "message": message[:4000],
                "metadata_json": {},
            })
            sequence += 1


def _persist_result_artifacts(
    config: ControlPlaneConfig,
    *,
    job_id: str,
    attempt_id: str,
    runner_job_id: str,
    bucket: str,
    result: dict[str, Any],
) -> list[dict]:
    paths = validate_declared_outputs(result, work_root=runner.WORK_ROOT)
    if not paths:
        return []

    root = runner.WORK_ROOT.resolve()
    primary_value = primary_output_path(result)
    primary_path = (root / primary_value).resolve() if primary_value else None
    persisted: list[dict] = []
    for path in paths:
        rel = str(path.relative_to(root)).replace("\\", "/")
        digest = sha256_file(path)
        is_primary = bool(primary_path is not None and path == primary_path)
        if is_primary:
            expected = result.get("sha256")
            if expected and expected != digest:
                raise RuntimeError(f"artifact checksum mismatch for {rel}")
        object_path = f"artifacts/{job_id}/{attempt_id}/{path.name}"
        _upload_object(config.supabase_url, config.secret_key, bucket, object_path, path, allow_existing=False)
        declared_ids = result.get("output_artifact_ids", {})
        identity = {"artifact_id": str(uuid.UUID(declared_ids[rel]))} if rel in declared_ids else {}
        persisted.append(create_artifact(config, {
            **identity,
            "job_id": job_id,
            "attempt_id": attempt_id,
            "artifact_type": "research_output",
            "storage_backend": "supabase_storage",
            "bucket_name": bucket,
            "object_path": object_path,
            "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "size_bytes": path.stat().st_size,
            "sha256": digest,
            "is_primary": is_primary,
            "metadata_json": {"runner_job_id": runner_job_id, "runner_relative_path": rel, **(result.get("output_artifact_metadata", {}).get(rel, {}))},
        }))
    return persisted


def _persist_runner_artifacts(config: ControlPlaneConfig, *, job_id: str, attempt_id: str, runner_job_id: str, bucket: str) -> list[dict]:
    state = runner._load_state()
    result = state.get("jobs", {}).get(runner_job_id, {}).get("result") or {}
    return _persist_result_artifacts(
        config,
        job_id=job_id,
        attempt_id=attempt_id,
        runner_job_id=runner_job_id,
        bucket=bucket,
        result=result,
    )


def run_one_outcome(
    config: ControlPlaneConfig,
    *,
    executor: str = "github_actions",
    external_execution_id: str | None = None,
    artifact_bucket: str = DEFAULT_ARTIFACT_BUCKET,
    exact_job_id: str | None = None,
) -> RunOutcome:
    infrastructure_sha = runner._git_sha()
    if not infrastructure_sha:
        raise RuntimeError("worker Git SHA is unavailable")

    # When the dispatcher runs from certified current infrastructure, the governed
    # research SHA is supplied separately. The claim still uses the research SHA
    # recorded on research_jobs, preserving the existing atomic RPC contract.
    research_sha = os.environ.get("TR_RESEARCH_SHA") or infrastructure_sha

    if exact_job_id:
        claim = claim_job_by_id(config, job_id=exact_job_id, executor=executor, git_sha=research_sha, external_execution_id=external_execution_id)
    else:
        claim = claim_job(config, executor=executor, git_sha=research_sha, external_execution_id=external_execution_id)
    if claim is None:
        print("NO_ELIGIBLE_CONTROL_PLANE_JOBS")
        return RunOutcome(exit_code=0)

    job = claim["job"]
    job_id = job["job_id"]
    runner_job_id = job["runner_job_id"]
    attempt_id = claim["attempt_id"]
    attempt_no = int(claim.get("attempt_no") or 1)
    governed_sha = str(job.get("git_sha") or research_sha)
    if governed_sha != research_sha:
        raise RuntimeError(f"claimed job research SHA mismatch: expected={research_sha} claimed={governed_sha}")

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    materialized: list[Any] = []
    adapter_used = runner_job_id in GOVERNED_RESEARCH_TARGETS and research_sha != infrastructure_sha
    provenance = {
        "runner_job_id": runner_job_id,
        "atomic_claim": True,
        "research_sha": research_sha,
        "infrastructure_sha": infrastructure_sha,
        "exact_research_sha_verified": bool(adapter_used),
        "research_revision_adapter": "v1" if adapter_used else None,
    }
    try:
        if runner_job_id == "SW11-S2A-CERT":
            parameters=job.get("parameters_json") or {}
            if parameters.get("mwe_uuid")!="eabd2257-bb59-4f32-af71-ad4b87bda4f5" or parameters.get("synthetic_only") is not True or parameters.get("scientific_outcomes_authorized") is not False:
                raise RuntimeError("exact SW11 synthetic certification authority required")
            from cloud_compute.control_plane import _fetch_rows
            if _fetch_rows(config,"research_job_inputs",{"job_id":f"eq.{job_id}","limit":"1"}):
                raise RuntimeError("synthetic certification must have zero input dependencies")
            snapshot=parameters.get("contract_snapshot") or []
            if len(snapshot)!=4 or set(x["decision_id"] for x in snapshot)!={"7c6279c1-a86d-4336-a08d-244bb5e005b4","11407ad3-97cd-459e-b78e-9162a115b8e4","f240f40d-65a0-40dd-91dc-bdf722431e2b","a040e9fa-4fdf-4dc8-8ab7-5d8db622c779"}:
                raise RuntimeError("four complete SW11 decisions required")
            for expected in snapshot:
                found=_fetch_rows(config,"project_decisions",{"decision_id":f"eq.{expected['decision_id']}","limit":"2"})
                fields=("decision_id","title","decision","rationale","evidence","metadata_json")
                if len(found)!=1 or any(found[0].get(k)!=expected.get(k) for k in fields) or found[0]["metadata_json"].get("status")!="FROZEN":
                    raise RuntimeError("unchanged frozen SW11 authority required")
        elif runner_job_id == "SW11-S2A":
            parameters=job.get("parameters_json") or {}
            if parameters.get("mwe_uuid")!="eabd2257-bb59-4f32-af71-ad4b87bda4f5" or parameters.get("preflight_only") is not True or parameters.get("scientific_outcomes_authorized") is not False:
                raise RuntimeError("SW11 exact predictor-only envelope required before private access")
            from cloud_compute.control_plane import _fetch_rows
            snapshot=parameters.get("contract_snapshot") or []
            if len(snapshot)!=3:raise RuntimeError("all three complete decision snapshots required")
            for expected in snapshot:
                found=_fetch_rows(config,"project_decisions",{"decision_id":f"eq.{expected['decision_id']}","limit":"2"})
                fields=("decision_id","title","decision","rationale","evidence","metadata_json")
                if len(found)!=1 or any(found[0].get(k)!=expected.get(k) for k in fields) or found[0]["metadata_json"].get("status")!="FROZEN":
                    raise RuntimeError("unchanged frozen SW11 authority required")
            admitted=[{"input_id":parameters["input_registration_id"],"object_path":"governed_inputs/swing10/s2_b1/market_daily_history_2025-02-03_2026-08-27/ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2.csv","object_size_bytes":2411604,"sha256":"ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2","metadata_json":{"bucket_name":"trading-research-market-data","local_relative_path":"job_inputs/swing11/development.csv"}}]
            materialized=materialize_job_inputs(config,job_id=job_id,work_root=runner.WORK_ROOT,allowed_inputs=admitted)
        elif runner_job_id == "SW10-S3":
            from cloud_compute.s3_activation_gate import verify_activation
            parameters=job.get("parameters_json") or {}
            activation=verify_activation(config,parameters)
            admitted=[{"input_id":parameters["input_registration_id"],"object_path":"governed_inputs/swing10/s2_b1/market_daily_history_2025-02-03_2026-08-27/ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2.csv","object_size_bytes":2411604,"sha256":"ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2","metadata_json":{"bucket_name":"trading-research-market-data","local_relative_path":"job_inputs/swing10/s3_development_daily_history.csv"}}]
            materialized=materialize_job_inputs(config,job_id=job_id,work_root=runner.WORK_ROOT,allowed_inputs=admitted)
        elif runner_job_id == "SW10-S3-ARTIFACT-CERT":
            parameters = job.get("parameters_json") or {}
            if parameters.get("mwe_uuid") != "3ac865ff-4f78-4f2c-807d-e579604ea39f" or parameters.get("synthetic_only") is not True:
                raise RuntimeError("exact synthetic S3 activation envelope required")
            materialized = materialize_job_inputs(config, job_id=job_id, work_root=runner.WORK_ROOT, allowed_inputs=[])
        elif runner_job_id == "SW10-S3-PREFLIGHT":
            parameters = job.get("parameters_json") or {}
            if (parameters.get("mwe_uuid") != "7d95c3a7-1c08-48a2-a865-3aa7eea8873a" or
                parameters.get("protocol_decision_id") != "21091322-b757-42e5-9918-dba46b2e1252" or
                parameters.get("preflight_only") is not True or parameters.get("scientific_outcomes_authorized") is not False):
                raise RuntimeError("S3P exact frozen outcome-blind envelope required before private access")
            admitted = [{"input_id":"131b6bd5-65d1-4dc7-a856-3300f73babcb",
                         "object_path":"governed_inputs/swing10/s2_b1/market_daily_history_2025-02-03_2026-08-27/ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2.csv",
                         "object_size_bytes":2411604,
                         "sha256":"ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2",
                         "metadata_json":{"bucket_name":"trading-research-market-data", "local_relative_path":"job_inputs/swing10/s3_development_daily_history.csv"}}]
            materialized = materialize_job_inputs(config, job_id=job_id, work_root=runner.WORK_ROOT, allowed_inputs=admitted)
        else:
            materialized = materialize_job_inputs(config, job_id=job_id, work_root=runner.WORK_ROOT)
        if materialized:
            create_log(config, {
                "job_id": job_id, "attempt_id": attempt_id, "sequence_no": 0,
                "level": "INFO", "source": "input_materializer",
                "message": f"materialized {len(materialized)} governed input(s)",
                "metadata_json": {"inputs": [{
                    "input_id": item.input_id,
                    "object_path": item.object_path,
                    "local_path": str(item.local_path.relative_to(runner.WORK_ROOT.resolve())),
                    "size_bytes": item.size_bytes,
                    "sha256": item.sha256,
                } for item in materialized]},
            })

        if runner_job_id in {"SW11-S2A-CERT", "SW11-S2A", "SW10-S3", "SW10-S3-ARTIFACT-CERT", "SW10-S3-PREFLIGHT", "SW10-S2-B2", "SW10-S2-B3-PREFLIGHT", "SW10-S2-B3-CONTINUOUS-PREFLIGHT", "SW10-S2-B3", "SW10-S2-B4-PREFLIGHT", "SW10-S2-B4", "SW10-S2-B5-PREFLIGHT", "SW10-S2-B5-ACQUISITION", "SW10-S2-B5"}:
            context = {
                "job_id": job_id, "attempt_id": attempt_id, "attempt_no": attempt_no,
                "research_revision": research_sha, "infrastructure_revision": infrastructure_sha,
                "github_run_id": external_execution_id,
                "github_job_name": os.environ.get("GITHUB_JOB"),
                "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                "materialized_inputs": [{"input_id": x.input_id, "object_path": x.object_path,
                                         "size_bytes": x.size_bytes, "sha256": x.sha256} for x in materialized],
            }
            if runner_job_id == "SW10-S3":
                parameters=job.get("parameters_json") or {}
                for key in ("mwe_uuid","protocol_decision_id","scientific_outcomes_authorized","input_registration_id"):
                    context[key]=parameters.get(key)
                context["operational_activation_verified"]=True
                context["operational_activation_evidence"]=activation
            if runner_job_id in {"SW11-S2A", "SW11-S2A-CERT"}:
                for key in ("mwe_uuid","preflight_only","synthetic_only","scientific_outcomes_authorized","contract_snapshot"):
                    context[key]=parameters.get(key)
            if runner_job_id in {"SW10-S3-PREFLIGHT", "SW10-S3-ARTIFACT-CERT"}:
                parameters = job.get("parameters_json") or {}
                for key in ("mwe_uuid", "protocol_decision_id", "scientific_outcomes_authorized", "preflight_only", "synthetic_only"):
                    context[key] = parameters.get(key)
            if runner_job_id == "SW10-S2-B5":
                parameters = job.get("parameters_json") or {}
                context["parent_input_id"] = parameters.get("parent_input_id")
                context["input_registration_id"] = parameters.get("input_registration_id")
            context_path = runner.WORK_ROOT / "job_inputs" / "swing10" / "execution_context.json"
            context_path.parent.mkdir(parents=True, exist_ok=True)
            context_path.write_text(json.dumps(context), encoding="utf-8")

        governed_result: dict[str, Any] | None = None
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            if adapter_used:
                governed_result = run_governed_revision(
                    repo_root=Path.cwd(),
                    work_root=runner.WORK_ROOT,
                    runner_job_id=runner_job_id,
                    research_sha=research_sha,
                )
                rc = 0
            else:
                rc = runner.run_id(runner_job_id)
        _record_stream_logs(config, job_id=job_id, attempt_id=attempt_id, stdout_text=stdout_buffer.getvalue(), stderr_text=stderr_buffer.getvalue())
        completed = _now()
        if rc == 0:
            if governed_result is not None:
                artifacts = _persist_result_artifacts(
                    config,
                    job_id=job_id,
                    attempt_id=attempt_id,
                    runner_job_id=runner_job_id,
                    bucket=artifact_bucket,
                    result=governed_result,
                )
            else:
                artifacts = _persist_runner_artifacts(config, job_id=job_id, attempt_id=attempt_id, runner_job_id=runner_job_id, bucket=artifact_bucket)
            primary = next((row for row in artifacts if row.get("is_primary")), None)
            artifact_id = primary.get("artifact_id") if primary else None
            update_job(config, job_id, {"status": "succeeded", "completed_at": completed})
            update_attempt(config, attempt_id, {
                "status": "succeeded", "completed_at": completed, "exit_code": 0,
                "metadata_json": {
                    **provenance,
                    "artifact_id": artifact_id,
                    "artifact_count": len(artifacts),
                    "materialized_input_count": len(materialized),
                },
            })
            print(f"CONTROL_PLANE_JOB_SUCCEEDED={job_id}")
            return RunOutcome(0, job, attempt_id, attempt_no, artifact_id)

        error = f"research_runner returned exit code {rc}"
        update_job(config, job_id, {"status": "failed", "completed_at": completed, "last_error": error})
        update_attempt(config, attempt_id, {
            "status": "failed", "completed_at": completed, "exit_code": rc,
            "error_summary": error,
            "metadata_json": {**provenance, "materialized_input_count": len(materialized)},
        })
        print(f"CONTROL_PLANE_JOB_FAILED={job_id}")
        return RunOutcome(rc, job, attempt_id, attempt_no)
    except Exception as exc:
        completed = _now()
        error = f"worker persistence failure: {exc}"
        update_job(config, job_id, {"status": "failed", "completed_at": completed, "last_error": error})
        update_attempt(config, attempt_id, {
            "status": "failed", "completed_at": completed, "exit_code": 1,
            "error_summary": error,
            "metadata_json": {**provenance, "materialized_input_count": len(materialized)},
        })
        print(f"CONTROL_PLANE_JOB_FAILED={job_id}")
        return RunOutcome(1, job, attempt_id, attempt_no)


def run_one(config: ControlPlaneConfig, *, executor: str = "github_actions", external_execution_id: str | None = None, artifact_bucket: str = DEFAULT_ARTIFACT_BUCKET, exact_job_id: str | None = None) -> int:
    return run_one_outcome(config, executor=executor, external_execution_id=external_execution_id, artifact_bucket=artifact_bucket, exact_job_id=exact_job_id).exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute one queued TradingResearch control-plane job")
    parser.add_argument("--executor", default="github_actions")
    parser.add_argument("--external-execution-id", default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--artifact-bucket", default=os.environ.get("TR_ARTIFACT_BUCKET", DEFAULT_ARTIFACT_BUCKET))
    parser.add_argument("--job-id", default=None)
    args = parser.parse_args()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    return run_one(ControlPlaneConfig(url, key), executor=args.executor, external_execution_id=args.external_execution_id, artifact_bucket=args.artifact_bucket, exact_job_id=args.job_id)


if __name__ == "__main__":
    raise SystemExit(main())
