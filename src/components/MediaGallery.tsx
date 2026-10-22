/** Görsel ızgarası, tam ekran görüntüleyici ve indirme bağlantıları (genel sayfalar ve panel için ortak). */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronLeft, ChevronRight, Download, FileText, FileCode2, X, Maximize2 } from 'lucide-react';
import type { Media } from '../services/entities';
import { mediaUrls, downloadUrl } from '../services/media';
import { useQuery } from '../lib/query';
import { isImage, isPdf } from '../lib/files';
import { fmtBytes, fmtDate } from '../lib/format';
import { mediaCategoryLabels } from '../lib/labels';
import { errorMessage } from '../lib/errors';

export function useMediaUrls(items: Media[], width?: number) {
  const key = items.length ? `media_files:urls:${width ?? 0}:${items.map((m) => `${m.id}@${m.updated_at}`).join(',')}` : null;
  return useQuery(key, () => mediaUrls(items, width ? { width } : undefined), { staleMs: 50 * 60_000 });
}

export function Lightbox({ items, urls, index, onClose, onIndex }: { items: Media[]; urls: Record<string, string>; index: number; onClose: () => void; onIndex: (i: number) => void }) {
  const m = items[index];
  const go = useCallback((d: number) => onIndex((index + d + items.length) % items.length), [index, items.length, onIndex]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowRight') go(1);
      if (e.key === 'ArrowLeft') go(-1);
    };
    document.addEventListener('keydown', onKey);
    const o = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = o; };
  }, [go, onClose]);
  if (!m) return null;
  return createPortal(
    <div className="fixed inset-0 z-[90] flex flex-col bg-[#120509]/95 text-white" role="dialog" aria-modal="true" aria-label={`Görsel: ${m.title}`}>
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          <div className="truncate font-semibold">{m.title}</div>
          <div className="text-[12px] text-white/60">{mediaCategoryLabels[m.category]} · {fmtDate(m.created_at)} · {index + 1}/{items.length}</div>
        </div>
        <div className="flex items-center gap-1">
          <DownloadButton media={m} className="rounded-md px-3 py-2 text-[13px] text-white hover:bg-white/10" />
          <button autoFocus className="rounded-md p-2 hover:bg-white/10" onClick={onClose} aria-label="Kapat"><X size={22} /></button>
        </div>
      </div>
      <div className="relative flex flex-1 items-center justify-center px-2 pb-4 sm:px-14" onClick={(e) => e.target === e.currentTarget && onClose()}>
        {isImage(m.mime_type) ? (
          <img src={urls[m.id]} alt={m.title} className="max-h-full max-w-full rounded object-contain" />
        ) : isPdf(m.mime_type) ? (
          <iframe title={m.title} src={urls[m.id]} className="h-full w-full max-w-5xl rounded bg-white" />
        ) : (
          <div className="text-center"><FileCode2 size={48} className="mx-auto text-white/70" aria-hidden /><div className="mt-2">{m.original_file_name}</div></div>
        )}
        {items.length > 1 && <>
          <button className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-white/10 p-2.5 hover:bg-white/20" onClick={() => go(-1)} aria-label="Önceki"><ChevronLeft size={24} /></button>
          <button className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-white/10 p-2.5 hover:bg-white/20" onClick={() => go(1)} aria-label="Sonraki"><ChevronRight size={24} /></button>
        </>}
      </div>
      {m.description && <div className="mx-auto max-w-3xl px-4 pb-5 text-center text-[14px] text-white/80">{m.description}</div>}
    </div>,
    document.body,
  );
}

export function DownloadButton({ media, className = 'btn-ghost px-2 py-1 text-[13px]', label = 'İndir' }: { media: Media; className?: string; label?: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <button className={className} disabled={busy} title={err ?? undefined}
      onClick={async () => {
        setBusy(true); setErr(null);
        try { window.location.assign(await downloadUrl(media)); }
        catch (e) { setErr(errorMessage(e)); alertFallback(errorMessage(e)); }
        finally { setBusy(false); }
      }}>
      <Download size={15} aria-hidden /> {busy ? 'Hazırlanıyor…' : label}
    </button>
  );
}
const alertFallback = (m: string) => console.warn('[indirme]', m);

/** Görseller ızgarada, diğer dosyalar indirilebilir liste olarak gösterilir. */
export function MediaGallery({ items, empty, columns = 3, showMeta = true }: { items: Media[]; empty?: React.ReactNode; columns?: 2 | 3 | 4; showMeta?: boolean }) {
  const images = useMemo(() => items.filter((m) => isImage(m.mime_type)), [items]);
  const files = useMemo(() => items.filter((m) => !isImage(m.mime_type)), [items]);
  const thumbs = useMediaUrls(images, 640);
  const full = useMediaUrls(images);
  const [open, setOpen] = useState<number | null>(null);
  if (!items.length) return <>{empty ?? null}</>;
  const cols = { 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-2 lg:grid-cols-3', 4: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4' }[columns];
  return (
    <div className="space-y-4">
      {images.length > 0 && (
        <div className={`grid gap-3 ${cols}`}>
          {images.map((m, i) => (
            <figure key={m.id} className="card group overflow-hidden">
              <button className="relative block w-full bg-brand-mist" onClick={() => setOpen(i)} aria-label={`${m.title} — tam ekran görüntüle`}>
                {thumbs.data?.[m.id]
                  ? <img src={thumbs.data[m.id]} alt={m.title} loading="lazy" decoding="async" className="aspect-[4/3] w-full object-contain transition-transform duration-300 group-hover:scale-[1.02]" />
                  : <span className="block aspect-[4/3] w-full animate-pulse" />}
                <span className="absolute right-2 top-2 rounded-md bg-white/90 p-1.5 text-ink opacity-0 transition-opacity group-hover:opacity-100" aria-hidden><Maximize2 size={14} /></span>
              </button>
              {showMeta && (
                <figcaption className="border-t border-brand-line p-3 text-[13px]">
                  <b className="block truncate text-ink">{m.title}</b>
                  <span className="text-ink-3">{mediaCategoryLabels[m.category]} · {fmtDate(m.created_at)}</span>
                  {m.description && <p className="mt-1 line-clamp-2 text-ink-2">{m.description}</p>}
                </figcaption>
              )}
            </figure>
          ))}
        </div>
      )}
      {files.length > 0 && (
        <ul className="divide-y divide-brand-line/60 rounded-[10px] border border-brand-line">
          {files.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-[14px]">
              {isPdf(m.mime_type) ? <FileText size={18} className="text-brand" aria-hidden /> : <FileCode2 size={18} className="text-brand" aria-hidden />}
              <span className="min-w-0 flex-1"><b className="block truncate">{m.title}</b><span className="text-[12px] text-ink-3">{m.original_file_name} · {fmtBytes(m.file_size)}</span></span>
              <DownloadButton media={m} />
            </li>
          ))}
        </ul>
      )}
      {open !== null && full.data && <Lightbox items={images} urls={full.data} index={open} onIndex={setOpen} onClose={() => setOpen(null)} />}
    </div>
  );
}
