-- FTHC Staging -> Production Normalization V1.1
-- Fix: integer-semantic staging values like '0.0' are cast text -> numeric -> integer.
-- Fix: boolean parser accepts 0.0 / 1.0.
-- Idempotent and safe to rerun after the prior failed transaction.
begin;

-- 1) Signals
insert into public.signals (
    signal_key, symbol, direction, signal_timestamp, reference_price,
    research_event, production_signal, data_source, research_population,
    historical_set, schema_version, collector_build,
    entry_grade_version, warning_model_version, leaderboard_version
)
select
    upper(s."symbol") || '|' || s."eventdt" || '|' || case when nullif(s."fthc_direction", '')::numeric=1 then 'BULL' when nullif(s."fthc_direction", '')::numeric=-1 then 'BEAR' end as signal_key,
    upper(s."symbol") as symbol,
    case when nullif(s."fthc_direction", '')::numeric=1 then 'BULL' when nullif(s."fthc_direction", '')::numeric=-1 then 'BEAR' end as direction,
    s."eventdt"::timestamptz as signal_timestamp,
    nullif(s."fthc_referenceprice", '')::numeric as reference_price,
    coalesce(case when nullif(s."fthc_researchevent", '') is null then null when lower(s."fthc_researchevent") in ('1','1.0','true','t','yes','y') then true when lower(s."fthc_researchevent") in ('0','0.0','false','f','no','n') then false else null end, true) as research_event,
    coalesce(case when nullif(s."fthc_productionsignal", '') is null then null when lower(s."fthc_productionsignal") in ('1','1.0','true','t','yes','y') then true when lower(s."fthc_productionsignal") in ('0','0.0','false','f','no','n') then false else null end, false) as production_signal,
    'historical_30m', 'historical',
    nullif(s."set", ''),
    'FTHC_WEBHOOK_V1', 'S1M_FTHC_1.0.3A/B + 1.0C',
    null, 'WTV1', 'LBV0'
from public.fthc_historical_staging_v1 s
on conflict (signal_key) do update set
    symbol=excluded.symbol, direction=excluded.direction, signal_timestamp=excluded.signal_timestamp,
    reference_price=excluded.reference_price, research_event=excluded.research_event,
    production_signal=excluded.production_signal, historical_set=excluded.historical_set;

-- 2) Entry context
insert into public.signal_entry_context (signal_id, c1_open, c1_high, c1_low, c1_close, c1_volume, c1_tr, c1_vwap, c2_open, c2_high, c2_low, c2_close, c2_volume, c2_tr, c2_vwap, c1_relvol, c2_relvol, combined_relvol, atr_daily, atr_1m_prev_day, atr_1m_prev_5d, atr_first_two_candles, selected_atr, delta_pct, vwap_distance_pct, pmh, pml, pm_open, pm_last, pm_volume, ah_high, ah_low, ah_volume, pdh, pdl, previous_rth_close)
select sg.id,
    nullif(s."fthc_c1_open", '')::numeric,
    nullif(s."fthc_c1_high", '')::numeric,
    nullif(s."fthc_c1_low", '')::numeric,
    nullif(s."fthc_c1_close", '')::numeric,
    nullif(s."fthc_c1_volume", '')::numeric,
    nullif(s."fthc_c1_tr", '')::numeric,
    nullif(s."fthc_c1_vwap", '')::numeric,
    nullif(s."fthc_c2_open", '')::numeric,
    nullif(s."fthc_c2_high", '')::numeric,
    nullif(s."fthc_c2_low", '')::numeric,
    nullif(s."fthc_c2_close", '')::numeric,
    nullif(s."fthc_c2_volume", '')::numeric,
    nullif(s."fthc_c2_tr", '')::numeric,
    nullif(s."fthc_c2_vwap", '')::numeric,
    nullif(s."fthc_c1_relvol", '')::numeric,
    nullif(s."fthc_c2_relvol", '')::numeric,
    nullif(s."fthc_combined_relvol", '')::numeric,
    nullif(s."fthc_atr_prevdaily", '')::numeric,
    nullif(s."fthc_atr_prevday1m", '')::numeric,
    nullif(s."fthc_atr_prev5day1m", '')::numeric,
    nullif(s."fthc_atr_first2", '')::numeric,
    nullif(s."fthc_atr_selected", '')::numeric,
    nullif(s."fthc_deltapct", '')::numeric,
    nullif(s."fthc_vwap_distance", '')::numeric,
    nullif(s."fthc_pmh", '')::numeric,
    nullif(s."fthc_pml", '')::numeric,
    nullif(s."fthc_pm_open", '')::numeric,
    nullif(s."fthc_pm_last", '')::numeric,
    nullif(s."fthc_pm_volume", '')::numeric,
    nullif(s."fthc_ah_high", '')::numeric,
    nullif(s."fthc_ah_low", '')::numeric,
    nullif(s."fthc_ah_volume", '')::numeric,
    nullif(s."fthc_pdh", '')::numeric,
    nullif(s."fthc_pdl", '')::numeric,
    nullif(s."fthc_prevrthclose", '')::numeric
