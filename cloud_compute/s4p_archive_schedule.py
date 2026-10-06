"""Dedicated append-only metadata capture; no price inputs or phase transitions."""
import os,re,subprocess,sys,uuid,json
from cloud_compute.control_plane import ControlPlaneConfig,_fetch_rows,_insert_one
from tr_platform.research.swing11_s4p import MWE,archive_guard

def validate_activation(mwe):
 c=(mwe.get('metadata_json') or {}).get('option_b_collector') or {}
 if c.get('enabled') is not True:return None
 if mwe.get('work_envelope_id')!=MWE or mwe.get('status') not in ('ACTIVE','BLOCKED_USER'):raise ValueError('same authorized MWE only')
 if not re.fullmatch('[0-9a-f]{40}',c.get('research_sha','')):raise ValueError('exact collector SHA')
 if c.get('scientific_outcomes_authorized') is not False or c.get('future_price_access_authorized') is not False:raise ValueError('no science/prices')
 archive_guard(c['parameters']);return c

def execution_env(research_sha):
 if not re.fullmatch('[0-9a-f]{40}',research_sha):raise ValueError('exact source SHA')
 return {**os.environ,'TR_RESEARCH_SHA':research_sha,'TR_GIT_REF':research_sha}

def main():
 if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REF')!='refs/heads/main':raise ValueError('trusted default branch only')
 cp=ControlPlaneConfig(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SECRET_KEY'])
 rows=_fetch_rows(cp,'work_envelopes',{'work_envelope_id':f'eq.{MWE}','limit':'2'})
 if len(rows)!=1:raise RuntimeError('exact MWE')
 c=validate_activation(rows[0])
 if c is None:print('ARCHIVAL_DISABLED_NO_SOURCE_REQUESTS');return
 subprocess.run(['git','merge-base','--is-ancestor',c['research_sha'],'HEAD'],check=True,capture_output=True)
 pending=_fetch_rows(cp,'research_jobs',{'status':'eq.queued','runner_job_id':'eq.SW11-S4P','git_sha':f"eq.{c['research_sha']}",'order':'created_at.asc','limit':'100'})
 pending=[j for j in pending if (j.get('parameters_json') or {}).get('persistent_collector_direct') is True and j['parameters_json'].get('mwe_uuid')==MWE]
 if pending:
  jid=pending[0]['job_id']
 else:
  jid=str(uuid.uuid4());p={**c['parameters'],'persistent_collector_direct':True,'github_job_id':os.environ.get('GITHUB_JOB'),'scheduler_run_id':os.environ['GITHUB_RUN_ID']}
  _insert_one(cp,'research_jobs',{'job_id':jid,'strategy_id':rows[0]['strategy_id'],'runner_job_id':'SW11-S4P','project_code':'SWING11','phase_code':'S4P','status':'queued','preferred_executor':'github_actions','cloud_run_spend_approved':False,'git_sha':c['research_sha'],'dataset_version':'PROSPECTIVE_METADATA_ONLY_NO_PRICE_INPUT','parameters_json':p,'priority':50})
  _insert_one(cp,'work_envelope_research_jobs',{'work_envelope_id':MWE,'job_id':jid,'relationship_role':'EXECUTION'})
 subprocess.run([sys.executable,'-m','cloud_compute.certify_dispatch_contracts','--job-id',jid],check=True)
 subprocess.run([sys.executable,'-m','cloud_compute.autonomous_loop','--executor','github_actions','--external-execution-id',os.environ['GITHUB_RUN_ID'],'--job-id',jid,'--max-jobs','1'],check=True,env=execution_env(c['research_sha']))
 subprocess.run([sys.executable,'-m','cloud_compute.b2_readback_if_applicable','--job-id',jid],check=True)
 _insert_one(cp,'work_envelope_events',{'work_envelope_id':MWE,'authority_class':'E1','event_type':'OPTION_B_SCHEDULED_CAPTURE_VERIFIED','event_status':'VERIFIED','summary':'Metadata capture/readback succeeded; practical source coverage remains fail-closed.','research_job_id':jid,'git_sha':c['research_sha'],'metadata_json':{'external_execution_id':os.environ['GITHUB_RUN_ID'],'infrastructure_sha':os.environ['GITHUB_SHA'],'future_prices_accessed':False,'new_S4_outcomes_exposed':False,'protected_validation_access':False}})
 print(json.dumps({'job_id':jid,'metadata_capture_verified':True,'S4_science_authorized':False}))
if __name__=='__main__':main()
