"""Outcome-blind, zero-source, full-scale frozen-schema storage certification."""
import csv
import hashlib
import json
from pathlib import Path
import uuid
from cloud_compute.streaming_artifacts import package
from tr_platform.research import swing10_s3_preparation as prep

MWE='3ac865ff-4f78-4f2c-807d-e579604ea39f'
DECISION='21091322-b757-42e5-9918-dba46b2e1252'

def run(work_root):
    work_root=Path(work_root);root=Path(__file__).resolve().parents[2]
    contract=json.loads((root/'research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.proposed.json').read_text())
    context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text())
    if context.get('mwe_uuid')!=MWE or context.get('synthetic_only') is not True or context.get('materialized_inputs')!=[]:
        raise ValueError('zero-input synthetic activation only; real/protected source forbidden')
    prep.validate_contract(contract);out=work_root/'research_outputs/swing10/s3_artifact_cert';out.mkdir(parents=True,exist_ok=True)
    declarations=[];ids={};metadata={};paths=[];primary=None
    schemas=contract['artifact_schemas']
    for name,columns in schemas.items():
        if not name.endswith('.csv'):continue
        path=out/name;rows=0
        with path.open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');writer.writeheader()
            if name=='s3_event_paths.csv':
                # Same full cardinality established outcome-blind in verified S3P:
                # 36cells *379signal dates *23symbols *10path sessions.
                for cell in range(36):
                    for date in range(379):
                        for symbol in range(23):
                            for day in range(1,11):
                                value=20+(date*31+symbol*17+day*11)%1000/7
                                writer.writerow(dict(candidate_id=f'FIXTURE_CELL_{cell:02}',symbol=f'FIXTURE_SYMBOL_{symbol:03}',signal_date=f'FIXTURE_DATE_{date:03}',entry_date=f'FIXTURE_SESSION_{date+1:03}',entry_price=value,path_day=day,session_date=f'FIXTURE_SESSION_{date+day:03}',open=value,high=value*1.02,low=value*.98,close=value*1.001,side_return=0.,path_eligible=True,censor_reason='SYNTHETIC_NO_MARKET_SOURCE'))
                                rows+=1
            else:
                count=313812 if name=='s3_event_exits.csv' else 12 if name=='s3_candidate_summary.csv' else 36 if name=='s3_candidate_registry.csv' else 379*36 if name=='s3_date_candidate_metrics.csv' else 48 if name=='s3_temporal_stability.csv' else 112*12 if name=='s3_symbol_concentration.csv' else 1000 if name=='s3_cost_path_diagnostics.csv' else 6
                for i in range(count):
                    row={c:f'SYNTHETIC_{i}_{c}' for c in columns};writer.writerow(row);rows+=1
        stored,meta=package(path);meta.update(synthetic_only=True,rows=rows,logical_schema=columns)
        rel=str(stored.relative_to(work_root));identity=str(uuid.uuid4());ids[rel]=identity;metadata[rel]=meta;paths.append(rel)
        if name=='s3_candidate_summary.csv':primary=rel
        declarations.append(dict(name=name,artifact_id=identity,object_path=f"artifacts/{context['job_id']}/{context['attempt_id']}/{stored.name}",**meta))
    manifest=out/'sw10_s3_manifest.json'
    manifest.write_text(json.dumps(dict(protocol_decision_ids=[DECISION],execution_ids=context,synthetic_only=True,real_outcomes_computed=False,source_inputs=[],certified_full_path_rows=3138120,schemas=schemas,artifacts=declarations,protected_flags={'B5_read':False,'S5_read':False},billing_evidence=None,manifest_self_hash='external immutable registration only'),indent=2,sort_keys=True)+'\n')
    stored,meta=package(manifest);rel=str(stored.relative_to(work_root));paths.append(rel);ids[rel]=str(uuid.uuid4());metadata[rel]=dict(meta,synthetic_only=True)
    return {'status':'PASS','artifact':primary,'output_paths':paths,'output_artifact_ids':ids,'output_artifact_metadata':metadata}
