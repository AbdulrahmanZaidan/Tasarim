-- =====================================================================
-- 0002 · Güvenlik: rol yardımcıları, tetikleyiciler, etkinlik günlüğü, RLS, yetkiler
-- Güvenlik sınırı veritabanıdır; arayüzdeki rol kontrolleri yalnızca kullanım kolaylığıdır.
-- =====================================================================

-- ---------- Rol yardımcıları ----------
create or replace function public.current_app_role()
returns public.app_role
language sql stable security definer set search_path = ''
as $$
  select p.role from public.profiles p where p.id = (select auth.uid())
$$;

create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = ''
as $$ select coalesce(public.current_app_role() = 'admin', false) $$;

create or replace function public.can_edit()
returns boolean language sql stable security definer set search_path = ''
as $$ select coalesce(public.current_app_role() in ('admin', 'editor'), false) $$;

create or replace function public.can_view_private()
returns boolean language sql stable security definer set search_path = ''
as $$ select public.current_app_role() is not null $$;

-- ---------- Yeni Auth kullanıcısı → profil (varsayılan rol: viewer) ----------
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, email, full_name, role)
  values (new.id, new.email, nullif(btrim(new.raw_user_meta_data ->> 'full_name'), ''), 'viewer')
  on conflict (id) do nothing;
  return new;
end $$;

create or replace function public.handle_user_email_change()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  if new.email is distinct from old.email then
    update public.profiles set email = new.email where id = new.id;
  end if;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();
drop trigger if exists on_auth_user_email_changed on auth.users;
create trigger on_auth_user_email_changed after update of email on auth.users
  for each row execute function public.handle_user_email_change();

-- Geçiş öncesinde oluşturulmuş kullanıcılar için profil
insert into public.profiles (id, email, role)
select u.id, u.email, 'viewer' from auth.users u
on conflict (id) do nothing;

-- ---------- Profil koruması: rol yalnızca yönetici tarafından değiştirilir ----------
create or replace function public.tg_profiles_guard()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  if new.id <> old.id then
    raise exception 'Profil kimliği değiştirilemez.' using errcode = '42501';
  end if;
  -- API üzerinden gelen istekler (auth.uid() dolu). SQL düzenleyicisi ve Auth hizmeti muaftır.
  if (select auth.uid()) is not null then
    if new.email is distinct from old.email then
      new.email := old.email;  -- e-posta Supabase Auth ile eşitlenir
    end if;
    if new.role <> old.role then
      if not public.is_admin() then
        raise exception 'Rol değiştirme yetkiniz yok.' using errcode = '42501';
      end if;
    end if;
  end if;
  if old.role = 'admin' and new.role <> 'admin'
     and (select count(*) from public.profiles where role = 'admin') <= 1 then
    raise exception 'Sistemde en az bir yönetici kalmalıdır.' using errcode = '23514';
  end if;
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists profiles_guard on public.profiles;
create trigger profiles_guard before update on public.profiles
  for each row execute function public.tg_profiles_guard();

-- SQL düzenleyicisinden ilk yöneticiyi atamak için (istemcilere kapalı)
create or replace function public.set_user_role(target_email text, new_role public.app_role)
returns void language plpgsql security definer set search_path = ''
as $$
begin
  if (select auth.uid()) is not null and not public.is_admin() then
    raise exception 'Bu işlem için yönetici yetkisi gerekir.' using errcode = '42501';
  end if;
  update public.profiles set role = new_role where lower(email) = lower(btrim(target_email));
  if not found then
    raise exception 'Bu e-posta ile kayıtlı kullanıcı bulunamadı: %', target_email using errcode = 'P0002';
  end if;
end $$;
revoke all on function public.set_user_role(text, public.app_role) from public, anon, authenticated;

