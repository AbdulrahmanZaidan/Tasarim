-- Keep the RLS-bypassing profile lookup outside the exposed API schema.
-- Public role helpers preserve their existing signatures for policies and clients.
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to anon, authenticated;

create or replace function private.current_app_role()
returns public.app_role
language sql stable security definer set search_path = ''
as $$
  select p.role from public.profiles p
  where (select auth.uid()) is not null and p.id = (select auth.uid())
$$;
revoke all on function private.current_app_role() from public;
grant execute on function private.current_app_role() to anon, authenticated;

create or replace function public.current_app_role()
returns public.app_role
language sql stable security invoker set search_path = ''
as $$ select private.current_app_role() $$;

alter function public.is_admin() security invoker;
alter function public.can_edit() security invoker;
alter function public.can_view_private() security invoker;

-- Trigger execution does not require exposing these functions as RPC endpoints.
revoke all on function public.tg_profiles_guard(), public.tg_log_activity()
  from public, anon, authenticated;

-- Replace only the original template URL, preserving any separately customized URL.
update public.project_settings
set github_url = 'https://github.com/AbdulrahmanZaidan/Tasarim'
where id = true and github_url = 'https://github.com/Siiingularity/Tasarim1';

notify pgrst, 'reload schema';
