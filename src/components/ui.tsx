import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronLeft, ChevronRight, Info, AlertTriangle, Home } from 'lucide-react';
import { phaseStatusLabels, phaseTone, toneClass, type PhaseStatus, type Tone } from '../lib/labels';
import { useCore } from '../data/public';

export function StatusBadge({ status, size = 'sm' }: { status: PhaseStatus; size?: 'sm' | 'md' }) {
  const dot: Record<PhaseStatus, string> = {
    completed: 'bg-emerald-600', in_progress: 'bg-amber-500 animate-pulse', planned: 'bg-brand', not_started: 'bg-ink-3/50', blocked: 'bg-red-600',
  };
  return (
    <span className={`chip ${toneClass[phaseTone[status]]} ${size === 'md' ? 'px-3 py-1 text-[13px]' : ''}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot[status]}`} aria-hidden />
      {phaseStatusLabels[status]}
    </span>
  );
}

/** Genel amaçlı durum rozeti */
export function Badge({ tone, children, dot = true }: { tone: Tone; children: ReactNode; dot?: boolean }) {
  const dots: Record<Tone, string> = { success: 'bg-emerald-600', warning: 'bg-amber-500', danger: 'bg-red-600', brand: 'bg-brand', info: 'bg-sky-600', muted: 'bg-ink-3/50' };
  return (
    <span className={`chip whitespace-nowrap ${toneClass[tone]}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dots[tone]}`} aria-hidden />}
      {children}
    </span>
  );
}

