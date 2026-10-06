"""S4P design recommendation and synthetic-only safeguards. Never S4 science."""
import hashlib
import json
import math
import os
from datetime import datetime
from pathlib import Path

MWE = '9ddaa698-f607-4b86-b145-6bb0d762d34d'
AUTHORITY = '694d2ba3-f470-40ea-ad8f-a73eaaaa57ec'
PARENT = '00215876-a9cf-4076-ad9b-64abeefb87d4'
FILES = (
    'sw11_s4p_candidate_registry.json', 'sw11_s4p_strategy_semantics.json',
    'sw11_s4p_statistics.json', 'sw11_s4p_robustness_registry.json',
    'sw11_s4p_advancement_truth_table.json', 'sw11_s4p_data_boundary.json',
    'sw11_s4p_source_audit.json', 'sw11_s4p_synthetic_certification.json',
    'sw11_s4p_unresolved_decisions.json', 'sw11_s4p_manifest.json')

# These are a reviewable E1 recommendation, not a scientific freeze.
PROPOSAL = {
 'status':'DRAFT_REQUIRES_CANONICAL_PROSPECTIVE_APPROVAL',
 'protocol_recommendation':'SWING11_S4_STRATEGY_PROTOCOL_V1',
 'parent_architecture':'S3-C0_PRICE_ONLY',
 'registry':[
   {'id':'S4-TIME-5','sessions':5,'rationale':'Shortest previously registered compatible holding horizon.'},
   {'id':'S4-TIME-7','sessions':7,'rationale':'Middle previously registered compatible holding horizon.'},
   {'id':'S4-TIME-10','sessions':10,'rationale':'User maximum; a cap, never a mandated target.'}],
 'inherited':{
   'signal':'Finite positive same-date adjusted close; average ranks/N; centered=2*pct-1.',
   'tails':'Long pct<=0.20; short pct>=0.80; inclusive ties; overlap => NO_TRADE.',
   'selection':'Keep every eligible tail member; equal weight within each side; minimum five per side.',
   'entry':'Decision close t; entry no earlier than adjusted open t+1.',
   'time_exit':'Adjusted close t+H, H in 5/7/10; no 15-session deployable candidate.',
   'return_algebra':'long=exit/entry-1; short=1-exit/entry; 50/50 side allocation.',
   'cash':'Inactive sleeves remain cash; no redistribution among active cohorts.'},
 'new_semantics':{
   'calendar':'Freeze common candidate decision dates from current predictor availability and complete 10-session date/bar capacity, before outcomes. Never read post-2026-08-27 prices.',
   'portfolio':'H fixed entry-capital sleeves, each at most initial equity/H. At each next-open launch reserve funded long capital, short collateral and fees. Scale both sides equally to remaining funded capacity and available gross room max(0,initial equity-existing marked gross). Unfunded slots stay cash; no external financing or reinvestment of short proceeds. Price drift can exceed the entry gross cap; report it, never claim an intraday guaranteed cap.',
   'positions':'At most 112 unique symbols and H*112 open lots; net opposite same-symbol obligations for execution while preserving separate sleeve ledgers and allocated costs. Exit obligations before new entries; no position replacement or discretionary rebalance.',
   'risk':'No price stop, profit target, trailing stop, volatility sizing or drawdown-control search. Mandatory earnings/borrow/missing-data safety exits only; 10-session forced final exit. Gap exits use first available authorized open, never fictional threshold fills. Any inability to satisfy the earnings or ten-session bound invalidates practical-test support.',
   'earnings':'Require versioned as-known calendar with symbol/event id, published_at/observed_at, expected event timestamp/timezone, revisions and certified coverage completeness. Unknown is not no earnings. Exclude entry if an event can occur before intended exit; unknown time/date treated conservatively. Re-check prior to every session; if a newly known event threatens a held position exit at the last feasible market execution before the event. If announced too late to guarantee avoidance, flag breach and fail practical support. No retrospective final-date replacement.',
   'borrow':'Require point-in-time broker/supplier locate, availability, fee and recall evidence for each short. Unknown/unavailable shorts are excluded prospectively; if either side falls below five, whole cohort NO_TRADE. Recall closes at first tradable open with actual costs. Short-interest/short-volume aggregates are not locate evidence.',
   'costs':'Proposed primary execution round trip 25 bp plus 5% annual short borrow on actual short exposure/calendar days (ACT/365); use higher certified realized fee when available. Explicit commissions/regulatory fees added, not assumed zero. Financing zero only under fully funded bookkeeping; unsupported funding => NOT_TESTABLE. Costs accrued even on forced exits; no credits assumed for short proceeds.',
   'cost_diagnostics':'Fixed execution 0/10/25/50 bp and short-borrow 0/5/20% annually, full Cartesian 12 stress views, diagnostic only, no extra candidates or favorable-scenario selection. Primary practical support also requires positive mean in 50bp/20% stress. These assumptions are modeling recommendations, not observed quotes.',
   'earnings_absence':'No certified historical PIT earnings input currently registered. Practical S4 outcomes must stay disabled until resolved; a research-only exception would require distinct explicit canonical authorization and cannot be described as meeting no-earnings holding.'},
 'statistics':{
   'primary':'Three candidate net dailyized cohort R/H date-series, NO_TRADE=0. Actual per-side costs and mandatory exits included. Trading signal date is inference unit, not trade or sleeve.',
   'families':'One family of exactly three two-sided primary tests; unavailable slots p=1. No extra inferential tests from stress or side decomposition.',
   'inference':'Intercept mean with Newey-West/Bartlett lag 9 for all H; asymptotic normal, two-sided 95%, no small-sample multiplier.',
   'materiality':'positive mean / sample SD(ddof=1)>=0.20; nonfinite or zero SD fails closed. This proposed inheritance keeps comparable dailyized date units; costs and practical exclusions require canonical acceptance.',
   'FDR':'BH jointly across 3 slots; q<=0.05.',
   'secondary':'Per-horizon net/gross returns, calendar-day portfolio P&L, cumulative non-compounded return and drawdown, long/short breakdown, holding distribution, safety exits, turnover, trades, capital/gross/net exposure, cost decomposition. Diagnostic only.'},
 'robustness':{
   'temporal':'Four deterministic approximately equal blocks from common eligible predictor/calendar dates before outcomes; >=20 dates/block, >=3/4 positive primary means, max absolute block aggregate share<=0.50.',
   'concentration':'Additive symbol reconciliation; top1/5/10 absolute shares; top5<=0.50 and HHI<=0.10. Deterministic absolute-contribution/symbol-order top-five removal and complete portfolio refit. No sign reversal; ES loss<=75%; zero ES fails positive/materiality support.',
   'capacity':'>=100 common comparison dates; active cohort rate>=0.80; >=5 symbols/side active; no borrowing of unavailable slots; unknown earnings capacity must be reported separately, not fabricated.',
   'holding':'Candidate must have at least one positive registered grid neighbor (5<->7<->10); absent outside neighbor not failure. No 15-day calculation.',
   'execution':'Primary positive/material/FDR plus positive stressed 50bp/20% mean; certified funding/earnings/borrow/data integrity; synthetic invariant suite. Long/short and market diagnostics do not become predictor rules.'},
 'selection':{
   'NOT_TESTABLE':'Primary estimand invalid from semantic/data/numerical insufficiency.',
   'NO_ADVANCE':'Any primary or required robustness/practical gate fails; unavailable required diagnostics fail advancement.',
   'QUALIFIED':'Every applicable primary and robustness/practical gate passes.',
   'precedence':'Among qualifying candidates choose shortest holding H in 5,7,10 (pre-outcome operational duration preference, not largest mean); if none NO_ADVANCE; exactly one maximum; canonical next phase remains separately authorized.'},
 'unresolved':[
   {'id':'E2-S4-DESIGN','decision':'Prospectively approve/revise this complete finite three-TIME design, all new cost/funding/inference/precedence rules before outcomes. No rule here is frozen by E1.'},
   {'id':'DATA-PIT-EARNINGS','decision':'Supply/certify historical as-known earnings plus completeness, or authorize zero-cost prospective snapshot archival and redesign the eligible development boundary prospectively. Do not treat current/finalized calendars as historical knowledge.'},
   {'id':'DATA-PIT-BORROW','decision':'Certify historical locate/availability/fees/recalls for the preserved short sleeve; otherwise explicitly authorize a separately labeled theoretical short-cost study. It cannot establish implementable short capacity.'}]
}

