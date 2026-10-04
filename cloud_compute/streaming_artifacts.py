"""Lossless gzip storage and complete base64 SQL readback; no scientific logic."""
import base64
import codecs
import gzip
import hashlib
import shutil
from pathlib import Path

MAX_STORAGE_BYTES = 250 * 1024 * 1024
MAX_SQL_ENCODED_BYTES = 90 * 1024 * 1024
CHUNK = 1024 * 1024

def digest(path):
    h=hashlib.sha256();size=0
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(CHUNK),b''):
            size+=len(chunk);h.update(chunk)
    return {'size_bytes':size,'sha256':h.hexdigest()}

def logical_digest(path,encoding):
    if encoding not in ('identity','gzip'):raise ValueError('unapproved storage encoding')
    opener=gzip.open if encoding=='gzip' else open
    decoder=codecs.getincrementaldecoder('utf-8')('strict');h=hashlib.sha256();size=0
    with opener(path,'rb') as f:
        for chunk in iter(lambda:f.read(CHUNK),b''):
            decoder.decode(chunk);h.update(chunk);size+=len(chunk)
    decoder.decode(b'',final=True)
    return {'size_bytes':size,'sha256':h.hexdigest()}

def package(path):
    path=Path(path);logical=logical_digest(path,'identity')
    stored=path;encoding='identity'
    if logical['size_bytes']>10*1024*1024:
        stored=Path(str(path)+'.gz');encoding='gzip'
        with path.open('rb') as src,stored.open('wb') as dest:
            with gzip.GzipFile(fileobj=dest,mode='wb',filename='',mtime=0,compresslevel=6) as zipped:
                shutil.copyfileobj(src,zipped,CHUNK)
    physical=digest(stored)
    if physical['size_bytes']>MAX_STORAGE_BYTES or encoding=='gzip' and 4*((physical['size_bytes']+2)//3)>MAX_SQL_ENCODED_BYTES:
        raise RuntimeError('lossless artifact exceeds certified existing storage/SQL capacity; never truncate')
    return stored,{'logical_name':path.name,'storage_encoding':encoding,'logical_size_bytes':logical['size_bytes'],'logical_sha256':logical['sha256'],'stored_size_bytes':physical['size_bytes'],'stored_sha256':physical['sha256']}

def verify(path,artifact):
    physical=digest(path)
    if physical!={'size_bytes':int(artifact['size_bytes']),'sha256':artifact['sha256']}:raise RuntimeError('private physical byte parity failure')
    meta=artifact.get('metadata_json') or {};encoding=meta.get('storage_encoding','identity')
    logical=logical_digest(path,encoding)
    expected={'size_bytes':int(meta.get('logical_size_bytes',artifact['size_bytes'])),'sha256':meta.get('logical_sha256',artifact['sha256'])}
    if logical!=expected:raise RuntimeError('decompressed logical UTF-8 byte parity failure')
    return physical,logical

def sql_encode(path,artifact):
    physical,logical=verify(path,artifact)
    if (artifact.get('metadata_json') or {}).get('storage_encoding')=='gzip':
        if 4*((physical['size_bytes']+2)//3)>MAX_SQL_ENCODED_BYTES:raise RuntimeError('SQL lossless capacity exceeded')
        return base64.b64encode(Path(path).read_bytes()).decode('ascii'),'base64+gzip',logical
    return Path(path).read_text(encoding='utf-8'),'utf-8',logical

def verify_sql(row,artifact,destination):
    encoding=row['content_encoding']
    if encoding=='base64+gzip':data=base64.b64decode(row['content_text'],validate=True)
    elif encoding=='utf-8':data=row['content_text'].encode('utf-8')
    else:raise RuntimeError('unapproved SQL content encoding')
    Path(destination).write_bytes(data)
    return verify(destination,artifact)
