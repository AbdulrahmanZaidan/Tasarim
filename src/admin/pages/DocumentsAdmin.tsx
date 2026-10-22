import { useRef, useState } from 'react';
import { Plus, Pencil, Trash2, Globe, Lock, RefreshCw, Eye } from 'lucide-react';
import { AdminPage, ReadOnlyNotice, SearchBox, Table, Th, Td, Dropzone, ProgressLine } from '../ui';
import { useComponents, useDocuments, useMediaList } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { Modal, useConfirm, useToast, SkeletonRows, ErrorNotice, EmptyState } from '../../components/feedback';
import { Select, TextArea, TextInput, Checkbox, useForm, v, nn } from '../../components/form';
import { Badge } from '../../components/ui';
import { DownloadButton, useMediaUrls } from '../../components/MediaGallery';
import { documents as docSvc, type TechDoc, type Media } from '../../services/entities';
import { createDocument, deleteDocument, replaceDocumentFile, setDocumentPublished } from '../../services/documents';
import { invalidateMedia } from '../../services/media';
import { documentTypeLabels, options, type DocumentType } from '../../lib/labels';
import { checkFile, isPdf, PRIVATE_BUCKET, PUBLIC_BUCKET } from '../../lib/files';
import { fmtBytes, fmtDate, norm, } from '../../lib/format';
import { errorMessage } from '../../lib/errors';

type Vals = { title: string; description: string; document_type: DocumentType; component_id: string; version: string; is_published: boolean };

