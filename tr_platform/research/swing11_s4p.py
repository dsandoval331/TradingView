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
    if context.get('prospective_archival') is True:
        return run_prospective_archival(work_root, context)
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

# Option B: metadata only. No boundary is assigned and no market bars are fetched.
ARCHIVE_AUTHORITY = '650c2556-5b10-437b-9bf6-cdf9af20c29e'
ARCHIVE_SYMBOLS = ["AAPL","ABBV","ABNB","ADBE","AMAT","AMD","AMGN","AMZN","ANET","APP","ARM","ASML","AVGO","AXON","AXP","BA","BAC","BKNG","BLK","BMY","C","CAT","CEG","CMCSA","CME","CMG","COIN","COP","COST","CRM","CRWD","CSCO","CVS","CVX","DASH","DDOG","DE","DELL","DIS","EOG","ETN","FDX","GE","GILD","GOOG","GS","HAL","HD","HON","HOOD","IBM","INTC","ISRG","IWM","JNJ","JPM","KLAC","LLY","LMT","LOW","LRCX","LULU","MA","MCD","META","MNDY","MRK","MRNA","MRVL","MS","MSFT","MU","NEE","NFLX","NKE","NOW","NVDA","ORCL","OXY","PANW","PEP","PFE","PLTR","PYPL","QCOM","QQQ","RBLX","REGN","RTX","SBUX","SCHW","SHOP","SLB","SNOW","SPY","T","TEAM","TGT","TMO","TMUS","TQQQ","TSLA","TXN","UBER","UNH","UPS","URI","V","VRTX","VZ","WMT","XOM"]
ARCHIVE_NAMES = ('architecture','schemas','source_registry','collector_specification',
 'quality_gates','coverage_specification','boundary_recommendation','contamination_controls',
 'scheduler_specification','synthetic_certification','unresolved_decisions',
 'snapshot','coverage_health','manifest')
ARCHIVE_FILES = tuple('sw11_s4p_option_b_'+n+'.json' for n in ARCHIVE_NAMES)
ARCHIVE_DOMAINS = ('earnings','dividends','splits','broker_locate','borrow_fee','recall','funding')
ARCHIVE_ENDPOINTS = {'earnings':'/benzinga/v1/earnings',
 'dividends':'/stocks/v1/dividends','splits':'/stocks/v1/splits'}
ARCHIVE_KEYS = dict((n,k) for n,_,_,k in PROBES)
BOUNDARY_RECOMMENDATION = {
 'state':'PROPOSED_NOT_FROZEN_REQUIRES_CANONICAL_APPROVAL',
 'collection_start':'Actual first successful certified retrieval; never authorization time or provider last_updated.',
 'maturity_sessions':20,'required_slot_success_rate':0.95,
 'universe_symbols':112,'minimum_fully_observed_symbols':101,
 'per_symbol_admission':'All applicable sources complete and finite; earnings revisions/session known; account-specific short availability, quantity, fee and observable recall; declared cash flows and funding certified. Unknown is ineligible. Observed unavailable differs from unknown and is not tradable.',
 'freshness':'Latest relevant observation must precede decision/entry; pre-entry and pre-close snapshot age <=30 minutes. Delayed capture is not backdated.',
 'S4':'First fixed 126 registered trading sessions after prospective maturity/source gates pass. Missing dates remain in the interval and cannot extend it. At least 100 usable common dates; >=80% active rate; >=5 symbols/side. Final ten sessions additionally reserved for S4 endpoint runoff; no new S4 signals.',
 'S5':'Next fixed 252 registered trading sessions after S4 ten-session runoff, plus ten endpoint-only runoff sessions. At least 200 usable comparison dates and four blocks >=20 dates; missing dates never extend or move the reservation.',
 'seal':'Approve deterministic algorithm before any future price admission; publish exact dates as soon start/maturity is mechanically established and before any S4 outcome exposure. Sealed S5 never reassigned, resized or extended on results.',
 'symbol_changes':'Frozen 112-symbol universe; eligibility changes prospectively only from source records and actual timestamp. No imputation/backfill or outcome-driven inclusion.',
 'outage':'Append error/UNKNOWN; no carried-forward complete status across stale slots. Coverage gating uses actual captured slots; scheduler success alone is not source success.',
 'duration':'Conditional minimum 20 maturity +126 S4 +10 runoff +252 S5 +10 runoff =418 trading sessions (~20 months). No guaranteed start/ETA; unresolved sources prevent maturity clock.',
 'rationale':'126/252 sessions bound development and protected validation approximately half/full year; 126 allows four >=20-date blocks and >=100-date gate. Coverage thresholds are prospective proposals, not power calculations.',
 'alternatives':['Fixed calendar half-year development/full-year validation: simpler sealing but calendar/holiday coverage variation.', '252-session development +252-session validation: more stability coverage, roughly six months longer; no outcome-driven extension.'],
 'trade_count':'Report all trades; no new optimized trade-count cutoff. Existing >=5 per side and >=80% active rate remain controlling.',
 'current_boundary_assignments':0,'future_price_access_authorized':False}

