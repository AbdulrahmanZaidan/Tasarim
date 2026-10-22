import { useMemo, useState, type ReactNode } from 'react';
import { Search, Download, RotateCcw, AlertTriangle, ArrowUpDown, Pencil, Check, Info } from 'lucide-react';
import { parts, programmerParts, categories, sourceEstimate, calcTotal, hasMismatch, sumRanges, round2, type Part, type Range, type Category } from '../../data/parts';
import type { PhaseVM } from '../../data/public';
import { PageHeader, Section, Callout, StageNav, StatusBadge, Stat, Figure } from '../../components/ui';
import { useLocalState } from '../../lib/useLocalState';

type PStatus = 'none' | 'ordered' | 'received' | 'tested';
const pLabels: Record<PStatus, string> = { none: 'Alınmadı', ordered: 'Sipariş Verildi', received: 'Teslim Alındı', tested: 'Test Edildi' };
const pStyles: Record<PStatus, string> = {
  none: 'border-ink-3/25 bg-white text-ink-3', ordered: 'border-amber-400 bg-amber-50 text-amber-800',
  received: 'border-sky-400 bg-sky-50 text-sky-800', tested: 'border-emerald-500 bg-emerald-50 text-emerald-800',
};

interface Edit { qty?: number; unit?: number; status?: PStatus }
interface Store { items: Record<string, Edit>; extra: Record<string, Edit>; shipping: number; rate: number | null; includeExtra: boolean }
const initialStore: Store = { items: {}, extra: {}, shipping: 0, rate: null, includeExtra: false };