from public.fthc_historical_staging_v1 s
join public.signals sg on sg.signal_key = upper(s."symbol") || '|' || s."eventdt" || '|' || case when nullif(s."fthc_direction", '')::numeric=1 then 'BULL' when nullif(s."fthc_direction", '')::numeric=-1 then 'BEAR' end
on conflict (signal_id) do update set
    c1_open=excluded.c1_open,
    c1_high=excluded.c1_high,
    c1_low=excluded.c1_low,
    c1_close=excluded.c1_close,
    c1_volume=excluded.c1_volume,
    c1_tr=excluded.c1_tr,
    c1_vwap=excluded.c1_vwap,
    c2_open=excluded.c2_open,
    c2_high=excluded.c2_high,
    c2_low=excluded.c2_low,
    c2_close=excluded.c2_close,
    c2_volume=excluded.c2_volume,
    c2_tr=excluded.c2_tr,
    c2_vwap=excluded.c2_vwap,
    c1_relvol=excluded.c1_relvol,
    c2_relvol=excluded.c2_relvol,
    combined_relvol=excluded.combined_relvol,
    atr_daily=excluded.atr_daily,
    atr_1m_prev_day=excluded.atr_1m_prev_day,
    atr_1m_prev_5d=excluded.atr_1m_prev_5d,
    atr_first_two_candles=excluded.atr_first_two_candles,
    selected_atr=excluded.selected_atr,
    delta_pct=excluded.delta_pct,
    vwap_distance_pct=excluded.vwap_distance_pct,
    pmh=excluded.pmh,
    pml=excluded.pml,
    pm_open=excluded.pm_open,
    pm_last=excluded.pm_last,
    pm_volume=excluded.pm_volume,
    ah_high=excluded.ah_high,
    ah_low=excluded.ah_low,
    ah_volume=excluded.ah_volume,
    pdh=excluded.pdh,
    pdl=excluded.pdl,
    previous_rth_close=excluded.previous_rth_close;

-- 3) CP1
insert into public.signal_checkpoints (
 signal_id, checkpoint_minute, has_checkpoint, open, high, low, close, rth_vwap, mfe_pct, mae_pct,
 vwap_state, vwap_lost_since_signal, vwap_reclaimed, wrong_side_close_count, max_wrong_side_streak,
 pm_state, ah_state, pd_state, levels_retained, min_levels_retained,
 pm_lost, pm_reclaimed, ah_lost, ah_reclaimed, pd_lost, pd_reclaimed, warning_model_version)