-- ---------- Ortak zaman/sahiplik damgası ----------
-- Argümanlar: 1) oluşturan sütunu ('-' = yok), 2) güncelleyen sütunu (isteğe bağlı)
create or replace function public.tg_stamp()
returns trigger language plpgsql set search_path = ''
as $$
declare
  uid uuid := (select auth.uid());
  patch jsonb := jsonb_build_object('updated_at', now());
begin
  -- Satın alma eşitlemesi sırasında malzemenin güncellenme zamanı değişmez
  if tg_op = 'UPDATE' and coalesce(current_setting('app.qty_sync', true), '') = 'on' then
    return new;
  end if;
  if tg_op = 'INSERT' then
    if uid is not null then
      patch := patch || jsonb_build_object('created_at', now());
      if tg_nargs > 0 and tg_argv[0] <> '-' then
        patch := patch || jsonb_build_object(tg_argv[0], uid);
      end if;
    end if;
  else
    -- Oluşturan ve oluşturulma zamanı sonradan değiştirilemez
    patch := patch || jsonb_build_object('created_at', to_jsonb(old) -> 'created_at');
    if tg_nargs > 0 and tg_argv[0] <> '-' then
      patch := patch || jsonb_build_object(tg_argv[0], to_jsonb(old) -> tg_argv[0]);
    end if;
  end if;
  if tg_nargs > 1 and uid is not null then
    patch := patch || jsonb_build_object(tg_argv[1], uid);
  end if;
  return jsonb_populate_record(new, patch);
end $$;

drop trigger if exists stamp on public.project_phases;
create trigger stamp before insert or update on public.project_phases for each row execute function public.tg_stamp('-');
drop trigger if exists stamp on public.project_settings;
create trigger stamp before insert or update on public.project_settings for each row execute function public.tg_stamp('-', 'updated_by');
drop trigger if exists stamp on public.project_components;
create trigger stamp before insert or update on public.project_components for each row execute function public.tg_stamp('-');
drop trigger if exists stamp on public.project_tasks;
create trigger stamp before insert or update on public.project_tasks for each row execute function public.tg_stamp('created_by');
drop trigger if exists stamp on public.simulations;
create trigger stamp before insert or update on public.simulations for each row execute function public.tg_stamp('created_by', 'updated_by');
drop trigger if exists stamp on public.progress_updates;
create trigger stamp before insert or update on public.progress_updates for each row execute function public.tg_stamp('created_by');
drop trigger if exists stamp on public.media_files;
create trigger stamp before insert or update on public.media_files for each row execute function public.tg_stamp('uploaded_by');
drop trigger if exists stamp on public.technical_documents;
create trigger stamp before insert or update on public.technical_documents for each row execute function public.tg_stamp('created_by');
drop trigger if exists stamp on public.materials;
create trigger stamp before insert or update on public.materials for each row execute function public.tg_stamp('-', 'updated_by');
drop trigger if exists stamp on public.purchases;
create trigger stamp before insert or update on public.purchases for each row execute function public.tg_stamp('-');

-- Satın almayı yapan kişi belirtilmezse kaydı giren kullanıcıdır
alter table public.purchases alter column purchased_by set default auth.uid();

-- ---------- Görev tamamlanma zamanı ----------
create or replace function public.tg_task_completion()
returns trigger language plpgsql set search_path = ''
as $$
begin
  if new.status = 'completed' then
    if tg_op = 'INSERT' then
      new.completed_at := coalesce(new.completed_at, now());
    elsif old.status <> 'completed' then
      new.completed_at := case when new.completed_at is distinct from old.completed_at and new.completed_at is not null
                               then new.completed_at else now() end;
    end if;
  else
    new.completed_at := null;
  end if;
  return new;
end $$;
drop trigger if exists task_completion on public.project_tasks;
create trigger task_completion before insert or update on public.project_tasks
  for each row execute function public.tg_task_completion();