def finite_rank(values):
    eligible={s:float(v) for s,v in values.items() if math.isfinite(float(v)) and float(v)>0}
    n=len(eligible)
    return {s:(sum(x<v for x in eligible.values())+(sum(x==v for x in eligible.values())+1)/2)/n for s,v in eligible.items()}

def membership(values):
    ranks=finite_rank(values)
    low=sorted(s for s,p in ranks.items() if p<=.20)
    high=sorted(s for s,p in ranks.items() if p>=.80)
    active=len(low)>=5 and len(high)>=5 and not set(low)&set(high)
    return {'long':low if active else [],'short':high if active else [],'active':active}

def schedule(calendar,index,horizon):
    if horizon not in (5,7,10):raise ValueError('unregistered holding horizon')
    if len(set(calendar))!=len(calendar) or calendar!=sorted(calendar):raise ValueError('invalid calendar')
    if not 0<=index<len(calendar) or index+horizon>=len(calendar):raise ValueError('endpoint capacity')
    if any(d>'2026-08-27' for d in calendar):raise ValueError('protected date')
    return calendar[index+1],calendar[index+horizon]

def earnings_safe(record,decision_time,entry_time,exit_time):
    if not record or record.get('complete') is not True:return False
    parse=lambda s:datetime.fromisoformat(s.replace('Z','+00:00'))
    observed=parse(record['observed_at']);decision=parse(decision_time)
    if observed.tzinfo is None or decision.tzinfo is None or observed>decision:return False
    for event in record.get('events',[]):
        if not event.get('expected_at') or not event.get('published_at'):return False
        when=parse(event['expected_at']);published=parse(event['published_at'])
        if when.tzinfo is None or published.tzinfo is None or published>decision:return False
        if parse(entry_time)<=when<=parse(exit_time):return False
    return True