select sg.id,
 1, coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false),
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp1_open", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp1_high", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp1_low", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp1_close", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp1_rth_vwap", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthc_cp1_mfe", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthc_cp1_mae", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp1_vwap_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fthv_cp1_vwap_lost", '') is null then null when lower(s."fthv_cp1_vwap_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_cp1_vwap_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fthv_cp1_vwap_reclaimed", '') is null then null when lower(s."fthv_cp1_vwap_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_cp1_vwap_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp1_wrongsideclosecount", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp1_maxwrongsidestreak", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp1_pm_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp1_ah_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp1_pd_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp1_levelsretained", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp1_minlevelsretained", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp1_pm_lost", '') is null then null when lower(s."fths_cp1_pm_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp1_pm_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp1_pm_reclaimed", '') is null then null when lower(s."fths_cp1_pm_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp1_pm_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp1_ah_lost", '') is null then null when lower(s."fths_cp1_ah_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp1_ah_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp1_ah_reclaimed", '') is null then null when lower(s."fths_cp1_ah_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp1_ah_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp1_pd_lost", '') is null then null when lower(s."fths_cp1_pd_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp1_pd_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp1", '') is null then null when lower(s."fthv_has_cp1") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp1") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp1_pd_reclaimed", '') is null then null when lower(s."fths_cp1_pd_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp1_pd_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 'WTV1'
from public.fthc_historical_staging_v1 s
join public.signals sg on sg.signal_key = upper(s."symbol") || '|' || s."eventdt" || '|' || case when nullif(s."fthc_direction", '')::numeric=1 then 'BULL' when nullif(s."fthc_direction", '')::numeric=-1 then 'BEAR' end
on conflict (signal_id, checkpoint_minute) do update set
 has_checkpoint=excluded.has_checkpoint,
 open=excluded.open,
 high=excluded.high,
 low=excluded.low,
 close=excluded.close,
 rth_vwap=excluded.rth_vwap,
 mfe_pct=excluded.mfe_pct,
 mae_pct=excluded.mae_pct,
 vwap_state=excluded.vwap_state,
 vwap_lost_since_signal=excluded.vwap_lost_since_signal,
 vwap_reclaimed=excluded.vwap_reclaimed,
 wrong_side_close_count=excluded.wrong_side_close_count,
 max_wrong_side_streak=excluded.max_wrong_side_streak,
 pm_state=excluded.pm_state,
 ah_state=excluded.ah_state,
 pd_state=excluded.pd_state,
 levels_retained=excluded.levels_retained,
 min_levels_retained=excluded.min_levels_retained,
 pm_lost=excluded.pm_lost,
 pm_reclaimed=excluded.pm_reclaimed,
 ah_lost=excluded.ah_lost,
 ah_reclaimed=excluded.ah_reclaimed,
 pd_lost=excluded.pd_lost,
 pd_reclaimed=excluded.pd_reclaimed,
 warning_model_version=excluded.warning_model_version;

-- 3) CP2
insert into public.signal_checkpoints (
 signal_id, checkpoint_minute, has_checkpoint, open, high, low, close, rth_vwap, mfe_pct, mae_pct,
 vwap_state, vwap_lost_since_signal, vwap_reclaimed, wrong_side_close_count, max_wrong_side_streak,
 pm_state, ah_state, pd_state, levels_retained, min_levels_retained,
 pm_lost, pm_reclaimed, ah_lost, ah_reclaimed, pd_lost, pd_reclaimed, warning_model_version)
