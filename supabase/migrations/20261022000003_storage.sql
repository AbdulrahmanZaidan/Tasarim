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
