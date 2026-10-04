import hashlib
from pathlib import Path
import pytest
from cloud_compute import streaming_artifacts as stream

def artifact(path,meta):
    return {**stream.digest(path),'metadata_json':meta}

def test_full_lossless_private_and_sql_parity_above_old_ceiling(tmp_path):
    path=tmp_path/'frozen.csv';data=('symbol,date,open,high,low,close\n'+'FIXTURE,2000-01-01,100,101,99,100\n'*400000).encode();path.write_bytes(data)
    stored,meta=stream.package(path)
    assert len(data)>10*1024*1024 and meta['storage_encoding']=='gzip'
    row={'content_text':stream.sql_encode(stored,artifact(stored,meta))[0],'content_encoding':'base64+gzip'}
    physical,logical=stream.verify_sql(row,artifact(stored,meta),tmp_path/'SQL-original.gz')
    assert logical=={'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    assert physical==stream.digest(stored)

def test_gzip_deterministic_and_no_logical_schema_change(tmp_path):
    path=tmp_path/'complete.csv';path.write_bytes(b'a,b\n'+b'x,y\n'*3000000)
    first,meta=stream.package(path);digest=stream.digest(first);_,again=stream.package(path)
    assert digest==stream.digest(first) and meta==again and meta['logical_name']=='complete.csv'

@pytest.mark.parametrize('kind',['physical','logical','utf8','corrupt_gzip','unknown_encoding'])
def test_fail_closed(tmp_path,kind):
    path=tmp_path/'logical.csv';path.write_bytes(b'a,b\n'+b'x,y\n'*3000000);stored,meta=stream.package(path);record=artifact(stored,meta)
    if kind=='physical':record['sha256']='f'*64
    elif kind=='logical':meta['logical_sha256']='f'*64
    elif kind=='utf8':path.write_bytes(b'\xff');stored=path;record=artifact(path,{'storage_encoding':'identity'})
    elif kind=='corrupt_gzip':stored.write_bytes(b'bad gzip');record=artifact(stored,meta)
    else:meta['storage_encoding']='zstd'
    with pytest.raises((RuntimeError,ValueError,UnicodeError,OSError)):stream.verify(stored,record)

def test_storage_or_sql_capacity_fails_without_truncation(tmp_path,monkeypatch):
    path=tmp_path/'complete.csv';path.write_bytes(b'x\n'*6000000)
    monkeypatch.setattr(stream,'MAX_STORAGE_BYTES',1)
    with pytest.raises(RuntimeError,match='never truncate'):stream.package(path)
    assert path.stat().st_size==12000000

def test_cert_has_zero_real_input_boundary(tmp_path):
    import json
    from tr_platform.research.swing10_s3_artifact_cert import run,MWE
    context=tmp_path/'job_inputs/swing10/execution_context.json';context.parent.mkdir(parents=True)
    context.write_text(json.dumps({'mwe_uuid':MWE,'synthetic_only':True,'materialized_inputs':[{'input_id':'B5'}]}))
    with pytest.raises(ValueError,match='zero-input'):run(tmp_path)
