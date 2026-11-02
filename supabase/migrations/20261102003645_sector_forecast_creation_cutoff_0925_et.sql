alter table public.sector_winner_forecasts drop constraint sector_winner_forecasts_recorded_at_check;
alter table public.sector_winner_forecasts add constraint sector_winner_forecasts_recorded_at_check check ((recorded_at at time zone 'America/New_York')::time < time '09:25');
