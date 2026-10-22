import { Link } from 'react-router-dom';
import { FlaskConical, ListChecks, Boxes, Wallet, ArrowRight, CalendarClock, Upload, ScrollText } from 'lucide-react';
import { AdminPage } from '../ui';
import { usePhases, useTasks, useSimulations, useMaterials, usePurchases, useMediaList, useRecentActivity, useComponents } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { weightedProgress, phaseProgress } from '../../lib/progress';
import { summarize, combinedTRY, type Totals } from '../../lib/costs';
import { useSettings } from '../data';
import { fmtDate, fmtMoneyRange, fmtRelative, todayISO } from '../../lib/format';
import { resultLabels, type ExperimentResult } from '../../lib/labels';
import { Skeleton, ErrorNotice, EmptyState } from '../../components/feedback';
import { ProgressBar } from '../../components/ui';
import { useMediaUrls } from '../../components/MediaGallery';
import { isImage } from '../../lib/files';
import { actionLabel } from './activityLabels';

const TotalsText = ({ t, empty = '—' }: { t: Totals; empty?: string }) => {
  const e = Object.entries(t).filter(([, r]) => r.max > 0);
  return e.length ? <span className="flex flex-col">{e.map(([c, r]) => <span key={c}>{fmtMoneyRange(r.min, r.max, c, 0)}</span>)}</span> : <>{empty}</>;
};

function Kpi({ icon: Icon, label, value, hint, to }: { icon: typeof FlaskConical; label: string; value: React.ReactNode; hint?: React.ReactNode; to?: string }) {
  const body = (
    <>
      <div className="flex items-center justify-between"><span className="text-[12px] font-semibold uppercase tracking-[0.1em] text-brand">{label}</span><Icon size={18} className="text-brand" aria-hidden /></div>
      <div className="mono mt-2 text-[24px] font-bold text-ink">{value}</div>
      {hint && <div className="mt-1 text-[12px] leading-5 text-ink-3">{hint}</div>}
    </>
  );
  return to ? <Link to={to} className="card block p-4 text-ink transition-colors hover:border-brand hover:text-ink">{body}</Link> : <div className="card p-4">{body}</div>;
}

/** Sonuç dağılımı: yığılmış çubuk + etiketli lejant (renk tek başına anlam taşımaz) */
const resultColor: Record<ExperimentResult, string> = { passed: '#047857', failed: '#B91C1C', needs_review: '#0369A1', in_progress: '#B45309', not_started: '#A8A2A4' };