select sg.id,
 2, coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false),
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp2_open", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp2_high", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp2_low", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp2_close", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp2_rth_vwap", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthc_cp2_mfe", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthc_cp2_mae", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp2_vwap_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fthv_cp2_vwap_lost", '') is null then null when lower(s."fthv_cp2_vwap_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_cp2_vwap_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fthv_cp2_vwap_reclaimed", '') is null then null when lower(s."fthv_cp2_vwap_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_cp2_vwap_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp2_wrongsideclosecount", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp2_maxwrongsidestreak", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp2_pm_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp2_ah_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp2_pd_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp2_levelsretained", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp2_minlevelsretained", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp2_pm_lost", '') is null then null when lower(s."fths_cp2_pm_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp2_pm_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp2_pm_reclaimed", '') is null then null when lower(s."fths_cp2_pm_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp2_pm_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp2_ah_lost", '') is null then null when lower(s."fths_cp2_ah_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp2_ah_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp2_ah_reclaimed", '') is null then null when lower(s."fths_cp2_ah_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp2_ah_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp2_pd_lost", '') is null then null when lower(s."fths_cp2_pd_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp2_pd_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp2", '') is null then null when lower(s."fthv_has_cp2") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp2") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp2_pd_reclaimed", '') is null then null when lower(s."fths_cp2_pd_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp2_pd_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 'WTV1'
from public.fthc_historical_staging_v1 s
join public.signals sg on sg.signal_key = upper(s."symbol") || '|' || s."eventdt" || '|' || case when nullif(s."fthc_direction", '')::numeric=1 then 'BULL' when nullif(s."fthc_direction", '')::numeric=-1 then 'BEAR' end
on conflict (signal_id, checkpoint_minute) do update set
 has_checkpoint=excluded.has_checkpoint,
 open=excluded.open,
 high=excluded.high,
 low=excluded.low,
 close=excluded.close,
 rth_vwap=excluded.rth_vwap,
 mfe_pct=excluded.mfe_pct,
 mae_pct=excluded.mae_pct,
 vwap_state=excluded.vwap_state,
 vwap_lost_since_signal=excluded.vwap_lost_since_signal,
 vwap_reclaimed=excluded.vwap_reclaimed,
 wrong_side_close_count=excluded.wrong_side_close_count,
 max_wrong_side_streak=excluded.max_wrong_side_streak,
 pm_state=excluded.pm_state,
 ah_state=excluded.ah_state,
 pd_state=excluded.pd_state,
 levels_retained=excluded.levels_retained,
 min_levels_retained=excluded.min_levels_retained,
 pm_lost=excluded.pm_lost,
 pm_reclaimed=excluded.pm_reclaimed,
 ah_lost=excluded.ah_lost,
 ah_reclaimed=excluded.ah_reclaimed,
 pd_lost=excluded.pd_lost,
 pd_reclaimed=excluded.pd_reclaimed,
 warning_model_version=excluded.warning_model_version;

-- 3) CP3
insert into public.signal_checkpoints (
 signal_id, checkpoint_minute, has_checkpoint, open, high, low, close, rth_vwap, mfe_pct, mae_pct,
 vwap_state, vwap_lost_since_signal, vwap_reclaimed, wrong_side_close_count, max_wrong_side_streak,
 pm_state, ah_state, pd_state, levels_retained, min_levels_retained,
 pm_lost, pm_reclaimed, ah_lost, ah_reclaimed, pd_lost, pd_reclaimed, warning_model_version)
select sg.id,
 3, coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false),
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp3_open", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp3_high", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp3_low", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp3_close", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp3_rth_vwap", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthc_cp3_mfe", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthc_cp3_mae", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp3_vwap_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fthv_cp3_vwap_lost", '') is null then null when lower(s."fthv_cp3_vwap_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_cp3_vwap_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fthv_cp3_vwap_reclaimed", '') is null then null when lower(s."fthv_cp3_vwap_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_cp3_vwap_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp3_wrongsideclosecount", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp3_maxwrongsidestreak", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp3_pm_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp3_ah_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp3_pd_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp3_levelsretained", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp3_minlevelsretained", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp3_pm_lost", '') is null then null when lower(s."fths_cp3_pm_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp3_pm_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp3_pm_reclaimed", '') is null then null when lower(s."fths_cp3_pm_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp3_pm_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp3_ah_lost", '') is null then null when lower(s."fths_cp3_ah_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp3_ah_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp3_ah_reclaimed", '') is null then null when lower(s."fths_cp3_ah_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp3_ah_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp3_pd_lost", '') is null then null when lower(s."fths_cp3_pd_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp3_pd_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp3", '') is null then null when lower(s."fthv_has_cp3") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp3") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp3_pd_reclaimed", '') is null then null when lower(s."fths_cp3_pd_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp3_pd_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 'WTV1'
from public.fthc_historical_staging_v1 s
join public.signals sg on sg.signal_key = upper(s."symbol") || '|' || s."eventdt" || '|' || case when nullif(s."fthc_direction", '')::numeric=1 then 'BULL' when nullif(s."fthc_direction", '')::numeric=-1 then 'BEAR' end
on conflict (signal_id, checkpoint_minute) do update set
 has_checkpoint=excluded.has_checkpoint,
 open=excluded.open,
 high=excluded.high,
 low=excluded.low,
 close=excluded.close,
 rth_vwap=excluded.rth_vwap,
 mfe_pct=excluded.mfe_pct,
 mae_pct=excluded.mae_pct,
 vwap_state=excluded.vwap_state,
 vwap_lost_since_signal=excluded.vwap_lost_since_signal,
 vwap_reclaimed=excluded.vwap_reclaimed,
 wrong_side_close_count=excluded.wrong_side_close_count,
 max_wrong_side_streak=excluded.max_wrong_side_streak,
 pm_state=excluded.pm_state,
 ah_state=excluded.ah_state,
 pd_state=excluded.pd_state,
 levels_retained=excluded.levels_retained,
 min_levels_retained=excluded.min_levels_retained,
 pm_lost=excluded.pm_lost,
 pm_reclaimed=excluded.pm_reclaimed,
 ah_lost=excluded.ah_lost,
 ah_reclaimed=excluded.ah_reclaimed,
 pd_lost=excluded.pd_lost,
 pd_reclaimed=excluded.pd_reclaimed,
 warning_model_version=excluded.warning_model_version;

-- 3) CP5
insert into public.signal_checkpoints (
 signal_id, checkpoint_minute, has_checkpoint, open, high, low, close, rth_vwap, mfe_pct, mae_pct,
 vwap_state, vwap_lost_since_signal, vwap_reclaimed, wrong_side_close_count, max_wrong_side_streak,
 pm_state, ah_state, pd_state, levels_retained, min_levels_retained,
 pm_lost, pm_reclaimed, ah_lost, ah_reclaimed, pd_lost, pd_reclaimed, warning_model_version)
