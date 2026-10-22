import { describe, it, expect } from 'vitest';
import { taskProgress, weightedProgress, validateWeights, phaseProgress } from '../../src/lib/progress';
import { summarize, combinedTRY, unitPrice, type CostMaterial } from '../../src/lib/costs';
import { parseCsv, toCsv, parseNumber } from '../../src/lib/csv';
import { previewMaterialsCsv, previewLegacy, materialsToCsv, slugify, type MaterialLike } from '../../src/lib/materialsImport';
import { checkFile, storagePath, titleFromFileName } from '../../src/lib/files';
import { toAppError } from '../../src/lib/errors';
import { seedMaterials, seedTasks, seedPhases } from '../../src/data/fallback';
import { parts } from '../../src/data/parts';

describe('ilerleme hesabı', () => {
  it('görev ağırlıklarına göre yüzde verir; görev yoksa null', () => {
    expect(taskProgress([])).toBeNull();
    expect(taskProgress([{ status: 'completed' }, { status: 'not_started' }])).toBe(50);
    expect(taskProgress([{ status: 'completed', weight: 3 }, { status: 'in_progress', weight: 1 }])).toBe(75);
  });
  it('genel ilerleme aşama ağırlıklarıyla ağırlıklı ortalamadır', () => {
    const phases = [{ id: 'a', weight: 60 }, { id: 'b', weight: 40 }];
    const tasks = [{ status: 'completed', phase_id: 'a' }, { status: 'completed', phase_id: 'b' }, { status: 'not_started', phase_id: 'b' }];
    const r = weightedProgress(phases, tasks);
    expect(r.value).toBe(80); // 0.6×100 + 0.4×50
    expect(r.weightsValid).toBe(true);
  });
  it('ağırlıklar 0 ise eşit ağırlık; toplam 100 değilse uyarı bayrağı', () => {
    expect(weightedProgress([{ id: 'a', weight: 0 }, { id: 'b', weight: 0 }], [{ status: 'completed', phase_id: 'a' }]).value).toBe(50);
    const r = weightedProgress([{ id: 'a', weight: 30 }, { id: 'b', weight: 30 }], []);
    expect(r.weightsValid).toBe(false);
    expect(r.phasesWithoutTasks).toBe(2);
  });
  it('ağırlık doğrulaması', () => {
    expect(validateWeights({ a: 50, b: 50 })).toBeNull();
    expect(validateWeights({ a: 50, b: 40 })).toMatch(/100/);
    expect(validateWeights({ a: -1, b: 101 })).toMatch(/0 ile 100/);
  });
  it('başlangıç verisi: yalnızca doğrulanabilir depo oluşturma görevi tamamlanmış', () => {
    expect(seedTasks.filter((t) => t.status === 'completed').map((t) => t.title)).toEqual(['GitHub deposunun oluşturulması']);
    expect(seedPhases.reduce((a, p) => a + p.weight, 0)).toBe(100);
    expect(phaseProgress('tasarim2', seedTasks.map((t) => ({ status: t.status, phase_id: t.phase })))).toBe(0);
  });
});

const mat = (o: Partial<CostMaterial>): CostMaterial => ({
  id: 'x', category: 'K', required_quantity: 1, purchased_quantity: 0, unit_price: null, currency: 'TRY',
  ref_unit_price_min: null, ref_unit_price_max: null, ref_currency: 'USD', ...o,
});

