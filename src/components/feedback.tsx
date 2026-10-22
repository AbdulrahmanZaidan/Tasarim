/** Bildirimler (toast), onay iletişim kutusu ve modal — sitenin tasarım diliyle. */
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, AlertTriangle, X, Info } from 'lucide-react';

/* ---------------- Toast ---------------- */
type ToastKind = 'success' | 'error' | 'info';
interface Toast { id: number; kind: ToastKind; text: string }
interface ToastApi { success: (t: string) => void; error: (t: string) => void; info: (t: string) => void }
const ToastCtx = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((kind: ToastKind, text: string) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-3), { id, kind, text }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), kind === 'error' ? 8000 : 4000);
  }, []);
  const api = useRef<ToastApi>({ success: (t) => push('success', t), error: (t) => push('error', t), info: (t) => push('info', t) });
  return (
    <ToastCtx.Provider value={api.current}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-4 z-[70] flex flex-col items-center gap-2 px-4 sm:items-end sm:pr-6" aria-live="polite" role="status">
        {items.map((t) => {
          const Icon = t.kind === 'success' ? CheckCircle2 : t.kind === 'error' ? AlertTriangle : Info;
          return (
            <div key={t.id} className={`pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-[10px] border bg-white px-4 py-3 text-[14px] shadow-[0_8px_24px_rgba(28,27,31,0.14)] animate-rise ${t.kind === 'error' ? 'border-red-300' : t.kind === 'success' ? 'border-emerald-300' : 'border-brand-line'}`}>
              <Icon size={18} className={`mt-0.5 shrink-0 ${t.kind === 'error' ? 'text-red-700' : t.kind === 'success' ? 'text-emerald-700' : 'text-brand'}`} aria-hidden />
              <span className="flex-1 text-ink-2">{t.text}</span>
              <button className="text-ink-3 hover:text-ink" onClick={() => setItems((x) => x.filter((y) => y.id !== t.id))} aria-label="Bildirimi kapat"><X size={16} /></button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}
export function useToast() {
  const v = useContext(ToastCtx);
  if (!v) throw new Error('useToast, ToastProvider içinde kullanılmalıdır.');
  return v;
}

/* ---------------- Modal ---------------- */
export function Modal({ open, onClose, title, children, footer, size = 'md', busy = false }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; size?: 'sm' | 'md' | 'lg' | 'xl'; busy?: boolean;
}) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const lastFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!open) return;
    lastFocus.current = document.activeElement as HTMLElement;
    const t = setTimeout(() => {
      const first = panel.current?.querySelector<HTMLElement>('[data-autofocus], input:not([type=hidden]), select, textarea, button:not([data-close])');
      (first ?? panel.current)?.focus();
    }, 20);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onClose();
      if (e.key === 'Tab' && panel.current) {
        const f = [...panel.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')];
        if (!f.length) return;
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f.at(-1)!.focus(); }
        else if (!e.shiftKey && document.activeElement === f.at(-1)) { e.preventDefault(); f[0].focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { clearTimeout(t); document.removeEventListener('keydown', onKey); document.body.style.overflow = prevOverflow; lastFocus.current?.focus?.(); };
  }, [open, onClose, busy]);
  if (!open) return null;
  const w = { sm: 'max-w-md', md: 'max-w-2xl', lg: 'max-w-4xl', xl: 'max-w-6xl' }[size];
  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-ink/40 p-0 sm:items-center sm:p-4" onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        className={`flex max-h-[94vh] w-full ${w} flex-col overflow-hidden rounded-t-[14px] bg-white shadow-2xl animate-rise sm:rounded-[14px]`}>
        <div className="flex items-center justify-between gap-3 border-b border-brand-line px-5 py-3.5">
          <h2 id={titleId} className="text-[17px] font-semibold text-ink">{title}</h2>
          <button data-close className="btn-ghost -mr-2 p-1.5" onClick={onClose} disabled={busy} aria-label="Kapat"><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-brand-line bg-brand-mist/50 px-5 py-3">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

/* ---------------- Onay ---------------- */
interface ConfirmOpts { title: string; message: ReactNode; confirmLabel?: string; cancelLabel?: string; tone?: 'danger' | 'default' }
type ConfirmFn = (o: ConfirmOpts) => Promise<boolean>;
const ConfirmCtx = createContext<ConfirmFn | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<(ConfirmOpts & { resolve: (v: boolean) => void }) | null>(null);
  const confirm = useCallback<ConfirmFn>((o) => new Promise((resolve) => setState({ ...o, resolve })), []);
  const close = (v: boolean) => { state?.resolve(v); setState(null); };
  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      <Modal open={!!state} onClose={() => close(false)} title={state?.title ?? ''} size="sm"
        footer={<>
          <button className="btn-ghost" onClick={() => close(false)}>{state?.cancelLabel ?? 'Vazgeç'}</button>
          <button data-autofocus className={state?.tone === 'danger' ? 'btn bg-red-700 text-white hover:bg-red-800' : 'btn-primary'} onClick={() => close(true)}>{state?.confirmLabel ?? 'Onayla'}</button>
        </>}>
        <div className="text-[14px] leading-6 text-ink-2">{state?.message}</div>
      </Modal>
    </ConfirmCtx.Provider>
  );
}
export function useConfirm() {
  const v = useContext(ConfirmCtx);
  if (!v) throw new Error('useConfirm, ConfirmProvider içinde kullanılmalıdır.');
  return v;
}

/* ---------------- Yükleniyor / boş / hata ---------------- */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-brand-mist ${className}`} aria-hidden />;
}
export function SkeletonRows({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Yükleniyor">
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-10 w-full" />)}
    </div>
  );
}
export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-[10px] border-2 border-dashed border-brand-line bg-brand-mist/40 px-6 py-10 text-center">
      {icon && <div className="mx-auto mb-2 flex justify-center text-brand">{icon}</div>}
      <div className="text-[16px] font-semibold text-ink">{title}</div>
      {children && <div className="mx-auto mt-1 max-w-xl text-[14px] text-ink-3">{children}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}
export function ErrorNotice({ error, onRetry, title = 'Veriler yüklenemedi' }: { error: { message: string }; onRetry?: () => void; title?: string }) {
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-[10px] border border-red-200 bg-red-50/70 p-4 text-[14px] text-ink-2 sm:flex-row sm:items-center">
      <AlertTriangle size={18} className="shrink-0 text-red-700" aria-hidden />
      <div className="flex-1"><b className="text-ink">{title}.</b> {error.message}</div>
      {onRetry && <button className="btn-outline py-1.5" onClick={onRetry}>Tekrar dene</button>}
    </div>
  );
}
