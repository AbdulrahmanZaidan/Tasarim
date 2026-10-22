/** Çoklu dosya yükleme kuyruğu: doğrulama, dosya başına ilerleme, hata gösterimi. */
import { useState } from 'react';
import { CheckCircle2, AlertTriangle, X, Loader2 } from 'lucide-react';
import { Dropzone, ProgressLine } from './ui';
import { Select } from '../components/form';
import { useToast } from '../components/feedback';
import { uploadMedia, invalidateMedia } from '../services/media';
import { checkFile, allowedExt, sizeLimits, PUBLIC_BUCKET, PRIVATE_BUCKET, type Bucket } from '../lib/files';
import { mediaCategoryLabels, options, type MediaCategory } from '../lib/labels';
import { fmtBytes } from '../lib/format';
import { errorMessage } from '../lib/errors';
import type { Media } from '../services/entities';

interface Item { id: string; file: File; progress: number; status: 'waiting' | 'uploading' | 'done' | 'error'; error?: string }

export interface UploadDefaults {
  category?: MediaCategory;
  bucket?: Bucket;
  component_id?: string | null;
  simulation_id?: string | null;
  progress_update_id?: string | null;
}

export default function UploadPanel({ defaults = {}, components, lockCategory = false, onUploaded, disabled }: {
  defaults?: UploadDefaults; components?: { id: string; name: string }[]; lockCategory?: boolean; onUploaded?: (m: Media[]) => void; disabled?: boolean;
}) {
  const toast = useToast();
  const [category, setCategory] = useState<MediaCategory>(defaults.category ?? 'simulation_screenshot');
  const [bucket, setBucket] = useState<Bucket>(defaults.bucket ?? PRIVATE_BUCKET);
  const [componentId, setComponentId] = useState<string>(defaults.component_id ?? '');
  const [items, setItems] = useState<Item[]>([]);
  const [busy, setBusy] = useState(false);
  const patch = (id: string, p: Partial<Item>) => setItems((xs) => xs.map((x) => (x.id === id ? { ...x, ...p } : x)));

  const add = (files: File[]) => {
    setItems((xs) => [...xs, ...files.map((file) => {
      const c = checkFile(file, bucket);
      return { id: `${file.name}-${file.size}-${Math.random()}`, file, progress: 0, status: c.ok ? 'waiting' as const : 'error' as const, error: c.error };
    })]);
  };

  const start = async () => {
    setBusy(true);
    const done: Media[] = [];
    // Sırayla yükle: bant genişliği paylaşımı ve tutarlı ilerleme göstergesi için
    for (const it of items) {
      if (it.status !== 'waiting') continue;
      const c = checkFile(it.file, bucket);
      if (!c.ok) { patch(it.id, { status: 'error', error: c.error }); continue; }
      patch(it.id, { status: 'uploading', progress: 0 });
      try {
        const m = await uploadMedia(it.file, {
          bucket, category, component_id: componentId || null,
          simulation_id: defaults.simulation_id ?? null, progress_update_id: defaults.progress_update_id ?? null,
        }, (p) => patch(it.id, { progress: p }));
        done.push(m);
        patch(it.id, { status: 'done', progress: 100 });
      } catch (e) {
        patch(it.id, { status: 'error', error: errorMessage(e) });
      }
    }
    setBusy(false);
    invalidateMedia();
    if (done.length) { toast.success(`${done.length} dosya yüklendi.`); onUploaded?.(done); }
  };
  const waiting = items.filter((i) => i.status === 'waiting').length;

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Select label="Kategori" value={category} disabled={lockCategory || busy} onChange={(e) => setCategory(e.target.value as MediaCategory)} options={options(mediaCategoryLabels)} />
        <Select label="Görünürlük" value={bucket} disabled={busy} onChange={(e) => { const b = e.target.value as Bucket; setBucket(b); setItems((xs) => xs.map((x) => x.status === 'waiting' || x.status === 'error' ? (() => { const c = checkFile(x.file, b); return { ...x, status: c.ok ? 'waiting' as const : 'error' as const, error: c.error }; })() : x)); }}
          options={[{ value: PRIVATE_BUCKET, label: 'Özel (yalnızca ekip)' }, { value: PUBLIC_BUCKET, label: 'Herkese açık (yayımlanır)' }]}
          hint={bucket === PUBLIC_BUCKET ? 'Dosya bağlantıyı bilen herkes tarafından görüntülenebilir.' : 'Yalnızca giriş yapmış ekip üyeleri görebilir.'} />
        {components && <Select label="İlgili bileşen" value={componentId} disabled={busy} onChange={(e) => setComponentId(e.target.value)} placeholder="— Yok —" options={components.map((c) => ({ value: c.id, label: c.name }))} />}
      </div>
      <Dropzone onFiles={add} disabled={disabled || busy}
        hint={<>İzin verilen uzantılar: {allowedExt[bucket].join(', ')} · En fazla {fmtBytes(sizeLimits[bucket])}. Özgün dosya adı korunur, depoda benzersiz bir adla saklanır.</>} />
      {items.length > 0 && (
        <ul className="divide-y divide-brand-line/60 rounded-[10px] border border-brand-line" aria-live="polite">
          {items.map((it) => (
            <li key={it.id} className="space-y-1.5 px-3 py-2.5 text-[13.5px]">
              <div className="flex items-center gap-2">
                {it.status === 'done' ? <CheckCircle2 size={16} className="text-emerald-600" aria-label="yüklendi" />
                  : it.status === 'error' ? <AlertTriangle size={16} className="text-red-600" aria-label="hata" />
                  : it.status === 'uploading' ? <Loader2 size={16} className="animate-spin text-brand" aria-label="yükleniyor" /> : <span className="h-4 w-4 rounded-full border-2 border-brand-line" aria-label="sırada" />}
                <span className="min-w-0 flex-1 truncate">{it.file.name}</span>
                <span className="mono text-[12px] text-ink-3">{fmtBytes(it.file.size)}</span>
                {it.status !== 'uploading' && <button className="text-ink-3 hover:text-ink" onClick={() => setItems((xs) => xs.filter((x) => x.id !== it.id))} aria-label={`${it.file.name} listeden kaldır`}><X size={15} /></button>}
              </div>
              <ProgressLine value={it.progress} error={it.status === 'error' ? it.error : undefined} />
              {it.error && <div className="text-[12px] text-red-700">{it.error}</div>}
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        {items.some((i) => i.status === 'done' || i.status === 'error') && !busy && <button className="btn-ghost" onClick={() => setItems((xs) => xs.filter((x) => x.status === 'waiting'))}>Tamamlananları temizle</button>}
        <button className="btn-primary" disabled={busy || waiting === 0 || disabled} onClick={() => void start()}>{busy ? 'Yükleniyor…' : `Yükle (${waiting})`}</button>
      </div>
    </div>
  );
}