select sg.id,
 5, coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false),
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp5_open", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp5_high", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp5_low", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp5_close", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp5_rth_vwap", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthc_cp5_mfe", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthc_cp5_mae", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp5_vwap_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fthv_cp5_vwap_lost", '') is null then null when lower(s."fthv_cp5_vwap_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_cp5_vwap_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fthv_cp5_vwap_reclaimed", '') is null then null when lower(s."fthv_cp5_vwap_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_cp5_vwap_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp5_wrongsideclosecount", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp5_maxwrongsidestreak", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp5_pm_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp5_ah_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp5_pd_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp5_levelsretained", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp5_minlevelsretained", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp5_pm_lost", '') is null then null when lower(s."fths_cp5_pm_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp5_pm_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp5_pm_reclaimed", '') is null then null when lower(s."fths_cp5_pm_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp5_pm_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp5_ah_lost", '') is null then null when lower(s."fths_cp5_ah_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp5_ah_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp5_ah_reclaimed", '') is null then null when lower(s."fths_cp5_ah_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp5_ah_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp5_pd_lost", '') is null then null when lower(s."fths_cp5_pd_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp5_pd_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp5", '') is null then null when lower(s."fthv_has_cp5") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp5") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp5_pd_reclaimed", '') is null then null when lower(s."fths_cp5_pd_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp5_pd_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 'WTV1'
from public.fthc_historical_staging_v1 s
join public.signals sg on sg.signal_key = upper(s."symbol") || '|' || s."eventdt" || '|' || case when nullif(s."fthc_direction", '')::numeric=1 then 'BULL' when nullif(s."fthc_direction", '')::numeric=-1 then 'BEAR' end
on conflict (signal_id, checkpoint_minute) do update set
 has_checkpoint=excluded.has_checkpoint,
 open=excluded.open,
 high=excluded.high,
 low=excluded.low,
 close=excluded.close,
 rth_vwap=excluded.rth_vwap,
 mfe_pct=excluded.mfe_pct,
 mae_pct=excluded.mae_pct,
 vwap_state=excluded.vwap_state,
 vwap_lost_since_signal=excluded.vwap_lost_since_signal,
 vwap_reclaimed=excluded.vwap_reclaimed,
 wrong_side_close_count=excluded.wrong_side_close_count,
 max_wrong_side_streak=excluded.max_wrong_side_streak,
 pm_state=excluded.pm_state,
 ah_state=excluded.ah_state,
 pd_state=excluded.pd_state,
 levels_retained=excluded.levels_retained,
 min_levels_retained=excluded.min_levels_retained,
 pm_lost=excluded.pm_lost,
 pm_reclaimed=excluded.pm_reclaimed,
 ah_lost=excluded.ah_lost,
 ah_reclaimed=excluded.ah_reclaimed,
 pd_lost=excluded.pd_lost,
 pd_reclaimed=excluded.pd_reclaimed,
 warning_model_version=excluded.warning_model_version;

-- 3) CP10
insert into public.signal_checkpoints (
 signal_id, checkpoint_minute, has_checkpoint, open, high, low, close, rth_vwap, mfe_pct, mae_pct,
 vwap_state, vwap_lost_since_signal, vwap_reclaimed, wrong_side_close_count, max_wrong_side_streak,
 pm_state, ah_state, pd_state, levels_retained, min_levels_retained,
 pm_lost, pm_reclaimed, ah_lost, ah_reclaimed, pd_lost, pd_reclaimed, warning_model_version)
