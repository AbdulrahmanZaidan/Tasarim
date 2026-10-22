-- 8-Bit Breadboard Bilgisayar · Tek dosyalık kurulum betiği
-- Bu dosya supabase/migrations/ klasöründeki dosyaların sıralı birleşimidir (node scripts/generate-seed.mjs ile üretilir).
-- Supabase panelinde SQL Editor'a yapıştırıp çalıştırın. Tekrar çalıştırmak güvenlidir; veri silinmez.

-- >>> 20261022000001_schema.sql
-- =====================================================================
-- 8-Bit Breadboard Bilgisayar · Proje yönetim platformu
-- 0001 · Şema: türler, tablolar, kısıtlar, dizinler
-- Tekrar çalıştırılabilir (idempotent): mevcut nesneler korunur, veri silinmez.
-- =====================================================================

-- ---------- Sayım (enum) türleri ----------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'app_role' and typnamespace = 'public'::regnamespace) then
    create type public.app_role as enum ('admin', 'editor', 'viewer');
  end if;
  if not exists (select 1 from pg_type where typname = 'semester' and typnamespace = 'public'::regnamespace) then
    create type public.semester as enum ('tasarim_1', 'tasarim_2');
  end if;
  if not exists (select 1 from pg_type where typname = 'phase_status' and typnamespace = 'public'::regnamespace) then
    create type public.phase_status as enum ('planned', 'not_started', 'in_progress', 'completed', 'blocked');
  end if;
  if not exists (select 1 from pg_type where typname = 'work_status' and typnamespace = 'public'::regnamespace) then
    -- Görevler, bileşenler ve ilerleme kayıtları için ortak durum kümesi
    create type public.work_status as enum ('not_started', 'in_progress', 'completed', 'blocked');
  end if;
  if not exists (select 1 from pg_type where typname = 'task_priority' and typnamespace = 'public'::regnamespace) then
    create type public.task_priority as enum ('low', 'medium', 'high');
  end if;
  if not exists (select 1 from pg_type where typname = 'experiment_result' and typnamespace = 'public'::regnamespace) then
    create type public.experiment_result as enum ('not_started', 'in_progress', 'passed', 'failed', 'needs_review');
  end if;
  if not exists (select 1 from pg_type where typname = 'purchase_status' and typnamespace = 'public'::regnamespace) then
    create type public.purchase_status as enum ('not_purchased', 'ordered', 'received', 'tested');
  end if;
  if not exists (select 1 from pg_type where typname = 'media_category' and typnamespace = 'public'::regnamespace) then
    create type public.media_category as enum (
      'simulation_screenshot', 'architecture_diagram', 'circuit_schematic', 'breadboard_photo',
      'component_photo', 'testing_evidence', 'report', 'technical_file', 'receipt');
  end if;
  if not exists (select 1 from pg_type where typname = 'document_type' and typnamespace = 'public'::regnamespace) then
    create type public.document_type as enum (
      'project_report', 'circuit_schematic', 'architecture_document', 'simulation_report',
      'datasheet', 'test_report', 'meeting_notes', 'graduation_deliverable');
  end if;
end $$;

-- Sonradan eklenen değerler (eski kurulumları yükseltmek için)
alter type public.media_category add value if not exists 'receipt';

-- ---------- Kullanıcı profilleri (Supabase Auth ile 1:1) ----------
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  full_name   text check (char_length(full_name) <= 120),
  email       text,
  role        public.app_role not null default 'viewer',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- ---------- Proje aşamaları (Tasarım I / Tasarım II) ----------
create table if not exists public.project_phases (
  id           uuid primary key default gen_random_uuid(),
  slug         text not null unique check (slug ~ '^[a-z0-9-]{2,40}$'),
  title        text not null check (char_length(title) between 2 and 160),
  short_title  text check (char_length(short_title) <= 40),
  description  text check (char_length(description) <= 4000),
  deliverable  text check (char_length(deliverable) <= 400),
  semester     public.semester not null,
  status       public.phase_status not null default 'planned',
  -- Genel ilerleme hesabındaki ağırlık (tüm aşamaların toplamı 100 olmalıdır)
  weight       numeric(5,2) not null default 0 check (weight >= 0 and weight <= 100),
  start_date   date,
  target_date  date,
  route        text check (route is null or route ~ '^/[a-z0-9/-]*$'),
  sort_order   integer not null default 0,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint phase_dates_ok check (target_date is null or start_date is null or target_date >= start_date)
);

-- ---------- Proje ayarları (tek satır) ----------
create table if not exists public.project_settings (
  id                   boolean primary key default true check (id),
  project_title        text not null default '8-Bit Breadboard Bilgisayar',
  project_subtitle     text,
  project_description  text check (char_length(project_description) <= 4000),
  university           text,
  course               text,
  supervisor           text,
  -- [{ "name": "...", "student_id": "..." }]
  team_members         jsonb not null default '[]'::jsonb check (jsonb_typeof(team_members) = 'array'),
  academic_year        text,
  github_url           text check (github_url is null or github_url ~ '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$'),
  project_status       text,
  current_phase_id     uuid references public.project_phases (id) on delete set null,
  default_currency     char(3) not null default 'TRY' check (default_currency ~ '^[A-Z]{3}$'),
  -- Döviz kuru yalnızca açıkça kaydedildiğinde birleşik toplam gösterilir
  usd_try_rate         numeric(12,4) check (usd_try_rate is null or usd_try_rate > 0),
  usd_try_rate_date    date,
  tasarim_ii_active    boolean not null default false,
  updated_at           timestamptz not null default now(),
  updated_by           uuid references public.profiles (id) on delete set null,
  constraint rate_has_date check (usd_try_rate is null or usd_try_rate_date is not null)
);