def archive_guard(context):
    guard(context)
    if context.get('prospective_archival') is not True or context.get('source_option')!='B':
        raise ValueError('exact Option B metadata mode required')
    if context.get('source_certification') is True:raise ValueError('mutually exclusive source modes')
    records=[x for x in context.get('contract_snapshot',[]) if x.get('decision_id')==ARCHIVE_AUTHORITY]
    if len(records)!=1:raise ValueError('Option B frozen authority missing')
    md=records[0].get('metadata_json') or {}
    if md.get('state')!='FROZEN' or md.get('prospective_archival_authorized') is not True:
        raise ValueError('prospective archival not authorized')
    for k in ('exact_future_boundary_frozen','future_price_access_authorized','protected_validation_authorized','s4_development_outcome_exposure_authorized'):
        if md.get(k) is not False:raise ValueError('metadata-only authorization boundary')
    symbols=context.get('archive_symbols')
    if symbols != ARCHIVE_SYMBOLS:
        raise ValueError('exact frozen symbol registry required')
    if any(k in context for k in ('price_rows','forward_returns','boundary_assignments','validation_input')):
        raise ValueError('prices/outcomes/boundary assignment denied')

_ARCHIVE_LAST_REQUEST = None
_ARCHIVE_DEADLINE = None

def archive_pace():
    import time
    global _ARCHIVE_LAST_REQUEST
    now=time.monotonic()
    if _ARCHIVE_DEADLINE is not None and now+61>_ARCHIVE_DEADLINE:return False
    delay=max(0,16- (now-_ARCHIVE_LAST_REQUEST)) if _ARCHIVE_LAST_REQUEST is not None else 0
    if delay:time.sleep(delay)
    _ARCHIVE_LAST_REQUEST=time.monotonic()
    return True

def archive_parameters(domain,now):
    from datetime import timedelta
    p={'limit':1000}
    if domain=='earnings':p.update({'date.gte':now.date().isoformat(),'date.lte':(now+timedelta(days=42)).date().isoformat()})
    elif domain=='dividends':p.update({'ex_dividend_date.gte':(now-timedelta(days=30)).date().isoformat(),'ex_dividend_date.lte':(now+timedelta(days=42)).date().isoformat(),'sort':'ex_dividend_date.asc'})
    elif domain=='splits':p.update({'execution_date.gte':now.date().isoformat(),'execution_date.lte':(now+timedelta(days=42)).date().isoformat()})
    else:raise ValueError('closed metadata source registry')
    return p

def archive_request(domain,params,key):
    import requests
    if domain not in ARCHIVE_ENDPOINTS:raise ValueError('closed metadata source registry')
    if not archive_pace():return None,b''
    try:
        r=requests.get('https://api.massive.com'+ARCHIVE_ENDPOINTS[domain],
          headers={'Authorization':'Bearer '+key},params=params,allow_redirects=False,timeout=45)
        if len(r.content)>2_000_000:return None,b''
        return r.status_code,r.content if r.status_code==200 else b''
    except requests.RequestException:return None,b''

