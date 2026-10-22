import { Link } from 'react-router-dom';
import { Lock, CalendarClock, ArrowLeft } from 'lucide-react';
import { useCore } from '../data/public';
import { Breadcrumbs, Callout, StageNav, StatusBadge, Badge, ProgressBar } from '../components/ui';
import DataNotice from '../components/DataNotice';
import { Skeleton } from '../components/feedback';
import { workStatusLabels, workTone } from '../lib/labels';
import { fmtDate } from '../lib/format';

export default function TasarimIIPage() {
  const core = useCore();
  const { phases, settings, tasarim2 } = core.data;
  const t2 = phases.filter((p) => p.semesterKey === 'tasarim_2');
  const stage = t2[0];
  const active = settings.tasarimIIActive;
  const roadmap = t2.flatMap((p) => p.tasks);
  const anyDone = roadmap.some((t) => t.status !== 'not_started');

  return (
    <>
      <header className="pt-8 sm:pt-10">
        <div className="container-x">
          <Breadcrumbs items={[{ label: 'Proje Planı', to: '/proje' }, { label: 'Tasarım II' }]} />
          <div className="relative overflow-hidden rounded-[14px] bg-brand px-6 py-10 text-white sm:px-10 sm:py-12">
            <svg className="pointer-events-none absolute -right-10 -top-10 h-72 w-72 opacity-[0.09]" viewBox="0 0 200 200" aria-hidden>
              {Array.from({ length: 8 }, (_, i) => <rect key={i} x={20 + (i % 4) * 44} y={30 + Math.floor(i / 4) * 80} width="30" height="56" rx="3" fill="#fff" />)}
            </svg>
            <div className="relative">
              <div className="flex items-center gap-3">
                <span className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-white/40 bg-white/10" aria-hidden>
                  {active ? <CalendarClock size={22} /> : <Lock size={22} />}
                </span>
                <span className="text-[12px] font-semibold tracking-[0.16em] text-white/80">AŞAMA {stage?.number ?? '05'} · 2. DÖNEM</span>
              </div>
              <h1 className="mt-4 text-[30px] font-bold leading-tight sm:text-[40px]">Tasarım II — Uygulama ve Gerçekleştirme</h1>
              <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-white px-3.5 py-1 text-[14px] font-semibold text-brand">
                <span className="h-2 w-2 animate-pulse rounded-full bg-brand" aria-hidden />{active ? 'Başladı' : 'Yakında'}
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="container-x py-10">
        <DataNotice state={core} className="mb-6" />
        <div className="grid gap-8 lg:grid-cols-[1.1fr_1fr]">
          <div>
            {stage && <div className="flex items-center gap-2"><span className="eyebrow">Durum</span><StatusBadge status={stage.status} /></div>}
            <p className="lead mt-3">
              Tasarım I kapsamında bilgisayarın mimari tasarımı, devre şemaları, simülasyon çalışmaları ve malzeme hazırlıkları planlanmaktadır.
              Tasarım II aşamasında ise hazırlanan tasarım doğrultusunda bilgisayarın donanım modülleri breadboard üzerinde kurulacak, test edilecek
              ve tek bir sistem hâlinde birleştirilecektir.{' '}
              {active ? 'Bu aşamaya ait çalışmalar başlamıştır; gelişmeler aşağıda ve İlerleme Durumu sayfasında güncellenmektedir.'
                : 'Bu aşamaya ait çalışmalar henüz başlamamıştır. Gelişmeler ilerleyen dönemde bu sayfaya eklenecektir.'}
            </p>
            {active && <div className="mt-5 max-w-sm"><ProgressBar value={tasarim2.value} label="Tasarım II ilerlemesi (görevlerden)" /></div>}
            <div className="mt-6">
              <Callout title={active ? 'Görev durumları' : 'Planlanan çalışmalar'}>
                {active || anyDone
                  ? 'Yol haritasındaki her adımın durumu ekip tarafından kaydedilen görevlerden gelir. Bir adım yalnızca tamamlandı olarak işaretlendiğinde “Tamamlandı” görünür.'
                  : <>Yandaki yol haritası <b>planlanan</b> etkinlikleri göstermektedir; hiçbiri tamamlanmış değildir. Gerçekleşen çalışmalar, kanıtlarıyla (fotoğraf, test kaydı, depo bağlantısı) birlikte eklenecektir.</>}
              </Callout>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/proje" className="btn-outline"><ArrowLeft size={16} aria-hidden /> Tasarım I planına dön</Link>
              <Link to="/proje/ilerleme#zaman-cizelgesi" className="btn-ghost">Proje günlüğü</Link>
            </div>
          </div>

          <div>
            <div className="eyebrow mb-3">{active ? 'Yol haritası' : 'Planlanan yol haritası'}</div>
            {core.loading ? <Skeleton className="h-72 w-full" /> : (
              <ol className="relative space-y-3 before:absolute before:bottom-6 before:left-[19px] before:top-6 before:w-px before:border-l-2 before:border-dashed before:border-brand-line">
                {roadmap.map((r, i) => (
                  <li key={r.id} className="relative flex gap-4" style={{ animation: `rise .45s ease-out ${i * 70}ms both` }}>
                    <span className={`mono relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 text-[14px] font-bold ${r.status === 'completed' ? 'border-emerald-500 bg-emerald-50 text-emerald-700' : 'border-brand-line bg-white text-brand'}`}>{i + 1}</span>
                    <div className="card flex-1 p-3.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <b className="text-[15px]">{r.title}</b>
                        {r.status === 'not_started' && !active
                          ? <span className="chip border-ink-3/25 bg-neutral-100 text-ink-3">Planlandı</span>
                          : <Badge tone={workTone[r.status]}>{workStatusLabels[r.status]}</Badge>}
                      </div>
                      {r.description && <p className="mt-1 text-[13.5px] leading-5 text-ink-3">{r.description}</p>}
                      {r.completedAt && <p className="mt-1 text-[12px] text-ink-3">Tamamlanma: {fmtDate(r.completedAt)}</p>}
                    </div>
                  </li>
                ))}
                {roadmap.length === 0 && <li className="card p-4 text-[14px] text-ink-3">Tasarım II için henüz görev tanımlanmadı.</li>}
              </ol>
            )}
          </div>
        </div>
      </div>
      <StageNav current={stage?.slug ?? 'tasarim2'} />
    </>
  );
}
