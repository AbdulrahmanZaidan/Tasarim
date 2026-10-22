/** Veritabanından okunan, ekip tarafından güncellenen malzeme ve maliyet sayfası (ziyaretçiler için salt okunur). */
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Search, Download, ArrowUpDown, Info, ExternalLink, AlertTriangle, ShoppingCart, Lock } from 'lucide-react';
import type { MaterialsData, PhaseVM, SettingsVM } from '../../data/public';
import { PageHeader, Section, Callout, StageNav, StatusBadge, Stat, Figure, Badge } from '../../components/ui';
import { EmptyState, Skeleton } from '../../components/feedback';
import { summarize, unitPrice, combinedTRY, remainingQty, type Totals } from '../../lib/costs';
import { fmtDate, fmtMoney, fmtMoneyRange, norm } from '../../lib/format';
import { purchaseLabels, purchaseTone, type PurchaseStatus } from '../../lib/labels';
import { downloadCsv } from '../../lib/csv';
import type { Material } from '../../services/entities';

const TotalsView = ({ t, empty = '—' }: { t: Totals; empty?: string }) => {
  const e = Object.entries(t).filter(([, r]) => r.max > 0);
  if (!e.length) return <>{empty}</>;
  return <span className="flex flex-col">{e.map(([c, r]) => <span key={c}>{fmtMoneyRange(r.min, r.max, c)}</span>)}</span>;
};

type SortKey = 'order' | 'name' | 'category' | 'qty' | 'total';
const r2 = (n: number) => Math.round(n * 100) / 100;

