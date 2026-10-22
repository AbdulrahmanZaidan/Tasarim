import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Pencil, Trash2, Globe, Lock, ExternalLink, Paperclip, Wand2 } from 'lucide-react';
import { AdminPage, ReadOnlyNotice, SearchBox, Table, Th, Td } from '../ui';
import UploadPanel from '../UploadPanel';
import { useComponents, useMediaList, useSimulations } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { Modal, useConfirm, useToast, EmptyState, SkeletonRows, ErrorNotice } from '../../components/feedback';
import { Select, TextArea, TextInput, Checkbox, useForm, v, nn } from '../../components/form';
import { Badge } from '../../components/ui';
import { MediaGallery } from '../../components/MediaGallery';
import { simulations, type Simulation } from '../../services/entities';
import { setMediaBucket, invalidateMedia } from '../../services/media';
import { resultLabels, resultTone, softwareOptions, options, type ExperimentResult } from '../../lib/labels';
import { PUBLIC_BUCKET, PRIVATE_BUCKET } from '../../lib/files';
import { fmtDate, norm, todayISO } from '../../lib/format';
import { errorMessage } from '../../lib/errors';

type FormVals = {
  title: string; component_id: string; software_used: string; software_version: string; description: string;
  experiment_objective: string; methodology: string; input_values: string; operation: string; expected_output: string;
  actual_output: string; result_status: ExperimentResult; experiment_date: string; notes: string; conclusion: string; is_published: boolean;
};
const empty: FormVals = {
  title: '', component_id: '', software_used: 'Digital', software_version: '', description: '', experiment_objective: '', methodology: '',
  input_values: '', operation: '', expected_output: '', actual_output: '', result_status: 'not_started', experiment_date: '', notes: '', conclusion: '', is_published: false,
};
const fromRow = (s: Simulation): FormVals => ({
  title: s.title, component_id: s.component_id ?? '', software_used: s.software_used, software_version: s.software_version ?? '', description: s.description ?? '',
  experiment_objective: s.experiment_objective ?? '', methodology: s.methodology ?? '', input_values: s.input_values ?? '', operation: s.operation ?? '',
  expected_output: s.expected_output ?? '', actual_output: s.actual_output ?? '', result_status: s.result_status, experiment_date: s.experiment_date ?? '',
  notes: s.notes ?? '', conclusion: s.conclusion ?? '', is_published: s.is_published,
});

