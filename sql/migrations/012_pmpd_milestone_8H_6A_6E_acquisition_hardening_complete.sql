-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Milestone Update — 8H-6A-6E Acquisition Hardening COMPLETE
-- Generated: 2026-08-28
--
-- Recommended repo location:
--   sql/migrations/012_pmpd_milestone_8H_6A_6E_acquisition_hardening_complete.sql
--
-- VERIFIED:
--   Deterministic:
--     all-complete / no API-key prompt = PASS
--     mixed batch / prompt once = PASS
--     failure isolation / continue batch = PASS
--   Live production manifest/cache:
--     AAPL 2025 = SKIPPED_COMPLETE (188072)
--     MSFT 2025 = SKIPPED_COMPLETE (156075)
--     NVDA 2025 = SKIPPED_COMPLETE (237805)
--     downloaded=0, skipped=3, failed=0
--     no API-key prompt = PASS
--
-- Keeps 8H-6 ACTIVE and 8H-7 next.
-- ============================================================================

begin;

with pmpd as (
    select strategy_id from public.strategies where strategy_code = 'PMPD'
)
insert into public.project_decisions (
    strategy_id, title, decision, rationale, evidence,
    affects_model_version, metadata_json
)
select
    strategy_id,
    '8H-6A-6E Acquisition Hardening completed',
    'Acquisition hardening passed deterministic and live production-cache validation, including lazy credential prompting and per-partition failure isolation.',
    'The batch layer is now safer for larger acquisition runs: an all-complete batch requires no Massive credential prompt, mixed batches prompt once, and an isolated partition failure does not prevent subsequent partitions from running.',
    'Deterministic tests PASS: all-complete/no-prompt; mixed/prompt-once; failure-isolation/continue. Live test PASS: AAPL 2025 188072, MSFT 2025 156075, NVDA 2025 237805 all SKIPPED_COMPLETE; downloaded=0 skipped=3 failed=0; no API-key prompt.',
    'V4',
    jsonb_build_object(
        'milestone_code','8H-6A-6E',
        'milestone_name','Acquisition Hardening',
        'milestone_status','COMPLETE',
        'deterministic_validation','PASS',
        'live_no_prompt_validation','PASS',
        'failure_isolation','PASS',
        'mixed_batch_prompt_once','PASS',
        'live_downloaded',0,
        'live_skipped',3,
        'live_failed',0,
        'completed_at',now()
    )
from pmpd
where not exists (
    select 1 from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6E Acquisition Hardening completed'
      and d.status = 'active'
);

with pmpd as (
    select strategy_id from public.strategies where strategy_code = 'PMPD'
)
update public.project_state ps
set
    active_phase_code='8H-6',
    active_phase_name='Historical Engine & Ingestion',
    next_phase_code='8H-7',
    next_phase_name='Small-Sample Parity Validation',
    last_decision='8H-6A-6E Acquisition Hardening passed; proceed to controlled acquisition scaling before full-universe bootstrap.',
    metadata_json=coalesce(ps.metadata_json,'{}'::jsonb) || jsonb_build_object(
        '8H-6A-6E_status','COMPLETE',
        '8H-6A-6E_validation','PASS',
        'historical_engine_status','ACQUISITION_HARDENED',
        '8H-6A_next','8H-6A-6F'
    ),
    updated_at=now()
from pmpd
where ps.strategy_id=pmpd.strategy_id;

commit;

select
    pd.title, pd.status, pd.decision_date
from public.project_decisions pd
join public.strategies s on s.strategy_id=pd.strategy_id
where s.strategy_code='PMPD'
  and pd.title='8H-6A-6E Acquisition Hardening completed';

select
    s.strategy_code,
    ps.active_phase_code,
    ps.next_phase_code,
    ps.metadata_json ->> '8H-6A-6E_status' as milestone_status,
    ps.metadata_json ->> 'historical_engine_status' as historical_engine_status,
    ps.metadata_json ->> '8H-6A_next' as next_implementation_step,
    ps.last_decision
from public.project_state ps
join public.strategies s on s.strategy_id=ps.strategy_id
where s.strategy_code='PMPD';
