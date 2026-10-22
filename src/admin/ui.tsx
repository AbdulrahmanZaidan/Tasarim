/** Yönetim paneline özgü ortak parçalar (sayfa başlığı, tablolar, dosya bırakma alanı, yetki uyarısı). */
import { useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, UploadCloud, Lock, Search } from 'lucide-react';
import { useAuth } from '../auth/AuthProvider';

export function AdminPage({ title, description, actions, children, crumb }: { title: string; description?: ReactNode; actions?: ReactNode; children: ReactNode; crumb?: string }) {
  return (
    <div className="animate-rise">
      <nav aria-label="Sayfa konumu" className="mb-3 text-[13px] text-ink-3">
        <ol className="flex flex-wrap items-center gap-1">
          <li><Link to="/admin/dashboard" className="text-ink-3 hover:text-brand">Yönetim</Link></li>
          <li className="flex items-center gap-1"><ChevronRight size={13} className="text-brand-line" aria-hidden /><span aria-current="page" className="font-medium text-ink">{crumb ?? title}</span></li>
        </ol>
      </nav>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[26px] font-bold leading-tight text-ink sm:text-[30px]">{title}</h1>
          {description && <p className="mt-1 max-w-3xl text-[14.5px] text-ink-3">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
      <div className="rule mb-6 mt-4" />
      {children}
    </div>
  );
}

/** Yetkisi olmayan kullanıcıya düzenleme denetimlerinin neden gizlendiğini açıklar. */
export function ReadOnlyNotice({ need = 'edit' }: { need?: 'edit' | 'admin' }) {
  const { canEdit, isAdmin } = useAuth();
  if ((need === 'edit' && canEdit) || (need === 'admin' && isAdmin)) return null;
  return (
    <div className="mb-4 flex items-center gap-2 rounded-[10px] border border-brand-line bg-brand-soft/60 px-4 py-2.5 text-[13.5px] text-ink-2">
      <Lock size={15} className="text-brand" aria-hidden />
      {need === 'admin' ? 'Bu bölümü yalnızca yöneticiler değiştirebilir; görüntüleme kipindesiniz.' : 'Hesabınız izleyici (salt okunur) rolündedir; kayıt ekleyemez veya değiştiremezsiniz.'}
    </div>
  );
}

export function SearchBox({ value, onChange, placeholder = 'Ara…', label = 'Ara' }: { value: string; onChange: (v: string) => void; placeholder?: string; label?: string }) {
  return (
    <div className="relative min-w-[200px] flex-1">
      <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" aria-hidden />
      <input type="search" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={label} className="input pl-9" />
    </div>
  );
}

export function Table({ children, minWidth = 760 }: { children: ReactNode; minWidth?: number }) {
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-[13.5px]" style={{ minWidth }}>{children}</table>
    </div>
  );
}
export function Th({ children, className = '' }: { children?: ReactNode; className?: string }) {
  return <th scope="col" className={`whitespace-nowrap border-b-2 border-brand bg-brand-mist px-3 py-2.5 text-left text-[11.5px] font-semibold uppercase tracking-[0.06em] text-brand ${className}`}>{children}</th>;
}
export function Td({ children, className = '' }: { children?: ReactNode; className?: string }) {
  return <td className={`border-b border-brand-line/50 px-3 py-2.5 align-top ${className}`}>{children}</td>;
}

/** Sürükle-bırak ve dosya seçici; birden çok dosya kabul eder. */
export function Dropzone({ onFiles, accept, multiple = true, hint, disabled }: { onFiles: (f: File[]) => void; accept?: string; multiple?: boolean; hint?: ReactNode; disabled?: boolean }) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); if (!disabled && e.dataTransfer.files.length) onFiles([...e.dataTransfer.files]); }}
      className={`flex flex-col items-center justify-center gap-2 rounded-[10px] border-2 border-dashed px-6 py-8 text-center transition-colors ${over ? 'border-brand bg-brand-soft' : 'border-brand-line bg-brand-mist/40'} ${disabled ? 'opacity-50' : ''}`}>
      <UploadCloud size={30} className="text-brand" aria-hidden />
      <div className="text-[15px] font-semibold text-ink">Dosyaları buraya sürükleyip bırakın</div>
      <div className="text-[13px] text-ink-3">veya</div>
      <button type="button" className="btn-outline py-1.5" disabled={disabled} onClick={() => input.current?.click()}>Dosya seç</button>
      <input ref={input} type="file" className="sr-only" accept={accept} multiple={multiple} disabled={disabled} tabIndex={-1} aria-hidden
        onChange={(e) => { if (e.target.files?.length) onFiles([...e.target.files]); e.target.value = ''; }} />
      {hint && <div className="mt-1 max-w-lg text-[12px] text-ink-3">{hint}</div>}
    </div>
  );
}

export function ProgressLine({ value, error }: { value: number; error?: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-brand-mist" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}>
      <div className={`h-full rounded-full transition-[width] duration-200 ${error ? 'bg-red-600' : value === 100 ? 'bg-emerald-600' : 'bg-brand'}`} style={{ width: `${error ? 100 : value}%` }} />
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  return (
    <div className="mt-3 flex items-center justify-between text-[13px] text-ink-3">
      <span>{total} kayıttan {page * pageSize + 1}–{Math.min(total, (page + 1) * pageSize)}</span>
      <div className="flex gap-1">
        <button className="btn-outline px-3 py-1" disabled={page === 0} onClick={() => onPage(page - 1)}>Önceki</button>
        <span className="px-2 py-1">{page + 1} / {pages}</span>
        <button className="btn-outline px-3 py-1" disabled={page >= pages - 1} onClick={() => onPage(page + 1)}>Sonraki</button>
      </div>
    </div>
  );
}

/** Basit sayfalama yardımcıları */
export function paginate<T>(rows: T[], page: number, size: number) {
  return rows.slice(page * size, (page + 1) * size);
}