def archive_projection(domain,status,body,secret,symbols,retrieved_at):
    # Preserve metadata projection, wire SHA and version hash; never credentials,
    # next_url query tokens, EPS/revenue, prices, error bodies or exception text.
    if domain not in ARCHIVE_ENDPOINTS:raise ValueError('unregistered source')
    observed=datetime.fromisoformat(retrieved_at.replace('Z','+00:00'))
    if observed.tzinfo is None:raise ValueError('timezone required')
    base={'domain':domain,'source':'Massive','retrieved_at':retrieved_at,
          'http_status':status,'records':[],'coverage_complete':False,
          'raw_wire_retained':False,'raw_projection_retained':True,
          'missing_status':'UNKNOWN','wire_sha256':None}
    if status!=200:return base
    try:payload=json.loads(body)
    except (ValueError,UnicodeDecodeError):return base
    if not isinstance(payload,dict) or not isinstance(payload.get('results'),list):return base
    for row in payload['results']:
        if not isinstance(row,dict):raise ValueError('source row schema')
        ticker=row.get('ticker')
        if ticker not in symbols:continue
        clean={k:row[k] for k in ARCHIVE_KEYS[domain] if k in row and isinstance(row[k],(str,int,float,bool,type(None)))}
        if any(isinstance(v,float) and not math.isfinite(v) for v in clean.values()):raise ValueError('nonfinite metadata')
        if secret and secret in json.dumps(clean):raise ValueError('secret-bearing projection rejected')
        canonical=json.dumps(clean,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        clean['normalized_record_sha256']=hashlib.sha256(canonical).hexdigest()
        clean['known_no_earlier_than']=retrieved_at
        clean['session_semantics_certified']=False
        base['records'].append(clean)
    base['wire_sha256']=hashlib.sha256(body).hexdigest()
    base['projection_sha256']=hashlib.sha256(json.dumps(base['records'],sort_keys=True,allow_nan=False).encode()).hexdigest()
    base['pagination_pending']=bool(payload.get('next_url'))
    base['missing_status']='PARTIAL_METADATA_OBSERVATION'
    # One bounded bulk page never proves per-symbol no-event or broker coverage.
    return base

def archive_cursor(domain,url):
    from urllib.parse import urlsplit,parse_qs
    if domain not in ARCHIVE_ENDPOINTS:raise ValueError('unregistered source')
    u=urlsplit(url)
    if u.scheme!='https' or u.netloc!='api.massive.com' or u.path!=ARCHIVE_ENDPOINTS[domain] or u.fragment:
        raise ValueError('closed pagination source')
    q=parse_qs(u.query,strict_parsing=True)
    if set(q)-{'cursor','limit','apiKey'} or len(q.get('cursor',[]))!=1:
        raise ValueError('closed pagination parameters')
    cursor=q['cursor'][0]
    if not cursor or len(cursor)>16000:raise ValueError('bounded cursor')
    # Ignore supplied API keys; use existing header authentication only.
    return {'cursor':cursor,'limit':1000}

def archive_collect(domain,params,key,symbols):
    from datetime import timezone
    filters={k:v for k,v in params.items() if k!='cursor'}
    pages=[];records=[];seen=set();pending=False
    for _ in range(10):
        status,body=archive_request(domain,params,key) if key else (None,b'')
        at=datetime.now(timezone.utc).isoformat()
        page=archive_projection(domain,status,body,key,symbols,at)
        records.extend(page['records'])
        pages.append({k:v for k,v in page.items() if k!='records'})
        if status!=200 or not page.get('projection_sha256'):
            pending=True;break
        payload=json.loads(body)
        nxt=payload.get('next_url')
        if not nxt:pending=False;break
        pending=True
        try:new=archive_cursor(domain,nxt)
        except ValueError:pages[-1]['pagination_rejection']='UNKNOWN_UNSAFE_OR_UNSUPPORTED_CURSOR';break
        if key and key in new['cursor']:
            pages[-1]['pagination_rejection']='UNKNOWN_CREDENTIAL_BEARING_CURSOR';break
        if new['cursor'] in seen:
            pages[-1]['pagination_rejection']='UNKNOWN_REPEATED_CURSOR';break
        seen.add(new['cursor']);params=new
    versions={};duplicates=0;seen_hash=set()
    for row in records:
        h=row['normalized_record_sha256']
        duplicates+=h in seen_hash;seen_hash.add(h)
        identity=(row.get('ticker'),row.get('id') or row.get('benzinga_id'))
        if identity[1]:versions.setdefault(identity,set()).add(h)
    date_field={'earnings':'date','dividends':'ex_dividend_date','splits':'execution_date'}[domain]
    low=filters.get(date_field+'.gte');high=filters.get(date_field+'.lte')
    def in_window(row):
        value=row.get(date_field)
        if not isinstance(value,str):return False
        try:datetime.fromisoformat(value)
        except ValueError:return False
        return (not low or value>=low) and (not high or value<=high)
    outside=sum(not in_window(r) for r in records) if low or high else 0
    return {'domain':domain,'source':'Massive','retrieved_at':pages[-1]['retrieved_at'],'requested_filters':filters,'outside_window_records':outside,'requested_window_pass':outside==0,
      'http_status':pages[-1]['http_status'],'records':records,'pages':pages,
      'page_count':len(pages),'listing_exhausted':not pending and pages[-1].get('projection_sha256') is not None,
      'pagination_pending':pending,'coverage_complete':False,
      'missing_status':'PARTIAL_METADATA_OBSERVATION' if records else 'UNKNOWN',
      'raw_wire_retained':False,'raw_projection_retained':True,
      'projection_sha256':hashlib.sha256(json.dumps(records,sort_keys=True,allow_nan=False).encode()).hexdigest(),
      'identical_projection_duplicates':duplicates,'conflicting_event_ids':sum(len(v)>1 for v in versions.values()),
      'wire_hashes':[x['wire_sha256'] for x in pages if x.get('wire_sha256')]}

def run_prospective_archival(work_root,context):
    from datetime import timezone,timedelta
    archive_guard(context)
    import time
    global _ARCHIVE_DEADLINE
    _ARCHIVE_DEADLINE=time.monotonic()+600
    now=datetime.now(timezone.utc)
    key=os.environ.get('MASSIVE_API_KEY') or os.environ.get('TR_MASSIVE_API_KEY')
    snapshots=[]
    for domain in ARCHIVE_ENDPOINTS:
        params=archive_parameters(domain,now)
        snapshots.append(archive_collect(domain,params,key,context['archive_symbols']))
    unavailable=[{'domain':d,'status':'NOT_CONNECTED_UNKNOWN','complete':False} for d in ARCHIVE_DOMAINS if d not in ARCHIVE_ENDPOINTS]
    schema={'version':1,'append_only':True,'observation_fields':['source','domain','symbol/ticker','event_id','retrieved_at','provider_last_updated','expected_date','expected_time','revision/status','availability','available_quantity','borrow_fee','recall_state','wire_sha256','projection_sha256','normalized_record_sha256','collector_revision','job_id','attempt_id','run_id','coverage_complete','missing_status'],
      'retention':'All prior artifacts/readbacks stay immutable. Same event changed projection hash creates a new version, never overwrites.',
      'timestamps':'UTC timezone-aware actual retrieval establishes knowledge. Provider timestamp never backdates archived knowledge.',
      'raw_policy':'Whitelisted provider metadata projection retained; full wire hash retained, raw wire not retained. Projection cannot establish absent-provider-field knowledge.',
      'no_event':'Empty page is UNKNOWN, not certified no earnings.',
      'corporate_action_basis':'Preserve provider amount/currency/ex/pay/declaration/split ratio; adjusted-price/share-basis mapping remains uncertified until source plus broker cash ledger certified.'}
    docs={
      ARCHIVE_FILES[0]:{'mode':'METADATA_ONLY_NO_PRICES','storage':'Existing private Supabase governed job/attempt immutable objects and durable readbacks','new_tables':False,'source_inputs':0,'archival_start_backdating':False},
      ARCHIVE_FILES[1]:schema,
      ARCHIVE_FILES[2]:{'existing_credential_configured':bool(key),'active_endpoint_registry':ARCHIVE_ENDPOINTS,'sources_not_connected':unavailable,'indicative_borrow_is_not_account_specific_locate':True,'FMP':'No configured entitlement established in this collector; not probed or claimed globally unavailable.'},
      ARCHIVE_FILES[3]:{'window_days':42,'dividend_lookback_calendar_days':30,'min_request_gap_seconds':16,'total_source_budget_seconds':600,'documented_filter':'ex_dividend_date range; never unsupported declaration_date query','page_limit':1000,'max_response_bytes':2000000,'max_pages':10,'redirects':False,'pagination':'At most ten pages; same exact HTTPS Massive source path and bounded cursor only, repeated/unsafe cursors fail closed; original wire hashes per page. Pending page marks incomplete; listing exhaustion never proves universe/absence completeness.','retries':'Next scheduled governed job creates new immutable attempt/output; failed history preserved.','knowledge':'Current-as-collected only; never historical reconstruction before first capture.'},
      ARCHIVE_FILES[4]:{'operational_checks':['UTC timestamp','closed endpoint','bounded response','finite metadata','secret rejection','immutable private upload','independent hash/byte readback'],'practical_complete':False,'source_missing_fails_closed':True,'boundary_quality_thresholds':'Proposed separately, not scientific freeze.'},
      ARCHIVE_FILES[5]:{'symbols':context['archive_symbols'],'expected_symbols':112,'required_domains':ARCHIVE_DOMAINS,'complete_practical_symbol_count':0,'coverage_cannot_be_inferred_from_empty_pages':True},
      ARCHIVE_FILES[6]:BOUNDARY_RECOMMENDATION,
      ARCHIVE_FILES[7]:{'future_prices_denied':True,'B5_consumed_denied':True,'protected_validation_denied':True,'boundary_assignments':0,'S5_S6_locked':True,'snapshot_metadata_not_strategy_outcomes':True},
      ARCHIVE_FILES[8]:{'workflow':'.github/workflows/sw11-s4p-archive.yml','timezone':'America/New_York','weekdays':['09:15','15:45','16:15'],'cron_delays':'Actual retrieval time controls; missed/late snapshots do not become historical knowledge.','activation':'Exact certified research head persisted in MWE collector config; dedicated workflow checks ancestor and snapshot authority.','secrets':'Existing Massive/Supabase only in dedicated trusted collector workflow; no credential logs/artifacts.'},
      ARCHIVE_FILES[9]:{'scope':'Synthetic + governed compatibility only; zero real strategy performance','certification':context.get('certification'),'protected_boundaries_pass':True},
      ARCHIVE_FILES[10]:{'status':'BLOCKED_USER','decisions':['Prospectively approve exact S4/S5 boundary recommendation or alternatives.','Connect/certify a zero-cost complete current earnings revision/session feed and broker/account-specific locate/fee/recall/funding evidence; do not weaken practical gates.'],'scientific_ready':False},
      ARCHIVE_FILES[11]:{'capture_started_at':now.isoformat(),'snapshots':snapshots,'unconnected_domains':unavailable},
      ARCHIVE_FILES[12]:{'technical_capture_succeeded':any(x['http_status']==200 for x in snapshots),'all_practical_domains_complete':False,'source_statuses':[{k:x.get(k) for k in ('domain','http_status','retrieved_at','missing_status','pagination_pending')} for x in snapshots],'complete_symbols':0,'MWE':MWE,'job_id':context['job_id'],'attempt_id':context['attempt_id']}}
    out=Path(work_root)/'research_outputs/swing11/s4p';out.mkdir(parents=True,exist_ok=True)
    inventory=[]
    for name,data in docs.items():
        p=out/name;p.write_text(json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+'\n')
        inventory.append({'name':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size_bytes':p.stat().st_size})
    manifest={'MWE':MWE,'authority':ARCHIVE_AUTHORITY,'job_id':context['job_id'],'attempt_id':context['attempt_id'],'run_id':context['github_run_id'],'research_sha':context['research_revision'],'infrastructure_sha':context['infrastructure_revision'],'artifacts':inventory,'self_hash':'external registration only','input_count':0,'new_S4_outcomes_exposed':False,'protected_validation_access':False,'future_price_access':False,'boundary_assignments':0,'paid_fallback':False,'billing_verified_zero':False}
    (out/ARCHIVE_FILES[-1]).write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    paths=[str((out/n).relative_to(work_root)) for n in ARCHIVE_FILES]
    return {'status':'PASS','artifact':paths[0],'output_paths':paths,'output_artifact_metadata':{p:{'logical_name':Path(p).name} for p in paths}}
