/**
 * Medya yönetimi: Storage'a yükleme (ilerleme göstergeli), meta veri kaydı, değiştirme,
 * görünürlük (açık/özel depo) değiştirme, güvenli silme ve indirme bağlantıları.
 */
import type { TablesInsert } from '../lib/database.types';
import { db, supabaseAnonKey, supabaseUrl, imageTransformEnabled } from '../lib/supabase';
import { AppError, toAppError } from '../lib/errors';
import { invalidate } from '../lib/query';
import { checkFile, storagePath, titleFromFileName, type Bucket, PUBLIC_BUCKET } from '../lib/files';
import type { MediaCategory } from '../lib/labels';
import { mediaRows, type Media } from './entities';
import { unwrap } from './base';

export interface UploadMeta {
  bucket: Bucket;
  category: MediaCategory;
  title?: string;
  description?: string | null;
  component_id?: string | null;
  simulation_id?: string | null;
  progress_update_id?: string | null;
}

async function accessToken() {
  const { data } = await db().auth.getSession();
  const t = data.session?.access_token;
  if (!t) throw new AppError('Dosya yüklemek için giriş yapmalısınız.', 'session_expired');
  return t;
}

/** Ham Storage yüklemesi — XMLHttpRequest ile gerçek yükleme ilerlemesi raporlanır. */
function putObject(bucket: Bucket, path: string, file: Blob, contentType: string, token: string, onProgress?: (p: number) => void, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${supabaseUrl}/storage/v1/object/${bucket}/${path.split('/').map(encodeURIComponent).join('/')}`);
    xhr.setRequestHeader('authorization', `Bearer ${token}`);
    xhr.setRequestHeader('apikey', supabaseAnonKey);
    xhr.setRequestHeader('x-upsert', 'false');
    xhr.setRequestHeader('cache-control', 'max-age=3600');
    xhr.setRequestHeader('content-type', contentType);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100)); };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) { onProgress?.(100); resolve(); return; }
      let body: { message?: string; error?: string; statusCode?: string } = {};
      try { body = JSON.parse(xhr.responseText); } catch { /* yanıt JSON değil */ }
      reject(toAppError({ message: body.message ?? body.error ?? `HTTP ${xhr.status}`, statusCode: body.statusCode ?? String(xhr.status), status: xhr.status }));
    };
    xhr.onerror = () => reject(toAppError({ message: 'Failed to fetch' }));
    xhr.onabort = () => reject(new AppError('Yükleme iptal edildi.', 'aborted'));
    signal?.addEventListener('abort', () => xhr.abort(), { once: true });
    xhr.send(file);
  });
}

async function removeObject(bucket: string, path: string) {
  const { error } = await db().storage.from(bucket).remove([path]);
  return !error;
}

/** Dosyayı yükler ve meta veri kaydını oluşturur. Kayıt başarısız olursa yüklenen dosya geri silinir. */
export async function uploadMedia(file: File, meta: UploadMeta, onProgress?: (p: number) => void, signal?: AbortSignal): Promise<Media> {
  const check = checkFile(file, meta.bucket);
  if (!check.ok) throw new AppError(check.error!, 'validation');
  const token = await accessToken();
  const { fileName, path } = storagePath(meta.category, check.ext);
  await putObject(meta.bucket, path, file, check.contentType, token, onProgress, signal);
  const row: TablesInsert<'media_files'> = {
    file_name: fileName,
    original_file_name: file.name.slice(0, 255),
    storage_path: path,
    bucket_name: meta.bucket,
    mime_type: check.contentType,
    file_size: file.size,
    title: (meta.title?.trim() || titleFromFileName(file.name)).slice(0, 200),
    description: meta.description ?? null,
    category: meta.category,
    component_id: meta.component_id ?? null,
    simulation_id: meta.simulation_id ?? null,
    progress_update_id: meta.progress_update_id ?? null,
  };
  try {
    return await mediaRows.insert(row);
  } catch (e) {
    await removeObject(meta.bucket, path);
    throw e;
  }
}

/** Dosyanın içeriğini değiştirir (yeni benzersiz yol), meta veriyi korur, eski nesneyi siler. */
export async function replaceMediaFile(media: Media, file: File, onProgress?: (p: number) => void): Promise<Media> {
  const bucket = media.bucket_name as Bucket;
  const check = checkFile(file, bucket);
  if (!check.ok) throw new AppError(check.error!, 'validation');
  const token = await accessToken();
  const { fileName, path } = storagePath(media.category, check.ext);
  await putObject(bucket, path, file, check.contentType, token, onProgress);
  let updated: Media;
  try {
    updated = await mediaRows.update(media.id, {
      file_name: fileName, storage_path: path, original_file_name: file.name.slice(0, 255), mime_type: check.contentType, file_size: file.size,
    }, media.updated_at);
  } catch (e) {
    await removeObject(bucket, path);
    throw e;
  }
  await removeObject(bucket, media.storage_path);
  return updated;
}

/** Dosyayı açık ↔ özel depo arasında taşır. */
export async function setMediaBucket(media: Media, target: Bucket): Promise<Media> {
  if (media.bucket_name === target) return media;
  const check = checkFile({ name: media.file_name, size: media.file_size }, target);
  if (!check.ok) throw new AppError(check.error!, 'validation');
  const { error } = await db().storage.from(media.bucket_name).copy(media.storage_path, media.storage_path, { destinationBucket: target });
  if (error) throw toAppError(error);
  let updated: Media;
  try {
    updated = await mediaRows.update(media.id, { bucket_name: target }, media.updated_at);
  } catch (e) {
    await removeObject(target, media.storage_path);
    throw e;
  }
  await removeObject(media.bucket_name, media.storage_path);
  return updated;
}

/**
 * Önce meta veri kaydı silinir: dosya bir belgede veya satın almada kullanılıyorsa veritabanı silmeyi reddeder
 * ve hiçbir şey kaybolmaz. Ardından depodaki nesne silinir.
 */
export async function deleteMedia(media: Media): Promise<{ storageRemoved: boolean }> {
  await mediaRows.remove(media.id);
  const storageRemoved = await removeObject(media.bucket_name, media.storage_path);
  return { storageRemoved };
}

export async function updateMediaMeta(media: Media, patch: Partial<Pick<Media, 'title' | 'description' | 'category' | 'component_id' | 'simulation_id' | 'progress_update_id'>>) {
  return mediaRows.update(media.id, patch, media.updated_at);
}

export function publicUrl(path: string, opts?: { width?: number; download?: string }) {
  const s = db().storage.from(PUBLIC_BUCKET);
  if (opts?.width && imageTransformEnabled) return s.getPublicUrl(path, { transform: { width: opts.width, resize: 'contain' } }).data.publicUrl;
  return s.getPublicUrl(path, opts?.download ? { download: opts.download } : undefined).data.publicUrl;
}

/** Görüntüleme adresleri: açık depo için kalıcı, özel depo için süreli imzalı bağlantı. */
export async function mediaUrls(items: Media[], opts?: { width?: number }): Promise<Record<string, string>> {
  const out: Record<string, string> = {};
  const priv = items.filter((m) => m.bucket_name !== PUBLIC_BUCKET);
  for (const m of items) if (m.bucket_name === PUBLIC_BUCKET) out[m.id] = publicUrl(m.storage_path, opts);
  if (priv.length) {
    const { data, error } = await db().storage.from('private-files').createSignedUrls(priv.map((m) => m.storage_path), 3600);
    if (error) throw toAppError(error);
    data?.forEach((d, i) => { if (d.signedUrl) out[priv[i].id] = d.signedUrl; });
  }
  return out;
}

export async function downloadUrl(m: Media): Promise<string> {
  if (m.bucket_name === PUBLIC_BUCKET) return publicUrl(m.storage_path, { download: m.original_file_name });
  const { data, error } = await db().storage.from(m.bucket_name).createSignedUrl(m.storage_path, 120, { download: m.original_file_name });
  if (error || !data) throw toAppError(error ?? { message: 'Bağlantı oluşturulamadı' });
  return data.signedUrl;
}

export async function listMedia(filter?: { simulationId?: string; componentId?: string; progressUpdateId?: string; publicOnly?: boolean }) {
  let q = db().from('media_files').select('*').order('created_at', { ascending: false });
  if (filter?.simulationId) q = q.eq('simulation_id', filter.simulationId);
  if (filter?.componentId) q = q.eq('component_id', filter.componentId);
  if (filter?.progressUpdateId) q = q.eq('progress_update_id', filter.progressUpdateId);
  if (filter?.publicOnly) q = q.eq('bucket_name', PUBLIC_BUCKET);
  return unwrap(q);
}

export function invalidateMedia() {
  invalidate('media_files', 'simulations', 'progress_updates', 'technical_documents');
}
