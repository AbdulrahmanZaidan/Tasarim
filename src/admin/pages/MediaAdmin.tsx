import { useMemo, useRef, useState } from 'react';
import { Pencil, Trash2, RefreshCw, Globe, Lock, Maximize2, FileCode2, FileText, Upload } from 'lucide-react';
import { AdminPage, ReadOnlyNotice, SearchBox, Pager, paginate } from '../ui';
import UploadPanel from '../UploadPanel';
import { useComponents, useMediaList, useSimulations, useProgressUpdates } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { Modal, useConfirm, useToast, EmptyState, SkeletonRows, ErrorNotice } from '../../components/feedback';
import { Select, TextArea, TextInput, useForm, v, nn } from '../../components/form';
import { Lightbox, useMediaUrls, DownloadButton } from '../../components/MediaGallery';
import { Badge } from '../../components/ui';
import { deleteMedia, replaceMediaFile, setMediaBucket, updateMediaMeta, invalidateMedia } from '../../services/media';
import { mediaCategoryLabels, options, type MediaCategory } from '../../lib/labels';
import { isImage, isPdf, PRIVATE_BUCKET, PUBLIC_BUCKET } from '../../lib/files';
import { fmtBytes, fmtDate, norm } from '../../lib/format';
import { errorMessage } from '../../lib/errors';
import type { Media } from '../../services/entities';

const PAGE = 24;