select sg.id,
 10, coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false),
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp10_open", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp10_high", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp10_low", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp10_close", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp10_rth_vwap", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthc_cp10_mfe", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthc_cp10_mae", '')::numeric else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp10_vwap_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fthv_cp10_vwap_lost", '') is null then null when lower(s."fthv_cp10_vwap_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_cp10_vwap_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fthv_cp10_vwap_reclaimed", '') is null then null when lower(s."fthv_cp10_vwap_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_cp10_vwap_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp10_wrongsideclosecount", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fthv_cp10_maxwrongsidestreak", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp10_pm_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp10_ah_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp10_pd_state", '') else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp10_levelsretained", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then nullif(s."fths_cp10_minlevelsretained", '')::numeric::integer else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp10_pm_lost", '') is null then null when lower(s."fths_cp10_pm_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp10_pm_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp10_pm_reclaimed", '') is null then null when lower(s."fths_cp10_pm_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp10_pm_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp10_ah_lost", '') is null then null when lower(s."fths_cp10_ah_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp10_ah_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp10_ah_reclaimed", '') is null then null when lower(s."fths_cp10_ah_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp10_ah_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp10_pd_lost", '') is null then null when lower(s."fths_cp10_pd_lost") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp10_pd_lost") in ('0','0.0','false','f','no','n') then false else null end else null end,
 case when coalesce(case when nullif(s."fthv_has_cp10", '') is null then null when lower(s."fthv_has_cp10") in ('1','1.0','true','t','yes','y') then true when lower(s."fthv_has_cp10") in ('0','0.0','false','f','no','n') then false else null end, false) then case when nullif(s."fths_cp10_pd_reclaimed", '') is null then null when lower(s."fths_cp10_pd_reclaimed") in ('1','1.0','true','t','yes','y') then true when lower(s."fths_cp10_pd_reclaimed") in ('0','0.0','false','f','no','n') then false else null end else null end,
 'WTV1'
from public.fthc_historical_staging_v1 s
join public.signals sg on sg.signal_key = upper(s."symbol") || '|' || s."eventdt" || '|' || case when nullif(s."fthc_direction", '')::numeric=1 then 'BULL' when nullif(s."fthc_direction", '')::numeric=-1 then 'BEAR' end
on conflict (signal_id, checkpoint_minute) do update set
 has_checkpoint=excluded.has_checkpoint,
 open=excluded.open,
 high=excluded.high,
 low=excluded.low,
 close=excluded.close,
 rth_vwap=excluded.rth_vwap,
 mfe_pct=excluded.mfe_pct,
 mae_pct=excluded.mae_pct,
 vwap_state=excluded.vwap_state,
 vwap_lost_since_signal=excluded.vwap_lost_since_signal,
 vwap_reclaimed=excluded.vwap_reclaimed,
 wrong_side_close_count=excluded.wrong_side_close_count,
 max_wrong_side_streak=excluded.max_wrong_side_streak,
 pm_state=excluded.pm_state,
 ah_state=excluded.ah_state,
 pd_state=excluded.pd_state,
 levels_retained=excluded.levels_retained,
 min_levels_retained=excluded.min_levels_retained,
 pm_lost=excluded.pm_lost,
 pm_reclaimed=excluded.pm_reclaimed,
 ah_lost=excluded.ah_lost,
 ah_reclaimed=excluded.ah_reclaimed,
 pd_lost=excluded.pd_lost,
 pd_reclaimed=excluded.pd_reclaimed,
 warning_model_version=excluded.warning_model_version;

