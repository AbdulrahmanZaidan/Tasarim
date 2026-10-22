import { Link } from 'react-router-dom';
import { CheckCircle2, Circle, ArrowRight, CircleDot, Ban, CalendarClock, History } from 'lucide-react';
import { useCore, useTimeline, type TaskVM } from '../data/public';
import { PageHeader, StatusBadge, ProgressBar, Callout, Badge } from '../components/ui';
import { iconFor } from '../components/Timeline';
import { EmptyState, Skeleton } from '../components/feedback';
import { MediaGallery } from '../components/MediaGallery';
import DataNotice from '../components/DataNotice';
import { fmtDate } from '../lib/format';
import { phaseStatusLabels, workStatusLabels, workTone, type PhaseStatus } from '../lib/labels';

const taskIcon = (t: TaskVM) =>
  t.status === 'completed' ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-600" aria-label="tamamlandı" />
  : t.status === 'in_progress' ? <CircleDot size={16} className="mt-0.5 shrink-0 text-amber-600" aria-label="devam ediyor" />
  : t.status === 'blocked' ? <Ban size={16} className="mt-0.5 shrink-0 text-red-600" aria-label="engellendi" />
  : <Circle size={16} className="mt-0.5 shrink-0 text-ink-3" aria-label="başlanmadı" />;

function TaskList({ title, tasks, empty }: { title: string; tasks: TaskVM[]; empty: string }) {
  return (
    <div>
      <div className="text-[11px] font-semibold tracking-[0.12em] text-brand">{title}</div>
      {tasks.length ? (
        <ul className="mt-1.5 space-y-1 text-[13.5px]">
          {tasks.map((t) => (
            <li key={t.id} className={`flex gap-1.5 ${t.status === 'completed' ? 'text-ink' : 'text-ink-2'}`}>
              {taskIcon(t)}
              <span>{t.title}
                {t.dueDate && t.status !== 'completed' && <span className="ml-1 text-[11.5px] text-ink-3">(hedef: {fmtDate(t.dueDate)})</span>}
                {t.completedAt && t.status === 'completed' && <span className="ml-1 text-[11.5px] text-ink-3">({fmtDate(t.completedAt)})</span>}
              </span>
            </li>
          ))}
        </ul>
      ) : <p className="mt-1.5 text-[13px] text-ink-3">{empty}</p>}
    </div>
  );
}