function SimulationEditor({ sim, onClose }: { sim: Simulation | null; onClose: () => void }) {
  const { canEdit } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const comps = useComponents();
  const media = useMediaList();
  const [current, setCurrent] = useState<Simulation | null>(sim);
  const [busy, setBusy] = useState(false);
  const f = useForm<FormVals>(sim ? fromRow(sim) : empty, {
    title: [v.required(), v.min(3), v.max(200)],
    software_used: [v.required()],
    actual_output: [(x, all) => (['passed', 'failed'].includes(all.result_status) && !String(x).trim() ? '“Başarılı/Başarısız” sonucu için gözlenen çıktıyı girin.' : null)],
    experiment_date: [(x, all) => (['passed', 'failed'].includes(all.result_status) && !x ? 'Deney tarihini girin.' : null), (x) => (x && String(x) > todayISO() ? 'Deney tarihi gelecekte olamaz.' : null)],
  });
  const attachments = (media.data ?? []).filter((m) => current && m.simulation_id === current.id);
  const privateAtt = attachments.filter((m) => m.bucket_name !== PUBLIC_BUCKET);

  const close = async () => {
    if (f.dirty && !(await confirm({ title: 'Kaydedilmemiş değişiklikler', message: 'Formda kaydetmediğiniz değişiklikler var. Kapatırsanız kaybolacak.', confirmLabel: 'Kapat', tone: 'danger' }))) return;
    onClose();
  };
  const save = async () => {
    if (!f.check()) { toast.error('Lütfen işaretli alanları düzeltin.'); return; }
    const x = f.values;
    const payload = {
      title: x.title.trim(), component_id: x.component_id || null, software_used: x.software_used, software_version: nn(x.software_version),
      description: nn(x.description), experiment_objective: nn(x.experiment_objective), methodology: nn(x.methodology), input_values: nn(x.input_values),
      operation: nn(x.operation), expected_output: nn(x.expected_output), actual_output: nn(x.actual_output), result_status: x.result_status,
      experiment_date: x.experiment_date || null, notes: nn(x.notes), conclusion: nn(x.conclusion), is_published: x.is_published,
    };
    setBusy(true);
    try {
      const row = current ? await simulations.update(current.id, payload, current.updated_at) : await simulations.insert(payload);
      setCurrent(row);
      f.reset(fromRow(row));
      toast.success(current ? 'Deney güncellendi.' : 'Deney kaydedildi. Şimdi ekran görüntüsü ve dosya ekleyebilirsiniz.');
      if (row.is_published && privateAtt.length) toast.info(`Bu deneyin ${privateAtt.length} eki özel depoda; genel sitede görünmesi için “Ekleri herkese açık yap” düğmesini kullanın.`);
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const publishAttachments = async () => {
    setBusy(true);
    let ok = 0; const errs: string[] = [];
    for (const m of privateAtt) { try { await setMediaBucket(m, PUBLIC_BUCKET); ok++; } catch (e) { errs.push(`${m.title}: ${errorMessage(e)}`); } }
    invalidateMedia(); setBusy(false);
    if (ok) toast.success(`${ok} ek herkese açık yapıldı.`);
    errs.forEach((e) => toast.error(e));
  };
  const applyTemplate = () => {
    const alu = comps.data?.find((c) => c.slug === 'alu');
    if (!f.values.title) f.set('title', 'ALU 8-bit toplama testi');
    if (!f.values.component_id && alu) f.set('component_id', alu.id);
    f.set('operation', 'Toplama (SU = 0)');
    f.set('input_values', 'A = 00000101 (5)\nB = 00000011 (3)');
    f.set('expected_output', 'Σ = 00001000 (8), CF = 0');
    if (!f.values.experiment_objective) f.set('experiment_objective', 'ALU’nun iki 8-bit sayıyı doğru topladığını ve elde (carry) bayrağının doğru üretildiğini doğrulamak.');
  };
  const x = f.values;
  return (
    <Modal open onClose={() => void close()} title={current ? 'Deneyi düzenle' : 'Yeni simülasyon deneyi'} size="lg" busy={busy}
      footer={<>
        {!current && canEdit && <button className="btn-ghost mr-auto" onClick={applyTemplate} type="button"><Wand2 size={15} aria-hidden /> ALU toplama şablonu</button>}
        <button className="btn-ghost" onClick={() => void close()} disabled={busy}>Kapat</button>
        {canEdit && <button className="btn-primary" onClick={() => void save()} disabled={busy || (!f.dirty && !!current)}>{busy ? 'Kaydediliyor…' : current ? 'Değişiklikleri kaydet' : 'Kaydet'}</button>}
      </>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput className="sm:col-span-2" label="Deney başlığı" required value={x.title} error={f.errors.title} onChange={(e) => f.set('title', e.target.value)} placeholder="ör. ALU 8-bit toplama testi" />
        <Select label="İlgili bileşen" value={x.component_id} onChange={(e) => f.set('component_id', e.target.value)} placeholder="— Seçiniz —" options={(comps.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
        <div className="grid grid-cols-[1fr_120px] gap-2">
          <Select label="Yazılım" required value={softwareOptions.includes(x.software_used as never) ? x.software_used : 'Diğer'} onChange={(e) => f.set('software_used', e.target.value)} options={softwareOptions.map((s) => ({ value: s, label: s }))} />
          <TextInput label="Sürüm" value={x.software_version} onChange={(e) => f.set('software_version', e.target.value)} placeholder="ör. 0.31" />
        </div>
        <TextArea className="sm:col-span-2" label="Açıklama" rows={2} value={x.description} onChange={(e) => f.set('description', e.target.value)} />
        <TextArea label="Deneyin amacı" value={x.experiment_objective} onChange={(e) => f.set('experiment_objective', e.target.value)} />
        <TextArea label="Yöntem" value={x.methodology} onChange={(e) => f.set('methodology', e.target.value)} hint="Devrenin nasıl kurulduğu, uygulanan adımlar" />
        <TextArea label="Giriş değerleri" className="[&_textarea]:font-mono" value={x.input_values} onChange={(e) => f.set('input_values', e.target.value)} placeholder={'A = 00000101\nB = 00000011'} />
        <TextInput label="Yapılan işlem" value={x.operation} onChange={(e) => f.set('operation', e.target.value)} placeholder="ör. Toplama" />
        <TextArea label="Beklenen çıktı" className="[&_textarea]:font-mono" value={x.expected_output} onChange={(e) => f.set('expected_output', e.target.value)} placeholder="ör. 00001000" />
        <TextArea label="Gözlenen (gerçek) çıktı" className="[&_textarea]:font-mono" value={x.actual_output} error={f.errors.actual_output} onChange={(e) => f.set('actual_output', e.target.value)} hint="Simülasyonda gerçekten gözlenen değer. Tahmin girmeyin." />
        <Select label="Sonuç durumu" value={x.result_status} onChange={(e) => f.set('result_status', e.target.value as ExperimentResult)} options={options(resultLabels)} hint="“Başarılı” yalnızca kaydedilmiş gözleme ve kanıta dayanmalıdır." />
        <TextInput label="Deney tarihi" type="date" max={todayISO()} value={x.experiment_date} error={f.errors.experiment_date} onChange={(e) => f.set('experiment_date', e.target.value)} />
        <TextArea label="Notlar" value={x.notes} onChange={(e) => f.set('notes', e.target.value)} />
        <TextArea label="Sonuç ve değerlendirme" value={x.conclusion} onChange={(e) => f.set('conclusion', e.target.value)} />
        <div className="sm:col-span-2"><Checkbox label="Genel sitede yayımla" hint="Yayımlanan deneyler Simülasyon sayfasında ve ilgili bileşen sayfasında görünür." checked={x.is_published} onChange={(b) => f.set('is_published', b)} /></div>
      </div>

      <div className="mt-6 border-t border-brand-line pt-5">
        <h3 className="flex items-center gap-2 text-[15px] font-semibold"><Paperclip size={16} className="text-brand" aria-hidden /> Ekran görüntüleri ve teknik dosyalar</h3>
        {!current ? <p className="mt-2 text-[13.5px] text-ink-3">Dosya eklemek için önce deneyi kaydedin.</p> : (
          <div className="mt-3 space-y-4">
            {attachments.length > 0 && (
              <>
                {privateAtt.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 rounded-lg border border-brand-line bg-brand-soft/50 px-3 py-2 text-[13px]">
                    <Lock size={14} className="text-brand" aria-hidden /> {privateAtt.length} ek özel depoda; genel sitede görünmez.
                    <button className="btn-outline ml-auto py-1 text-[13px]" disabled={busy} onClick={() => void publishAttachments()}><Globe size={14} aria-hidden /> Ekleri herkese açık yap</button>
                  </div>
                )}
                <MediaGallery items={attachments} columns={4} />
              </>
            )}
            {canEdit && <UploadPanel defaults={{ category: 'simulation_screenshot', bucket: current.is_published ? PUBLIC_BUCKET : PRIVATE_BUCKET, simulation_id: current.id, component_id: current.component_id }}
              components={comps.data ?? []} />}
            <p className="text-[12px] text-ink-3">Simülasyon kaynak dosyaları (.dig, .circ, .pdsprj, .zip) “Teknik dosya” kategorisiyle eklenebilir; ziyaretçilere yalnızca indirme olarak sunulur. Ekleri yönetmek için <Link to="/admin/media">Medya</Link> sayfasını da kullanabilirsiniz.</p>
          </div>
        )}
      </div>
    </Modal>
  );
}

export default function SimulationsAdmin() {
  const { canEdit } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const sims = useSimulations();
  const comps = useComponents();
  const media = useMediaList();
  const [q, setQ] = useState('');
  const [comp, setComp] = useState('');
  const [res, setRes] = useState('');
  const [pub, setPub] = useState('');
  const [editing, setEditing] = useState<Simulation | null | 'new'>(null);

  const list = useMemo(() => (sims.data ?? []).filter((s) =>
    (!q.trim() || norm(`${s.title} ${s.description ?? ''} ${s.software_used}`).includes(norm(q.trim())))
    && (!comp || s.component_id === comp) && (!res || s.result_status === res) && (!pub || String(s.is_published) === pub)), [sims.data, q, comp, res, pub]);
  const compName = (id: string | null) => comps.data?.find((c) => c.id === id)?.name ?? '—';

  const togglePublish = async (s: Simulation) => {
    try { await simulations.update(s.id, { is_published: !s.is_published }, s.updated_at); toast.success(s.is_published ? 'Deney yayından kaldırıldı.' : 'Deney yayımlandı.'); }
    catch (e) { toast.error(errorMessage(e)); }
  };
  const remove = async (s: Simulation) => {
    const n = (media.data ?? []).filter((m) => m.simulation_id === s.id).length;
    if (!(await confirm({ title: 'Deney silinsin mi?', tone: 'danger', confirmLabel: 'Sil', message: <>“<b>{s.title}</b>” silinecek.{n > 0 && <> Bu deneye bağlı {n} dosya silinmez; Medya sayfasında bağlantısız olarak kalır.</>}</> }))) return;
    try { await simulations.remove(s.id); invalidateMedia(); toast.success('Deney silindi.'); } catch (e) { toast.error(errorMessage(e)); }
  };

  return (
    <AdminPage title="Simülasyon Deneyleri" description="Her deney; amaç, yöntem, giriş değerleri, beklenen ve gözlenen çıktı, sonuç ve kanıt dosyalarıyla kaydedilir. Tarayıcı içi eğitsel demolar bu kayıtlardan ayrıdır."
      actions={canEdit && <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} aria-hidden /> Yeni deney</button>}>
      <ReadOnlyNotice />
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={q} onChange={setQ} placeholder="Deney ara" />
        <select className="input w-auto" value={comp} onChange={(e) => setComp(e.target.value)} aria-label="Bileşen"><option value="">Tüm bileşenler</option>{(comps.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <select className="input w-auto" value={res} onChange={(e) => setRes(e.target.value)} aria-label="Sonuç"><option value="">Tüm sonuçlar</option>{options(resultLabels).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
        <select className="input w-auto" value={pub} onChange={(e) => setPub(e.target.value)} aria-label="Yayın durumu"><option value="">Tümü</option><option value="true">Yayımlanan</option><option value="false">Taslak</option></select>
      </div>
      {sims.error && <ErrorNotice error={sims.error} onRetry={() => void sims.refetch()} />}
      {!sims.data && !sims.error ? <SkeletonRows /> : list.length === 0 ? (
        <EmptyState title={(sims.data ?? []).length ? 'Süzgeçlere uyan deney yok' : 'Henüz simülasyon deneyi kaydedilmedi'}
          action={canEdit && !(sims.data ?? []).length ? <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} aria-hidden /> İlk deneyi ekle</button> : undefined}>
          {(sims.data ?? []).length ? 'Farklı süzgeçler deneyin.' : 'Digital veya Proteus çalışmalarınızı giriş/çıkış değerleri ve ekran görüntüleriyle kaydedin.'}
        </EmptyState>
      ) : (
        <Table minWidth={860}>
          <thead><tr><Th>Deney</Th><Th>Bileşen</Th><Th>Yazılım</Th><Th>Sonuç</Th><Th>Tarih</Th><Th>Ek</Th><Th>Yayın</Th><Th /></tr></thead>
          <tbody>{list.map((s) => (
            <tr key={s.id} className="hover:bg-brand-mist/40">
              <Td><button className="text-left font-semibold text-ink hover:text-brand" onClick={() => setEditing(s)}>{s.title}</button>{s.operation && <div className="text-[12px] text-ink-3">{s.operation}</div>}</Td>
              <Td>{compName(s.component_id)}</Td>
              <Td>{s.software_used}{s.software_version && <span className="text-ink-3"> {s.software_version}</span>}</Td>
              <Td><Badge tone={resultTone[s.result_status]}>{resultLabels[s.result_status]}</Badge></Td>
              <Td className="whitespace-nowrap">{fmtDate(s.experiment_date)}</Td>
              <Td className="mono">{(media.data ?? []).filter((m) => m.simulation_id === s.id).length}</Td>
              <Td>{s.is_published ? <Badge tone="success" dot={false}><Globe size={11} aria-hidden /> Yayında</Badge> : <Badge tone="muted" dot={false}><Lock size={11} aria-hidden /> Taslak</Badge>}</Td>
              <Td className="whitespace-nowrap text-right">
                {s.is_published && <Link to={`/proje/simulasyon/deney/${s.id}`} className="btn-ghost px-2 py-1" title="Genel sayfada görüntüle" aria-label="Genel sayfada görüntüle"><ExternalLink size={15} /></Link>}
                {canEdit && <>
                  <button className="btn-ghost px-2 py-1" onClick={() => void togglePublish(s)} title={s.is_published ? 'Yayından kaldır' : 'Yayımla'} aria-label={s.is_published ? 'Yayından kaldır' : 'Yayımla'}>{s.is_published ? <Lock size={15} /> : <Globe size={15} />}</button>
                  <button className="btn-ghost px-2 py-1" onClick={() => setEditing(s)} aria-label={`${s.title} düzenle`}><Pencil size={15} /></button>
                  <button className="btn-ghost px-2 py-1 text-red-700 hover:bg-red-50" onClick={() => void remove(s)} aria-label={`${s.title} sil`}><Trash2 size={15} /></button>
                </>}
              </Td>
            </tr>
          ))}</tbody>
        </Table>
      )}
      {editing && <SimulationEditor sim={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </AdminPage>
  );
}