-- ---------- Aşama ağırlıkları yalnızca toplu ve doğrulanmış biçimde değişir ----------
create or replace function public.tg_phase_weight_guard()
returns trigger language plpgsql set search_path = ''
as $$
begin
  if coalesce(current_setting('app.phase_weights', true), '') = 'on' then
    return new;
  end if;
  if tg_op = 'INSERT' then
    new.weight := 0;  -- yeni aşama ağırlıksız başlar; ardından ağırlıklar yeniden dağıtılır
  elsif new.weight <> old.weight then
    raise exception 'Aşama ağırlıkları yalnızca “Ağırlıkları kaydet” işlemiyle (toplam 100) değiştirilebilir.' using errcode = '23514';
  end if;
  return new;
end $$;
drop trigger if exists phase_weight_guard on public.project_phases;
create trigger phase_weight_guard before insert or update on public.project_phases
  for each row execute function public.tg_phase_weight_guard();

create or replace function public.set_phase_weights(weights jsonb)
returns void language plpgsql security invoker set search_path = ''
as $$
declare
  total numeric;
  phase_count integer;
  key_count integer;
  updated_count integer;
begin
  if not public.can_edit() then
    raise exception 'Bu işlem için düzenleme yetkisi gerekir.' using errcode = '42501';
  end if;
  if jsonb_typeof(weights) <> 'object' then
    raise exception 'Geçersiz ağırlık verisi.' using errcode = '22023';
  end if;
  select count(*) into phase_count from public.project_phases;
  select count(*), coalesce(sum(value::numeric), 0) into key_count, total from jsonb_each_text(weights);
  if key_count <> phase_count then
    raise exception 'Tüm aşamalar için ağırlık girilmelidir (% / %).', key_count, phase_count using errcode = '22023';
  end if;
  if exists (select 1 from jsonb_each_text(weights) where value::numeric < 0 or value::numeric > 100) then
    raise exception 'Ağırlıklar 0 ile 100 arasında olmalıdır.' using errcode = '22023';
  end if;
  if round(total, 2) <> 100 then
    raise exception 'Ağırlıkların toplamı 100 olmalıdır (şu an %).', round(total, 2) using errcode = '22023';
  end if;
  perform set_config('app.phase_weights', 'on', true);
  update public.project_phases p
     set weight = (weights ->> p.id::text)::numeric
   where weights ? p.id::text;
  get diagnostics updated_count = row_count;
  perform set_config('app.phase_weights', 'off', true);
  if updated_count <> phase_count then
    raise exception 'Ağırlıklar kaydedilemedi: aşama kimlikleri eşleşmiyor.' using errcode = '22023';
  end if;
end $$;

-- ---------- Satın alınan adet: satın alma kayıtlarının toplamı ----------
create or replace function public.tg_material_purchased_qty()
returns trigger language plpgsql set search_path = ''
as $$
begin
  new.purchased_quantity := coalesce((select sum(p.quantity) from public.purchases p where p.material_id = new.id), 0);
  return new;
end $$;
drop trigger if exists material_purchased_qty on public.materials;
create trigger material_purchased_qty before insert or update on public.materials
  for each row execute function public.tg_material_purchased_qty();

create or replace function public.tg_purchases_sync()
returns trigger language plpgsql set search_path = ''
as $$
begin
  perform set_config('app.qty_sync', 'on', true);
  if tg_op in ('INSERT', 'UPDATE') then
    update public.materials set purchased_quantity = purchased_quantity where id = new.material_id;
  end if;
  if tg_op = 'DELETE' or (tg_op = 'UPDATE' and old.material_id <> new.material_id) then
    update public.materials set purchased_quantity = purchased_quantity where id = old.material_id;
  end if;
  perform set_config('app.qty_sync', 'off', true);
  return null;
end $$;
drop trigger if exists purchases_sync on public.purchases;
create trigger purchases_sync after insert or update or delete on public.purchases
  for each row execute function public.tg_purchases_sync();