const usd = (n: number) => `$${n.toFixed(2)}`;
const rng = (r: Range) => (r.min === r.max ? usd(r.min) : `${usd(r.min)} – ${usd(r.max)}`);
const tryFmt = (n: number) => n.toLocaleString('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 });

type SortKey = 'order' | 'name' | 'category' | 'qty' | 'total';

/**
 * Supabase yapılandırılmadığında kullanılan özgün malzeme sayfası.
 * Ziyaretçi düzenlemeleri yalnızca kendi tarayıcısında (localStorage) saklanır.
 */
export default function MaterialsStatic({ stage, notice }: { stage?: PhaseVM; notice?: ReactNode }) {
  const [store, setStore] = useLocalState<Store>('sdu8bit.materials.v1', initialStore);
  const [q, setQ] = useState('');
  const [cat, setCat] = useState<'all' | Category>('all');
  const [stf, setStf] = useState<'all' | PStatus>('all');
  const [sort, setSort] = useState<{ k: SortKey; dir: 1 | -1 }>({ k: 'order', dir: 1 });
  const [editing, setEditing] = useState(false);

  const eff = (p: Part) => {
    const e = store.items[p.id] ?? {};
    const qty = e.qty ?? p.qty;
    const unit: Range = e.unit !== undefined ? { min: e.unit, max: e.unit } : p.unit;
    return { qty, unit, total: calcTotal({ qty, unit }), status: (e.status ?? 'none') as PStatus, edited: e.qty !== undefined || e.unit !== undefined };
  };
  const setItem = (id: string, patch: Edit) => setStore((s) => ({ ...s, items: { ...s.items, [id]: { ...s.items[id], ...patch } } }));
  const setExtra = (id: string, patch: Edit) => setStore((s) => ({ ...s, extra: { ...s.extra, [id]: { ...s.extra[id], ...patch } } }));

  const stated = sumRanges(parts.map((p) => p.statedTotal));
  const calculated = sumRanges(parts.map((p) => calcTotal(p)));
  const editedParts = sumRanges(parts.map((p) => eff(p).total));
  const extraTotal = round2(programmerParts.reduce((a, x) => a + (store.extra[x.id]?.unit ?? 0) * (store.extra[x.id]?.qty ?? x.qty), 0));
  const extraPriced = programmerParts.some((x) => store.extra[x.id]?.unit !== undefined);
  const edited: Range = {
    min: round2(editedParts.min + store.shipping + (store.includeExtra ? extraTotal : 0)),
    max: round2(editedParts.max + store.shipping + (store.includeExtra ? extraTotal : 0)),
  };
  const refQty = parts.reduce((a, p) => a + p.qty, 0);
  const curQty = parts.reduce((a, p) => a + eff(p).qty, 0);
  const counts = parts.reduce((a, p) => { a[eff(p).status]++; return a; }, { none: 0, ordered: 0, received: 0, tested: 0 } as Record<PStatus, number>);
  const mismatches = parts.filter(hasMismatch);
  const anyEdited = parts.some((p) => eff(p).edited) || store.shipping > 0;

  const rows = useMemo(() => {
    const norm = (s: string) => s.toLocaleLowerCase('tr-TR');
    let r = parts.map((p, i) => ({ p, i, e: eff(p) }));
    if (q.trim()) r = r.filter(({ p }) => norm(`${p.name} ${p.source} ${p.category}`).includes(norm(q.trim())));
    if (cat !== 'all') r = r.filter(({ p }) => p.category === cat);
    if (stf !== 'all') r = r.filter(({ e }) => e.status === stf);
    const key = (x: (typeof r)[number]): string | number =>
      sort.k === 'name' ? x.p.name : sort.k === 'category' ? categories.indexOf(x.p.category) * 100 + x.i : sort.k === 'qty' ? x.e.qty : sort.k === 'total' ? x.e.total.max : x.i;
    return [...r].sort((a, b) => { const ka = key(a), kb = key(b); return (typeof ka === 'string' ? ka.localeCompare(kb as string, 'tr') : ka - (kb as number)) * sort.dir; });
  }, [q, cat, stf, sort, store]);

  const byCat = categories.map((c) => ({ c, r: sumRanges(parts.filter((p) => p.category === c).map((p) => p.statedTotal)) }));
  const maxCat = Math.max(...byCat.map((x) => x.r.max));

  const exportCsv = () => {
    const n = (x: number) => x.toFixed(2).replace('.', ',');
    const nr = (r: Range) => (r.min === r.max ? n(r.min) : `${n(r.min)} - ${n(r.max)}`);
    const head = ['Malzeme Adı', 'Kaynaktaki Tanım', 'Kategori', 'Adet (referans)', 'Adet (güncel)', 'Birim Fiyat USD (referans)', 'Birim Fiyat USD (güncel)', 'Toplam USD (kaynak beyanı)', 'Toplam USD (adet x birim)', 'Toplam USD (güncel)', 'Satın Alma Durumu'];
    const lines = parts.map((p) => {
      const e = eff(p);
      return [p.name, p.source, p.category, p.qty, e.qty, nr(p.unit), nr(e.unit), nr(p.statedTotal), nr(calcTotal(p)), nr(e.total), pLabels[e.status]];
    });
    lines.push([], ['Kargo (USD)', store.shipping] as never);
    const csv = [head, ...lines].map((l) => (l as (string | number)[]).map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(';')).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'malzeme-listesi-8bit.csv'; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  const Th = ({ k, children, className = '' }: { k?: SortKey; children: ReactNode; className?: string }) => (
    <th scope="col" className={`whitespace-nowrap px-3 py-2.5 text-left text-[12px] font-semibold uppercase tracking-[0.06em] text-brand ${className}`}
      aria-sort={k && sort.k === k ? (sort.dir === 1 ? 'ascending' : 'descending') : undefined}>
      {k ? <button className="inline-flex items-center gap-1 uppercase hover:text-brand-dark" onClick={() => setSort((s) => ({ k, dir: s.k === k ? (s.dir === 1 ? -1 : 1) : 1 }))}>{children}<ArrowUpDown size={12} aria-hidden className={sort.k === k ? 'opacity-100' : 'opacity-40'} /></button> : children}
    </th>
  );

  return (
    <>
      <PageHeader eyebrow={`Aşama ${stage?.number ?? '04'} · Tasarım I`} title="Malzeme ve Maliyet Analizi"
        subtitle="Ben Eater referans malzeme listesinin tamamı, maliyet özeti, kur ile TL tahmini ve satın alma takibi."
        crumbs={[{ label: 'Proje Planı', to: '/proje' }, { label: 'Malzeme ve Maliyet' }]} right={stage && <StatusBadge status={stage.status} size="md" />} />
      {notice && <div className="container-x pt-6">{notice}</div>}

      <div className="container-x pt-6">
        <Callout tone="warn" title="Fiyatlar tarihsel / referans değerlerdir">
          Tablodaki fiyatlar referans listede ABD tedarikçileri için verilen <b>yaklaşık</b> USD değerleridir; güncel Türkiye piyasa fiyatlarından önemli ölçüde farklı olabilir ve doğrulanmış satın alma teklifi değildir.
          Gerçek teklifler “Düzenle” kipinde girilebilir. Değişiklikler yalnızca bu tarayıcıda saklanır.
        </Callout>
      </div>

      <Section eyebrow="Özet" title="Maliyet ve satın alma panosu">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Stat label="Kalem türü" value={parts.length} hint={`+ ${programmerParts.length} ek programlayıcı malzemesi`} />
          <Stat label="Toplam adet" value={curQty} hint={curQty !== refQty ? `Referans: ${refQty}` : 'Referans listeye göre'} />
          <Stat label="Kaynak tahmini" value={`$${sourceEstimate.min}–${sourceEstimate.max}`} hint="Kargo dâhil, kaynak beyanı (tarihsel)" />
          <Stat label="Satın alınan" value={counts.received + counts.tested} hint={`Teslim alındı: ${counts.received} · Test edildi: ${counts.tested}`} />
          <Stat label="Kalan" value={counts.none + counts.ordered} hint={`Alınmadı: ${counts.none} · Sipariş verildi: ${counts.ordered}`} />
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <div className="card p-4">
            <div className="text-[12px] font-semibold uppercase tracking-[0.1em] text-brand">Kaynakta yazan satır toplamları</div>
            <div className="mono mt-1.5 text-[20px] font-bold">{rng(stated)}</div>
            <p className="mt-1 text-[12px] leading-5 text-ink-3">Tablodaki kaynak toplamlarının doğrudan toplamı (kargo hariç). Aralık, breadboard fiyatının $4–$9 olmasından kaynaklanır.</p>
          </div>
          <div className="card p-4">
            <div className="text-[12px] font-semibold uppercase tracking-[0.1em] text-brand">Hesaplanan (adet × birim fiyat)</div>
            <div className="mono mt-1.5 text-[20px] font-bold">{rng(calculated)}</div>
            <p className="mt-1 text-[12px] leading-5 text-ink-3">Referans birim fiyatlardan matematiksel hesap. {mismatches.length} satırda kaynak toplamından farklıdır (aşağıya bakınız).</p>
          </div>
          <div className="card border-brand p-4">
            <div className="text-[12px] font-semibold uppercase tracking-[0.1em] text-brand">Güncel proje tahmini</div>
            <div className="mono mt-1.5 text-[20px] font-bold">{rng(edited)}</div>
            <p className="mt-1 text-[12px] leading-5 text-ink-3">{anyEdited ? 'Girdiğiniz adet / fiyat değişiklikleri ve kargo dâhil.' : 'Henüz yerel teklif girilmedi; referans fiyatlarla hesaplanmıştır.'}{store.includeExtra && extraPriced ? ' Ek malzemeler dâhil.' : ''}</p>
            {store.rate ? <div className="mono mt-2 rounded bg-brand-mist px-2 py-1 text-[14px]">≈ {edited.min === edited.max ? tryFmt(edited.min * store.rate) : `${tryFmt(edited.min * store.rate)} – ${tryFmt(edited.max * store.rate)}`} <span className="font-sans text-[11px] text-ink-3">(tahmini)</span></div> : null}
          </div>
        </div>

        <div className="card-soft mt-4 grid gap-4 p-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <div>
            <label htmlFor="rate" className="mb-1 block text-[13px] font-medium text-ink-2">USD/TRY kuru (isteğe bağlı, elle girilir)</label>
            <input id="rate" type="number" min={0} step="0.01" placeholder="ör. güncel kuru giriniz" value={store.rate ?? ''} className="input mono"
              onChange={(e) => setStore((s) => ({ ...s, rate: e.target.value === '' ? null : Math.max(0, Number(e.target.value)) }))} />
            <p className="mt-1 text-[11.5px] text-ink-3">Canlı kur kullanılmaz. TL karşılıkları yalnızca tahmindir.</p>
          </div>
          <div>
            <label htmlFor="ship" className="mb-1 block text-[13px] font-medium text-ink-2">Kargo / ek masraf (USD)</label>
            <input id="ship" type="number" min={0} step="0.01" value={store.shipping || ''} placeholder="0" className="input mono"
              onChange={(e) => setStore((s) => ({ ...s, shipping: Math.max(0, Number(e.target.value) || 0) }))} />
            <p className="mt-1 text-[11.5px] text-ink-3">Yerel teklif TL ise kura bölerek USD olarak girebilirsiniz.</p>
          </div>
          <button className="btn-ghost text-[13px]" onClick={() => { if (confirm('Tüm yerel düzenlemeler (adet, fiyat, durum, kur, kargo) silinsin mi?')) setStore(initialStore); }}><RotateCcw size={15} aria-hidden /> Düzenlemeleri sıfırla</button>
        </div>
      </Section>

      <Section eyebrow="Malzeme listesi" title="Tam referans malzeme listesi" intro={<>Kaynaktaki <b>{parts.length} satırın tamamı</b> özgün adet ve fiyatlarıyla listelenmiştir. Sıralamak için sütun başlıklarına tıklayın.</>}>
        <div className="mb-3 grid gap-2 md:grid-cols-[1fr_auto_auto_auto_auto]">
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" aria-hidden />
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Malzeme ara (ör. 74LS173, LED, direnç)" className="input pl-9" aria-label="Malzeme ara" />
          </div>
          <select className="input w-auto" value={cat} onChange={(e) => setCat(e.target.value as typeof cat)} aria-label="Kategori filtresi">
            <option value="all">Tüm kategoriler</option>{categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select className="input w-auto" value={stf} onChange={(e) => setStf(e.target.value as typeof stf)} aria-label="Durum filtresi">
            <option value="all">Tüm durumlar</option>{(Object.keys(pLabels) as PStatus[]).map((k) => <option key={k} value={k}>{pLabels[k]}</option>)}
          </select>
          <button className={editing ? 'btn-primary' : 'btn-outline'} onClick={() => setEditing(!editing)} aria-pressed={editing}>{editing ? <><Check size={16} aria-hidden /> Bitti</> : <><Pencil size={15} aria-hidden /> Düzenle</>}</button>
          <button className="btn-outline" onClick={exportCsv}><Download size={16} aria-hidden /> CSV</button>
        </div>
        <div className="mb-2 text-[13px] text-ink-3" aria-live="polite">{rows.length} / {parts.length} kalem gösteriliyor{editing && ' · Düzenleme kipi: adet ve birim fiyat (USD) girilebilir'}</div>

        <div className="card overflow-x-auto">
          <table className="w-full min-w-[980px] text-[13.5px]">
            <thead className="border-b-2 border-brand bg-brand-mist">
              <tr>
                <Th k="name">Malzeme Adı</Th><Th k="category">Kategori</Th><Th k="qty" className="text-right">Adet</Th>
                <Th className="text-right">Birim Fiyat (USD)</Th><Th k="total" className="text-right">Toplam Fiyat (USD)</Th><Th>Satın Alma Durumu</Th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={6} className="px-3 py-10 text-center text-ink-3">Aramanızla eşleşen malzeme bulunamadı.</td></tr>}
              {rows.map(({ p, e }) => {
                const mis = hasMismatch(p), calc = calcTotal(p);
                return (
                  <tr key={p.id} className="border-b border-brand-line/50 align-top transition-colors hover:bg-brand-mist/40">
                    <td className="px-3 py-2.5">
                      <div className="font-semibold text-ink">{p.name}</div>
                      <div className="text-[12px] text-ink-3">{p.source}</div>
                      {p.note && <div className="mt-1 flex gap-1 text-[12px] text-ink-2"><Info size={13} className="mt-0.5 shrink-0 text-brand" aria-hidden />{p.note}</div>}
                    </td>
                    <td className="px-3 py-2.5 text-[12.5px] text-ink-2">{p.category}</td>
                    <td className="mono px-3 py-2.5 text-right">
                      {editing ? <input type="number" min={0} aria-label={`${p.name} adet`} className="input mono w-20 py-1 text-right" value={e.qty}
                        onChange={(ev) => setItem(p.id, { qty: Math.max(0, Math.floor(Number(ev.target.value) || 0)) })} /> : <>{e.qty}{e.qty !== p.qty && <div className="text-[11px] text-ink-3">ref. {p.qty}</div>}</>}
                    </td>
                    <td className="mono px-3 py-2.5 text-right">
                      {editing ? <input type="number" min={0} step="0.01" aria-label={`${p.name} birim fiyat`} placeholder={p.unit.min === p.unit.max ? String(p.unit.min) : `${p.unit.min}–${p.unit.max}`}
                        className="input mono w-24 py-1 text-right" value={store.items[p.id]?.unit ?? ''}
                        onChange={(ev) => setItem(p.id, { unit: ev.target.value === '' ? undefined : Math.max(0, Number(ev.target.value)) })} /> :
                        <>{rng(e.unit)}{store.items[p.id]?.unit !== undefined && <div className="text-[11px] text-ink-3">ref. {rng(p.unit)}</div>}</>}
                    </td>
                    <td className="mono px-3 py-2.5 text-right">
                      <div className="font-semibold">{rng(e.edited ? e.total : p.statedTotal)}</div>
                      {e.edited && <div className="text-[11px] text-ink-3">kaynak: {rng(p.statedTotal)}</div>}
                      {mis && !e.edited && (
                        <div className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-amber-700" title="Kaynakta yazan satır toplamı, adet × birim fiyat ile örtüşmüyor">
                          <AlertTriangle size={12} aria-hidden /> hesap: {rng(calc)}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <select aria-label={`${p.name} satın alma durumu`} value={e.status} onChange={(ev) => setItem(p.id, { status: ev.target.value as PStatus })}
                        className={`rounded-full border px-2.5 py-1 text-[12px] font-medium focus:outline-none focus:ring-2 focus:ring-brand/30 ${pStyles[e.status]}`}>
                        {(Object.keys(pLabels) as PStatus[]).map((k) => <option key={k} value={k}>{pLabels[k]}</option>)}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot className="border-t-2 border-brand bg-brand-mist font-semibold">
              <tr>
                <td className="px-3 py-2.5" colSpan={2}>Toplam ({parts.length} kalem)</td>
                <td className="mono px-3 py-2.5 text-right">{curQty}</td>
                <td />
                <td className="mono px-3 py-2.5 text-right">{rng(anyEdited ? editedParts : stated)}<div className="text-[11px] font-normal text-ink-3">{anyEdited ? 'güncel, kargo hariç' : 'kaynak beyanı, kargo hariç'}</div></td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      </Section>

      <Section eyebrow="Şeffaflık" title="Kaynaktaki tutarsız satır toplamları" intro="Aşağıdaki satırlarda kaynakta yazan toplam, adet ile birim fiyatın çarpımına eşit değildir. Kaynak değerleri değiştirilmeden korunmuş, hesaplanan değer ayrıca verilmiştir. Farkın olası nedeni paket hâlinde satış veya yuvarlamadır; bu bir varsayımdır.">
        <div className="card overflow-x-auto">
          <table className="mono w-full min-w-[560px] text-[13px]">
            <thead className="border-b-2 border-brand bg-brand-mist font-sans text-[12px] uppercase tracking-[0.06em] text-brand">
              <tr><th className="px-3 py-2 text-left">Malzeme</th><th className="px-3 text-right">Adet × Birim</th><th className="px-3 text-right">Kaynak toplamı</th><th className="px-3 text-right">Hesaplanan</th><th className="px-3 text-right">Fark</th></tr>
            </thead>
            <tbody>{mismatches.map((p) => {
              const c = calcTotal(p);
              return (
                <tr key={p.id} className="border-b border-brand-line/50">
                  <td className="px-3 py-1.5 font-sans">{p.name}</td><td className="px-3 text-right">{p.qty} × {rng(p.unit)}</td>
                  <td className="px-3 text-right">{rng(p.statedTotal)}</td><td className="px-3 text-right">{rng(c)}</td>
                  <td className="px-3 text-right text-amber-700">+{usd(round2(p.statedTotal.min - c.min))}</td>
                </tr>
              );
            })}</tbody>
            <tfoot className="font-semibold"><tr><td className="px-3 py-2 font-sans" colSpan={2}>Tüm liste toplamı</td><td className="px-3 text-right">{rng(stated)}</td><td className="px-3 text-right">{rng(calculated)}</td><td className="px-3 text-right text-amber-700">+{usd(round2(stated.min - calculated.min))}</td></tr></tfoot>
          </table>
        </div>
      </Section>

      <Section eyebrow="Bileşen dağılımı" title="Kategorilere göre referans maliyet">
        <Figure n="4" kind="referans" caption="Kaynakta yazan satır toplamlarının kategorilere göre dağılımı (USD). Açık renkli uzantı, breadboard fiyat aralığının üst sınırını gösterir.">
          <div className="space-y-2.5">
            {byCat.map(({ c, r }) => (
              <div key={c} className="grid grid-cols-[minmax(120px,220px)_1fr_auto] items-center gap-3 text-[13px]">
                <span className="text-ink-2">{c}</span>
                <div className="relative h-4 rounded bg-brand-mist" aria-hidden>
                  <div className="absolute inset-y-0 left-0 rounded bg-brand-line" style={{ width: `${(r.max / maxCat) * 100}%` }} />
                  <div className="absolute inset-y-0 left-0 rounded bg-brand transition-[width] duration-700" style={{ width: `${(r.min / maxCat) * 100}%` }} />
                </div>
                <span className="mono w-32 text-right">{rng(r)}</span>
              </div>
            ))}
          </div>
        </Figure>
      </Section>

      <Section eyebrow="Ek malzemeler" title="EEPROM Programlayıcı İçin Ek Malzemeler" intro={<>Kaynakta, çıkış modülü ve kontrol birimindeki 28C16 EEPROM’ların programlanması için bir Arduino Nano ve iki 74HC595 kaydırmalı yazmaçla basit bir EEPROM programlayıcı kurulduğu belirtilmektedir. Bu malzemelerin fiyatı kaynakta verilmediği için yukarıdaki toplamlara <b>dâhil edilmemiştir</b>.</>}>
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[640px] text-[13.5px]">
            <thead className="border-b-2 border-brand bg-brand-mist text-[12px] uppercase tracking-[0.06em] text-brand">
              <tr><th className="px-3 py-2.5 text-left">Malzeme Adı</th><th className="px-3 text-right">Adet</th><th className="px-3 text-right">Birim Fiyat (USD)</th><th className="px-3 text-left">Satın Alma Durumu</th></tr>
            </thead>
            <tbody>{programmerParts.map((x) => {
              const e = store.extra[x.id] ?? {};
              const st = (e.status ?? 'none') as PStatus;
              return (
                <tr key={x.id} className="border-b border-brand-line/50">
                  <td className="px-3 py-2.5 font-semibold">{x.name}<div className="text-[12px] font-normal text-ink-3">{x.note}</div></td>
                  <td className="mono px-3 text-right">{x.qty}</td>
                  <td className="px-3 text-right"><input type="number" min={0} step="0.01" placeholder="fiyat yok" aria-label={`${x.name} birim fiyat`} className="input mono w-28 py-1 text-right" value={e.unit ?? ''}
                    onChange={(ev) => setExtra(x.id, { unit: ev.target.value === '' ? undefined : Math.max(0, Number(ev.target.value)) })} /></td>
                  <td className="px-3">
                    <select aria-label={`${x.name} satın alma durumu`} value={st} onChange={(ev) => setExtra(x.id, { status: ev.target.value as PStatus })}
                      className={`rounded-full border px-2.5 py-1 text-[12px] font-medium ${pStyles[st]}`}>
                      {(Object.keys(pLabels) as PStatus[]).map((k) => <option key={k} value={k}>{pLabels[k]}</option>)}
                    </select>
                  </td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
        <label className="mt-3 flex items-center gap-2 text-[14px] text-ink-2">
          <input type="checkbox" className="h-4 w-4 accent-[#9E1B32]" checked={store.includeExtra} onChange={(e) => setStore((s) => ({ ...s, includeExtra: e.target.checked }))} />
          Girilen ek malzeme fiyatlarını “Güncel proje tahmini”ne dâhil et {extraPriced ? <span className="mono">({usd(extraTotal)})</span> : <span className="text-ink-3">(henüz fiyat girilmedi)</span>}
        </label>
        <p className="mt-2 text-[12px] text-ink-3">Not: Ek malzemelerin satın alma durumları yukarıdaki “Satın alınan / Kalan” sayaçlarına dâhil değildir; sayaçlar yalnızca ana listeyi kapsar.</p>
      </Section>

      <StageNav current="materials" />
    </>
  );
}
