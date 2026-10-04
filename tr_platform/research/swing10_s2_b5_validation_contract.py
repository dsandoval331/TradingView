"""Deterministic prospective B5 base+supplement contract; outcome-free constants."""
from tr_platform.research.swing10_s2_b5_preparation import CASES, KEYS, FILES, INPUT_SHA, INPUT_BYTES, INPUT_ID, centered_rank, normalize_state, validate_cases

PROTOCOL='SW10_S2_B5_VALIDATION_PROTOCOL_V1'
BASE_DECISION='880644f4-afcc-49d9-8641-27cc0bf5bcfd'
SUPPLEMENT_DECISION='80b02259-dd45-4b45-b496-66a36ff303a4'
GRID=(1,2,3,5,7,10)
MATERIAL=.20
FDR=.05
PANEL_COLUMNS=('symbol','trade_date','open','high','low','close','volume')
SNAPSHOTS={
 'SW10_S2_B5_VALIDATION_PROTOCOL_V1.persisted.json':'90705b2fdaefa9b7ffb9a6a2fc410135b9a10d1756a401d7de51ab253b544955',
 'SW10_S2_B5_VALIDATION_PROTOCOL_V1_SUPPLEMENT_1.persisted.json':'0e47ac9636305f17f80f2179ba6cb8ed5054e052f42f0351f531277ba2c53c83'}
COMMON=('family','horizon_days','frozen_direction','limited_temporal_capacity')
SCHEMAS={
FILES[0]:COMMON+('testable','testability_reason','primary_quantity_type','eligible_dates','eligible_symbol_dates','primary_estimate','date_effect_mean','date_effect_median','date_effect_sample_sd','standardized_effect','positive_date_share','negative_date_share','hypothesized_date_share','hac_lag','hac_se','hac_t','ci95_low','ci95_high','p_raw','p_bh','direction_pass','material_pass','fdr_pass','same_direction_blocks','max_absolute_block_share','temporal_direction_pass','temporal_concentration_pass','symbol_diagnostics_available','top1_absolute_share','top5_absolute_share','top10_absolute_share','contribution_hhi','removed_top5_symbols','leave_top5_estimate','leave_top5_sign_reversal','symbol_sign_pass','registered_adjacent_horizons','adjacency_applicable','adjacent_coherence_pass','robustness_pass','disposition','failed_gates'),
FILES[1]:COMMON+('trade_date','temporal_block','eligible_symbols','date_effect','effect_type','standardized_market_state','stage1_intercept','low_count','high_count','low_mean_return','high_mean_return','overlap_count'),
FILES[2]:COMMON+('block','start','end','eligible_dates','primary_estimate','date_effect_mean','date_effect_median','primary_sign','required_direction_pass','absolute_block_effect','absolute_block_share','diagnostic_available','unavailable_reason'),
FILES[3]:COMMON+('symbol','eligible_symbol_dates','contribution_rank','additive_primary_contribution','absolute_contribution_share','removed_leave_top5'),
FILES[4]:COMMON+('testable','direction_pass','material_pass','fdr_pass','temporal_direction_pass','temporal_concentration_pass','symbol_sign_pass','adjacent_coherence_pass','robustness_pass','disposition','failed_gates'),
FILES[5]:COMMON+('semantic_data_integrity_pass','predictor_future_invariance','input_sha256','input_bytes','parent_input_id','strict_endpoint_before','eligibility_dates','blocks_fixed_before_outcomes','raw_p_available','bh_unavailable_bookkeeping','protected_data_access','earnings_used','reason')}

def registered_neighbors(family,horizon):
    i=GRID.index(horizon)
    return tuple(GRID[j] for j in (i-1,i+1) if 0<=j<len(GRID) and (family,GRID[j]) in KEYS)

def adjacency(family,horizon,estimates,estimate):
    ns=registered_neighbors(family,horizon)
    return bool(not ns or any(estimates.get((family,h),0)*estimate>0 for h in ns))

def direction_pass(estimate,direction):
    return bool(estimate>0 if direction=='POSITIVE' else estimate<0)

def disposition(testable,directional,material,fdr,robust):
    if not testable:return 'NOT_TESTABLE'
    if not (directional and material and fdr):return 'INDEPENDENT_VALIDATION_FAILED'
    return 'INDEPENDENT_VALIDATION_SUPPORTED' if robust else 'PARTIAL_VALIDATION_EVIDENCE'
