import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, Pencil, Trash2, Receipt } from 'lucide-react';
import { AdminPage, ReadOnlyNotice, Table, Th, Td } from '../ui';
import { useMaterials, usePurchases, useProfiles, useMediaList } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { Modal, useConfirm, useToast, SkeletonRows, ErrorNotice, EmptyState } from '../../components/feedback';
import { Select, TextArea, TextInput, useForm, v, nn } from '../../components/form';
import { Stat } from '../../components/ui';
import { DownloadButton } from '../../components/MediaGallery';
import { purchases as purchSvc, type Purchase } from '../../services/entities';
import { uploadMedia, deleteMedia, invalidateMedia } from '../../services/media';
import { summarize } from '../../lib/costs';
import { PRIVATE_BUCKET, checkFile } from '../../lib/files';
import { fmtDate, fmtMoney, todayISO } from '../../lib/format';
import { errorMessage } from '../../lib/errors';
import { invalidate } from '../../lib/query';

type Vals = { material_id: string; quantity: string; unit_price: string; currency: string; purchase_date: string; supplier: string; purchased_by: string; notes: string };

function Editor({ row, defaultMaterial, onClose }: { row: Purchase | null; defaultMaterial: string; onClose: () => void }) {
  const toast = useToast();
  const mats = useMaterials(); const people = useProfiles(); const media = useMediaList();
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const f = useForm<Vals>(row ? {
    material_id: row.material_id, quantity: String(row.quantity), unit_price: row.unit_price === null ? '' : String(row.unit_price), currency: row.currency,
    purchase_date: row.purchase_date, supplier: row.supplier ?? '', purchased_by: row.purchased_by ?? '', notes: row.notes ?? '',
  } : { material_id: defaultMaterial, quantity: '1', unit_price: '', currency: 'TRY', purchase_date: todayISO(), supplier: '', purchased_by: user?.id ?? '', notes: '' }, {
    material_id: [v.required('Malzeme seçin.')], quantity: [v.required(), v.number({ integer: true, min: 1, max: 100000 })], unit_price: [v.number({ min: 0 })],
    purchase_date: [v.required(), (x) => (String(x) > todayISO() ? 'Satın alma tarihi gelecekte olamaz.' : null)], notes: [v.max(2000)],
  });
  const mat = mats.data?.find((m) => m.id === f.values.material_id);
  const currentReceipt = media.data?.find((m) => m.id === row?.receipt_file_id);
  const save = async () => {
    if (!f.check()) return;
    if (receipt) { const c = checkFile(receipt, PRIVATE_BUCKET); if (!c.ok) { toast.error(c.error!); return; } }
    const x = f.values;
    setBusy(true);
    let uploaded: Awaited<ReturnType<typeof uploadMedia>> | null = null;
    try {
      if (receipt) uploaded = await uploadMedia(receipt, { bucket: PRIVATE_BUCKET, category: 'receipt', title: `Makbuz · ${mat?.name ?? ''} · ${x.purchase_date}` }, setProgress);
      const p = { material_id: x.material_id, quantity: Number(x.quantity), unit_price: x.unit_price === '' ? null : Number(x.unit_price.replace(',', '.')), currency: x.currency,
        purchase_date: x.purchase_date, supplier: nn(x.supplier), purchased_by: x.purchased_by || null, notes: nn(x.notes), ...(uploaded ? { receipt_file_id: uploaded.id } : {}) };
      if (row) await purchSvc.update(row.id, p, row.updated_at); else await purchSvc.insert(p);
      if (uploaded && currentReceipt) await deleteMedia(currentReceipt).catch(() => undefined);
      invalidateMedia(); invalidate('materials');
      toast.success(row ? 'Satın alma güncellendi.' : 'Satın alma kaydedildi; malzemenin satın alınan adedi güncellendi.');
      onClose();
    } catch (e) {
      if (uploaded) await deleteMedia(uploaded).catch(() => undefined);
      toast.error(errorMessage(e));
    } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} busy={busy} title={row ? 'Satın almayı düzenle' : 'Satın alma kaydet'}
      footer={<><button className="btn-ghost" onClick={onClose} disabled={busy}>Vazgeç</button><button className="btn-primary" disabled={busy || (!f.dirty && !receipt)} onClick={() => void save()}>{busy ? (progress && progress < 100 ? `Makbuz yükleniyor %${progress}` : 'Kaydediliyor…') : 'Kaydet'}</button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Select className="sm:col-span-2" label="Malzeme" required value={f.values.material_id} error={f.errors.material_id} onChange={(e) => f.set('material_id', e.target.value)} placeholder="— Seçiniz —"
          options={(mats.data ?? []).map((m) => ({ value: m.id, label: `${m.name} (gerekli ${m.required_quantity}, alınan ${m.purchased_quantity})` }))} />
        <TextInput label="Adet" type="number" min={1} required value={f.values.quantity} error={f.errors.quantity} onChange={(e) => f.set('quantity', e.target.value)} />
        <TextInput label="Satın alma tarihi" type="date" max={todayISO()} required value={f.values.purchase_date} error={f.errors.purchase_date} onChange={(e) => f.set('purchase_date', e.target.value)} />
        <div className="grid grid-cols-[1fr_96px] gap-2">
          <TextInput label="Birim fiyat" inputMode="decimal" value={f.values.unit_price} error={f.errors.unit_price} onChange={(e) => f.set('unit_price', e.target.value)} hint="Bilinmiyorsa boş bırakın (ör. laboratuvardan temin)." />
          <Select label="Para birimi" value={f.values.currency} onChange={(e) => f.set('currency', e.target.value)} options={['TRY', 'USD', 'EUR'].map((c) => ({ value: c, label: c }))} />
        </div>
        <TextInput label="Tedarikçi" value={f.values.supplier} onChange={(e) => f.set('supplier', e.target.value)} />
        <Select label="Satın alan" value={f.values.purchased_by} onChange={(e) => f.set('purchased_by', e.target.value)} placeholder="— Belirtilmedi —" options={(people.data ?? []).map((p) => ({ value: p.id, label: p.full_name || p.email || p.id }))} />
        <div>
          <label className="mb-1 block text-[13px] font-medium text-ink-2" htmlFor="receipt">Makbuz / fatura (isteğe bağlı)</label>
          <input id="receipt" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" className="input py-1.5 text-[13px]" onChange={(e) => setReceipt(e.target.files?.[0] ?? null)} />
          <p className="mt-1 text-[12px] text-ink-3">Özel depoda saklanır; yalnızca ekip görür.{currentReceipt && ' Yeni dosya seçerseniz mevcut makbuz değiştirilir.'}</p>
        </div>
        <TextArea className="sm:col-span-2" label="Notlar" value={f.values.notes} error={f.errors.notes} onChange={(e) => f.set('notes', e.target.value)} />
        {f.values.unit_price && f.values.quantity && <p className="text-[13px] text-ink-2 sm:col-span-2">Tutar: <b className="mono">{fmtMoney(Number(f.values.unit_price.replace(',', '.')) * Number(f.values.quantity), f.values.currency)}</b></p>}
      </div>
    </Modal>
  );
}