export default function DashboardPage() {
  const auth = useAuth();
  const phases = usePhases(); const tasks = useTasks(); const sims = useSimulations(); const mats = useMaterials();
  const purch = usePurchases(); const media = useMediaList(); const settings = useSettings(); const comps = useComponents();
  const activity = useRecentActivity(auth.canEdit);
  const err = phases.error ?? tasks.error ?? sims.error ?? mats.error ?? purch.error;
  const loading = !phases.data || !tasks.data || !sims.data || !mats.data || !purch.data;

  const P = phases.data ?? [], T = tasks.data ?? [], S = sims.data ?? [], M = mats.data ?? [];
  const ptasks = T.map((t) => ({ status: t.status, weight: t.weight, phase_id: t.phase_id }));
  const forCalc = P.map((p) => ({ id: p.id, weight: p.weight, semester: p.semester }));
  const overall = weightedProgress(forCalc, ptasks);
  const t1 = weightedProgress(forCalc.filter((p) => p.semester === 'tasarim_1'), ptasks);
  const t2 = weightedProgress(forCalc.filter((p) => p.semester === 'tasarim_2'), ptasks);
  const cost = summarize(M.filter((m) => !m.is_programmer_extra), []);
  const spent = summarize(M, purch.data ?? []);
  const rate = settings.data?.usd_try_rate ?? null;
  const combined = combinedTRY(cost.estimated, rate);
  const today = todayISO();
  const pending = T.filter((t) => t.status !== 'completed');
  const overdue = pending.filter((t) => t.due_date && t.due_date < today);
  const upcoming = [
    ...pending.filter((t) => t.due_date && t.due_date >= today).map((t) => ({ id: t.id, date: t.due_date!, title: t.title, kind: 'Görev' })),
    ...P.filter((p) => p.target_date && p.target_date >= today && p.status !== 'completed').map((p) => ({ id: p.id, date: p.target_date!, title: p.title, kind: 'Aşama hedefi' })),
  ].sort((a, b) => a.date.localeCompare(b.date)).slice(0, 6);
  const resCounts = (Object.keys(resultLabels) as ExperimentResult[]).map((k) => ({ k, n: S.filter((s) => s.result_status === k).length }));
  const recentUploads = (media.data ?? []).slice(0, 6);
  const thumbs = useMediaUrls(recentUploads.filter((m) => isImage(m.mime_type)), 320);

  return (
    <AdminPage title="Genel Bakış" description={`Hoş geldiniz${auth.profile?.full_name ? `, ${auth.profile.full_name}` : ''}. Aşağıdaki değerler yalnızca kaydedilmiş verilerden hesaplanır.`}>
      {err && <div className="mb-4"><ErrorNotice error={err} onRetry={() => { void phases.refetch(); void tasks.refetch(); void sims.refetch(); void mats.refetch(); void purch.refetch(); }} /></div>}
      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-28" />)}</div>
      ) : (
        <>
          <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr]">
            <div className="card p-5">
              <div className="flex items-end justify-between gap-3">
                <div><div className="eyebrow">Genel proje tamamlanma</div><div className="mono mt-1 text-[40px] font-bold leading-none">%{overall.value.toLocaleString('tr-TR')}</div></div>
                <Link to="/admin/phases" className="text-[13px] font-semibold">Aşamalar ve ağırlıklar →</Link>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <ProgressBar value={t1.value} label="Tasarım I" />
                <ProgressBar value={t2.value} label="Tasarım II" />
              </div>
              {!overall.weightsValid && <p className="mt-3 rounded bg-amber-50 px-2 py-1 text-[12.5px] text-amber-800">Aşama ağırlıklarının toplamı {overall.weightSum.toLocaleString('tr-TR')}; 100 olacak şekilde güncelleyin.</p>}
              <div className="mt-5 space-y-2" role="list" aria-label="Aşamalara göre ilerleme">
                {P.map((p) => {
                  const v = phaseProgress(p.id, ptasks);
                  const n = T.filter((t) => t.phase_id === p.id);
                  return (
                    <div key={p.id} role="listitem" className="grid grid-cols-[minmax(120px,1fr)_2fr_auto] items-center gap-3 text-[13px]" title={`${p.title}: %${v ?? 0} (${n.filter((t) => t.status === 'completed').length}/${n.length} görev)`}>
                      <span className="truncate text-ink-2">{p.title}</span>
                      <span className="h-2.5 overflow-hidden rounded bg-brand-mist"><span className="block h-full rounded bg-brand" style={{ width: `${v ?? 0}%` }} /></span>
                      <span className="mono w-24 text-right text-ink-3">%{(v ?? 0).toLocaleString('tr-TR')} · {n.filter((t) => t.status === 'completed').length}/{n.length}</span>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="card p-5">
              <div className="flex items-center justify-between"><div className="eyebrow">Simülasyon deneyleri</div><Link to="/admin/simulations" className="text-[13px] font-semibold">Yönet →</Link></div>
              <div className="mono mt-1 text-[32px] font-bold">{S.length}</div>
              {S.length ? (
                <>
                  <div className="mt-3 flex h-3 gap-[2px] overflow-hidden rounded" aria-hidden>
                    {resCounts.filter((r) => r.n).map((r) => <span key={r.k} style={{ width: `${(r.n / S.length) * 100}%`, background: resultColor[r.k] }} title={`${resultLabels[r.k]}: ${r.n}`} />)}
                  </div>
                  <ul className="mt-3 grid grid-cols-2 gap-1.5 text-[13px]">
                    {resCounts.map((r) => <li key={r.k} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: resultColor[r.k] }} aria-hidden /><span className="text-ink-2">{resultLabels[r.k]}</span><b className="mono ml-auto">{r.n}</b></li>)}
                  </ul>
                </>
              ) : <p className="mt-2 text-[13px] text-ink-3">Henüz deney kaydı yok.</p>}
              <p className="mt-3 text-[12px] text-ink-3">Yayımlanan: {S.filter((s) => s.is_published).length} · Taslak: {S.filter((s) => !s.is_published).length}</p>
            </div>
          </div>

          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi icon={ListChecks} label="Bekleyen görev" value={pending.length} hint={`Tamamlanan: ${T.length - pending.length}${overdue.length ? ` · Gecikmiş: ${overdue.length}` : ''}`} to="/admin/tasks" />
            <Kpi icon={Boxes} label="Malzeme adedi" value={`${cost.purchasedQty}/${cost.requiredQty}`} hint={`Tamamı alınan kalem: ${cost.fullyPurchased}/${cost.itemCount}`} to="/admin/materials" />
            <Kpi icon={Wallet} label="Tahmini maliyet" value={<span className="text-[17px]"><TotalsText t={cost.estimated} /></span>}
              hint={combined ? `≈ ${fmtMoneyRange(combined.min, combined.max, 'TRY', 0)} (kayıtlı kur)` : 'Kur kaydı yok; para birimleri ayrı gösterilir'} />
            <Kpi icon={Wallet} label="Kayıtlı harcama" value={<span className="text-[17px]"><TotalsText t={spent.purchased} empty="Henüz yok" /></span>} hint={`${(purch.data ?? []).length} satın alma kaydı`} to="/admin/purchases" />
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            <section className="card p-4" aria-labelledby="yaklasan">
              <h2 id="yaklasan" className="flex items-center gap-2 text-[15px] font-semibold"><CalendarClock size={17} className="text-brand" aria-hidden /> Yaklaşan hedefler</h2>
              {upcoming.length ? (
                <ul className="mt-2 divide-y divide-brand-line/60">
                  {upcoming.map((u) => <li key={u.id} className="flex items-start justify-between gap-2 py-2 text-[13.5px]"><span><b className="font-medium">{u.title}</b><span className="block text-[12px] text-ink-3">{u.kind}</span></span><span className="mono whitespace-nowrap text-[12.5px] text-ink-2">{fmtDate(u.date)}</span></li>)}
                </ul>
              ) : <p className="mt-2 text-[13px] text-ink-3">Hedef tarihi girilmiş bekleyen görev veya aşama yok.</p>}
              {overdue.length > 0 && <Link to="/admin/tasks?durum=overdue" className="mt-2 inline-block text-[13px] font-semibold text-red-700">{overdue.length} gecikmiş görev →</Link>}
            </section>
            <section className="card p-4" aria-labelledby="yuklemeler">
              <h2 id="yuklemeler" className="flex items-center gap-2 text-[15px] font-semibold"><Upload size={17} className="text-brand" aria-hidden /> Son yüklemeler</h2>
              {recentUploads.length ? (
                <ul className="mt-2 grid grid-cols-3 gap-2">
                  {recentUploads.map((m) => (
                    <li key={m.id}><Link to="/admin/media" className="block overflow-hidden rounded-md border border-brand-line bg-brand-mist" title={m.title}>
                      {isImage(m.mime_type) && thumbs.data?.[m.id] ? <img src={thumbs.data[m.id]} alt={m.title} className="aspect-square w-full object-cover" loading="lazy" />
                        : <span className="flex aspect-square items-center justify-center p-1 text-center text-[11px] text-ink-3">{m.original_file_name}</span>}
                    </Link></li>
                  ))}
                </ul>
              ) : <p className="mt-2 text-[13px] text-ink-3">Henüz dosya yüklenmedi.</p>}
            </section>
            <section className="card p-4" aria-labelledby="etkinlik">
              <h2 id="etkinlik" className="flex items-center gap-2 text-[15px] font-semibold"><ScrollText size={17} className="text-brand" aria-hidden /> Son etkinlikler</h2>
              {!auth.canEdit ? <p className="mt-2 text-[13px] text-ink-3">Etkinlik günlüğü yalnızca yönetici ve düzenleyicilere açıktır.</p>
                : activity.data?.length ? (
                  <ul className="mt-2 divide-y divide-brand-line/60">
                    {activity.data.map((a) => <li key={a.id} className="py-2 text-[13px]"><b className="font-medium">{actionLabel(a.action)}</b> · {a.entity_label}<span className="block text-[11.5px] text-ink-3">{a.actor_email ?? 'Sistem'} · {fmtRelative(a.created_at)}</span></li>)}
                  </ul>
                ) : <p className="mt-2 text-[13px] text-ink-3">Henüz etkinlik yok.</p>}
              {auth.canEdit && <Link to="/admin/activity" className="mt-2 inline-flex items-center gap-1 text-[13px] font-semibold">Tüm günlük <ArrowRight size={13} aria-hidden /></Link>}
            </section>
          </div>

          {(comps.data ?? []).length > 0 && T.length === 0 && (
            <div className="mt-6"><EmptyState title="Henüz görev tanımlanmadı">İlerleme yüzdeleri görevlerden hesaplanır. <Link to="/admin/tasks">Görevler</Link> sayfasından görev ekleyin.</EmptyState></div>
          )}
        </>
      )}
    </AdminPage>
  );
}
