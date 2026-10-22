import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Pencil, Trash2, Scale } from 'lucide-react';
import { AdminPage, ReadOnlyNotice, Table, Th, Td } from '../ui';
import { usePhases, useTasks } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { Modal, useConfirm, useToast, SkeletonRows, ErrorNotice } from '../../components/feedback';
import { Select, TextArea, TextInput, useForm, v, nn, useUnsavedChanges } from '../../components/form';
import { StatusBadge, ProgressBar, Callout } from '../../components/ui';
import { phases, setPhaseWeights, type Phase } from '../../services/entities';
import { phaseProgress, validateWeights, weightedProgress } from '../../lib/progress';
import { phaseStatusLabels, semesterLabels, options, type PhaseStatus, type Semester } from '../../lib/labels';
import { fmtDate } from '../../lib/format';
import { errorMessage } from '../../lib/errors';
import { slugify } from '../../lib/materialsImport';

const routeOptions = [
  { value: '/proje/mimari-sema', label: 'Mimari ve Şema sayfası' }, { value: '/proje/simulasyon', label: 'Simülasyon sayfası' },
  { value: '/proje/github', label: 'GitHub sayfası' }, { value: '/proje/malzeme-maliyet', label: 'Malzeme ve Maliyet sayfası' },
  { value: '/proje/tasarim-ii', label: 'Tasarım II sayfası' },
];
type Vals = { title: string; short_title: string; slug: string; description: string; deliverable: string; semester: Semester; status: PhaseStatus; start_date: string; target_date: string; route: string; sort_order: string };

