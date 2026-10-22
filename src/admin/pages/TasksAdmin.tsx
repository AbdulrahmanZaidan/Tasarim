import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, Pencil, Trash2, CheckCircle2, RotateCcw } from 'lucide-react';
import { AdminPage, ReadOnlyNotice, SearchBox, Table, Th, Td, Pager, paginate } from '../ui';
import { usePhases, useTasks, useComponents, useProfiles } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { Modal, useConfirm, useToast, SkeletonRows, ErrorNotice, EmptyState } from '../../components/feedback';
import { Select, TextArea, TextInput, useForm, v, nn } from '../../components/form';
import { Badge } from '../../components/ui';
import { tasks as taskSvc, type Task } from '../../services/entities';
import { priorityLabels, priorityTone, workStatusLabels, workTone, semesterLabels, options, type Priority, type WorkStatus } from '../../lib/labels';
import { fmtDate, norm, todayISO } from '../../lib/format';
import { errorMessage } from '../../lib/errors';

type Vals = { title: string; description: string; phase_id: string; component_id: string; status: WorkStatus; priority: Priority; weight: string; assigned_to: string; due_date: string };
const PAGE = 30;

function Editor({ row, defaults, onClose }: { row: Task | null; defaults: Partial<Vals>; onClose: () => void }) {
  const toast = useToast();
  const ph = usePhases(); const comps = useComponents(); const people = useProfiles();
  const [busy, setBusy] = useState(false);
  const f = useForm<Vals>(row ? {
    title: row.title, description: row.description ?? '', phase_id: row.phase_id, component_id: row.component_id ?? '', status: row.status, priority: row.priority,
    weight: String(row.weight), assigned_to: row.assigned_to ?? '', due_date: row.due_date ?? '',
  } : { title: '', description: '', phase_id: '', component_id: '', status: 'not_started', priority: 'medium', weight: '1', assigned_to: '', due_date: '', ...defaults }, {
    title: [v.required(), v.min(2), v.max(200)], phase_id: [v.required('Aşama seçin.')], weight: [v.required(), v.number({ min: 0.01, max: 1000 })], description: [v.max(4000)],
  });
  const save = async () => {
    if (!f.check()) return;
    const x = f.values;
    const p = { title: x.title.trim(), description: nn(x.description), phase_id: x.phase_id, component_id: x.component_id || null, status: x.status, priority: x.priority,
      weight: Number(x.weight.replace(',', '.')), assigned_to: x.assigned_to || null, due_date: x.due_date || null };
    setBusy(true);
    try {
      if (row) await taskSvc.update(row.id, p, row.updated_at); else await taskSvc.insert(p);
      toast.success('Görev kaydedildi.'); onClose();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} busy={busy} title={row ? 'Görevi düzenle' : 'Yeni görev'}
      footer={<><button className="btn-ghost" onClick={onClose} disabled={busy}>Vazgeç</button><button className="btn-primary" disabled={busy || !f.dirty} onClick={() => void save()}>{busy ? 'Kaydediliyor…' : 'Kaydet'}</button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput className="sm:col-span-2" label="Görev" required value={f.values.title} error={f.errors.title} onChange={(e) => f.set('title', e.target.value)} />
        <TextArea className="sm:col-span-2" label="Açıklama / kilometre taşı notu" value={f.values.description} error={f.errors.description} onChange={(e) => f.set('description', e.target.value)} />
        <Select label="Aşama" required value={f.values.phase_id} error={f.errors.phase_id} onChange={(e) => f.set('phase_id', e.target.value)} placeholder="— Seçiniz —"
          options={(ph.data ?? []).map((p) => ({ value: p.id, label: `${semesterLabels[p.semester]} · ${p.title}` }))} />
        <Select label="İlgili bileşen" value={f.values.component_id} onChange={(e) => f.set('component_id', e.target.value)} placeholder="— Yok —" options={(comps.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
        <Select label="Durum" value={f.values.status} onChange={(e) => f.set('status', e.target.value as WorkStatus)} options={options(workStatusLabels)} hint="“Tamamlandı” yalnızca gerçekleşen iş için seçilmelidir; tamamlanma tarihi otomatik kaydedilir." />
        <Select label="Öncelik" value={f.values.priority} onChange={(e) => f.set('priority', e.target.value as Priority)} options={options(priorityLabels)} />
        <Select label="Sorumlu" value={f.values.assigned_to} onChange={(e) => f.set('assigned_to', e.target.value)} placeholder="— Atanmadı —" options={(people.data ?? []).map((p) => ({ value: p.id, label: p.full_name || p.email || p.id }))} />
        <TextInput label="Hedef tarih" type="date" value={f.values.due_date} onChange={(e) => f.set('due_date', e.target.value)} />
        <TextInput label="Ağırlık" inputMode="decimal" value={f.values.weight} error={f.errors.weight} onChange={(e) => f.set('weight', e.target.value)} hint="Aşama ilerlemesine katkısı (varsayılan 1)." />
      </div>
    </Modal>
  );
}

export default function TasksAdmin() {
  const { canEdit } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const [params] = useSearchParams();
  const tasks = useTasks(); const ph = usePhases(); const comps = useComponents(); const people = useProfiles();
  const [q, setQ] = useState('');
  const [phase, setPhase] = useState('');
  const [status, setStatus] = useState(params.get('durum') ?? '');
  const [sem, setSem] = useState('');
  const [page, setPage] = useState(0);
  const [editing, setEditing] = useState<Task | null | 'new'>(null);
  const today = todayISO();
  const phaseById = new Map((ph.data ?? []).map((p) => [p.id, p]));

  const list = useMemo(() => (tasks.data ?? []).filter((t) =>
    (!q.trim() || norm(`${t.title} ${t.description ?? ''}`).includes(norm(q.trim())))
    && (!phase || t.phase_id === phase)
    && (!sem || phaseById.get(t.phase_id)?.semester === sem)
    && (!status || (status === 'overdue' ? t.status !== 'completed' && !!t.due_date && t.due_date < today : t.status === status)),
  ).sort((a, b) => (phaseById.get(a.phase_id)?.sort_order ?? 0) - (phaseById.get(b.phase_id)?.sort_order ?? 0) || a.sort_order - b.sort_order), [tasks.data, q, phase, sem, status, ph.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const setTaskStatus = async (t: Task, s: WorkStatus) => {
    try { await taskSvc.update(t.id, { status: s }, t.updated_at); toast.success(s === 'completed' ? 'Görev tamamlandı olarak işaretlendi.' : 'Görev durumu güncellendi.'); }
    catch (e) { toast.error(errorMessage(e)); }
  };
  const remove = async (t: Task) => {
    if (!(await confirm({ title: 'Görev silinsin mi?', tone: 'danger', confirmLabel: 'Sil', message: <>“<b>{t.title}</b>” kalıcı olarak silinecek ve ilerleme hesabından çıkarılacak.</> }))) return;
    try { await taskSvc.remove(t.id); toast.success('Görev silindi.'); } catch (e) { toast.error(errorMessage(e)); }
  };
  const person = (id: string | null) => people.data?.find((p) => p.id === id)?.full_name ?? (id ? 'Ekip üyesi' : '—');

  return (
    <AdminPage title="Görevler" description="Aşama ve bileşen ilerlemesi yalnızca bu görevlerin tamamlanma durumundan hesaplanır."
      actions={canEdit && <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} aria-hidden /> Yeni görev</button>}>
      <ReadOnlyNotice />
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={q} onChange={(x) => { setQ(x); setPage(0); }} placeholder="Görev ara" />
        <select className="input w-auto" value={sem} onChange={(e) => { setSem(e.target.value); setPage(0); }} aria-label="Dönem"><option value="">Tüm dönemler</option>{options(semesterLabels).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
        <select className="input w-auto" value={phase} onChange={(e) => { setPhase(e.target.value); setPage(0); }} aria-label="Aşama"><option value="">Tüm aşamalar</option>{(ph.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select>
        <select className="input w-auto" value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }} aria-label="Durum"><option value="">Tüm durumlar</option>{options(workStatusLabels).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}<option value="overdue">Gecikmiş</option></select>
      </div>
      {tasks.error && <ErrorNotice error={tasks.error} onRetry={() => void tasks.refetch()} />}
      {!tasks.data ? <SkeletonRows /> : list.length === 0 ? <EmptyState title="Görev bulunamadı">{(tasks.data ?? []).length ? 'Süzgeçleri değiştirin.' : 'Henüz görev eklenmedi.'}</EmptyState> : (
        <>
          <Table minWidth={980}>
            <thead><tr><Th>Görev</Th><Th>Aşama</Th><Th>Durum</Th><Th>Öncelik</Th><Th>Sorumlu</Th><Th>Hedef</Th><Th>Ağırlık</Th><Th /></tr></thead>
            <tbody>{paginate(list, page, PAGE).map((t) => {
              const late = t.status !== 'completed' && t.due_date && t.due_date < today;
              return (
                <tr key={t.id} className="hover:bg-brand-mist/40">
                  <Td><b className={t.status === 'completed' ? 'text-ink-3 line-through decoration-ink-3/40' : ''}>{t.title}</b>
                    {t.component_id && <div className="text-[12px] text-ink-3">{comps.data?.find((c) => c.id === t.component_id)?.name}</div>}
                    {t.completed_at && <div className="text-[12px] text-emerald-700">Tamamlandı: {fmtDate(t.completed_at)}</div>}</Td>
                  <Td className="text-[12.5px]">{phaseById.get(t.phase_id)?.title}</Td>
                  <Td>
                    {canEdit ? (
                      <select aria-label={`${t.title} durumu`} className={`chip cursor-pointer ${({ muted: 'border-ink-3/25 bg-neutral-100 text-ink-3', warning: 'border-amber-600/30 bg-amber-50 text-amber-800', success: 'border-emerald-700/30 bg-emerald-50 text-emerald-800', danger: 'border-red-700/30 bg-red-50 text-red-800' } as Record<string, string>)[workTone[t.status]]}`}
                        value={t.status} onChange={(e) => void setTaskStatus(t, e.target.value as WorkStatus)}>
                        {options(workStatusLabels).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    ) : <Badge tone={workTone[t.status]}>{workStatusLabels[t.status]}</Badge>}
                  </Td>
                  <Td><Badge tone={priorityTone[t.priority]} dot={false}>{priorityLabels[t.priority]}</Badge></Td>
                  <Td className="text-[12.5px]">{person(t.assigned_to)}</Td>
                  <Td className={`whitespace-nowrap text-[12.5px] ${late ? 'font-semibold text-red-700' : ''}`}>{fmtDate(t.due_date)}{late && ' · gecikti'}</Td>
                  <Td className="mono">{t.weight}</Td>
                  <Td className="whitespace-nowrap text-right">
                    {canEdit && <>
                      {t.status !== 'completed' ? <button className="btn-ghost px-2 py-1 text-emerald-700" onClick={() => void setTaskStatus(t, 'completed')} title="Tamamlandı olarak işaretle" aria-label={`${t.title} tamamlandı`}><CheckCircle2 size={16} /></button>
                        : <button className="btn-ghost px-2 py-1" onClick={() => void setTaskStatus(t, 'in_progress')} title="Yeniden aç" aria-label={`${t.title} yeniden aç`}><RotateCcw size={15} /></button>}
                      <button className="btn-ghost px-2 py-1" onClick={() => setEditing(t)} aria-label={`${t.title} düzenle`}><Pencil size={15} /></button>
                      <button className="btn-ghost px-2 py-1 text-red-700 hover:bg-red-50" onClick={() => void remove(t)} aria-label={`${t.title} sil`}><Trash2 size={15} /></button>
                    </>}
                  </Td>
                </tr>
              );
            })}</tbody>
          </Table>
          <Pager page={page} pageSize={PAGE} total={list.length} onPage={setPage} />
        </>
      )}
      {editing && <Editor row={editing === 'new' ? null : editing} defaults={{ phase_id: phase }} onClose={() => setEditing(null)} />}
    </AdminPage>
  );
}
