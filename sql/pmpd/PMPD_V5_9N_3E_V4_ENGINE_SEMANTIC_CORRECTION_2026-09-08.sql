-- PM+PD V5 9N-3E — Reconstructed V4 Engine Semantic Correction
-- Strategy: 84fb30c1-7600-49bf-a024-022f0500492e
-- Roadmap: PMPD-V5-RM-2.0
-- Phase remains 9N. V4 and V5 remain frozen. TradingView parity is NOT yet validated.

update public.project_state
set
    last_decision =
        '9N-3E active: reconstructed external V4 parity engine corrected to recovered frozen Pine semantics. Key corrections: Pine/Wilder RMA ATR on regular-session 5m stream; confTimeClose canonical signal timestamp; exact ARM->CONFIRM->SCORE state machine; exact V4 profile/priority/trade-type/TQS/confidence matrix; raw-valid signals preserved separately from production-alert gating; signal candle excluded; first-outcome freezes while MFE/MAE continue through same RTH session. Static semantic certification passes locally, but TradingView parity remains unvalidated. Next: run 9N-3E semantic certification in local repo, then build machine-readable TradingView CSV parity exporter and compare frozen recapture cases before 2026 H2H.',
    metadata_json =
        coalesce(metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            'v5_current_substep', '9N-3E-V4-ENGINE-SEMANTIC-CORRECTION',
            'v5_9n_3e_status', 'ACTIVE_LOCAL_CERT_PENDING',
            'v5_9n_v4_engine_version', 'v4_parity_engine_v2',
            'v5_9n_v4_source_sha256', '79b9d80f0ec2c254bd69607ff626c2007ae7e617018d984f083ba2a25e7ba681',
            'v5_9n_v4_atr_semantics', 'PINE_TA_ATR_RMA_REGULAR_5M_COMPLETED_BAR',
            'v5_9n_v4_signal_timestamp_semantics', 'CONF_TIME_CLOSE_COMPLETED_5M',
            'v5_9n_v4_raw_valid_vs_production_separated', true,
            'v5_9n_v4_full_session_mfe_mae', true,
            'v5_9n_tradingview_parity_validated', false,
            'v5_9n_v4_modified', false,
            'v5_9n_v5_modified', false,
            'v5_production_rule_authorized', false
        ),
    updated_at = now()
where strategy_id = '84fb30c1-7600-49bf-a024-022f0500492e';
