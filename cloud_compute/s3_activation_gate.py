"""Fail-closed S3 authority/operational gate before any private input download."""
import json
from pathlib import Path
from cloud_compute.control_plane import _fetch_rows

MWE='3ac865ff-4f78-4f2c-807d-e579604ea39f'
DECISION='21091322-b757-42e5-9918-dba46b2e1252'

def verify_activation(config,parameters):
    if parameters.get('mwe_uuid')!=MWE or parameters.get('protocol_decision_id')!=DECISION or parameters.get('scientific_outcomes_authorized') is not True or parameters.get('parent_input_id')!='131b6bd5-65d1-4dc7-a856-3300f73babcb':
        raise RuntimeError('exact frozen S3 scientific envelope required before private access')
    mwes=_fetch_rows(config,'work_envelopes',{'work_envelope_id':f'eq.{MWE}','limit':'2'})
    if len(mwes)!=1 or mwes[0]['status']!='ACTIVE' or mwes[0]['frozen_contract_json'].get('scientific_execution_authorized') is not True or mwes[0]['metadata_json'].get('operational_activation_verified') is not True:
        raise RuntimeError('durable MWE authority and independently verified activation required')
    decisions=_fetch_rows(config,'project_decisions',{'decision_id':f'eq.{DECISION}','limit':'2'})
    snapshot=json.loads(Path('research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.persisted.json').read_text())
    if len(decisions)!=1 or any(decisions[0].get(k)!=v for k,v in snapshot.items()):
        raise RuntimeError('complete unchanged frozen protocol independently reread before source access')
    evidence=parameters.get('operational_activation_evidence') or {};job_id=evidence.get('job_id')
    if evidence!=mwes[0]['metadata_json'].get('operational_activation_evidence'):
        raise RuntimeError('activation provenance must match independently verified durable MWE evidence')
    jobs=_fetch_rows(config,'research_jobs',{'job_id':f'eq.{job_id}','limit':'2'})
    if len(jobs)!=1 or jobs[0]['runner_job_id']!='SW10-S3-ARTIFACT-CERT' or jobs[0]['status']!='succeeded' or jobs[0]['git_sha']!=evidence.get('research_sha'):
        raise RuntimeError('succeeded exact-revision synthetic activation required')
    attempts=_fetch_rows(config,'research_job_attempts',{'job_id':f'eq.{job_id}','order':'attempt_no.desc','limit':'1'})
    if len(attempts)!=1 or attempts[0]['status']!='succeeded' or attempts[0]['attempt_id']!=evidence.get('attempt_id') or attempts[0]['git_sha']!=evidence.get('research_sha'):
        raise RuntimeError('latest exact activation attempt required')
    artifacts=_fetch_rows(config,'research_job_artifacts',{'job_id':f'eq.{job_id}','attempt_id':f"eq.{evidence['attempt_id']}"})
    readbacks=_fetch_rows(config,'research_artifact_readbacks',{'job_id':f'eq.{job_id}','select':'artifact_id,size_bytes,sha256,verified_sha256,metadata_json,source_git_sha,readback_git_sha'})
    expected=set(json.loads(Path('research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.proposed.json').read_text())['artifact_schemas'])
    if len(artifacts)!=10 or {a['metadata_json'].get('logical_name') for a in artifacts}!=expected:raise RuntimeError('all ten full-scale frozen artifact schemas required')
    rb={x['artifact_id']:x for x in readbacks}
    for a in artifacts:
        b=rb.get(a['artifact_id'])
        if not b or b['verified_sha256'] is not True or b['sha256']!=a['sha256'] or b['size_bytes']!=a['size_bytes'] or b['source_git_sha']!=evidence['research_sha'] or b['metadata_json'].get('source_attempt_id')!=evidence['attempt_id']:
            raise RuntimeError('complete exact-attempt durable lossless readback parity required')
    paths=[a for a in artifacts if a['metadata_json']['logical_name']=='s3_event_paths.csv']
    if paths[0]['metadata_json'].get('rows')!=3138120 or paths[0]['metadata_json'].get('logical_size_bytes',0)<=10*1024*1024:
        raise RuntimeError('full-scale above-ceiling path certification required')
    return evidence
