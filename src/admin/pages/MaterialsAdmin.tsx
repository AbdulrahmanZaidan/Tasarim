import { useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Pencil, Trash2, Upload, Download, HardDriveDownload, ShoppingCart, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { AdminPage, ReadOnlyNotice, SearchBox, Table, Th, Td } from '../ui';
import { useMaterials, usePurchases, useSettings } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { Modal, useConfirm, useToast, SkeletonRows, ErrorNotice } from '../../components/feedback';
import { Select, TextArea, TextInput, Checkbox, useForm, v, nn } from '../../components/form';
import { Badge, Callout, Stat } from '../../components/ui';
import { materials as matSvc, type Material } from '../../services/entities';
import { summarize, unitPrice, combinedTRY, type Totals } from '../../lib/costs';
import { purchaseLabels, purchaseTone, options, type PurchaseStatus } from '../../lib/labels';
import { fmtMoney, fmtMoneyRange, norm } from '../../lib/format';
import { errorMessage } from '../../lib/errors';
import { invalidate } from '../../lib/query';
import { materialsToCsv, previewMaterialsCsv, previewLegacy, readLegacyStore, slugify, LEGACY_STORAGE_KEY, type ImportPreview, type LegacyPreview } from '../../lib/materialsImport';

const TotalsText = ({ t }: { t: Totals }) => {
  const e = Object.entries(t).filter(([, r]) => r.max > 0);
  return e.length ? <span className="flex flex-col">{e.map(([c, r]) => <span key={c}>{fmtMoneyRange(r.min, r.max, c, 0)}</span>)}</span> : <>—</>;
};

type Vals = { name: string; slug: string; source_name: string; category: string; description: string; required_quantity: string; unit_price: string; currency: string; supplier: string; product_url: string; purchase_status: PurchaseStatus; notes: string; is_programmer_extra: boolean; sort_order: string };

function Editor({ row, categories, nextOrder, onClose }: { row: Material | null; categories: string[]; nextOrder: number; onClose: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const f = useForm<Vals>(row ? {
    name: row.name, slug: row.slug, source_name: row.source_name ?? '', category: row.category, description: row.description ?? '', required_quantity: String(row.required_quantity),
    unit_price: row.unit_price === null ? '' : String(row.unit_price), currency: row.currency, supplier: row.supplier ?? '', product_url: row.product_url ?? '',
    purchase_status: row.purchase_status, notes: row.notes ?? '', is_programmer_extra: row.is_programmer_extra, sort_order: String(row.sort_order),
  } : { name: '', slug: '', source_name: '', category: categories[0] ?? '', description: '', required_quantity: '1', unit_price: '', currency: 'TRY', supplier: '', product_url: '', purchase_status: 'not_purchased', notes: '', is_programmer_extra: false, sort_order: String(nextOrder) }, {
    name: [v.required(), v.min(2), v.max(200)], category: [v.required(), v.max(80)], slug: [v.required(), v.pattern(/^[a-z0-9-]{2,60}$/, 'Küçük harf, rakam ve tire (2–60).')],
    required_quantity: [v.required(), v.number({ integer: true, min: 0, max: 100000 })], unit_price: [v.number({ min: 0 })],
    currency: [v.pattern(/^[A-Z]{3}$/, 'Üç harfli kod (TRY, USD, EUR).')], product_url: [v.url()], notes: [v.max(4000)],
  });
  const save = async () => {
    if (!f.check()) return;
    const x = f.values;
    const p = { name: x.name.trim(), slug: x.slug, source_name: nn(x.source_name), category: x.category.trim(), description: nn(x.description), required_quantity: Number(x.required_quantity),
      unit_price: x.unit_price === '' ? null : Number(x.unit_price.replace(',', '.')), currency: x.currency, supplier: nn(x.supplier), product_url: nn(x.product_url),
      purchase_status: x.purchase_status, notes: nn(x.notes), is_programmer_extra: x.is_programmer_extra, sort_order: Number(x.sort_order) || 0 };
    setBusy(true);
    try { if (row) await matSvc.update(row.id, p, row.updated_at); else await matSvc.insert(p); toast.success('Malzeme kaydedildi.'); onClose(); }
    catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} busy={busy} size="lg" title={row ? 'Malzemeyi düzenle' : 'Yeni malzeme'}
      footer={<><button className="btn-ghost" onClick={onClose} disabled={busy}>Vazgeç</button><button className="btn-primary" disabled={busy || !f.dirty} onClick={() => void save()}>{busy ? 'Kaydediliyor…' : 'Kaydet'}</button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput label="Malzeme adı" required value={f.values.name} error={f.errors.name} onChange={(e) => { f.set('name', e.target.value); if (!row) f.set('slug', slugify(e.target.value)); }} />
        <TextInput label="Kod" required value={f.values.slug} error={f.errors.slug} disabled={!!row} onChange={(e) => f.set('slug', e.target.value)} hint="CSV içe aktarmada eşleştirme anahtarı" />
        <div>
          <TextInput label="Kategori" required list="mat-cats" value={f.values.category} error={f.errors.category} onChange={(e) => f.set('category', e.target.value)} />
          <datalist id="mat-cats">{categories.map((c) => <option key={c} value={c} />)}</datalist>
        </div>
        <TextInput label="Gerekli adet" type="number" min={0} required value={f.values.required_quantity} error={f.errors.required_quantity} onChange={(e) => f.set('required_quantity', e.target.value)} />
        <div className="grid grid-cols-[1fr_96px] gap-2">
          <TextInput label="Birim fiyat (yerel teklif)" inputMode="decimal" value={f.values.unit_price} error={f.errors.unit_price} onChange={(e) => f.set('unit_price', e.target.value)} hint="Boş bırakılırsa referans fiyat kullanılır." />
          <Select label="Para birimi" value={f.values.currency} onChange={(e) => f.set('currency', e.target.value)} options={['TRY', 'USD', 'EUR'].map((c) => ({ value: c, label: c }))} />
        </div>
        <Select label="Satın alma durumu" value={f.values.purchase_status} onChange={(e) => f.set('purchase_status', e.target.value as PurchaseStatus)} options={options(purchaseLabels)} hint="Satın alınan adet, satın alma kayıtlarından otomatik hesaplanır." />
        <TextInput label="Tedarikçi" value={f.values.supplier} onChange={(e) => f.set('supplier', e.target.value)} />
        <TextInput label="Ürün bağlantısı" type="url" value={f.values.product_url} error={f.errors.product_url} onChange={(e) => f.set('product_url', e.target.value)} />
        <TextInput label="Referans listedeki tanım" value={f.values.source_name} onChange={(e) => f.set('source_name', e.target.value)} />
        <TextInput label="Sıra" type="number" value={f.values.sort_order} onChange={(e) => f.set('sort_order', e.target.value)} />
        <TextArea className="sm:col-span-2" label="Notlar" value={f.values.notes} error={f.errors.notes} onChange={(e) => f.set('notes', e.target.value)} />
        <div className="sm:col-span-2"><Checkbox label="EEPROM programlayıcı ek malzemesi" hint="Ana maliyet toplamlarına dâhil edilmez." checked={f.values.is_programmer_extra} onChange={(b) => f.set('is_programmer_extra', b)} /></div>
        {row && row.ref_unit_price_min !== null && (
          <p className="text-[12.5px] text-ink-3 sm:col-span-2">Referans değerler (değiştirilemez): {row.ref_quantity} adet × {fmtMoneyRange(row.ref_unit_price_min, row.ref_unit_price_max ?? row.ref_unit_price_min, row.ref_currency)} · liste toplamı {fmtMoneyRange(row.ref_stated_total_min ?? 0, row.ref_stated_total_max ?? 0, row.ref_currency)}</p>
        )}
      </div>
    </Modal>
  );
}

/** CSV içe aktarma: önizleme → doğrulama → yinelenen tespiti → onay */
function CsvImport({ existing, onClose }: { existing: Material[]; onClose: () => void }) {
  const toast = useToast();
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [readErr, setReadErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const read = async (file: File) => {
    setReadErr(null); setName(file.name);
    if (file.size > 2 * 1024 * 1024) { setReadErr('CSV dosyası en fazla 2 MB olabilir.'); return; }
    try { setPreview(previewMaterialsCsv(await file.text(), existing)); } catch (e) { setReadErr(errorMessage(e)); }
  };
  const counts = preview ? { create: preview.rows.filter((r) => r.action === 'create').length, update: preview.rows.filter((r) => r.action === 'update').length, same: preview.rows.filter((r) => r.action === 'unchanged').length, error: preview.rows.filter((r) => r.action === 'error').length } : null;
  const apply = async () => {
    if (!preview) return;
    setBusy(true);
    let done = 0; const errs: string[] = [];
    try {
      const creates = preview.rows.filter((r) => r.action === 'create').map((r) => ({ ...r.values, name: r.values.name!, category: r.values.category!, slug: r.slug, required_quantity: r.values.required_quantity ?? 0 }));
      if (creates.length) { await matSvc.insertMany(creates); done += creates.length; }
      for (const r of preview.rows.filter((x) => x.action === 'update')) {
        const ex = existing.find((m) => m.id === r.existingId)!;
        const patch = Object.fromEntries(Object.keys(r.changes).map((k) => [k, r.values[k as keyof typeof r.values]]));
        try { await matSvc.update(ex.id, patch, ex.updated_at); done++; } catch (e) { errs.push(`Satır ${r.line} (${r.slug}): ${errorMessage(e)}`); }
      }
      toast.success(`${done} kalem içe aktarıldı.`);
      errs.forEach((e) => toast.error(e));
      if (!errs.length) onClose();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); invalidate('materials'); }
  };
  return (
    <Modal open onClose={onClose} busy={busy} size="xl" title="CSV’den içe aktar"
      footer={<><button className="btn-ghost" onClick={onClose} disabled={busy}>Vazgeç</button>
        <button className="btn-primary" disabled={busy || !counts || counts.create + counts.update === 0} onClick={() => void apply()}>{busy ? 'Aktarılıyor…' : counts ? `${counts.create} yeni, ${counts.update} güncelleme uygula` : 'Uygula'}</button></>}>
      <div className="space-y-4">
        <Callout>Beklenen başlıklar: <span className="mono text-[12.5px]">Kod; Malzeme Adı; Kategori; Gerekli Adet; Birim Fiyat; Para Birimi; Tedarikçi; Ürün Bağlantısı; Satın Alma Durumu; Notlar</span>. Kod eşleşen satırlar güncellenir, yeni kodlar eklenir; hiçbir kalem silinmez. Hatalı satırlar atlanır. Önce “CSV dışa aktar” ile örnek dosya alabilirsiniz.</Callout>
        <div className="flex flex-wrap items-center gap-3">
          <button className="btn-outline" onClick={() => input.current?.click()} disabled={busy}><Upload size={16} aria-hidden /> CSV dosyası seç</button>
          {name && <span className="text-[13px] text-ink-3">{name}</span>}
          <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" tabIndex={-1} aria-hidden onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) void read(f); }} />
        </div>
        {readErr && <div role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[13.5px] text-red-800">{readErr}</div>}
        {preview && (
          <>
            {preview.missingRequired.length > 0 && <div role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[13.5px] text-red-800">Eksik zorunlu sütun: {preview.missingRequired.join(', ')}</div>}
            {preview.unknownHeaders.length > 0 && <p className="text-[13px] text-amber-800">Tanınmayan sütunlar yok sayılacak: {preview.unknownHeaders.join(', ')}</p>}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat label="Yeni" value={counts!.create} /><Stat label="Güncellenecek" value={counts!.update} /><Stat label="Değişmeyen" value={counts!.same} /><Stat label="Hatalı" value={counts!.error} />
            </div>
            <div className="max-h-[45vh] overflow-auto rounded-[10px] border border-brand-line">
              <table className="w-full min-w-[720px] text-[13px]">
                <thead className="sticky top-0 bg-brand-mist text-left text-[11.5px] uppercase text-brand"><tr><th className="px-3 py-2">Satır</th><th className="px-3">Kod</th><th className="px-3">Ad</th><th className="px-3">İşlem</th><th className="px-3">Ayrıntı</th></tr></thead>
                <tbody>{preview.rows.map((r) => (
                  <tr key={r.line} className="border-t border-brand-line/50 align-top">
                    <td className="mono px-3 py-1.5">{r.line}</td><td className="mono px-3">{r.slug}</td><td className="px-3">{r.name}</td>
                    <td className="px-3">{r.action === 'create' ? <Badge tone="success">Yeni</Badge> : r.action === 'update' ? <Badge tone="info">Güncelle</Badge> : r.action === 'error' ? <Badge tone="danger">Hata</Badge> : <Badge tone="muted">Aynı</Badge>}</td>
                    <td className="px-3 text-[12.5px]">{r.errors.length ? <span className="text-red-700">{r.errors.join(' · ')}</span>
                      : Object.entries(r.changes).map(([k, [a, b]]) => <div key={k}><span className="text-ink-3">{k}:</span> {String(a ?? '—')} → <b>{String(b ?? '—')}</b></div>)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

/** Önceki sürümde ziyaretçi tarayıcısında saklanan düzenlemelerin isteğe bağlı aktarımı */
function LegacyImport({ existing, onClose }: { existing: Material[]; onClose: () => void }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [p] = useState<LegacyPreview>(() => previewLegacy(readLegacyStore(), existing));
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const apply = async () => {
    setBusy(true);
    const errs: string[] = [];
    for (const c of p.changes) {
      const m = existing.find((x) => x.id === c.materialId)!;
      const patch = Object.fromEntries(Object.entries(c.changes).map(([k, [, b]]) => [k, b]));
      try { await matSvc.update(m.id, patch, m.updated_at); } catch (e) { errs.push(`${c.name}: ${errorMessage(e)}`); }
    }
    setBusy(false);
    if (errs.length) errs.forEach((e) => toast.error(e)); else { toast.success(`${p.changes.length} kalem güncellendi.`); setDone(true); }
  };
  const clearLocal = async () => {
    if (!(await confirm({ title: 'Tarayıcıdaki kopya silinsin mi?', tone: 'danger', confirmLabel: 'Yerel kopyayı sil', message: 'Bu yalnızca bu tarayıcıda saklanan eski düzenlemeleri siler. Veritabanındaki kayıtlar etkilenmez.' }))) return;
    try { localStorage.removeItem(LEGACY_STORAGE_KEY); toast.success('Yerel kopya silindi.'); onClose(); } catch { toast.error('Tarayıcı depolamasına erişilemedi.'); }
  };
  return (
    <Modal open onClose={onClose} busy={busy} size="lg" title="Tarayıcı verilerini içe aktar"
      footer={<>{p.found && <button className="btn-ghost mr-auto text-red-700" onClick={() => void clearLocal()} disabled={busy}>Yerel kopyayı sil…</button>}
        <button className="btn-ghost" onClick={onClose} disabled={busy}>Kapat</button>
        {!done && <button className="btn-primary" disabled={busy || p.changes.length === 0} onClick={() => void apply()}>{busy ? 'Aktarılıyor…' : `${p.changes.length} değişikliği uygula`}</button>}</>}>
      {!p.found ? <p className="prose-body">Bu tarayıcıda önceki sürüme ait yerel malzeme düzenlemesi bulunamadı.</p> : (
        <div className="space-y-4">
          <Callout>Önceki sürümde malzeme sayfasındaki düzenlemeler yalnızca bu tarayıcıda saklanıyordu. Aşağıdaki değişiklikler <b>onayınızla</b> ortak veritabanına aktarılır. Eski sürümde fiyatlar USD girildiği için para birimi USD olarak aktarılır. Yerel kopya siz silmedikçe korunur.</Callout>
          {p.changes.length === 0 ? <p className="flex items-center gap-2 text-[14px] text-emerald-700"><CheckCircle2 size={16} aria-hidden /> Yerel veriler veritabanıyla aynı; aktarılacak değişiklik yok.</p> : (
            <ul className="divide-y divide-brand-line/60 rounded-[10px] border border-brand-line text-[13.5px]">
              {p.changes.map((c) => <li key={c.slug} className="px-3 py-2"><b>{c.name}</b>{Object.entries(c.changes).map(([k, [a, b]]) => <div key={k} className="text-[12.5px]"><span className="text-ink-3">{k === 'required_quantity' ? 'Adet' : k === 'unit_price' ? 'Birim fiyat' : k === 'currency' ? 'Para birimi' : 'Durum'}:</span> {String(a ?? '—')} → <b>{k === 'purchase_status' ? purchaseLabels[b as PurchaseStatus] : String(b)}</b></div>)}</li>)}
            </ul>
          )}
          {p.unmatched.length > 0 && <p className="text-[13px] text-amber-800">Eşleşmeyen kodlar: {p.unmatched.join(', ')}</p>}
          {(p.shipping > 0 || p.rate) && <p className="text-[13px] text-ink-3">Yerel kopyada kargo ({p.shipping} USD) ve kur ({p.rate ?? '—'}) bilgisi de var; bunlar kişisel tahmin olduğu için aktarılmaz. Kur kaydetmek için <Link to="/admin/settings">Ayarlar</Link> sayfasını kullanın.</p>}
        </div>
      )}
    </Modal>
  );
}

export default function MaterialsAdmin() {
  const { canEdit } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const mats = useMaterials(); const purch = usePurchases(); const settings = useSettings();
  const [q, setQ] = useState('');
  const [cat, setCat] = useState('');
  const [st, setSt] = useState('');
  const [editing, setEditing] = useState<Material | null | 'new'>(null);
  const [modal, setModal] = useState<'csv' | 'legacy' | null>(null);
  const M = mats.data ?? [];
  const categories = useMemo(() => [...new Set(M.map((m) => m.category))], [M]);
  const legacyFound = useMemo(() => { const s = readLegacyStore(); return !!s && Object.keys({ ...(s.items ?? {}), ...(s.extra ?? {}) }).length > 0; }, []);
  const sum = summarize(M.filter((m) => !m.is_programmer_extra), purch.data ?? []);
  const combined = combinedTRY(sum.estimated, settings.data?.usd_try_rate ?? null);
  const list = M.filter((m) => (!q.trim() || norm(`${m.name} ${m.slug} ${m.source_name ?? ''} ${m.supplier ?? ''}`).includes(norm(q.trim()))) && (!cat || m.category === cat) && (!st || m.purchase_status === st));
  const purchCount = (id: string) => (purch.data ?? []).filter((p) => p.material_id === id).length;

  const exportCsv = () => {
    const blob = new Blob(['﻿' + materialsToCsv(M)], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'malzemeler-yonetim.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  const remove = async (m: Material) => {
    if (purchCount(m.id)) { toast.error('Bu malzemeye ait satın alma kayıtları olduğu için silinemez. Mali kayıtların korunması için önce satın almaları silin.'); return; }
    if (!(await confirm({ title: 'Malzeme silinsin mi?', tone: 'danger', confirmLabel: 'Sil', message: <>“<b>{m.name}</b>” listeden kalıcı olarak kaldırılacak.</> }))) return;
    try { await matSvc.remove(m.id); toast.success('Malzeme silindi.'); } catch (e) { toast.error(errorMessage(e)); }
  };
  const setStatus = async (m: Material, s: PurchaseStatus) => {
    try { await matSvc.update(m.id, { purchase_status: s }, m.updated_at); toast.success('Durum güncellendi.'); } catch (e) { toast.error(errorMessage(e)); }
  };

  return (
    <AdminPage title="Malzemeler" description="Ortak malzeme listesi. Değişiklikler anında genel Malzeme ve Maliyet sayfasına yansır. Satın alınan adetler satın alma kayıtlarından hesaplanır."
      actions={<>
        <button className="btn-outline" onClick={exportCsv} disabled={!M.length}><Download size={16} aria-hidden /> CSV dışa aktar</button>
        {canEdit && <button className="btn-outline" onClick={() => setModal('csv')}><Upload size={16} aria-hidden /> CSV içe aktar</button>}
        {canEdit && <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} aria-hidden /> Yeni malzeme</button>}
      </>}>
      <ReadOnlyNotice />
      {canEdit && legacyFound && (
        <div className="mb-4 flex flex-col gap-2 rounded-[10px] border border-amber-300 bg-amber-50/70 p-3 text-[13.5px] sm:flex-row sm:items-center">
          <HardDriveDownload size={18} className="text-amber-700" aria-hidden />
          <span className="flex-1">Bu tarayıcıda, sitenin önceki sürümünde yapılmış yerel malzeme düzenlemeleri bulundu. İsterseniz önizleyip ortak listeye aktarabilirsiniz.</span>
          <button className="btn-outline py-1.5" onClick={() => setModal('legacy')}>Önizle ve aktar</button>
        </div>
      )}
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Kalem" value={sum.itemCount} hint={`${sum.quotedItems} kalemde yerel teklif`} />
        <Stat label="Adet (alınan/gerekli)" value={`${sum.purchasedQty}/${sum.requiredQty}`} hint={`Kalan ${sum.remainingQty} adet`} />
        <Stat label="Tahmini toplam" value={<span className="text-[16px]"><TotalsText t={sum.estimated} /></span>} hint={combined ? `≈ ${fmtMoneyRange(combined.min, combined.max, 'TRY', 0)}` : 'Kur girilmeden para birimleri ayrı tutulur'} />
        <Stat label="Kalan tahmini" value={<span className="text-[16px]"><TotalsText t={sum.remaining} /></span>} />
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={q} onChange={setQ} placeholder="Ad, kod veya tedarikçi ara" />
        <select className="input w-auto" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Kategori"><option value="">Tüm kategoriler</option>{categories.map((c) => <option key={c} value={c}>{c}</option>)}</select>
        <select className="input w-auto" value={st} onChange={(e) => setSt(e.target.value)} aria-label="Durum"><option value="">Tüm durumlar</option>{options(purchaseLabels).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
      </div>
      {mats.error && <ErrorNotice error={mats.error} onRetry={() => void mats.refetch()} />}
      {!mats.data ? <SkeletonRows rows={8} /> : (
        <Table minWidth={1040}>
          <thead><tr><Th>Malzeme</Th><Th>Kategori</Th><Th className="text-right">Gerekli</Th><Th className="text-right">Alınan</Th><Th className="text-right">Birim fiyat</Th><Th className="text-right">Tahmini toplam</Th><Th>Durum</Th><Th /></tr></thead>
          <tbody>{list.map((m) => {
            const p = unitPrice(m);
            return (
              <tr key={m.id} className="hover:bg-brand-mist/40">
                <Td><b>{m.name}</b><div className="mono text-[11.5px] text-ink-3">{m.slug}{m.is_programmer_extra && ' · programlayıcı'}</div>{m.supplier && <div className="text-[12px] text-ink-3">{m.supplier}</div>}</Td>
                <Td className="text-[12.5px]">{m.category}</Td>
                <Td className="mono text-right">{m.required_quantity}</Td>
                <Td className={`mono text-right ${m.purchased_quantity >= m.required_quantity && m.required_quantity > 0 ? 'text-emerald-700' : ''}`}>{m.purchased_quantity}</Td>
                <Td className="mono text-right">{p.source === 'none' ? '—' : fmtMoneyRange(p.range.min, p.range.max, p.currency)}<div className="font-sans text-[11px] text-ink-3">{p.source === 'quote' ? 'teklif' : p.source === 'reference' ? 'referans' : ''}</div></Td>
                <Td className="mono text-right">{p.source === 'none' ? '—' : fmtMoneyRange(p.range.min * m.required_quantity, p.range.max * m.required_quantity, p.currency)}</Td>
                <Td>{canEdit ? (
                  <select aria-label={`${m.name} satın alma durumu`} value={m.purchase_status} onChange={(e) => void setStatus(m, e.target.value as PurchaseStatus)} className="input w-auto py-1 text-[12.5px]">
                    {options(purchaseLabels).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>) : <Badge tone={purchaseTone[m.purchase_status]}>{purchaseLabels[m.purchase_status]}</Badge>}</Td>
                <Td className="whitespace-nowrap text-right">
                  <Link to={`/admin/purchases?malzeme=${m.id}`} className="btn-ghost px-2 py-1" title="Satın almalar" aria-label={`${m.name} satın almaları`}><ShoppingCart size={15} /></Link>
                  {canEdit && <><button className="btn-ghost px-2 py-1" onClick={() => setEditing(m)} aria-label={`${m.name} düzenle`}><Pencil size={15} /></button>
                    <button className="btn-ghost px-2 py-1 text-red-700 hover:bg-red-50" onClick={() => void remove(m)} aria-label={`${m.name} sil`}><Trash2 size={15} /></button></>}
                </Td>
              </tr>
            );
          })}</tbody>
        </Table>
      )}
      {sum.unpricedItems > 0 && <p className="mt-3 flex items-center gap-1.5 text-[12.5px] text-amber-800"><AlertTriangle size={14} aria-hidden /> {sum.unpricedItems} kalemde hiç fiyat bilgisi yok; tahmini toplama dâhil edilmedi.</p>}
      {(purch.data ?? []).length > 0 && <p className="mt-1 text-[12.5px] text-ink-3">Kayıtlı harcama: {Object.entries(sum.purchased).map(([c, r]) => fmtMoney(r.min, c)).join(' + ') || '—'}</p>}
      {editing && <Editor row={editing === 'new' ? null : editing} categories={categories} nextOrder={(M.at(-1)?.sort_order ?? 0) + 10} onClose={() => setEditing(null)} />}
      {modal === 'csv' && <CsvImport existing={M} onClose={() => setModal(null)} />}
      {modal === 'legacy' && <LegacyImport existing={M} onClose={() => setModal(null)} />}
    </AdminPage>
  );
}
