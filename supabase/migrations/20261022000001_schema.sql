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