describe('maliyet hesabı', () => {
  it('yerel teklif referans fiyattan önceliklidir', () => {
    expect(unitPrice(mat({ unit_price: 12, ref_unit_price_min: 1 })).source).toBe('quote');
    expect(unitPrice(mat({ ref_unit_price_min: 4, ref_unit_price_max: 9 })).range).toEqual({ min: 4, max: 9 });
    expect(unitPrice(mat({})).source).toBe('none');
  });
  it('para birimlerini karıştırmaz; kur yoksa birleşik toplam üretmez', () => {
    const s = summarize([
      mat({ id: 'a', required_quantity: 2, unit_price: 10, currency: 'TRY' }),
      mat({ id: 'b', required_quantity: 3, ref_unit_price_min: 1, ref_unit_price_max: 2 }),
    ], []);
    expect(s.estimated).toEqual({ TRY: { min: 20, max: 20 }, USD: { min: 3, max: 6 } });
    expect(combinedTRY(s.estimated, null)).toBeNull();
    expect(combinedTRY(s.estimated, 40)).toEqual({ min: 140, max: 260 });
    expect(combinedTRY({ TRY: { min: 5, max: 5 } }, null)).toEqual({ min: 5, max: 5 });
  });
  it('kalan adet ve kalan maliyet satın alınan adede göre hesaplanır', () => {
    const s = summarize([mat({ required_quantity: 10, purchased_quantity: 4, unit_price: 2 })], [{ quantity: 4, unit_price: 2.5, currency: 'TRY' }, { quantity: 1, unit_price: null, currency: 'TRY' }]);
    expect(s.remainingQty).toBe(6);
    expect(s.remaining.TRY).toEqual({ min: 12, max: 12 });
    expect(s.purchased.TRY).toEqual({ min: 10, max: 10 });
    expect(s.purchasesWithoutPrice).toBe(1);
    expect(s.partiallyPurchased).toBe(1);
  });
  it('başlangıç listesi referans toplamları değişmeden korunur (38 kalem, $172.24–$242.24)', () => {
    const main = seedMaterials.filter((m) => !m.is_programmer_extra);
    expect(main).toHaveLength(38);
    expect(main).toHaveLength(parts.length);
    const stated = main.reduce((a, m) => ({ min: a.min + (m.ref_stated_total_min ?? 0), max: a.max + (m.ref_stated_total_max ?? 0) }), { min: 0, max: 0 });
    expect(Math.round(stated.min * 100) / 100).toBe(172.24);
    expect(Math.round(stated.max * 100) / 100).toBe(242.24);
    expect(main.reduce((a, m) => a + m.required_quantity, 0)).toBe(230);
  });
});

describe('CSV', () => {
  it('tırnaklı alanları, ayırıcıyı ve BOM’u doğru okur', () => {
    expect(parseCsv('﻿a;b\n"x;y";"say ""merhaba"""\n')).toEqual([['a', 'b'], ['x;y', 'say "merhaba"']]);
    expect(parseCsv('a,b\r\n1,2')).toEqual([['a', 'b'], ['1', '2']]);
    expect(() => parseCsv('a;"b')).toThrow(/tırnak/);
  });
  it('yazma–okuma gidiş dönüşü', () => {
    const rows = [['Ad', 'Not'], ['74LS00 — NAND', 'çok "özel"; değer']];
    expect(parseCsv(toCsv(rows))).toEqual(rows);
  });
  it('Türkçe ve İngilizce sayı biçimleri', () => {
    expect(parseNumber('1.234,50')).toBe(1234.5);
    expect(parseNumber('1234.50')).toBe(1234.5);
    expect(parseNumber('18,5 TL')).toBe(18.5);
    expect(parseNumber('')).toBeNull();
    expect(Number.isNaN(parseNumber('abc'))).toBe(true);
  });
});

const existing: MaterialLike[] = [
  { id: '1', slug: 'ls00', name: '74LS00', category: 'Mantık kapıları', required_quantity: 2, unit_price: null, currency: 'TRY', supplier: null, product_url: null, purchase_status: 'not_purchased', notes: null },
];

describe('malzeme CSV içe aktarma önizlemesi', () => {
  it('güncellemeleri, yeni kalemleri, hataları ve dosya içi yinelenenleri ayırt eder', () => {
    const csv = [
      'Kod;Malzeme Adı;Kategori;Gerekli Adet;Birim Fiyat;Para Birimi;Satın Alma Durumu',
      'ls00;74LS00;Mantık kapıları;5;12,50;TL;Sipariş Verildi',
      ';Yeni Direnç;Dirençler;10;;;',
      'ls00;74LS00;Mantık kapıları;1;;;',
      'bad code;X;Y;-1;abc;TRY;bilinmiyor',
    ].join('\n');
    const p = previewMaterialsCsv(csv, existing);
    expect(p.rows.map((r) => r.action)).toEqual(['update', 'create', 'error', 'error']);
    expect(p.rows[0].changes).toMatchObject({ required_quantity: [2, 5], unit_price: [null, 12.5], purchase_status: ['not_purchased', 'ordered'] });
    expect(p.rows[1].slug).toBe('yeni-direnc');
    expect(p.rows[2].errors.join()).toMatch(/yinelenen/);
    expect(p.rows[3].errors.length).toBeGreaterThanOrEqual(3);
  });
  it('dışa aktarılan dosya değişiklik olmadan geri okunur', () => {
    const p = previewMaterialsCsv(materialsToCsv(existing), existing);
    expect(p.rows.map((r) => r.action)).toEqual(['unchanged']);
  });
  it('Türkçe karakterli kod üretimi', () => {
    expect(slugify('Çift JK Flip-Flop Şeması')).toBe('cift-jk-flip-flop-semasi');
  });
});

