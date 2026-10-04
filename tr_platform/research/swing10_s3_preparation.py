"""Outcome-blind S3 preparation only. No scientific execution capability."""
import ast
import hashlib
import math

DEVELOPMENT_SHA='ea2908cd89123548404a0f48dca6633f6ef87491793f327705588b4e2ecefae2'
DEVELOPMENT_BYTES=2411604
CONSUMED_B5_SHA='b905affcb0843a4d313557fc59fc543a46413258f2c49a68f1eb87d338e55915'
OBJECT='governed_inputs/swing10/s2_b1/market_daily_history_2025-02-03_2026-08-27/'+DEVELOPMENT_SHA+'.csv'
CAPS=(5,7,10)
ARCHITECTURES=('TIME','BRACKET_1_1','BRACKET_2_1','BRACKET_2_2','TRAIL_2','STRUCTURE_5')
SIDES=('LONG_LOW','SHORT_HIGH')
FIELDS={'symbol','trade_date','open','high','low','close','volume'}

def reject_outcome_columns(columns):
    if set(columns)!=FIELDS:raise ValueError('exact canonical daily-panel fields only; outcome-bearing/unknown fields prohibited')

def validate_input_registration(record):
    if record.get('sha256')!=DEVELOPMENT_SHA or record.get('object_size_bytes')!=DEVELOPMENT_BYTES or record.get('object_path')!=OBJECT:
        raise ValueError('deny B5, S5, unknown object or mismatched immutable input')
    if record.get('role')!='DEVELOPMENT_CANDIDATE' or record.get('date_start')!='2025-02-03' or record.get('date_end')!='2026-08-27':
        raise ValueError('exact provisional development boundary required')
    return True

def opaque_bytes_verify(blob):
    if len(blob)!=DEVELOPMENT_BYTES or hashlib.sha256(blob).hexdigest()!=DEVELOPMENT_SHA:
        raise ValueError('immutable byte identity mismatch')
    return True

def same_date_ranks(observations):
    # Pure predictor operation; caller supplies one current-date cross section.
    if len({s for s,v in observations})!=len(observations):raise ValueError('duplicate symbol')
    valid=sorted((float(v),s) for s,v in observations if v is not None and math.isfinite(float(v)))
    if not valid:raise ValueError('no finite predictor')
    n=len(valid);result={};i=0
    while i<n:
        j=i+1
        while j<n and valid[j][0]==valid[i][0]:j+=1
        rank=((i+1)+j)/2/n
        for k in range(i,j):result[valid[k][1]]=2*rank-1
        i=j
    return result

def quantile(values,p):
    finite=sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not finite or not 0<=p<=1:raise ValueError('finite quantile input required')
    pos=(len(finite)-1)*p;i=int(pos);j=min(i+1,len(finite)-1)
    return finite[i]+(finite[j]-finite[i])*(pos-i)

def tail_membership(current):
    lo=quantile([v for s,v in current],.2);hi=quantile([v for s,v in current],.8)
    return ({s for s,v in current if v is not None and math.isfinite(float(v)) and float(v)<=lo},
            {s for s,v in current if v is not None and math.isfinite(float(v)) and float(v)>=hi})

def signal_at_date(panel,date):
    current=panel.get(date)
    if current is None:raise ValueError('no current-date observations')
    return tail_membership(current),same_date_ranks(current)

def common_date_eligibility(calendar,signal_date):
    # Calendar-only capacity check: prior5 completed sessions, next-open entry,
    # and common full10 holding sessions, independent of all financial outcomes.
    if len(set(calendar))!=len(calendar) or calendar!=sorted(calendar):raise ValueError('unique ordered calendar')
    if any(d<'2025-02-03' or d>'2026-08-27' for d in calendar):raise ValueError('calendar outside development boundary')
    if signal_date not in calendar:return False
    i=calendar.index(signal_date)
    return i>=5 and i+10<len(calendar)

def registry():
    return [{'candidate_id':f'{s}__{a}__CAP{h}','side':s,'architecture_id':a,'cap_days':h,'status':'PROPOSED_NOT_FROZEN'} for s in SIDES for a in ARCHITECTURES for h in CAPS]

def validate_contract(c):
    if c.get('status')!='DRAFT_CANONICAL_REVIEW_REQUIRED' or c.get('outcome_execution_authorized') is not False:raise ValueError('preparation must remain draft/non-executable')
    if c['factor']['name']!='LIQ_ADJUSTED_PRICE' or c['horizons']['validated_caps']!=list(CAPS):raise ValueError('inherited factor/horizon drift')
    if c['candidate_cells']!=36 or c['primary_tests']!=12 or tuple(a['id'] for a in c['architectures'])!=ARCHITECTURES:raise ValueError('draft bounded registry mismatch')
    if c['consumed_validation']['deny_sha256']!=CONSUMED_B5_SHA or c['development']['sha256']!=DEVELOPMENT_SHA:raise ValueError('data boundary drift')
    if c['S5']['future_validation_authorized'] is not False:raise ValueError('S5 locked')
    return True

def source_guard(source):
    tree=ast.parse(source)
    allowed={'ast','hashlib','math'}
    for n in ast.walk(tree):
        if isinstance(n,(ast.Import,ast.ImportFrom)):
            mods=[a.name.split('.')[0] for a in n.names] if isinstance(n,ast.Import) else [str(n.module).split('.')[0]]
            if any(m not in allowed for m in mods):raise ValueError('outcome/network/data-access import denied')
        if isinstance(n,ast.Call):
            name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
            if name in {'shift','pct_change','read_csv','read_parquet','open','read_text','read_bytes','exec','eval','compile','__import__','get','post'}:
                # dict.get is used to select only one current date / metadata.
                if name!='get':raise ValueError('future/data/outcome primitive denied')
    return True

def execute_science(*args,**kwargs):
    raise RuntimeError('S3 outcomes disabled: canonical freeze/readback and separate scientific runner authorization required')
