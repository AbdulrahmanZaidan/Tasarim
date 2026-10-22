import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Pencil, Trash2, ExternalLink } from 'lucide-react';
import { AdminPage, ReadOnlyNotice, Table, Th, Td } from '../ui';
import { useComponents, useTasks, useSimulations, useMediaList } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { Modal, useConfirm, useToast, SkeletonRows, ErrorNotice } from '../../components/feedback';
import { Select, TextArea, TextInput, useForm, v, nn } from '../../components/form';
import { Badge, ProgressBar } from '../../components/ui';
import { components, type Component } from '../../services/entities';
import { componentProgress } from '../../lib/progress';
import { workStatusLabels, workTone, options, type WorkStatus } from '../../lib/labels';
import { errorMessage } from '../../lib/errors';
import { slugify } from '../../lib/materialsImport';

type Vals = { name: string; name_en: string; slug: string; description: string; architecture_notes: string; status: WorkStatus; sort_order: string };

function Editor({ row, nextOrder, onClose }: { row: Component | null; nextOrder: number; onClose: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const f = useForm<Vals>(row ? { name: row.name, name_en: row.name_en ?? '', slug: row.slug, description: row.description ?? '', architecture_notes: row.architecture_notes ?? '', status: row.status, sort_order: String(row.sort_order) }
    : { name: '', name_en: '', slug: '', description: '', architecture_notes: '', status: 'not_started', sort_order: String(nextOrder) }, {
    name: [v.required(), v.min(2), v.max(120)],
    slug: [v.required(), v.pattern(/^[a-z0-9-]{2,40}$/, 'Yalnızca küçük harf, rakam ve tire (2–40 karakter).')],
    sort_order: [v.number({ integer: true, min: 0 })],
    architecture_notes: [v.max(20000)],
  });
  const save = async () => {
    if (!f.check()) return;
    const x = f.values;
    const p = { name: x.name.trim(), name_en: nn(x.name_en), slug: x.slug, description: nn(x.description), architecture_notes: nn(x.architecture_notes), status: x.status, sort_order: Number(x.sort_order) || 0 };
    setBusy(true);
    try {
      if (row) await components.update(row.id, p, row.updated_at); else await components.insert(p);
      toast.success('Bileşen kaydedildi.'); onClose();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} busy={busy} title={row ? 'Bileşeni düzenle' : 'Yeni bileşen'}
      footer={<><button className="btn-ghost" onClick={onClose} disabled={busy}>Vazgeç</button><button className="btn-primary" disabled={busy || !f.dirty} onClick={() => void save()}>{busy ? 'Kaydediliyor…' : 'Kaydet'}</button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput label="Ad" required value={f.values.name} error={f.errors.name} onChange={(e) => { f.set('name', e.target.value); if (!row) f.set('slug', slugify(e.target.value).slice(0, 40)); }} />
        <TextInput label="İngilizce adı" value={f.values.name_en} onChange={(e) => f.set('name_en', e.target.value)} />
        <TextInput label="Kısa ad (adres)" required value={f.values.slug} error={f.errors.slug} onChange={(e) => f.set('slug', e.target.value)} hint={`/proje/bilesen/${f.values.slug || '…'}`} disabled={!!row} />
        <Select label="Durum" value={f.values.status} onChange={(e) => f.set('status', e.target.value as WorkStatus)} options={options(workStatusLabels)} hint="Yalnızca gerçekleşen çalışmaya göre değiştirin." />
        <TextArea className="sm:col-span-2" label="Açıklama" value={f.values.description} onChange={(e) => f.set('description', e.target.value)} />
        <TextArea className="sm:col-span-2" label="Mimari notları" rows={5} value={f.values.architecture_notes} error={f.errors.architecture_notes} onChange={(e) => f.set('architecture_notes', e.target.value)} hint="Ekibin tasarım kararları, bacak bağlantı notları vb. Bileşen sayfasında gösterilir." />
        <TextInput label="Sıra" type="number" min={0} value={f.values.sort_order} error={f.errors.sort_order} onChange={(e) => f.set('sort_order', e.target.value)} />
      </div>
    </Modal>
  );
}

export default function ComponentsAdmin() {
  const { canEdit } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const comps = useComponents(); const tasks = useTasks(); const sims = useSimulations(); const media = useMediaList();
  const [editing, setEditing] = useState<Component | null | 'new'>(null);
  const ptasks = (tasks.data ?? []).map((t) => ({ status: t.status, weight: t.weight, component_id: t.component_id }));
  const remove = async (c: Component) => {
    if (!(await confirm({ title: 'Bileşen silinsin mi?', tone: 'danger', confirmLabel: 'Sil', message: <>“<b>{c.name}</b>” silinecek. Bağlı görev, deney, dosya ve belgeler silinmez; bileşen bağlantıları kaldırılır.</> }))) return;
    try { await components.remove(c.id); toast.success('Bileşen silindi.'); } catch (e) { toast.error(errorMessage(e)); }
  };
  return (
    <AdminPage title="Bilgisayar Bileşenleri" description="Saat, yazmaçlar, ALU, RAM… Her bileşenin durumu, ilgili görevleri ve kanıtları bileşen sayfasında bir araya gelir. İlerleme yüzdesi bileşene bağlı görevlerden hesaplanır."
      actions={canEdit && <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} aria-hidden /> Yeni bileşen</button>}>
      <ReadOnlyNotice />
      {comps.error && <ErrorNotice error={comps.error} onRetry={() => void comps.refetch()} />}
      {!comps.data ? <SkeletonRows /> : (
        <Table minWidth={820}>
          <thead><tr><Th>#</Th><Th>Bileşen</Th><Th>Durum</Th><Th>Görev ilerlemesi</Th><Th>Deney</Th><Th>Dosya</Th><Th /></tr></thead>
          <tbody>{comps.data.map((c) => {
            const n = ptasks.filter((t) => t.component_id === c.id).length;
            return (
              <tr key={c.id} className="hover:bg-brand-mist/40">
                <Td className="mono text-ink-3">{c.sort_order}</Td>
                <Td><b>{c.name}</b><div className="text-[12px] text-ink-3">{c.name_en} · <span className="mono">{c.slug}</span></div></Td>
                <Td><Badge tone={workTone[c.status]}>{workStatusLabels[c.status]}</Badge></Td>
                <Td className="w-56">{n ? <ProgressBar value={componentProgress(c.id, ptasks)} label={`${n} görev`} /> : <span className="text-[12px] text-ink-3">Bağlı görev yok</span>}</Td>
                <Td className="mono">{(sims.data ?? []).filter((s) => s.component_id === c.id).length}</Td>
                <Td className="mono">{(media.data ?? []).filter((m) => m.component_id === c.id).length}</Td>
                <Td className="whitespace-nowrap text-right">
                  <Link to={`/proje/bilesen/${c.slug}`} className="btn-ghost px-2 py-1" aria-label="Genel sayfa"><ExternalLink size={15} /></Link>
                  {canEdit && <><button className="btn-ghost px-2 py-1" onClick={() => setEditing(c)} aria-label={`${c.name} düzenle`}><Pencil size={15} /></button>
                    <button className="btn-ghost px-2 py-1 text-red-700 hover:bg-red-50" onClick={() => void remove(c)} aria-label={`${c.name} sil`}><Trash2 size={15} /></button></>}
                </Td>
              </tr>
            );
          })}</tbody>
        </Table>
      )}
      {editing && <Editor row={editing === 'new' ? null : editing} nextOrder={(comps.data?.length ?? 0) + 1} onClose={() => setEditing(null)} />}
    </AdminPage>
  );
}
