-- PMPD V5 9J VWAP Event-Path V2 — governance backup
-- Mirrors the live Supabase checkpoint written 2026-09-07.
-- This file intentionally contains project-management metadata only; the 450,491-row
-- event dataset remains in the certified local research package and is not fabricated here.

begin;

update public.project_backlog
set status='complete', resolved_at=coalesce(resolved_at,now()), updated_at=now()
where strategy_id=(select strategy_id from public.strategies where strategy_code='PMPD')
  and title='Run 9H Batch 3 final individual-factor adjudication'
  and status <> 'complete';

-- See live DB experiment_code PMPD_V5_9J_VWAP_EVENT_PATH_V2_PREREG for the frozen JSON protocol.
-- The live DB also contains the active backlog item:
--   Run 9J VWAP Event-Path V2 from DP1 contact
-- and project_state.v5_9j_vwap_event_path_v2_status = PREREGISTERED_AWAITING_LOCAL_RUN.

commit;