def allocation(active,horizon,existing_gross,funded_room):
    if horizon not in (5,7,10):raise ValueError('holding')
    if not all(math.isfinite(v) and v>=0 for v in (existing_gross,funded_room)):raise ValueError('funding')
    gross=min(1/horizon,max(0,1-existing_gross),funded_room) if active else 0
    return {'long':gross/2,'short':gross/2,'cash':1/horizon-gross}

def cost(notional,round_trip_bp,short_notional,annual_borrow,calendar_days):
    if any(not math.isfinite(v) or v<0 for v in (notional,round_trip_bp,short_notional,annual_borrow,calendar_days)):raise ValueError('invalid cost input')
    return notional*round_trip_bp/10000+short_notional*annual_borrow*calendar_days/365

def select(gates):
    if set(gates)!= {'S4-TIME-5','S4-TIME-7','S4-TIME-10'}:raise ValueError('closed registry')
    required={'testable','direction','materiality','FDR','temporal','concentration','leave_five','capacity','holding','cost_stress','earnings','borrow','funding','integrity'}
    for h in (5,7,10):
        g=gates[f'S4-TIME-{h}']
        if set(g)!=required:raise ValueError('complete gates required')
        if all(v is True for v in g.values()):return f'S4-TIME-{h}'
    return 'NO_ADVANCE'