export interface Crumb { label: string; to?: string }
export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Sayfa konumu" className="mb-5 text-[13px] text-ink-3">
      <ol className="flex flex-wrap items-center gap-1">
        <li><Link to="/" className="inline-flex items-center gap-1 text-ink-3 hover:text-brand"><Home size={13} aria-hidden /> Ana Sayfa</Link></li>
        {items.map((c, i) => (
          <li key={i} className="flex items-center gap-1">
            <ChevronRight size={13} aria-hidden className="text-brand-line" />
            {c.to ? <Link to={c.to} className="text-ink-3 hover:text-brand">{c.label}</Link> : <span aria-current="page" className="font-medium text-ink">{c.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function PageHeader({ eyebrow, title, subtitle, crumbs, right }: { eyebrow: string; title: string; subtitle?: ReactNode; crumbs?: Crumb[]; right?: ReactNode }) {
  return (
    <header className="pt-8 sm:pt-10">
      <div className="container-x">
        {crumbs && <Breadcrumbs items={crumbs} />}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between animate-rise">
          <div className="max-w-3xl">
            <div className="eyebrow">{eyebrow}</div>
            <h1 className="mt-2 text-[30px] sm:text-[38px] font-bold leading-[1.15] text-ink">{title}</h1>
            {subtitle && <p className="lead mt-3">{subtitle}</p>}
          </div>
          {right && <div className="shrink-0 self-start sm:self-end">{right}</div>}
        </div>
        <div className="rule mt-6" />
      </div>
    </header>
  );
}

export function Section({ id, eyebrow, title, intro, children, className = '' }: { id?: string; eyebrow?: string; title?: string; intro?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section id={id} className={`scroll-mt-24 py-10 sm:py-12 ${className}`}>
      <div className="container-x">
        {(eyebrow || title) && (
          <div className="mb-6 max-w-3xl">
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            {title && <h2 className="h2 mt-1.5">{title}</h2>}
            {intro && <div className="prose-body mt-2.5">{intro}</div>}
          </div>
        )}
        {children}
      </div>
    </section>
  );
}

export function Figure({ n, caption, kind, children }: { n: string; caption: string; kind: 'kavramsal' | 'simulasyon' | 'referans'; children: ReactNode }) {
  const kinds = {
    kavramsal: 'Kavramsal çizim — doğrulanmış elektrik şeması değildir',
    simulasyon: 'Web tabanlı eğitsel simülasyon — donanım doğrulaması değildir',
    referans: 'Referans bilgi',
  } as const;
  return (
    <figure className="card overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-brand-line bg-brand-mist px-4 py-2 text-[12px] text-ink-3">
        <span className="font-medium">{kinds[kind]}</span>
      </div>
      <div className="p-3 sm:p-5">{children}</div>
      <figcaption className="border-t border-brand-line px-4 py-2.5 text-[13px] text-ink-2">
        <b className="text-brand">Şekil {n}.</b> {caption}
      </figcaption>
    </figure>
  );
}

export function Callout({ tone = 'info', title, children }: { tone?: 'info' | 'warn'; title?: string; children: ReactNode }) {
  const Icon = tone === 'warn' ? AlertTriangle : Info;
  return (
    <div className={`flex gap-3 rounded-[10px] border p-4 text-[14px] leading-6 ${tone === 'warn' ? 'border-amber-300 bg-amber-50/60 text-ink-2' : 'border-brand-line bg-brand-soft/70 text-ink-2'}`}>
      <Icon size={18} className={`mt-0.5 shrink-0 ${tone === 'warn' ? 'text-amber-700' : 'text-brand'}`} aria-hidden />
      <div>{title && <div className="mb-0.5 font-semibold text-ink">{title}</div>}{children}</div>
    </div>
  );
}

export function Disclosure({ title, badge, children, defaultOpen = false, id, open: openProp, onToggle }: { title: ReactNode; badge?: ReactNode; children: ReactNode; defaultOpen?: boolean; id?: string; open?: boolean; onToggle?: (v: boolean) => void }) {
  const [inner, setInner] = useState(defaultOpen);
  const open = openProp ?? inner;
  const setOpen = (v: boolean) => (onToggle ? onToggle(v) : setInner(v));
  return (
    <div id={id} className={`card scroll-mt-24 transition-shadow ${open ? 'shadow-[0_2px_14px_rgba(158,27,50,0.08)]' : ''}`}>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 rounded-[10px] px-4 py-3.5 text-left hover:bg-brand-mist/60 sm:px-5">
        <span className="flex min-w-0 flex-wrap items-center gap-2 text-[16px] font-semibold text-ink">{title}{badge}</span>
        <ChevronDown size={18} className={`shrink-0 text-brand transition-transform duration-200 ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>
      <div className={`grid transition-all duration-300 ${open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}>
        <div className="overflow-hidden"><div className="border-t border-brand-line px-4 py-5 sm:px-5">{children}</div></div>
      </div>
    </div>
  );
}

export function StageNav({ current }: { current: string }) {
  const phases = useCore().data.phases;
  const i = phases.findIndex((s) => s.slug === current);
  const prev = i > 0 ? phases[i - 1] : undefined;
  const next = i >= 0 ? phases[i + 1] : undefined;
  return (
    <nav aria-label="Aşamalar arası gezinme" className="container-x pb-14 pt-4">
      <div className="rule mb-6 h-px bg-brand-line" />
      <div className="grid gap-3 sm:grid-cols-3">
        <div>{prev && (
          <Link to={prev.path} className="card group flex items-center gap-3 p-4 hover:border-brand">
            <ChevronLeft className="text-brand transition-transform group-hover:-translate-x-0.5" size={18} aria-hidden />
            <span><span className="block text-[12px] text-ink-3">Önceki aşama · {prev.number}</span><span className="font-semibold text-ink">{prev.title}</span></span>
          </Link>)}
        </div>
        <Link to="/proje" className="btn-outline self-center justify-self-center">Proje Planına Dön</Link>
        <div>{next && (
          <Link to={next.path} className="card group flex items-center justify-end gap-3 p-4 text-right hover:border-brand">
            <span><span className="block text-[12px] text-ink-3">Sonraki aşama · {next.number}</span><span className="font-semibold text-ink">{next.title}</span></span>
            <ChevronRight className="text-brand transition-transform group-hover:translate-x-0.5" size={18} aria-hidden />
          </Link>)}
        </div>
      </div>
    </nav>
  );
}

/** 8 bitlik değeri LED dizisi olarak gösterir. */
export function Bits({ value, width = 8, color = 'red', label, size = 14 }: { value: number | null; width?: number; color?: 'red' | 'green' | 'blue' | 'yellow'; label?: string; size?: number }) {
  const on = { red: 'bg-red-600 shadow-[0_0_6px_rgba(220,38,38,.7)]', green: 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,.7)]', blue: 'bg-blue-600 shadow-[0_0_6px_rgba(37,99,235,.7)]', yellow: 'bg-amber-400 shadow-[0_0_6px_rgba(245,158,11,.7)]' }[color];
  return (
    <div className="flex items-center gap-[5px]" role="img" aria-label={`${label ?? 'Değer'}: ${value === null ? 'tanımsız' : value.toString(2).padStart(width, '0')}`}>
      {Array.from({ length: width }, (_, i) => {
        const bit = value === null ? null : (value >> (width - 1 - i)) & 1;
        return <span key={i} style={{ width: size, height: size }} className={`rounded-full border border-black/10 transition-colors duration-200 ${bit ? on : value === null ? 'bg-neutral-100' : 'bg-neutral-200'}`} />;
      })}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="card-soft p-4">
      <div className="text-[12px] font-semibold uppercase tracking-[0.1em] text-brand">{label}</div>
      <div className="mt-1.5 text-[22px] font-bold text-ink mono">{value}</div>
      {hint && <div className="mt-1 text-[12px] leading-5 text-ink-3">{hint}</div>}
    </div>
  );
}

export function ProgressBar({ value, label }: { value: number | null; label: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-[12px] text-ink-3"><span>{label}</span><span className="mono">{value === null ? 'Belirtilmedi' : `%${value}`}</span></div>
      <div className="h-2 overflow-hidden rounded-full bg-brand-mist" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value ?? undefined} aria-label={label}>
        <div className="h-full rounded-full bg-brand transition-[width] duration-700" style={{ width: `${value ?? 0}%` }} />
      </div>
    </div>
  );
}
