import { useState } from 'react';
import { Plus, Pencil, Trash2, Globe, Lock, ImagePlus } from 'lucide-react';
import { AdminPage, ReadOnlyNotice, Table, Th, Td } from '../ui';
import UploadPanel from '../UploadPanel';
import { usePhases, useComponents, useProgressUpdates, useMediaList } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { Modal, useConfirm, useToast, SkeletonRows, ErrorNotice, EmptyState } from '../../components/feedback';
import { Select, TextArea, TextInput, Checkbox, useForm, v, nn } from '../../components/form';
import { Badge, Callout } from '../../components/ui';
import { MediaGallery } from '../../components/MediaGallery';
import { progressUpdates, type ProgressUpdate } from '../../services/entities';
import { invalidateMedia } from '../../services/media';
import { workStatusLabels, workTone, options, type WorkStatus } from '../../lib/labels';
import { PUBLIC_BUCKET } from '../../lib/files';
import { fmtDate, todayISO } from '../../lib/format';
import { errorMessage } from '../../lib/errors';

type Vals = { title: string; description: string; phase_id: string; component_id: string; status: WorkStatus; progress_value: string; update_date: string; is_published: boolean };

function Editor({ row, onClose }: { row: ProgressUpdate | null; onClose: () => void }) {
  const toast = useToast();
  const ph = usePhases(); const comps = useComponents(); const media = useMediaList();
  const [current, setCurrent] = useState(row);
  const [busy, setBusy] = useState(false);
  const f = useForm<Vals>(row ? {
    title: row.title, description: row.description ?? '', phase_id: row.phase_id ?? '', component_id: row.component_id ?? '', status: row.status,
    progress_value: row.progress_value === null ? '' : String(row.progress_value), update_date: row.update_date, is_published: row.is_published,
  } : { title: '', description: '', phase_id: '', component_id: '', status: 'completed', progress_value: '', update_date: todayISO(), is_published: true }, {
    title: [v.required(), v.min(3), v.max(200)], update_date: [v.required(), (x) => (String(x) > todayISO() ? 'Gelecek tarihli kayıt girilemez; planlanan işler için görev ekleyin.' : null)],
    progress_value: [v.number({ min: 0, max: 100 })], description: [v.max(8000)],
  });
  const photos = (media.data ?? []).filter((m) => current && m.progress_update_id === current.id);
  const save = async () => {
    if (!f.check()) return;
    const x = f.values;
    const p = { title: x.title.trim(), description: nn(x.description), phase_id: x.phase_id || null, component_id: x.component_id || null, status: x.status,
      progress_value: x.progress_value === '' ? null : Number(x.progress_value), update_date: x.update_date, is_published: x.is_published };
    setBusy(true);
    try {
      const r = current ? await progressUpdates.update(current.id, p, current.updated_at) : await progressUpdates.insert(p);
      setCurrent(r);
      f.reset({ ...x });
      toast.success(current ? 'Kayıt güncellendi.' : 'Kayıt eklendi. Şimdi fotoğraf ekleyebilirsiniz.');
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} busy={busy} size="lg" title={current ? 'İlerleme kaydını düzenle' : 'Yeni ilerleme kaydı'}
      footer={<><button className="btn-ghost" onClick={onClose} disabled={busy}>Kapat</button><button className="btn-primary" disabled={busy || (!f.dirty && !!current)} onClick={() => void save()}>{busy ? 'Kaydediliyor…' : 'Kaydet'}</button></>}>
      <Callout>İlerleme kayıtları <b>gerçekleşmiş</b> çalışmaları belgeler (ör. “Saat modülü breadboard’a kuruldu”). Yüzdelere etki etmez; ilerleme görevlerden hesaplanır.</Callout>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <TextInput className="sm:col-span-2" label="Başlık" required value={f.values.title} error={f.errors.title} onChange={(e) => f.set('title', e.target.value)} />
        <TextArea className="sm:col-span-2" label="Açıklama" rows={4} value={f.values.description} error={f.errors.description} onChange={(e) => f.set('description', e.target.value)} />
        <TextInput label="Tarih" type="date" max={todayISO()} required value={f.values.update_date} error={f.errors.update_date} onChange={(e) => f.set('update_date', e.target.value)} />
        <Select label="Durum" value={f.values.status} onChange={(e) => f.set('status', e.target.value as WorkStatus)} options={options(workStatusLabels)} />
        <Select label="İlgili aşama" value={f.values.phase_id} onChange={(e) => f.set('phase_id', e.target.value)} placeholder="— Yok —" options={(ph.data ?? []).map((p) => ({ value: p.id, label: p.title }))} />
        <Select label="İlgili bileşen" value={f.values.component_id} onChange={(e) => f.set('component_id', e.target.value)} placeholder="— Yok —" options={(comps.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
        <TextInput label="O günkü kayıtlı ilerleme (%)" inputMode="decimal" value={f.values.progress_value} error={f.errors.progress_value} onChange={(e) => f.set('progress_value', e.target.value)} hint="İsteğe bağlı, yalnızca bilgi amaçlı." />
        <div className="self-end"><Checkbox label="Genel sitede yayımla" checked={f.values.is_published} onChange={(b) => f.set('is_published', b)} /></div>
      </div>
      <div className="mt-6 border-t border-brand-line pt-5">
        <h3 className="flex items-center gap-2 text-[15px] font-semibold"><ImagePlus size={16} className="text-brand" aria-hidden /> Fotoğraflar ve kanıtlar</h3>
        {!current ? <p className="mt-2 text-[13.5px] text-ink-3">Fotoğraf eklemek için önce kaydı kaydedin.</p> : (
          <div className="mt-3 space-y-4">
            <MediaGallery items={photos} columns={4} />
            <UploadPanel defaults={{ category: 'breadboard_photo', bucket: PUBLIC_BUCKET, progress_update_id: current.id, component_id: current.component_id }} components={comps.data ?? []} onUploaded={() => invalidateMedia()} />
            <p className="text-[12px] text-ink-3">Genel zaman çizelgesinde yalnızca herkese açık depodaki fotoğraflar gösterilir.</p>
          </div>
        )}
      </div>
    </Modal>
  );
}

export default function ProgressAdmin() {
  const { canEdit } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const ups = useProgressUpdates(); const ph = usePhases(); const media = useMediaList();
  const [editing, setEditing] = useState<ProgressUpdate | null | 'new'>(null);
  const remove = async (u: ProgressUpdate) => {
    if (!(await confirm({ title: 'Kayıt silinsin mi?', tone: 'danger', confirmLabel: 'Sil', message: <>“<b>{u.title}</b>” silinecek. Bağlı fotoğraflar silinmez; Medya sayfasında kalır.</> }))) return;
    try { await progressUpdates.remove(u.id); invalidateMedia(); toast.success('Kayıt silindi.'); } catch (e) { toast.error(errorMessage(e)); }
  };
  return (
    <AdminPage title="İlerleme Kayıtları" description="Kilometre taşları ve gerçekleşen çalışmalar. Yayımlanan kayıtlar İlerleme Durumu sayfasındaki zaman çizelgesinde tarih sırasıyla gösterilir."
      actions={canEdit && <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} aria-hidden /> Yeni kayıt</button>}>
      <ReadOnlyNotice />
      {ups.error && <ErrorNotice error={ups.error} onRetry={() => void ups.refetch()} />}
      {!ups.data ? <SkeletonRows /> : ups.data.length === 0 ? (
        <EmptyState title="Henüz ilerleme kaydı yok" action={canEdit ? <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} aria-hidden /> İlk kaydı ekle</button> : undefined}>Tamamlanan bir çalışmayı fotoğraflarıyla birlikte kaydedin.</EmptyState>
      ) : (
        <Table minWidth={760}>
          <thead><tr><Th>Tarih</Th><Th>Kayıt</Th><Th>Aşama</Th><Th>Durum</Th><Th>Fotoğraf</Th><Th>Yayın</Th><Th /></tr></thead>
          <tbody>{ups.data.map((u) => (
            <tr key={u.id} className="hover:bg-brand-mist/40">
              <Td className="whitespace-nowrap">{fmtDate(u.update_date)}</Td>
              <Td><button className="text-left font-semibold hover:text-brand" onClick={() => setEditing(u)}>{u.title}</button>{u.description && <div className="line-clamp-1 text-[12px] text-ink-3">{u.description}</div>}</Td>
              <Td className="text-[12.5px]">{ph.data?.find((p) => p.id === u.phase_id)?.title ?? '—'}</Td>
              <Td><Badge tone={workTone[u.status]}>{workStatusLabels[u.status]}</Badge></Td>
              <Td className="mono">{(media.data ?? []).filter((m) => m.progress_update_id === u.id).length}</Td>
              <Td>{u.is_published ? <Badge tone="success" dot={false}><Globe size={11} aria-hidden /> Yayında</Badge> : <Badge tone="muted" dot={false}><Lock size={11} aria-hidden /> Taslak</Badge>}</Td>
              <Td className="whitespace-nowrap text-right">{canEdit && <>
                <button className="btn-ghost px-2 py-1" onClick={() => setEditing(u)} aria-label={`${u.title} düzenle`}><Pencil size={15} /></button>
                <button className="btn-ghost px-2 py-1 text-red-700 hover:bg-red-50" onClick={() => void remove(u)} aria-label={`${u.title} sil`}><Trash2 size={15} /></button></>}</Td>
            </tr>
          ))}</tbody>
        </Table>
      )}
      {editing && <Editor row={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </AdminPage>
  );
}