function EditMedia({ media, onClose }: { media: Media; onClose: () => void }) {
  const toast = useToast();
  const comps = useComponents();
  const sims = useSimulations();
  const prog = useProgressUpdates();
  const [busy, setBusy] = useState(false);
  const f = useForm({
    title: media.title, description: media.description ?? '', category: media.category as string,
    component_id: media.component_id ?? '', simulation_id: media.simulation_id ?? '', progress_update_id: media.progress_update_id ?? '',
  }, { title: [v.required(), v.max(200)], description: [v.max(4000)] });
  const save = async () => {
    if (!f.check()) return;
    setBusy(true);
    try {
      await updateMediaMeta(media, {
        title: f.values.title.trim(), description: nn(f.values.description), category: f.values.category as MediaCategory,
        component_id: f.values.component_id || null, simulation_id: f.values.simulation_id || null, progress_update_id: f.values.progress_update_id || null,
      });
      toast.success('Dosya bilgileri güncellendi.');
      onClose();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} title="Dosya bilgilerini düzenle" busy={busy}
      footer={<><button className="btn-ghost" onClick={onClose} disabled={busy}>Vazgeç</button><button className="btn-primary" onClick={() => void save()} disabled={busy || !f.dirty}>{busy ? 'Kaydediliyor…' : 'Kaydet'}</button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput className="sm:col-span-2" label="Görünen başlık" required value={f.values.title} error={f.errors.title} onChange={(e) => f.set('title', e.target.value)} />
        <TextArea className="sm:col-span-2" label="Açıklama" value={f.values.description} error={f.errors.description} onChange={(e) => f.set('description', e.target.value)} />
        <Select label="Kategori" value={f.values.category} onChange={(e) => f.set('category', e.target.value)} options={options(mediaCategoryLabels)} />
        <Select label="İlgili bileşen" value={f.values.component_id} onChange={(e) => f.set('component_id', e.target.value)} placeholder="— Yok —" options={(comps.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
        <Select label="İlgili simülasyon" value={f.values.simulation_id} onChange={(e) => f.set('simulation_id', e.target.value)} placeholder="— Yok —" options={(sims.data ?? []).map((s) => ({ value: s.id, label: s.title }))} />
        <Select label="İlgili ilerleme kaydı" value={f.values.progress_update_id} onChange={(e) => f.set('progress_update_id', e.target.value)} placeholder="— Yok —" options={(prog.data ?? []).map((p) => ({ value: p.id, label: `${fmtDate(p.update_date)} · ${p.title}` }))} />
        <div className="text-[12.5px] text-ink-3 sm:col-span-2">Özgün dosya: <span className="mono">{media.original_file_name}</span> · {fmtBytes(media.file_size)} · {media.mime_type}</div>
      </div>
    </Modal>
  );
}

export default function MediaAdmin() {
  const { canEdit } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const media = useMediaList();
  const comps = useComponents();
  const [q, setQ] = useState('');
  const [cat, setCat] = useState('');
  const [vis, setVis] = useState('');
  const [comp, setComp] = useState('');
  const [order, setOrder] = useState<'desc' | 'asc'>('desc');
  const [page, setPage] = useState(0);
  const [showUpload, setShowUpload] = useState(false);
  const [editing, setEditing] = useState<Media | null>(null);
  const [viewing, setViewing] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const replaceInput = useRef<HTMLInputElement>(null);
  const replaceTarget = useRef<Media | null>(null);

  const list = useMemo(() => {
    let r = media.data ?? [];
    if (q.trim()) r = r.filter((m) => norm(`${m.title} ${m.original_file_name} ${m.description ?? ''}`).includes(norm(q.trim())));
    if (cat) r = r.filter((m) => m.category === cat);
    if (vis) r = r.filter((m) => m.bucket_name === vis);
    if (comp) r = r.filter((m) => m.component_id === comp);
    return [...r].sort((a, b) => (order === 'desc' ? b.created_at.localeCompare(a.created_at) : a.created_at.localeCompare(b.created_at)));
  }, [media.data, q, cat, vis, comp, order]);
  const pageItems = paginate(list, page, PAGE);
  const thumbs = useMediaUrls(pageItems.filter((m) => isImage(m.mime_type)), 400);
  const viewable = pageItems.filter((m) => isImage(m.mime_type) || isPdf(m.mime_type));
  const fullUrls = useMediaUrls(viewing !== null ? viewable : []);
  const compName = (id: string | null) => comps.data?.find((c) => c.id === id)?.name;

  const run = async (m: Media, fn: () => Promise<unknown>, ok: string) => {
    setBusyId(m.id);
    try { await fn(); toast.success(ok); invalidateMedia(); } catch (e) { toast.error(errorMessage(e)); } finally { setBusyId(null); }
  };
  const onDelete = async (m: Media) => {
    const yes = await confirm({ title: 'Dosya silinsin mi?', tone: 'danger', confirmLabel: 'Kalıcı olarak sil',
      message: <>“<b>{m.title}</b>” kalıcı olarak silinecek. Dosya bir teknik belgede veya satın alma makbuzu olarak kullanılıyorsa silme işlemi engellenir.</> });
    if (!yes) return;
    await run(m, async () => {
      const r = await deleteMedia(m);
      if (!r.storageRemoved) toast.info('Kayıt silindi ancak depodaki dosya kaldırılamadı; yönetici depoyu kontrol etmelidir.');
    }, 'Dosya silindi.');
  };
  const onToggleVisibility = async (m: Media) => {
    const toPublic = m.bucket_name !== PUBLIC_BUCKET;
    const yes = await confirm({
      title: toPublic ? 'Herkese açık yapılsın mı?' : 'Özel yapılsın mı?', confirmLabel: toPublic ? 'Herkese açık yap' : 'Özel yap',
      message: toPublic ? 'Dosya herkese açık depoya taşınacak ve genel sitede (ilgili sayfalarda) görüntülenebilecek.' : 'Dosya özel depoya taşınacak; genel sitede artık görünmeyecek ve eski bağlantısı çalışmayacak.',
    });
    if (yes) await run(m, () => setMediaBucket(m, toPublic ? PUBLIC_BUCKET : PRIVATE_BUCKET), toPublic ? 'Dosya herkese açık yapıldı.' : 'Dosya özel yapıldı.');
  };

  return (
    <AdminPage title="Medya Yönetimi" description="Simülasyon ekran görüntüleri, şemalar, breadboard fotoğrafları ve teknik dosyalar. Dosyalar Supabase Storage’da, bilgileri veritabanında tutulur."
      actions={canEdit && <button className="btn-primary" onClick={() => setShowUpload((s) => !s)}><Upload size={16} aria-hidden /> {showUpload ? 'Yükleme alanını gizle' : 'Dosya yükle'}</button>}>
      <ReadOnlyNotice />
      {showUpload && canEdit && (
        <div className="card mb-6 p-5"><h2 className="mb-3 text-[16px] font-semibold">Yeni dosyalar</h2>
          <UploadPanel components={comps.data ?? []} onUploaded={() => setShowUpload(false)} />
        </div>
      )}
      <input ref={replaceInput} type="file" className="sr-only" tabIndex={-1} aria-hidden onChange={(e) => {
        const file = e.target.files?.[0]; const m = replaceTarget.current; e.target.value = '';
        if (file && m) void run(m, () => replaceMediaFile(m, file), 'Dosya değiştirildi.');
      }} />

      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={q} onChange={(x) => { setQ(x); setPage(0); }} placeholder="Başlık, dosya adı veya açıklamada ara" />
        <select className="input w-auto" value={cat} onChange={(e) => { setCat(e.target.value); setPage(0); }} aria-label="Kategori"><option value="">Tüm kategoriler</option>{options(mediaCategoryLabels).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
        <select className="input w-auto" value={vis} onChange={(e) => { setVis(e.target.value); setPage(0); }} aria-label="Görünürlük"><option value="">Tüm görünürlükler</option><option value={PUBLIC_BUCKET}>Herkese açık</option><option value={PRIVATE_BUCKET}>Özel</option></select>
        <select className="input w-auto" value={comp} onChange={(e) => { setComp(e.target.value); setPage(0); }} aria-label="Bileşen"><option value="">Tüm bileşenler</option>{(comps.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <select className="input w-auto" value={order} onChange={(e) => setOrder(e.target.value as 'asc' | 'desc')} aria-label="Sıralama"><option value="desc">En yeni önce</option><option value="asc">En eski önce</option></select>
      </div>

      {media.error && <ErrorNotice error={media.error} onRetry={() => void media.refetch()} />}
      {!media.data && !media.error ? <SkeletonRows rows={6} /> : list.length === 0 ? (
        <EmptyState title={(media.data ?? []).length ? 'Süzgeçlere uyan dosya yok' : 'Henüz dosya yüklenmedi'}>
          {(media.data ?? []).length ? 'Farklı bir arama veya süzgeç deneyin.' : 'Simülasyon ekran görüntülerini ve fotoğrafları “Dosya yükle” düğmesiyle ekleyebilirsiniz.'}
        </EmptyState>
      ) : (
        <>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {pageItems.map((m) => {
              const vi = viewable.findIndex((x) => x.id === m.id);
              return (
                <li key={m.id} className={`card flex flex-col overflow-hidden ${busyId === m.id ? 'opacity-60' : ''}`}>
                  <button className="group relative block bg-brand-mist" onClick={() => vi >= 0 && setViewing(vi)} disabled={vi < 0} aria-label={`${m.title} görüntüle`}>
                    {isImage(m.mime_type) ? (thumbs.data?.[m.id] ? <img src={thumbs.data[m.id]} alt={m.title} loading="lazy" className="aspect-[4/3] w-full object-contain" /> : <span className="block aspect-[4/3] animate-pulse" />)
                      : <span className="flex aspect-[4/3] flex-col items-center justify-center gap-1 text-brand">{isPdf(m.mime_type) ? <FileText size={34} aria-hidden /> : <FileCode2 size={34} aria-hidden />}<span className="mono text-[12px] text-ink-3">.{m.file_name.split('.').pop()}</span></span>}
                    {vi >= 0 && <span className="absolute right-2 top-2 rounded bg-white/90 p-1 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden><Maximize2 size={14} /></span>}
                  </button>
                  <div className="flex flex-1 flex-col gap-1.5 p-3 text-[13px]">
                    <div className="flex items-start justify-between gap-2">
                      <b className="line-clamp-2 text-[14px] leading-snug">{m.title}</b>
                      {m.bucket_name === PUBLIC_BUCKET ? <Badge tone="success" dot={false}><Globe size={11} aria-hidden /> Açık</Badge> : <Badge tone="muted" dot={false}><Lock size={11} aria-hidden /> Özel</Badge>}
                    </div>
                    <span className="text-ink-3">{mediaCategoryLabels[m.category]}{compName(m.component_id) ? ` · ${compName(m.component_id)}` : ''}</span>
                    <span className="text-[12px] text-ink-3">{fmtDate(m.created_at)} · {fmtBytes(m.file_size)}</span>
                    <div className="mt-auto flex flex-wrap gap-1 border-t border-brand-line/60 pt-2">
                      <DownloadButton media={m} label="" className="btn-ghost px-2 py-1" />
                      {canEdit && <>
                        <button className="btn-ghost px-2 py-1" onClick={() => setEditing(m)} title="Düzenle" aria-label={`${m.title} düzenle`}><Pencil size={15} /></button>
                        <button className="btn-ghost px-2 py-1" onClick={() => { replaceTarget.current = m; replaceInput.current?.click(); }} title="Dosyayı değiştir" aria-label={`${m.title} dosyasını değiştir`}><RefreshCw size={15} /></button>
                        <button className="btn-ghost px-2 py-1" onClick={() => void onToggleVisibility(m)} title={m.bucket_name === PUBLIC_BUCKET ? 'Özel yap' : 'Herkese açık yap'} aria-label="Görünürlüğü değiştir">{m.bucket_name === PUBLIC_BUCKET ? <Lock size={15} /> : <Globe size={15} />}</button>
                        <button className="btn-ghost ml-auto px-2 py-1 text-red-700 hover:bg-red-50" onClick={() => void onDelete(m)} title="Sil" aria-label={`${m.title} sil`}><Trash2 size={15} /></button>
                      </>}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
          <Pager page={page} pageSize={PAGE} total={list.length} onPage={setPage} />
        </>
      )}
      {editing && <EditMedia media={editing} onClose={() => setEditing(null)} />}
      {viewing !== null && fullUrls.data && <Lightbox items={viewable} urls={fullUrls.data} index={viewing} onIndex={setViewing} onClose={() => setViewing(null)} />}
    </AdminPage>
  );
}
