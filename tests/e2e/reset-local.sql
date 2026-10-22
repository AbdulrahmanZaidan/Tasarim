-- !!! YALNIZCA YEREL TEST VERİTABANI İÇİNDİR — ÜRETİM VERİTABANINDA ÇALIŞTIRMAYIN !!!
-- Uçtan uca testlerden önce proje verilerini başlangıç durumuna döndürür (kullanıcılar korunur),
-- ardından başlangıç verisini yeniden yükler:  psql "$TEST_DATABASE_URL" -f tests/e2e/reset-local.sql
do $$
begin
  -- Barındırılan Supabase bağlantıları yerel (loopback) adres değildir
  if inet_server_addr() is not null and host(inet_server_addr()) not in ('127.0.0.1', '::1') then
    raise exception 'Güvenlik: bu betik yalnızca yerel (127.0.0.1) test veritabanında çalışır.';
  end if;
  if (select count(*) from auth.users where email not like '%@test.local') > 0 then
    raise exception 'Güvenlik: test dışı kullanıcı bulundu; bu bir gerçek proje veritabanı olabilir. Betik durduruldu.';
  end if;
end $$;
begin;
select set_config('app.seeding', 'on', true);
delete from public.technical_documents;
delete from public.purchases;
delete from public.media_files;
delete from public.simulations;
delete from public.progress_updates;
delete from public.project_tasks;
delete from public.materials;
update public.project_settings set current_phase_id = null;
delete from public.project_phases;
delete from public.project_components;
delete from public.project_settings;
commit;
\i supabase/migrations/20261022000004_seed.sql
delete from public.activity_logs;