function Editor({ row, file, onClose }: { row: TechDoc | null; file?: Media; onClose: () => void }) {
  const toast = useToast();
  const comps = useComponents();
  const [busy, setBusy] = useState(false);
  const [upload, setUpload] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const f = useForm<Vals>(row ? { title: row.title, description: row.description ?? '', document_type: row.document_type, component_id: row.component_id ?? '', version: row.version, is_published: row.is_published }
    : { title: '', description: '', document_type: 'project_report', component_id: '', version: '1.0', is_published: false }, {
    title: [v.required(), v.min(3), v.max(200)], version: [v.required(), v.pattern(/^[0-9A-Za-z.-]{1,20}$/, 'ör. 1.0, 2.1-taslak')], description: [v.max(4000)],
  });
  const bucket = f.values.is_published ? PUBLIC_BUCKET : PRIVATE_BUCKET;
  const fileErr = upload ? checkFile(upload, bucket).error : null;
  const save = async () => {
    if (!f.check()) return;
    if (!row && !upload) { toast.error('Belge dosyası seçin.'); return; }
    if (fileErr) { toast.error(fileErr); return; }
    const x = f.values;
    setBusy(true);
    try {
      const meta = { title: x.title.trim(), description: nn(x.description), document_type: x.document_type, component_id: x.component_id || null, version: x.version };
      if (!row) {
        await createDocument(upload!, { ...meta, is_published: x.is_published }, setProgress);
      } else {
        await docSvc.update(row.id, meta, row.updated_at);
        let fresh = await docSvc.get(row.id);
        if (upload && file) { await replaceDocumentFile(fresh, file, upload, x.version, setProgress); fresh = await docSvc.get(row.id); }
        if (x.is_published !== row.is_published && file) await setDocumentPublished(fresh, file, x.is_published);
      }
      invalidateMedia();
      toast.success('Belge kaydedildi.');
      onClose();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} busy={busy} size="lg" title={row ? 'Belgeyi düzenle' : 'Yeni teknik belge'}
      footer={<><button className="btn-ghost" onClick={onClose} disabled={busy}>Vazgeç</button><button className="btn-primary" disabled={busy || (!f.dirty && !upload)} onClick={() => void save()}>{busy ? 'Kaydediliyor…' : 'Kaydet'}</button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput className="sm:col-span-2" label="Başlık" required value={f.values.title} error={f.errors.title} onChange={(e) => f.set('title', e.target.value)} />
        <TextArea className="sm:col-span-2" label="Açıklama" value={f.values.description} error={f.errors.description} onChange={(e) => f.set('description', e.target.value)} />
        <Select label="Belge türü" value={f.values.document_type} onChange={(e) => f.set('document_type', e.target.value as DocumentType)} options={options(documentTypeLabels)} />
        <Select label="İlgili bileşen" value={f.values.component_id} onChange={(e) => f.set('component_id', e.target.value)} placeholder="— Yok —" options={(comps.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
        <TextInput label="Sürüm" required value={f.values.version} error={f.errors.version} onChange={(e) => f.set('version', e.target.value)} hint={row ? 'Dosyayı değiştirirken sürümü artırın.' : undefined} />
        <div className="self-end"><Checkbox label="Herkese açık yayımla" hint="Yayımlanan belgenin dosyası herkese açık depoya taşınır; kaldırılınca özel depoya alınır." checked={f.values.is_published} onChange={(b) => f.set('is_published', b)} /></div>
        <div className="sm:col-span-2">
          <div className="mb-1 text-[13px] font-medium text-ink-2">{row ? 'Dosyayı değiştir (isteğe bağlı)' : 'Belge dosyası *'}</div>
          {file && !upload && <p className="mb-2 text-[13px] text-ink-3">Mevcut: <span className="mono">{file.original_file_name}</span> · {fmtBytes(file.file_size)}</p>}
          {upload ? (
            <div className="rounded-lg border border-brand-line p-3 text-[13.5px]">
              <div className="flex items-center justify-between gap-2"><span className="truncate">{upload.name} · {fmtBytes(upload.size)}</span><button className="btn-ghost px-2 py-1 text-[13px]" onClick={() => setUpload(null)} disabled={busy}>Kaldır</button></div>
              {fileErr && <p className="mt-1 text-[12.5px] text-red-700">{fileErr}</p>}
              {busy && <div className="mt-2"><ProgressLine value={progress} /></div>}
            </div>
          ) : <Dropzone multiple={false} onFiles={(fs) => setUpload(fs[0])} accept=".pdf,.png,.jpg,.jpeg,.zip,.txt,.csv,.docx,.xlsx,.pptx,.dig,.circ" hint="PDF önerilir (genel sitede önizlenebilir). Word/Excel dosyaları yalnızca özel belgelerde kullanılabilir." />}
        </div>
      </div>
    </Modal>
  );
}

function Preview({ media, onClose }: { media: Media; onClose: () => void }) {
  const urls = useMediaUrls([media]);
  return <Modal open onClose={onClose} title={media.title} size="xl">{urls.data?.[media.id] ? <iframe title={media.title} src={urls.data[media.id]} className="h-[75vh] w-full rounded border border-brand-line" /> : <SkeletonRows />}</Modal>;
}

export default function DocumentsAdmin() {
  const { canEdit } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const docs = useDocuments(); const media = useMediaList(); const comps = useComponents();
  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const [editing, setEditing] = useState<TechDoc | null | 'new'>(null);
  const [preview, setPreview] = useState<Media | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const quickReplace = useRef<HTMLInputElement>(null);
  void quickReplace;
  const fileOf = (d: TechDoc) => media.data?.find((m) => m.id === d.file_id);
  const list = (docs.data ?? []).filter((d) => (!q.trim() || norm(`${d.title} ${d.description ?? ''}`).includes(norm(q.trim()))) && (!type || d.document_type === type));

  const togglePublish = async (d: TechDoc) => {
    const f = fileOf(d); if (!f) return;
    setBusyId(d.id);
    try { await setDocumentPublished(d, f, !d.is_published); toast.success(d.is_published ? 'Belge yayından kaldırıldı ve özel depoya alındı.' : 'Belge yayımlandı.'); }
    catch (e) { toast.error(errorMessage(e)); } finally { setBusyId(null); invalidateMedia(); }
  };
  const remove = async (d: TechDoc) => {
    if (!(await confirm({ title: 'Belge silinsin mi?', tone: 'danger', confirmLabel: 'Belgeyi ve dosyasını sil', message: <>“<b>{d.title}</b>” ve bağlı dosyası kalıcı olarak silinecek.</> }))) return;
    setBusyId(d.id);
    try { await deleteDocument(d, fileOf(d)); toast.success('Belge silindi.'); } catch (e) { toast.error(errorMessage(e)); } finally { setBusyId(null); }
  };

  return (
    <AdminPage title="Teknik Belgeler" description="Raporlar, devre şemaları, simülasyon/test raporları, veri sayfaları, toplantı notları ve bitirme teslimleri. Yalnızca yayımlanan belgeler genel sitede görünür."
      actions={canEdit && <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} aria-hidden /> Yeni belge</button>}>
      <ReadOnlyNotice />
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={q} onChange={setQ} placeholder="Belge ara" />
        <select className="input w-auto" value={type} onChange={(e) => setType(e.target.value)} aria-label="Tür"><option value="">Tüm türler</option>{options(documentTypeLabels).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
      </div>
      {docs.error && <ErrorNotice error={docs.error} onRetry={() => void docs.refetch()} />}
      {!docs.data ? <SkeletonRows /> : list.length === 0 ? <EmptyState title="Belge yok">{(docs.data ?? []).length ? 'Süzgeçleri değiştirin.' : 'İlk raporu veya şemayı “Yeni belge” ile yükleyin.'}</EmptyState> : (
        <Table minWidth={900}>
          <thead><tr><Th>Belge</Th><Th>Tür</Th><Th>Bileşen</Th><Th>Sürüm</Th><Th>Güncelleme</Th><Th>Durum</Th><Th /></tr></thead>
          <tbody>{list.map((d) => {
            const f = fileOf(d);
            return (
              <tr key={d.id} className={`hover:bg-brand-mist/40 ${busyId === d.id ? 'opacity-60' : ''}`}>
                <Td><b>{d.title}</b>{f && <div className="text-[12px] text-ink-3">{f.original_file_name} · {fmtBytes(f.file_size)}</div>}</Td>
                <Td className="text-[12.5px]">{documentTypeLabels[d.document_type]}</Td>
                <Td className="text-[12.5px]">{comps.data?.find((c) => c.id === d.component_id)?.name ?? '—'}</Td>
                <Td className="mono">{d.version}</Td>
                <Td className="whitespace-nowrap text-[12.5px]">{fmtDate(d.updated_at)}</Td>
                <Td>{d.is_published ? <Badge tone="success" dot={false}><Globe size={11} aria-hidden /> Yayında</Badge> : <Badge tone="muted" dot={false}><Lock size={11} aria-hidden /> Özel</Badge>}</Td>
                <Td className="whitespace-nowrap text-right">
                  {f && isPdf(f.mime_type) && <button className="btn-ghost px-2 py-1" onClick={() => setPreview(f)} aria-label="PDF önizle"><Eye size={15} /></button>}
                  {f && <DownloadButton media={f} label="" className="btn-ghost px-2 py-1" />}
                  {canEdit && <>
                    <button className="btn-ghost px-2 py-1" disabled={busyId === d.id} onClick={() => void togglePublish(d)} aria-label={d.is_published ? 'Yayından kaldır' : 'Yayımla'} title={d.is_published ? 'Yayından kaldır' : 'Yayımla'}>{d.is_published ? <Lock size={15} /> : <Globe size={15} />}</button>
                    <button className="btn-ghost px-2 py-1" onClick={() => setEditing(d)} aria-label="Düzenle / dosyayı değiştir" title="Düzenle / dosyayı değiştir"><Pencil size={15} /></button>
                    <button className="btn-ghost px-2 py-1 text-red-700 hover:bg-red-50" disabled={busyId === d.id} onClick={() => void remove(d)} aria-label="Sil"><Trash2 size={15} /></button>
                  </>}
                </Td>
              </tr>
            );
          })}</tbody>
        </Table>
      )}
      <p className="mt-3 flex items-center gap-1.5 text-[12.5px] text-ink-3"><RefreshCw size={13} aria-hidden /> Belge dosyasını değiştirmek için düzenle düğmesini kullanın; eski dosya otomatik olarak kaldırılır.</p>
      {editing && <Editor row={editing === 'new' ? null : editing} file={editing === 'new' ? undefined : fileOf(editing)} onClose={() => setEditing(null)} />}
      {preview && <Preview media={preview} onClose={() => setPreview(null)} />}
    </AdminPage>
  );
}
