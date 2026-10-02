from pathlib import Path

import pytest

from cloud_compute.artifact_contract import completeness_summary, declared_output_paths, validate_declared_outputs


def test_declared_output_paths_include_primary_and_named_secondaries() -> None:
    result = {
        "output_dir": "research_outputs/demo",
        "artifact": "research_outputs/demo/summary.json",
        "summary": "research_outputs/demo/summary.json",
        "table": "research_outputs/demo/table.csv",
        "sha256": "not-a-path",
        "flag": True,
    }
    assert declared_output_paths(result) == [
        "research_outputs/demo/summary.json",
        "research_outputs/demo/table.csv",
    ]


def test_validate_and_summarize_multiple_outputs(tmp_path: Path) -> None:
    out = tmp_path / "research_outputs" / "demo"
    out.mkdir(parents=True)
    (out / "summary.json").write_text("{}", encoding="utf-8")
    (out / "table.csv").write_text("a\n1\n", encoding="utf-8")
    result = {
        "artifact": "research_outputs/demo/summary.json",
        "summary": "research_outputs/demo/summary.json",
        "table": "research_outputs/demo/table.csv",
    }
    paths = validate_declared_outputs(result, work_root=tmp_path)
    assert len(paths) == 2
    summary = completeness_summary(result, work_root=tmp_path)
    assert summary["declared_file_count"] == 2
    assert summary["primary_in_declared_files"] is True


def test_missing_declared_output_fails_closed(tmp_path: Path) -> None:
    result = {"artifact": "research_outputs/demo/missing.json"}
    with pytest.raises(RuntimeError, match="declared artifact does not exist"):
        validate_declared_outputs(result, work_root=tmp_path)


def test_path_escape_fails_closed(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    result = {"artifact": "../outside.txt"}
    with pytest.raises(RuntimeError, match="escapes work root"):
        validate_declared_outputs(result, work_root=tmp_path)


def test_attempt_scoped_readback_preserves_prior_attempts(monkeypatch):
    import hashlib
    from cloud_compute import artifact_readback as rb
    blob=b'{"classification":"BLOCKED_CREDENTIALS"}\n';sha=hashlib.sha256(blob).hexdigest();seen=[];saved=[]
    for key,value in {'SUPABASE_URL':'https://fixture.invalid','SUPABASE_SECRET_KEY':'fixture','TR_GIT_SHA':'infra'}.items():monkeypatch.setenv(key,value)
    def fetch(config,table,params):
        seen.append((table,params.copy()))
        if table=='research_jobs':return [{'status':'succeeded','git_sha':'research'}]
        if table=='research_job_attempts':return [{'status':'succeeded','git_sha':'research','attempt_id':'new'}]
        assert params['attempt_id']=='eq.new'
        return [{'artifact_id':'new-artifact','object_path':'artifacts/job/new/audit.json','bucket_name':'private','size_bytes':len(blob),'sha256':sha,'media_type':'application/json'}]
    monkeypatch.setattr(rb,'_fetch_rows',fetch)
    monkeypatch.setattr(rb,'_download_object',lambda url,key,bucket,path,local:local.write_bytes(blob))
    def save(config,payload):saved.append(payload);return payload
    monkeypatch.setattr(rb,'_upsert',save)
    result=rb.run('job',['audit.json'],attempt_id='new');assert result['count']==1
    assert [r['artifact_id'] for r in saved]==['new-artifact']
    assert saved[0]['metadata_json']['source_attempt_id']=='new'
    assert any(t=='research_job_attempts' and p['job_id']=='eq.job' and p['attempt_id']=='eq.new' for t,p in seen)


def test_attempt_scoped_readback_rejects_revision_mismatch(monkeypatch):
    from cloud_compute import artifact_readback as rb
    monkeypatch.setenv('SUPABASE_URL','https://fixture.invalid');monkeypatch.setenv('SUPABASE_SECRET_KEY','fixture')
    def fetch(config,table,params):
        if table=='research_jobs':return [{'status':'succeeded','git_sha':'current'}]
        if table=='research_job_attempts':return [{'status':'succeeded','git_sha':'old'}]
        raise AssertionError('must fail before artifact fetch/write')
    monkeypatch.setattr(rb,'_fetch_rows',fetch)
    with pytest.raises(RuntimeError,match='exact-revision'):rb.run('job',attempt_id='old')
