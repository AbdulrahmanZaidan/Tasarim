/**
 * MALİYET HESAPLARI
 * Para birimleri asla kendiliğinden karıştırılmaz. Toplamlar para birimine göre ayrı tutulur;
 * birleşik TL tahmini yalnızca açıkça kaydedilmiş bir USD/TRY kuru varsa üretilir.
 * Fiyatı girilmemiş kalemler için referans liste fiyatı (tarihsel, USD aralığı) kullanılır.
 */

export interface CostMaterial {
  id: string;
  category: string;
  required_quantity: number;
  purchased_quantity: number;
  unit_price: number | null;
  currency: string;
  ref_unit_price_min: number | null;
  ref_unit_price_max: number | null;
  ref_currency: string;
  is_programmer_extra?: boolean;
}
export interface CostPurchase { quantity: number; unit_price: number | null; currency: string; material_id?: string }

export interface Range { min: number; max: number }
/** Para birimi → aralık */
export type Totals = Record<string, Range>;

const r2 = (n: number) => Math.round(n * 100) / 100;

function add(t: Totals, currency: string, min: number, max = min) {
  const cur = t[currency] ?? { min: 0, max: 0 };
  t[currency] = { min: r2(cur.min + min), max: r2(cur.max + max) };
}

export type PriceSource = 'quote' | 'reference' | 'none';

/** Bir kalemin birim fiyatı: önce yerel teklif, yoksa referans fiyat. */
export function unitPrice(m: CostMaterial): { source: PriceSource; currency: string; range: Range } {
  if (m.unit_price !== null && m.unit_price !== undefined) return { source: 'quote', currency: m.currency, range: { min: m.unit_price, max: m.unit_price } };
  if (m.ref_unit_price_min !== null && m.ref_unit_price_min !== undefined) {
    return { source: 'reference', currency: m.ref_currency, range: { min: m.ref_unit_price_min, max: m.ref_unit_price_max ?? m.ref_unit_price_min } };
  }
  return { source: 'none', currency: m.currency, range: { min: 0, max: 0 } };
}

export function remainingQty(m: CostMaterial) {
  return Math.max(0, m.required_quantity - m.purchased_quantity);
}

export interface CostSummary {
  estimated: Totals;
  remaining: Totals;
  purchased: Totals;
  /** Fiyatı olmayan satın alma kaydı sayısı */
  purchasesWithoutPrice: number;
  /** Fiyat bilgisi (teklif veya referans) olmayan kalem sayısı */
  unpricedItems: number;
  quotedItems: number;
  referenceItems: number;
  byCategory: { category: string; totals: Totals }[];
  requiredQty: number;
  purchasedQty: number;
  remainingQty: number;
  fullyPurchased: number;
  partiallyPurchased: number;
  notPurchased: number;
  itemCount: number;
}

export function summarize(materials: CostMaterial[], purchases: CostPurchase[]): CostSummary {
  const s: CostSummary = {
    estimated: {}, remaining: {}, purchased: {}, purchasesWithoutPrice: 0, unpricedItems: 0, quotedItems: 0, referenceItems: 0,
    byCategory: [], requiredQty: 0, purchasedQty: 0, remainingQty: 0, fullyPurchased: 0, partiallyPurchased: 0, notPurchased: 0,
    itemCount: materials.length,
  };
  const cats = new Map<string, Totals>();
  for (const m of materials) {
    const p = unitPrice(m);
    if (p.source === 'quote') s.quotedItems++;
    else if (p.source === 'reference') s.referenceItems++;
    else s.unpricedItems++;
    const rem = remainingQty(m);
    if (p.source !== 'none') {
      add(s.estimated, p.currency, p.range.min * m.required_quantity, p.range.max * m.required_quantity);
      if (rem > 0) add(s.remaining, p.currency, p.range.min * rem, p.range.max * rem);
      const c = cats.get(m.category) ?? {};
      add(c, p.currency, p.range.min * m.required_quantity, p.range.max * m.required_quantity);
      cats.set(m.category, c);
    }
    s.requiredQty += m.required_quantity;
    s.purchasedQty += m.purchased_quantity;
    s.remainingQty += rem;
    if (m.required_quantity > 0 && m.purchased_quantity >= m.required_quantity) s.fullyPurchased++;
    else if (m.purchased_quantity > 0) s.partiallyPurchased++;
    else s.notPurchased++;
  }
  for (const p of purchases) {
    if (p.unit_price === null || p.unit_price === undefined) { s.purchasesWithoutPrice++; continue; }
    add(s.purchased, p.currency, p.unit_price * p.quantity);
  }
  s.byCategory = [...cats.entries()].map(([category, totals]) => ({ category, totals }));
  return s;
}

/** Kaydedilmiş kur ile birleşik TL tahmini. Kur yoksa null (para birimleri karıştırılmaz). */
export function combinedTRY(t: Totals, usdTryRate: number | null): Range | null {
  const currencies = Object.keys(t);
  if (currencies.length === 0) return { min: 0, max: 0 };
  if (currencies.some((c) => c !== 'TRY' && c !== 'USD')) return null;
  if (currencies.includes('USD') && !usdTryRate) return null;
  const tr = t.TRY ?? { min: 0, max: 0 };
  const us = t.USD ?? { min: 0, max: 0 };
  const rate = usdTryRate ?? 0;
  return { min: r2(tr.min + us.min * rate), max: r2(tr.max + us.max * rate) };
}

export function totalsEmpty(t: Totals) {
  return Object.values(t).every((r) => r.min === 0 && r.max === 0);
}