-- ---------- Yayımlanan belgelerin dosyası herkese açık olmalı ----------
create or replace function public.tg_document_publish_check()
returns trigger language plpgsql set search_path = ''
as $$
begin
  if new.is_published and not exists (
    select 1 from public.media_files m where m.id = new.file_id and m.bucket_name = 'public-media'
  ) then
    raise exception 'Yayımlanan belgenin dosyası herkese açık medya deposunda olmalıdır.' using errcode = '23514';
  end if;
  return new;
end $$;
drop trigger if exists document_publish_check on public.technical_documents;
create trigger document_publish_check before insert or update on public.technical_documents
  for each row execute function public.tg_document_publish_check();

create or replace function public.tg_media_private_check()
returns trigger language plpgsql set search_path = ''
as $$
begin
  if new.bucket_name = 'private-files' and old.bucket_name = 'public-media' and exists (
    select 1 from public.technical_documents d where d.file_id = new.id and d.is_published
  ) then
    raise exception 'Bu dosya yayımlanmış bir belgede kullanılıyor; önce belgenin yayımını kaldırın.' using errcode = '23514';
  end if;
  return new;
end $$;
drop trigger if exists media_private_check on public.media_files;
create trigger media_private_check before update on public.media_files
  for each row execute function public.tg_media_private_check();

-- ---------- Etkinlik günlüğü (istemciler doğrudan yazamaz) ----------
create or replace function public.tg_log_activity()
returns trigger language plpgsql security definer set search_path = ''
as $$
declare
  uid uuid := (select auth.uid());
  etype text := tg_argv[0];
  rec jsonb := case when tg_op = 'DELETE' then to_jsonb(old) else to_jsonb(new) end;
  prev jsonb := case when tg_op = 'UPDATE' then to_jsonb(old) else null end;
  ignored text[] := array['updated_at', 'updated_by', 'created_at', 'purchased_quantity', 'is_public'];
  changes jsonb := '{}'::jsonb;
  k text;
  act text;
  label text;
  details jsonb := '{}'::jsonb;
  short_val jsonb;
  short_prev jsonb;
begin
  if coalesce(current_setting('app.seeding', true), '') = 'on' then return null; end if;
  if tg_table_name = 'materials' and coalesce(current_setting('app.qty_sync', true), '') = 'on' then return null; end if;

  label := left(coalesce(rec ->> 'title', rec ->> 'name', rec ->> 'full_name', rec ->> 'project_title', rec ->> 'email', rec ->> 'id'), 200);

  if tg_op = 'UPDATE' then
    for k in select jsonb_object_keys(rec) loop
      if not (k = any (ignored)) and (rec -> k) is distinct from (prev -> k) then
        short_val := case when jsonb_typeof(rec -> k) = 'string' and char_length(rec ->> k) > 240
                          then to_jsonb(left(rec ->> k, 240) || '…') else rec -> k end;
        short_prev := case when jsonb_typeof(prev -> k) = 'string' and char_length(prev ->> k) > 240
                           then to_jsonb(left(prev ->> k, 240) || '…') else prev -> k end;
        changes := changes || jsonb_build_object(k, jsonb_build_array(short_prev, short_val));
      end if;
    end loop;
    if changes = '{}'::jsonb then return null; end if;
    details := jsonb_build_object('changes', changes);
  end if;

  act := etype || '.' || case tg_op when 'INSERT' then 'created' when 'DELETE' then 'deleted' else 'updated' end;
  if etype = 'task' and tg_op = 'UPDATE' and changes ? 'status' and rec ->> 'status' = 'completed' then act := 'task.completed'; end if;
  if etype = 'phase' and tg_op = 'UPDATE' and changes ? 'status' then act := 'phase.status_changed'; end if;
  if etype = 'simulation' and tg_op = 'UPDATE' and changes ? 'result_status' then act := 'simulation.result_changed'; end if;
  if etype = 'media' and tg_op = 'INSERT' then act := 'media.uploaded'; end if;
  if etype = 'purchase' and tg_op = 'INSERT' then act := 'purchase.recorded'; end if;
  if etype = 'profile' and tg_op = 'UPDATE' and changes ? 'role' then act := 'profile.role_changed'; end if;

  if etype = 'media' and tg_op in ('INSERT', 'DELETE') then
    details := details || jsonb_build_object('bucket', rec ->> 'bucket_name', 'category', rec ->> 'category',
      'file', rec ->> 'original_file_name', 'size', rec -> 'file_size');
  elsif etype = 'purchase' and tg_op in ('INSERT', 'DELETE') then
    details := details || jsonb_build_object('quantity', rec -> 'quantity', 'unit_price', rec -> 'unit_price',
      'currency', rec ->> 'currency', 'material_id', rec ->> 'material_id');
    label := coalesce((select m.name from public.materials m where m.id = (rec ->> 'material_id')::uuid), label);
  end if;

  insert into public.activity_logs (actor_id, actor_email, action, entity_type, entity_id, entity_label, details)
  values ((select p.id from public.profiles p where p.id = uid),
          (select p.email from public.profiles p where p.id = uid),
          act, etype, rec ->> 'id', label, details);
  return null;