describe('tarayıcıdaki eski düzenlemelerin aktarımı', () => {
  it('yalnızca farkları önerir; USD fiyatları USD olarak taşır; eşleşmeyenleri raporlar', () => {
    const p = previewLegacy({ items: { ls00: { qty: 3, unit: 0.9, status: 'received' }, yok: { qty: 1 } }, shipping: 12, rate: 41 }, existing);
    expect(p.found).toBe(true);
    expect(p.changes[0].changes).toEqual({ required_quantity: [2, 3], unit_price: [null, 0.9], currency: ['TRY', 'USD'], purchase_status: ['not_purchased', 'received'] });
    expect(p.unmatched).toEqual(['yok']);
    expect(previewLegacy(null, existing).found).toBe(false);
  });
});

describe('dosya doğrulama', () => {
  it('uzantı, depo ve boyut kurallarını uygular', () => {
    expect(checkFile({ name: 'a.PNG', size: 10 }, 'public-media').ok).toBe(true);
    expect(checkFile({ name: 'alu.dig', size: 10 }, 'public-media').contentType).toBe('application/octet-stream');
    expect(checkFile({ name: 'x.html', size: 10 }, 'public-media').ok).toBe(false);
    expect(checkFile({ name: 'x.svg', size: 10 }, 'private-files').ok).toBe(false);
    expect(checkFile({ name: 'rapor.docx', size: 10 }, 'public-media').ok).toBe(false);
    expect(checkFile({ name: 'rapor.docx', size: 10 }, 'private-files').ok).toBe(true);
    expect(checkFile({ name: 'big.png', size: 21 * 1024 * 1024 }, 'public-media').error).toMatch(/20 MB/);
    expect(checkFile({ name: 'empty.png', size: 0 }, 'public-media').ok).toBe(false);
  });
  it('depolama yolu özgün adı içermez ve sunucu kuralıyla eşleşir', () => {
    const { path, fileName } = storagePath('simulation_screenshot', 'png', new Date('2026-10-22'));
    expect(path).toMatch(/^simulation_screenshot\/2026\/[a-f0-9-]{36}\.png$/);
    expect(path.endsWith(fileName)).toBe(true);
    expect(titleFromFileName('alu_toplama-testi.png')).toBe('alu toplama testi');
  });
});

describe('hata iletileri', () => {
  it('Supabase hatalarını Türkçe iletilere çevirir', () => {
    expect(toAppError({ message: 'Invalid login credentials' }).message).toBe('E-posta adresi veya parola hatalı.');
    expect(toAppError({ code: '42501', message: 'new row violates row-level security policy' }).code).toBe('forbidden');
    expect(toAppError({ code: '23503', message: 'update or delete on table violates foreign key' }).message).toMatch(/silinemez/);
    expect(toAppError({ code: '23514', message: 'violates check constraint "result_needs_evidence"' }).message).toMatch(/gözlenen çıktı/);
    expect(toAppError(new TypeError('Failed to fetch')).code).toBe('network');
    expect(toAppError({ code: '22023', message: 'Ağırlıkların toplamı 100 olmalıdır (şu an 90).' }).message).toMatch(/şu an 90/);
  });
});

import { v, validate } from '../../src/components/form';
describe('form doğrulama', () => {
  it('Türkçe ondalık virgülünü kabul eder, geçersiz sayıyı reddeder', () => {
    const r = v.number<{ x: string }>({ min: 0 });
    expect(r('18,50', { x: '' })).toBeNull();
    expect(r('41,5', { x: '' })).toBeNull();
    expect(r('abc', { x: '' })).toMatch(/Geçerli bir sayı/);
    expect(r('-1', { x: '' })).toMatch(/En az 0/);
    expect(validate({ a: '', b: 'http://x' }, { a: [v.required()], b: [v.url()] })).toEqual({ a: 'Bu alan zorunludur.' });
  });
});
