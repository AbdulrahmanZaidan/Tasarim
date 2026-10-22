import { Link } from 'react-router-dom';
import { CircuitBoard, Activity, GitBranch, Boxes, Wrench, ArrowRight, Lock, ClipboardList, type LucideIcon } from 'lucide-react';
import { useCore, type PhaseVM } from '../data/public';
import { StatusBadge } from './ui';
import { Skeleton } from './feedback';

export const stageIcons: Record<string, LucideIcon> = {
  architecture: CircuitBoard, simulation: Activity, github: GitBranch, materials: Boxes, tasarim2: Wrench,
};
export const iconFor = (slug: string): LucideIcon => stageIcons[slug] ?? ClipboardList;

function Arrow() {
  return (
    <svg width="8" height="40" viewBox="0 0 8 40" className="mx-auto block overflow-visible" aria-hidden>
      <path d="M4 0 L4 34" stroke="#9E1B32" strokeWidth="2" strokeLinecap="round" />
      <path d="M0 33 L4 40 L8 33 Z" fill="#9E1B32" />
    </svg>
  );
}

/** Ekteki dönem planındaki dikey, numaralı ve oklarla bağlı zaman çizelgesinin etkileşimli sürümü. */
export default function Timeline({ compact = false }: { compact?: boolean }) {
  const { data, loading } = useCore();
  if (loading) {
    return <div className="space-y-6" aria-busy="true">{[0, 1, 2, 3].map((i) => <div key={i} className="grid gap-3 md:grid-cols-[260px_1fr] md:gap-8"><Skeleton className="h-24" /><Skeleton className="h-24" /></div>)}</div>;
  }
  const t1 = data.phases.filter((s) => s.semesterKey === 'tasarim_1');
  const t2 = data.phases.filter((s) => s.semesterKey === 'tasarim_2');
  const locked = !data.settings.tasarimIIActive;
  return (
    <ol className="relative">
      {t1.map((s, i) => <Row key={s.id} s={s} i={i} compact={compact} arrow={i < t1.length - 1 || t2.length > 0} />)}
      {t2.length > 0 && (
        <li aria-hidden className="grid grid-cols-1 md:grid-cols-[260px_1fr] md:gap-8">
          <div />
          <div className="-mt-6 mb-4 hidden items-center md:flex">
            <span className="eyebrow flex items-center gap-3 text-ink-3"><span className="h-px w-10 bg-brand-line" />2. DÖNEM · TASARIM II<span className="h-px w-10 bg-brand-line" /></span>
          </div>
        </li>
      )}
      {t2.map((s, i) => <Row key={s.id} s={s} i={t1.length + i} compact={compact} final locked={locked} arrow={i < t2.length - 1} />)}
    </ol>
  );
}

function Row({ s, i, compact, final = false, locked = false, arrow }: { s: PhaseVM; i: number; compact: boolean; final?: boolean; locked?: boolean; arrow: boolean }) {
  const Icon = iconFor(s.slug);
  const done = s.tasks.filter((t) => t.status === 'completed').length;
  return (
    <li id={`asama-${s.slug}`} className="grid scroll-mt-24 grid-cols-1 gap-3 md:grid-cols-[260px_1fr] md:gap-8" style={{ animation: `rise .5s ease-out ${i * 80}ms both` }}>
      <div>
        <Link to={s.path}
          className={`group relative flex min-h-[96px] items-center justify-center rounded-[10px] px-4 py-4 text-center transition-all duration-200 hover:-translate-y-0.5 ${final ? 'bg-brand text-white hover:bg-brand-dark hover:text-white shadow-[0_6px_18px_rgba(158,27,50,0.25)]' : 'border border-brand-line bg-brand-soft text-ink hover:border-brand hover:text-ink hover:shadow-[0_6px_18px_rgba(158,27,50,0.12)]'}`}>
          <span className={`absolute left-3 top-2.5 mono text-[12px] font-semibold ${final ? 'text-white/70' : 'text-brand'}`}>{s.number}</span>
          <span className="absolute right-3 top-2.5">{locked ? <Lock size={14} className="text-white/80" aria-label="Kilitli" /> : null}</span>
          <span className="flex flex-col items-center gap-1.5">
            <Icon size={22} className={final ? 'text-white' : 'text-brand'} aria-hidden />
            <b className="text-[15px] leading-5">{s.number} · {s.title}</b>
            <span className={`text-[13px] ${final ? 'text-white/85' : 'text-ink-3'}`}>{s.semester}</span>
          </span>
        </Link>
        {arrow && <div className="py-1"><Arrow /></div>}
      </div>
      <div className={`pb-6 md:pt-2 ${!arrow ? 'md:pb-0' : ''}`}>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="h3">{s.title}</h3>
          <StatusBadge status={s.status} />
          {final && <span className="chip border-brand bg-white text-brand">Sonraki dönem</span>}
        </div>
        <p className="prose-body mt-1.5 max-w-2xl">{s.summary}</p>
        {!compact && s.deliverable && <p className="mt-1.5 text-[14px] text-ink-2"><b className="text-brand">Çıktı:</b> {s.deliverable}</p>}
        {!compact && s.tasks.length > 0 && (
          <p className="mt-1 text-[13px] text-ink-3"><span className="mono">%{(s.progress ?? 0).toLocaleString('tr-TR')}</span> · {done}/{s.tasks.length} görev tamamlandı</p>
        )}
        <Link to={s.path} className="mt-3 inline-flex items-center gap-1.5 text-[14px] font-semibold text-brand hover:gap-2.5 transition-all">
          Detayları İncele <ArrowRight size={16} aria-hidden />
        </Link>
      </div>
    </li>
  );
}