end $$;

do $$
declare t record;
begin
  for t in select * from (values
      ('project_settings', 'settings'), ('project_phases', 'phase'), ('project_components', 'component'),
      ('project_tasks', 'task'), ('simulations', 'simulation'), ('progress_updates', 'progress'),
      ('media_files', 'media'), ('technical_documents', 'document'), ('materials', 'material'),
      ('purchases', 'purchase'), ('profiles', 'profile')) as v(tbl, etype)
  loop
    execute format('drop trigger if exists log_activity on public.%I', t.tbl);
    execute format('create trigger log_activity after insert or update or delete on public.%I
                    for each row execute function public.tg_log_activity(%L)', t.tbl, t.etype);
  end loop;
end $$;

-- ---------- Satır düzeyi güvenlik (RLS) ----------
alter table public.profiles            enable row level security;
alter table public.project_settings    enable row level security;
alter table public.project_phases      enable row level security;
alter table public.project_components  enable row level security;
alter table public.project_tasks       enable row level security;
alter table public.simulations         enable row level security;
alter table public.progress_updates    enable row level security;
alter table public.media_files         enable row level security;
alter table public.technical_documents enable row level security;
alter table public.materials           enable row level security;
alter table public.purchases           enable row level security;
alter table public.activity_logs       enable row level security;

-- Profiller
drop policy if exists "profiles: kendi profili veya ekip" on public.profiles;
create policy "profiles: kendi profili veya ekip" on public.profiles for select to authenticated
  using (id = (select auth.uid()) or (select public.can_view_private()));
drop policy if exists "profiles: kendi adını veya yönetici" on public.profiles;
create policy "profiles: kendi adını veya yönetici" on public.profiles for update to authenticated
  using (id = (select auth.uid()) or (select public.is_admin()))
  with check (id = (select auth.uid()) or (select public.is_admin()));

-- Herkese açık okunan, düzenleyicilerin yazdığı tablolar
do $$
declare tbl text;
begin
  foreach tbl in array array['project_phases', 'project_components', 'project_tasks', 'materials', 'purchases'] loop
    execute format('drop policy if exists "herkes okur" on public.%I', tbl);
    execute format('create policy "herkes okur" on public.%I for select to anon, authenticated using (true)', tbl);
    execute format('drop policy if exists "düzenleyici ekler" on public.%I', tbl);
    execute format('create policy "düzenleyici ekler" on public.%I for insert to authenticated with check ((select public.can_edit()))', tbl);
    execute format('drop policy if exists "düzenleyici günceller" on public.%I', tbl);
    execute format('create policy "düzenleyici günceller" on public.%I for update to authenticated using ((select public.can_edit())) with check ((select public.can_edit()))', tbl);
    execute format('drop policy if exists "düzenleyici siler" on public.%I', tbl);
    execute format('create policy "düzenleyici siler" on public.%I for delete to authenticated using ((select public.can_edit()))', tbl);
  end loop;
end $$;

-- Yayın durumuna bağlı tablolar: ziyaretçi yalnızca yayımlananı görür
do $$
declare tbl text;
begin
  foreach tbl in array array['simulations', 'progress_updates', 'technical_documents'] loop
    execute format('drop policy if exists "yayımlanan veya ekip okur" on public.%I', tbl);
    execute format('create policy "yayımlanan veya ekip okur" on public.%I for select to anon, authenticated using (is_published or (select public.can_view_private()))', tbl);
    execute format('drop policy if exists "düzenleyici ekler" on public.%I', tbl);
    execute format('create policy "düzenleyici ekler" on public.%I for insert to authenticated with check ((select public.can_edit()))', tbl);
    execute format('drop policy if exists "düzenleyici günceller" on public.%I', tbl);
    execute format('create policy "düzenleyici günceller" on public.%I for update to authenticated using ((select public.can_edit())) with check ((select public.can_edit()))', tbl);
    execute format('drop policy if exists "düzenleyici siler" on public.%I', tbl);
    execute format('create policy "düzenleyici siler" on public.%I for delete to authenticated using ((select public.can_edit()))', tbl);
  end loop;
end $$;

-- Medya: herkese açık depodakiler herkese, özel depodakiler yalnızca ekibe görünür
drop policy if exists "açık medya veya ekip okur" on public.media_files;
create policy "açık medya veya ekip okur" on public.media_files for select to anon, authenticated
  using (bucket_name = 'public-media' or (select public.can_view_private()));
drop policy if exists "düzenleyici ekler" on public.media_files;
create policy "düzenleyici ekler" on public.media_files for insert to authenticated with check ((select public.can_edit()));
drop policy if exists "düzenleyici günceller" on public.media_files;
create policy "düzenleyici günceller" on public.media_files for update to authenticated
  using ((select public.can_edit())) with check ((select public.can_edit()));
drop policy if exists "düzenleyici siler" on public.media_files;
create policy "düzenleyici siler" on public.media_files for delete to authenticated using ((select public.can_edit()));

-- Proje ayarları: herkes okur, yalnızca yönetici günceller (ekleme/silme yok)
drop policy if exists "herkes okur" on public.project_settings;
create policy "herkes okur" on public.project_settings for select to anon, authenticated using (true);
drop policy if exists "yönetici günceller" on public.project_settings;
create policy "yönetici günceller" on public.project_settings for update to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));