function Editor({ row, nextOrder, onClose }: { row: Phase | null; nextOrder: number; onClose: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const f = useForm<Vals>(row ? {
    title: row.title, short_title: row.short_title ?? '', slug: row.slug, description: row.description ?? '', deliverable: row.deliverable ?? '', semester: row.semester,
    status: row.status, start_date: row.start_date ?? '', target_date: row.target_date ?? '', route: row.route ?? '', sort_order: String(row.sort_order),
  } : { title: '', short_title: '', slug: '', description: '', deliverable: '', semester: 'tasarim_1', status: 'planned', start_date: '', target_date: '', route: '', sort_order: String(nextOrder) }, {
    title: [v.required(), v.min(2), v.max(160)],
    slug: [v.required(), v.pattern(/^[a-z0-9-]{2,40}$/, 'Yalnızca küçük harf, rakam ve tire.')],
    short_title: [v.max(40)],
    target_date: [(x, all) => (x && all.start_date && String(x) < all.start_date ? 'Hedef tarih başlangıçtan önce olamaz.' : null)],
    sort_order: [v.number({ integer: true, min: 0 })],
  });
  const save = async () => {
    if (!f.check()) return;
    const x = f.values;
    const p = { title: x.title.trim(), short_title: nn(x.short_title), slug: x.slug, description: nn(x.description), deliverable: nn(x.deliverable), semester: x.semester, status: x.status,
      start_date: x.start_date || null, target_date: x.target_date || null, route: x.route || null, sort_order: Number(x.sort_order) || 0 };
    setBusy(true);
    try {
      if (row) await phases.update(row.id, p, row.updated_at);
      else { await phases.insert(p); toast.info('Yeni aşama 0 ağırlıkla eklendi. Genel ilerlemeye katılması için ağırlıkları yeniden dağıtın.'); }
      toast.success('Aşama kaydedildi.'); onClose();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const t2NotStartedWarning = f.values.semester === 'tasarim_2' && ['in_progress', 'completed'].includes(f.values.status) && row?.status !== f.values.status;
  return (
    <Modal open onClose={onClose} busy={busy} title={row ? 'Aşamayı düzenle' : 'Yeni aşama'} size="lg"
      footer={<><button className="btn-ghost" onClick={onClose} disabled={busy}>Vazgeç</button><button className="btn-primary" disabled={busy || !f.dirty} onClick={() => void save()}>{busy ? 'Kaydediliyor…' : 'Kaydet'}</button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput label="Başlık" required value={f.values.title} error={f.errors.title} onChange={(e) => { f.set('title', e.target.value); if (!row) f.set('slug', slugify(e.target.value).slice(0, 40)); }} />
        <TextInput label="Kısa başlık" value={f.values.short_title} error={f.errors.short_title} onChange={(e) => f.set('short_title', e.target.value)} />
        <Select label="Dönem" value={f.values.semester} onChange={(e) => f.set('semester', e.target.value as Semester)} options={options(semesterLabels)} />
        <Select label="Durum" value={f.values.status} onChange={(e) => f.set('status', e.target.value as PhaseStatus)} options={options(phaseStatusLabels)} />
        {t2NotStartedWarning && <div className="sm:col-span-2"><Callout tone="warn">Tasarım II aşamasını “{phaseStatusLabels[f.values.status]}” olarak işaretliyorsunuz. Bu durum yalnızca gerçekleşmiş çalışmalarla desteklenmelidir.</Callout></div>}
        <TextArea className="sm:col-span-2" label="Açıklama" value={f.values.description} onChange={(e) => f.set('description', e.target.value)} />
        <TextInput className="sm:col-span-2" label="Çıktı (teslim edilecek)" value={f.values.deliverable} onChange={(e) => f.set('deliverable', e.target.value)} />
        <TextInput label="Başlangıç tarihi" type="date" value={f.values.start_date} onChange={(e) => f.set('start_date', e.target.value)} />
        <TextInput label="Hedef tarih" type="date" value={f.values.target_date} error={f.errors.target_date} onChange={(e) => f.set('target_date', e.target.value)} />
        <Select label="Ayrıntı sayfası" value={f.values.route} onChange={(e) => f.set('route', e.target.value)} placeholder="İlerleme sayfasındaki kart" options={routeOptions} />
        <div className="grid grid-cols-2 gap-2">
          <TextInput label="Kısa ad" required value={f.values.slug} error={f.errors.slug} disabled={!!row} onChange={(e) => f.set('slug', e.target.value)} />
          <TextInput label="Sıra" type="number" value={f.values.sort_order} error={f.errors.sort_order} onChange={(e) => f.set('sort_order', e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}

export default function PhasesAdmin() {
  const { canEdit } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const ph = usePhases(); const tasks = useTasks();
  const [editing, setEditing] = useState<Phase | null | 'new'>(null);
  const [weights, setWeights] = useState<Record<string, string>>({});
  const [savingW, setSavingW] = useState(false);
  useEffect(() => { if (ph.data) setWeights(Object.fromEntries(ph.data.map((p) => [p.id, String(p.weight)]))); }, [ph.data]);
  const P = ph.data ?? [];
  const ptasks = (tasks.data ?? []).map((t) => ({ status: t.status, weight: t.weight, phase_id: t.phase_id }));
  const numW = Object.fromEntries(Object.entries(weights).map(([k, x]) => [k, Number(String(x).replace(',', '.'))]));
  const wErr = P.length ? validateWeights(numW) : null;
  const wDirty = P.some((p) => Number(weights[p.id]) !== Number(p.weight));
  useUnsavedChanges(wDirty);
  const overall = weightedProgress(P.map((p) => ({ id: p.id, weight: p.weight })), ptasks);

  const saveWeights = async () => {
    if (wErr) return;
    setSavingW(true);
    try { await setPhaseWeights(numW); toast.success('Aşama ağırlıkları kaydedildi.'); } catch (e) { toast.error(errorMessage(e)); } finally { setSavingW(false); }
  };
  const remove = async (p: Phase) => {
    const n = ptasks.filter((t) => t.phase_id === p.id).length;
    if (!(await confirm({ title: 'Aşama silinsin mi?', tone: 'danger', confirmLabel: 'Aşamayı ve görevlerini sil', message: <>“<b>{p.title}</b>” ve bu aşamaya ait <b>{n} görev</b> kalıcı olarak silinecek. İlerleme kayıtları silinmez. Silme sonrasında ağırlıkları yeniden dağıtmanız gerekir.</> }))) return;
    try { await phases.remove(p.id); toast.success('Aşama silindi.'); } catch (e) { toast.error(errorMessage(e)); }
  };
  const even = () => {
    const each = Math.floor((100 / P.length) * 100) / 100;
    const rest = Math.round((100 - each * P.length) * 100) / 100;
    setWeights(Object.fromEntries(P.map((p, i) => [p.id, String(i === 0 ? Math.round((each + rest) * 100) / 100 : each)])));
  };

  return (
    <AdminPage title="Proje Aşamaları" description="Tasarım I ve Tasarım II aşamaları. Aşama yüzdesi görevlerden hesaplanır; genel ilerleme bu yüzdelerin aşama ağırlıklarıyla ağırlıklı ortalamasıdır."
      actions={canEdit && <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} aria-hidden /> Yeni aşama</button>}>
      <ReadOnlyNotice />
      {ph.error && <ErrorNotice error={ph.error} onRetry={() => void ph.refetch()} />}
      {!ph.data ? <SkeletonRows /> : (
        <>
          <Table minWidth={900}>
            <thead><tr><Th>#</Th><Th>Aşama</Th><Th>Dönem</Th><Th>Durum</Th><Th>İlerleme</Th><Th>Tarihler</Th><Th>Ağırlık</Th><Th /></tr></thead>
            <tbody>{P.map((p, i) => {
              const n = ptasks.filter((t) => t.phase_id === p.id);
              return (
                <tr key={p.id} className="hover:bg-brand-mist/40">
                  <Td className="mono text-ink-3">{String(i + 1).padStart(2, '0')}</Td>
                  <Td><b>{p.title}</b><div className="text-[12px] text-ink-3">{p.deliverable}</div></Td>
                  <Td>{semesterLabels[p.semester]}</Td>
                  <Td><StatusBadge status={p.status} /></Td>
                  <Td className="w-48">{n.length ? <ProgressBar value={phaseProgress(p.id, ptasks)} label={`${n.filter((t) => t.status === 'completed').length}/${n.length} görev`} /> : <Link to="/admin/tasks" className="text-[12px]">Görev ekleyin</Link>}</Td>
                  <Td className="whitespace-nowrap text-[12.5px]">{p.start_date || p.target_date ? <>{fmtDate(p.start_date)}<br />→ {fmtDate(p.target_date)}</> : '—'}</Td>
                  <Td>
                    <input aria-label={`${p.title} ağırlığı`} inputMode="decimal" className="input mono w-20 py-1 text-right" disabled={!canEdit}
                      value={weights[p.id] ?? ''} onChange={(e) => setWeights((w) => ({ ...w, [p.id]: e.target.value }))} />
                  </Td>
                  <Td className="whitespace-nowrap text-right">
                    {canEdit && <><button className="btn-ghost px-2 py-1" onClick={() => setEditing(p)} aria-label={`${p.title} düzenle`}><Pencil size={15} /></button>
                      <button className="btn-ghost px-2 py-1 text-red-700 hover:bg-red-50" onClick={() => void remove(p)} aria-label={`${p.title} sil`}><Trash2 size={15} /></button></>}
                  </Td>
                </tr>
              );
            })}</tbody>
          </Table>
          <div className="card mt-4 flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
            <Scale size={20} className="shrink-0 text-brand" aria-hidden />
            <div className="flex-1 text-[13.5px]">
              <b>Ağırlık toplamı: <span className={wErr ? 'text-red-700' : 'text-emerald-700'}>{Object.values(numW).reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0).toLocaleString('tr-TR')}</span> / 100</b>
              <span className="block text-ink-3">{wErr ?? 'Ağırlıklar geçerli.'} Kayıtlı değerlerle genel ilerleme: %{overall.value.toLocaleString('tr-TR')}.</span>
            </div>
            {canEdit && <div className="flex gap-2">
              <button className="btn-ghost" onClick={even} disabled={!P.length}>Eşit dağıt</button>
              <button className="btn-primary" disabled={!!wErr || !wDirty || savingW} onClick={() => void saveWeights()}>{savingW ? 'Kaydediliyor…' : 'Ağırlıkları kaydet'}</button>
            </div>}
          </div>
        </>
      )}
      {editing && <Editor row={editing === 'new' ? null : editing} nextOrder={P.length + 1} onClose={() => setEditing(null)} />}
    </AdminPage>
  );
}
