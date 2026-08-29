-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Migration 006 — Populate PM+PD Master Research Factor Roadmap
-- Generated: 2026-08-28
--
-- PURPOSE
--   1) Seed the authoritative PM+PD research-factor roadmap.
--   2) Preserve the shared multi-strategy research_factors architecture.
--   3) Record roadmap governance in project_decisions / project_state.
--   4) Validate family coverage, factor-code uniqueness, and total row count.
--
-- SAFETY
--   * Existing research_factors table is currently empty.
--   * Uses ON CONFLICT(strategy_id, factor_code) DO UPDATE for idempotency.
--   * Does not alter Second1M research tables.
--   * Does not change current active phase (8H-6 remains active).
-- ============================================================================

begin;

-- ============================================================================
-- 1. SEED PM+PD MASTER RESEARCH ROADMAP
--    Roadmap version: PMPD-RM-1.0
-- ============================================================================

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
),
factors (
    factor_code,
    family,
    factor_name,
    description,
    priority,
    status,
    timing_type,
    data_type,
    data_available,
    implementation_status,
    finding,
    production_status
) as (
    values

    -- ------------------------------------------------------------------------
    -- FAMILY A — SETUP / BREAKOUT QUALITY
    -- ------------------------------------------------------------------------
    ('A01','A_SETUP_QUALITY','Breakout penetration beyond required PM/PD levels',
     'ATR-normalized penetration beyond the final required PM/PD breakout level.',
     1,'validated','signal_time','numeric',true,'existing_v4',
     'Core frozen V4 signal-strength component; expanded-universe validation remains required.',
     'baseline_component'),

    ('A02','A_SETUP_QUALITY','Breakout candle body-to-range ratio',
     'Directional confirmation-candle body divided by full candle range.',
     1,'validated','signal_time','numeric',true,'existing_v4',
     'Core frozen V4 signal-strength component; expanded-universe validation remains required.',
     'baseline_component'),

    ('A03','A_SETUP_QUALITY','Strong-close / close-location percentage',
     'Directional close location within the confirmation candle range.',
     1,'validated','signal_time','numeric',true,'existing_v4',
     'Core frozen V4 signal-strength component; expanded-universe validation remains required.',
     'baseline_component'),

    ('A04','A_SETUP_QUALITY','Breakout candle range vs ATR',
     'Confirmation-candle total range normalized by ATR.',
     1,'validated','signal_time','numeric',true,'existing_v4',
     'Core frozen V4 signal-strength component; expanded-universe validation remains required.',
     'baseline_component'),

    ('A05','A_SETUP_QUALITY','Directional candle quality',
     'Whether confirmation candle direction agrees with breakout direction.',
     1,'validated','signal_time','boolean',true,'existing_v4',
     'Used in frozen V4 confirmation logic.',
     'baseline_component'),

    ('A06','A_SETUP_QUALITY','Breakout speed / velocity',
     'Bars from arm event to successful confirmation.',
     1,'validated','signal_time','numeric',true,'existing_v4',
     'Confirmation speed is part of frozen V4 scoring and profile logic.',
     'baseline_component'),

    ('A07','A_SETUP_QUALITY','Pre-signal 1-minute velocity',
     'Directional price velocity immediately before signal on 1-minute data.',
     1,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('A08','A_SETUP_QUALITY','Pre-signal 2-minute velocity',
     'Directional price velocity immediately before signal on 2-minute aggregation.',
     1,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('A09','A_SETUP_QUALITY','Pre-signal 3-minute velocity',
     'Directional price velocity immediately before signal on 3-minute aggregation.',
     1,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('A10','A_SETUP_QUALITY','Pre-signal acceleration / deceleration',
     'Change in directional velocity approaching the breakout.',
     1,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('A11','A_SETUP_QUALITY','Distance between required PM/PD breakout levels',
     'Absolute price separation between the two required breakout levels.',
     1,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('A12','A_SETUP_QUALITY','ATR-normalized distance between required levels',
     'Required-level separation normalized by ATR.',
     1,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('A13','A_SETUP_QUALITY','Which required level was crossed first',
     'Whether PM or PD level was the first of the two required levels to be crossed.',
     1,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('A14','A_SETUP_QUALITY','Time between first-level and second-level break',
     'Elapsed time between crossing the first and final required level.',
     1,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('A15','A_SETUP_QUALITY','Distance traveled before final breakout / pre-signal extension',
     'Directional extension before the final breakout signal confirms.',
     1,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('A16','A_SETUP_QUALITY','Volume at breakout',
     'Raw confirmation-candle volume.',
     1,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('A17','A_SETUP_QUALITY','Relative-volume / volume expansion',
     'Breakout volume relative to an appropriate historical/intraday baseline.',
     1,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('A18','A_SETUP_QUALITY','Existing PM+PD Strength Score validation',
     'Revalidate the frozen V4 composite score on the expanded universe.',
     1,'research_only','signal_time','composite',true,'existing_v4',
     'Historically useful; larger 112-stock validation remains pending.',
     'baseline_research'),

    ('A19','A_SETUP_QUALITY','Existing Grade validation',
     'Validate exact Grade and Grade-family performance on expanded data.',
     1,'research_only','signal_time','categorical',true,'existing_v4',
     'Grade alone was not sufficient as a quality ranking; Grade x Profile interaction matters.',
     'baseline_research'),

    ('A20','A_SETUP_QUALITY','Existing V4 Profile validation',
     'Validate frozen V4 profile categories on expanded data.',
     1,'research_only','signal_time','categorical',true,'existing_v4',
     'V4 materially reduced Unclassified population and created distinct behavioral groups in the 16-stock study.',
     'baseline_research'),

    ('A21','A_SETUP_QUALITY','Grade x V4 Profile validation',
     'Validate the frozen Grade-family x Profile production matrix.',
     1,'research_only','signal_time','interaction',true,'existing_v4',
     'Core production lookup uses Grade x Profile; expanded-universe validation pending.',
     'baseline_research'),

    ('A22','A_SETUP_QUALITY','PRIME vs CONDITIONAL vs suppressed populations',
     'Compare frozen V4 production-priority populations.',
     1,'testing','signal_time','categorical',true,'existing_v4',
     'Frozen forward validation is currently testing whether production priorities generalize.',
     'forward_validation'),

    ('A23','A_SETUP_QUALITY','EXPANSION vs SCALP behavior',
     'Compare continuation behavior and path characteristics by frozen trade type.',
     1,'testing','signal_time','categorical',true,'existing_v4',
     'Historical data suggested different MFE/MAE behavior; forward validation ongoing.',
     'forward_validation'),

    -- ------------------------------------------------------------------------
    -- FAMILY B — STOCK CONTEXT
    -- ------------------------------------------------------------------------
    ('B01','B_STOCK_CONTEXT','Previous-day stock candle direction',
     'Bullish/bearish/neutral direction of the previous RTH daily candle.',
     2,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('B02','B_STOCK_CONTEXT','Previous-day stock return magnitude',
     'Previous RTH close-to-close or open-to-close return magnitude.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B03','B_STOCK_CONTEXT','Previous-day candle body strength',
     'Previous-day body size relative to full daily range.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B04','B_STOCK_CONTEXT','Previous-day candle range',
     'Absolute or percentage previous-day RTH range.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B05','B_STOCK_CONTEXT','Previous-day range normalized by ATR',
     'Previous-day range normalized by stock ATR.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B06','B_STOCK_CONTEXT','Previous-day close location',
     'Previous-day close location within daily range.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B07','B_STOCK_CONTEXT','Previous-day candle strength composite',
     'Composite representation of previous-day direction, body, range, and close location.',
     2,'not_tested','signal_time','composite',false,'planned',null,null),

    ('B08','B_STOCK_CONTEXT','Stock 3-day trend',
     'Three-session stock trend/return context.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B09','B_STOCK_CONTEXT','Stock 5-day trend',
     'Five-session stock trend/return context.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B10','B_STOCK_CONTEXT','Stock 10-day trend',
     'Ten-session stock trend/return context.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B11','B_STOCK_CONTEXT','Stock 20-day trend',
     'Twenty-session stock trend/return context.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B12','B_STOCK_CONTEXT','Multi-day trend strength / slope',
     'Slope or normalized rate of change across multi-day windows.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B13','B_STOCK_CONTEXT','HH/HL vs LH/LL structure',
     'Higher-high/higher-low versus lower-high/lower-low structural regime.',
     2,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('B14','B_STOCK_CONTEXT','Higher-timeframe moving-average position / slope',
     'Stock position and slope relative to selected higher-timeframe moving averages.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B15','B_STOCK_CONTEXT','Weekly symbol bias',
     'Versioned bullish/neutral/bearish higher-timeframe weekly context.',
     2,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('B16','B_STOCK_CONTEXT','Weekly-bias strength',
     'Numeric confidence/strength of weekly symbol bias.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B17','B_STOCK_CONTEXT','Signal x weekly-bias alignment',
     'Whether signal direction aligns with, opposes, or is neutral to weekly stock bias.',
     2,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('B18','B_STOCK_CONTEXT','Gap direction',
     'Direction of RTH open relative to previous RTH close.',
     2,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('B19','B_STOCK_CONTEXT','Gap magnitude',
     'Magnitude of opening gap relative to previous close/ATR.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B20','B_STOCK_CONTEXT','Gap alignment with breakout',
     'Whether gap direction aligns with breakout direction.',
     2,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('B21','B_STOCK_CONTEXT','Premarket direction / trend',
     'Directional trend of same-day premarket price action.',
     2,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('B22','B_STOCK_CONTEXT','Premarket move magnitude',
     'Magnitude of same-day premarket move.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B23','B_STOCK_CONTEXT','Premarket range',
     'Same-day premarket high-low range.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B24','B_STOCK_CONTEXT','Premarket position relative to previous-day levels',
     'Premarket location relative to prior-day range and PM/PD breakout structure.',
     2,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('B25','B_STOCK_CONTEXT','Distance from VWAP at signal',
     'Signal reference-price distance from RTH VWAP.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B26','B_STOCK_CONTEXT','VWAP slope at signal',
     'Directional slope of RTH VWAP at signal time.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B27','B_STOCK_CONTEXT','Signal direction vs VWAP side',
     'Whether signal occurs on the directionally favorable or unfavorable VWAP side.',
     2,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('B28','B_STOCK_CONTEXT','ATR-normalized extension from VWAP',
     'Signal distance from RTH VWAP normalized by ATR.',
     2,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('B29','B_STOCK_CONTEXT','ATR / volatility regime',
     'Stock-level volatility regime defined from ATR or realized volatility.',
     2,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('B30','B_STOCK_CONTEXT','Normal intraday volatility regime',
     'Intraday realized-volatility regime relative to the symbol normal.',
     2,'not_tested','signal_time','categorical',false,'planned',null,null),

    -- ------------------------------------------------------------------------
    -- FAMILY C — MARKET CONTEXT
    -- ------------------------------------------------------------------------
    ('C01','C_MARKET_CONTEXT','Previous-day SPY direction / return',
     'Previous-session SPY direction and magnitude.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C02','C_MARKET_CONTEXT','Previous-day QQQ direction / return',
     'Previous-session QQQ direction and magnitude.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C03','C_MARKET_CONTEXT','Previous-day DIA direction / return',
     'Previous-session DIA direction and magnitude.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C04','C_MARKET_CONTEXT','Previous-day 3-index agreement',
     'Agreement/disagreement among SPY, QQQ, and DIA previous-session direction.',
     3,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('C05','C_MARKET_CONTEXT','Previous-day Bullish/Bearish/Mixed regime',
     'Versioned previous-day market-regime classification.',
     3,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('C06','C_MARKET_CONTEXT','SPY/QQQ/DIA 3-day trends',
     'Three-session directional trend of broad-market proxies.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C07','C_MARKET_CONTEXT','Aggregate 3-day market trend',
     'Composite 3-day broad-market trend.',
     3,'not_tested','signal_time','composite',false,'planned',null,null),

    ('C08','C_MARKET_CONTEXT','SPY/QQQ/DIA 5-day trends',
     'Five-session directional trend of broad-market proxies.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C09','C_MARKET_CONTEXT','SPY/QQQ/DIA 10-day trends',
     'Ten-session directional trend of broad-market proxies.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C10','C_MARKET_CONTEXT','SPY/QQQ/DIA 20-day trends',
     'Twenty-session directional trend of broad-market proxies.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C11','C_MARKET_CONTEXT','Multi-day market trend strength',
     'Strength/slope of multi-day broad-market trend.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C12','C_MARKET_CONTEXT','Current-day SPY direction at signal',
     'SPY current-session return/direction measured at signal time.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C13','C_MARKET_CONTEXT','Current-day QQQ direction at signal',
     'QQQ current-session return/direction measured at signal time.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C14','C_MARKET_CONTEXT','Current-day DIA direction at signal',
     'DIA current-session return/direction measured at signal time.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C15','C_MARKET_CONTEXT','Current-day 3-index agreement',
     'Current-session directional agreement among SPY, QQQ, and DIA.',
     3,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('C16','C_MARKET_CONTEXT','Current market bias',
     'Versioned bullish/mixed/bearish current-session market-bias classification.',
     3,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('C17','C_MARKET_CONTEXT','Signal x market-bias alignment',
     'Whether PM+PD signal direction aligns with current market bias.',
     3,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('C18','C_MARKET_CONTEXT','Current market move magnitude',
     'Magnitude of current-session broad-market move at signal time.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C19','C_MARKET_CONTEXT','Market velocity into signal',
     'Short-term broad-market price velocity approaching signal time.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C20','C_MARKET_CONTEXT','Market acceleration / deceleration',
     'Change in broad-market velocity approaching signal time.',
     3,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('C21','C_MARKET_CONTEXT','Broad-market volatility regime',
     'Broad-market realized-volatility regime at signal time.',
     3,'not_tested','signal_time','categorical',false,'planned',null,null),

    -- ------------------------------------------------------------------------
    -- FAMILY D — RELATIVE / ALIGNMENT
    -- ------------------------------------------------------------------------
    ('D01','D_RELATIVE_ALIGNMENT','Signal vs previous-day market regime',
     'Signal direction aligned/opposed/mixed versus previous-day market regime.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D02','D_RELATIVE_ALIGNMENT','Signal vs current market regime',
     'Signal direction aligned/opposed/mixed versus current market regime.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D03','D_RELATIVE_ALIGNMENT','Signal vs previous-day stock direction',
     'Signal alignment with the stock previous-session direction.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D04','D_RELATIVE_ALIGNMENT','Signal vs multi-day stock trend',
     'Signal alignment with multi-day stock trend.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D05','D_RELATIVE_ALIGNMENT','Signal vs weekly stock bias',
     'Signal alignment with versioned weekly stock bias.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D06','D_RELATIVE_ALIGNMENT','Stock trend vs market trend alignment',
     'Stock higher-timeframe trend alignment versus broad-market trend.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D07','D_RELATIVE_ALIGNMENT','Stock vs SPY relative strength / weakness',
     'Stock return/velocity relative to SPY.',
     4,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('D08','D_RELATIVE_ALIGNMENT','Stock vs QQQ relative strength / weakness',
     'Stock return/velocity relative to QQQ.',
     4,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('D09','D_RELATIVE_ALIGNMENT','Relative strength / weakness persistence',
     'Persistence of relative strength or weakness before signal.',
     4,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('D10','D_RELATIVE_ALIGNMENT','Sector direction at signal',
     'Sector proxy return/direction at signal time.',
     4,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('D11','D_RELATIVE_ALIGNMENT','Stock vs sector relative strength',
     'Stock strength/weakness relative to its sector proxy.',
     4,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('D12','D_RELATIVE_ALIGNMENT','Stock x sector alignment',
     'Directional alignment between stock and sector.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D13','D_RELATIVE_ALIGNMENT','Sector x market alignment',
     'Directional alignment between sector and broad market.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D14','D_RELATIVE_ALIGNMENT','Stock + sector + market three-way alignment',
     'Three-way directional alignment among stock, sector, and market.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D15','D_RELATIVE_ALIGNMENT','Gap + stock trend + signal alignment',
     'Interaction between opening gap, higher-timeframe stock trend, and signal direction.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D16','D_RELATIVE_ALIGNMENT','Previous-day stock + previous-day market alignment',
     'Joint previous-session stock/market directional context.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D17','D_RELATIVE_ALIGNMENT','Setup strength + market regime',
     'Interaction between setup quality and market regime.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D18','D_RELATIVE_ALIGNMENT','Setup strength + stock trend',
     'Interaction between setup quality and stock higher-timeframe trend.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D19','D_RELATIVE_ALIGNMENT','Setup strength + relative strength',
     'Interaction between setup quality and stock relative strength.',
     4,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('D20','D_RELATIVE_ALIGNMENT','Pre-signal context vs subsequent warning probability',
     'Relationship between entry context and later deterioration/warning probability.',
     4,'not_tested','mixed','interaction',false,'planned',null,null),

    -- ------------------------------------------------------------------------
    -- FAMILY E — TRADE HEALTH / WARNING RESEARCH
    -- ------------------------------------------------------------------------
    ('E01','E_TRADE_HEALTH','Favorable separation after signal',
     'Early favorable excursion achieved after the confirmed signal.',
     5,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('E02','E_TRADE_HEALTH','Time to first favorable progress',
     'Elapsed time until first meaningful favorable excursion.',
     5,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('E03','E_TRADE_HEALTH','Time without new favorable extreme',
     'Duration since last new favorable excursion/extreme.',
     5,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('E04','E_TRADE_HEALTH','MFE trajectory',
     'Evolution of maximum favorable excursion through time.',
     5,'not_tested','post_signal','trajectory',false,'planned',null,null),

    ('E05','E_TRADE_HEALTH','MAE trajectory',
     'Evolution of maximum adverse excursion through time.',
     5,'not_tested','post_signal','trajectory',false,'planned',null,null),

    ('E06','E_TRADE_HEALTH','MFE/MAE relationship through time',
     'Joint path of favorable and adverse excursion after entry.',
     5,'not_tested','post_signal','trajectory',false,'planned',null,null),

    ('E07','E_TRADE_HEALTH','Confirmation-candle retracement',
     'Retracement relative to the confirmed signal candle structure.',
     5,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('E08','E_TRADE_HEALTH','Post-breakout impulse retracement',
     'Retracement of the post-breakout directional impulse.',
     5,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('E09','E_TRADE_HEALTH','Fib 23.6% retracement',
     'Post-signal event indicating a 23.6% retracement of the selected impulse.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E10','E_TRADE_HEALTH','Fib 38.2% retracement',
     'Post-signal event indicating a 38.2% retracement of the selected impulse.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E11','E_TRADE_HEALTH','Fib 50% retracement',
     'Post-signal event indicating a 50% retracement of the selected impulse.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E12','E_TRADE_HEALTH','Fib 61.8% retracement',
     'Post-signal event indicating a 61.8% retracement of the selected impulse.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E13','E_TRADE_HEALTH','Fib 78.6% retracement',
     'Post-signal event indicating a 78.6% retracement of the selected impulse.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E14','E_TRADE_HEALTH','PM/PD breakout-level loss',
     'Loss of the breakout structure after signal.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E15','E_TRADE_HEALTH','Loss of one required breakout level',
     'One of the two required PM/PD levels is lost after signal.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E16','E_TRADE_HEALTH','Loss of both required breakout levels',
     'Both required breakout levels are lost after signal.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E17','E_TRADE_HEALTH','Close back inside breakout structure',
     'Completed close returns inside the pre-breakout structure.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E18','E_TRADE_HEALTH','Breakout level reclaim after failure',
     'Previously lost breakout structure is subsequently reclaimed.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E19','E_TRADE_HEALTH','VWAP loss against trade',
     'Price moves to the unfavorable side of RTH VWAP after signal.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E20','E_TRADE_HEALTH','VWAP reclaim',
     'Price returns to the favorable side of RTH VWAP after a loss.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E21','E_TRADE_HEALTH','VWAP lost/not-reclaimed state',
     'Persistent unfavorable VWAP state after signal.',
     5,'not_tested','post_signal','state',false,'planned',null,null),

    ('E22','E_TRADE_HEALTH','Consecutive adverse candles',
     'Count/streak of candles moving against the trade after signal.',
     5,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('E23','E_TRADE_HEALTH','Momentum deterioration',
     'Post-signal deterioration in directional momentum.',
     5,'not_tested','post_signal','state',false,'planned',null,null),

    ('E24','E_TRADE_HEALTH','Speed of deterioration',
     'Rate at which adverse structure develops after signal.',
     5,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('E25','E_TRADE_HEALTH','Warning persistence / duration',
     'Duration for which a warning condition remains active.',
     5,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('E26','E_TRADE_HEALTH','Recovery after warning',
     'Whether a deteriorating trade subsequently recovers structurally or reaches favorable targets.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E27','E_TRADE_HEALTH','MAE progression milestones',
     'Adverse-excursion milestone progression after signal.',
     5,'not_tested','post_signal','event',false,'planned',null,null),

    ('E28','E_TRADE_HEALTH','Profile-aware deterioration',
     'Warning/deterioration behavior conditioned on frozen V4 profile.',
     5,'not_tested','post_signal','interaction',false,'planned',null,null),

    ('E29','E_TRADE_HEALTH','PRIME vs CONDITIONAL deterioration',
     'Compare deterioration/recovery behavior by production priority.',
     5,'not_tested','post_signal','interaction',false,'planned',null,null),

    ('E30','E_TRADE_HEALTH','EXPANSION vs SCALP deterioration',
     'Compare deterioration/recovery behavior by trade type.',
     5,'not_tested','post_signal','interaction',false,'planned',null,null),

    ('E31','E_TRADE_HEALTH','Candidate W1 severity',
     'Discover and validate evidence-based mild deterioration state.',
     5,'not_tested','post_signal','state',false,'planned',null,null),

    ('E32','E_TRADE_HEALTH','Candidate W2 severity',
     'Discover and validate evidence-based moderate deterioration state.',
     5,'not_tested','post_signal','state',false,'planned',null,null),

    ('E33','E_TRADE_HEALTH','Candidate W3 severity',
     'Discover and validate evidence-based severe deterioration state.',
     5,'not_tested','post_signal','state',false,'planned',null,null),

    ('E34','E_TRADE_HEALTH','Probability of eventual +0.50% success after warning',
     'Conditional favorable-first probability after each warning state.',
     5,'not_tested','post_signal','outcome',false,'planned',null,null),

    ('E35','E_TRADE_HEALTH','False-warning / recovery rate',
     'Frequency with which warning states recover and ultimately resolve favorably.',
     5,'not_tested','post_signal','outcome',false,'planned',null,null),

    -- ------------------------------------------------------------------------
    -- FAMILY F — TIME / EXECUTION
    -- ------------------------------------------------------------------------
    ('F01','F_TIME_EXECUTION','Time-of-day signal performance',
     'Performance by signal time bucket/minutes since RTH open.',
     6,'ready','signal_time','categorical',true,'research_build_ready',
     'Dedicated Time-of-Day Research build exists; pooled large-sample study not yet completed.',
     'research_ready'),

    ('F02','F_TIME_EXECUTION','Minutes since RTH open',
     'Continuous minutes elapsed since 09:30 ET at signal.',
     6,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('F03','F_TIME_EXECUTION','Early vs middle vs late RTH',
     'Coarse session-time buckets for signal performance.',
     6,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('F04','F_TIME_EXECUTION','Time x direction',
     'Interaction between time-of-day and bull/bear signal direction.',
     6,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('F05','F_TIME_EXECUTION','Time x PRIME/CONDITIONAL',
     'Interaction between time-of-day and production priority.',
     6,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('F06','F_TIME_EXECUTION','Time x EXPANSION/SCALP',
     'Interaction between time-of-day and trade type.',
     6,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('F07','F_TIME_EXECUTION','Time x market regime',
     'Interaction between signal time and market regime.',
     6,'not_tested','signal_time','interaction',false,'planned',null,null),

    ('F08','F_TIME_EXECUTION','Day of week',
     'Signal performance by weekday.',
     6,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('F09','F_TIME_EXECUTION','Month / seasonality',
     'Signal performance by month/season.',
     6,'not_tested','signal_time','categorical',false,'planned',null,null),

    ('F10','F_TIME_EXECUTION','5-minute confirmation lag',
     'Delay between initial breakout and actionable 5-minute confirmation.',
     6,'not_tested','mixed','numeric',false,'planned',null,null),

    ('F11','F_TIME_EXECUTION','Favorable move consumed before alert',
     'Favorable excursion already completed before the actionable 5-minute signal/alert.',
     6,'not_tested','mixed','numeric',false,'planned',null,null),

    ('F12','F_TIME_EXECUTION','Executable price vs confirmation reference price',
     'Difference between theoretical 5-minute confirmation close and plausible executable entry.',
     6,'not_tested','mixed','numeric',false,'planned',null,null),

    ('F13','F_TIME_EXECUTION','2-minute vs 5-minute confirmation',
     'Compare signal quality, latency, and favorable-first performance between 2m and frozen 5m confirmation.',
     6,'research_only','mixed','comparison',true,'planned',
     'Prior research favored 5-minute confirmation; expanded-universe executable-entry analysis remains pending.',
     'baseline_research'),

    ('F14','F_TIME_EXECUTION','1M/2M/3M/5M confirmation comparison',
     'Multi-timeframe comparison using one canonical 1-minute source.',
     6,'not_tested','mixed','comparison',false,'planned',null,null),

    ('F15','F_TIME_EXECUTION','Signal quality vs entry latency tradeoff',
     'Quantify the tradeoff between stricter confirmation and lost favorable movement.',
     6,'not_tested','mixed','interaction',false,'planned',null,null),

    -- ------------------------------------------------------------------------
    -- FAMILY G — SYMBOL / UNIVERSE
    -- ------------------------------------------------------------------------
    ('G01','G_SYMBOL_UNIVERSE','Overall performance by symbol',
     'Compare all PM+PD signals by symbol.',
     7,'ready','static','categorical',true,'planned',
     'Original 16-stock data exists; expanded event-level DB will make the ranking reproducible.',
     'research_ready'),

    ('G02','G_SYMBOL_UNIVERSE','Bull performance by symbol',
     'Compare bullish PM+PD performance by symbol.',
     7,'ready','static','categorical',true,'planned',
     'Directional symbol ranking requested; expanded dataset will support it.',
     'research_ready'),

    ('G03','G_SYMBOL_UNIVERSE','Bear performance by symbol',
     'Compare bearish PM+PD performance by symbol.',
     7,'ready','static','categorical',true,'planned',
     'Directional symbol ranking requested; expanded dataset will support it.',
     'research_ready'),

    ('G04','G_SYMBOL_UNIVERSE','PRIME performance by symbol',
     'Compare PRIME performance by individual symbol.',
     7,'not_tested','static','interaction',false,'planned',null,null),

    ('G05','G_SYMBOL_UNIVERSE','CONDITIONAL performance by symbol',
     'Compare CONDITIONAL performance by individual symbol.',
     7,'not_tested','static','interaction',false,'planned',null,null),

    ('G06','G_SYMBOL_UNIVERSE','EXPANSION performance by symbol',
     'Compare EXPANSION behavior by individual symbol.',
     7,'not_tested','static','interaction',false,'planned',null,null),

    ('G07','G_SYMBOL_UNIVERSE','SCALP performance by symbol',
     'Compare SCALP behavior by individual symbol.',
     7,'not_tested','static','interaction',false,'planned',null,null),

    ('G08','G_SYMBOL_UNIVERSE','Symbol x direction',
     'Interaction between symbol and bull/bear direction.',
     7,'not_tested','static','interaction',false,'planned',null,null),

    ('G09','G_SYMBOL_UNIVERSE','Symbol x Grade/Profile',
     'Interaction between symbol and frozen V4 Grade/Profile.',
     7,'not_tested','static','interaction',false,'planned',null,null),

    ('G10','G_SYMBOL_UNIVERSE','Symbol x market regime',
     'Interaction between symbol and market regime.',
     7,'not_tested','static','interaction',false,'planned',null,null),

    ('G11','G_SYMBOL_UNIVERSE','Symbol x time of day',
     'Interaction between symbol and signal time.',
     7,'not_tested','static','interaction',false,'planned',null,null),

    ('G12','G_SYMBOL_UNIVERSE','Recent symbol-performance changes',
     'Detect recent changes in directional symbol performance.',
     7,'not_tested','static','trajectory',false,'planned',null,null),

    ('G13','G_SYMBOL_UNIVERSE','Performance stability through time',
     'Assess whether symbol-level performance remains stable across subperiods.',
     7,'not_tested','static','robustness',false,'planned',null,null),

    ('G14','G_SYMBOL_UNIVERSE','Sample maturity / N',
     'Track whether symbol-direction samples are large enough for meaningful interpretation.',
     7,'research_only','static','numeric',true,'existing_research',
     'Confidence rules already separate sample size from observed favorable-first quality.',
     'baseline_research'),

    ('G15','G_SYMBOL_UNIVERSE','Stock volatility characteristics',
     'Relate symbol-level volatility characteristics to PM+PD performance.',
     7,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('G16','G_SYMBOL_UNIVERSE','Stock liquidity characteristics',
     'Relate symbol liquidity/volume characteristics to PM+PD performance.',
     7,'not_tested','signal_time','numeric',false,'planned',null,null),

    ('G17','G_SYMBOL_UNIVERSE','Performance clusters by stock characteristics',
     'Identify stable clusters by volatility, liquidity, sector, trend, or other characteristics.',
     7,'not_tested','static','interaction',false,'planned',null,null),

    ('G18','G_SYMBOL_UNIVERSE','Original 16-stock vs expanded 112-stock universe',
     'Compare discovery-set findings with the frozen 112-stock universe.',
     7,'not_tested','static','robustness',false,'planned',null,null),

    ('G19','G_SYMBOL_UNIVERSE','Cross-universe robustness',
     'Assess stability across alternate future universes/holdout cohorts.',
     7,'not_tested','static','robustness',false,'planned',null,null),

    -- ------------------------------------------------------------------------
    -- FAMILY H — OUTCOME / TARGET OPTIMIZATION
    -- ------------------------------------------------------------------------
    ('H01','H_OUTCOME_TARGETS','+0.25% favorable-first',
     'Probability of +0.25% favorable move before the selected adverse threshold.',
     8,'not_tested','post_signal','outcome',false,'planned',null,null),

    ('H02','H_OUTCOME_TARGETS','+0.50% favorable-first',
     'Primary symmetric benchmark: +0.50% favorable before -0.50% adverse.',
     8,'validated','post_signal','outcome',true,'existing_v4',
     'Primary frozen PM+PD research benchmark.',
     'primary_metric'),

    ('H03','H_OUTCOME_TARGETS','+0.75% favorable-first',
     'Probability of +0.75% favorable move before selected adverse threshold.',
     8,'not_tested','post_signal','outcome',false,'planned',null,null),

    ('H04','H_OUTCOME_TARGETS','+1.00% favorable hit',
     'Secondary continuation benchmark: whether +1.00% favorable excursion is reached.',
     8,'validated','post_signal','outcome',true,'existing_v4',
     'Secondary continuation benchmark used throughout V4 research.',
     'secondary_metric'),

    ('H05','H_OUTCOME_TARGETS','MFE distribution percentiles',
     'Distribution/percentiles of maximum favorable excursion.',
     8,'not_tested','post_signal','distribution',false,'planned',null,null),

    ('H06','H_OUTCOME_TARGETS','MAE distribution percentiles',
     'Distribution/percentiles of maximum adverse excursion.',
     8,'not_tested','post_signal','distribution',false,'planned',null,null),

    ('H07','H_OUTCOME_TARGETS','Time to +0.25%',
     'Elapsed time from confirmed signal to first +0.25% favorable excursion.',
     8,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('H08','H_OUTCOME_TARGETS','Time to +0.50%',
     'Elapsed time from confirmed signal to first +0.50% favorable excursion.',
     8,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('H09','H_OUTCOME_TARGETS','Time to +0.75%',
     'Elapsed time from confirmed signal to first +0.75% favorable excursion.',
     8,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('H10','H_OUTCOME_TARGETS','Time to +1.00%',
     'Elapsed time from confirmed signal to first +1.00% favorable excursion.',
     8,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('H11','H_OUTCOME_TARGETS','Time to adverse milestones',
     'Elapsed time to selected adverse excursion milestones.',
     8,'not_tested','post_signal','numeric',false,'planned',null,null),

    ('H12','H_OUTCOME_TARGETS','Same-bar favorable/adverse cases',
     'Analyze ambiguous bars in which favorable and adverse thresholds both occur.',
     8,'research_only','post_signal','outcome',true,'existing_v4',
     'Same-bar BOTH cases are already recognized; larger-dataset treatment remains required.',
     'baseline_research'),

    ('H13','H_OUTCOME_TARGETS','EXPANSION-specific targets',
     'Optimize continuation targets conditional on EXPANSION trade type.',
     8,'not_tested','post_signal','optimization',false,'planned',null,null),

    ('H14','H_OUTCOME_TARGETS','SCALP-specific targets',
     'Optimize targets/exits conditional on SCALP trade type.',
     8,'not_tested','post_signal','optimization',false,'planned',null,null),

    ('H15','H_OUTCOME_TARGETS','Structural exits vs fixed exits',
     'Compare evidence-based structural exits with fixed percentage exits.',
     8,'not_tested','post_signal','comparison',false,'planned',null,null),

    -- ------------------------------------------------------------------------
    -- FAMILY I — CONTROLLED INTERACTIONS / MODEL DEVELOPMENT
    -- ------------------------------------------------------------------------
    ('I01','I_MODEL_INTERACTIONS','Grade x Profile x Time',
     'Three-way interaction among Grade family, Profile, and time of day.',
     9,'not_tested','mixed','interaction',false,'planned',null,null),

    ('I02','I_MODEL_INTERACTIONS','Grade x Profile x Market Bias',
     'Three-way interaction among Grade family, Profile, and market bias.',
     9,'not_tested','mixed','interaction',false,'planned',null,null),

    ('I03','I_MODEL_INTERACTIONS','Grade x Profile x Weekly Bias',
     'Three-way interaction among Grade family, Profile, and weekly stock bias.',
     9,'not_tested','mixed','interaction',false,'planned',null,null),

    ('I04','I_MODEL_INTERACTIONS','Grade x Profile x Relative Strength',
     'Three-way interaction among Grade family, Profile, and relative strength.',
     9,'not_tested','mixed','interaction',false,'planned',null,null),

    ('I05','I_MODEL_INTERACTIONS','Market x Weekly alignment',
     'Joint current market-bias and weekly stock-bias alignment.',
     9,'not_tested','mixed','interaction',false,'planned',null,null),

    ('I06','I_MODEL_INTERACTIONS','Time x Market Bias',
     'Interaction between signal time and current market bias.',
     9,'not_tested','mixed','interaction',false,'planned',null,null),

    ('I07','I_MODEL_INTERACTIONS','Volatility x Profile',
     'Interaction between volatility regime and V4 profile.',
     9,'not_tested','mixed','interaction',false,'planned',null,null),

    ('I08','I_MODEL_INTERACTIONS','Symbol characteristics x Profile',
     'Interaction between stable symbol characteristics and V4 profile.',
     9,'not_tested','mixed','interaction',false,'planned',null,null),

    ('I09','I_MODEL_INTERACTIONS','Setup quality x warning probability',
     'Relationship between entry setup quality and subsequent warning probability.',
     9,'not_tested','mixed','interaction',false,'planned',null,null),

    ('I10','I_MODEL_INTERACTIONS','Signal context x warning recovery',
     'Relationship between entry context and probability of recovery after deterioration.',
     9,'not_tested','mixed','interaction',false,'planned',null,null),

    ('I11','I_MODEL_INTERACTIONS','Minimal-factor model development',
     'Develop the simplest model that materially improves frozen V4 performance.',
     9,'not_tested','mixed','model',false,'planned',null,null),

    ('I12','I_MODEL_INTERACTIONS','Complexity vs V4 baseline improvement',
     'Evaluate whether incremental model complexity produces robust improvement over V4.',
     9,'not_tested','mixed','model',false,'planned',null,null),

    ('I13','I_MODEL_INTERACTIONS','Signal-frequency cost of added filters',
     'Measure how candidate filters affect signal frequency and opportunity count.',
     9,'not_tested','mixed','model',false,'planned',null,null),

    -- ------------------------------------------------------------------------
    -- FAMILY J — ROBUSTNESS / VALIDATION
    -- ------------------------------------------------------------------------
    ('J01','J_ROBUSTNESS','Discovery vs holdout datasets',
     'Separate discovery and untouched holdout samples for candidate-model evaluation.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J02','J_ROBUSTNESS','Older vs newer periods',
     'Compare results across older and newer historical subperiods.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J03','J_ROBUSTNESS','Bull vs Bear robustness',
     'Confirm findings independently across bullish and bearish directions.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J04','J_ROBUSTNESS','Market-regime robustness',
     'Confirm findings across bullish, bearish, and mixed market regimes.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J05','J_ROBUSTNESS','Volatility-regime robustness',
     'Confirm findings across low/normal/high volatility regimes.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J06','J_ROBUSTNESS','Cross-symbol robustness',
     'Confirm findings are not dependent on a small set of symbols.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J07','J_ROBUSTNESS','Cross-stock-set robustness',
     'Confirm findings across the four frozen 28-stock sets.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J08','J_ROBUSTNESS','Across-year robustness',
     'Confirm findings across calendar years/subperiods.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J09','J_ROBUSTNESS','Threshold sensitivity',
     'Evaluate whether results survive reasonable changes to thresholds.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J10','J_ROBUSTNESS','Nearby-parameter stability',
     'Evaluate whether nearby parameter settings yield similar conclusions.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J11','J_ROBUSTNESS','Original 16 vs 112-stock universe',
     'Compare original discovery conclusions with the expanded frozen universe.',
     10,'not_tested','static','robustness',false,'planned',null,null),

    ('J12','J_ROBUSTNESS','Frozen candidate out-of-sample test',
     'Evaluate a frozen candidate model on untouched out-of-sample data.',
     10,'not_tested','static','validation',false,'planned',null,null),

    ('J13','J_ROBUSTNESS','Forward validation',
     'Validate frozen V4 / later candidate behavior on live forward data.',
     10,'testing','static','validation',true,'existing_v4',
     'Frozen V4 forward validation is currently underway.',
     'forward_validation'),

    ('J14','J_ROBUSTNESS','Optimized candidate vs frozen V4 baseline',
     'Final direct comparison of candidate model against frozen V4 baseline.',
     10,'not_tested','static','validation',false,'planned',null,null)
)

insert into public.research_factors (
    strategy_id,
    factor_code,
    family,
    factor_name,
    description,
    priority,
    status,
    timing_type,
    data_type,
    data_available,
    implementation_status,
    finding,
    production_status,
    metadata_json,
    roadmap_version
)
select
    pmpd.strategy_id,
    f.factor_code,
    f.family,
    f.factor_name,
    f.description,
    f.priority,
    f.status,
    f.timing_type,
    f.data_type,
    f.data_available,
    f.implementation_status,
    f.finding,
    f.production_status,
    jsonb_build_object(
        'roadmap_family_order', f.priority,
        'seed_source', 'Migration_006',
        'authoritative', true
    ),
    'PMPD-RM-1.0'
from pmpd
cross join factors f
on conflict (strategy_id, factor_code) do update
set
    family = excluded.family,
    factor_name = excluded.factor_name,
    description = excluded.description,
    priority = excluded.priority,
    status = excluded.status,
    timing_type = excluded.timing_type,
    data_type = excluded.data_type,
    data_available = excluded.data_available,
    implementation_status = excluded.implementation_status,
    finding = excluded.finding,
    production_status = excluded.production_status,
    metadata_json = excluded.metadata_json,
    roadmap_version = excluded.roadmap_version,
    updated_at = now();

-- ============================================================================
-- 2. RECORD ROADMAP GOVERNANCE DECISION
-- ============================================================================

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
    'PM+PD master research roadmap is authoritative in Supabase',
    'PMPD-RM-1.0 stored in public.research_factors is the authoritative PM+PD factor roadmap. New research factors/tangents must be added there or explicitly promoted through the backlog/decision process.',
    'Prevents roadmap drift, duplicated research, forgotten tangents, and undocumented model changes.',
    'Governance correction completed during 8H-6A-5D on 2026-08-28.',
    'V4',
    jsonb_build_object(
        'roadmap_version', 'PMPD-RM-1.0',
        'authoritative_table', 'public.research_factors'
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = 'PM+PD master research roadmap is authoritative in Supabase'
      and d.status = 'active'
);

-- ============================================================================
-- 3. UPDATE PROJECT STATE WITHOUT CHANGING ACTIVE PHASE
-- ============================================================================

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
update public.project_state ps
set
    roadmap_version = 'PMPD-RM-1.0',
    last_decision = 'PMPD-RM-1.0 research-factor roadmap populated and authoritative in Supabase; return to 8H-6 Historical Engine & Ingestion.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            'roadmap_population_status', 'POPULATED_AND_AUTHORITATIVE',
            'roadmap_table', 'research_factors',
            'roadmap_version', 'PMPD-RM-1.0',
            'governance_correction', '8H-6A-5D_COMPLETE'
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

-- ============================================================================
-- 4. VALIDATION — ABORT IF ROADMAP IS INCOMPLETE
-- ============================================================================

do $$
declare
    v_strategy_id uuid;
    v_total integer;
    v_unique integer;
    v_families integer;
    v_bad_version integer;
begin
    select strategy_id
      into v_strategy_id
    from public.strategies
    where strategy_code = 'PMPD';

    if v_strategy_id is null then
        raise exception 'PMPD strategy not found.';
    end if;

    select
        count(*),
        count(distinct factor_code),
        count(distinct family),
        count(*) filter (where roadmap_version <> 'PMPD-RM-1.0')
    into
        v_total,
        v_unique,
        v_families,
        v_bad_version
    from public.research_factors
    where strategy_id = v_strategy_id;

    if v_total <> 205 then
        raise exception 'Roadmap validation failed: expected 205 factors, found %.', v_total;
    end if;

    if v_unique <> 205 then
        raise exception 'Roadmap validation failed: expected 205 unique factor codes, found %.', v_unique;
    end if;

    if v_families <> 10 then
        raise exception 'Roadmap validation failed: expected 10 research families, found %.', v_families;
    end if;

    if v_bad_version <> 0 then
        raise exception 'Roadmap validation failed: % rows have unexpected roadmap_version.', v_bad_version;
    end if;
end $$;

commit;

-- ============================================================================
-- 5. POST-MIGRATION VALIDATION OUTPUT
-- ============================================================================

select
    rf.family,
    count(*) as factor_count,
    count(*) filter (where rf.status = 'validated') as validated,
    count(*) filter (where rf.status = 'testing') as testing,
    count(*) filter (where rf.status = 'ready') as ready,
    count(*) filter (where rf.status = 'research_only') as research_only,
    count(*) filter (where rf.status = 'not_tested') as not_tested
from public.research_factors rf
join public.strategies s
  on s.strategy_id = rf.strategy_id
where s.strategy_code = 'PMPD'
group by rf.family
order by min(rf.priority), rf.family;

select
    count(*) as total_factors,
    count(distinct rf.factor_code) as unique_factor_codes,
    count(distinct rf.family) as research_families,
    min(rf.roadmap_version) as roadmap_version
from public.research_factors rf
join public.strategies s
  on s.strategy_id = rf.strategy_id
where s.strategy_code = 'PMPD';

select
    s.strategy_code,
    ps.active_phase_code,
    ps.active_phase_name,
    ps.next_phase_code,
    ps.next_phase_name,
    ps.roadmap_version,
    ps.metadata_json ->> 'roadmap_population_status' as roadmap_population_status
from public.project_state ps
join public.strategies s
  on s.strategy_id = ps.strategy_id
where s.strategy_code = 'PMPD';

-- ============================================================================
-- END MIGRATION 006
-- ============================================================================