export default function ProgressPage() {
  const core = useCore();
  const timeline = useTimeline();
  const { phases, overall, tasarim1, tasarim2, components } = core.data;
  const count = (s: PhaseStatus) => phases.filter((x) => x.status === s).length;
  const statusesShown: PhaseStatus[] = ['completed', 'in_progress', 'planned', 'not_started', ...(count('blocked') ? ['blocked' as const] : [])];
  const allTasks = phases.flatMap((p) => p.tasks);
  const doneTasks = allTasks.filter((t) => t.status === 'completed').length;

  return (
    <>
      <PageHeader eyebrow="Tasarım I · Tasarım II" title="Proje İlerleme Durumu"
        subtitle="Aşamaların güncel durumu, sürmekte olan ve sıradaki görevler ile kayıtlı gelişmeler. Yüzdeler yalnızca tamamlanan görevlerden hesaplanır."
        crumbs={[{ label: 'Proje Planı', to: '/proje' }, { label: 'İlerleme Durumu' }]} />

      <div className="container-x py-8">
        <DataNotice state={core} className="mb-4" />
        <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
          <div className="card p-5">
            <div className="eyebrow">Genel ilerleme</div>
            {core.loading ? <Skeleton className="mt-2 h-12 w-40" /> : (
              <div className="mt-2 flex items-end gap-3"><span className="mono text-[44px] font-bold leading-none text-ink">%{overall.value.toLocaleString('tr-TR')}</span>
                <span className="pb-1 text-[13px] text-ink-3">{doneTasks}/{allTasks.length} görev tamamlandı</span></div>
            )}
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <ProgressBar value={core.loading ? null : tasarim1.value} label="Tasarım I" />
              <ProgressBar value={core.loading ? null : tasarim2.value} label="Tasarım II" />
            </div>
            <div className="mt-5 flex h-3 overflow-hidden rounded-full bg-brand-mist" aria-hidden>
              {phases.map((s) => (
                <div key={s.id} className="h-full border-r-2 border-white last:border-r-0" style={{ width: `${overall.weightSum ? (s.weight / overall.weightSum) * 100 : 100 / phases.length}%` }}>
                  <div className="h-full bg-brand transition-[width] duration-700" style={{ width: `${s.progress ?? 0}%` }} />
                </div>
              ))}
            </div>
            <div className="mt-1.5 flex text-[11px] text-ink-3">
              {phases.map((s) => <span key={s.id} className="mono text-center" style={{ width: `${overall.weightSum ? (s.weight / overall.weightSum) * 100 : 100 / phases.length}%` }}>{s.number}</span>)}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {statusesShown.map((s) => (
              <div key={s} className="card-soft flex flex-col justify-between p-4">
                <StatusBadge status={s} />
                <div className="mono mt-2 text-[28px] font-bold">{count(s)}</div>
                <div className="text-[12px] text-ink-3">aşama · {phaseStatusLabels[s].toLocaleLowerCase('tr-TR')}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4">
          <Callout title="İlerleme nasıl hesaplanır?">
            Her aşamanın yüzdesi, o aşamadaki <b>tamamlanan görevlerin</b> (görev ağırlıklarına göre) oranıdır. Genel ilerleme, aşama yüzdelerinin
            aşama ağırlıklarıyla ({phases.map((p) => `${p.number}: ${p.weight.toLocaleString('tr-TR')}`).join(' · ')}) ağırlıklı ortalamasıdır.
            Elle girilen yüzde kullanılmaz; bir görev ancak ekip tarafından tamamlandı olarak işaretlendiğinde ilerlemeye yansır.
            {!overall.weightsValid && <b className="text-amber-800"> Aşama ağırlıklarının toplamı şu an {overall.weightSum.toLocaleString('tr-TR')}; değerler normalize edilerek hesaplanmıştır.</b>}
          </Callout>
        </div>

        <ol className="mt-8 space-y-4">
          {phases.map((s, i) => {
            const Icon = iconFor(s.slug);
            const t2 = s.semesterKey === 'tasarim_2';
            const inProgress = s.tasks.filter((t) => t.status === 'in_progress' || t.status === 'blocked');
            const next = s.tasks.filter((t) => t.status === 'not_started');
            const done = s.tasks.filter((t) => t.status === 'completed');
            return (
              <li key={s.id} id={`asama-${s.slug}`} className={`card scroll-mt-24 overflow-hidden ${t2 ? 'border-dashed' : ''}`} style={{ animation: `rise .45s ease-out ${i * 70}ms both` }}>
                <div className="grid gap-5 p-5 md:grid-cols-[230px_1fr]">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className={`flex h-11 w-11 items-center justify-center rounded-[10px] ${t2 ? 'bg-brand text-white' : 'border border-brand-line bg-brand-soft text-brand'}`}><Icon size={20} aria-hidden /></span>
                      <div><div className="mono text-[13px] font-semibold text-brand">{s.number} · {s.semester}</div><div className="font-semibold leading-5">{s.title}</div></div>
                    </div>
                    <div className="mt-3"><StatusBadge status={s.status} size="md" /></div>
                    <div className="mt-3"><ProgressBar value={s.tasks.length ? s.progress : null} label={s.tasks.length ? `Tamamlanma · ${done.length}/${s.tasks.length} görev` : 'Görev tanımlanmadı'} /></div>
                    {(s.startDate || s.targetDate) && (
                      <div className="mt-2 flex items-center gap-1 text-[12px] text-ink-3"><CalendarClock size={13} aria-hidden />{fmtDate(s.startDate)} – {fmtDate(s.targetDate)}</div>
                    )}
                    <div className="mt-1 text-[12px] text-ink-3">Son güncelleme: {s.lastUpdated ? fmtDate(s.lastUpdated) : 'belirtilmedi'}</div>
                  </div>
                  <div>
                    <p className="prose-body">{s.summary}</p>
                    <div className="mt-4 grid gap-4 sm:grid-cols-3">
                      <TaskList title="DEVAM EDEN GÖREVLER" tasks={inProgress} empty="Şu an devam eden görev yok." />
                      <TaskList title="SIRADAKİ GÖREVLER" tasks={next} empty={s.tasks.length ? 'Sırada bekleyen görev yok.' : 'Bu aşama için henüz görev tanımlanmadı.'} />
                      <TaskList title="TAMAMLANANLAR" tasks={done} empty="Bu aşama için henüz tamamlanan görev yok." />
                    </div>
                    <Link to={s.path} className="mt-4 inline-flex items-center gap-1.5 text-[14px] font-semibold">Aşama sayfasına git <ArrowRight size={15} aria-hidden /></Link>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>

        <section id="zaman-cizelgesi" className="mt-12 scroll-mt-24">
          <div className="eyebrow">Proje günlüğü</div>
          <h2 className="h2 mt-1.5">Kilometre taşları ve gelişmeler</h2>
          <p className="prose-body mt-2 max-w-3xl">Ekip tarafından kaydedilen gelişmeler tarih sırasıyla listelenir. Yalnızca gerçekleşmiş ve kayda geçirilmiş çalışmalar burada yer alır.</p>
          <div className="mt-6">
            <DataNotice state={timeline} className="mb-4" />
            {timeline.loading ? <Skeleton className="h-32 w-full" /> : timeline.data.updates.length === 0 ? (
              <EmptyState icon={<History size={30} aria-hidden />} title="Bu aşama için henüz ilerleme kaydedilmedi.">
                Ekip gelişmeleri kaydettikçe tarih, açıklama ve fotoğraflarla birlikte burada yayımlanacaktır.
              </EmptyState>
            ) : (
              <ol className="relative space-y-5 border-l-2 border-brand-line pl-6">
                {timeline.data.updates.map((u) => {
                  const phase = phases.find((p) => p.id === u.phase_id);
                  const comp = components.find((c) => c.id === u.component_id);
                  const media = timeline.data.media.filter((m) => m.progress_update_id === u.id);
                  return (
                    <li key={u.id} className="relative">
                      <span className="absolute -left-[33px] top-1 h-4 w-4 rounded-full border-[3px] border-white bg-brand shadow" aria-hidden />
                      <div className="card p-4">
                        <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-ink-3">
                          <time dateTime={u.update_date} className="font-semibold text-brand">{fmtDate(u.update_date)}</time>
                          <Badge tone={workTone[u.status]}>{workStatusLabels[u.status]}</Badge>
                          {phase && <Link to={phase.path} className="chip border-brand-line bg-white text-ink-2 hover:text-brand">{phase.number} · {phase.shortTitle}</Link>}
                          {comp && <Link to={`/proje/bilesen/${comp.slug}`} className="chip border-brand-line bg-white text-ink-2 hover:text-brand">{comp.name}</Link>}
                        </div>
                        <h3 className="mt-1.5 text-[16px] font-semibold">{u.title}</h3>
                        {u.description && <p className="prose-body mt-1 whitespace-pre-line">{u.description}</p>}
                        {media.length > 0 && <div className="mt-3"><MediaGallery items={media} columns={4} showMeta={false} /></div>}
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
