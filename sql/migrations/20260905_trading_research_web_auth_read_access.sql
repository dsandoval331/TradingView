-- Applied to Supabase Pineview on 2026-09-05.
-- Private web-app allowlist plus read-only RLS policies.

create table if not exists public.trading_research_web_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

alter table public.trading_research_web_users enable row level security;
revoke all on table public.trading_research_web_users from anon, authenticated;
grant usage on schema public to authenticated;
grant select on table public.strategies, public.datasets, public.project_state to authenticated;
revoke all on table public.strategies, public.datasets, public.project_state from anon;

create or replace function public.is_trading_research_web_user()
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.trading_research_web_users u
    where u.user_id = (select auth.uid())
  );
$$;

revoke all on function public.is_trading_research_web_user() from public;
grant execute on function public.is_trading_research_web_user() to authenticated;

create policy "Trading Research web users can read strategies"
on public.strategies for select to authenticated
using (public.is_trading_research_web_user());

create policy "Trading Research web users can read datasets"
on public.datasets for select to authenticated
using (public.is_trading_research_web_user());

create policy "Trading Research web users can read project state"
on public.project_state for select to authenticated
using (public.is_trading_research_web_user());
