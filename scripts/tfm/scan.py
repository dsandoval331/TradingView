"""Bounded TFM scan over operational archives only; no market-provider calls.
CLI reads existing GitHub secret path. Fixture-only tests need no credentials.
"""
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sector_rotation'))
from collect import request_json
from engine import RULES, VERSION, SYMBOLS, SECTORS, STOCKS, digest, evaluate

MWE_UUID='19dd7129-0d19-4c1b-a65b-03480a925b8d'


def reconcile(setups, results, existing_setups, existing_results):
    old={r['setup_key']:r for r in existing_setups}
    old_results={r['setup_key']:r for r in existing_results}
    additions=[s for s in setups if s['setup_key'] not in old]
    changes={s['setup_key'] for s in setups if s['setup_key'] in old and s['setup_sha256']!=old[s['setup_key']]['setup_sha256']}
    # Never score a restated target against a differently adjusted frozen Friday.
    new_results=[r for r in results if r['setup_key'] not in old_results and r['setup_key'] not in changes]
    result_changes=[r['setup_key'] for r in results if r['setup_key'] in old_results and r['result_sha256']!=old_results[r['setup_key']]['result_sha256']]
    return additions,new_results,{'reference_corrections':len(changes),'outcome_corrections':len(result_changes)}


def scan(db, sha, external_id=None, now=None):
    if not re.fullmatch('[a-f0-9]{40}',sha):raise ValueError('INVALID_GIT_SHA')
    now=now or datetime.now(timezone.utc)
    envelope=db('work_envelopes?mwe_id=eq.MWE-SECTOR-TFM-001&select=work_envelope_id,authority_ceiling,cost_policy_code')
    if len(envelope)!=1 or envelope[0]['work_envelope_id']!=MWE_UUID or envelope[0]['authority_ceiling']!='E1' or envelope[0]['cost_policy_code']!='ZERO_INCREMENTAL_COST_FIRST':raise ValueError('INVALID_ENVELOPE_AUTHORITY')
    contract=db('tfm_rules?version=eq.'+VERSION+'&select=rules_sha256')
    if not contract or contract[0]['rules_sha256']!=digest(RULES):raise ValueError('RULE_FREEZE_REQUIRED')
    run_id=str(uuid.uuid4())
    db('tfm_runs','POST',{'run_id':run_id,'rule_version':VERSION,'work_envelope_id':MWE_UUID,'status':'RUNNING','git_sha':sha,'external_run_id':external_id})
    def load(path):
        rows=[]
        for offset in range(0,200000,1000):
            page=db(path+f'&limit=1000&offset={offset}')
            rows.extend(page)
            if len(page)<1000:return rows
        raise ValueError('PAGINATION_LIMIT')
    try:
        rows=[]
        for source,symbols in [('v_sector_daily_latest',('SPY',)+SECTORS),('v_stock_daily_latest',STOCKS)]:
            select='symbol,trade_date,open,high,low,close,run_id,collected_at,response_sha256'
            source_rows=load(source+'?select='+select+'&symbol=in.('+','.join(symbols)+')&order=symbol,trade_date')
            for row in source_rows:row['source_view']=source
            rows.extend(source_rows)
        # Require provenance for every bar, never accept untraceable observations.
        if any(not r.get('run_id') or not re.fullmatch('[a-f0-9]{64}',r.get('response_sha256','')) for r in rows):raise ValueError('SOURCE_PROVENANCE_MISSING')
        setups,results,coverage=evaluate(rows,now)
        existing_setups=load('tfm_setups?select=setup_key,setup_sha256,run_id&rule_version=eq.'+VERSION+'&order=setup_key')
        existing_results=load('tfm_outcomes?select=setup_key,result_sha256,run_id&order=setup_key')
        # A partial publication must not be mistaken for a successful prior run.
        runs=load('tfm_runs?select=run_id,status&rule_version=eq.'+VERSION+'&order=run_id')
        published={r['run_id'] for r in runs if r['status']=='COMPLETE'}
        if any(r['run_id'] not in published for r in existing_setups+existing_results):raise ValueError('PARTIAL_PUBLICATION_REQUIRES_RECOVERY')
        additions,new_results,corrections=reconcile(setups,results,existing_setups,existing_results)
        setup_rows=[{**{k:s[k] for k in ('setup_key','rule_version','symbol','friday','target_date','cohort','qualifies','origin','setup_sha256')},'run_id':run_id,'payload':s} for s in additions]
        result_rows=[{'setup_key':r['setup_key'],'run_id':run_id,'setup_sha256':r['setup_sha256'],'result_sha256':r['result_sha256'],'payload':r} for r in new_results]
        diagnostics={**corrections,'setups_added':len(additions),'outcomes_added':len(new_results),'evaluated_setups':len(setups),'qualified_setups':sum(s['qualifies'] for s in setups),'market_provider_calls':0,'cost_policy':'ZERO_INCREMENTAL_COST_FIRST','billing_verified':False}
        db('rpc/tfm_publish_scan','POST',{'p_run_id':run_id,'p_setups':setup_rows,'p_outcomes':result_rows,'p_coverage':coverage,'p_diagnostics':diagnostics})
        return {'run_id':run_id,'status':'COMPLETE','diagnostics':diagnostics,'coverage':coverage}
    except Exception as error:
        db('tfm_runs?run_id=eq.'+run_id,'PATCH',{'status':'FAILED','completed_at':datetime.now(timezone.utc).isoformat(),'diagnostics':{'error_type':type(error).__name__,'error_code':str(error) if isinstance(error,ValueError) else 'REQUEST_FAILED'}})
        raise


def main():
    base=os.environ['SUPABASE_URL'].rstrip('/')+'/rest/v1/'
    secret=os.environ['SUPABASE_SECRET_KEY']
    headers={'apikey':secret,'Authorization':'Bearer '+secret}
    def db(path,method='GET',data=None):return request_json(base+path,headers,method,data)[0]
    print(json.dumps(scan(db,os.environ['GITHUB_SHA'],os.environ.get('GITHUB_RUN_ID')),allow_nan=False))

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'FAILED','error_type':type(error).__name__}),file=sys.stderr)
        raise SystemExit(1)