-- ---------- Bilgisayar bileşenleri / modüller ----------
create table if not exists public.project_components (
  id                  uuid primary key default gen_random_uuid(),
  slug                text not null unique check (slug ~ '^[a-z0-9-]{2,40}$'),
  name                text not null check (char_length(name) between 2 and 120),
  name_en             text check (char_length(name_en) <= 120),
  description         text check (char_length(description) <= 4000),
  architecture_notes  text check (char_length(architecture_notes) <= 20000),
  status              public.work_status not null default 'not_started',
  sort_order          integer not null default 0,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

-- ---------- Görevler ----------
create table if not exists public.project_tasks (
  id            uuid primary key default gen_random_uuid(),
  phase_id      uuid not null references public.project_phases (id) on delete cascade,
  component_id  uuid references public.project_components (id) on delete set null,
  title         text not null check (char_length(title) between 2 and 200),
  description   text check (char_length(description) <= 4000),
  status        public.work_status not null default 'not_started',
  priority      public.task_priority not null default 'medium',
  -- Aşama ilerlemesi, tamamlanan görevlerin ağırlık oranıdır
  weight        numeric(6,2) not null default 1 check (weight > 0 and weight <= 1000),
  assigned_to   uuid references public.profiles (id) on delete set null,
  due_date      date,
  completed_at  timestamptz,
  sort_order    integer not null default 0,
  created_by    uuid references public.profiles (id) on delete set null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- ---------- Simülasyon deneyleri ----------
create table if not exists public.simulations (
  id                    uuid primary key default gen_random_uuid(),
  component_id          uuid references public.project_components (id) on delete set null,
  title                 text not null check (char_length(title) between 3 and 200),
  description           text check (char_length(description) <= 4000),
  software_used         text not null default 'Digital' check (char_length(software_used) between 2 and 60),
  software_version      text check (char_length(software_version) <= 40),
  experiment_objective  text check (char_length(experiment_objective) <= 4000),
  methodology           text check (char_length(methodology) <= 8000),
  input_values          text check (char_length(input_values) <= 4000),
  operation             text check (char_length(operation) <= 400),
  expected_output       text check (char_length(expected_output) <= 4000),
  actual_output         text check (char_length(actual_output) <= 4000),
  result_status         public.experiment_result not null default 'not_started',
  notes                 text check (char_length(notes) <= 8000),
  conclusion            text check (char_length(conclusion) <= 4000),
  experiment_date       date,
  is_published          boolean not null default false,
  created_by            uuid references public.profiles (id) on delete set null,
  updated_by            uuid references public.profiles (id) on delete set null,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  -- "Başarılı" veya "Başarısız" sonucu, gözlenen çıktı ve deney tarihi kaydedilmeden verilemez
  constraint result_needs_evidence check (
    result_status not in ('passed', 'failed')
    or (coalesce(btrim(actual_output), '') <> '' and experiment_date is not null)
  )
);

-- ---------- İlerleme kayıtları / kilometre taşları ----------
create table if not exists public.progress_updates (
  id              uuid primary key default gen_random_uuid(),
  phase_id        uuid references public.project_phases (id) on delete set null,
  component_id    uuid references public.project_components (id) on delete set null,
  title           text not null check (char_length(title) between 3 and 200),
  description     text check (char_length(description) <= 8000),
  status          public.work_status not null default 'completed',
  -- İsteğe bağlı, o tarihteki kaydedilmiş yüzde (bilgi amaçlı; hesaplamada kullanılmaz)
  progress_value  numeric(5,2) check (progress_value is null or (progress_value >= 0 and progress_value <= 100)),
  update_date     date not null default current_date,
  is_published    boolean not null default true,
  created_by      uuid references public.profiles (id) on delete set null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- ---------- Medya dosyaları (içerik Storage'da, burada yalnızca meta veri) ----------
create table if not exists public.media_files (
  id                  uuid primary key default gen_random_uuid(),
  file_name           text not null check (file_name ~ '^[a-f0-9-]{36}\.[a-z0-9]{1,8}$'),
  original_file_name  text not null check (char_length(original_file_name) between 1 and 255),
  storage_path        text not null check (storage_path !~ '\.\.' and storage_path ~ '^[a-z_]+/[0-9]{4}/[a-f0-9-]{36}\.[a-z0-9]{1,8}$'),
  bucket_name         text not null check (bucket_name in ('public-media', 'private-files')),
  mime_type           text not null check (char_length(mime_type) <= 120),
  file_size           bigint not null check (file_size > 0 and file_size <= 52428800),
  title               text not null check (char_length(title) between 1 and 200),
  description         text check (char_length(description) <= 4000),
  category            public.media_category not null,
  component_id        uuid references public.project_components (id) on delete set null,
  simulation_id       uuid references public.simulations (id) on delete set null,
  progress_update_id  uuid references public.progress_updates (id) on delete set null,
  is_public           boolean generated always as (bucket_name = 'public-media') stored,
  uploaded_by         uuid references public.profiles (id) on delete set null,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  unique (bucket_name, storage_path)
);

-- ---------- Teknik belgeler ----------
create table if not exists public.technical_documents (
  id             uuid primary key default gen_random_uuid(),
  title          text not null check (char_length(title) between 3 and 200),
  description    text check (char_length(description) <= 4000),
  document_type  public.document_type not null,
  -- Belgeye bağlı dosya silinemez (önce belge silinmeli veya dosya değiştirilmelidir)
  file_id        uuid not null references public.media_files (id) on delete restrict,
  component_id   uuid references public.project_components (id) on delete set null,
  version        text not null default '1.0' check (version ~ '^[0-9A-Za-z.\-]{1,20}$'),
  is_published   boolean not null default false,
  created_by     uuid references public.profiles (id) on delete set null,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

-- ---------- Malzemeler ----------
create table if not exists public.materials (
  id                    uuid primary key default gen_random_uuid(),
  slug                  text not null unique check (slug ~ '^[a-z0-9-]{2,60}$'),
  name                  text not null check (char_length(name) between 2 and 200),
  source_name           text check (char_length(source_name) <= 200),
  category              text not null check (char_length(category) between 2 and 80),
  description           text check (char_length(description) <= 2000),
  required_quantity     integer not null default 0 check (required_quantity >= 0 and required_quantity <= 100000),
  -- Satın alma kayıtlarından tetikleyici ile hesaplanır; doğrudan değiştirilemez
  purchased_quantity    integer not null default 0 check (purchased_quantity >= 0),
  -- Referans liste değerleri (tarihsel, USD); değiştirilmeden saklanır
  ref_quantity          integer check (ref_quantity >= 0),
  ref_unit_price_min    numeric(12,2) check (ref_unit_price_min >= 0),
  ref_unit_price_max    numeric(12,2) check (ref_unit_price_max >= 0),
  ref_stated_total_min  numeric(12,2) check (ref_stated_total_min >= 0),
  ref_stated_total_max  numeric(12,2) check (ref_stated_total_max >= 0),
  ref_currency          char(3) not null default 'USD' check (ref_currency ~ '^[A-Z]{3}$'),
  -- Güncel birim fiyat teklifi (yerel); varsayılan para birimi TL
  unit_price            numeric(12,2) check (unit_price is null or unit_price >= 0),
  currency              char(3) not null default 'TRY' check (currency ~ '^[A-Z]{3}$'),
  supplier              text check (char_length(supplier) <= 120),
  product_url           text check (product_url is null or product_url ~ '^https?://'),
  purchase_status       public.purchase_status not null default 'not_purchased',
  is_programmer_extra   boolean not null default false,
  notes                 text check (char_length(notes) <= 4000),
  sort_order            integer not null default 0,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  updated_by            uuid references public.profiles (id) on delete set null,
  constraint ref_price_order check (ref_unit_price_max is null or ref_unit_price_min is null or ref_unit_price_max >= ref_unit_price_min)
);

-- ---------- Satın almalar ----------
create table if not exists public.purchases (
  id               uuid primary key default gen_random_uuid(),
  -- Satın alma kaydı olan malzeme silinemez (mali kayıt kaybını önler)
  material_id      uuid not null references public.materials (id) on delete restrict,
  quantity         integer not null check (quantity > 0 and quantity <= 100000),
  unit_price       numeric(12,2) check (unit_price is null or unit_price >= 0),
  currency         char(3) not null default 'TRY' check (currency ~ '^[A-Z]{3}$'),
  purchase_date    date not null,
  supplier         text check (char_length(supplier) <= 120),
  receipt_file_id  uuid references public.media_files (id) on delete restrict,
  purchased_by     uuid references public.profiles (id) on delete set null,
  notes            text check (char_length(notes) <= 2000),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

-- ---------- Etkinlik günlüğü (yalnızca tetikleyiciler yazar) ----------
create table if not exists public.activity_logs (
  id           bigint generated always as identity primary key,
  actor_id     uuid references public.profiles (id) on delete set null,
  actor_email  text,
  action       text not null,
  entity_type  text not null,
  entity_id    text,
  entity_label text,
  details      jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now()
);

-- ---------- Dizinler ----------
create index if not exists idx_phases_sort on public.project_phases (semester, sort_order);
create index if not exists idx_components_sort on public.project_components (sort_order);
create index if not exists idx_tasks_phase on public.project_tasks (phase_id, sort_order);
create index if not exists idx_tasks_component on public.project_tasks (component_id);
create index if not exists idx_tasks_status_due on public.project_tasks (status, due_date);
create index if not exists idx_tasks_assigned on public.project_tasks (assigned_to);
create index if not exists idx_sims_component on public.simulations (component_id);
create index if not exists idx_sims_published on public.simulations (is_published, experiment_date desc);
create index if not exists idx_progress_date on public.progress_updates (update_date desc);
create index if not exists idx_progress_phase on public.progress_updates (phase_id);
create index if not exists idx_progress_component on public.progress_updates (component_id);
create index if not exists idx_media_created on public.media_files (created_at desc);
create index if not exists idx_media_component on public.media_files (component_id);
create index if not exists idx_media_simulation on public.media_files (simulation_id);
create index if not exists idx_media_progress on public.media_files (progress_update_id);
create index if not exists idx_media_category on public.media_files (category);
create index if not exists idx_docs_component on public.technical_documents (component_id);
create index if not exists idx_docs_file on public.technical_documents (file_id);
create index if not exists idx_materials_category on public.materials (category, sort_order);
create index if not exists idx_purchases_material on public.purchases (material_id);
create index if not exists idx_purchases_date on public.purchases (purchase_date desc);
create index if not exists idx_purchases_receipt on public.purchases (receipt_file_id);
create index if not exists idx_activity_created on public.activity_logs (created_at desc);
create index if not exists idx_activity_entity on public.activity_logs (entity_type, entity_id);


-- >>> 20261022000002_security.sql
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


-- >>> 20261022000003_storage.sql
-- =====================================================================
-- 0003 · Supabase Storage: depolar (bucket) ve erişim ilkeleri
--   public-media   → yayımlanan görseller, PDF'ler ve indirilebilir simülasyon dosyaları (herkese açık okuma)
--                    HTML, SVG ve XML gibi tarayıcıda çalışabilen türler bu depoya yüklenemez.
--   private-files  → özel dosyalar, simülasyon kaynak dosyaları, makbuzlar (yalnızca ekip)
-- Yol biçimi: <kategori>/<yıl>/<uuid>.<uzantı>  (özgün dosya adı yol olarak kullanılmaz)
-- =====================================================================

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('public-media', 'public-media', true, 20971520,
   array['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'application/pdf',
         'application/octet-stream', 'application/zip', 'application/x-zip-compressed', 'text/plain', 'text/csv']),
  ('private-files', 'private-files', false, 52428800,
   array['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'application/pdf',
         'application/zip', 'application/x-zip-compressed', 'text/plain', 'text/csv',
         'application/xml', 'text/xml', 'application/octet-stream',
         'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
         'application/vnd.openxmlformats-officedocument.presentationml.presentation'])
on conflict (id) do update
  set public = excluded.public,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- İzin verilen klasör (kategori) ve uzantı kontrolü
create or replace function public.storage_path_allowed(bucket text, object_name text)
returns boolean language sql immutable set search_path = ''
as $$
  select
    (string_to_array(object_name, '/'))[1] = any (array[
      'simulation_screenshot', 'architecture_diagram', 'circuit_schematic', 'breadboard_photo',
      'component_photo', 'testing_evidence', 'report', 'technical_file', 'receipt'])
    and object_name ~ '^[a-z_]+/[0-9]{4}/[a-f0-9-]{36}\.[a-z0-9]{1,8}$'
    and lower(substring(object_name from '\.([a-z0-9]{1,8})$')) = any (
      case bucket
        when 'public-media' then array['png', 'jpg', 'jpeg', 'webp', 'gif', 'pdf', 'zip', 'txt', 'csv',
                                       'dig', 'circ', 'pdsprj', 'hex', 'bin', 'asm', 'ino']
        when 'private-files' then array['png', 'jpg', 'jpeg', 'webp', 'gif', 'pdf', 'zip', 'txt', 'csv',
                                        'xml', 'dig', 'circ', 'pdsprj', 'hex', 'bin', 'asm', 'ino',
                                        'docx', 'xlsx', 'pptx']
        else array[]::text[]
      end)
$$;
grant execute on function public.storage_path_allowed(text, text) to anon, authenticated;

drop policy if exists "medya: açık depo herkese görünür" on storage.objects;
create policy "medya: açık depo herkese görünür" on storage.objects for select to anon, authenticated
  using (bucket_id = 'public-media');

drop policy if exists "medya: özel depo yalnızca ekibe" on storage.objects;
create policy "medya: özel depo yalnızca ekibe" on storage.objects for select to authenticated
  using (bucket_id = 'private-files' and (select public.can_view_private()));

drop policy if exists "medya: düzenleyici yükler" on storage.objects;
create policy "medya: düzenleyici yükler" on storage.objects for insert to authenticated
  with check (
    bucket_id in ('public-media', 'private-files')
    and (select public.can_edit())
    and public.storage_path_allowed(bucket_id, name)
  );

drop policy if exists "medya: düzenleyici günceller" on storage.objects;
create policy "medya: düzenleyici günceller" on storage.objects for update to authenticated
  using (bucket_id in ('public-media', 'private-files') and (select public.can_edit()))
  with check (
    bucket_id in ('public-media', 'private-files')
    and (select public.can_edit())
    and public.storage_path_allowed(bucket_id, name)
  );

drop policy if exists "medya: düzenleyici siler" on storage.objects;
create policy "medya: düzenleyici siler" on storage.objects for delete to authenticated
  using (bucket_id in ('public-media', 'private-files') and (select public.can_edit()));


-- >>> 20261022000004_seed.sql
-- =====================================================================
-- 0004 · Başlangıç verisi (scripts/generate-seed.mjs tarafından üretilmiştir — elle düzenlemeyin)
-- Kaynak: src/data/fallback.ts (projectData.ts, parts.ts, architecture.ts)
-- Tekrar çalıştırılabilir: mevcut kayıtlar değiştirilmez (on conflict do nothing).
-- Simülasyon sonucu, satın alma veya kanıtsız tamamlanmış iş UYDURULMAZ.
-- =====================================================================
begin;
select set_config('app.seeding', 'on', true), set_config('app.phase_weights', 'on', true);

insert into public.project_settings (id, project_title, project_subtitle, project_description, university, course, supervisor, team_members, github_url, project_status, default_currency, tasarim_ii_active)
values (true, '8-Bit Breadboard Bilgisayar', 'Sıfırdan Tasarlanan Programlanabilir 8-Bit Bilgisayar', 'Bu bitirme projesinin amacı, yalnızca temel dijital mantık entegre devreleri kullanılarak programlanabilir bir 8-bit bilgisayarın tasarlanması ve ikinci dönemde breadboard’lar üzerinde fiziksel olarak gerçekleştirilmesidir.', 'Süleyman Demirel Üniversitesi', 'Tasarım I · Bitirme Projesi', 'Doç. Dr. Fatih Şenel',
  '[{"name":"Abdelrahman Ahmad Radwan Zidan","student_id":"2321032807"},{"name":"Taha Deniz Akgül","student_id":"2426512003"}]'::jsonb, 'https://github.com/Siiingularity/Tasarim1', 'Hazırlık aşaması', 'TRY', false)
on conflict (id) do nothing;

insert into public.project_phases (slug, title, short_title, description, deliverable, semester, status, weight, route, sort_order)
values
  ('architecture', 'Mimari ve Şema', 'Mimari', 'Bilgisayarın blok diyagramı ile saat, yazmaçlar, ALU, RAM, program sayacı, çıkış ve kontrol biriminin devre şemaları hazırlanır; komut seti ve kontrol sinyalleri belirlenir.', 'Tam devre şeması ve blok diyagram', 'tasarim_1', 'planned', 20, '/proje/mimari-sema', 1),
  ('simulation', 'Simülasyon', 'Simülasyon', 'Devre, Digital (H. Neemann) veya Proteus ortamında kurularak her modül ayrı ayrı test edilir; ardından modüller birleştirilerek örnek programlar çalıştırılır.', 'Çalışan simülasyon ve örnek programlar', 'tasarim_1', 'planned', 20, '/proje/simulasyon', 2),
  ('github', 'GitHub Deposu', 'GitHub', 'Şemalar, simülasyon dosyaları, mikrokod/EEPROM kodları ve dokümanlar GitHub deposunda toplanır; sürüm takibi ve ekip içi iş bölümü buradan yürütülür.', 'Düzenli proje deposu', 'tasarim_1', 'planned', 20, '/proje/github', 3),
  ('materials', 'Malzeme ve Maliyet Analizi', 'Malzeme', 'Malzeme listesi simülasyon sonuçlarına göre kesinleştirilir; entegreler, breadboard’lar ve diğer parçalar temin edilip test edilir. EEPROM programlayıcı hazırlanır.', 'Eksiksiz ve test edilmiş malzeme seti', 'tasarim_1', 'planned', 20, '/proje/malzeme-maliyet', 4),
  ('tasarim2', 'Tasarım II: Uygulamaya Geçiş', 'Tasarım II', 'İkinci dönemde modüller breadboard üzerinde kurulur, test edilir ve birleştirilerek çalışan 8-bit bilgisayar elde edilir.', 'Çalışan 8-bit breadboard bilgisayar', 'tasarim_2', 'not_started', 20, '/proje/tasarim-ii', 5)
on conflict (slug) do nothing;

insert into public.project_components (slug, name, name_en, description, sort_order)
values
  ('clock', 'Saat Devresi', 'Clock Module', 'Bilgisayardaki tüm senkron işlemleri zamanlayan kare dalga üreteci.', 1),
  ('registers', 'A ve B Yazmaçları', 'Registers', 'Her biri 8 bit veri saklayan, ALU’nun iki işlenenini tutan yazmaçlar.', 2),
  ('alu', 'Aritmetik Mantık Birimi', 'ALU', 'A ve B yazmaçlarındaki değerleri toplayan veya çıkaran kombinasyonel devre.', 3),
  ('ram', 'RAM Bellek Modülü', 'RAM & Memory Address Register', '16 adres × 8 bit kapasiteli rastgele erişimli bellek ve onu adresleyen 4-bit bellek adres yazmacı (MAR).', 4),
  ('pc', 'Program Sayacı', 'Program Counter', 'Bir sonraki çalıştırılacak komutun bellek adresini tutan 4-bit sayıcı.', 5),
  ('ir', 'Komut Yazmacı', 'Instruction Register', 'Bellekten okunan geçerli komutu saklayan 8-bit yazmaç.', 6),
  ('control', 'Kontrol Birimi', 'Control Unit', 'Opcode, mikro adım ve bayraklara göre 16 kontrol sinyalini üreten birim.', 7),
  ('bus', 'Ortak Veri Yolu', '8-Bit Bus', 'Tüm modülleri birbirine bağlayan 8 hatlı ortak iletişim yolu.', 8),
  ('output', 'Çıkış Yazmacı', 'Output Register', 'Veri yolundaki 8-bit değeri saklayıp dört adet 7 segment göstergede ondalık olarak gösteren modül.', 9),
  ('eeprom', 'EEPROM ve Mikrokod', 'EEPROM & Microcode', 'Kontrol birimi ve çıkış modülünde kullanılan 28C16 EEPROM’ların içeriği (mikrokod ve 7 segment tabloları) ile bu EEPROM’ları programlamak için kullanılan programlayıcı.', 10),
  ('isa', 'Komut Seti Mimarisi', 'Instruction Set Architecture', 'Bilgisayarın desteklediği komutlar, işlem kodları (opcode) ve her komutun mikro adımları.', 11),
  ('integration', 'Bilgisayarın Bütünleştirilmesi', 'Complete Computer Integration', 'Tüm modüllerin ortak veri yolu ve kontrol birimi üzerinden birleştirilerek tek bir bilgisayar olarak çalıştırılması.', 12)
on conflict (slug) do nothing;

insert into public.project_tasks (phase_id, title, description, status, completed_at, sort_order)
select p.id, v.title, v.description, v.status::public.work_status, v.completed_at::timestamptz, v.sort_order
from (values
  ('architecture', 'Ben Eater referans mimarisinin modül modül incelenmesi', null, 'not_started', null, 1),
  ('architecture', 'Blok diyagramın proje ekibince çizilmesi', null, 'not_started', null, 2),
  ('architecture', 'Modül devre şemalarının hazırlanması', null, 'not_started', null, 3),
  ('architecture', 'Komut seti ve kontrol kelimesinin kesinleştirilmesi', null, 'not_started', null, 4),
  ('architecture', 'Genel blok diyagram', null, 'not_started', null, 5),
  ('architecture', 'Modül devre şemaları', null, 'not_started', null, 6),
  ('architecture', 'Komut seti ve mikrokod tablosu', null, 'not_started', null, 7),
  ('simulation', 'Simülasyon aracının seçilmesi (Digital / Proteus)', null, 'not_started', null, 1),
  ('simulation', 'Saat ve yazmaç modüllerinin simülasyonu', null, 'not_started', null, 2),
  ('simulation', 'ALU, RAM ve program sayacı simülasyonu', null, 'not_started', null, 3),
  ('simulation', 'Kontrol birimi ve tam sistem simülasyonu', null, 'not_started', null, 4),
  ('simulation', 'Modül bazlı simülasyonlar', null, 'not_started', null, 5),
  ('simulation', 'Bütünleşik sistem simülasyonu', null, 'not_started', null, 6),
  ('simulation', 'Örnek programların çalıştırılması', null, 'not_started', null, 7),
  ('github', 'Depo klasör yapısının belirlenmesi', null, 'not_started', null, 1),
  ('github', 'README ve dokümantasyonun eklenmesi', null, 'not_started', null, 2),
  ('github', 'Şema ve simülasyon dosyalarının yüklenmesi', null, 'not_started', null, 3),
  ('github', 'GitHub deposunun oluşturulması', 'Depo github.com/Siiingularity/Tasarim1 adresinde oluşturulmuştur. Tamamlanma tarihi olarak deponun mevcut olduğunun ilk doğrulandığı tarih girilmiştir.', 'completed', '2026-10-20T00:00:00+03:00', 4),
  ('github', 'README ve klasör yapısı', null, 'not_started', null, 5),
  ('github', 'Teknik dosyaların düzenli eklenmesi', null, 'not_started', null, 6),
  ('materials', 'Referans malzeme listesinin çıkarılması', null, 'not_started', null, 1),
  ('materials', 'Türkiye tedarikçilerinden fiyat alınması', null, 'not_started', null, 2),
  ('materials', 'Siparişlerin verilmesi', null, 'not_started', null, 3),
  ('materials', 'Gelen parçaların test edilmesi', null, 'not_started', null, 4),
  ('materials', 'Referans malzeme listesi', null, 'not_started', null, 5),
  ('materials', 'Yerel fiyat teklifleri', null, 'not_started', null, 6),
  ('materials', 'Satın alma ve parça testleri', null, 'not_started', null, 7),
  ('tasarim2', 'Modüllerin Breadboard Üzerinde Kurulması', 'Saat, yazmaçlar, ALU, RAM, program sayacı, çıkış ve kontrol modüllerinin ayrı breadboard’lar üzerinde kurulması.', 'not_started', null, 1),
  ('tasarim2', 'Devrelerin Test Edilmesi', 'Her modülün LED göstergeler ve manuel saat adımlarıyla bağımsız olarak doğrulanması.', 'not_started', null, 2),
  ('tasarim2', 'Veri Yolunun Birleştirilmesi', 'Modüllerin 8-bit ortak veri yoluna 74LS245 üç-durumlu tamponlar üzerinden bağlanması.', 'not_started', null, 3),
  ('tasarim2', 'Kontrol Biriminin Entegrasyonu', 'EEPROM tabanlı mikrokodun programlanması ve kontrol sinyallerinin modüllere dağıtılması.', 'not_started', null, 4),
  ('tasarim2', 'Programların Çalıştırılması', 'Toplama, çıkarma ve döngü içeren örnek programların RAM’e yüklenip çalıştırılması.', 'not_started', null, 5),
  ('tasarim2', 'Nihai Sistem Testleri', 'Tüm komut setinin, bayrakların ve koşullu atlamaların bütünleşik sistemde sınanması.', 'not_started', null, 6)
) as v(phase_slug, title, description, status, completed_at, sort_order)
join public.project_phases p on p.slug = v.phase_slug
where not exists (select 1 from public.project_tasks t where t.phase_id = p.id and t.title = v.title);

insert into public.materials (slug, name, source_name, category, notes, required_quantity, ref_quantity, ref_unit_price_min, ref_unit_price_max, ref_stated_total_min, ref_stated_total_max, is_programmer_extra, sort_order, ref_currency)
select v.*, 'USD' from (values
  ('breadboard', 'Breadboard (delikli deney tahtası)', 'Breadboard', 'Breadboard ve bağlantı malzemeleri', 'Kaynak, en iyi kalite olarak BusBoard BB830 modelini önermektedir.', 14, 14, 4, 9, 56, 126, false, 10),
  ('wire', '22 AWG tek damarlı kalaylı bakır bağlantı teli (set)', '22 AWG Solid Tinned-Copper Hook-Up Wire', 'Breadboard ve bağlantı malzemeleri', null, 1, 1, 16, 16, 16, 16, false, 20),
  ('r1k', '1 kΩ direnç', '1kΩ resistor', 'Dirençler', null, 10, 10, 0.06, 0.06, 0.6, 0.6, false, 30),
  ('r10k', '10 kΩ direnç', '10kΩ resistor', 'Dirençler', null, 9, 9, 0.06, 0.06, 0.6, 0.6, false, 40),
  ('r100k', '100 kΩ direnç', '100kΩ resistor', 'Dirençler', null, 1, 1, 0.06, 0.06, 0.6, 0.6, false, 50),
  ('r470', '470 Ω direnç', '470Ω resistor', 'Dirençler', null, 24, 24, 0.06, 0.06, 1.8, 1.8, false, 60),
  ('r1m', '1 MΩ direnç', '1MΩ resistor', 'Dirençler', null, 1, 1, 0.06, 0.06, 0.6, 0.6, false, 70),
  ('pot1m', '1 MΩ potansiyometre', '1MΩ potentiometer', 'Dirençler', null, 1, 1, 1.39, 1.39, 1.39, 1.39, false, 80),
  ('c001', '0,01 µF kondansatör', '0.01µF capacitor', 'Kondansatörler', null, 6, 6, 0.12, 0.12, 1.2, 1.2, false, 90),
  ('c01', '0,1 µF kondansatör', '0.1µF capacitor', 'Kondansatörler', null, 16, 16, 0.15, 0.15, 3, 3, false, 100),
  ('c1', '1 µF kondansatör', '1µF capacitor', 'Kondansatörler', null, 1, 1, 0.15, 0.15, 0.15, 0.15, false, 110),
  ('ne555', '555 zamanlayıcı entegresi', '555 timer IC', 'Zamanlayıcı entegreler', null, 4, 4, 0.35, 0.35, 1.4, 1.4, false, 120),
  ('ls00', '74LS00 — dörtlü NAND kapısı', '74LS00 (Quad NAND gate)', 'Mantık kapıları', null, 2, 2, 0.79, 0.79, 1.58, 1.58, false, 130),
  ('ls02', '74LS02 — dörtlü NOR kapısı', '74LS02 (Quad NOR gate)', 'Mantık kapıları', null, 1, 1, 0.55, 0.55, 0.55, 0.55, false, 140),
  ('ls04', '74LS04 — altılı tersleyici (NOT)', '74LS04 (Hex inverter)', 'Mantık kapıları', null, 5, 5, 0.59, 0.59, 2.95, 2.95, false, 150),
  ('ls08', '74LS08 — dörtlü AND kapısı', '74LS08 (Quad AND gate)', 'Mantık kapıları', null, 3, 3, 0.69, 0.69, 2.07, 2.07, false, 160),
  ('ls32', '74LS32 — dörtlü OR kapısı', '74LS32 (Quad OR gate)', 'Mantık kapıları', null, 1, 1, 0.49, 0.49, 0.49, 0.49, false, 170),
  ('ls107', '74LS107 — çift JK flip-flop', '74LS107 (Dual JK flip-flop)', 'Yazmaç ve sayaç entegreleri', 'Videolarda kullanılan 74LS76 zor bulunur; 74LS107 işlevsel olarak eşdeğerdir ancak bacak dizilimi (pinout) farklıdır.', 1, 1, 1.75, 1.75, 1.75, 1.75, false, 180),
  ('ls86', '74LS86 — dörtlü XOR kapısı', '74LS86 (Quad XOR gate)', 'Mantık kapıları', null, 2, 2, 0.55, 0.55, 1.1, 1.1, false, 190),
  ('ls138', '74LS138 — 3’ten 8’e kod çözücü', '74LS138 (3-to-8 line decoder)', 'Mantık kapıları', null, 1, 1, 0.69, 0.69, 0.69, 0.69, false, 200),
  ('ls139', '74LS139 — çift 2’den 4’e kod çözücü', '74LS139 (Dual 2-line to 4-line decoder)', 'Mantık kapıları', null, 1, 1, 0.69, 0.69, 0.69, 0.69, false, 210),
  ('ls157', '74LS157 — dörtlü 2’den 1’e veri seçici (multiplexer)', '74LS157 (Quad 2-to-1 line data selector)', 'Mantık kapıları', null, 4, 4, 0.69, 0.69, 2.76, 2.76, false, 220),
  ('ls161', '74LS161 — 4-bit senkron ikili sayıcı', '74LS161 (4-bit synchronous binary counter)', 'Yazmaç ve sayaç entegreleri', null, 2, 2, 0.79, 0.79, 1.58, 1.58, false, 230),
  ('ls173', '74LS173 — 4-bit D tipi yazmaç', '74LS173 (4-bit D-type register)', 'Yazmaç ve sayaç entegreleri', null, 8, 8, 1.39, 1.39, 11.12, 11.12, false, 240),
  ('ls189', '74189 — 64-bit (16 × 4) RAM', '74189 (64-bit random access memory)', 'Bellek ve EEPROM', null, 2, 2, 4.95, 4.95, 9.9, 9.9, false, 250),
  ('ls245', '74LS245 — sekizli veri yolu alıcı-vericisi', '74LS245 (Octal bus transceiver)', 'Mantık kapıları', null, 6, 6, 0.79, 0.79, 4.74, 4.74, false, 260),
  ('ls273', '74LS273 — sekizli D flip-flop', '74LS273 (Octal D flip-flop)', 'Yazmaç ve sayaç entegreleri', null, 1, 1, 0.75, 0.75, 0.75, 0.75, false, 270),
  ('ls283', '74LS283 — 4-bit ikili tam toplayıcı', '74LS283 (4-bit binary full adder)', 'Mantık kapıları', null, 2, 2, 1.49, 1.49, 2.98, 2.98, false, 280),
  ('eeprom', '28C16 EEPROM (2K × 8)', '28C16 EEPROM', 'Bellek ve EEPROM', null, 3, 3, 3.95, 3.95, 11.85, 11.85, false, 290),
  ('toggle', 'Çift konumlu (double-throw) toggle anahtar', 'Double-throw toggle switch', 'Anahtarlar ve kontrol elemanları', null, 3, 3, 0.99, 0.99, 2.97, 2.97, false, 300),
  ('tact', '6 mm anlık (momentary) buton', 'Momentary 6mm tact switch', 'Anahtarlar ve kontrol elemanları', null, 3, 3, 0.35, 0.35, 1.05, 1.05, false, 310),
  ('dip8', '8 konumlu DIP anahtar', '8-position DIP switch', 'Anahtarlar ve kontrol elemanları', null, 1, 1, 0.79, 0.79, 0.79, 0.79, false, 320),
  ('dip4', '4 konumlu DIP anahtar', '4-position DIP switch', 'Anahtarlar ve kontrol elemanları', null, 1, 1, 0.89, 0.89, 0.89, 0.89, false, 330),
  ('led-r', 'Kırmızı LED', 'Red LED', 'LED ve göstergeler', null, 44, 44, 0.12, 0.12, 6, 6, false, 340),
  ('led-y', 'Sarı LED', 'Yellow LED', 'LED ve göstergeler', null, 8, 8, 0.09, 0.09, 0.9, 0.9, false, 350),
  ('led-g', 'Yeşil LED', 'Green LED', 'LED ve göstergeler', null, 12, 12, 0.1, 0.1, 2, 2, false, 360),
  ('led-b', 'Mavi LED', 'Blue LED', 'LED ve göstergeler', null, 21, 21, 0.59, 0.59, 12.39, 12.39, false, 370),
  ('seg7', 'Ortak katotlu 7 segment gösterge', 'Common cathode 7-segment display', 'LED ve göstergeler', null, 4, 4, 1.09, 1.09, 4.36, 4.36, false, 380),
  ('nano', 'Arduino Nano', null, 'EEPROM programlayıcı', 'Kaynakta fiyat belirtilmemiştir.', 1, 1, null, null, null, null, true, 1000),
  ('hc595', '74HC595 — 8-bit seri giriş / paralel çıkış kaydırmalı yazmaç', null, 'EEPROM programlayıcı', 'Kaynakta fiyat belirtilmemiştir.', 2, 2, null, null, null, null, true, 1010)
) as v(slug, name, source_name, category, notes, required_quantity, ref_quantity, ref_unit_price_min, ref_unit_price_max, ref_stated_total_min, ref_stated_total_max, is_programmer_extra, sort_order)
on conflict (slug) do nothing;

commit;