-- Etkinlik günlüğü: yalnızca yönetici ve düzenleyici okur; kimse yazamaz/silemez
drop policy if exists "yönetici ve düzenleyici okur" on public.activity_logs;
create policy "yönetici ve düzenleyici okur" on public.activity_logs for select to authenticated
  using ((select public.can_edit()));

-- ---------- Tablo yetkileri (RLS'e ek savunma katmanı) ----------
revoke all on all tables in schema public from anon, authenticated;
grant select on public.project_settings, public.project_phases, public.project_components, public.project_tasks,
  public.simulations, public.progress_updates, public.media_files, public.technical_documents,
  public.materials, public.purchases to anon, authenticated;
grant insert, update, delete on public.project_phases, public.project_components, public.project_tasks,
  public.simulations, public.progress_updates, public.media_files, public.technical_documents,
  public.materials, public.purchases to authenticated;
grant update on public.project_settings to authenticated;
grant select, update (full_name, role) on public.profiles to authenticated;
grant select on public.activity_logs to authenticated;

revoke all on function public.set_phase_weights(jsonb) from public, anon;
grant execute on function public.set_phase_weights(jsonb) to authenticated;
grant execute on function public.current_app_role(), public.is_admin(), public.can_edit(), public.can_view_private() to anon, authenticated;
revoke all on function public.handle_new_user(), public.handle_user_email_change() from public, anon, authenticated;

-- PostgREST şema önbelleğini yenile (barındırılan Supabase'de zararsızdır)
notify pgrst, 'reload schema';
