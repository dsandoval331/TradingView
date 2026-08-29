-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Milestone Update — 8H-6A-6G-4 Research Readiness Certification COMPLETE
-- Generated: 2026-08-28
--
-- Recommended repo location:
--   sql/migrations/018_pmpd_milestone_8H_6A_6G_4_research_readiness_certified.sql
--
-- VERIFIED EVIDENCE
--   PMPD_112_V1 / 2025:
--     Structural integrity PASS: 112 / 112
--     Structural FAIL: 0
--     Coverage WARN: 8
--     Coverage FAIL: 0
--     Vendor-cache parity PASS: 4 / 4
--     Vendor-cache parity FAIL: 0
--     Universe partitions: 112 / 112
--     Known source-sparse symbols: 8
--     Readiness status: RESEARCH_READY
--     Research ready: true
--
-- SAFETY
--   * Keeps parent phase 8H-6 ACTIVE.
--   * Keeps 8H-7 as next top-level phase.
--   * Marks the 2025 dataset research-ready without prematurely completing 8H-6.
-- ============================================================================

begin;

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
insert into public.project_decisions (
    strategy_id,
    title,
    decision,
    rationale,
    evidence,
    affects_model_version,
    metadata_json
)
select
    pmpd.strategy_id,
    '8H-6A-6G-4 PMPD_112_V1 2025 research readiness certified',
    'PMPD_112_V1 x 2025 is certified RESEARCH_READY for historical-engine use.',
    'The dataset passed full structural integrity, zero coverage failures, reviewed source-sparsity warnings, exact vendor-to-cache parity on sampled forensic/control cases, and full 112-partition universe coverage.',
    'Certification PASS: structural 112/112, structural fail 0, coverage warn/fail 8/0, vendor-cache parity 4/4 with 0 failures, universe 112/112, eight warnings documented as known source-level sparse aggregates, readiness_status=RESEARCH_READY, research_ready=true.',
    'V4',
    jsonb_build_object(
        'milestone_code', '8H-6A-6G-4',
        'milestone_name', 'Research Readiness Certification',
        'milestone_status', 'COMPLETE',
        'universe_code', 'PMPD_112_V1',
        'year', 2025,
        'structural_pass', 112,
        'structural_fail', 0,
        'coverage_warn', 8,
        'coverage_fail', 0,
        'vendor_cache_parity_cases', 4,
        'vendor_cache_parity_failures', 0,
        'universe_partitions_complete', 112,
        'universe_partitions_expected', 112,
        'known_source_sparse_symbols', 8,
        'readiness_status', 'RESEARCH_READY',
        'research_ready', true,
        'completed_at', now()
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6G-4 PMPD_112_V1 2025 research readiness certified'
      and d.status = 'active'
);

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
update public.project_state ps
set
    active_phase_code = '8H-6',
    active_phase_name = 'Historical Engine & Ingestion',
    next_phase_code = '8H-7',
    next_phase_name = 'Small-Sample Parity Validation',
    historical_dataset_status = 'PMPD_112_V1_2025_RESEARCH_READY',
    last_decision = '8H-6A-6G-4 passed: PMPD_112_V1 x 2025 is certified RESEARCH_READY. Review remaining 8H-6 closeout gates before advancing to 8H-7.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            '8H-6A-6G-4_status', 'COMPLETE',
            '8H-6A-6G-4_validation', 'PASS',
            'historical_engine_status', '2025_DATASET_RESEARCH_READY',
            'pmpd_112_2025_research_ready', true,
            'pmpd_112_2025_readiness_status', 'RESEARCH_READY',
            'pmpd_112_2025_structural_pass', 112,
            'pmpd_112_2025_coverage_fail', 0,
            'pmpd_112_2025_vendor_parity_pass', '4/4',
            '8H-6A_next', '8H-6A-6H'
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

commit;

-- Verification
select
    s.strategy_code,
    ps.active_phase_code,
    ps.next_phase_code,
    ps.historical_dataset_status,
    ps.metadata_json ->> '8H-6A-6G-4_status' as milestone_status,
    ps.metadata_json ->> 'historical_engine_status' as historical_engine_status,
    ps.metadata_json ->> 'pmpd_112_2025_research_ready' as research_ready,
    ps.metadata_json ->> 'pmpd_112_2025_readiness_status' as readiness_status,
    ps.metadata_json ->> '8H-6A_next' as next_implementation_step,
    ps.last_decision
from public.project_state ps
join public.strategies s on s.strategy_id = ps.strategy_id
where s.strategy_code = 'PMPD';