-- 4) Outcomes
insert into public.signal_outcomes (
 signal_id, primary_outcome_code, primary_outcome, outcome_100v050_code,
 minutes_to_025, minutes_to_050, minutes_to_075, minutes_to_100,
 minutes_to_adverse_050, final_mfe_pct, final_mae_pct, session_complete)
select sg.id,
 coalesce(nullif(s."fthc_outcome_050v050", '')::numeric::integer,0), case coalesce(nullif(s."fthc_outcome_050v050", '')::numeric::integer,0) when 1 then 'FAVORABLE' when 2 then 'ADVERSE' when 3 then 'BOTH' else 'UNRESOLVED' end, nullif(s."fthc_outcome_100v050", '')::numeric::integer,
 nullif(s."fthc_minutesto_025", '')::numeric, nullif(s."fthc_minutesto_050", '')::numeric,
 nullif(s."fthc_minutesto_075", '')::numeric, nullif(s."fthc_minutesto_100", '')::numeric,
 nullif(s."fthc_minutesto_adverse050", '')::numeric, nullif(s."fthc_final_mfe", '')::numeric,
 nullif(s."fthc_final_mae", '')::numeric, true
from public.fthc_historical_staging_v1 s
join public.signals sg on sg.signal_key = upper(s."symbol") || '|' || s."eventdt" || '|' || case when nullif(s."fthc_direction", '')::numeric=1 then 'BULL' when nullif(s."fthc_direction", '')::numeric=-1 then 'BEAR' end
on conflict (signal_id) do update set
 primary_outcome_code=excluded.primary_outcome_code,
 primary_outcome=excluded.primary_outcome,
 outcome_100v050_code=excluded.outcome_100v050_code,
 minutes_to_025=excluded.minutes_to_025,
 minutes_to_050=excluded.minutes_to_050,
 minutes_to_075=excluded.minutes_to_075,
 minutes_to_100=excluded.minutes_to_100,
 minutes_to_adverse_050=excluded.minutes_to_adverse_050,
 final_mfe_pct=excluded.final_mfe_pct,
 final_mae_pct=excluded.final_mae_pct,
 session_complete=excluded.session_complete;

commit;

-- Acceptance Suite
select
 (select count(*) from public.signals where data_source='historical_30m') as signals,
 (select count(*) from public.signal_entry_context e join public.signals s on s.id=e.signal_id where s.data_source='historical_30m') as entry_context,
 (select count(*) from public.signal_checkpoints c join public.signals s on s.id=c.signal_id where s.data_source='historical_30m') as checkpoints,
 (select count(*) from public.signal_outcomes o join public.signals s on s.id=o.signal_id where s.data_source='historical_30m') as outcomes,
 (select count(distinct symbol) from public.signals where data_source='historical_30m') as symbols,
 (select count(*) from public.signals where data_source='historical_30m' and direction='BULL') as bullish,
 (select count(*) from public.signals where data_source='historical_30m' and direction='BEAR') as bearish;

select o.primary_outcome, count(*)
from public.signal_outcomes o join public.signals s on s.id=o.signal_id
where s.data_source='historical_30m'
group by o.primary_outcome order by o.primary_outcome;

select c.checkpoint_minute, count(*) filter (where c.has_checkpoint) as available, count(*) as total_rows
from public.signal_checkpoints c join public.signals s on s.id=c.signal_id
where s.data_source='historical_30m'
group by c.checkpoint_minute order by c.checkpoint_minute;

select min(signal_timestamp) as earliest_event, max(signal_timestamp) as latest_event
from public.signals where data_source='historical_30m';

select count(*) as duplicate_signal_keys from (
 select signal_key from public.signals group by signal_key having count(*) > 1
) d;