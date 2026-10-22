/**
 * Malzeme CSV içe aktarma ve tarayıcı (localStorage) verisi aktarma mantığı.
 * Saf fonksiyonlardır; veritabanına yazma işlemini çağıran sayfa yapar (önizleme + onay sonrası).
 */
import { parseCsv, parseNumber, toCsv } from './csv';
import type { PurchaseStatus } from './labels';
import { purchaseLabels } from './labels';

export interface MaterialLike {
  id: string;
  slug: string;
  name: string;
  category: string;
  required_quantity: number;
  unit_price: number | null;
  currency: string;
  supplier: string | null;
  product_url: string | null;
  purchase_status: PurchaseStatus;
  notes: string | null;
}

export type ImportField = 'slug' | 'name' | 'category' | 'required_quantity' | 'unit_price' | 'currency' | 'supplier' | 'product_url' | 'purchase_status' | 'notes';

/** Başlık eşleştirmesi (Türkçe ve İngilizce adlar kabul edilir) */
const headerMap: Record<string, ImportField> = {
  kod: 'slug', slug: 'slug', 'malzeme kodu': 'slug',
  'malzeme adı': 'name', ad: 'name', name: 'name', malzeme: 'name',
  kategori: 'category', category: 'category',
  'gerekli adet': 'required_quantity', adet: 'required_quantity', required_quantity: 'required_quantity', quantity: 'required_quantity',
  'birim fiyat': 'unit_price', unit_price: 'unit_price', fiyat: 'unit_price',
  'para birimi': 'currency', currency: 'currency',
  tedarikçi: 'supplier', supplier: 'supplier',
  'ürün bağlantısı': 'product_url', bağlantı: 'product_url', product_url: 'product_url', url: 'product_url',
  'satın alma durumu': 'purchase_status', durum: 'purchase_status', purchase_status: 'purchase_status',
  notlar: 'notes', not: 'notes', notes: 'notes',
};

export const exportHeaders = ['Kod', 'Malzeme Adı', 'Kategori', 'Gerekli Adet', 'Birim Fiyat', 'Para Birimi', 'Tedarikçi', 'Ürün Bağlantısı', 'Satın Alma Durumu', 'Notlar'];

export function materialsToCsv(items: MaterialLike[]) {
  return toCsv([
    exportHeaders,
    ...items.map((m) => [m.slug, m.name, m.category, m.required_quantity, m.unit_price === null ? '' : String(m.unit_price).replace('.', ','), m.currency,
      m.supplier ?? '', m.product_url ?? '', purchaseLabels[m.purchase_status], m.notes ?? '']),
  ]);
}

const statusByLabel: Record<string, PurchaseStatus> = Object.fromEntries(
  (Object.entries(purchaseLabels) as [PurchaseStatus, string][]).flatMap(([k, v]) => [[v.toLocaleLowerCase('tr-TR'), k], [k, k]]),
);

export type RowAction = 'create' | 'update' | 'unchanged' | 'error';
export interface ImportRow {
  line: number;
  action: RowAction;
  slug: string;
  name: string;
  errors: string[];
  /** Değişen alanlar: alan → [eski, yeni] */
  changes: Partial<Record<ImportField, [unknown, unknown]>>;
  values: Partial<Omit<MaterialLike, 'id'>>;
  existingId?: string;
}
export interface ImportPreview { rows: ImportRow[]; unknownHeaders: string[]; missingRequired: string[] }

export const slugify = (s: string) =>
  s.toLocaleLowerCase('tr-TR').replace(/ç/g, 'c').replace(/ğ/g, 'g').replace(/ı/g, 'i').replace(/ö/g, 'o').replace(/ş/g, 's').replace(/ü/g, 'u')
    .normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60);

