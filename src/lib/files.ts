/** Yükleme doğrulaması ve güvenli depolama yolu üretimi (sunucudaki depo kurallarıyla aynı). */
import type { MediaCategory } from './labels';

export type Bucket = 'public-media' | 'private-files';
export const PUBLIC_BUCKET: Bucket = 'public-media';
export const PRIVATE_BUCKET: Bucket = 'private-files';

export const sizeLimits: Record<Bucket, number> = { 'public-media': 20 * 1024 * 1024, 'private-files': 50 * 1024 * 1024 };

const imageExt = ['png', 'jpg', 'jpeg', 'webp', 'gif'];
const sourceExt = ['dig', 'circ', 'pdsprj', 'hex', 'bin', 'asm', 'ino', 'zip', 'txt', 'csv'];
export const allowedExt: Record<Bucket, string[]> = {
  'public-media': [...imageExt, 'pdf', ...sourceExt],
  'private-files': [...imageExt, 'pdf', ...sourceExt, 'xml', 'docx', 'xlsx', 'pptx'],
};

/** Sunucuya gönderilecek içerik türü. Simülasyon kaynak dosyaları her zaman indirme olarak sunulur. */
const mimeByExt: Record<string, string> = {
  png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif', pdf: 'application/pdf',
  zip: 'application/zip', txt: 'text/plain', csv: 'text/csv', xml: 'application/xml',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  dig: 'application/octet-stream', circ: 'application/octet-stream', pdsprj: 'application/octet-stream',
  hex: 'application/octet-stream', bin: 'application/octet-stream', asm: 'text/plain', ino: 'text/plain',
};

export const extOf = (name: string) => (name.match(/\.([A-Za-z0-9]{1,8})$/)?.[1] ?? '').toLowerCase();
export const isImage = (mime: string) => mime.startsWith('image/');
export const isPdf = (mime: string) => mime === 'application/pdf';

export interface FileCheck { ok: boolean; error?: string; ext: string; contentType: string }

export function checkFile(file: { name: string; size: number }, bucket: Bucket): FileCheck {
  const ext = extOf(file.name);
  const contentType = mimeByExt[ext] ?? '';
  if (!ext || !allowedExt[bucket].includes(ext)) {
    const where = bucket === PUBLIC_BUCKET ? 'herkese açık depoya' : 'özel depoya';
    return { ok: false, ext, contentType, error: `“.${ext || '?'}” uzantılı dosyalar ${where} yüklenemez. İzin verilenler: ${allowedExt[bucket].join(', ')}` };
  }
  if (file.size <= 0) return { ok: false, ext, contentType, error: 'Dosya boş.' };
  if (file.size > sizeLimits[bucket]) return { ok: false, ext, contentType, error: `Dosya çok büyük (en fazla ${sizeLimits[bucket] / 1024 / 1024} MB).` };
  return { ok: true, ext, contentType };
}

export function uuid() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  // Eski tarayıcılar için yedek
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/** <kategori>/<yıl>/<uuid>.<uzantı> — özgün dosya adı yolda kullanılmaz. */
export function storagePath(category: MediaCategory, ext: string, date = new Date()) {
  const id = uuid();
  return { fileName: `${id}.${ext}`, path: `${category}/${date.getFullYear()}/${id}.${ext}` };
}

/** Görünen başlık için dosya adından uzantıyı ve ayırıcıları temizler. */
export function titleFromFileName(name: string) {
  return name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 200) || 'Adsız dosya';
}