export default function PurchasesAdmin() {
  const { canEdit } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const [params, setParams] = useSearchParams();
  const matFilter = params.get('malzeme') ?? '';
  const purch = usePurchases(); const mats = useMaterials(); const media = useMediaList(); const people = useProfiles();
  const [editing, setEditing] = useState<Purchase | null | 'new'>(null);
  const list = useMemo(() => (purch.data ?? []).filter((p) => !matFilter || p.material_id === matFilter), [purch.data, matFilter]);
  const sum = summarize([], list);
  const matName = (id: string) => mats.data?.find((m) => m.id === id)?.name ?? '—';
  const remove = async (p: Purchase) => {
    if (!(await confirm({ title: 'Satın alma kaydı silinsin mi?', tone: 'danger', confirmLabel: 'Sil', message: <>{matName(p.material_id)} · {p.quantity} adet · {fmtDate(p.purchase_date)} kaydı silinecek ve malzemenin satın alınan adedi yeniden hesaplanacak. Makbuz dosyası da silinir.</> }))) return;
    try {
      await purchSvc.remove(p.id);
      const r = media.data?.find((m) => m.id === p.receipt_file_id);
      if (r) await deleteMedia(r).catch(() => undefined);
      invalidateMedia(); invalidate('materials');
      toast.success('Satın alma kaydı silindi.');
    } catch (e) { toast.error(errorMessage(e)); }
  };
  return (
    <AdminPage title="Satın Almalar" description="Her satın alma, ilgili malzemenin satın alınan adedini otomatik günceller. Toplamlar para birimine göre ayrı tutulur."
      actions={canEdit && <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} aria-hidden /> Satın alma kaydet</button>}>
      <ReadOnlyNotice />
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Stat label="Kayıt" value={list.length} />
        <Stat label="Toplam harcama" value={<span className="flex flex-col text-[17px]">{Object.entries(sum.purchased).map(([c, r]) => <span key={c}>{fmtMoney(r.min, c)}</span>)}{!Object.keys(sum.purchased).length && '—'}</span>} />
        <Stat label="Fiyatsız kayıt" value={sum.purchasesWithoutPrice} hint="Birim fiyatı girilmemiş satın almalar toplamlara katılmaz." />
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <select className="input w-auto" value={matFilter} onChange={(e) => { const p = new URLSearchParams(params); if (e.target.value) p.set('malzeme', e.target.value); else p.delete('malzeme'); setParams(p, { replace: true }); }} aria-label="Malzeme">
          <option value="">Tüm malzemeler</option>{(mats.data ?? []).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
      </div>
      {purch.error && <ErrorNotice error={purch.error} onRetry={() => void purch.refetch()} />}
      {!purch.data ? <SkeletonRows /> : list.length === 0 ? <EmptyState title="Satın alma kaydı yok">Malzemeler alındıkça adet, fiyat, tarih ve tedarikçi bilgisiyle kaydedin.</EmptyState> : (
        <Table minWidth={900}>
          <thead><tr><Th>Tarih</Th><Th>Malzeme</Th><Th className="text-right">Adet</Th><Th className="text-right">Birim fiyat</Th><Th className="text-right">Tutar</Th><Th>Tedarikçi</Th><Th>Satın alan</Th><Th>Makbuz</Th><Th /></tr></thead>
          <tbody>{list.map((p) => {
            const r = media.data?.find((m) => m.id === p.receipt_file_id);
            return (
              <tr key={p.id} className="hover:bg-brand-mist/40">
                <Td className="whitespace-nowrap">{fmtDate(p.purchase_date)}</Td>
                <Td><b>{matName(p.material_id)}</b>{p.notes && <div className="line-clamp-1 text-[12px] text-ink-3">{p.notes}</div>}</Td>
                <Td className="mono text-right">{p.quantity}</Td>
                <Td className="mono text-right">{p.unit_price === null ? '—' : fmtMoney(p.unit_price, p.currency)}</Td>
                <Td className="mono text-right">{p.unit_price === null ? '—' : fmtMoney(p.unit_price * p.quantity, p.currency)}</Td>
                <Td>{p.supplier ?? '—'}</Td>
                <Td className="text-[12.5px]">{people.data?.find((x) => x.id === p.purchased_by)?.full_name ?? '—'}</Td>
                <Td>{r ? <DownloadButton media={r} label="" className="btn-ghost px-2 py-1" /> : <Receipt size={15} className="text-ink-3/40" aria-label="makbuz yok" />}</Td>
                <Td className="whitespace-nowrap text-right">{canEdit && <>
                  <button className="btn-ghost px-2 py-1" onClick={() => setEditing(p)} aria-label="Düzenle"><Pencil size={15} /></button>
                  <button className="btn-ghost px-2 py-1 text-red-700 hover:bg-red-50" onClick={() => void remove(p)} aria-label="Sil"><Trash2 size={15} /></button></>}</Td>
              </tr>
            );
          })}</tbody>
        </Table>
      )}
      {editing && <Editor row={editing === 'new' ? null : editing} defaultMaterial={matFilter} onClose={() => setEditing(null)} />}
    </AdminPage>
  );
}