export function previewMaterialsCsv(text: string, existing: MaterialLike[]): ImportPreview {
  const table = parseCsv(text);
  if (table.length === 0) return { rows: [], unknownHeaders: [], missingRequired: ['Dosya boş'] };
  const header = table[0].map((h) => h.trim().toLocaleLowerCase('tr-TR'));
  const fields = header.map((h) => headerMap[h]);
  const unknownHeaders = table[0].filter((_, i) => !fields[i]);
  const missingRequired = (['name'] as ImportField[]).filter((f) => !fields.includes(f)).map(() => 'Malzeme Adı');
  const bySlug = new Map(existing.map((m) => [m.slug, m]));
  const seen = new Map<string, number>();
  const rows: ImportRow[] = [];

  table.slice(1).forEach((cells, idx) => {
    const line = idx + 2;
    const raw: Partial<Record<ImportField, string>> = {};
    fields.forEach((f, i) => { if (f) raw[f] = (cells[i] ?? '').trim(); });
    const errors: string[] = [];
    const name = raw.name ?? '';
    const slug = raw.slug ? raw.slug.toLowerCase() : slugify(name);
    if (!name && !raw.slug) errors.push('Malzeme adı veya kod gerekli');
    if (slug && !/^[a-z0-9-]{2,60}$/.test(slug)) errors.push('Kod yalnızca küçük harf, rakam ve tire içerebilir (2–60 karakter)');
    if (seen.has(slug)) errors.push(`Dosyada yinelenen kod (satır ${seen.get(slug)})`);
    else seen.set(slug, line);

    const values: Partial<Omit<MaterialLike, 'id'>> = { slug };
    if (raw.name !== undefined && raw.name !== '') {
      if (raw.name.length > 200) errors.push('Ad en fazla 200 karakter olabilir'); else values.name = raw.name;
    }
    if (raw.category !== undefined && raw.category !== '') values.category = raw.category.slice(0, 80);
    if (raw.required_quantity !== undefined && raw.required_quantity !== '') {
      const n = parseNumber(raw.required_quantity);
      if (n === null || !Number.isInteger(n) || n < 0) errors.push('Gerekli adet 0 veya pozitif tam sayı olmalı'); else values.required_quantity = n;
    }
    if (raw.unit_price !== undefined) {
      const n = parseNumber(raw.unit_price);
      if (n !== null && (Number.isNaN(n) || n < 0)) errors.push('Birim fiyat geçersiz'); else values.unit_price = n;
    }
    if (raw.currency !== undefined && raw.currency !== '') {
      const c = raw.currency.toUpperCase().replace('TL', 'TRY');
      if (!/^[A-Z]{3}$/.test(c)) errors.push('Para birimi üç harfli olmalı (TRY, USD, EUR)'); else values.currency = c;
    }
    if (raw.supplier !== undefined) values.supplier = raw.supplier || null;
    if (raw.product_url !== undefined) {
      if (raw.product_url && !/^https?:\/\//i.test(raw.product_url)) errors.push('Ürün bağlantısı http:// veya https:// ile başlamalı');
      else values.product_url = raw.product_url || null;
    }
    if (raw.purchase_status !== undefined && raw.purchase_status !== '') {
      const st = statusByLabel[raw.purchase_status.toLocaleLowerCase('tr-TR')];
      if (!st) errors.push(`Bilinmeyen satın alma durumu: “${raw.purchase_status}”`); else values.purchase_status = st;
    }
    if (raw.notes !== undefined) values.notes = raw.notes || null;

    const ex = bySlug.get(slug);
    if (!ex) {
      if (!values.name) errors.push('Yeni kalem için malzeme adı gerekli');
      if (!values.category) errors.push('Yeni kalem için kategori gerekli');
    }
    const changes: ImportRow['changes'] = {};
    if (ex) {
      (Object.keys(values) as ImportField[]).forEach((k) => {
        if (k === 'slug') return;
        const oldV = ex[k as keyof MaterialLike] ?? null;
        const newV = values[k as keyof typeof values] ?? null;
        if (oldV !== newV) changes[k] = [oldV, newV];
      });
    }
    const action: RowAction = errors.length ? 'error' : !ex ? 'create' : Object.keys(changes).length ? 'update' : 'unchanged';
    rows.push({ line, action, slug, name: values.name ?? ex?.name ?? '', errors, changes, values, existingId: ex?.id });
  });
  return { rows, unknownHeaders, missingRequired };
}

/* ---------------- Tarayıcıdaki (localStorage) eski düzenlemeler ---------------- */

export const LEGACY_STORAGE_KEY = 'sdu8bit.materials.v1';

interface LegacyEdit { qty?: number; unit?: number; status?: 'none' | 'ordered' | 'received' | 'tested' }
interface LegacyStore { items?: Record<string, LegacyEdit>; extra?: Record<string, LegacyEdit>; shipping?: number; rate?: number | null }

const legacyStatus: Record<string, PurchaseStatus> = { none: 'not_purchased', ordered: 'ordered', received: 'received', tested: 'tested' };

export interface LegacyChange { slug: string; name: string; materialId: string; changes: Partial<Record<'required_quantity' | 'unit_price' | 'currency' | 'purchase_status', [unknown, unknown]>> }
export interface LegacyPreview { changes: LegacyChange[]; unmatched: string[]; shipping: number; rate: number | null; found: boolean }

export function readLegacyStore(): LegacyStore | null {
  try {
    const raw = localStorage.getItem(LEGACY_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as LegacyStore) : null;
  } catch {
    return null;
  }
}

/** Eski sürümde birim fiyatlar USD olarak girilirdi; bu nedenle para birimi USD olarak aktarılır. */
export function previewLegacy(store: LegacyStore | null, existing: MaterialLike[]): LegacyPreview {
  if (!store) return { changes: [], unmatched: [], shipping: 0, rate: null, found: false };
  const bySlug = new Map(existing.map((m) => [m.slug, m]));
  const changes: LegacyChange[] = [];
  const unmatched: string[] = [];
  for (const [slug, e] of Object.entries({ ...(store.items ?? {}), ...(store.extra ?? {}) })) {
    const m = bySlug.get(slug);
    if (!m) { unmatched.push(slug); continue; }
    const c: LegacyChange['changes'] = {};
    if (typeof e.qty === 'number' && e.qty !== m.required_quantity) c.required_quantity = [m.required_quantity, e.qty];
    if (typeof e.unit === 'number' && (e.unit !== m.unit_price || m.currency !== 'USD')) {
      c.unit_price = [m.unit_price, e.unit];
      if (m.currency !== 'USD') c.currency = [m.currency, 'USD'];
    }
    if (e.status && legacyStatus[e.status] && legacyStatus[e.status] !== m.purchase_status) c.purchase_status = [m.purchase_status, legacyStatus[e.status]];
    if (Object.keys(c).length) changes.push({ slug, name: m.name, materialId: m.id, changes: c });
  }
  return { changes, unmatched, shipping: store.shipping ?? 0, rate: store.rate ?? null, found: true };
}
