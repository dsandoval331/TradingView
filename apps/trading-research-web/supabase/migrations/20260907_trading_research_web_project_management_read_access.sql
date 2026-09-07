revoke all on table public.program_phases from anon;
revoke all on table public.project_decisions from anon;
revoke all on table public.project_backlog from anon;

grant select on table public.program_phases to authenticated;
grant select on table public.project_decisions to authenticated;
grant select on table public.project_backlog to authenticated;

drop policy if exists trading_research_web_read on public.program_phases;
create policy trading_research_web_read
on public.program_phases
for select
to authenticated
using (public.is_trading_research_web_user());

drop policy if exists trading_research_web_read on public.project_decisions;
create policy trading_research_web_read
on public.project_decisions
for select
to authenticated
using (public.is_trading_research_web_user());

drop policy if exists trading_research_web_read on public.project_backlog;
create policy trading_research_web_read
on public.project_backlog
for select
to authenticated
using (public.is_trading_research_web_user());