def guard(context):
    def reject(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key.lower() in {'forward_return','future_return','pnl','effect','p_value','profitability','win_rate','price_rows','outcome_rows'}:raise ValueError('outcome/data field denied')
                reject(item)
        elif isinstance(value,list):
            for item in value:reject(item)
    # Frozen decisions may describe outcomes; only source payloads are guarded.
    for key in ('inputs','source_payload','price_rows'):reject(context.get(key))
    if context.get('mwe_uuid')!=MWE or context.get('preflight_only') is not True or context.get('scientific_outcomes_authorized') is not False:raise ValueError('S4P-only authority')
    if context.get('input_provenance') or context.get('inputs') or context.get('price_rows'):raise ValueError('S4P accepts no real market data')
    if context.get('protected_validation_authorized') is not False:raise ValueError('protected denial required')
    if context.get('parent_mwe_uuid')!=PARENT:raise ValueError('exact parent')
    if context.get('selected_architecture')!='S3-C0_PRICE_ONLY':raise ValueError('sole parent')

def run(work_root):
    context=json.loads((Path(work_root)/'job_inputs/swing10/execution_context.json').read_text())
    guard(context)
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('governed execution only')
    if any((Path(work_root)/'job_inputs').rglob('*.csv')):raise ValueError('real data materialization denied')
    if context.get('source_certification') is True:
        return run_source_certification(work_root, context)
    out=Path(work_root)/'research_outputs/swing11/s4p';out.mkdir(parents=True,exist_ok=True)
    docs={
      FILES[0]:{'status':PROPOSAL['status'],'registry':PROPOSAL['registry']},
      FILES[1]:{'status':PROPOSAL['status'],'inherited':PROPOSAL['inherited'],'new_semantics':PROPOSAL['new_semantics']},
      FILES[2]:PROPOSAL['statistics'],FILES[3]:PROPOSAL['robustness'],FILES[4]:PROPOSAL['selection'],
      FILES[5]:{'market_data_materialized':False,'new_S4_outcomes_exposed':False,'protected_validation_access':False,'B5_consumed_denied':True,'post_2026_08_27_denied':True,'S5_S6_locked':True,'development_input_metadata_only':context.get('development_metadata'),'unchanged_frozen_authority':context.get('contract_snapshot')},
      FILES[6]:context.get('source_audit'),
      FILES[7]:{'scope':'synthetic only; no real return arrays','checks':context.get('certification'),'components':['PRICE/ties','minimum side','entry/exit maximum','earnings fail closed','funded sleeves/cash','cost debit','closed registry/precedence','protected/source denial'],'future_execution_ready':False},
      FILES[8]:{'status':'BLOCKED_USER_RECOMMENDATION','decisions':PROPOSAL['unresolved'],'no_scientific_freeze_performed':True}}
    artifacts=[]
    for name,data in docs.items():
        p=out/name;p.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
        artifacts.append({'name':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size_bytes':p.stat().st_size})
    manifest={'MWE':MWE,'phase':'S4P_OUTCOME_BLIND_ONLY','status':PROPOSAL['status'],'job_id':context['job_id'],'attempt_id':context['attempt_id'],'external_execution_id':context['github_run_id'],'research_sha':context['research_revision'],'infrastructure_sha':context['infrastructure_revision'],'github_job_id':context.get('github_job_id'),'parent_mwe':PARENT,'selected_parent':'S3-C0_PRICE_ONLY','artifact_inventory':artifacts,'manifest_self_hash':'external registration only, never recursive','new_S4_outcomes_exposed':False,'protected_validation_access':False,'incremental_paid_fallback':False,'literal_zero_billing_verified':False}
    (out/FILES[-1]).write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    paths=[str((out/n).relative_to(work_root)) for n in FILES]
    return {'status':'PASS','artifact':paths[0],'output_paths':paths,'output_artifact_metadata':{p:{'logical_name':Path(p).name} for p in paths}}

# Option A is a separate bounded source-certification mode. Legacy evidence stays unchanged.
SOURCE_AUTHORITY = '46b8d99f-db1c-4dec-9f50-a0b1a5f01c4e'
SOURCE_FILES = ('sw11_s4p_option_a_source_inventory.json',
 'sw11_s4p_option_a_entitlement_probes.json',
 'sw11_s4p_option_a_historical_notice.json',
 'sw11_s4p_option_a_cashflow_funding.json',
 'sw11_s4p_option_a_gate_summary.json', 'sw11_s4p_option_a_manifest.json')
NOTICE_URL = 'https://news.microsoft.com/source/2025/04/09/microsoft-announces-quarterly-earnings-release-date-63/'
PROBES = (
 ('earnings', '/benzinga/v1/earnings', {'ticker':'MSFT','date.gte':'2025-02-03','date.lte':'2026-08-27','limit':1},
  ('benzinga_id','ticker','date','time','date_status','last_updated')),
 ('dividends', '/stocks/v1/dividends', {'ticker':'MSFT','ex_dividend_date.gte':'2025-02-03','ex_dividend_date.lte':'2026-08-27','limit':1},
  ('id','ticker','declaration_date','ex_dividend_date','record_date','pay_date','cash_amount','currency','split_adjusted_cash_amount')),
 ('splits', '/stocks/v1/splits', {'ticker':'MSFT','execution_date.gte':'2025-02-03','execution_date.lte':'2026-08-27','limit':1},
  ('id','ticker','execution_date','split_from','split_to')))

def source_guard(context):
    guard(context)
    if context.get('source_certification') is not True or context.get('source_option') != 'A_FIRST':
        raise ValueError('Option A only')
    snapshots=context.get('contract_snapshot') or []
    new=[x for x in snapshots if x.get('decision_id') == SOURCE_AUTHORITY]
    if len(new)!=1:raise ValueError('frozen source authority required')
    md=new[0].get('metadata_json') or {}
    if md.get('state')!='FROZEN' or md.get('source_certification_option')!='A_FIRST' or md.get('s4_development_outcome_exposure_authorized') is not False:
        raise ValueError('source authority or outcome boundary mismatch')

def source_request(url, *, key=None, params=None):
    # No redirects, pagination, prices, broker logins, exception text, or response-body logs.
    import requests
    allowed={'https://api.massive.com'+x[1] for x in PROBES}|{NOTICE_URL}
    if url not in allowed:raise ValueError('closed source URL registry')
    headers={'Authorization':'Bearer '+key} if key else {}
    try:
        response=requests.get(url,headers=headers,params=params,timeout=45,allow_redirects=False)
        if len(response.content)>2_000_000:raise ValueError('bounded source response exceeded')
        return response.status_code, response.content
    except requests.RequestException:
        return None, b''

def project_probe(name, status, body, keys, secret):
    # Failed bodies may echo authentication data. Never persist them or exception text.
    base={'source':name,'http_status':status,'rows_projected':[],
          'scope':'single-symbol endpoint access probe, not universe or PIT completeness'}
    if status!=200:
        base['access']='DENIED' if status in (401,403) else 'UNAVAILABLE_HTTP_OR_NETWORK'
        return base
    try:payload=json.loads(body)
    except (ValueError,UnicodeDecodeError):
        base['access']='UNPARSEABLE';return base
    rows=payload.get('results')
    if not isinstance(rows,list):base['access']='UNEXPECTED_SCHEMA';return base
    projected=[]
    for row in rows:
        if not isinstance(row,dict):raise ValueError('source row schema')
        clean={k:row[k] for k in keys if k in row and isinstance(row[k],(str,int,float,bool,type(None)))}
        if secret and secret in json.dumps(clean):raise ValueError('credential-bearing source projection rejected')
        for k in ('date','ex_dividend_date','execution_date'):
            if k in clean and not ('2025-02-03' <= str(clean[k]) <= '2026-08-27'):
                raise ValueError('source date outside development boundary')
        projected.append(clean)
    base.update(access='AVAILABLE_ENDPOINT_ONLY',rows_projected=projected,
                projected_count=len(projected),pagination_present=bool(payload.get('next_url')),
                excluded_fields='No EPS, revenue, surprises, price, return, effect or outcome fields retained')
    return base

def notice_evidence(status, body):
    import re
    import html
    result={'url':NOTICE_URL,'http_status':status,'certification':'UNAVAILABLE',
            'universe_completeness':False,'revisions_complete':False}
    if status!=200:return result
    text=body.decode('utf-8',errors='strict')
    plain=html.unescape(re.sub('<[^>]+>',' ',text))
    plain=' '.join(plain.split())
    required=('April 9, 2025','April 30, 2025','after the close of the market')
    if not all(x in plain for x in required):return result
    result.update(certification='PARTIAL_ISSUER_NOTICE_ONLY',symbol='MSFT',
      publication_date='2025-04-09',event_date='2025-04-30',event_session='AFTER_CLOSE',
      session_timezone='America/New_York',publication_time='UNKNOWN',
      earliest_conservative_daily_admission='2025-04-10',
      raw_public_archive_utf8=text,raw_sha256=hashlib.sha256(body).hexdigest(),raw_size_bytes=len(body),
      limitations=['Retrieved current authoritative archived page; publication date is issuer asserted, not independent historical capture proof.',
       'One notice does not certify revisions or absence of other events for 112 symbols and 394 sessions.'])
    return result

def funding_cashflows(*, cash, long_reserve, short_collateral, fees, dividend_debit):
    vals=(cash,long_reserve,short_collateral,fees,dividend_debit)
    if not all(math.isfinite(x) and x>=0 for x in vals):raise ValueError('finite nonnegative funding required')
    remaining=cash-long_reserve-short_collateral-fees-dividend_debit
    return {'remaining_cash':remaining,'fully_funded':remaining>=0,'short_proceeds_reinvested':False}

def run_source_certification(work_root, context):
    source_guard(context)
    key=os.environ.get('MASSIVE_API_KEY') or os.environ.get('TR_MASSIVE_API_KEY')
    probes=[]
    for name,path,params,keys in PROBES:
        if not key:
            probes.append({'source':name,'access':'CREDENTIAL_NOT_AVAILABLE','http_status':None,'rows_projected':[]});continue
        status,body=source_request('https://api.massive.com'+path,key=key,params=params)
        probes.append(project_probe(name,status,body,keys,key))
    status,body=source_request(NOTICE_URL)
    notice=notice_evidence(status,body)
    inv={'authority':context['contract_snapshot'],'source_audit':context.get('source_audit'),
         'development_metadata_only':context.get('development_metadata'),
         'credential_available_boolean_only':bool(key),'new_price_data_requested':False,
         'no_provider_purchase_or_upgrade':True,'scope':'Option A historical certification, not prospective snapshot archival'}
    cash={'synthetic_fully_funded_fixture':funding_cashflows(cash=100,long_reserve=40,short_collateral=40,fees=2,dividend_debit=1),
      'semantics':'Debit short dividend obligations on consistent share basis. Reserve long capital and short collateral. No reinvestment of short proceeds or external funding.',
      'corporate_actions':'Endpoint access alone is not full coverage. Split-adjusted prices require same-basis dividends/quantities; never add dividends twice to a total-return series.',
      'historical_broker_terms_certified':False,'complete_universe_cashflows_certified':False,
      'funding_certification':'SYNTHETIC_ACCOUNTING_ONLY_NOT_HISTORICAL_BROKER_CERTIFICATION'}
    gates={'pit_earnings_complete':False,'historical_locate_availability_fee_recall_complete':False,
           'corporate_action_cashflow_universe_complete':False,'historical_funding_terms_complete':False,
           'source_option_a_certified':False,'s4_execution_ready':False,
           'reason':'No complete as-known earnings revision/completeness ledger or historical broker locate/recall ledger in registered sources. Current endpoint probes and isolated issuer notices cannot supply missing knowledge.',
           'design_blocker_resolved':True,'option_b_authorized':False,
           'new_s4_outcomes_exposed':False,'protected_validation_access':False,
           'frozen_candidate_registry':[x['id'] for x in PROPOSAL['registry']],
           'primary_modeled_cost':{'execution_round_trip_bp':25,'short_borrow_annual_pct':5},
           'stress_views':[[x,y] for x in (0,10,25,50) for y in (0,5,20)],
           'certification':context.get('certification')}
    docs=dict(zip(SOURCE_FILES[:-1],(inv,{'probes':probes,'failure_bodies_persisted':False},notice,cash,gates)))
    out=Path(work_root)/'research_outputs/swing11/s4p_option_a';out.mkdir(parents=True,exist_ok=True)
    inventory=[]
    for name,doc in docs.items():
        p=out/name;p.write_text(json.dumps(doc,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        inventory.append({'name':name,'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    manifest={k:context.get(k) for k in ('job_id','attempt_id','github_run_id','github_job_id','research_revision','infrastructure_revision','mwe_uuid')}
    manifest.update(authority=SOURCE_AUTHORITY,artifact_inventory=inventory,manifest_self_hash='external registration only',
       source_gate_status='BLOCKED_USER_SOURCE_REQUIREMENTS',new_s4_outcomes_exposed=False,protected_validation_access=False,
       incremental_paid_fallback=False,literal_zero_billing_verified=False)
    (out/SOURCE_FILES[-1]).write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    paths=[str((out/n).relative_to(work_root)) for n in SOURCE_FILES]
    return {'status':'PASS','artifact':paths[0],'output_paths':paths,'output_artifact_metadata':{p:{'logical_name':Path(p).name,'scope':'OPTION_A_SOURCE_CERTIFICATION_ONLY'} for p in paths}}
