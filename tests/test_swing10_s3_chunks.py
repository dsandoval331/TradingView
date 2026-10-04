import base64
import hashlib
from pathlib import Path
import pytest
from cloud_compute import artifact_readback as rb
from cloud_compute import streaming_artifacts as stream

def setup(tmp_path):
    path=tmp_path/'frozen.csv';path.write_bytes(b'a,b\n'+b'x,y\n'*3000000)
    stored,meta=stream.package(path);record={'artifact_id':'fixture',**stream.digest(stored),'metadata_json':meta};plan=rb._chunk_plan(stored)
    return stored,record,plan

def test_complete_streamed_private_to_sql_parity(tmp_path,monkeypatch):
    stored,record,plan=setup(tmp_path);saved=[]
    monkeypatch.setattr(rb,'_save_chunk',lambda c,p:saved.append(p))
    rb._persist_chunks(None,record,stored,plan)
    monkeypatch.setattr(rb,'_fetch_rows',lambda c,t,p:[x for x in saved if x['chunk_no']==int(p['chunk_no'][3:])])
    physical,logical=rb._verify_chunks(None,{'metadata_json':{'chunks':plan}},record,tmp_path/'reconstructed.gz')
    assert physical==stream.digest(stored) and logical['sha256']==record['metadata_json']['logical_sha256']
    assert all(x['size_bytes']<=1048576 for x in saved)

@pytest.mark.parametrize('fault',['missing','corrupt','wrong_number','wrong_digest','bad_plan'])
def test_chunk_failures_are_closed(tmp_path,monkeypatch,fault):
    stored,record,plan=setup(tmp_path);data=stored.read_bytes();row={'chunk_no':0,'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'content_base64':base64.b64encode(data).decode()}
    if fault=='missing':result=[]
    else:
        result=[row]
        if fault=='corrupt':row['content_base64']=base64.b64encode(b'wrong').decode()
        elif fault=='wrong_number':row['chunk_no']=1
        elif fault=='wrong_digest':row['sha256']='0'*64
        elif fault=='bad_plan':plan=[]
    monkeypatch.setattr(rb,'_fetch_rows',lambda *a:result)
    with pytest.raises(RuntimeError):rb._verify_chunks(None,{'metadata_json':{'chunks':plan}},record,tmp_path/'bad.gz')

def test_multi_chunk_order_exact_and_no_omission(tmp_path,monkeypatch):
    # Entropy fixture ensures multiple bounded physical chunks without market data.
    import random
    path=tmp_path/'entropy.csv';randomizer=random.Random(73)
    with path.open('w') as f:
        for i in range(150000):f.write(f'FIXTURE,{i},'+''.join(randomizer.choices('abcdefghijklmnopqrstuvwxyz0123456789',k=80))+'\n')
    stored,meta=stream.package(path);record={'artifact_id':'fixture',**stream.digest(stored),'metadata_json':meta};plan=rb._chunk_plan(stored);assert len(plan)>1
    saved=[];monkeypatch.setattr(rb,'_save_chunk',lambda c,p:saved.append(p));rb._persist_chunks(None,record,stored,plan)
    monkeypatch.setattr(rb,'_fetch_rows',lambda c,t,p:[saved[int(p['chunk_no'][3:])]])
    assert rb._verify_chunks(None,{'metadata_json':{'chunks':plan}},record,tmp_path/'SQL.gz')[1]['sha256']==meta['logical_sha256']