export default function MaterialsLive({ data, loading, stage, settings, notice }: { data: MaterialsData; loading: boolean; stage?: PhaseVM; settings: SettingsVM; notice?: ReactNode }) {
  const [q, setQ] = useState('');
  const [cat, setCat] = useState('all');
  const [stf, setStf] = useState<'all' | PurchaseStatus>('all');
  const [sort, setSort] = useState<{ k: SortKey; dir: 1 | -1 }>({ k: 'order', dir: 1 });
  const [rate, setRate] = useState<string>(settings.usdTryRate ? String(settings.usdTryRate).replace('.', ',') : '');
  const [rateTouched, setRateTouched] = useState(false);
  // Ayarlar sonradan yüklenirse kayıtlı kur alana getirilir (ziyaretçi kendi değerini yazmadıysa)
  useEffect(() => { if (!rateTouched) setRate(settings.usdTryRate ? String(settings.usdTryRate).replace('.', ',') : ''); }, [settings.usdTryRate, rateTouched]);

  const main = data.materials.filter((m) => !m.is_programmer_extra);
  const extras = data.materials.filter((m) => m.is_programmer_extra);
  const categories = useMemo(() => [...new Set(main.map((m) => m.category))], [main]);
  const sum = useMemo(() => summarize(main, data.purchases.filter((p) => main.some((m) => m.id === p.material_id))), [main, data.purchases]);
  const allPurchases = useMemo(() => summarize(data.materials, data.purchases), [data]);
  const userRate = Number(rate.replace(',', '.')) || null;
  const combined = combinedTRY(sum.estimated, userRate);
  const combinedRemaining = combinedTRY(sum.remaining, userRate);

  const rows = useMemo(() => {
    let r = main.map((m, i) => ({ m, i, p: unitPrice(m) }));
    if (q.trim()) r = r.filter(({ m }) => norm(`${m.name} ${m.source_name ?? ''} ${m.category} ${m.supplier ?? ''}`).includes(norm(q.trim())));
    if (cat !== 'all') r = r.filter(({ m }) => m.category === cat);
    if (stf !== 'all') r = r.filter(({ m }) => m.purchase_status === stf);
    const key = (x: (typeof r)[number]): string | number =>
      sort.k === 'name' ? x.m.name : sort.k === 'category' ? categories.indexOf(x.m.category) * 1000 + x.i : sort.k === 'qty' ? x.m.required_quantity : sort.k === 'total' ? x.p.range.max * x.m.required_quantity : x.i;
    return [...r].sort((a, b) => { const ka = key(a), kb = key(b); return (typeof ka === 'string' ? ka.localeCompare(kb as string, 'tr') : ka - (kb as number)) * sort.dir; });
  }, [main, q, cat, stf, sort, categories]);

  const mismatches = main.filter((m) => m.ref_stated_total_min !== null && m.ref_unit_price_min !== null && m.ref_quantity !== null
    && (Math.abs(r2(m.ref_quantity * m.ref_unit_price_min) - m.ref_stated_total_min) > 0.004));
  const refStated = main.reduce((a, m) => ({ min: r2(a.min + (m.ref_stated_total_min ?? 0)), max: r2(a.max + (m.ref_stated_total_max ?? 0)) }), { min: 0, max: 0 });
  const refCalc = main.reduce((a, m) => ({ min: r2(a.min + (m.ref_quantity ?? 0) * (m.ref_unit_price_min ?? 0)), max: r2(a.max + (m.ref_quantity ?? 0) * (m.ref_unit_price_max ?? 0)) }), { min: 0, max: 0 });

  const exportCsv = () => {
    const n = (x: number | null) => (x === null ? '' : String(x).replace('.', ','));
    downloadCsv('malzeme-listesi-8bit.csv', [
      ['Malzeme Adı', 'Kaynaktaki Tanım', 'Kategori', 'Gerekli Adet', 'Satın Alınan Adet', 'Birim Fiyat', 'Para Birimi', 'Fiyat Kaynağı', 'Referans Birim Fiyat (USD)', 'Referans Satır Toplamı (USD)', 'Tedarikçi', 'Ürün Bağlantısı', 'Satın Alma Durumu'],
      ...main.map((m) => {
        const p = unitPrice(m);
        return [m.name, m.source_name ?? '', m.category, m.required_quantity, m.purchased_quantity, n(p.source === 'none' ? null : p.range.min) + (p.range.max !== p.range.min ? ` - ${n(p.range.max)}` : ''),
          p.currency, p.source === 'quote' ? 'Yerel teklif' : p.source === 'reference' ? 'Referans (tarihsel)' : 'Yok',
          n(m.ref_unit_price_min) + (m.ref_unit_price_max !== m.ref_unit_price_min ? ` - ${n(m.ref_unit_price_max)}` : ''),
          n(m.ref_stated_total_min) + (m.ref_stated_total_max !== m.ref_stated_total_min ? ` - ${n(m.ref_stated_total_max)}` : ''),
          m.supplier ?? '', m.product_url ?? '', purchaseLabels[m.purchase_status]];
      }),
    ]);
  };

  const Th = ({ k, children, className = '' }: { k?: SortKey; children: ReactNode; className?: string }) => (
    <th scope="col" className={`whitespace-nowrap px-3 py-2.5 text-left text-[12px] font-semibold uppercase tracking-[0.06em] text-brand ${className}`}
      aria-sort={k && sort.k === k ? (sort.dir === 1 ? 'ascending' : 'descending') : undefined}>
      {k ? <button className="inline-flex items-center gap-1 uppercase hover:text-brand-dark" onClick={() => setSort((s) => ({ k, dir: s.k === k ? (s.dir === 1 ? -1 : 1) : 1 }))}>{children}<ArrowUpDown size={12} aria-hidden className={sort.k === k ? 'opacity-100' : 'opacity-40'} /></button> : children}
    </th>
  );
  const byCat = categories.map((c) => {
    const items = main.filter((m) => m.category === c);
    return { c, min: r2(items.reduce((a, m) => a + (m.ref_stated_total_min ?? 0), 0)), max: r2(items.reduce((a, m) => a + (m.ref_stated_total_max ?? 0), 0)) };
  });
  const maxCat = Math.max(1, ...byCat.map((x) => x.max));
  const matName = (id: string) => data.materials.find((m) => m.id === id)?.name ?? '—';

  return (
    <>
      <PageHeader eyebrow={`Aşama ${stage?.number ?? '04'} · Tasarım I`} title="Malzeme ve Maliyet Analizi"
        subtitle="Projenin malzeme listesi, maliyet tahmini ve ekip tarafından kaydedilen satın almalar."
        crumbs={[{ label: 'Proje Planı', to: '/proje' }, { label: 'Malzeme ve Maliyet' }]} right={stage && <StatusBadge status={stage.status} size="md" />} />

      <div className="container-x space-y-3 pt-6">
        {notice}
        <Callout tone="warn" title="Fiyatların kaynağı">
          Ekip tarafından girilen <b>yerel teklifler</b> varsayılan olarak Türk lirası (TL) cinsindendir. Teklif girilmemiş kalemlerde referans listedeki
          <b> tarihsel, yaklaşık USD</b> fiyatları kullanılır; bunlar güncel Türkiye fiyatı değildir. Farklı para birimleri <b>birbirine eklenmez</b>;
          birleşik TL tahmini yalnızca bir kur girildiğinde gösterilir.
        </Callout>
      </div>

      <Section eyebrow="Özet" title="Maliyet ve satın alma panosu">
        {loading ? <div className="grid gap-3 sm:grid-cols-5">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24" />)}</div> : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <Stat label="Kalem türü" value={sum.itemCount} hint={`+ ${extras.length} ek programlayıcı malzemesi`} />
              <Stat label="Gerekli adet" value={sum.requiredQty} hint={`Kalan: ${sum.remainingQty} adet`} />
              <Stat label="Satın alınan" value={sum.purchasedQty} hint={`Tamamı alınan kalem: ${sum.fullyPurchased} · kısmi: ${sum.partiallyPurchased}`} />
              <Stat label="Alınmamış kalem" value={sum.notPurchased} hint={`${sum.quotedItems} kalemde yerel teklif, ${sum.referenceItems} kalemde referans fiyat`} />
              <Stat label="Kayıtlı harcama" value={<span className="text-[17px]"><TotalsView t={allPurchases.purchased} empty="Henüz yok" /></span>}
                hint={allPurchases.purchasesWithoutPrice ? `${allPurchases.purchasesWithoutPrice} satın almada fiyat girilmemiş` : `${data.purchases.length} satın alma kaydı`} />
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-3">
              <div className="card p-4">
                <div className="text-[12px] font-semibold uppercase tracking-[0.1em] text-brand">Tahmini toplam maliyet</div>
                <div className="mono mt-1.5 text-[18px] font-bold"><TotalsView t={sum.estimated} /></div>
                <p className="mt-1 text-[12px] leading-5 text-ink-3">Para birimlerine göre ayrı toplamlar (kargo hariç).</p>
              </div>
              <div className="card p-4">
                <div className="text-[12px] font-semibold uppercase tracking-[0.1em] text-brand">Kalan tahmini maliyet</div>
                <div className="mono mt-1.5 text-[18px] font-bold"><TotalsView t={sum.remaining} empty="Tüm malzemeler alındı" /></div>
                <p className="mt-1 text-[12px] leading-5 text-ink-3">Henüz alınmamış adetler için.</p>
              </div>
              <div className="card border-brand p-4">
                <div className="text-[12px] font-semibold uppercase tracking-[0.1em] text-brand">Birleşik TL tahmini</div>
                <label htmlFor="live-rate" className="mt-1.5 block text-[12px] text-ink-3">USD/TRY kuru {settings.usdTryRate ? `(kayıtlı: ${settings.usdTryRate.toLocaleString('tr-TR')} · ${fmtDate(settings.rateDate)})` : '(elle girin)'}</label>
                <input id="live-rate" inputMode="decimal" className="input mono mt-1" placeholder="ör. güncel kuru giriniz" value={rate} onChange={(e) => { setRateTouched(true); setRate(e.target.value); }} />
                <div className="mono mt-2 text-[15px] font-semibold">
                  {combined ? <>≈ {fmtMoneyRange(combined.min, combined.max, 'TRY', 0)} <span className="font-sans text-[11px] font-normal text-ink-3">(tahmini)</span></> : <span className="font-sans text-[13px] font-normal text-ink-3">Kur girilmeden USD ve TL toplamları birleştirilmez.</span>}
                </div>
                {combined && combinedRemaining && <div className="mt-0.5 text-[12px] text-ink-3">Kalan: ≈ {fmtMoneyRange(combinedRemaining.min, combinedRemaining.max, 'TRY', 0)}</div>}
              </div>
            </div>
          </>
        )}
      </Section>

      <Section eyebrow="Malzeme listesi" title="Proje malzeme listesi" intro={<>Liste ekip tarafından güncellenir. Sıralamak için sütun başlıklarına tıklayın. Düzenleme yalnızca yetkili ekip üyeleri tarafından <Link to="/admin/materials">yönetim panelinden</Link> yapılır.</>}>
        <div className="mb-3 grid gap-2 md:grid-cols-[1fr_auto_auto_auto]">
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" aria-hidden />
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Malzeme ara (ör. 74LS173, LED, direnç)" className="input pl-9" aria-label="Malzeme ara" />
          </div>
          <select className="input w-auto" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Kategori filtresi">
            <option value="all">Tüm kategoriler</option>{categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select className="input w-auto" value={stf} onChange={(e) => setStf(e.target.value as typeof stf)} aria-label="Durum filtresi">
            <option value="all">Tüm durumlar</option>{(Object.keys(purchaseLabels) as PurchaseStatus[]).map((k) => <option key={k} value={k}>{purchaseLabels[k]}</option>)}
          </select>
          <button className="btn-outline" onClick={exportCsv}><Download size={16} aria-hidden /> CSV</button>
        </div>
        <div className="mb-2 flex items-center gap-1.5 text-[13px] text-ink-3" aria-live="polite"><Lock size={13} aria-hidden /> {rows.length} / {main.length} kalem gösteriliyor · salt okunur görünüm</div>

        {loading ? <Skeleton className="h-96 w-full" /> : (
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[980px] text-[13.5px]">
              <thead className="border-b-2 border-brand bg-brand-mist">
                <tr>
                  <Th k="name">Malzeme Adı</Th><Th k="category">Kategori</Th><Th k="qty" className="text-right">Adet</Th>
                  <Th className="text-right">Birim Fiyat</Th><Th k="total" className="text-right">Toplam (tahmini)</Th><Th>Kaynak</Th><Th>Satın Alma Durumu</Th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && <tr><td colSpan={7} className="px-3 py-10 text-center text-ink-3">Aramanızla eşleşen malzeme bulunamadı.</td></tr>}
                {rows.map(({ m, p }) => (
                  <tr key={m.id} className="border-b border-brand-line/50 align-top transition-colors hover:bg-brand-mist/40">
                    <td className="px-3 py-2.5">
                      <div className="font-semibold text-ink">{m.name}</div>
                      {m.source_name && <div className="text-[12px] text-ink-3">{m.source_name}</div>}
                      {m.notes && <div className="mt-1 flex gap-1 text-[12px] text-ink-2"><Info size={13} className="mt-0.5 shrink-0 text-brand" aria-hidden />{m.notes}</div>}
                    </td>
                    <td className="px-3 py-2.5 text-[12.5px] text-ink-2">{m.category}</td>
                    <td className="mono px-3 py-2.5 text-right">{m.required_quantity}
                      <div className={`text-[11px] ${m.purchased_quantity >= m.required_quantity && m.required_quantity > 0 ? 'text-emerald-700' : 'text-ink-3'}`}>alınan {m.purchased_quantity}{remainingQty(m) > 0 && m.purchased_quantity > 0 ? ` · kalan ${remainingQty(m)}` : ''}</div>
                    </td>
                    <td className="mono px-3 py-2.5 text-right">{p.source === 'none' ? '—' : fmtMoneyRange(p.range.min, p.range.max, p.currency)}
                      <div className="font-sans text-[11px] text-ink-3">{p.source === 'quote' ? 'yerel teklif' : p.source === 'reference' ? 'referans (tarihsel)' : 'fiyat yok'}</div>
                    </td>
                    <td className="mono px-3 py-2.5 text-right font-semibold">{p.source === 'none' ? '—' : fmtMoneyRange(p.range.min * m.required_quantity, p.range.max * m.required_quantity, p.currency)}
                      {p.source === 'reference' && m.ref_stated_total_min !== null && Math.abs(r2((m.ref_quantity ?? 0) * (m.ref_unit_price_min ?? 0)) - m.ref_stated_total_min) > 0.004 && (
                        <div className="mt-0.5 inline-flex items-center gap-1 font-sans text-[11px] font-normal text-amber-700" title="Referans listedeki satır toplamı, adet × birim fiyat ile örtüşmüyor"><AlertTriangle size={12} aria-hidden /> listede: {fmtMoneyRange(m.ref_stated_total_min, m.ref_stated_total_max ?? m.ref_stated_total_min, 'USD')}</div>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-[12.5px]">
                      {m.supplier ?? (p.source === 'reference' ? 'Referans liste' : '—')}
                      {m.product_url && <a href={m.product_url} target="_blank" rel="noreferrer nofollow" className="ml-1 inline-flex items-center gap-0.5">ürün <ExternalLink size={11} aria-hidden /></a>}
                    </td>
                    <td className="px-3 py-2.5"><Badge tone={purchaseTone[m.purchase_status]}>{purchaseLabels[m.purchase_status]}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section eyebrow="Satın almalar" title="Kayıtlı satın almalar" intro="Ekip tarafından kaydedilen gerçek satın almalar. Her kayıt ilgili malzemenin “satın alınan adet” değerini otomatik olarak günceller.">
        {data.purchases.length === 0 ? (
          <EmptyState icon={<ShoppingCart size={28} aria-hidden />} title="Henüz satın alma kaydı yok">Malzemeler satın alındıkça tarih, tedarikçi ve fiyat bilgisiyle burada listelenecektir.</EmptyState>
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[640px] text-[13.5px]">
              <thead className="border-b-2 border-brand bg-brand-mist text-[12px] uppercase tracking-[0.06em] text-brand">
                <tr><th className="px-3 py-2.5 text-left">Tarih</th><th className="px-3 text-left">Malzeme</th><th className="px-3 text-right">Adet</th><th className="px-3 text-right">Birim fiyat</th><th className="px-3 text-right">Tutar</th><th className="px-3 text-left">Tedarikçi</th></tr>
              </thead>
              <tbody>{data.purchases.slice(0, 50).map((p) => (
                <tr key={p.id} className="border-b border-brand-line/50">
                  <td className="px-3 py-2">{fmtDate(p.purchase_date)}</td>
                  <td className="px-3 font-medium">{matName(p.material_id)}</td>
                  <td className="mono px-3 text-right">{p.quantity}</td>
                  <td className="mono px-3 text-right">{p.unit_price === null ? '—' : fmtMoney(p.unit_price, p.currency)}</td>
                  <td className="mono px-3 text-right">{p.unit_price === null ? '—' : fmtMoney(p.unit_price * p.quantity, p.currency)}</td>
                  <td className="px-3">{p.supplier ?? '—'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Section>

      {mismatches.length > 0 && (
        <Section eyebrow="Şeffaflık" title="Referans listedeki tutarsız satır toplamları" intro="Bu satırlarda referans listede yazan toplam, adet ile birim fiyatın çarpımına eşit değildir. Liste değerleri değiştirilmeden korunmuş, hesaplanan değer ayrıca verilmiştir.">
          <div className="card overflow-x-auto">
            <table className="mono w-full min-w-[560px] text-[13px]">
              <thead className="border-b-2 border-brand bg-brand-mist font-sans text-[12px] uppercase tracking-[0.06em] text-brand">
                <tr><th className="px-3 py-2 text-left">Malzeme</th><th className="px-3 text-right">Adet × Birim</th><th className="px-3 text-right">Liste toplamı</th><th className="px-3 text-right">Hesaplanan</th><th className="px-3 text-right">Fark</th></tr>
              </thead>
              <tbody>{mismatches.map((m) => {
                const calc = r2((m.ref_quantity ?? 0) * (m.ref_unit_price_min ?? 0));
                return (
                  <tr key={m.id} className="border-b border-brand-line/50">
                    <td className="px-3 py-1.5 font-sans">{m.name}</td><td className="px-3 text-right">{m.ref_quantity} × {fmtMoney(m.ref_unit_price_min ?? 0, 'USD')}</td>
                    <td className="px-3 text-right">{fmtMoney(m.ref_stated_total_min ?? 0, 'USD')}</td><td className="px-3 text-right">{fmtMoney(calc, 'USD')}</td>
                    <td className="px-3 text-right text-amber-700">+{fmtMoney(r2((m.ref_stated_total_min ?? 0) - calc), 'USD')}</td>
                  </tr>
                );
              })}</tbody>
              <tfoot className="font-semibold"><tr><td className="px-3 py-2 font-sans" colSpan={2}>Tüm referans liste</td><td className="px-3 text-right">{fmtMoneyRange(refStated.min, refStated.max, 'USD')}</td><td className="px-3 text-right">{fmtMoneyRange(refCalc.min, refCalc.max, 'USD')}</td><td className="px-3 text-right text-amber-700">+{fmtMoney(r2(refStated.min - refCalc.min), 'USD')}</td></tr></tfoot>
            </table>
          </div>
        </Section>
      )}

      <Section eyebrow="Bileşen dağılımı" title="Kategorilere göre referans maliyet">
        <Figure n="4" kind="referans" caption="Referans listedeki satır toplamlarının kategorilere göre dağılımı (USD, tarihsel). Açık renkli uzantı, breadboard fiyat aralığının üst sınırını gösterir.">
          <div className="space-y-2.5">
            {byCat.filter((x) => x.max > 0).map(({ c, min, max }) => (
              <div key={c} className="grid grid-cols-[minmax(120px,220px)_1fr_auto] items-center gap-3 text-[13px]">
                <span className="text-ink-2">{c}</span>
                <div className="relative h-4 rounded bg-brand-mist" aria-hidden>
                  <div className="absolute inset-y-0 left-0 rounded bg-brand-line" style={{ width: `${(max / maxCat) * 100}%` }} />
                  <div className="absolute inset-y-0 left-0 rounded bg-brand transition-[width] duration-700" style={{ width: `${(min / maxCat) * 100}%` }} />
                </div>
                <span className="mono w-32 text-right">{fmtMoneyRange(min, max, 'USD')}</span>
              </div>
            ))}
          </div>
        </Figure>
      </Section>

      {extras.length > 0 && (
        <Section eyebrow="Ek malzemeler" title="EEPROM Programlayıcı İçin Ek Malzemeler" intro="28C16 EEPROM’ları programlamak için kullanılacak ek malzemeler. Referans listede fiyatları bulunmadığından, ekip teklif girene kadar yukarıdaki toplamlara dâhil edilmez.">
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[560px] text-[13.5px]">
              <thead className="border-b-2 border-brand bg-brand-mist text-[12px] uppercase tracking-[0.06em] text-brand">
                <tr><th className="px-3 py-2.5 text-left">Malzeme Adı</th><th className="px-3 text-right">Adet</th><th className="px-3 text-right">Birim Fiyat</th><th className="px-3 text-left">Satın Alma Durumu</th></tr>
              </thead>
              <tbody>{extras.map((x: Material) => (
                <tr key={x.id} className="border-b border-brand-line/50">
                  <td className="px-3 py-2.5 font-semibold">{x.name}{x.notes && <div className="text-[12px] font-normal text-ink-3">{x.notes}</div>}</td>
                  <td className="mono px-3 text-right">{x.required_quantity}</td>
                  <td className="mono px-3 text-right">{x.unit_price === null ? 'fiyat yok' : fmtMoney(x.unit_price, x.currency)}</td>
                  <td className="px-3"><Badge tone={purchaseTone[x.purchase_status]}>{purchaseLabels[x.purchase_status]}</Badge></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Section>
      )}

      <StageNav current="materials" />
    </>
  );
}
